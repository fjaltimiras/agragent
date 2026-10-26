#!/usr/bin/env node
// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 Francisco Altimiras. See LICENSING.md.
//
// Stability and sensitivity of the management zones and hotspots of app.html, computed in Earth Engine with the
// same recipe the browser runs (s2Collection + maskS2, buildZoneStack 'series', normalizeStack, wekaKMeans with
// seed 42, focalMode, relabelling by ascending NDVI; hotspots as z-score patches >= 0.05 ha).
//
// For each of the example vineyards of the release (EXAMPLE_FIELDS in app.html):
//   1. zones for three complete seasons with the same calendar window, and Cohen's kappa between every pair of
//      seasons (pixel by pixel, 10 m, zones relabelled by vigour so that labels are comparable);
//   2. sensitivity of the zone map of the latest season to k (2, 3, 4) and to the modal filter (kappa against
//      the released setting k = 3, filter on), and of the hotspot area to the z threshold (1, 1.5, 2);
//   3. the field area from ee.Image.pixelArea() against the pixel count x 100 m2.
//
//   NODE_PATH=../agragent-app/node_modules node scripts/zone_stability.mjs [--only colchagua] [--extra]
//   --extra adds, to an existing result file, the within-season kappa between k-means seeds (noise floor) and the
//   pixel count in the native UTM grid.
// Credentials: GEE_CLIENT_EMAIL + GEE_PRIVATE_KEY_B64 in the environment or in ../agragent-app/backend/.env.
// Output: eval/results/zone_stability.json
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '..');

// The three wine-grape example fields of the release (rings copied from EXAMPLE_FIELDS in app.html).
const FIELDS = {
  colchagua: { label: 'Vineyard, Santa Cruz, Colchagua (Chile)', hemisphere: 'S',
    ring: [[-71.306033, -34.649079], [-71.303887, -34.651568], [-71.307449, -34.653765], [-71.309724, -34.651064], [-71.306033, -34.649079]] },
  agrelo: { label: 'Malbec, Agrelo, Mendoza (Argentina)', hemisphere: 'S',
    ring: [[-68.950367, -33.095817], [-68.940668, -33.096321], [-68.941694, -33.107148], [-68.951479, -33.106572], [-68.950367, -33.095817]] },
  oakville: { label: 'Cabernet, Oakville, Napa Valley (USA)', hemisphere: 'N',
    ring: [[-122.384136, 38.432582], [-122.377056, 38.436682], [-122.374606, 38.432413], [-122.372718, 38.43053], [-122.371563, 38.428247], [-122.374224, 38.426331], [-122.376752, 38.427168], [-122.379456, 38.42848], [-122.381387, 38.431135], [-122.384136, 38.432582]] },
};
// Full-canopy window of three complete seasons: 1 Nov - 31 Mar (south), 1 May - 30 Sep (north).
const SEASONS = {
  S: [['2022-23', '2022-11-01', '2023-03-31'], ['2023-24', '2023-11-01', '2024-03-31'], ['2024-25', '2024-11-01', '2025-03-31']],
  N: [['2023', '2023-05-01', '2023-09-30'], ['2024', '2024-05-01', '2024-09-30'], ['2025', '2025-05-01', '2025-09-30']],
};
const CLOUD = 20;

const argv = process.argv.slice(2);
const only = (i => i >= 0 ? argv[i + 1] : null)(argv.indexOf('--only'));

function loadEnv() {
  if (process.env.GEE_CLIENT_EMAIL && process.env.GEE_PRIVATE_KEY_B64) return process.env;
  const p = resolve(ROOT, '../agragent-app/backend/.env');
  const out = { ...process.env };
  if (existsSync(p)) for (const line of readFileSync(p, 'utf8').split('\n')) {
    if (!line || line.startsWith('#') || !line.includes('=')) continue;
    const k = line.slice(0, line.indexOf('=')), v = line.slice(line.indexOf('=') + 1).trim().replace(/^"|"$/g, '');
    if (!out[k]) out[k] = v;
  }
  return out;
}
const env = loadEnv();
if (!env.GEE_CLIENT_EMAIL || !env.GEE_PRIVATE_KEY_B64) { console.error('Missing GEE_CLIENT_EMAIL / GEE_PRIVATE_KEY_B64'); process.exit(1); }
const ee = require('@google/earthengine');
const evaluate = o => new Promise((ok, fail) => o.evaluate((v, e) => e ? fail(new Error(e)) : ok(v)));

