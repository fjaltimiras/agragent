#!/usr/bin/env python3
"""
AgrAgent tool-selection evaluation harness — OPEN-WEIGHT edition.

Same benchmark and scoring as run_eval.py, but drives the *production* agent
stack instead of Anthropic: OpenAI-compatible chat.completions against an
open-weight model served by Cerebras (gpt-oss-120b) or Groq
(llama-3.3-70b-versatile), mirroring app/agent/claude.py exactly (OpenAI tool
format, tool_choice="auto", max_tokens=1024, role:"tool" stub results, K=10 loop).

One provider/model is pinned per run so the reported metrics are attributable to
that specific model (no cross-provider fallback here — unlike production, which
falls back for availability). Tool execution is STUBBED to isolate tool
*selection*. The historical Claude metrics.csv is left untouched; outputs are
written to per-model files.

Usage (from the backend directory):
  python3 eval/run_eval_openweight.py --provider cerebras            # gpt-oss-120b
  python3 eval/run_eval_openweight.py --provider groq --sleep 3      # llama-3.3-70b
  python3 eval/run_eval_openweight.py --provider cerebras --dry-run  # no API calls

Requires CEREBRAS_API_KEY / GROQ_API_KEY (environment or backend/.env).
"""
import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
EVAL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

MAX_ITERATIONS = 10
MAX_TOKENS = 1024  # matches production (app/agent/claude.py)

# OpenAI-compatible providers (mirrors app/agent/claude.py). One is pinned per run.
PROVIDERS = {
    "cerebras": {"base_url": "https://api.cerebras.ai/v1", "key_env": "CEREBRAS_API_KEY", "model": "gpt-oss-120b"},
    "groq":     {"base_url": "https://api.groq.com/openai/v1", "key_env": "GROQ_API_KEY", "model": "llama-3.3-70b-versatile"},
}

# Fixed application-context block (identical to run_eval.py) so that
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

# Some open-weight models (notably Llama 3.3 70B via Groq) "leak" a tool call as
# text — e.g. `<function=get_climate_data{"latitude": "-33.32"}</function>` — which
# Groq surfaces as a 400 `tool_use_failed` with a `failed_generation` field, and
# other backends surface as plain assistant content. The model HAS selected the
# right tool; only the wire format is wrong. To measure the model's actual
# tool-selection ability (not an API-format bug), we recover these — the same fix
# used in the production INIA open-weight stack — and count recoveries so the
# reliance on leaked-call recovery is reported transparently.
# Match a leaked call regardless of the delimiter the model chose after the name
# (`>` or `(`), then find the JSON args object inside the block. Covers both
# observed Groq/Llama forms: `<function=name>{...}</function>` and
# `<function=name({...})</function>`, plus `<tool_call>{"name":...}</tool_call>`.
_FUNC_RE = re.compile(r"<function\s*=\s*([a-zA-Z_][a-zA-Z0-9_]*)(.*?)</function>", re.DOTALL)
_TOOLCALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
_recovered = {"count": 0}


def extract_leaked_calls(text):
    """Return [(name, args_dict), ...] from leaked tool-call blocks in text."""
    out = []
    for m in _FUNC_RE.finditer(text or ""):
        name = m.group(1)
        jm = _JSON_RE.search(m.group(2) or "")
        try:
            args = json.loads(jm.group(0)) if jm else {}
        except Exception:
            args = {}
        out.append((name, args))
    for m in _TOOLCALL_RE.finditer(text or ""):
        try:
            obj = json.loads(m.group(1))
            if isinstance(obj, dict) and obj.get("name"):
                out.append((obj["name"], obj.get("arguments", {})))
        except Exception:
            pass
    return out


def failed_generation_text(err):
    """Pull the `failed_generation` string out of a Groq tool_use_failed 400."""
    body = getattr(err, "body", None)
    if isinstance(body, dict):
        e = body.get("error", body)
        if isinstance(e, dict) and e.get("failed_generation"):
            return e["failed_generation"]
    return str(err)


def load_env(key_env):
    """Load the given API key from environment or backend/.env."""
    if os.environ.get(key_env):
        return
    env_path = BACKEND_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k == key_env and v:
                os.environ[key_env] = v
                return


