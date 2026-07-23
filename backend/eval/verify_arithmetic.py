#!/usr/bin/env python3
"""Deterministic arithmetic-correctness check for AgrAgent's quantitative tools.

Unlike ``run_eval.py`` (which measures *tool selection* with a stubbed executor),
this harness exercises the *production* numeric implementations of the irrigation
and fertilization tools and checks their outputs against independently computed
FAO-56 / mass-balance references. It requires no LLM and no network: it imports
``AgroAgent._calculate_irrigation`` and ``AgroAgent._calculate_fertilization``
directly and recomputes the expected values in this file from first principles.

Checks:
  Irrigation (FAO-56):
    - ET_c = K_c x ET_0                                 (crop water demand)
    - I_gross = I_net / eta                              (system efficiency, Eq. 7)
    - weekly gross depth = (7 x ET_c) / eta
  Fertilization (mass balance):
    - total N/P2O5/K2O = uptake_per_ton x yield_target
    - scheduled N across all applications == total N     (no over/under-dosing;
      this is the FAO-style nutrient-budget closure the reviewer asked for)

Run from the backend directory:
    python3 eval/verify_arithmetic.py
Outputs eval/arithmetic_results.csv and prints a summary table.
"""

import csv
import os
import sys

# Make the backend package importable when run from backend/ or eval/.
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.agent.claude import (  # noqa: E402
    AgroAgent,
    KC_TABLE,
    SOIL_AWC,
    IRRIGATION_EFFICIENCY,
    NPK_PER_TON,
    STAGE_ALIASES,
)

TOL_MM = 0.15      # mm tolerance (absolute) for irrigation depths
TOL_KG = 0.2       # kg/ha tolerance (absolute) for nutrient masses
REL_TOL = 0.02     # 2% relative tolerance for the N-budget closure


def _close(actual, expected, tol):
    return abs(actual - expected) <= tol


# ---------------------------------------------------------------------------
# Irrigation cases (crop, stage, soil, system, et0)
# ---------------------------------------------------------------------------
IRRIGATION_CASES = [
    ("grapevine-veraison-drip", "default", "mid_season", "franco", "goteo", 4.2),
    ("tomate-mid-drip",         "tomate",  "mid_season", "franco", "goteo", 5.0),
    ("maiz-mid-sprinkler",      "maiz",    "mid_season", "arcilloso", "aspersion", 6.0),
    ("trigo-dev-furrow",        "trigo",   "development", "franco", "surcos", 3.5),
    ("papa-late-flood",         "papa",    "late_season", "arenoso", "inundacion", 4.0),
    ("lechuga-init-drip",       "lechuga", "initial",    "franco", "goteo", 3.0),
]


def check_irrigation():
    agent = AgroAgent.__new__(AgroAgent)  # skip __init__ (no LLM/GEE clients needed)
    rows = []
    for cid, crop, stage, soil, system, et0 in IRRIGATION_CASES:
        out = AgroAgent._calculate_irrigation(agent, {
            "crop_type": crop,
            "growth_stage": stage,
            "soil_type": soil,
            "irrigation_system": system,
            "et0": et0,
            "area_ha": 1.0,
        })
        # Reference values recomputed independently.
        kc_stage = STAGE_ALIASES.get(stage, "mid_season")
        kc_ref = KC_TABLE.get(crop, KC_TABLE["default"]).get(
            kc_stage, KC_TABLE.get(crop, KC_TABLE["default"])["mid_season"])
        eta_ref = IRRIGATION_EFFICIENCY.get(system, IRRIGATION_EFFICIENCY["default"])
        etc_ref = round(et0 * kc_ref, 2)
        net_ref = out["net_irrigation_depth_mm"]           # soil-reservoir (AWC x MAD)
        gross_ref = round(net_ref / eta_ref, 1)
        weekly_etc_ref = round(etc_ref * 7, 1)             # weekly net ET demand (mm)
        weekly_gross_ref = round(weekly_etc_ref * 10 / eta_ref, 1)  # m3/ha gross

        etc_ok = _close(out["etc_daily_mm"], etc_ref, 0.01)
        gross_ok = _close(out["gross_irrigation_depth_mm"], gross_ref, TOL_MM)
        weekly_ok = _close(out["weekly_volume_per_ha_m3"], weekly_gross_ref, TOL_MM)
        passed = etc_ok and gross_ok and weekly_ok
        rows.append({
            "id": cid, "tool": "irrigation", "system": system,
            "kc": kc_ref, "et0": et0, "etc_expected": etc_ref, "etc_actual": out["etc_daily_mm"],
            "gross_expected": gross_ref, "gross_actual": out["gross_irrigation_depth_mm"],
            "pass": passed,
            "detail": f"etc={etc_ok} gross={gross_ok} weekly={weekly_ok}",
        })
    return rows