// ── Same recipe as app.html ──
function maskS2(img) {
  const qa = img.select('QA60');
  const qaOk = qa.bitwiseAnd(1 << 10).eq(0).and(qa.bitwiseAnd(1 << 11).eq(0));
  const scl = img.select('SCL');
  const sclOk = scl.neq(3).and(scl.neq(8)).and(scl.neq(9)).and(scl.neq(10)).and(scl.neq(11));
  return img.updateMask(qaOk.and(sclOk));
}
const s2Collection = (geom, start, end) => ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterDate(start, end).filterBounds(geom)
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', CLOUD)).map(maskS2);
const ndviOf = img => img.normalizedDifference(['B8', 'B4']);
const ndmiOf = img => img.normalizedDifference(['B8', 'B11']);
function seriesStack(coll) {   // buildZoneStack(coll, geom, 'series')
  const ndvi = coll.map(img => ndviOf(img).rename('NDVI'));
  return { image: ndvi.mean().rename('t_mean').addBands(ndvi.reduce(ee.Reducer.stdDev()).rename('t_sd'))
    .addBands(ndvi.min().rename('t_min')).addBands(ndvi.max().rename('t_max')), bands: ['t_mean', 't_sd', 't_min', 't_max'] };
}
function normalizeStack(img, bands, geom) {
  const mm = img.reduceRegion({ reducer: ee.Reducer.minMax(), geometry: geom, scale: 20, maxPixels: 1e9, bestEffort: true });
  let out = null;
  for (const b of bands) {
    const lo = ee.Number(mm.get(b + '_min')), hi = ee.Number(mm.get(b + '_max')).max(lo.add(1e-6));
    const scaled = img.select(b).unitScale(lo, hi).rename(b);
    out = out ? out.addBands(scaled) : scaled;
  }
  return out;
}
// Zones relabelled 1..k by ascending mean NDVI of the composite, as the app does, so labels mean "vigour rank".
async function zones(geom, start, end, k = 3, smooth = true, seed = 42) {
  const coll = s2Collection(geom, start, end);
  const { image, bands } = seriesStack(coll);
  const norm = normalizeStack(image, bands, geom).clip(geom);
  const training = norm.sample({ region: geom, scale: 10, numPixels: 2000, seed, tileScale: 2 });
  let z = norm.cluster(ee.Clusterer.wekaKMeans(k).train(training)).rename('zone').toInt();
  if (smooth) z = z.focalMode({ radius: 2, kernelType: 'square', iterations: 2 }).toInt().clip(geom);
  const ref = ndviOf(coll.median()).rename('val').clip(geom);
  const grouped = await evaluate(ref.addBands(z).reduceRegion({ reducer: ee.Reducer.mean().group({ groupField: 1, groupName: 'zone' }),
    geometry: geom, scale: 10, maxPixels: 1e9, bestEffort: true }));
  const areas = await evaluate(ee.Image.pixelArea().updateMask(ref.mask()).addBands(z).reduceRegion({
    reducer: ee.Reducer.sum().group({ groupField: 1, groupName: 'zone' }), geometry: geom, scale: 10, maxPixels: 1e9, bestEffort: true }));
  const rows = (grouped.groups || []).map(g => ({ cluster: g.zone, mean: g.mean })).sort((a, b) => a.mean - b.mean);
  const areaBy = Object.fromEntries((areas.groups || []).map(g => [g.zone, g.sum / 1e4]));
  rows.forEach((r, i) => { r.zone = i + 1; r.area_ha = areaBy[r.cluster] || 0; });
  const relabelled = z.remap(rows.map(r => r.cluster), rows.map(r => r.zone), 0).rename('zone');
  const nScenes = await evaluate(coll.size());
  return { image: relabelled, rows: rows.map(({ zone, area_ha, mean }) => ({ zone, area_ha: +area_ha.toFixed(2), mean_ndvi: +mean.toFixed(3) })), n_scenes: nScenes };
}
// Cohen's kappa between two zone maps, from the joint histogram of (zoneA, zoneB) over the field at 10 m.
async function kappa(a, b, geom, k) {
  const joint = a.multiply(10).add(b).rename('j');
  const hist = await evaluate(joint.reduceRegion({ reducer: ee.Reducer.frequencyHistogram(), geometry: geom, scale: 10, maxPixels: 1e9, bestEffort: true }));
  const h = hist.j || {}; let n = 0; const ra = {}, rb = {}; let agree = 0;
  for (const [key, c] of Object.entries(h)) { const i = Math.floor(+key / 10), j = +key % 10; if (!i || !j) continue;
    n += c; ra[i] = (ra[i] || 0) + c; rb[j] = (rb[j] || 0) + c; if (i === j) agree += c; }
  if (!n) return null;
  const po = agree / n; let pe = 0; for (let i = 1; i <= k; i++) pe += ((ra[i] || 0) / n) * ((rb[i] || 0) / n);
  return { kappa: +((po - pe) / (1 - pe)).toFixed(3), agreement: +po.toFixed(3), n_pixels: n };
}
async function hotspots(geom, start, end, zCut, index = 'NDMI') {
  const coll = s2Collection(geom, start, end);
  const img = (index === 'NDMI' ? ndmiOf(coll.median()) : ndviOf(coll.median())).rename('val').clip(geom);
  const st = img.reduceRegion({ reducer: ee.Reducer.mean().combine({ reducer2: ee.Reducer.stdDev(), sharedInputs: true }), geometry: geom, scale: 10, maxPixels: 1e9, bestEffort: true });
  const z = img.subtract(ee.Image.constant(ee.Number(st.get('val_mean')))).divide(ee.Image.constant(ee.Number(st.get('val_stdDev'))).max(1e-6)).rename('z');
  const patches = z.lte(-zCut).selfMask().rename('hot').addBands(z).reduceToVectors({ reducer: ee.Reducer.mean(), geometry: geom, scale: 10,
    geometryType: 'polygon', labelProperty: 'hot', eightConnected: true, maxPixels: 1e9, bestEffort: true })
    .map(f => f.set('area_ha', f.geometry().area(5).divide(1e4))).filter(ee.Filter.gte('area_ha', 0.05));
  const fc = await evaluate(patches);
  const areas = (fc.features || []).map(f => f.properties.area_ha);
  return { z: zCut, n_patches: areas.length, area_ha: +areas.reduce((s, v) => s + v, 0).toFixed(2) };
}
async function areaCheck(geom, start, end) {
  const ref = ndviOf(s2Collection(geom, start, end).median()).rename('val').clip(geom);
  const pa = await evaluate(ee.Image.pixelArea().updateMask(ref.mask()).reduceRegion({ reducer: ee.Reducer.sum(), geometry: geom, scale: 10, maxPixels: 1e9, bestEffort: true }));
  // Without a crs, a composite is reduced in the default geographic grid (EPSG:4326): a "10 m" cell there is 10 m
  // tall but 10·cos(latitude) m wide, so count × 100 m² overstates the area by 1/cos(latitude). The same count in the
  // native UTM grid of the Sentinel-2 tile is reported alongside.
  const cnt = await evaluate(ref.reduceRegion({ reducer: ee.Reducer.count(), geometry: geom, scale: 10, maxPixels: 1e9, bestEffort: true }));
  const c = await evaluate(geom.centroid(1).coordinates());
  const utm = `EPSG:${(c[1] < 0 ? 32700 : 32600) + Math.floor((c[0] + 180) / 6) + 1}`;
  const cntUtm = await evaluate(ref.reduceRegion({ reducer: ee.Reducer.count(), geometry: geom, crs: utm, scale: 10, maxPixels: 1e9 }));
  const geo = await evaluate(geom.area(1));
  return { polygon_ha: +(geo / 1e4).toFixed(2), pixel_area_ha: +(pa.area / 1e4).toFixed(2), count_x100m2_ha: +(cnt.val * 100 / 1e4).toFixed(2),
    count_utm_x100m2_ha: +(cntUtm.val * 100 / 1e4).toFixed(2), utm_crs: utm, one_over_cos_lat: +(1 / Math.cos(c[1] * Math.PI / 180)).toFixed(3) };
}

