#!/usr/bin/env python3
"""Build blind rating workbooks for the expert-panel evaluation (see PROTOCOL.md).

Reads the assistant's real answers from an eval results file and emits one CSV per rater with the
score columns left empty. Out-of-scope queries are dropped (abstention is measured objectively).
Rows are shuffled per rater with a recorded seed so the ordering is reproducible but not shared.

No score is ever written by this script.
"""
import argparse
import csv
import json
import random
from pathlib import Path

ITEMS = ["factual", "complete", "safe", "grounded"]
HEADER = ["row", "answer_id", "lang", "query", "answer"] + ITEMS + ["hallucination", "comment"]
OOS = {"out_of_scope", "out-of-scope", "oos"}


def load_answers(path):
    data = json.loads(Path(path).read_text(encoding="utf8"))
    records = data if isinstance(data, list) else data.get("results", data.get("queries", []))
    out = []
    for r in records:
        if str(r.get("category", "")).lower().replace(" ", "_") in OOS:
            continue
        text = (r.get("final_text") or "").strip()
        if not text:
            continue
        out.append({
            "answer_id": r["id"],
            "lang": r.get("lang", ""),
            "category": r.get("category", ""),
            "query": r.get("query", "").strip(),
            "answer": text,
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True, help="eval results_*.json with final_text fields")
    ap.add_argument("--raters", type=int, default=3)
    ap.add_argument("--sample", type=int, default=0,
                    help="stratified sample size (0 = use every on-topic answer)")
    ap.add_argument("--seed", type=int, default=20260722)
    ap.add_argument("--outdir", default=".")
    args = ap.parse_args()

    answers = load_answers(args.results)
    if not answers:
        raise SystemExit("no on-topic answers with final_text found")

    rng = random.Random(args.seed)
    if args.sample and args.sample < len(answers):
        by_cat = {}
        for a in answers:
            by_cat.setdefault(a["category"], []).append(a)
        per_cat = max(1, args.sample // max(1, len(by_cat)))
        picked = []
        for cat in sorted(by_cat):
            pool = sorted(by_cat[cat], key=lambda a: a["answer_id"])
            picked += rng.sample(pool, min(per_cat, len(pool)))
        remaining = [a for a in answers if a not in picked]
        rng.shuffle(remaining)
        picked += remaining[: max(0, args.sample - len(picked))]
        answers = picked

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    for i in range(1, args.raters + 1):
        rows = answers[:]
        random.Random(args.seed + i).shuffle(rows)
        path = outdir / f"panel_workbook_rater{i}.csv"
        with path.open("w", newline="", encoding="utf8") as fh:
            w = csv.writer(fh)
            w.writerow(HEADER)
            for n, a in enumerate(rows, 1):
                # category is deliberately omitted from the rater's view to avoid priming
                w.writerow([n, a["answer_id"], a["lang"], a["query"], a["answer"]]
                           + [""] * len(ITEMS) + ["", ""])
        print(f"wrote {path} ({len(rows)} answers)")

    cfg = {
        "results_file": str(args.results),
        "n_answers": len(answers),
        "raters": args.raters,
        "sample_requested": args.sample or None,
        "seed": args.seed,
        "items": ITEMS,
        "scale": "1-5 Likert; hallucination is yes/no",
        "note": "Scores are blank by design. No rating may be generated programmatically.",
    }
    (outdir / "panel_config.json").write_text(json.dumps(cfg, indent=2), encoding="utf8")
    print(f"wrote {outdir/'panel_config.json'}")


if __name__ == "__main__":
    main()
