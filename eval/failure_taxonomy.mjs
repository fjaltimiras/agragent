// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 Francisco Altimiras. See LICENSING.md.
//
// Classifies the failed in-scope queries of a run into the categories used in the paper:
//   clarification  no tool called and the answer is a question back to the user (asks for missing data)
//   no_tool        no tool called and the answer is given from the model's own knowledge
//   incomplete     some required intent groups covered, at least one missing, nothing outside the acceptable set
//   extraneous     a tool outside the acceptable set was called
// The rule is mechanical (last non-empty line ends with "?" or "？"), so it can be re-applied to any run.
//   node eval/failure_taxonomy.mjs eval/runs/<slug>.jsonl
import { readFileSync } from 'node:fs';

const file = process.argv[2];
if (!file) { console.error('usage: node eval/failure_taxonomy.mjs eval/runs/<slug>.jsonl'); process.exit(1); }
const rows = readFileSync(file, 'utf8').trim().split('\n').map(JSON.parse);
const endsWithQuestion = t => /[?？]\s*$/.test(String(t || '').trim().split('\n').filter(Boolean).pop() || '');

const out = { clarification: [], no_tool: [], incomplete: [], extraneous: [] };
for (const r of rows) {
  if (r.score.correct || !r.score.expect_tool) continue;
  if (!r.score.no_extraneous) out.extraneous.push(r.id);
  else if (r.called.length === 0) (endsWithQuestion(r.final_text) ? out.clarification : out.no_tool).push(r.id);
  else out.incomplete.push(r.id);
}
const inScope = rows.filter(r => r.score.expect_tool).length;
const failed = Object.values(out).reduce((a, v) => a + v.length, 0);
console.log(`${file}\nin-scope ${inScope}, failed ${failed}`);
for (const [k, v] of Object.entries(out)) console.log(`${k.padEnd(14)} ${String(v.length).padStart(3)}  ${v.join(' ')}`);
const rescored = rows.filter(r => r.score.correct || (r.score.expect_tool && r.called.length === 0 && endsWithQuestion(r.final_text))).length;
console.log(`counting clarification questions as acceptable: ${rescored}/${rows.length}`);