async function main() {
  await new Promise((ok, fail) => ee.data.authenticateViaPrivateKey({ private_key: Buffer.from(env.GEE_PRIVATE_KEY_B64, 'base64').toString('utf8'), client_email: env.GEE_CLIENT_EMAIL }, ok, fail));
  await new Promise((ok, fail) => ee.initialize(null, null, ok, fail, null, env.GEE_PROJECT_ID || 'agragent-491300'));
  const outPath = resolve(ROOT, 'eval/results/zone_stability.json');
  if (argv.includes('--extra')) {   // noise floor and UTM area check, merged into an existing result file
    const prev = JSON.parse(readFileSync(outPath, 'utf8'));
    for (const [id, f] of Object.entries(FIELDS)) {
      if (only && only !== id) continue;
      const geom = ee.Geometry.Polygon([f.ring]);
      const [lname, ls, le] = SEASONS[f.hemisphere].slice(-1)[0];
      const base = await zones(geom, ls, le, 3, true, 42);
      const floor = {};
      for (const seed of [1, 7]) { const alt = await zones(geom, ls, le, 3, true, seed); floor[`seed ${seed} vs 42`] = await kappa(base.image, alt.image, geom, 3); }
      prev.fields[id].within_season_seed_kappa = { season: lname, ...floor };
      prev.fields[id].area = await areaCheck(geom, ls, le);
      console.log(id, 'seed floor', floor, 'area', prev.fields[id].area);
      writeFileSync(outPath, JSON.stringify(prev, null, 1));
    }
    console.log('ok (extra) ->', outPath); return;
  }
  const out = { _about: 'Stability and sensitivity of zones and hotspots, same recipe as app.html; see scripts/zone_stability.mjs', run_date: new Date().toISOString().slice(0, 10), fields: {} };
  for (const [id, f] of Object.entries(FIELDS)) {
    if (only && only !== id) continue;
    console.log(`\n${id}: ${f.label}`);
    const geom = ee.Geometry.Polygon([f.ring]);
    const seasons = SEASONS[f.hemisphere];
    const res = { label: f.label, hemisphere: f.hemisphere, seasons: {}, kappa_between_seasons: {}, sensitivity: { k: {}, smooth_off: null, hotspots_z: {} }, area: null };
    const maps = {};
    for (const [name, s, e] of seasons) {
      const zr = await zones(geom, s, e); maps[name] = zr.image;
      res.seasons[name] = { window: [s, e], n_scenes: zr.n_scenes, zones: zr.rows };
      console.log(`  ${name}: ${zr.n_scenes} scenes; zones`, zr.rows.map(r => `${r.area_ha} ha / ${r.mean_ndvi}`).join(' | '));
    }
    for (let i = 0; i < seasons.length; i++) for (let j = i + 1; j < seasons.length; j++) {
      const a = seasons[i][0], b = seasons[j][0];
      res.kappa_between_seasons[`${a} vs ${b}`] = await kappa(maps[a], maps[b], geom, 3);
      console.log(`  kappa ${a} vs ${b}:`, res.kappa_between_seasons[`${a} vs ${b}`]);
    }
    const [lname, ls, le] = seasons[seasons.length - 1];
    for (const k of [2, 4]) { const zk = await zones(geom, ls, le, k); res.sensitivity.k[k] = { zones: zk.rows }; }
    const zs = await zones(geom, ls, le, 3, false);
    res.sensitivity.smooth_off = { zones: zs.rows, kappa_vs_released: await kappa(maps[lname], zs.image, geom, 3) };
    for (const z of [1, 1.5, 2]) { res.sensitivity.hotspots_z[z] = await hotspots(geom, ls, le, z); console.log(`  hotspots z<=-${z}:`, res.sensitivity.hotspots_z[z]); }
    res.area = await areaCheck(geom, ls, le);
    console.log('  area:', res.area);
    out.fields[id] = res;
    writeFileSync(resolve(ROOT, 'eval/results/zone_stability.json'), JSON.stringify(out, null, 1));
  }
  console.log('\nok -> eval/results/zone_stability.json');
}
main().catch(e => { console.error(e); process.exit(1); });
