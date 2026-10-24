// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 Francisco Altimiras. See LICENSING.md.
//
// Tool-selection evaluation of the assistant, using the same system prompt, tool schemas and loop limits
// as api/chat-stream.js. Tool execution is stubbed so that only *selection* is measured; the arithmetic of
// the quantitative tools is checked separately by verify_arithmetic.mjs.
//
//   CEREBRAS_API_KEY=… node eval/run_tool_selection.mjs --provider cerebras --model gpt-oss-120b
//   GROQ_API_KEY=…     node eval/run_tool_selection.mjs --provider groq --model openai/gpt-oss-120b
//   node eval/run_tool_selection.mjs --dry-run                     # validates benchmark and scoring only
//
// Options: --mode agentic|planned|single|router  --limit N  --sleep S (seconds between queries)  --benchmark FILE  --tag NAME
// Modes: agentic = the deployed loop without the planning step (prompt B); planned = plan-then-act, the deployed
// agent (api/_planner.js + loop); single = one model turn; router = the planning step alone.
// One provider/model is pinned per run (no fallback), so every number is attributable to one model.
// Each answered query is appended to eval/runs/<slug>.jsonl; re-running resumes where it stopped, which
// matters on free tiers that rate-limit (HTTP 429). Summary: eval/results/<slug>.json and <slug>.md.
import { createRequire } from 'node:module';
import { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

process.env.SUPABASE_URL ||= 'https://not-used.invalid';
process.env.SUPABASE_SERVICE_ROLE_KEY ||= 'not-used';
const require = createRequire(import.meta.url);
const { SYSTEM_PROMPT, GROQ_TOOLS } = require('../api/chat-stream.js').internals;
const { planTools, planDirective, PLANNER_PROMPT, catalogueOf } = require('../api/_planner.js');
const HERE = dirname(fileURLToPath(import.meta.url));

const PROVIDERS = {
  cerebras: { url: 'https://api.cerebras.ai/v1/chat/completions', key: 'CEREBRAS_API_KEY', model: 'gpt-oss-120b' },
  groq:     { url: 'https://api.groq.com/openai/v1/chat/completions', key: 'GROQ_API_KEY', model: 'openai/gpt-oss-120b' },
};
const MAX_ITERATIONS = 6;     // same as the loop in api/chat-stream.js
const MAX_TOKENS = 1024;      // same as api/chat-stream.js
const AUX_TOOLS = new Set(['geocode_place']);   // auxiliary lookup, not a labelled intent (see benchmark _about)

// Fixed application context, in the format app.html appends after the user's question.
const APP_CONTEXT = [
  '[App Context: All computed data from agragent platform]',
  'Language: en. Crop: grapevine (Vitis vinifera). Today: 2026-01-15. Current season: 2025-26 (southern hemisphere).',
  'Field location: Casablanca, Valparaíso Region, Chile',
  'Field area: 5.0 ha (5.00 hectares). Centroid: latitude -33.32, longitude -71.41.',
  'Irrigation system: drip. Soil texture: loam. Current phenological stage (projected): berry growth.',
  '[/App Context]',
].join('\n');
const STUB = JSON.stringify({ status: 'ok', note: 'Evaluation stub: tool executed successfully; payload omitted.' });
const LANG_NAMES = { en: 'English', es: 'Spanish (Español)', pt: 'Portuguese (Português)' };
const langDirective = l => `\n\n## CRITICAL LANGUAGE RULE\nThe user interface is set to **${LANG_NAMES[l]}**. You MUST reply ENTIRELY in ${LANG_NAMES[l]} — every sentence, every question, every word. Do NOT mix languages. Do NOT switch to Spanish if the user is using English or Portuguese. This rule overrides any default behavior.`;

// The router ablation uses the same prompt and catalogue as the planner of the deployed agent (api/_planner.js).
const ROUTER_PROMPT = PLANNER_PROMPT;

// ── CLI ──
const argv = process.argv.slice(2);
const opt = (name, def) => { const i = argv.indexOf('--' + name); return i >= 0 ? argv[i + 1] : def; };
const flag = name => argv.includes('--' + name);
const providerName = opt('provider', 'cerebras');
const prov = PROVIDERS[providerName];
if (!prov) throw new Error('unknown provider ' + providerName);
const model = opt('model', prov.model);
const mode = opt('mode', 'agentic');
const limit = +opt('limit', 0);
const sleepS = +opt('sleep', 1);
const benchFile = opt('benchmark', join(HERE, 'benchmark.json'));
const tag = opt('tag', '');   // labels a run made with a different prompt version, e.g. --tag promptA
const slug = `${providerName}_${model.replace(/[/.]/g, '-')}_${mode}${tag ? '_' + tag : ''}`;

const bench = JSON.parse(readFileSync(benchFile, 'utf8'));
let queries = bench.queries;
if (limit) queries = queries.slice(0, limit);
const toolNames = new Set(GROQ_TOOLS.map(t => t.function.name));
for (const q of queries) for (const g of q.groups) for (const t of g) {
  if (!toolNames.has(t)) throw new Error(`${q.id}: tool ${t} is not offered by the agent`);
}

// ── Scoring (same rubric as the v1 harness) ──
function score(q, calledList) {
  const called = new Set(calledList);
  if (!q.groups.length) {
    return { expect_tool: false, coverage: called.size === 0, no_extraneous: called.size === 0, correct: called.size === 0,
      groups_total: 0, groups_satisfied: 0, called_in_gold: 0, called_total: called.size };
  }
  for (const t of AUX_TOOLS) called.delete(t);
  const gold = new Set(q.gold);
  const satisfied = q.groups.filter(g => g.some(t => called.has(t))).length;
  const coverage = satisfied === q.groups.length;
  const noExtra = [...called].every(t => gold.has(t));
  return { expect_tool: true, coverage, no_extraneous: noExtra, correct: coverage && noExtra,
    groups_total: q.groups.length, groups_satisfied: satisfied,
    called_in_gold: [...called].filter(t => gold.has(t)).length, called_total: called.size };
}

function wilson(k, n, z = 1.96) {
  if (!n) return [0, 0];
  const p = k / n, d = 1 + z * z / n, c = p + z * z / (2 * n), m = z * Math.sqrt(p * (1 - p) / n + z * z / (4 * n * n));
  return [(c - m) / d, (c + m) / d];
}

function aggregate(rows) {
  const n = rows.length, sumBy = (a, f) => a.reduce((s, r) => s + f(r), 0);
  const on = rows.filter(r => r.score.expect_tool), oos = rows.filter(r => !r.score.expect_tool);
  const correct = sumBy(rows, r => +r.score.correct);
  const gT = sumBy(on, r => r.score.groups_total), gS = sumBy(on, r => r.score.groups_satisfied);
  const cT = sumBy(rows, r => r.score.called_total), cG = sumBy(rows, r => r.score.called_in_gold);
  const recall = gT ? gS / gT : 0, precision = cT ? cG / cT : 0;
  const by = key => Object.fromEntries([...new Set(rows.map(r => r[key]))].sort().map(v => {
    const s = rows.filter(r => r[key] === v); return [v, [sumBy(s, r => +r.score.correct), s.length]];
  }));
  const lat = rows.map(r => r.latency_s).sort((a, b) => a - b);
  return {
    n_queries: n, correct, query_accuracy: n ? correct / n : 0, query_accuracy_wilson95: wilson(correct, n),
    on_topic_accuracy: on.length ? sumBy(on, r => +r.score.correct) / on.length : 0,
    abstention: [sumBy(oos, r => +r.score.correct), oos.length],
    tool_precision: precision, group_recall: recall, f1: precision + recall ? 2 * precision * recall / (precision + recall) : 0,
    median_latency_s: lat.length ? lat[Math.floor(lat.length / 2)] : 0,
    mean_iterations: n ? +(sumBy(rows, r => r.iterations) / n).toFixed(2) : 0,
    recovered_leaked_calls: sumBy(rows, r => r.recovered || 0),
    by_lang: by('lang'), by_category: by('category'),
  };
}

// ── Model calls ──
const sleep = s => new Promise(ok => setTimeout(ok, s * 1000));
const fingerprints = new Set();

async function complete(body) {
  for (let attempt = 1; ; attempt++) {
    const res = await fetch(prov.url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${process.env[prov.key]}` },
      body: JSON.stringify({ ...body, model, stream: false }),
      signal: AbortSignal.timeout(90000),
    });
    if (res.status === 429 && attempt < 6) { await sleep(Math.min(120, 10 * 2 ** (attempt - 1))); continue; }
    const text = await res.text();
    if (!res.ok) { const e = new Error(`HTTP ${res.status}: ${text.slice(0, 300)}`); e.status = res.status; e.body = text; throw e; }
    const data = JSON.parse(text);
    if (data.system_fingerprint) fingerprints.add(data.system_fingerprint);
    return data.choices[0].message;
  }
}

// Some models emit a tool call as text (e.g. `<function=get_climate_data{...}</function>`); the model did
// select the tool, only the wire format is wrong. Recovered calls are counted and reported.
function leakedCalls(text) {
  const out = [];
  for (const m of String(text || '').matchAll(/<function\s*=\s*([A-Za-z_]\w*)/g)) out.push(m[1]);
  for (const m of String(text || '').matchAll(/<tool_call>\s*(\{[\s\S]*?\})\s*<\/tool_call>/g)) {
    try { const o = JSON.parse(m[1]); if (o.name) out.push(o.name); } catch (e) { /* ignore */ }
  }
  // Groq rejects a call whose arguments fail schema validation (HTTP 400 tool_use_failed) and returns the
  // attempted call in error.failed_generation: the tool was selected, its arguments were invalid.
  try {
    const fg = JSON.parse(text).error?.failed_generation;
    if (fg) for (const m of String(fg).matchAll(/"name"\s*:\s*"([A-Za-z_]\w*)"/g)) out.push(m[1]);
  } catch (e) { /* not JSON */ }
  return out.filter(n => toolNames.has(n));
}

async function runAgentic(q, maxIter, planned) {
  const messages = [
    { role: 'system', content: SYSTEM_PROMPT + langDirective(q.lang) + planDirective(planned) },
    { role: 'user', content: `${q.query}\n\n${APP_CONTEXT}` },
  ];
  const called = []; let iterations = 0, finalText = '', recovered = 0;
  while (iterations < maxIter) {
    iterations++;
    let msg;
    try {
      // as in api/chat-stream.js: with a non-empty plan, the first round must call a tool
      msg = await complete({ messages, tools: GROQ_TOOLS, tool_choice: iterations === 1 && planned?.length ? 'required' : 'auto', max_tokens: MAX_TOKENS });
    } catch (e) {
      const leaked = e.status === 400 ? leakedCalls(e.body) : [];
      if (!leaked.length) throw e;
      called.push(...leaked); recovered += leaked.length; finalText = '[recovered leaked tool call]'; break;
    }
    const calls = msg.tool_calls || [];
    if (!calls.length) {
      finalText = msg.content || '';
      const leaked = leakedCalls(finalText);
      called.push(...leaked); recovered += leaked.length;
      break;
    }
    called.push(...calls.map(c => c.function.name));
    messages.push({ role: 'assistant', content: msg.content || null,
      tool_calls: calls.map(c => ({ id: c.id, type: 'function', function: { name: c.function.name, arguments: c.function.arguments } })) });
    for (const c of calls) messages.push({ role: 'tool', tool_call_id: c.id, content: STUB });
  }
  return { called, iterations, final_text: finalText, recovered, ...(planned ? { planned } : {}) };
}

async function runRouter(q) {
  const catalogue = catalogueOf(GROQ_TOOLS);
  const msg = await complete({ messages: [{ role: 'system', content: ROUTER_PROMPT(catalogue) },
    { role: 'user', content: `${q.query}\n\n${APP_CONTEXT}` }], max_tokens: MAX_TOKENS });
  const text = msg.content || '';
  return { called: [...toolNames].filter(n => new RegExp(`\\b${n}\\b`).test(text)), iterations: 1, final_text: text, recovered: 0 };
}

// ── Main ──
const runsDir = join(HERE, 'runs'), resultsDir = join(HERE, 'results');
mkdirSync(runsDir, { recursive: true }); mkdirSync(resultsDir, { recursive: true });
const runFile = join(runsDir, slug + '.jsonl');

if (flag('dry-run')) {
  const rows = queries.map(q => ({ ...q, called: [], iterations: 0, latency_s: 0, score: score(q, []) }));
  console.log(`dry run: ${queries.length} queries, ${toolNames.size} tools offered; empty selection scores`,
    JSON.stringify(aggregate(rows).abstention), 'on abstention');
  process.exit(0);
}
if (!process.env[prov.key]) { console.error(`Set ${prov.key}.`); process.exit(1); }

const done = new Map();
if (existsSync(runFile)) for (const l of readFileSync(runFile, 'utf8').split('\n').filter(Boolean)) { const r = JSON.parse(l); done.set(r.id, r); }
console.log(`${slug}: ${queries.length} queries, ${done.size} already done (${runFile})`);

for (const q of queries) {
  if (done.has(q.id)) continue;
  const t0 = Date.now();
  let r;
  try {
    if (mode === 'router') r = await runRouter(q);
    else if (mode === 'planned') {
      // planTools fails open (returns []) like in production; a provider error there is not retried.
      const planned = await planTools(complete, `${q.query}\n\n${APP_CONTEXT}`, GROQ_TOOLS);
      r = await runAgentic(q, MAX_ITERATIONS, planned);
    } else r = await runAgentic(q, mode === 'single' ? 1 : MAX_ITERATIONS);
  } catch (e) {
    console.error(`${q.id}: ${e.message} — stopping; re-run the same command to resume.`);
    break;
  }
  const row = { id: q.id, lang: q.lang, category: q.category, query: q.query, gold: q.gold, ...r,
    called_set: [...new Set(r.called)].sort(), latency_s: +((Date.now() - t0) / 1000).toFixed(2) };
  row.score = score(q, row.called_set);
  appendFileSync(runFile, JSON.stringify(row) + '\n');
  done.set(q.id, row);
  console.log(`${q.id} ${row.score.correct ? 'ok ' : 'MISS'} [${row.called_set.join(', ') || '—'}]`);
  if (sleepS) await sleep(sleepS);
}

const rows = queries.filter(q => done.has(q.id)).map(q => done.get(q.id));
const summary = { slug, provider: providerName, model, mode, benchmark: benchFile.split('/').pop(),
  max_iterations: mode === 'single' ? 1 : MAX_ITERATIONS, complete: rows.length === queries.length,
  system_fingerprints: [...fingerprints], run_date: new Date().toISOString().slice(0, 10), ...aggregate(rows) };
writeFileSync(join(resultsDir, slug + '.json'), JSON.stringify(summary, null, 1));
const fails = rows.filter(r => !r.score.correct);
writeFileSync(join(resultsDir, slug + '.md'), [
  `# ${slug}`, '', `Queries: ${rows.length}/${queries.length} · accuracy ${(summary.query_accuracy * 100).toFixed(1)} % `
  + `(95 % Wilson ${summary.query_accuracy_wilson95.map(x => (x * 100).toFixed(1)).join('–')}) · F1 ${summary.f1.toFixed(3)} · `
  + `abstention ${summary.abstention[0]}/${summary.abstention[1]}`, '', '## Failures', '',
  '| ID | Lang | Category | Query | Expected | Selected |', '|---|---|---|---|---|---|',
  ...fails.map(r => `| ${r.id} | ${r.lang} | ${r.category} | ${r.query.replace(/\|/g, '/')} | ${r.gold.join(', ') || '(abstain)'} | ${r.called_set.join(', ') || '(none)'} |`),
].join('\n') + '\n');
console.log(`\n${summary.complete ? 'complete' : 'PARTIAL'}: accuracy ${(summary.query_accuracy * 100).toFixed(1)} % · F1 ${summary.f1.toFixed(3)} · abstention ${summary.abstention.join('/')}`);
