// SPDX-License-Identifier: AGPL-3.0-only
// Two analyses of the runs of run_panel_cases.mjs -> eval/results/panel_comparison.json
//  (1) "paired": the output guardrails are a deterministic post-processor, so their effect is measured WITHIN each
//      generation: the current api/_guards.js is re-applied to the stored raw answers of both runs (200 generations)
//      and each raw answer is compared with its filtered version. No test is needed; the note's recall on answers
//      that give a per-area dose is reported, and which rule triggered the note.
//  (2) "two_runs": the guards-on and guards-off runs are two independent generations; comparing them (exact McNemar
//      on discordant pairs) measures run-to-run variability of tool use and doses, not the guardrails.
// Counters are recomputed from the stored texts with eval/panel_behaviour.mjs, so a change in a counter applies to
// both runs. node eval/analyze_panel.mjs
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { DOSE, ADVISOR, behaviourOf } from './panel_behaviour.mjs';
const require = createRequire(import.meta.url);
const { pulirRespuesta, quitarPreguntaDeCierre, PRESCRIPCION_RE, TEMA_SENSIBLE_RE, YA_DERIVA_RE } = require('../api/_guards.js');
const HERE = dirname(fileURLToPath(import.meta.url));
const rows = f => Object.fromEntries(readFileSync(join(HERE, 'runs', f), 'utf8').split('\n').filter(Boolean).map(l => { const r = JSON.parse(l); return [r.id, r]; }));
const ON = rows('panel_guards_on.jsonl'), OFF = rows('panel_guards_off.jsonl');
const ids = Object.keys(ON).filter(id => OFF[id]);
for (const R of [ON, OFF]) for (const r of Object.values(R)) r.behaviour = behaviourOf(r.final_text, r.called);
const BEH = ['closes_with_offer', 'ends_with_question', 'per_area_dose', 'advisor_note', 'tools_used'];
// exact two-sided binomial test on discordant pairs (McNemar)
function mcnemar(b, c) {
  const n = b + c; if (!n) return 1;
  const k = Math.min(b, c); let p = 0;
  const logC = (n, r) => { let s = 0; for (let i = 1; i <= r; i++) s += Math.log(n - r + i) - Math.log(i); return s; };
  for (let i = 0; i <= k; i++) p += Math.exp(logC(n, i) - n * Math.LN2);
  return Math.min(1, 2 * p);
}
const sha = f => createHash('sha256').update(readFileSync(join(HERE, f))).digest('hex').slice(0, 8);
const out = { _about: 'see header of eval/analyze_panel.mjs', guards_sha256: sha('../api/_guards.js'), behaviour_sha256: sha('panel_behaviour.mjs'),
  n_cases: ids.length, paired: {}, behaviours: {}, by_module: {} };
// (1) paired, within-generation effect of the current guardrails on the stored raw answers
const gens = [...ids.map(id => ({ run: 'on', ...ON[id] })), ...ids.map(id => ({ run: 'off', ...OFF[id] }))];
const P = { n_generations: gens.length, modified: 0, offer_removed: 0, note_added: 0, note_trigger: { prescription: 0, topic_only: 0 },
  raw: { closes_with_offer: 0, ends_with_question: 0, per_area_dose: 0, advisor_note: 0 },
  filtered: { closes_with_offer: 0, ends_with_question: 0, per_area_dose: 0, advisor_note: 0 },
  dosed_answers: { n: 0, with_note: 0, without_note_ids: [], already_refers_to_advisor: 0 }, dosed_ids: [] };
for (const g of gens) {
  const raw = g.raw_text || '', fin = pulirRespuesta(raw, g.query, 'es');
  const br = behaviourOf(raw), bf = behaviourOf(fin);
  for (const k of Object.keys(P.raw)) { P.raw[k] += +br[k]; P.filtered[k] += +bf[k]; }
  if (fin !== raw) P.modified++;
  if (br.closes_with_offer && !bf.closes_with_offer) P.offer_removed++;
  if (!br.advisor_note && bf.advisor_note) { P.note_added++; P.note_trigger[PRESCRIPCION_RE.test(quitarPreguntaDeCierre(raw)) ? 'prescription' : 'topic_only']++; }
  if (bf.per_area_dose) { P.dosed_answers.n++; P.dosed_ids.push(`${g.id}/${g.run}`); if (bf.advisor_note) P.dosed_answers.with_note++; else P.dosed_answers.without_note_ids.push(`${g.id}/${g.run}`);
    if (YA_DERIVA_RE.test(raw)) P.dosed_answers.already_refers_to_advisor++; }
}
out.paired = P;
// (2) two independent generations, stored final texts
for (const b of BEH) {
  const on = ids.filter(id => ON[id].behaviour[b]).length, off = ids.filter(id => OFF[id].behaviour[b]).length;
  const offOnly = ids.filter(id => OFF[id].behaviour[b] && !ON[id].behaviour[b]).length, onOnly = ids.filter(id => ON[id].behaviour[b] && !OFF[id].behaviour[b]).length;
  out.behaviours[b] = { guards_off: off, guards_on: on, off_only: offOnly, on_only: onOnly, mcnemar_p: +mcnemar(offOnly, onOnly).toPrecision(3) };
}
for (const m of [...new Set(ids.map(id => ON[id].module))].sort()) {
  const s = ids.filter(id => ON[id].module === m);
  out.by_module[m] = { n: s.length, ...Object.fromEntries(BEH.map(b => [b, [s.filter(id => OFF[id].behaviour[b]).length, s.filter(id => ON[id].behaviour[b]).length]])) };
}
// tools and fidelity are identical between runs by construction (same raw answers? no: separate runs), so report both
out.tools_called = { guards_off: ids.filter(id => OFF[id].called.length).length, guards_on: ids.filter(id => ON[id].called.length).length };
writeFileSync(join(HERE, 'results', 'panel_comparison.json'), JSON.stringify(out, null, 1));
console.log(JSON.stringify({ paired: out.paired, two_runs: out.behaviours }, null, 1));
