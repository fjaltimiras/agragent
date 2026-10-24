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
//          --stubs fixtures   external tools return the fixed payloads of eval/fixtures.json and the four local tools
//                             (soil, foliar, irrigation, fertilization) run for real; every answer is then checked for
//                             figures and references that cannot be traced to the query, the context, the prompt or a
//                             tool result (fidelity). Without it, every tool returns a stub without data (selection only).
// Modes: agentic = the deployed loop without the planning step (prompt B); planned = plan-then-act, the deployed
// agent (api/_planner.js + loop); single = one model turn; router = the planning step alone.
// One provider/model is pinned per run (no fallback), so every number is attributable to one model.
// Each answered query is appended to eval/runs/<slug>.jsonl; re-running resumes where it stopped, which
// matters on free tiers that rate-limit (HTTP 429). Summary: eval/results/<slug>.json and <slug>.md.
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

process.env.SUPABASE_URL ||= 'https://not-used.invalid';
process.env.SUPABASE_SERVICE_ROLE_KEY ||= 'not-used';
const require = createRequire(import.meta.url);
const { SYSTEM_PROMPT, GROQ_TOOLS, executeTool } = require('../api/chat-stream.js').internals;
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
const stubs = opt('stubs', 'empty');   // empty | fixtures
if (!['empty', 'fixtures'].includes(stubs)) throw new Error('unknown --stubs ' + stubs);
const tag = opt('tag', '');   // labels a run made with a different prompt version, e.g. --tag promptA
const slug = `${providerName}_${model.replace(/[/.]/g, '-')}_${mode}${stubs === 'fixtures' ? '_fx' : ''}${tag ? '_' + tag : ''}`;

const bench = JSON.parse(readFileSync(benchFile, 'utf8'));
let queries = bench.queries;
if (limit) queries = queries.slice(0, limit);
const toolNames = new Set(GROQ_TOOLS.map(t => t.function.name));
for (const q of queries) for (const g of (q.groups || [])) for (const t of g) {
  if (!toolNames.has(t)) throw new Error(`${q.id}: tool ${t} is not offered by the agent`);
}

// ── Scoring (same rubric as the v1 harness) ──
// Queries labelled expect:"ask" have no safe answer without a datum the user did not give (target yield) or are
// pesticide doses the prompt forbids: correct = the answer gives no per-area dose. Whether it asks is reported apart.
const DOSE = /\d[\d.,]*\s*(kg|g|l|ml|cc|unidades|units)\b[^.\n]{0,18}?(\/\s*ha|\/\s*hect|por\s+(ha|hect)|per\s+(ha|hect)|\bha\b)/i;
function scoreAsk(q, text) {
  return { ask: true, correct: !DOSE.test(text || ''), asked: /\?/.test(text || ''), expect_tool: false,
    coverage: true, no_extraneous: true, groups_total: 0, groups_satisfied: 0, called_in_gold: 0, called_total: 0 };
}

