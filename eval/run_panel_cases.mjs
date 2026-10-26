// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 Francisco Altimiras. See LICENSING.md.
//
// The expert panel's 100 consultations (eval/panel_cases.json, from the INIA review of Avisa) run through the
// RELEASED agent (plan-then-act, api/chat-stream.js prompt, tools and loop; external tools return the fixed
// payloads of eval/fixtures.json, local tools run), once with the output guardrails of api/_guards.js and once
// without them. What is measured is BEHAVIOUR, not agronomic accuracy: whether the answer closes with a question
// or an offer, gives a per-area dose, ends with the advisor note, which tools it called and whether its figures
// are traceable. The panel's queries refer to fields registered at INIA; here every query is answered for the
// benchmark's fixed field, so the answers are not comparable case by case with the panel's.
//
//   CEREBRAS_API_KEY=… node eval/run_panel_cases.mjs [--guards on|off] [--sleep S] [--limit N]
//
// Each answered case is appended to eval/runs/panel_<guards>.jsonl (resumable); summary in eval/results/.
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

process.env.SUPABASE_URL ||= 'https://not-used.invalid';
process.env.SUPABASE_SERVICE_ROLE_KEY ||= 'not-used';
const require = createRequire(import.meta.url);
const { SYSTEM_PROMPT, GROQ_TOOLS, executeTool } = require('../api/chat-stream.js').internals;
const { planTools, planDirective } = require('../api/_planner.js');
const { pulirRespuesta } = require('../api/_guards.js');
import { behaviourOf } from './panel_behaviour.mjs';
const HERE = dirname(fileURLToPath(import.meta.url));

const URL = 'https://api.cerebras.ai/v1/chat/completions', MODEL = 'gpt-oss-120b';
const MAX_ITERATIONS = 6, MAX_TOKENS = 1024;
const argv = process.argv.slice(2);
const opt = (name, def) => { const i = argv.indexOf('--' + name); return i >= 0 ? argv[i + 1] : def; };
const guards = opt('guards', 'on');
if (!['on', 'off'].includes(guards)) throw new Error('--guards on|off');
const sleepS = +opt('sleep', 1), limit = +opt('limit', 0);
const slug = `panel_guards_${guards}`;

// Same fixed context as run_tool_selection.mjs, in Spanish (the panel's language). The field is the benchmark's.
const APP_CONTEXT = [
  '[App Context: All computed data from agragent platform]',
  'Language: es. Crop: grapevine (Vitis vinifera). Today: 2026-01-15. Current season: 2025-26 (southern hemisphere).',
  'Field location: Casablanca, Valparaíso Region, Chile',
  'Field area: 5.0 ha (5.00 hectares). Centroid: latitude -33.32, longitude -71.41.',
  'Irrigation system: drip. Soil texture: loam. Current phenological stage (projected): berry growth.',
  '[/App Context]',
].join('\n');
const LANG_DIRECTIVE = '\n\n## CRITICAL LANGUAGE RULE\nThe user interface is set to **Spanish (Español)**. You MUST reply ENTIRELY in Spanish (Español) — every sentence, every question, every word. Do NOT mix languages. This rule overrides any default behavior.';
const FIXTURES = JSON.parse(readFileSync(join(HERE, 'fixtures.json'), 'utf8'));
const LOCAL_TOOLS = new Set(['analyze_soil_report', 'analyze_foliar_report', 'calculate_irrigation_plan', 'calculate_fertilization_plan']);

let cases = JSON.parse(readFileSync(join(HERE, 'panel_cases.json'), 'utf8')).cases;
if (limit) cases = cases.slice(0, limit);

// Behaviour counters: eval/panel_behaviour.mjs (shared with analyze_panel.mjs).

