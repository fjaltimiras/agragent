// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 Francisco Altimiras. See LICENSING.md.
/* eslint-disable */
// ============================================================================
//  AgrAgent · Spectral index catalog
// ============================================================================
//  Single source of truth for every layer the map module can render.
//
//  Before this file each index lived in six disconnected places (INDEX_META,
//  INDEX_TIPS, a switch in buildImageAndVis, a button, two <option> lists and
//  three i18n blocks) and the colour ramp was written twice -- once as a GEE
//  palette, once as a CSS gradient -- with nothing keeping them in sync. Adding
//  an index meant six edits. Now it means one entry here.
//
//  Consumed by:
//    - app.html            (renders tiles, legend, buttons, compare selects)
//    - scripts/export-index-thumbnails.mjs  (renders the landing gallery PNGs)
//
//  Entry shape
//  -----------
//    group      key into GROUPS below
//    long       full name, English, language-neutral
//    formula    human-readable maths shown under the legend
//    bands      Sentinel-2 bands the index consumes (documentation + thumbnails)
//    build(img) receives ONE ee.Image with raw Sentinel-2 DN bands and returns
//               the ee.Image to render. Reflectance is DN/10000.
//    perScene   true when build() needs per-scene metadata (sun/view angles).
//               The caller then maps build() over the collection and composites
//               the RESULT, instead of building from an already-median image.
//    vis        { min, max, palette } -- the CSS legend gradient is derived
//               from palette, so the two can no longer drift apart.
//    labels     legend tick labels (numeric, language-neutral)
//    text       { en|es|pt: { label, good, alert, when } } -- button caption and
//               agronomic interpretation. Kept here rather than in app.html's
//               i18n block so the catalog stays self-contained for Node.
//    reference  primary literature, shown in the landing gallery
// ============================================================================