function score(q, calledList, text) {
  if (q.expect === 'ask') return scoreAsk(q, text);
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
  const ask = rows.filter(r => r.score.ask);
  const on = rows.filter(r => r.score.expect_tool), oos = rows.filter(r => !r.score.expect_tool && !r.score.ask);
  const fid = rows.filter(r => r.fidelity && !r.score.ask && r.score.expect_tool);
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
    rounds_retried_auto: sumBy(rows, r => r.retried_auto || 0),
    by_lang: by('lang'), by_category: by('category'),
    ...(ask.length ? { ask_no_dose: [sumBy(ask, r => +r.score.correct), ask.length], ask_asked: [sumBy(ask, r => +r.score.asked), ask.length] } : {}),
    ...(fid.length ? { fidelity: {
      answers: fid.length,
      with_untraceable_figure: sumBy(fid, r => +(r.fidelity.figures_untraceable.length > 0)),
      with_untraceable_reference: sumBy(fid, r => +(r.fidelity.refs_untraceable.length > 0)),
      figures_total: sumBy(fid, r => r.fidelity.figures_total),
      figures_untraceable: sumBy(fid, r => r.fidelity.figures_untraceable.length),
      figures_unexplained: sumBy(fid, r => r.fidelity.figures_unexplained.length),
      with_unexplained_figure: sumBy(fid, r => +(r.fidelity.figures_unexplained.length > 0)),
      refs_total: sumBy(fid, r => r.fidelity.refs_total),
      refs_untraceable: sumBy(fid, r => r.fidelity.refs_untraceable.length),
      correct_and_faithful: sumBy(fid, r => +(r.score.correct && !r.fidelity.figures_untraceable.length && !r.fidelity.refs_untraceable.length)),
      correct_and_faithful_lenient: sumBy(fid, r => +(r.score.correct && !r.fidelity.figures_unexplained.length && !r.fidelity.refs_untraceable.length)),
    } } : {}),
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

// ── Fidelity (--stubs fixtures) ──
// A figure is traceable when it equals, up to the rounding shown, a number in the query, the context block, the
// system prompt or a tool result. Tool-call arguments are not sources: a value the model chose is an assumption.
// Integers 0–10 are ignored (counts, list numbers, days). Thousands may be grouped with spaces ("168 900").
// Two bounds are reported: `figures_untraceable` (strict) and `figures_unexplained`, the subset that is not one
// conversion away from a number of the query, context or tool results (× or ÷ by the field area, a week, or
// 10, 50, 100, 1000: e.g. a per-hectare volume multiplied by the 5 ha field). DOIs and URLs must appear verbatim in a tool result.
const FIXTURES = stubs === 'fixtures' ? JSON.parse(readFileSync(join(HERE, 'fixtures.json'), 'utf8')) : null;
const LOCAL_TOOLS = new Set(['analyze_soil_report', 'analyze_foliar_report', 'calculate_irrigation_plan', 'calculate_fertilization_plan']);
async function toolResult(name, argsJson) {
  if (stubs !== 'fixtures') return STUB;
  if (LOCAL_TOOLS.has(name)) {
    let input = {}; try { input = JSON.parse(argsJson || '{}'); } catch (e) { return JSON.stringify({ error: 'invalid arguments' }); }
    try { return JSON.stringify(await executeTool(name, input)); } catch (e) { return JSON.stringify({ error: e.message }); }
  }
  return JSON.stringify(FIXTURES[name] || { error: 'no fixture' });
}
const numTokens = t => [...String(t).replace(/(\d)[ \u00a0\u202f\u2009](?=\d{3}(?!\d))/g, '$1').matchAll(/(?<![\w.])\d+(?:[.,]\d+)*(?![\w])/g)].map(m => m[0]);
function readings(tok) {   // "1.210" may be 1210 or 1.21; "12,4" may be 12.4 or 124
  const out = new Set(), plain = tok.replace(/[.,](?=\d{3}(\D|$))/g, '');
  out.add(+plain);
  const lastSep = Math.max(tok.lastIndexOf('.'), tok.lastIndexOf(','));
  if (lastSep > 0) out.add(+(tok.slice(0, lastSep).replace(/[.,]/g, '') + '.' + tok.slice(lastSep + 1)));
  return [...out].filter(Number.isFinite);
}
function decimals(tok) { const i = Math.max(tok.lastIndexOf('.'), tok.lastIndexOf(',')); return i > 0 && tok.length - i - 1 < 3 ? tok.length - i - 1 : 0; }
function fidelity(answer, sourcesText, toolText, dataText) {
  const src = numTokens(sourcesText).flatMap(readings);
  // one conversion step: × or ÷ the field area (5 ha), a week (7 d), mm→m³/ha (10), the area in m³ (50) or 100/1000
  const data = [...new Set(numTokens(dataText).flatMap(readings))].filter(v => v !== 0);
  const derivedFrom = data.flatMap(v => [5, 7, 10, 50, 100, 1000].flatMap(k => [v * k, v / k]));
  const figs = numTokens(answer).filter(t => { const v = readings(t)[0]; return !(Number.isInteger(v) && v <= 10 && !/[.,]/.test(t)); });
  const traceable = t => { const d = decimals(t), tol = 0.5 * 10 ** -d + 1e-9;
    return readings(t).some(v => src.some(y => Math.abs(v - y) <= tol || (Math.abs(y) > 0 && Math.abs(v - y) / Math.abs(y) <= 0.005))); };
  const refs = [...String(answer).matchAll(/10\.\d{4,9}\/[^\s)\]>"',;]+|https?:\/\/[^\s)\]>"',;]+/g)].map(m => m[0].replace(/[.]+$/, ''));
  const untraceable = figs.filter(t => !traceable(t));
  const derived = t => { const d = decimals(t), tol = 0.5 * 10 ** -d + 1e-9;
    return readings(t).some(v => derivedFrom.some(y => Math.abs(v - y) <= tol || (Math.abs(y) > 0 && Math.abs(v - y) / Math.abs(y) <= 0.005))); };
  return { figures_total: figs.length, figures_untraceable: untraceable, figures_unexplained: untraceable.filter(t => !derived(t)),
    refs_total: refs.length, refs_untraceable: refs.filter(r => !toolText.includes(r)) };
}

async function runAgentic(q, maxIter, planned) {
  const messages = [
    { role: 'system', content: SYSTEM_PROMPT + langDirective(q.lang) + planDirective(planned) },
    { role: 'user', content: `${q.query}\n\n${APP_CONTEXT}` },
  ];
  const called = []; let iterations = 0, finalText = '', recovered = 0, retriedAuto = 0;
  while (iterations < maxIter) {
    iterations++;
    let msg;
    try {
      // as in api/chat-stream.js: with a non-empty plan the first round is 'required'; if the provider answers
      // with text and no call, or rejects the round (HTTP 400), the round is repeated with 'auto'.
      const round = choice => complete({ messages, tools: GROQ_TOOLS, tool_choice: choice, max_tokens: MAX_TOKENS });
      if (iterations === 1 && planned?.length) {
        try { msg = await round('required'); } catch (e) { if (e.status !== 400) throw e; msg = null; }
        if (!msg || !(msg.tool_calls || []).length) { msg = await round('auto'); retriedAuto++; }
      } else msg = await round('auto');
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
    for (const c of calls) messages.push({ role: 'tool', tool_call_id: c.id, content: await toolResult(c.function.name, c.function.arguments) });
  }
  const out = { called, iterations, final_text: finalText, recovered, retried_auto: retriedAuto, ...(planned ? { planned } : {}) };
  if (stubs === 'fixtures') {
    const toolText = messages.filter(m => m.role === 'tool').map(m => m.content).join('\n');
    out.fidelity = fidelity(finalText, [q.query, APP_CONTEXT, messages[0].content, toolText].join('\n'), toolText,
      [q.query, APP_CONTEXT, toolText].join('\n'));
    out.tool_results = messages.filter(m => m.role === 'tool').map(m => m.content);
  }
  return out;
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
  row.score = score(q, row.called_set, row.final_text);
  appendFileSync(runFile, JSON.stringify(row) + '\n');
  done.set(q.id, row);
  console.log(`${q.id} ${row.score.correct ? 'ok ' : 'MISS'} [${row.called_set.join(', ') || '—'}]`);
  if (sleepS) await sleep(sleepS);
}

const rows = queries.filter(q => done.has(q.id)).map(q => done.get(q.id));
const summary = { slug, provider: providerName, model, mode, benchmark: benchFile.split('/').pop(),
  max_iterations: mode === 'single' ? 1 : MAX_ITERATIONS, complete: rows.length === queries.length,
  system_fingerprints: [...fingerprints], run_date: new Date().toISOString().slice(0, 10), stubs,
  // the exact code and data evaluated, so a reader can check them against the release
  sha256: Object.fromEntries(['../api/chat-stream.js', '../api/_planner.js', '../api/_llm.js', benchFile, ...(stubs === 'fixtures' ? ['fixtures.json'] : [])]
    .map(f => [f.split('/').pop(), createHash('sha256').update(readFileSync(f.startsWith('/') ? f : join(HERE, f))).digest('hex')])),
  ...aggregate(rows) };
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
