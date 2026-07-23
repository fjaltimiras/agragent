#!/usr/bin/env python3
"""
AgrAgent tool-selection evaluation harness.

Runs the labeled benchmark (agent_benchmark.json) through the *production* agent
configuration: the real tool schemas (app.agent.tools.TOOLS), the real system
prompt (app.agent.system_prompt.SYSTEM_PROMPT), the same model and agentic loop
(max 10 iterations). Tool execution is STUBBED with a canned result so that the
evaluation isolates tool-*selection* behavior (which tools the model chooses)
without depending on external data services (GEE, Open-Meteo, Supabase, etc.).

A fixed application-context block is prepended to every query, mirroring the
context injection used in production so that location/crop-dependent tools are
callable.

Outputs:
  eval/results.json   per-query trace (tools called, iterations, latency, text)
  eval/metrics.csv    per-query scores + summary block
Prints a human-readable summary to stdout.

Usage (from the backend directory):
  python3 eval/run_eval.py            # full run (calls the Anthropic API)
  python3 eval/run_eval.py --dry-run  # validate benchmark + scoring, no API calls

Requires ANTHROPIC_API_KEY (read from environment or backend/.env).
"""
import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
EVAL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

MODEL = "claude-sonnet-4-6"
MAX_ITERATIONS = 10
MAX_TOKENS = 1500

# Fixed application-context block (mirrors production context injection) so that
# coordinate/crop-dependent tools have the information they need to be called.
CONTEXT_BLOCK = (
    "[Application context]\n"
    "Active section: Dashboard.\n"
    "Field: 'Demo Vineyard', location: Casablanca, Valparaiso Region, Chile.\n"
    "Coordinates: latitude -33.32, longitude -71.41. Area: 5.0 ha.\n"
    "Crop: grapevine (Vitis vinifera), phenological stage: mid-season.\n"
    "Date: 2026-01-15 (Southern Hemisphere growing season).\n"
    "Irrigation system: drip. Soil texture: loam.\n"
)

STUB_RESULT = json.dumps({
    "status": "ok",
    "note": "Evaluation stub: tool executed successfully; representative payload omitted.",
})