(function (root) {
  'use strict';

  // ── Groups ────────────────────────────────────────────────────────────────
  var GROUPS = {
    vigor:       { icon: 'i-leaf',       i18n: 'idx_vigor',        order: 1 },
    health:      { icon: 'i-flask',      i18n: 'idx_crop_health',  order: 2 },
    water:       { icon: 'i-droplet',    i18n: 'idx_water',        order: 3 },
    soil:        { icon: 'i-mountain',   i18n: 'idx_soil',         order: 4 },
    biophysical: { icon: 'i-microscope', i18n: 'idx_biophysical',  order: 5 },
    visual:      { icon: 'i-palette',    i18n: 'idx_photo',        order: 6 },
    ai:          { icon: 'i-satellite',  i18n: 'idx_ai',           order: 7 }
  };

  // ── Shared colour ramps ───────────────────────────────────────────────────
  // Every gradient in the UI is derived from these, so palette and legend
  // cannot diverge the way the old hand-written CSS gradients did.
  var P = {
    veg:     ['d73027','f46d43','fdae61','fee08b','d9ef8b','a6d96a','66bd63','1a9850'],
    veg6:    ['d73027','fdae61','fee08b','d9ef8b','66bd63','1a9850'],
    chloro:  ['d73027','fdae61','fee08b','a6d96a','1a9850','006837'],
    stress:  ['1a9850','d9ef8b','fdae61','d73027'],          // low = healthy
    senesc:  ['1a9850','a6d96a','fee08b','fdae61','d73027'],
    water:   ['d73027','f46d43','fdae61','abd9e9','74add1','4575b4'],
    wetness: ['f5f5f5','abd9e9','74add1','4575b4','313695'],
    ndwi:    ['a6611a','dfc27d','f5f5f5','80cdc1','018571'],
    soil:    ['1a9850','a6d96a','fee08b','c8a46e','8B4513'],
    residue: ['f5f5f5','dfc27d','c8a46e','8B4513'],
    carbon:  ['3b2412','8B4513','c8a46e','dfc27d','f5f5f5']
  };

  // ── Band helpers ──────────────────────────────────────────────────────────
  // Sentinel-2 L2A stores reflectance as integers scaled by 10000.
  function R(img, band) { return img.select(band).divide(10000); }
  function nd(img, a, b) { return img.normalizedDifference([a, b]); }

  // ── SL2P: ESA S2ToolBox biophysical processor ─────────────────────────────
  // Two-layer neural net (11 inputs -> 5 tansig neurons -> linear output),
  // one net per variable. Coefficients live in sl2p-weights.js; the forward
  // pass below mirrors applyNet() in LEAF-Toolbox/toolsNets.py.
  //
  // The three geometry inputs are per-scene metadata, which is why every SL2P
  // entry sets perScene: true -- a median composite has no viewing angles.
  function sl2p(img, key) {
    var nets = root.SL2P_NETS || (typeof SL2P_NETS !== 'undefined' ? SL2P_NETS : null);
    if (!nets || !nets[key]) throw new Error('SL2P weights not loaded for ' + key);
    var net = nets[key];
    var D2R = Math.PI / 180;

    var vz  = ee.Number(img.get('MEAN_INCIDENCE_ZENITH_ANGLE_B8A')).multiply(D2R);
    var sz  = ee.Number(img.get('MEAN_SOLAR_ZENITH_ANGLE')).multiply(D2R);
    var raa = ee.Number(img.get('MEAN_SOLAR_AZIMUTH_ANGLE'))
                .subtract(ee.Number(img.get('MEAN_INCIDENCE_AZIMUTH_ANGLE_B8A'))).multiply(D2R);

    var inputs = [
      ee.Image.constant(vz.cos()),
      ee.Image.constant(sz.cos()),
      ee.Image.constant(raa.cos())
    ];
    ['B3','B4','B5','B6','B7','B8A','B11','B12'].forEach(function (b) {
      inputs.push(R(img, b));
    });

    // input normalisation
    var x = inputs.map(function (im, i) {
      return im.multiply(net.inpSlope[i]).add(net.inpOffset[i]);
    });

    // hidden layer, tansig(n) = 2/(1+e^-2n) - 1
    var hidden = [];
    for (var n = 0; n < net.h1bi.length; n++) {
      var acc = ee.Image.constant(net.h1bi[n]);
      for (var i = 0; i < x.length; i++) {
        acc = acc.add(x[i].multiply(net.h1wt[n * x.length + i]));
      }
      hidden.push(ee.Image(2).divide(ee.Image(1).add(acc.multiply(-2).exp())).subtract(1));
    }

    // linear output layer + inverse output scaling
    var y = ee.Image.constant(net.h2bi[0]);
    for (var k = 0; k < hidden.length; k++) y = y.add(hidden[k].multiply(net.h2wt[k]));

    // Clamp to the range the network can actually produce, not to the
    // dictionary's outMax. Those are ESA validity thresholds for QC flagging,
    // and for CCC the threshold (100 ug/cm2) sits well inside the attainable
    // range (3-652): using it as a ceiling flattened every healthy canopy --
    // a dense crop reaches ~150-220 -- and destroyed exactly the variation the
    // layer exists to show. For LAI, FAPAR and FCOVER the two agree anyway
    // (9.24 vs 10, 0.97 vs 1), so only CCC was affected.
    var lo = (-1 - net.outBias[0]) / net.outSlope[0];
    var hi = (1 - net.outBias[0]) / net.outSlope[0];
    var floor = Math.max(net.outMin, Math.min(lo, hi));
    var ceil = Math.max(lo, hi);

    return y.subtract(net.outBias[0]).divide(net.outSlope[0])
            .clamp(floor, ceil)
            .rename(key);
  }

  // ── Catalog ───────────────────────────────────────────────────────────────
  var CATALOG = {

    // ═══ Vigor ══════════════════════════════════════════════════════════════
    NDVI: {
      group: 'vigor',
      long: 'Normalized Difference Vegetation Index',
      formula: '(NIR - RED) / (NIR + RED) · B8, B4',
      bands: ['B8', 'B4'],
      build: function (img) { return nd(img, 'B8', 'B4').rename('NDVI'); },
      vis: { min: 0, max: 0.9, palette: P.veg },
      labels: ['0.0', '0.3', '0.5', '0.7', '0.9'],
      reference: 'Rouse et al. 1974',
      text: {
        en: { label: 'Health', good: '> 0.6: active vigour, crop in good condition',
              alert: '< 0.3: check irrigation, nutrition or pest pressure',
              when: 'All year · baseline seasonal monitoring index' },
        es: { label: 'Salud', good: '> 0.6: vigor activo, cultivo en buen estado',
              alert: '< 0.3: revisar riego, nutrición o presencia de plagas',
              when: 'Todo el año · índice base de monitoreo estacional' },
        pt: { label: 'Saúde', good: '> 0,6: vigor ativo, cultura em bom estado',
              alert: '< 0,3: revisar irrigação, nutrição ou presença de pragas',
              when: 'Todo o ano · índice base de monitoramento sazonal' }
      }
    },

    EVI: {
      group: 'vigor',
      long: 'Enhanced Vegetation Index',
      formula: '2.5·(NIR-RED) / (NIR + 6·RED - 7.5·BLUE + 1) · B8, B4, B2',
      bands: ['B8', 'B4', 'B2'],
      build: function (img) {
        var nir = R(img, 'B8'), red = R(img, 'B4'), blue = R(img, 'B2');
        return nir.subtract(red).multiply(2.5)
                  .divide(nir.add(red.multiply(6)).subtract(blue.multiply(7.5)).add(1))
                  .rename('EVI');
      },
      vis: { min: 0, max: 0.7, palette: P.veg },
      labels: ['0.0', '0.15', '0.3', '0.5', '0.7'],
      reference: 'Huete et al. 2002',
      text: {
        en: { label: 'Vigor+', good: '> 0.5: dense, active canopy',
              alert: '< 0.2: possible water stress or low leaf density',
              when: 'Best on dense canopies: vineyards and orchards' },
        es: { label: 'Vigor+', good: '> 0.5: dosel denso y activo',
              alert: '< 0.2: posible estrés hídrico o baja densidad foliar',
              when: 'Mejor en cultivos densos: viñedos y frutales' },
        pt: { label: 'Vigor+', good: '> 0,5: dossel denso e ativo',
              alert: '< 0,2: possível estresse hídrico ou baixa densidade foliar',
              when: 'Melhor em culturas densas: vinhedos e frutíferas' }
      }
    },

    SAVI: {
      group: 'vigor',
      long: 'Soil-Adjusted Vegetation Index',
      formula: '1.5·(NIR-RED) / (NIR + RED + 0.5) · B8, B4',
      bands: ['B8', 'B4'],
      build: function (img) {
        var nir = R(img, 'B8'), red = R(img, 'B4');
        return nir.subtract(red).multiply(1.5).divide(nir.add(red).add(0.5)).rename('SAVI');
      },
      vis: { min: 0, max: 0.8, palette: P.veg6 },
      labels: ['0.0', '0.2', '0.4', '0.6', '0.8'],
      reference: 'Huete 1988',
      text: {
        en: { label: 'Young Plants', good: '> 0.4: good vegetative development',
              alert: '< 0.15: low cover, review planting density',
              when: 'Early season · young or recently transplanted crops' },
        es: { label: 'Plantas Jóvenes', good: '> 0.4: buen desarrollo vegetativo',
              alert: '< 0.15: cobertura baja, evaluar densidad de siembra',
              when: 'Inicio de temporada · plantas jóvenes o recién transplantadas' },
        pt: { label: 'Plantas Jovens', good: '> 0,4: bom desenvolvimento vegetativo',
              alert: '< 0,15: cobertura baixa, avaliar densidade de plantio',
              when: 'Início de temporada · plantas jovens ou recém-transplantadas' }
      }
    },

    MSAVI: {
      group: 'vigor',
      long: 'Modified Soil-Adjusted Vegetation Index',
      formula: '(2·NIR + 1 - sqrt((2·NIR+1)^2 - 8·(NIR-RED))) / 2 · B8, B4',
      bands: ['B8', 'B4'],
      build: function (img) {
        var nir = R(img, 'B8'), red = R(img, 'B4');
        var a = nir.multiply(2).add(1);
        return a.subtract(a.multiply(a).subtract(nir.subtract(red).multiply(8)).sqrt())
                .divide(2).rename('MSAVI');
      },
      vis: { min: 0, max: 0.8, palette: P.veg6 },
      labels: ['0.0', '0.2', '0.4', '0.6', '0.8'],
      reference: 'Qi et al. 1994',
      text: {
        en: { label: 'Sparse Cover', good: '> 0.4: established vegetation',
              alert: '< 0.1: soil dominates, very low cover',
              when: 'Early season · plots with gaps or poor emergence' },
        es: { label: 'Cobertura Rala', good: '> 0.4: vegetación establecida',
              alert: '< 0.1: suelo dominante, cobertura muy baja',
              when: 'Inicio de temporada · parcelas con claros o baja emergencia' },
        pt: { label: 'Cobertura Rala', good: '> 0,4: vegetação estabelecida',
              alert: '< 0,1: solo dominante, cobertura muito baixa',
              when: 'Início de temporada · parcelas com falhas ou baixa emergência' }
      }
    },

    // ═══ Crop health · red edge & chlorophyll ═══════════════════════════════
    NDRE: {
      group: 'health',
      long: 'Normalized Difference Red Edge',
      formula: '(NIR - RE1) / (NIR + RE1) · B8, B5',
      bands: ['B8', 'B5'],
      build: function (img) { return nd(img, 'B8', 'B5').rename('NDRE'); },
      vis: { min: -0.1, max: 0.5, palette: P.veg6 },
      labels: ['-0.1', '0.1', '0.2', '0.4', '0.5'],
      reference: 'Gitelson & Merzlyak 1994',
      text: {
        en: { label: 'Nutrition', good: '> 0.3: adequate nitrogen status',
              alert: '< 0.15: likely nitrogen deficiency',
              when: 'Pre-flowering and fruit set · calibrate fertilisation plan' },
        es: { label: 'Nutrición', good: '> 0.3: estado nutricional N adecuado',
              alert: '< 0.15: probable deficiencia de nitrógeno',
              when: 'Pre-floración y cuaje · calibrar plan de fertilización' },
        pt: { label: 'Nutrição', good: '> 0,3: estado nutricional N adequado',
              alert: '< 0,15: provável deficiência de nitrogênio',
              when: 'Pré-floração e frutificação · calibrar plano de fertilização' }
      }
    },

    GNDVI: {
      group: 'health',
      long: 'Green Normalized Difference Vegetation Index',
      formula: '(NIR - GREEN) / (NIR + GREEN) · B8, B3',
      bands: ['B8', 'B3'],
      build: function (img) { return nd(img, 'B8', 'B3').rename('GNDVI'); },
      vis: { min: 0, max: 0.8, palette: P.veg6 },
      labels: ['0.0', '0.2', '0.4', '0.6', '0.8'],
      reference: 'Gitelson et al. 1996',
      text: {
        en: { label: 'Early Stress', good: '> 0.5: high chlorophyll, healthy leaves',
              alert: '< 0.25: chlorosis or active nutritional stress',
              when: 'Mid-season · leaf health monitoring' },
        es: { label: 'Estrés Temprano', good: '> 0.5: clorofila alta, hoja sana',
              alert: '< 0.25: clorosis o estrés nutricional activo',
              when: 'Mitad de temporada · monitoreo de salud foliar' },
        pt: { label: 'Estresse Precoce', good: '> 0,5: clorofila alta, folha sadia',
              alert: '< 0,25: clorose ou estresse nutricional ativo',
              when: 'Meio da temporada · monitoramento da saúde foliar' }
      }
    },

    TCARI: {
      group: 'health',
      long: 'Transformed Chlorophyll Absorption in Reflectance Index',
      formula: '3·[(RE1-RED) - 0.2·(RE1-GREEN)·(RE1/RED)] · B5, B4, B3',
      bands: ['B5', 'B4', 'B3'],
      build: function (img) {
        var g = R(img, 'B3'), r = R(img, 'B4'), re = R(img, 'B5');
        return re.subtract(r)
                 .subtract(re.subtract(g).multiply(0.2).multiply(re.divide(r.add(1e-6))))
                 .multiply(3).rename('TCARI');
      },
      vis: { min: 0, max: 0.5, palette: P.stress },
      labels: ['0.0', '0.1', '0.2', '0.3', '0.5'],
      reference: 'Haboudane et al. 2002',
      text: {
        en: { label: 'Chlorophyll', good: '< 0.15: healthy crop, high chlorophyll',
              alert: '> 0.30: chlorosis, pest damage or foliar fungi',
              when: 'Flowering and fruit development · early pathogen detection' },
        es: { label: 'Clorofila', good: '< 0.15: cultivo sano, alta clorofila',
              alert: '> 0.30: clorosis, daño por plagas o hongos foliares',
              when: 'Floración y desarrollo de fruto · detección temprana de patógenos' },
        pt: { label: 'Clorofila', good: '< 0,15: cultura sadia, alta clorofila',
              alert: '> 0,30: clorose, dano por pragas ou fungos foliares',
              when: 'Floração e desenvolvimento do fruto · detecção precoce de patógenos' }
      }
    },

    CIRE: {
      group: 'health',
      long: 'Chlorophyll Index Red Edge',
      formula: '(NIR / RE1) - 1 · B8, B5',
      bands: ['B8', 'B5'],
      build: function (img) {
        return R(img, 'B8').divide(R(img, 'B5').add(1e-6)).subtract(1).rename('CIRE');
      },
      vis: { min: 0, max: 3, palette: P.chloro },
      labels: ['0', '0.5', '1.0', '2.0', '3.0'],
      reference: 'Gitelson et al. 2003',
      text: {
        en: { label: 'N-Status', good: '> 1.5: adequate leaf nitrogen content',
              alert: '< 0.8: apply foliar nitrogen fertilisation',
              when: 'Pre-flowering · calibrate nitrogen dose' },
        es: { label: 'Estado N', good: '> 1.5: contenido de N foliar adecuado',
              alert: '< 0.8: aplicar fertilización nitrogenada foliar',
              when: 'Pre-floración · calibrar dosis de nitrógeno' },
        pt: { label: 'Estado N', good: '> 1,5: teor de N foliar adequado',
              alert: '< 0,8: aplicar fertilização nitrogenada foliar',
              when: 'Pré-floração · calibrar dose de nitrogênio' }
      }
    },

    NDRE705: {
      group: 'health',
      long: 'Red Edge NDVI (740/705)',
      formula: '(RE2 - RE1) / (RE2 + RE1) · B6, B5',
      bands: ['B6', 'B5'],
      build: function (img) { return nd(img, 'B6', 'B5').rename('NDRE705'); },
      vis: { min: 0, max: 0.6, palette: P.veg6 },
      labels: ['0.0', '0.15', '0.3', '0.45', '0.6'],
      reference: 'Gitelson & Merzlyak 1994',
      text: {
        en: { label: 'Red Edge', good: '> 0.35: dense canopy with high chlorophyll',
              alert: '< 0.15: thin canopy or early chlorophyll loss',
              when: 'Saturates later than NDVI · useful on dense canopies' },
        es: { label: 'Red Edge', good: '> 0.35: dosel denso con clorofila alta',
              alert: '< 0.15: dosel ralo o pérdida temprana de clorofila',
              when: 'Satura más tarde que NDVI · útil en doseles densos' },
        pt: { label: 'Red Edge', good: '> 0,35: dossel denso com clorofila alta',
              alert: '< 0,15: dossel ralo ou perda precoce de clorofila',
              when: 'Satura mais tarde que o NDVI · útil em dosséis densos' }
      }
    },

    MCARI: {
      group: 'health',
      long: 'Modified Chlorophyll Absorption in Reflectance Index',
      formula: '[(RE1-RED) - 0.2·(RE1-GREEN)] · (RE1/RED) · B5, B4, B3',
      bands: ['B5', 'B4', 'B3'],
      build: function (img) {
        var g = R(img, 'B3'), r = R(img, 'B4'), re = R(img, 'B5');
        return re.subtract(r).subtract(re.subtract(g).multiply(0.2))
                 .multiply(re.divide(r.add(1e-6))).rename('MCARI');
      },
      vis: { min: 0, max: 1, palette: P.chloro },
      labels: ['0.0', '0.25', '0.5', '0.75', '1.0'],
      reference: 'Daughtry et al. 2000',
      text: {
        en: { label: 'Leaf Chlorophyll', good: '> 0.4: strong chlorophyll absorption',
              alert: '< 0.1: low pigment content or very sparse canopy',
              when: 'Complements TCARI · sensitive to leaf pigments' },
        es: { label: 'Clorofila Foliar', good: '> 0.4: absorción de clorofila marcada',
              alert: '< 0.1: bajo contenido de pigmentos o dosel muy ralo',
              when: 'Complementa TCARI · sensible a pigmentos foliares' },
        pt: { label: 'Clorofila Foliar', good: '> 0,4: absorção de clorofila marcada',
              alert: '< 0,1: baixo teor de pigmentos ou dossel muito ralo',
              when: 'Complementa TCARI · sensível a pigmentos foliares' }
      }
    },

    MTCI: {
      group: 'health',
      long: 'MERIS Terrestrial Chlorophyll Index',
      formula: '(RE2 - RE1) / (RE1 - RED) · B6, B5, B4',
      bands: ['B6', 'B5', 'B4'],
      build: function (img) {
        var r = R(img, 'B4'), re1 = R(img, 'B5'), re2 = R(img, 'B6');
        return re2.subtract(re1).divide(re1.subtract(r).add(1e-6)).rename('MTCI');
      },
      vis: { min: 0, max: 5, palette: P.chloro },
      labels: ['0', '1', '2', '3.5', '5'],
      reference: 'Dash & Curran 2004',
      text: {
        en: { label: 'Chlorophyll MTCI', good: '> 3: high leaf chlorophyll content',
              alert: '< 1.5: chlorophyll loss, senescence or nitrogen deficit',
              when: 'One of the strongest predictors of leaf chlorophyll on S2' },
        es: { label: 'Clorofila MTCI', good: '> 3: contenido alto de clorofila foliar',
              alert: '< 1.5: pérdida de clorofila, senescencia o déficit de N',
              when: 'De los mejores predictores de clorofila foliar en S2' },
        pt: { label: 'Clorofila MTCI', good: '> 3: teor alto de clorofila foliar',
              alert: '< 1,5: perda de clorofila, senescência ou déficit de N',
              when: 'Um dos melhores preditores de clorofila foliar no S2' }
      }
    },

    IRECI: {
      group: 'health',
      long: 'Inverted Red-Edge Chlorophyll Index',
      formula: '(RE3 - RED) / (RE1 / RE2) · B7, B4, B5, B6',
      bands: ['B7', 'B4', 'B5', 'B6'],
      build: function (img) {
        var r = R(img, 'B4'), re1 = R(img, 'B5'), re2 = R(img, 'B6'), re3 = R(img, 'B7');
        return re3.subtract(r).divide(re1.divide(re2.add(1e-6)).add(1e-6)).rename('IRECI');
      },
      vis: { min: 0, max: 3, palette: P.chloro },
      labels: ['0', '0.75', '1.5', '2.25', '3'],
      reference: 'Frampton et al. 2013',
      text: {
        en: { label: 'CCC Proxy', good: '> 1.5: high canopy chlorophyll content',
              alert: '< 0.5: low chlorophyll or sparse canopy',
              when: 'Near 1:1 with CCC in g/m2 · sanity check for the SL2P product' },
        es: { label: 'Proxy CCC', good: '> 1.5: contenido de clorofila del dosel alto',
              alert: '< 0.5: clorofila baja o dosel ralo',
              when: 'Relación ~1:1 con CCC en g/m2 · control de sanidad del producto SL2P' },
        pt: { label: 'Proxy CCC', good: '> 1,5: teor de clorofila do dossel alto',
              alert: '< 0,5: clorofila baixa ou dossel ralo',
              when: 'Relação ~1:1 com CCC em g/m2 · verificação do produto SL2P' }
      }
    },

    S2REP: {
      group: 'health',
      long: 'Sentinel-2 Red-Edge Position',
      formula: '705 + 35·[((RED+RE3)/2 - RE1) / (RE2 - RE1)] · B4, B7, B5, B6',
      bands: ['B4', 'B7', 'B5', 'B6'],
      build: function (img) {
        var r = R(img, 'B4'), re1 = R(img, 'B5'), re2 = R(img, 'B6'), re3 = R(img, 'B7');
        return r.add(re3).divide(2).subtract(re1)
                .divide(re2.subtract(re1).add(1e-6))
                .multiply(35).add(705).rename('S2REP');
      },
      vis: { min: 700, max: 740, palette: P.chloro },
      labels: ['700', '710', '720', '730', '740'],
      reference: 'Frampton et al. 2013',
      text: {
        en: { label: 'Red Edge Position', good: '> 725 nm: chlorophyll-rich canopy',
              alert: '< 710 nm: red edge shifting to blue, early stress',
              when: 'Shifts before NDVI drops · early physiological signal' },
        es: { label: 'Posición Red Edge', good: '> 725 nm: dosel rico en clorofila',
              alert: '< 710 nm: red edge desplazado al azul, estrés temprano',
              when: 'Se desplaza antes de que caiga el NDVI · señal fisiológica temprana' },
        pt: { label: 'Posição Red Edge', good: '> 725 nm: dossel rico em clorofila',
              alert: '< 710 nm: red edge deslocado ao azul, estresse precoce',
              when: 'Desloca-se antes da queda do NDVI · sinal fisiológico precoce' }
      }
    },

    CCCI: {
      group: 'health',
      long: 'Canopy Chlorophyll Content Index',
      formula: 'NDRE / NDVI · B8, B5, B4',
      bands: ['B8', 'B5', 'B4'],
      build: function (img) {
        return nd(img, 'B8', 'B5').divide(nd(img, 'B8', 'B4').add(1e-6)).rename('CCCI');
      },
      vis: { min: 0, max: 1, palette: P.chloro },
      labels: ['0.0', '0.25', '0.5', '0.75', '1.0'],
      reference: 'Barnes et al. 2000',
      text: {
        en: { label: 'N Index', good: '> 0.6: nitrogen status not limiting',
              alert: '< 0.35: nitrogen deficit independent of biomass',
              when: 'Normalises NDRE by cover · compares plots of different vigour' },
        es: { label: 'Índice N', good: '> 0.6: estado nitrogenado no limitante',
              alert: '< 0.35: déficit de nitrógeno independiente de la biomasa',
              when: 'Normaliza NDRE por cobertura · compara lotes de distinto vigor' },
        pt: { label: 'Índice N', good: '> 0,6: estado nitrogenado não limitante',
              alert: '< 0,35: déficit de nitrogênio independente da biomassa',
              when: 'Normaliza NDRE pela cobertura · compara lotes de vigor distinto' }
      }
    },

    PSRI: {
      group: 'health',
      long: 'Plant Senescence Reflectance Index',
      formula: '(RED - BLUE) / RE2 · B4, B2, B6',
      bands: ['B4', 'B2', 'B6'],
      build: function (img) {
        return R(img, 'B4').subtract(R(img, 'B2'))
                 .divide(R(img, 'B6').add(1e-6)).rename('PSRI');
      },
      vis: { min: -0.2, max: 0.4, palette: P.senesc },
      labels: ['-0.2', '-0.05', '0.1', '0.25', '0.4'],
      reference: 'Merzlyak et al. 1999',
      text: {
        en: { label: 'Senescence', good: '< 0: green canopy, no senescence',
              alert: '> 0.2: active senescence or carotenoid accumulation',
              when: 'End of season · ripening and harvest timing' },
        es: { label: 'Senescencia', good: '< 0: dosel verde, sin senescencia',
              alert: '> 0.2: senescencia activa o acumulación de carotenoides',
              when: 'Fin de temporada · maduración y momento de cosecha' },
        pt: { label: 'Senescência', good: '< 0: dossel verde, sem senescência',
              alert: '> 0,2: senescência ativa ou acúmulo de carotenoides',
              when: 'Fim de temporada · maturação e momento de colheita' }
      }
    },

    // ═══ Water ══════════════════════════════════════════════════════════════
    NDMI: {
      group: 'water',
      long: 'Normalized Difference Moisture Index',
      formula: '(NIR - SWIR1) / (NIR + SWIR1) · B8, B11',
      bands: ['B8', 'B11'],
      build: function (img) { return nd(img, 'B8', 'B11').rename('NDMI'); },
      vis: { min: -0.5, max: 0.6, palette: P.water },
      labels: ['-0.5', '-0.2', '0.0', '0.3', '0.6'],
      reference: 'Gao 1996',
      text: {
        en: { label: 'Moisture', good: '> 0.2: adequate water content',
              alert: '< -0.1: active water stress, bring irrigation forward',
              when: 'Dry summers · irrigation scheduling' },
        es: { label: 'Humedad', good: '> 0.2: contenido hídrico adecuado',
              alert: '< -0.1: estrés hídrico activo, adelantar turno de riego',
              when: 'Veranos secos · programar frecuencia de riego' },
        pt: { label: 'Umidade', good: '> 0,2: teor hídrico adequado',
              alert: '< -0,1: estresse hídrico ativo, antecipar a irrigação',
              when: 'Verões secos · programar frequência de irrigação' }
      }
    },

    NDWI: {
      group: 'water',
      long: 'Normalized Difference Water Index',
      formula: '(GREEN - NIR) / (GREEN + NIR) · B3, B8',
      bands: ['B3', 'B8'],
      build: function (img) { return nd(img, 'B3', 'B8').rename('NDWI'); },
      vis: { min: -0.5, max: 0.5, palette: P.ndwi },
      labels: ['-0.5', '-0.2', '0.0', '0.2', '0.5'],
      reference: 'McFeeters 1996',
      text: {
        en: { label: 'Standing Water', good: '< 0: no free surface water',
              alert: '> 0.1: waterlogging or excess water',
              when: 'After heavy rain · find poorly drained areas' },
        es: { label: 'Agua Libre', good: '< 0: sin agua libre superficial',
              alert: '> 0.1: zona con exceso de agua o anegamiento',
              when: 'Post-lluvia intensa · detectar zonas de drenaje deficiente' },
        pt: { label: 'Água Livre', good: '< 0: sem água livre superficial',
              alert: '> 0,1: zona com excesso de água ou encharcamento',
              when: 'Após chuva intensa · detectar zonas de drenagem deficiente' }
      }
    },

    // ═══ Soil ═══════════════════════════════════════════════════════════════
    BSI: {
      group: 'soil',
      long: 'Bare Soil Index',
      formula: '[(SWIR1+RED) - (NIR+BLUE)] / [(SWIR1+RED) + (NIR+BLUE)] · B11, B4, B8, B2',
      bands: ['B11', 'B4', 'B8', 'B2'],
      build: function (img) {
        var s = R(img, 'B11'), r = R(img, 'B4'), n = R(img, 'B8'), b = R(img, 'B2');
        var num = s.add(r).subtract(n).subtract(b);
        var den = s.add(r).add(n).add(b).add(1e-6);
        return num.divide(den).rename('BSI');
      },
      vis: { min: -0.4, max: 0.4, palette: P.soil },
      labels: ['-0.4', '-0.1', '0.0', '0.2', '0.4'],
      reference: 'Rikimaru et al. 2002',
      text: {
        en: { label: 'Bare Soil', good: '< -0.1: good vegetative soil cover',
              alert: '> 0.2: exposed soil, erosion or crop failure',
              when: 'Pre-sowing and post-harvest · residue cover assessment' },
        es: { label: 'Suelo Desnudo', good: '< -0.1: buena cobertura vegetal del suelo',
              alert: '> 0.2: suelo expuesto, erosión o falla en cultivo',
              when: 'Pre-siembra y post-cosecha · evaluación de cobertura residual' },
        pt: { label: 'Solo Exposto', good: '< -0,1: boa cobertura vegetal do solo',
              alert: '> 0,2: solo exposto, erosão ou falha na cultura',
              when: 'Pré-semeadura e pós-colheita · avaliação da cobertura residual' }
      }
    },

    NBR2: {
      group: 'soil',
      long: 'Normalized Burn Ratio 2 (crop residue)',
      formula: '(SWIR1 - SWIR2) / (SWIR1 + SWIR2) · B11, B12',
      bands: ['B11', 'B12'],
      build: function (img) { return nd(img, 'B11', 'B12').rename('NBR2'); },
      vis: { min: 0, max: 0.4, palette: P.residue },
      labels: ['0.0', '0.1', '0.2', '0.3', '0.4'],
      reference: 'Key & Benson 2006',
      text: {
        en: { label: 'Crop Residue', good: '> 0.2: good residue cover, soil protected',
              alert: '< 0.05: bare, tilled soil exposed to erosion',
              when: 'Between seasons · separates dry residue from bare soil' },
        es: { label: 'Rastrojo', good: '> 0.2: buena cobertura de rastrojo, suelo protegido',
              alert: '< 0.05: suelo desnudo y laboreado, expuesto a erosión',
              when: 'Entre temporadas · distingue rastrojo seco de suelo desnudo' },
        pt: { label: 'Palhada', good: '> 0,2: boa cobertura de palhada, solo protegido',
              alert: '< 0,05: solo nu e preparado, exposto à erosão',
              when: 'Entre safras · distingue palhada seca de solo nu' }
      }
    },

    SOCI: {
      group: 'soil',
      long: 'Soil Organic Carbon Index',
      formula: 'BLUE / (GREEN · RED) · B2, B3, B4',
      bands: ['B2', 'B3', 'B4'],
      build: function (img) {
        return R(img, 'B2')
                 .divide(R(img, 'B3').multiply(R(img, 'B4')).add(1e-6))
                 .rename('SOCI');
      },
      vis: { min: 0, max: 15, palette: P.carbon },
      labels: ['0', '4', '8', '11', '15'],
      reference: 'Thaler et al. 2019',
      text: {
        en: { label: 'Organic Carbon', good: '< 5: dark soil, higher organic carbon',
              alert: '> 12: light soil, low organic matter',
              when: 'Read on bare soil only · inverse to organic carbon content' },
        es: { label: 'Carbono Orgánico', good: '< 5: suelo oscuro, mayor carbono orgánico',
              alert: '> 12: suelo claro, baja materia orgánica',
              when: 'Leer solo sobre suelo desnudo · es inverso al carbono orgánico' },
        pt: { label: 'Carbono Orgânico', good: '< 5: solo escuro, maior carbono orgânico',
              alert: '> 12: solo claro, baixa matéria orgânica',
              when: 'Ler apenas sobre solo nu · é inverso ao carbono orgânico' }
      }
    },

    SOIL_FRAC: {
      group: 'soil',
      long: 'Exposed Soil Fraction (1 - FCOVER)',
      formula: '1 - FCOVER · SL2P neural net · B3-B12 + geometry',
      bands: ['B3', 'B4', 'B5', 'B6', 'B7', 'B8A', 'B11', 'B12'],
      perScene: true,
      build: function (img) {
        return ee.Image(1).subtract(sl2p(img, 'FCOVER')).rename('SOIL_FRAC');
      },
      vis: { min: 0, max: 1, palette: P.soil },
      labels: ['0%', '25%', '50%', '75%', '100%'],
      reference: 'Weiss & Baret 2016 (S2ToolBox ATBD v2.0)',
      text: {
        en: { label: 'Exposed Soil', good: '< 30%: canopy covers most of the ground',
              alert: '> 60%: most of the plot is bare soil between rows',
              when: 'Physical measure of exposed soil · complements BSI' },
        es: { label: 'Suelo Expuesto', good: '< 30%: el dosel cubre la mayor parte del suelo',
              alert: '> 60%: gran parte del lote es suelo desnudo entre hileras',
              when: 'Medida física de suelo expuesto · complementa al BSI' },
        pt: { label: 'Solo Exposto', good: '< 30%: o dossel cobre a maior parte do solo',
              alert: '> 60%: grande parte do lote é solo nu entre linhas',
              when: 'Medida física de solo exposto · complementa o BSI' }
      }
    },

    // ═══ Biophysical · ESA S2ToolBox (SL2P) ═════════════════════════════════
    // These five are neural-net retrievals, not band ratios: they return
    // physical quantities with units, validated by ESA. All need per-scene sun
    // and view geometry, hence perScene: true.
    LAI: {
      group: 'biophysical',
      long: 'Leaf Area Index (m2/m2)',
      formula: 'SL2P neural net · B3, B4, B5, B6, B7, B8A, B11, B12 + geometry',
      bands: ['B3', 'B4', 'B5', 'B6', 'B7', 'B8A', 'B11', 'B12'],
      perScene: true,
      build: function (img) { return sl2p(img, 'LAI'); },
      // Stretch set from measured p98 across contrasting Chilean fields (2.3)
      // rather than the theoretical ceiling: at 0-6 a vigorous canopy rendered
      // in the red end of the ramp and read as stressed.
      vis: { min: 0, max: 4, palette: P.veg },
      labels: ['0', '1', '2', '3', '4'],
      reference: 'Weiss & Baret 2016 (S2ToolBox ATBD v2.0)',
      text: {
        en: { label: 'Leaf Area', good: '> 3: well developed canopy',
              alert: '< 1: little leaf area, review canopy management',
              when: 'Input to the yield model · drives light interception' },
        es: { label: 'Área Foliar', good: '> 3: dosel bien desarrollado',
              alert: '< 1: poca superficie foliar, revisar manejo de canopia',
              when: 'Insumo del modelo de rendimiento · gobierna la intercepción de luz' },
        pt: { label: 'Área Foliar', good: '> 3: dossel bem desenvolvido',
              alert: '< 1: pouca área foliar, revisar manejo do dossel',
              when: 'Insumo do modelo de produtividade · rege a interceptação de luz' }
      }
    },

    FAPAR: {
      group: 'biophysical',
      long: 'Fraction of Absorbed Photosynthetically Active Radiation',
      formula: 'SL2P neural net · B3, B4, B5, B6, B7, B8A, B11, B12 + geometry',
      bands: ['B3', 'B4', 'B5', 'B6', 'B7', 'B8A', 'B11', 'B12'],
      perScene: true,
      build: function (img) { return sl2p(img, 'FAPAR'); },
      vis: { min: 0, max: 1, palette: P.veg },
      labels: ['0%', '25%', '50%', '75%', '100%'],
      reference: 'Weiss & Baret 2016 (S2ToolBox ATBD v2.0)',
      text: {
        en: { label: 'FAPAR', good: '> 0.7: canopy absorbing most available light',
              alert: '< 0.3: low light interception, limited productivity',
              when: 'Drops before visible symptoms · early stress indicator' },
        es: { label: 'FAPAR', good: '> 0.7: dosel absorbe la mayor parte de la luz disponible',
              alert: '< 0.3: baja intercepción lumínica, productividad limitada',
              when: 'Cae antes que aparezcan síntomas visibles · indicador temprano de estrés' },
        pt: { label: 'FAPAR', good: '> 0,7: dossel absorve a maior parte da luz disponível',
              alert: '< 0,3: baixa interceptação de luz, produtividade limitada',
              when: 'Cai antes dos sintomas visíveis · indicador precoce de estresse' }
      }
    },

    FCOVER: {
      group: 'biophysical',
      long: 'Fraction of Green Vegetation Cover',
      formula: 'SL2P neural net · B3, B4, B5, B6, B7, B8A, B11, B12 + geometry',
      bands: ['B3', 'B4', 'B5', 'B6', 'B7', 'B8A', 'B11', 'B12'],
      perScene: true,
      build: function (img) { return sl2p(img, 'FCOVER'); },
      vis: { min: 0, max: 1, palette: P.veg },
      labels: ['0%', '25%', '50%', '75%', '100%'],
      reference: 'Weiss & Baret 2016 (S2ToolBox ATBD v2.0)',
      text: {
        en: { label: 'Leaf Cover', good: '> 0.7: ground well covered by canopy',
              alert: '< 0.3: sparse canopy, most of the plot is soil',
              when: 'Leaf cover area · its complement is exposed soil' },
        es: { label: 'Cobertura Foliar', good: '> 0.7: suelo bien cubierto por el dosel',
              alert: '< 0.3: dosel ralo, gran parte del lote es suelo',
              when: 'Área de cobertura foliar · su complemento es el suelo expuesto' },
        pt: { label: 'Cobertura Foliar', good: '> 0,7: solo bem coberto pelo dossel',
              alert: '< 0,3: dossel ralo, grande parte do lote é solo',
              when: 'Área de cobertura foliar · seu complemento é o solo exposto' }
      }
    },

    CCC: {
      group: 'biophysical',
      long: 'Canopy Chlorophyll Content (g/m2)',
      formula: 'SL2P neural net · B3, B4, B5, B6, B7, B8A, B11, B12 + geometry',
      bands: ['B3', 'B4', 'B5', 'B6', 'B7', 'B8A', 'B11', 'B12'],
      perScene: true,
      // The network returns ug/cm2; /100 converts to the g/m2 convention used
      // in the ATBD, which is also the unit IRECI tracks roughly 1:1.
      build: function (img) { return sl2p(img, 'CCC').divide(100).rename('CCC'); },
      vis: { min: 0, max: 2, palette: P.chloro },
      labels: ['0', '0.5', '1.0', '1.5', '2.0'],
      reference: 'Weiss & Baret 2016 (S2ToolBox ATBD v2.0)',
      text: {
        en: { label: 'Canopy Chlorophyll', good: '> 2 g/m2: high photosynthetic capacity',
              alert: '< 0.8 g/m2: chlorophyll loss across the canopy',
              when: 'Combines LAI and leaf chlorophyll · early stress detection' },
        es: { label: 'Clorofila del Dosel', good: '> 2 g/m2: alta capacidad fotosintética',
              alert: '< 0.8 g/m2: pérdida de clorofila a nivel de dosel',
              when: 'Integra LAI y clorofila foliar · detección temprana de estrés' },
        pt: { label: 'Clorofila do Dossel', good: '> 2 g/m2: alta capacidade fotossintética',
              alert: '< 0,8 g/m2: perda de clorofila no dossel',
              when: 'Integra LAI e clorofila foliar · detecção precoce de estresse' }
      }
    },

    CWC: {
      group: 'biophysical',
      long: 'Canopy Water Content (kg/m2)',
      formula: 'SL2P neural net · B3, B4, B5, B6, B7, B8A, B11, B12 + geometry',
      bands: ['B3', 'B4', 'B5', 'B6', 'B7', 'B8A', 'B11', 'B12'],
      perScene: true,
      // Network output is g/cm2; x10 gives the conventional kg/m2.
      build: function (img) { return sl2p(img, 'CWC').multiply(10).rename('CWC'); },
      vis: { min: 0, max: 1.5, palette: P.wetness },
      labels: ['0', '0.4', '0.8', '1.1', '1.5'],
      reference: 'Weiss & Baret 2016 (S2ToolBox ATBD v2.0)',
      text: {
        en: { label: 'Canopy Water', good: '> 1 kg/m2: canopy well hydrated',
              alert: '< 0.4 kg/m2: water deficit in canopy tissue',
              when: 'Physical water content · complements the NDMI ratio' },
        es: { label: 'Agua del Dosel', good: '> 1 kg/m2: dosel bien hidratado',
              alert: '< 0.4 kg/m2: déficit hídrico en el tejido del dosel',
              when: 'Contenido físico de agua · complementa la razón NDMI' },
        pt: { label: 'Água do Dossel', good: '> 1 kg/m2: dossel bem hidratado',
              alert: '< 0,4 kg/m2: déficit hídrico no tecido do dossel',
              when: 'Teor físico de água · complementa a razão NDMI' }
      }
    },

    // ═══ Visual composites ══════════════════════════════════════════════════
    RGB: {
      group: 'visual',
      long: 'True Colour',
      formula: 'B4 (Red), B3 (Green), B2 (Blue)',
      bands: ['B4', 'B3', 'B2'],
      composite: true,
      build: function (img) { return img.select(['B4', 'B3', 'B2']); },
      vis: { bands: ['B4', 'B3', 'B2'], min: 0, max: 3000, gamma: 1.4 },
      // Legend strip only. It must stay OUT of vis: Earth Engine refuses a
      // visualization that carries both a gamma and a palette.
      legendPalette: ['1a5ca8', '2e8b57', '8B4513', 'c8a46e', 'f5f5f5'],
      labels: ['Water', 'Vegetation', 'Soil', 'Dry', 'Clouds'],
      labelsI18n: ['lg_water', 'lg_vegetation', 'lg_soil', 'lg_dry', 'lg_clouds'],
      reference: 'Sentinel-2 MSI',
      text: {
        en: { label: 'Real Colour', good: 'Deep, even green = active vegetation',
              alert: 'Yellow or brown tones = senescence or visible stress',
              when: 'General visual reference · quick field inspection' },
        es: { label: 'Color Real', good: 'Verde intenso y uniforme = vegetación activa',
              alert: 'Tonos amarillos o cafés = senescencia o estrés visible',
              when: 'Referencia visual general · inspección rápida del campo' },
        pt: { label: 'Cor Real', good: 'Verde intenso e uniforme = vegetação ativa',
              alert: 'Tons amarelos ou marrons = senescência ou estresse visível',
              when: 'Referência visual geral · inspeção rápida do campo' }
      }
    },

    FALSE: {
      group: 'visual',
      long: 'False Colour Infrared',
      formula: 'B8 (NIR), B4 (Red), B3 (Green) · vegetation = red',
      bands: ['B8', 'B4', 'B3'],
      composite: true,
      build: function (img) { return img.select(['B8', 'B4', 'B3']); },
      vis: { bands: ['B8', 'B4', 'B3'], min: 0, max: 4000, gamma: 1.2 },
      legendPalette: ['1a1a2e', '0d4a1a', '2e8b57', 'c0392b', '8b0000'],
      labels: ['No veg.', 'Low', 'Medium', 'High', 'Very high'],
      labelsI18n: ['lg_noveg', 'lg_low', 'lg_medium', 'lg_high', 'lg_veryhigh'],
      reference: 'Sentinel-2 MSI',
      text: {
        en: { label: 'Infrared', good: 'Deep red = high photosynthetic activity',
              alert: 'Grey or black = no vegetation or severe stress',
              when: 'Quick vigour comparison between plots or seasons' },
        es: { label: 'Infrarrojo', good: 'Rojo intenso = alta actividad fotosintética',
              alert: 'Gris/negro = sin vegetación o estrés severo',
              when: 'Comparación rápida de vigor entre parcelas o temporadas' },
        pt: { label: 'Infravermelho', good: 'Vermelho intenso = alta atividade fotossintética',
              alert: 'Cinza/preto = sem vegetação ou estresse severo',
              when: 'Comparação rápida de vigor entre parcelas ou safras' }
      }
    },

    // ═══ AI · AlphaEarth ════════════════════════════════════════════════════
    // Annual embeddings, not Sentinel-2 reflectance: rendered by their own
    // loader (loadAlphaEarthLayer) rather than through build().
    ALPHAEARTH: {
      group: 'ai',
      dataset: 'GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL',
      long: 'AlphaEarth PCA False Colour',
      formula: 'Google DeepMind · 64-dim embeddings · components 0-1-2 to RGB · annual 2017-2025',
      bands: ['A00', 'A32', 'A63'],
      build: null,
      vis: { palette: ['0d0221', '1a0a4e', '2e1a8c', '4a6fa5', '68c9b0', 'f5f5f5'] },
      labels: ['Pattern A', '', 'Centre', '', 'Pattern B'],
      labelsI18n: ['lg_pattern_a', '', 'lg_centre', '', 'lg_pattern_b'],
      reference: 'Brown et al. 2025 (AlphaEarth Foundations)',
      text: {
        en: { label: 'PCA Colour', good: 'Contrasting colours = spectrally distinct zones',
              alert: 'Uniform area = homogeneous terrain or low contrast',
              when: 'Reveals spatial patterns invisible to single-band indices' },
        es: { label: 'Color PCA', good: 'Colores contrastados = zonas espectralmente distintas',
              alert: 'Zona uniforme = terreno homogéneo o falta de contraste',
              when: 'Identificar patrones espaciales invisibles en índices simples' },
        pt: { label: 'Cor PCA', good: 'Cores contrastantes = zonas espectralmente distintas',
              alert: 'Zona uniforme = terreno homogêneo ou falta de contraste',
              when: 'Identificar padrões espaciais invisíveis em índices simples' }
      }
    },

    ALPHAEARTH_CLASS: {
      group: 'ai',
      dataset: 'GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL',
      long: 'AlphaEarth Unsupervised Groups',
      formula: 'K-means, 4 groups on embeddings A00-A19 · group numbers are arbitrary, not land-cover classes',
      bands: ['A00-A19'],
      build: null,
      vis: { palette: ['1a9850', 'c8a46e', '4575b4', '888888'] },
      // k-means no asigna significado a los grupos: rotularlos como vegetación/agua/etc. inducía a error
      labels: ['Group 1', 'Group 2', 'Group 3', 'Group 4'],
      reference: 'Brown et al. 2025 (AlphaEarth Foundations)',
      text: {
        en: { label: 'AI groups', good: 'Each colour is a group of pixels with a similar annual signature',
              alert: 'Group numbers and colours have no fixed meaning: interpret them on the ground',
              when: 'Spot areas that behave differently within the field' },
        es: { label: 'Grupos IA', good: 'Cada color es un grupo de píxeles con firma anual parecida',
              alert: 'El número y color de cada grupo no tienen significado fijo: interpretarlos en terreno',
              when: 'Detectar sectores que se comportan distinto dentro del campo' },
        pt: { label: 'Grupos IA', good: 'Cada cor é um grupo de pixels com assinatura anual parecida',
              alert: 'O número e a cor de cada grupo não têm significado fixo: interpretá-los em campo',
              when: 'Detectar setores que se comportam diferente dentro do campo' }
      }
    }
  };

  // ── Public API ────────────────────────────────────────────────────────────

  // The single reason palette and legend can no longer drift: the CSS gradient
  // is computed from the same array GEE renders with.
  function gradientCss(id) {
    var e = CATALOG[id];
    if (!e) return '';
    var palette = e.legendPalette || (e.vis && e.vis.palette);
    if (!palette) return '';
    return 'linear-gradient(to right,' + palette.map(function (c) {
      return '#' + c;
    }).join(',') + ')';
  }

  // Indices grouped and ordered, ready to render buttons or <optgroup>s.
  function grouped() {
    var byGroup = {};
    Object.keys(CATALOG).forEach(function (id) {
      var g = CATALOG[id].group;
      (byGroup[g] = byGroup[g] || []).push(id);
    });
    return Object.keys(byGroup)
      .sort(function (a, b) { return GROUPS[a].order - GROUPS[b].order; })
      .map(function (g) {
        return { key: g, icon: GROUPS[g].icon, i18n: GROUPS[g].i18n, indices: byGroup[g] };
      });
  }

  // Localised strings for one index, falling back to English.
  function text(id, lang) {
    var e = CATALOG[id];
    if (!e) return null;
    return e.text[lang] || e.text.en;
  }

  // Ids of every Sentinel-2 index that build() can render directly, i.e.
  // excluding the AlphaEarth layers, which have their own loader.
  function spectralIds() {
    return Object.keys(CATALOG).filter(function (id) { return !!CATALOG[id].build; });
  }

  // ── Realce de contraste por campo ─────────────────────────────────────────
  // vis.min/max cubren el rango agronómico completo del índice (NDVI 0–0,9), así
  // que un cuartel parejo ocupa una franja angosta de la paleta y se ve plano.
  // fieldRange() mide los percentiles 2 y 98 dentro del polígono; applyRange()
  // estira ese tramo a toda la paleta. Todo es server-side (ee.Number), así que
  // getMapId/getThumbURL siguen siendo síncronos. Piso de amplitud: 15 % del rango
  // del catálogo, para no inventar contraste en un campo realmente uniforme.
  // Los compuestos de color (RGB, falso color) no se estiran.
  function canStretch(id) {
    var e = CATALOG[id];
    return !!(e && e.build && e.vis && e.vis.palette && !e.vis.bands);
  }

  function fieldRange(image, geom, id, opts) {
    var e = CATALOG[id];
    opts = opts || {};
    var st = image.select(0).reduceRegion({
      reducer: ee.Reducer.percentile([2, 98]), geometry: geom,
      scale: opts.scale || 10, maxPixels: 1e9, bestEffort: true, tileScale: 2
    });
    var v = st.values();   // claves <banda>_p2 < <banda>_p98, en orden alfabético
    var lo = ee.Number(ee.Algorithms.If(v.get(0), v.get(0), e.vis.min));
    var hi = ee.Number(ee.Algorithms.If(v.get(1), v.get(1), e.vis.max));
    var span = hi.subtract(lo).max((e.vis.max - e.vis.min) * (opts.minSpan || 0.15));
    var mid = hi.add(lo).divide(2);
    return ee.List([mid.subtract(span.divide(2)), mid.add(span.divide(2))]);
  }

  // Une dos rangos (comparación de fechas con el mismo índice: misma escala a ambos lados).
  function unionRange(a, b) {
    return ee.List([ee.Number(a.get(0)).min(b.get(0)), ee.Number(a.get(1)).max(b.get(1))]);
  }

  function applyRange(image, range, id) {
    return {
      image: image.select(0).unitScale(ee.Number(range.get(0)), ee.Number(range.get(1))),
      vis: { min: 0, max: 1, palette: CATALOG[id].vis.palette }
    };
  }

  // Cinco etiquetas para la leyenda a partir de un rango ya evaluado [lo, hi].
  function rangeLabels(r) {
    var span = Math.abs(r[1] - r[0]);
    var d = span >= 20 ? 0 : span >= 2 ? 1 : span >= 0.2 ? 2 : 3;
    var out = [];
    for (var i = 0; i < 5; i++) out.push((r[0] + (r[1] - r[0]) * i / 4).toFixed(d));
    return out;
  }

  var API = {
    CATALOG: CATALOG,
    GROUPS: GROUPS,
    PALETTES: P,
    gradientCss: gradientCss,
    grouped: grouped,
    text: text,
    spectralIds: spectralIds,
    sl2p: sl2p,
    canStretch: canStretch,
    fieldRange: fieldRange,
    unionRange: unionRange,
    applyRange: applyRange,
    rangeLabels: rangeLabels
  };

  if (typeof window !== 'undefined') {
    window.INDEX_CATALOG = CATALOG;
    window.INDEX_API = API;
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = API;

})(typeof globalThis !== 'undefined' ? globalThis : this);
