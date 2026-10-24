// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 Francisco Altimiras. See LICENSING.md.
//
// Deterministic arithmetic check of the assistant's two quantitative tools, exactly as the API runs them
// (api/chat-stream.js). No LLM and no network.
//
//   node eval/verify_arithmetic.mjs        → prints a table and writes eval/results/arithmetic.csv
//
// Irrigation: crop coefficients are checked against FAO-56 Table 12 (Allen et al. 1998), typed in below
// independently of the implementation, then
//   ETc = Kc × ET0,  gross = net / efficiency,  volume (m³) = gross (mm) × 10 × area (ha),
//   interval (days) = round(net / ETc).
// Fertilization: nutrient mass balance
//   total = uptake per tonne × yield target, field total = total × area,
//   and the documented rule that P2O5 is halved when soil P > 40 ppm.
import { createRequire } from 'node:module';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

process.env.SUPABASE_URL ||= 'https://not-used.invalid';   // _db.js builds a client at import time
process.env.SUPABASE_SERVICE_ROLE_KEY ||= 'not-used';
const require = createRequire(import.meta.url);
const { calculateIrrigationPlan, calculateFertilizationPlan } = require('../api/chat-stream.js').internals;
const HERE = dirname(fileURLToPath(import.meta.url));

// FAO-56, Table 12: Kc ini / Kc mid / Kc end. Tomato end 0.70–0.90 (implementation uses 0.80);
// maize (grain) end 0.60–0.35 (implementation uses the upper value). "vid" is FAO's table grapes row.
const FAO56 = {
  tomate: { initial: 0.60, mid_season: 1.15, late_season: [0.70, 0.90] },
  vid:    { initial: 0.30, mid_season: 0.85, late_season: [0.45, 0.45] },
  maiz:   { initial: 0.30, mid_season: 1.20, late_season: [0.35, 0.60] },
};
const within = (v, ref) => Array.isArray(ref) ? v >= ref[0] - 1e-9 && v <= ref[1] + 1e-9 : Math.abs(v - ref) < 1e-9;
const near = (a, b, tol) => Math.abs(a - b) <= tol;

const IRRIGATION = [
  ['tomate-mid-drip',      { crop_type: 'tomate', growth_stage: 'mid_season',  soil_type: 'franco',    irrigation_system: 'goteo',      et0: 5.0, area_ha: 1 }],
  ['tomate-ini-sprinkler', { crop_type: 'tomate', growth_stage: 'initial',     soil_type: 'arenoso',   irrigation_system: 'aspersion',  et0: 3.2, area_ha: 2.5 }],
  ['vid-mid-drip',         { crop_type: 'vid',    growth_stage: 'mid_season',  soil_type: 'franco',    irrigation_system: 'goteo',      et0: 4.2, area_ha: 5 }],
  ['vid-late-furrow',      { crop_type: 'vid',    growth_stage: 'late_season', soil_type: 'arcilloso', irrigation_system: 'surcos',     et0: 3.0, area_ha: 1 }],
  ['maiz-mid-sprinkler',   { crop_type: 'maiz',   growth_stage: 'mid_season',  soil_type: 'arcilloso', irrigation_system: 'aspersion',  et0: 6.0, area_ha: 10 }],
  ['maiz-late-flood',      { crop_type: 'maiz',   growth_stage: 'late_season', soil_type: 'franco',    irrigation_system: 'inundacion', et0: 4.0, area_ha: 1 }],
];

const FERTILIZATION = [
  // [id, input, uptake kg/t {N,P2O5,K2O} documented for the crop, expect P halved]
  ['tomate-60t',        { crop_type: 'tomate', yield_target: 60, area_ha: 1 },   { N: 3,  P2O5: 1,   K2O: 5 },   false],
  ['tomate-80t-highP',  { crop_type: 'tomate', yield_target: 80, area_ha: 2, soil_analysis: { P: 55 } }, { N: 3, P2O5: 1, K2O: 5 }, true],
  ['vid-12t',           { crop_type: 'vid',    yield_target: 12, area_ha: 5 },   { N: 2,  P2O5: 0.6, K2O: 3 },   false],
  ['maiz-12t',          { crop_type: 'maiz',   yield_target: 12, area_ha: 10 },  { N: 18, P2O5: 8,   K2O: 5 },   false],
  ['trigo-8t',          { crop_type: 'trigo',  yield_target: 8,  area_ha: 1 },   { N: 22, P2O5: 8,   K2O: 6 },   false],
  ['trigo-8t-lowP',     { crop_type: 'trigo',  yield_target: 8,  area_ha: 1, soil_analysis: { P: 12 } }, { N: 22, P2O5: 8, K2O: 6 }, false],
];

const rows = [];
for (const [id, input] of IRRIGATION) {
  const o = calculateIrrigationPlan(input);
  const kcOk = within(o.kc, FAO56[input.crop_type][input.growth_stage]);
  const eff = o.efficiency_pct / 100;
  const etcOk = near(o.etc_daily_mm, o.kc * input.et0, 0.01);
  const grossOk = near(o.gross_irrigation_mm, o.net_irrigation_mm / eff, 0.15);
  const volOk = near(o.volume_m3, o.gross_irrigation_mm * 10 * input.area_ha, 0.5);
  const intOk = o.interval_days === Math.max(1, Math.round(o.net_irrigation_mm / o.etc_daily_mm));
  rows.push({ id, tool: 'irrigation', pass: kcOk && etcOk && grossOk && volOk && intOk,
    detail: `Kc=${o.kc} (FAO-56 ${kcOk}) ETc=${o.etc_daily_mm} ${etcOk} gross=${o.gross_irrigation_mm} ${grossOk} vol=${o.volume_m3} ${volOk} interval=${o.interval_days} ${intOk}` });
}
for (const [id, input, up, halfP] of FERTILIZATION) {
  const o = calculateFertilizationPlan(input);
  const t = o.total_kg_ha, f = o.total_kg_field, y = input.yield_target, a = input.area_ha;
  const pRef = up.P2O5 * y * (halfP ? 0.5 : 1);
  const massOk = near(t.N, up.N * y, 0.1) && near(t.P2O5, pRef, 0.1) && near(t.K2O, up.K2O * y, 0.1);
  const fieldOk = near(f.N, t.N * a, 0.1) && near(f.P2O5, t.P2O5 * a, 0.1) && near(f.K2O, t.K2O * a, 0.1);
  rows.push({ id, tool: 'fertilization', pass: massOk && fieldOk,
    detail: `N=${t.N}/${up.N * y} P2O5=${t.P2O5}/${+pRef.toFixed(1)} K2O=${t.K2O}/${up.K2O * y} mass=${massOk} field=${fieldOk}` });
}

mkdirSync(join(HERE, 'results'), { recursive: true });
writeFileSync(join(HERE, 'results', 'arithmetic.csv'),
  'id,tool,pass,detail\n' + rows.map(r => `${r.id},${r.tool},${r.pass},"${r.detail}"`).join('\n') + '\n');

for (const r of rows) console.log(`  [${r.pass ? 'PASS' : 'FAIL'}] ${r.tool.padEnd(13)} ${r.id.padEnd(22)} ${r.detail}`);
const ok = rows.filter(r => r.pass).length;
const irr = rows.filter(r => r.tool === 'irrigation'), fer = rows.filter(r => r.tool === 'fertilization');
console.log(`\nIrrigation ${irr.filter(r => r.pass).length}/${irr.length} · Fertilization ${fer.filter(r => r.pass).length}/${fer.length} · Overall ${ok}/${rows.length}`);
process.exit(ok === rows.length ? 0 : 1);