def load_env():
    """Load ANTHROPIC_API_KEY from environment or backend/.env."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    env_path = BACKEND_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k == "ANTHROPIC_API_KEY" and v:
                os.environ["ANTHROPIC_API_KEY"] = v
                return


def block_to_dict(block):
    if block.type == "text":
        return {"type": "text", "text": block.text}
    if block.type == "tool_use":
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    return {"type": block.type}


def run_query(client, tools, system_prompt, query):
    """Run one query through the agentic loop with stubbed tool execution.

    Returns dict with called tools (ordered), unique set, iterations, latency, text.
    """
    messages = [{"role": "user", "content": f"{CONTEXT_BLOCK}\n\nUser question: {query}"}]
    called = []
    iterations = 0
    final_text = ""
    t0 = time.time()
    while iterations < MAX_ITERATIONS:
        iterations += 1
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            tools=tools,
            messages=messages,
        )
        tool_uses = [b for b in resp.content if b.type == "tool_use"]
        if resp.stop_reason != "tool_use" or not tool_uses:
            final_text = "".join(b.text for b in resp.content if b.type == "text")
            break
        for b in tool_uses:
            called.append(b.name)
        messages.append({"role": "assistant", "content": [block_to_dict(b) for b in resp.content]})
        messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": b.id, "content": STUB_RESULT} for b in tool_uses
        ]})
    latency = round(time.time() - t0, 2)
    return {
        "called": called,
        "called_set": sorted(set(called)),
        "iterations": iterations,
        "latency_s": latency,
        "final_text": final_text[:500],
    }


def score_query(q, called_set):
    """Score one query against its labels. Returns dict of booleans/counts."""
    groups = q.get("groups", [])
    gold = set(q.get("gold", []))
    called = set(called_set)
    expect_tool = len(groups) > 0

    if not expect_tool:  # out-of-scope: correct iff no tool called
        return {
            "expect_tool": False,
            "coverage": True if not called else False,
            "no_extraneous": len(called) == 0,
            "correct": len(called) == 0,
            "groups_total": 0,
            "groups_satisfied": 0,
            "called_in_gold": 0,
            "called_total": len(called),
        }

    groups_satisfied = sum(1 for g in groups if any(t in called for t in g))
    coverage = groups_satisfied == len(groups)
    no_extraneous = called.issubset(gold)
    called_in_gold = len(called & gold)
    return {
        "expect_tool": True,
        "coverage": coverage,
        "no_extraneous": no_extraneous,
        "correct": coverage and no_extraneous,
        "groups_total": len(groups),
        "groups_satisfied": groups_satisfied,
        "called_in_gold": called_in_gold,
        "called_total": len(called),
    }


def aggregate(rows):
    n = len(rows)
    correct = sum(r["correct"] for r in rows)
    on_topic = [r for r in rows if r["expect_tool"]]
    oos = [r for r in rows if not r["expect_tool"]]

    groups_total = sum(r["groups_total"] for r in on_topic)
    groups_satisfied = sum(r["groups_satisfied"] for r in on_topic)
    called_total = sum(r["called_total"] for r in rows)
    called_in_gold = sum(r["called_in_gold"] for r in rows)

    recall = groups_satisfied / groups_total if groups_total else 0.0
    precision = called_in_gold / called_total if called_total else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    def acc(subset):
        return sum(r["correct"] for r in subset) / len(subset) if subset else 0.0

    by_lang = {}
    for lang in sorted({r["lang"] for r in rows}):
        sub = [r for r in rows if r["lang"] == lang]
        by_lang[lang] = (sum(r["correct"] for r in sub), len(sub))

    by_cat = {}
    for cat in sorted({r["category"] for r in rows}):
        sub = [r for r in rows if r["category"] == cat]
        by_cat[cat] = (sum(r["correct"] for r in sub), len(sub))

    return {
        "n_queries": n,
        "query_accuracy": correct / n if n else 0.0,
        "on_topic_accuracy": acc(on_topic),
        "abstention_accuracy": acc(oos),
        "tool_precision": precision,
        "group_recall": recall,
        "f1": f1,
        "mean_latency_s": round(sum(r["latency_s"] for r in rows) / n, 2) if n else 0.0,
        "mean_iterations": round(sum(r["iterations"] for r in rows) / n, 2) if n else 0.0,
        "by_lang": by_lang,
        "by_category": by_cat,
    }


def write_cases(results, path):
    """Emit a markdown report of representative success and failure cases.

    Includes ALL failures (correctness == False) and a representative set of
    successes (the first correct query of each category, spanning languages).
    Feeds the qualitative case analysis in the manuscript.
    """
    def gold_str(r):
        return ", ".join(r.get("gold", [])) or "(abstain)"

    def called_str(r):
        return ", ".join(r.get("called_set", [])) or "(none)"

    failures = [r for r in results if not r["score"]["correct"]]

    successes, seen_cat = [], set()
    for r in results:
        if r["score"]["correct"] and r["category"] not in seen_cat:
            successes.append(r)
            seen_cat.add(r["category"])

    lines = ["# Agent tool-selection cases\n",
             f"Total queries: {len(results)} | successes: {len(results) - len(failures)} "
             f"| failures: {len(failures)}\n"]

    lines.append("\n## Representative success cases\n")
    lines.append("| ID | Lang | Category | Query | Expected | Selected |")
    lines.append("|----|------|----------|-------|----------|----------|")
    for r in successes:
        q = r["query"].replace("|", "/")
        lines.append(f"| {r['id']} | {r['lang']} | {r['category']} | {q} | "
                     f"{gold_str(r)} | {called_str(r)} |")

    lines.append("\n## Failure cases (all)\n")
    if not failures:
        lines.append("_No failures: every query was scored correct._")
    else:
        lines.append("| ID | Lang | Category | Query | Expected | Selected | Issue |")
        lines.append("|----|------|----------|-------|----------|----------|-------|")
        for r in failures:
            q = r["query"].replace("|", "/")
            sc = r["score"]
            issue = ("missing coverage" if not sc["coverage"]
                     else "extraneous tool" if not sc["no_extraneous"]
                     else "abstention failure")
            lines.append(f"| {r['id']} | {r['lang']} | {r['category']} | {q} | "
                         f"{gold_str(r)} | {called_str(r)} | {issue} |")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="validate benchmark + scoring without API calls")
    ap.add_argument("--limit", type=int, default=0, help="run only the first N queries")
    ap.add_argument("--sleep", type=float, default=1.0, help="seconds to sleep between queries")
    args = ap.parse_args()

    bench = json.loads((EVAL_DIR / "agent_benchmark.json").read_text())
    queries = bench["queries"]
    if args.limit:
        queries = queries[: args.limit]

    from app.agent.tools import TOOLS
    from app.agent.system_prompt import SYSTEM_PROMPT
    print(f"Loaded {len(TOOLS)} tools, system prompt {len(SYSTEM_PROMPT)} chars, {len(queries)} queries.")

    tool_names = {t["name"] for t in TOOLS}
    # sanity: every gold/group tool exists
    for q in queries:
        for g in q.get("groups", []):
            for t in g:
                assert t in tool_names, f"{q['id']}: unknown tool {t}"

    if args.dry_run:
        # score with empty calls to validate the scoring path
        rows = []
        for q in queries:
            s = score_query(q, [])
            s.update({"id": q["id"], "lang": q["lang"], "category": q["category"],
                      "iterations": 0, "latency_s": 0.0})
            rows.append(s)
        print(json.dumps(aggregate(rows), indent=2))
        print("Dry run OK (no API calls).")
        return

    load_env()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ERROR: ANTHROPIC_API_KEY not set (env or backend/.env).")
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    print(f"anthropic SDK {anthropic.__version__}, model {MODEL}")

    results, rows = [], []
    for i, q in enumerate(queries, 1):
        try:
            trace = run_query(client, TOOLS, SYSTEM_PROMPT, q["query"])
        except Exception as e:  # noqa: BLE001
            print(f"  [{q['id']}] ERROR: {e}")
            trace = {"called": [], "called_set": [], "iterations": 0, "latency_s": 0.0,
                     "final_text": f"ERROR: {e}"}
        s = score_query(q, trace["called_set"])
        s.update({"id": q["id"], "lang": q["lang"], "category": q["category"],
                  "iterations": trace["iterations"], "latency_s": trace["latency_s"]})
        rows.append(s)
        results.append({**q, **trace, "score": {k: s[k] for k in
                       ("correct", "coverage", "no_extraneous")}})
        flag = "OK " if s["correct"] else "XX "
        print(f"  [{i:>2}/{len(queries)}] {flag}{q['id']} ({q['lang']}/{q['category']}) "
              f"-> {trace['called_set']}  iters={trace['iterations']} {trace['latency_s']}s")
        if args.sleep:
            time.sleep(args.sleep)

    summary = aggregate(rows)

    (EVAL_DIR / "results.json").write_text(json.dumps(
        {"model": MODEL, "n_tools": len(TOOLS), "summary": summary, "results": results}, indent=2, ensure_ascii=False))

    with (EVAL_DIR / "metrics.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "lang", "category", "expect_tool", "coverage", "no_extraneous",
                    "correct", "groups_satisfied", "groups_total", "called_total",
                    "called_in_gold", "iterations", "latency_s"])
        for r in rows:
            w.writerow([r["id"], r["lang"], r["category"], r["expect_tool"], r["coverage"],
                        r["no_extraneous"], r["correct"], r["groups_satisfied"], r["groups_total"],
                        r["called_total"], r["called_in_gold"], r["iterations"], r["latency_s"]])
        w.writerow([])
        for k, v in summary.items():
            if isinstance(v, dict):
                w.writerow([k] + [f"{kk}={vv}" for kk, vv in v.items()])
            else:
                w.writerow([k, v])

    write_cases(results, EVAL_DIR / "cases.md")

    print("\n===== SUMMARY =====")
    for k, v in summary.items():
        print(f"{k}: {v}")
    print(f"\nWrote {EVAL_DIR/'results.json'}, {EVAL_DIR/'metrics.csv'}, and {EVAL_DIR/'cases.md'}")


if __name__ == "__main__":
    main()