def make_completion(client, model, messages, tools):
    """chat.completions.create with 3x linear backoff on rate limits."""
    from openai import RateLimitError
    last = None
    for attempt in range(1, 4):
        try:
            kwargs = {"model": model, "messages": messages, "max_tokens": MAX_TOKENS}
            if tools:  # the no-tools baseline offers none; the param must be omitted
                kwargs.update(tools=tools, tool_choice="auto")
            return client.chat.completions.create(**kwargs)
        except RateLimitError as e:
            last = e
            if attempt < 3:
                time.sleep(attempt * 3)
                continue
            raise
    raise last


def run_query(client, model, tools, system_prompt, query, max_iterations=MAX_ITERATIONS):
    """Run one query through the agentic loop with stubbed tool execution.

    Mirrors app/agent/claude.py: system prompt as first message, OpenAI tool
    format, assistant turn rebuilt with tool_calls, results returned as
    role:"tool" messages. Returns called tools (ordered), unique set,
    iterations, latency, and final text.

    max_iterations caps the loop: the production value is MAX_ITERATIONS (10);
    the single-call baseline passes 1 so that no round follows the tool results.
    """
    from openai import BadRequestError
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{CONTEXT_BLOCK}\n\nUser question: {query}"},
    ]
    called = []
    iterations = 0
    final_text = ""
    t0 = time.time()
    while iterations < max_iterations:
        iterations += 1
        try:
            resp = make_completion(client, model, messages, tools)
        except BadRequestError as e:
            # Groq tool_use_failed: the model emitted the call as text. Recover it.
            leaked = extract_leaked_calls(failed_generation_text(e))
            if leaked:
                _recovered["count"] += len(leaked)
                called.extend(name for name, _ in leaked)
                final_text = "[recovered leaked tool call]"
                break
            raise
        msg = resp.choices[0].message
        tool_calls = msg.tool_calls or []

        if not tool_calls:
            final_text = msg.content or ""
            # some backends leak the call into plain content; recover it too
            leaked = extract_leaked_calls(final_text)
            if leaked:
                _recovered["count"] += len(leaked)
                called.extend(name for name, _ in leaked)
            break

        called.extend(tc.function.name for tc in tool_calls)
        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in tool_calls
            ],
        })
        for tc in tool_calls:
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": STUB_RESULT})

    latency = round(time.time() - t0, 2)
    return {
        "called": called,
        "called_set": sorted(set(called)),
        "iterations": iterations,
        "latency_s": latency,
        "final_text": final_text[:500],
    }


ROUTER_PROMPT = (
    "You are an intent router for an agronomic assistant. Given a user question, "
    "decide which of the following tools should be called to answer it.\n\n"
    "{catalogue}\n\n"
    "Reply with a JSON array of tool names and nothing else, for example "
    '["get_climate_data"]. If the question is a greeting, off-topic, or answerable '
    "without any of these tools, reply with an empty array []."
)


def run_router_query(client, model, tool_specs, tool_names, query):
    """Non-agentic router baseline: one call, no tool-calling API, no loop.

    The model is asked to name the tools it would call, as a plain intent
    classifier would. Names are parsed out of the reply and scored with the
    same rubric as the agentic runs, so the numbers are comparable by
    construction.
    """
    catalogue = "\n".join(
        f"- {t['function']['name']}: {t['function']['description'].splitlines()[0][:150]}"
        for t in tool_specs
    )
    t0 = time.time()
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": ROUTER_PROMPT.format(catalogue=catalogue)},
            {"role": "user", "content": f"{CONTEXT_BLOCK}\n\nUser question: {query}"},
        ],
        max_tokens=MAX_TOKENS,
    )
    text = resp.choices[0].message.content or ""
    # Accept any known tool name appearing in the reply: models wrap the array in
    # prose or code fences often enough that strict JSON parsing loses real hits.
    called = [n for n in tool_names if re.search(rf"\b{re.escape(n)}\b", text)]
    return {
        "called": called,
        "called_set": sorted(set(called)),
        "iterations": 1,
        "latency_s": round(time.time() - t0, 2),
        "final_text": text[:500],
    }


# ---- scoring / aggregation / cases: identical to run_eval.py ----------------

def score_query(q, called_set):
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

    lat = sorted(r["latency_s"] for r in rows)
    median_latency = lat[len(lat) // 2] if lat else 0.0

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
        "median_latency_s": median_latency,
        "mean_iterations": round(sum(r["iterations"] for r in rows) / n, 2) if n else 0.0,
        "by_lang": by_lang,
        "by_category": by_cat,
    }