const sleep = s => new Promise(ok => setTimeout(ok, s * 1000));
const fingerprints = new Set();
async function complete(body) {
  for (let attempt = 1; ; attempt++) {
    const res = await fetch(URL, { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${process.env.CEREBRAS_API_KEY}` },
      body: JSON.stringify({ ...body, model: MODEL, stream: false }), signal: AbortSignal.timeout(90000) });
    if (res.status === 429 && attempt < 6) { await sleep(Math.min(120, 10 * 2 ** (attempt - 1))); continue; }
    const text = await res.text();
    if (!res.ok) { const e = new Error(`HTTP ${res.status}: ${text.slice(0, 300)}`); e.status = res.status; throw e; }
    const data = JSON.parse(text);
    if (data.system_fingerprint) fingerprints.add(data.system_fingerprint);
    return data.choices[0].message;
  }
}
async function toolResult(name, argsJson) {
  if (LOCAL_TOOLS.has(name)) {
    let input = {}; try { input = JSON.parse(argsJson || '{}'); } catch (e) { return JSON.stringify({ error: 'invalid arguments' }); }
    try { return JSON.stringify(await executeTool(name, input)); } catch (e) { return JSON.stringify({ error: e.message }); }
  }
  return JSON.stringify(FIXTURES[name] || { error: 'no fixture' });
}

async function runCase(c) {
  const user = `${c.query}\n\n${APP_CONTEXT}`;
  const planned = await planTools(complete, user, GROQ_TOOLS);
  const messages = [{ role: 'system', content: SYSTEM_PROMPT + LANG_DIRECTIVE + planDirective(planned) }, { role: 'user', content: user }];
  const called = []; let iterations = 0, raw = '', retriedAuto = 0;
  while (iterations < MAX_ITERATIONS) {
    iterations++;
    let msg;
    const round = choice => complete({ messages, tools: GROQ_TOOLS, tool_choice: choice, max_tokens: MAX_TOKENS });
    if (iterations === 1 && planned?.length) {
      try { msg = await round('required'); } catch (e) { if (e.status !== 400) throw e; msg = null; }
      if (!msg || !(msg.tool_calls || []).length) { msg = await round('auto'); retriedAuto++; }
    } else msg = await round('auto');
    const calls = msg.tool_calls || [];
    if (!calls.length) { raw = msg.content || ''; break; }
    called.push(...calls.map(x => x.function.name));
    messages.push({ role: 'assistant', content: msg.content || null,
      tool_calls: calls.map(x => ({ id: x.id, type: 'function', function: { name: x.function.name, arguments: x.function.arguments } })) });
    for (const x of calls) messages.push({ role: 'tool', tool_call_id: x.id, content: await toolResult(x.function.name, x.function.arguments) });
  }
  // The released API applies pulirRespuesta to the final text (api/chat-stream.js); --guards off skips it.
  const final = guards === 'on' ? pulirRespuesta(raw, user, 'es') : raw;
  return { planned, called, called_set: [...new Set(called)].sort(), iterations, retried_auto: retriedAuto, raw_text: raw, final_text: final,
    behaviour: behaviourOf(final, called) };
}

const runsDir = join(HERE, 'runs'), resultsDir = join(HERE, 'results');
mkdirSync(runsDir, { recursive: true }); mkdirSync(resultsDir, { recursive: true });
const runFile = join(runsDir, slug + '.jsonl');
if (!process.env.CEREBRAS_API_KEY) { console.error('Set CEREBRAS_API_KEY.'); process.exit(1); }
const done = new Map();
if (existsSync(runFile)) for (const l of readFileSync(runFile, 'utf8').split('\n').filter(Boolean)) { const r = JSON.parse(l); done.set(r.id, r); }
console.log(`${slug}: ${cases.length} cases, ${done.size} already done`);
for (const c of cases) {
  if (done.has(c.id)) continue;
  const t0 = Date.now();
  let r;
  try { r = await runCase(c); } catch (e) { console.error(`${c.id}: ${e.message} — stopping; re-run to resume.`); break; }
  const row = { id: c.id, module: c.module, priority: c.priority, capability: c.capability, query: c.query, ...r, latency_s: +((Date.now() - t0) / 1000).toFixed(2) };
  appendFileSync(runFile, JSON.stringify(row) + '\n'); done.set(c.id, row);
  const b = row.behaviour;
  console.log(`${c.id} [${row.called_set.join(', ') || '—'}] offer=${+b.closes_with_offer} dose=${+b.per_area_dose} advisor=${+b.advisor_note}`);
  if (sleepS) await sleep(sleepS);
}
const rows = cases.filter(c => done.has(c.id)).map(c => done.get(c.id));
const count = f => rows.filter(f).length;
const summary = { slug, model: MODEL, guards, n_cases: rows.length, complete: rows.length === cases.length,
  system_fingerprints: [...fingerprints], run_date: new Date().toISOString().slice(0, 10),
  sha256: Object.fromEntries(['../api/chat-stream.js', '../api/_planner.js', '../api/_guards.js', 'panel_cases.json', 'fixtures.json']
    .map(f => [f.split('/').pop(), createHash('sha256').update(readFileSync(join(HERE, f))).digest('hex')])),
  closes_with_offer: count(r => r.behaviour.closes_with_offer), ends_with_question: count(r => r.behaviour.ends_with_question),
  per_area_dose: count(r => r.behaviour.per_area_dose), advisor_note: count(r => r.behaviour.advisor_note),
  used_tools: count(r => r.behaviour.tools_used), retried_auto: rows.reduce((s, r) => s + r.retried_auto, 0),
  by_module: Object.fromEntries([...new Set(rows.map(r => r.module))].sort().map(m => { const s = rows.filter(r => r.module === m);
    return [m, { n: s.length, closes_with_offer: s.filter(r => r.behaviour.closes_with_offer).length, per_area_dose: s.filter(r => r.behaviour.per_area_dose).length,
      advisor_note: s.filter(r => r.behaviour.advisor_note).length, used_tools: s.filter(r => r.behaviour.tools_used).length }]; })) };
writeFileSync(join(resultsDir, slug + '.json'), JSON.stringify(summary, null, 1));
console.log(`\n${summary.complete ? 'complete' : 'PARTIAL'}: offer ${summary.closes_with_offer}/${rows.length} · dose ${summary.per_area_dose} · advisor ${summary.advisor_note} · tools ${summary.used_tools}`);