# ---------------------------------------------------------------------------
# Fertilization cases (crop, yield_target t/ha, irrigation_type, cycle_days)
# ---------------------------------------------------------------------------
FERTILIZATION_CASES = [
    ("tomate-60t-drip",   "tomate", 60.0, "goteo", 120),
    ("maiz-12t-drip",     "maiz",   12.0, "goteo", 140),
    ("trigo-8t-furrow",   "trigo",   8.0, "surcos", 150),
    ("papa-45t-sprink",   "papa",   45.0, "aspersion", 120),
    ("lechuga-40t-drip",  "lechuga",40.0, "goteo", 80),
    ("soya-4t-furrow",    "soya",    4.0, "surcos", 130),
]


def check_fertilization():
    agent = AgroAgent.__new__(AgroAgent)
    rows = []
    for cid, crop, ytar, irr, cycle in FERTILIZATION_CASES:
        out = AgroAgent._calculate_fertilization(agent, {
            "crop_type": crop,
            "yield_target": ytar,
            "irrigation_type": irr,
            "cycle_days": cycle,
            "area_ha": 1.0,
        })
        req = NPK_PER_TON.get(crop, NPK_PER_TON["default"])
        n_ref = round(req["N"] * ytar, 1)
        p_ref = round(req["P2O5"] * ytar, 1)
        k_ref = round(req["K2O"] * ytar, 1)
        totals = out["total_requirements_kg_ha"]
        mass_ok = (
            _close(totals["N"], n_ref, TOL_KG)
            and _close(totals["P2O5"], p_ref, TOL_KG)
            and _close(totals["K2O"], k_ref, TOL_KG)
        )
        # N-budget closure: scheduled N must equal total N (no double counting).
        scheduled_n = out["scheduled_nitrogen_kg_ha"]
        budget_ok = _close(scheduled_n, n_ref, max(TOL_KG, REL_TOL * n_ref))
        passed = mass_ok and budget_ok
        rows.append({
            "id": cid, "tool": "fertilization", "system": irr,
            "kc": "", "et0": "", "etc_expected": "", "etc_actual": "",
            "gross_expected": "", "gross_actual": "",
            "pass": passed,
            "detail": (
                f"N_total={totals['N']}/{n_ref} mass={mass_ok} "
                f"scheduled_N={scheduled_n}/{n_ref} budget={budget_ok}"
            ),
        })
    return rows


def main():
    rows = check_irrigation() + check_fertilization()
    out_path = os.path.join(_HERE, "arithmetic_results.csv")
    fields = ["id", "tool", "system", "kc", "et0", "etc_expected", "etc_actual",
              "gross_expected", "gross_actual", "pass", "detail"]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    irr = [r for r in rows if r["tool"] == "irrigation"]
    fer = [r for r in rows if r["tool"] == "fertilization"]
    irr_pass = sum(r["pass"] for r in irr)
    fer_pass = sum(r["pass"] for r in fer)
    total_pass = irr_pass + fer_pass

    print("\n=== AgrAgent arithmetic-correctness check ===")
    for r in rows:
        mark = "PASS" if r["pass"] else "FAIL"
        print(f"  [{mark}] {r['tool']:13s} {r['id']:22s} {r['detail']}")
    print("\nSummary:")
    print(f"  Irrigation:    {irr_pass}/{len(irr)} passed")
    print(f"  Fertilization: {fer_pass}/{len(fer)} passed")
    print(f"  Overall:       {total_pass}/{len(rows)} passed")
    print(f"  Results written to {out_path}")
    return 0 if total_pass == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