def write_cases(results, path):
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
    ap.add_argument("--provider", choices=list(PROVIDERS), default="cerebras",
                    help="which OpenAI-compatible provider/model to evaluate")
    ap.add_argument("--model", default=None, help="override the provider's default model id")
    ap.add_argument("--dry-run", action="store_true", help="validate benchmark + scoring without API calls")
    ap.add_argument("--limit", type=int, default=0, help="run only the first N queries")
    ap.add_argument("--sleep", type=float, default=1.0, help="seconds to sleep between queries")
    ap.add_argument("--timeout", type=float, default=90.0, help="per-request timeout in seconds")
    ap.add_argument("--mode", choices=["agentic", "single", "router", "notools"], default="agentic",
                    help="agentic: production loop (K=10). single: K=1, no round after the tool "
                         "results. router: one call, no tool-calling API, names parsed from text. "
                         "notools: no tools offered, free-text answer (not comparable on the "
                         "tool-selection rubric: it scores 0 by construction).")
    args = ap.parse_args()

    prov = PROVIDERS[args.provider]
    model = args.model or prov["model"]
    slug = f"{args.provider}_{model.replace('/', '-').replace('.', '')}"
    if args.mode != "agentic":
        slug += f"_{args.mode}"

    bench = json.loads((EVAL_DIR / "agent_benchmark.json").read_text())
    queries = bench["queries"]
    if args.limit:
        queries = queries[: args.limit]

    from app.agent.tools import TOOLS
    from app.agent.system_prompt import SYSTEM_PROMPT
    tools = [
        {"type": "function",
         "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
        for t in TOOLS
    ]
    print(f"Loaded {len(TOOLS)} tools, system prompt {len(SYSTEM_PROMPT)} chars, {len(queries)} queries.")

    tool_names = {t["name"] for t in TOOLS}
    for q in queries:
        for g in q.get("groups", []):
            for t in g:
                assert t in tool_names, f"{q['id']}: unknown tool {t}"

    if args.dry_run:
        rows = []
        for q in queries:
            s = score_query(q, [])
            s.update({"id": q["id"], "lang": q["lang"], "category": q["category"],
                      "iterations": 0, "latency_s": 0.0})
            rows.append(s)
        print(json.dumps(aggregate(rows), indent=2))
        print("Dry run OK (no API calls).")
        return

    load_env(prov["key_env"])
    if not os.environ.get(prov["key_env"]):
        sys.exit(f"ERROR: {prov['key_env']} not set (env or backend/.env).")

    from openai import OpenAI
    # Per-request timeout so a single pathological query can't hang the run;
    # on timeout the query is recorded as an error and the run proceeds.
    client = OpenAI(base_url=prov["base_url"], api_key=os.environ[prov["key_env"]],
                    timeout=args.timeout, max_retries=1)
    print(f"provider={args.provider} base_url={prov['base_url']} model={model} timeout={args.timeout}s")

    offered = [] if args.mode == "notools" else tools
    max_iters = 1 if args.mode in ("single", "notools") else MAX_ITERATIONS
    print(f"mode={args.mode} tools_offered={len(offered)} max_iterations={max_iters}")

    results, rows = [], []
    for i, q in enumerate(queries, 1):
        try:
            if args.mode == "router":
                trace = run_router_query(client, model, tools, sorted(tool_names), q["query"])
            else:
                trace = run_query(client, model, offered, SYSTEM_PROMPT, q["query"],
                                  max_iterations=max_iters)
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
    summary["provider"] = args.provider
    summary["model"] = model
    summary["mode"] = args.mode
    summary["max_iterations"] = max_iters
    summary["recovered_leaked_toolcalls"] = _recovered["count"]

    (EVAL_DIR / f"results_{slug}.json").write_text(json.dumps(
        {"provider": args.provider, "model": model, "mode": args.mode,
         "n_tools": len(offered), "summary": summary, "results": results},
        indent=2, ensure_ascii=False))

    with (EVAL_DIR / f"metrics_{slug}.csv").open("w", newline="") as f:
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

    write_cases(results, EVAL_DIR / f"cases_{slug}.md")

    print("\n===== SUMMARY =====")
    for k, v in summary.items():
        print(f"{k}: {v}")
    if _recovered["count"]:
        print(f"\nNOTE: recovered {_recovered['count']} leaked tool call(s) emitted as text "
              f"(open-weight function-calling format quirk; counted as tool selections).")
    print(f"\nWrote results_{slug}.json, metrics_{slug}.csv, cases_{slug}.md")


if __name__ == "__main__":
    main()
