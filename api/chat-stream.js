// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 Francisco Altimiras. See LICENSING.md.
const { cors } = require('./_cors');
/**
 * agragent — Streaming Chat Endpoint (Vercel Serverless)
 * POST /api/chat-stream
 *
 * Returns Server-Sent Events with the agentic tool loop (open-weight LLMs, see _llm.js).
 * Events: { type: "text"|"tool_start"|"tool_end"|"done"|"error", ... }
 *
 * Tools implemented (JS): geocode_place, get_climate_data, get_ndvi_data, search_openalex,
 *   search_agris, get_faostat_data, search_inia_biblioteca,
 *   analyze_soil_report, analyze_foliar_report,
 *   calculate_irrigation_plan, calculate_fertilization_plan
 */

const { completeLLM } = require('./_llm');
const { pulirRespuesta } = require('./_guards');
const { planTools, planDirective } = require('./_planner');

const { supabase } = require('./_db');
const { requireIdentity, canUseConversation, ownerColumns, checkChatQuota } = require('./_auth');

// ── SYSTEM PROMPT ──────────────────────────────────────────────────
const SYSTEM_PROMPT = `Eres agragent (tu nombre se escribe siempre en minúsculas: agragent), un agrónomo experto con más de 20 años de experiencia en agricultura latinoamericana e internacional. Ayudas a productores, ingenieros agrónomos y técnicos de campo con cualquier cultivo — cereales, hortalizas, frutales, leguminosas, café, caña, cultivos tropicales y cualquier otro que el usuario mencione. Tomas decisiones basadas en datos reales: clima, satélite, análisis de suelo/foliar y bibliografía científica.

## Cultivos que manejas:
Trigo, maíz, arroz, cebada, avena, soya, fréjol, arveja, quinua, tomate, pimiento, lechuga, cebolla, ajo, zapallo, papa, espárrago, fresa, uva/vid, manzano, peral, cerezo, duraznero, olivo, cítricos, palto/aguacate, mango, banano, café, cacao, caña de azúcar, girasol, raps/canola, aromáticas y cualquier otro cultivo.

## Tu expertise:

### Análisis de Suelos
- pH, CE, MO, N total, P (Bray/Olsen/Mehlich), K, Ca, Mg, Na, S y micronutrientes (B, Cu, Fe, Mn, Zn)
- Diagnóstico: salinidad, alcalinidad, deficiencias, desequilibrios catiónicos (Ca/Mg, Mg/K, Ca/K)
- Recomendaciones de enmiendas: cal, yeso, azufre, materia orgánica

### Análisis Foliares
- Macronutrientes (N, P, K, Ca, Mg, S) y micronutrientes (B, Cu, Fe, Mn, Zn, Mo)
- Diagnóstico de deficiencias/toxicidades y correcciones foliares urgentes vs. largo plazo

### Planificación de Riego
- Necesidades hídricas por cultivo y etapa fenológica (coeficientes Kc FAO-56)
- Sistemas: goteo, aspersión, surcos, inundación
- Ajuste por ET₀ real y precipitación efectiva

### Programas de Fertilización
- Requerimientos N-P-K por cultivo y objetivo de rendimiento
- Fertirrigación, base, cobertera y foliar
- Fuentes: urea, DAP, MAP, KCl, KNO3, quelados

## Cómo trabajas:

**REGLA PRINCIPAL: responde exactamente lo que se preguntó, nada más.** Antes de responder, identifica qué tipo de pregunta es:

- **Diagnóstico o estado** ("¿cómo está mi campo?", "salud del campo", "¿cómo viene el vigor?"): describe lo que muestran los datos — vigor satelital, clima, alertas, etapa — y qué significa. **No entregues planes de riego, fertilización ni aplicaciones.** Si ves un problema, nómbralo con el dato que lo respalda.
- **Pregunta puntual** ("¿cuánto llovió?", "¿qué es el NDRE?"): responde el dato en una o dos líneas.
- **Pedido de recomendación o plan** ("¿cuánto regar?", "arma el plan de fertilización", "¿qué aplico?"): recién ahí recomiendas.

Reglas:
1. **No te adelantes.** Nunca agregues un plan, programa, dosis o calendario que el usuario no pidió. Las herramientas \`calculate_irrigation_plan\` y \`calculate_fertilization_plan\` se usan **solo** cuando el usuario pide explícitamente un plan de riego o de fertilización.
2. **Antes de prescribir, verifica lo que falta.** Una dosis o lámina depende de datos que a menudo no tienes (análisis de suelo, sistema de riego, etapa confirmada en terreno, rendimiento objetivo). Primero busca esos datos en el mensaje y en el contexto: si el usuario pidió el plan y ahí están el cultivo y lo esencial (rendimiento objetivo para fertilizar; sistema de riego para regar), **llama la calculadora** y declara los supuestos que usaste. Pregunta solo lo que falte de verdad y cambie la recomendación, en una línea y en lenguaje natural ("¿qué tipo de suelo tiene y riega por goteo?", nunca nombres internos como franco_arenoso).
3. **Distingue medido de inferido, y no cambies los datos.** Repite los valores del contexto tal cual (suelo, sistema de riego, cultivo). **Distingue medido de inferido.** El NDVI o el balance hídrico son datos; "estrés hídrico" o "deficiencia de N" son hipótesis que se confirman en terreno. Dilo así: "el NDVI bajo en el sector norte es compatible con estrés hídrico; conviene revisar en terreno". Un solo índice satelital no basta para diagnosticar una causa.
4. **Nunca pidas al usuario un dato que puedes consultar** (ET₀, lluvia, temperatura, pronóstico, NDVI u otro índice satelital, de hoy, de un período o para comparar fechas): llama la herramienta (\`get_climate_data\`, \`get_ndvi_data\`). Si el contexto no trae el valor, consúltalo; nunca le pidas al usuario que te lo dé. Pregunta solo lo que ninguna herramienta trae (análisis de suelo, rendimiento objetivo, síntoma observado). **Datos faltantes o dudosos:** si un valor del contexto no está o parece raro, dilo en vez de rellenar con supuestos.
5. **Ubicación y cultivo:** si el mensaje nombra un cultivo, ese manda sobre el del contexto (el contexto describe el campo seleccionado, no limita la pregunta); no preguntes cuál de los dos. Si el usuario nombra un lugar (comuna, condado, valle, ciudad, región), ubícalo con \`geocode_place\` y sigue: **nunca pidas latitud y longitud**. Pregunta por el lugar o el cultivo solo si de verdad no se mencionan, en una sola línea.
6. **Suelo o foliar:** si el usuario escribe valores de un análisis (pH, CE, N, P, K, micronutrientes…), interprétalos con \`analyze_soil_report\` o \`analyze_foliar_report\`, no de memoria. Si solo menciona que tiene un análisis, sin valores, pídelo (botón 📎).
7. **Temporada:** fíjate en el hemisferio y la fecha de hoy. Si la herramienta dice que el cultivo está fuera de temporada (ya cosechado o sin plantar), dilo primero y no presentes una fase o riesgo como si estuviera ocurriendo.
8. **Riego fuera de temporada:** si el cultivo no está en período de riego (en Chile central, antes de octubre o tras la caída de hojas en frutales y vides), dilo primero y no armes un manejo de riego como si estuviera regando.
9. **Cierre:** termina cuando terminaste de responder. **No cierres con una pregunta ni con una oferta** ("¿Te armo el plan?", "¿Quieres que revise…?", "Si quieres, calculo…"): el comité de agrónomos que evaluó este asistente mostró que esa oferta es la que arrastra la conversación a una prescripción sin validar. La única pregunta permitida es la que pide un dato que falta para responder (qué cultivo, en qué etapa, qué sistema de riego), y en ese caso pregúntalo y nada más.
10. **Orientas; no dictaminas.** Puedes explicar cómo funciona algo, qué indicadores mirar, qué muestran los datos del campo y qué dice una publicación. No diagnosticas qué enfermedad, plaga o deficiencia tiene el cultivo: describes lo compatible y qué revisar en terreno. Para fitosanitarios **nunca des una dosis numérica**: remite a la etiqueta autorizada del producto y al asesor, aunque la dosis venga de una publicación (cítala como lo que dice el documento, no como lo que debe hacer). Cuando el usuario pida explícitamente un plan de riego o fertilización, entrégalo como **estimación a validar con su asesor**, con los supuestos a la vista.
11. **No ofrezcas lo que no existe.** No prometas activar alertas, enviar avisos, programar tareas ni conectar con servicios: solo puedes consultar datos y responder.

## Formato de respuestas:

Tu interlocutor es un **agrónomo o técnico de campo** — conoce la terminología, no necesita explicaciones básicas. Ve directo al dato.

**Máximo 3 párrafos cortos.** Si puedes decirlo en 2 líneas, úsalas.

- Primera línea: la respuesta o diagnóstico directo
- Usa datos del contexto sin introducirlos ("Tu NDVI es 0.61" no "Según los datos de tu campo, el NDVI registrado es...")
- **Negritas** solo para dosis, productos o valores críticos
- Listas solo si hay 3+ ítems accionables
- Tablas solo si el usuario pide un programa o cronograma explícito
- Sin encabezados markdown (##) salvo que la respuesta tenga 3+ secciones distintas
- NUNCA termines con una pregunta, una oferta ni fórmulas como "¿Quieres más información?" o "¿Algo más?" (regla 9)
- NUNCA empieces con "¡Excelente!", "¡Claro!", "Por supuesto" ni frases de relleno
- NUNCA uses etiquetas XML ni ángulos: no escribas <palabra>, </palabra> ni nada similar
- No expliques qué herramienta usaste ni menciones si una falló
- Si el usuario nombra un lugar, ubícalo con \`geocode_place\`; nunca le pidas coordenadas

## Criterios técnicos revisados por el comité de agrónomos:
- Estrés **hídrico** (no frío ni heladas) medido con termómetro infrarrojo: una hoja **2 a 3 °C más caliente** que el aire ya indica cierre estomático por falta de agua (no 5 °C). Úsalo solo si preguntan por indicadores de estrés hídrico.
- Humedad de suelo en vid y frutales: hoy se usan sensores **TDR/FDR** (capacitancia); el tensiómetro quedó como referencia secundaria.
- Responde por el cultivo que pregunta el usuario o el del contexto; no traigas otro cultivo (p. ej. palto) a una pregunta genérica.
- **Origen del clima:** los datos de clima vienen de reanálisis y modelos (ERA5 y Open-Meteo, ~9–25 km), no de una estación en el predio. Dilo así si preguntan, y no presentes una alerta que el contexto no trae.

## Estrategia de búsqueda bibliográfica:
- Preguntas técnicas en Chile → \`search_inia_biblioteca\`
- Cultivos o temas no-chilenos → \`search_openalex\`
- Para benchmarks globales o cultivos exóticos → \`search_openalex\`
- Cita siempre: título, año, autores y enlace.

## Contexto de la aplicación:

Los mensajes pueden incluir un bloque [App Context]...[/App Context] con datos en tiempo real que el usuario ya está viendo en la pantalla:
- **Campo**: nombre, área, coordenadas, polígono dibujado
- **Clima**: GDD, horas frío, heladas, olas de calor, ET₀, balance hídrico
- **Alertas activas**: heladas, sequía, calor extremo
- **Satélite NDVI/NDRE/MSAVI**: valores medios del polígono calculados desde Sentinel-2 (10m). Úsalos directamente para responder — no pidas al usuario que vaya al mapa a buscarlos.
- **Rendimiento**: estimación heurística (suma ponderada de indicadores de clima y satélite, con pesos
  asignados por criterio experto). No es un modelo entrenado y el rango mostrado no es un intervalo de
  confianza calibrado: nunca cites un R² ni un porcentaje de exactitud para esta estimación. Si preguntan
  por su fiabilidad, explica que la predictibilidad baja a medida que se achica la escala (país,
  región, predio) y que la variabilidad dentro del predio requiere
  observaciones de terreno, como el conteo de inflorescencias.

Usa estos datos para responder lo que se pregunta, sin pedirle al usuario lo que ya está en el contexto. Que tengas datos de riego o nutrición no significa que debas recomendar sobre eso: la regla de dosis del contexto aplica solo cuando el usuario pide una fertilización. Responde en el idioma del usuario.`;


// Idioma de la pregunta cuando la interfaz no lo manda (widgets u otras integraciones).
function guessLang(message) {
  const q = String(message || '').replace(/\[(App Context|APP CONTEXT)[\s\S]*$/i, '').toLowerCase();
  if (/\b(você|não|qual|está|meu|minha|são|irrigação|adubação)\b/.test(q)) return 'pt';
  if (/\b(the|what|how|my|is|are|should|which|when)\b/.test(q)) return 'en';
  return 'es';
}

// ── TOOLS DEFINITION ──────────────────────────────────────────────
const TOOLS = [
  {
    name: 'geocode_place',
    description: 'Convierte un lugar escrito (comuna, condado, valle, ciudad, región, país; ej. "Yolo County", "Colchagua", "Mendoza") en latitud y longitud. Úsala siempre que el usuario nombre un lugar y no haya coordenadas en el contexto, antes de llamar a herramientas que piden latitud/longitud. Nunca le pidas coordenadas al usuario.',
    input_schema: {
      type: 'object',
      properties: {
        place: { type: 'string', description: 'Lugar tal como lo escribió el usuario, con país o estado si se sabe (ej. "Yolo County, California")' }
      },
      required: ['place']
    }
  },
  {
    name: 'get_climate_data',
    description: 'Obtiene datos climáticos para una ubicación: temperatura, precipitación, humedad, radiación solar, ET₀, GDD, horas frío, heladas y olas de calor.',
    input_schema: {
      type: 'object',
      properties: {
        latitude:  { type: 'number', description: 'Latitud decimal' },
        longitude: { type: 'number', description: 'Longitud decimal' },
        days_forecast: { type: 'integer', description: 'Días de pronóstico', default: 7 }
      },
      required: ['latitude', 'longitude']
    }
  },
  {
    name: 'search_openalex',
    description: 'Busca publicaciones científicas en OpenAlex (250M+ trabajos académicos, acceso abierto). Cubre todas las áreas agrícolas a nivel global: cereales, hortalizas, frutales, riego, fertilización, plagas, suelos, etc. Usar para literatura internacional o cuando INIA no tenga el tema.',
    input_schema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Términos en inglés o español. Ej: "drip irrigation tomato yield", "nitrogen wheat Chile"' },
        max_results: { type: 'integer', description: 'Resultados (1-10)', default: 5 },
        year_from: { type: 'integer', description: 'Año mínimo', default: 2010 }
      },
      required: ['query']
    }
  },
  {
    name: 'search_inia_biblioteca',
    description: 'Busca documentos en la Biblioteca Digital INIA Chile (19.000+ publicaciones técnicas, acceso libre). Retorna título, autores, año, resumen y enlace.',
    input_schema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Términos de búsqueda en español. Ej: "riego vid Aconcagua", "fertilización trigo secano"' },
        max_results: { type: 'integer', description: 'Máximo resultados (1-10)', default: 5 }
      },
      required: ['query']
    }
  },
  {
    name: 'analyze_soil_report',
    description: 'Interpreta parámetros de análisis de suelo (pH, CE, MO, N, P, K, Ca, Mg) y genera recomendaciones de enmiendas y fertilizantes.',
    input_schema: {
      type: 'object',
      properties: {
        analysis_data: { type: 'object', description: 'Parámetros del análisis. Ej: {"pH":6.5,"CE":1.2,"MO":2.3,"P":18,"K":0.35}' },
        crop_type: { type: 'string', description: 'Cultivo (ej: tomate, maíz, vid, trigo)' }
      },
      required: ['analysis_data', 'crop_type']
    }
  },
  {
    name: 'analyze_foliar_report',
    description: 'Interpreta análisis foliar, identifica deficiencias y genera correcciones urgentes o de mediano plazo.',
    input_schema: {
      type: 'object',
      properties: {
        analysis_data: { type: 'object', description: 'Parámetros foliares. Ej: {"N":3.2,"P":0.28,"K":3.5,"Ca":1.8,"Mg":0.45,"Fe":85}' },
        crop_type:    { type: 'string' },
        growth_stage: { type: 'string', description: 'Estadío fenológico (vegetativo, floración, fructificación, maduración)' }
      },
      required: ['analysis_data', 'crop_type']
    }
  },
  {
    name: 'calculate_irrigation_plan',
    description: 'Calcula plan de riego: lámina neta/bruta, intervalo, volumen por hectárea. Usa coeficientes Kc FAO-56. Úsala SOLO si el usuario pide explícitamente un plan o cálculo de riego; nunca para responder preguntas de diagnóstico o estado del campo.',
    input_schema: {
      type: 'object',
      properties: {
        crop_type:         { type: 'string' },
        growth_stage:      { type: 'string', description: 'inicial, desarrollo, media_estacion, maduracion' },
        soil_type:         { type: 'string', description: 'arenoso, franco_arenoso, franco, franco_arcilloso, arcilloso' },
        area_ha:           { type: 'number' },
        et0:               { type: 'number', description: 'ET₀ en mm/día (opcional)' },
        irrigation_system: { type: 'string', description: 'goteo, aspersion, surcos, inundacion' }
      },
      required: ['crop_type', 'growth_stage', 'soil_type', 'area_ha']
    }
  },
  {
    name: 'get_ndvi_data',
    description: 'Consulta los índices de vegetación (NDVI, NDRE, EVI, MSAVI, TCARI, NDMI) del campo activo, derivados de Sentinel-2. Úsala cuando el usuario pregunte por el vigor o el estado del cultivo visto desde el satélite.',
    input_schema: {
      type: 'object',
      properties: {
        latitude:  { type: 'number', description: 'Latitud decimal' },
        longitude: { type: 'number', description: 'Longitud decimal' },
        radius_m:  { type: 'integer', description: 'Radio en metros alrededor del punto', default: 500 }
      },
      required: ['latitude', 'longitude']
    }
  },
  {
    name: 'search_agris',
    description: 'Busca publicaciones agrícolas en AGRIS (FAO), 16.5 millones de registros desde 1975 en 258 idiomas. Su ventaja frente a OpenAlex es la literatura gris: informes técnicos, boletines y publicaciones locales latinoamericanas no indexadas en revistas académicas. Úsala para literatura regional o cuando OpenAlex no devuelva resultados relevantes.',
    input_schema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Términos de búsqueda en español o inglés' },
        max_results: { type: 'integer', description: 'Resultados (1-10)', default: 5 },
        year_from: { type: 'integer', description: 'Año mínimo de publicación' }
      },
      required: ['query']
    }
  },
  {
    name: 'get_faostat_data',
    description: 'Obtiene estadísticas agrícolas oficiales de FAOSTAT (FAO): rendimiento, producción y superficie cosechada por cultivo y país, con series desde 1961. Úsala para benchmarks de rendimiento, comparaciones entre países o tendencias históricas.',
    input_schema: {
      type: 'object',
      properties: {
        crop:    { type: 'string', description: 'Cultivo en inglés. Ej: grapes, wheat, maize, tomatoes' },
        country: { type: 'string', description: 'País o región. Ej: chile, argentina, world', default: 'world' },
        element: { type: 'string', description: 'yield (rendimiento), production (toneladas) o area (superficie)', default: 'yield' },
        year_from: { type: 'integer', default: 2015 },
        year_to:   { type: 'integer', default: 2023 }
      },
      required: ['crop']
    }
  },
  {
    name: 'calculate_fertilization_plan',
    description: 'Calcula programa N-P-K basado en cultivo, objetivo de rendimiento y análisis de suelo disponible. Úsala SOLO si el usuario pide explícitamente un plan o programa de fertilización; nunca para responder preguntas de diagnóstico o estado del campo.',
    input_schema: {
      type: 'object',
      properties: {
        crop_type:     { type: 'string' },
        yield_target:  { type: 'number', description: 'Objetivo de rendimiento en t/ha' },
        soil_analysis: { type: 'object', description: 'Datos de suelo opcionales para ajuste' },
        area_ha:       { type: 'number' },
        irrigation_type: { type: 'string', description: 'goteo, aspersion, gravedad' },
        cycle_days:    { type: 'integer', description: 'Duración del ciclo en días' }
      },
      required: ['crop_type']
    }
  }
];

// ── GROQ TOOLS (input_schema → OpenAI function format) ───────────
const GROQ_TOOLS = TOOLS.map(t => ({
  type: 'function',
  function: { name: t.name, description: t.description, parameters: t.input_schema }
}));


// ── TOOL IMPLEMENTATIONS ──────────────────────────────────────────

async function getClimateData({ latitude, longitude, days_forecast = 7 }) {
  try {
    const vars = [
      'temperature_2m_max','temperature_2m_min','precipitation_sum',
      'relative_humidity_2m_mean','shortwave_radiation_sum',
      'et0_fao_evapotranspiration','wind_speed_10m_max'
    ].join(',');
    const today = new Date().toISOString().slice(0,10);
    const end   = new Date(Date.now() + days_forecast * 86400000).toISOString().slice(0,10);
    const url   = `https://api.open-meteo.com/v1/forecast?latitude=${latitude}&longitude=${longitude}` +
      `&daily=${vars}&start_date=${today}&end_date=${end}&timezone=auto`;
    const r = await fetch(url, { signal: AbortSignal.timeout(10000) });
    const d = await r.json();
    const daily = d.daily || {};
    const days  = (daily.time || []).length;
    const avgTemp = avg(daily.temperature_2m_max, daily.temperature_2m_min);
    const totalPrec = sum(daily.precipitation_sum);
    const avgEt0    = avg1(daily.et0_fao_evapotranspiration);
    const gdd = (daily.temperature_2m_max || []).reduce((acc, tmax, i) => {
      const tmin = (daily.temperature_2m_min || [])[i] || 0;
      return acc + Math.max(0, (tmax + tmin) / 2 - 10);
    }, 0);
    return {
      location: { latitude, longitude },
      period: `${today} → ${end}`,
      summary: {
        avg_temp_c: +avgTemp.toFixed(1),
        total_precip_mm: +totalPrec.toFixed(1),
        avg_et0_daily_mm: +avgEt0.toFixed(2),
        gdd_base10: +gdd.toFixed(1),
      },
      daily: {
        dates: daily.time,
        tmax:  daily.temperature_2m_max,
        tmin:  daily.temperature_2m_min,
        precip: daily.precipitation_sum,
        et0:   daily.et0_fao_evapotranspiration,
      }
    };
  } catch(e) { return { error: `Error obteniendo clima: ${e.message}` }; }
}

function avg(a, b) {
  if (!a) return 0;
  return a.reduce((s,v,i) => s + (v + (b||[])[i] || 0) / 2, 0) / a.length;
}
function avg1(a) { if (!a || !a.length) return 0; return a.reduce((s,v) => s + (v||0), 0) / a.length; }
function sum(a)  { if (!a || !a.length) return 0; return a.reduce((s,v) => s + (v||0), 0); }

// GET JSON a la Biblioteca INIA. Su certificado no valida en Node: la excepción vale solo para este host.
function iniaGetJson(url, timeoutMs) {
  return new Promise((resolve, reject) => {
    const req = require('https').get(url, {
      rejectUnauthorized: false,
      headers: { 'User-Agent': 'agragent/2.0', 'Accept': 'application/json' },
      timeout: timeoutMs,
    }, r => {
      let body = '';
      r.setEncoding('utf8');
      r.on('data', c => { body += c; });
      r.on('end', () => { try { resolve(JSON.parse(body)); } catch (e) { reject(e); } });
    });
    req.on('timeout', () => req.destroy(new Error('timeout')));
    req.on('error', reject);
  });
}

async function searchIniaLibraria({ query, max_results = 5 }) {
  try {
    const url = `https://biblioteca.inia.cl/server/api/discover/search/objects` +
      `?query=${encodeURIComponent(query)}&dsoType=item&size=${Math.min(max_results,10)}&sort=score,desc`;
    const data = await iniaGetJson(url, 12000);
    const total = data?._embedded?.searchResult?.page?.totalElements ?? 0;
    const objects = data?._embedded?.searchResult?._embedded?.objects ?? [];
    const results = objects.map(obj => {
      const meta = obj?._embedded?.indexableObject?.metadata ?? {};
      const mv = f => (meta[f]?.[0]?.value ?? '');
      const uuid = obj?._embedded?.indexableObject?.uuid ?? '';
      return {
        title:    mv('dc.title'),
        year:     mv('dc.date.issued').slice(0,4),
        authors:  (meta['dc.contributor.author'] || []).slice(0,3).map(v=>v.value),
        abstract: mv('dc.description.abstract').slice(0,400),
        link:     uuid ? `https://biblioteca.inia.cl/items/${uuid}` : '',
      };
    }).filter(d => d.title);
    return { query, total_available: total, returned: results.length, source: 'Biblioteca Digital INIA Chile', results };
  } catch(e) {
    return { error: `No se pudo conectar con INIA: ${e.message}`, query, results: [] };
  }
}

function analyzeSoilReport({ analysis_data: data = {}, crop_type = '' }) {
  const alerts = [], recs = [], interp = {};
  const n = (v) => v == null ? null : +v;
  const pH = n(data.pH ?? data.ph);
  if (pH != null) {
    let st = pH < 5 ? 'Muy ácido' : pH < 5.5 ? 'Ácido' : pH <= 6.5 ? 'Ideal (ligeramente ácido)' : pH <= 7 ? 'Neutro' : pH <= 7.5 ? 'Ligeramente alcalino' : 'Alcalino';
    interp.pH = { value: pH, status: st };
    if (pH < 5.5) { alerts.push(`pH ${pH} muy bajo`); recs.push(`Aplicar 1-2 t/ha cal dolomita para alcanzar pH 6.0-6.5`); }
    if (pH > 7.5)  { alerts.push(`pH ${pH} alcalino`); recs.push(`Aplicar azufre elemental 300-500 kg/ha + micronutrientes quelados`); }
  }
  const P = n(data.P ?? data.fosforo);
  if (P != null) {
    interp.P = { value: P, unit: 'ppm', status: P < 10 ? 'Deficiente' : P < 20 ? 'Bajo' : P < 40 ? 'Adecuado' : 'Alto' };
    if (P < 10) recs.push(`P muy bajo (${P} ppm): aplicar 150-200 kg/ha DAP o superfosfato triple`);
  }
  const K = n(data.K ?? data.potasio);
  if (K != null) {
    const km = K > 10 ? K / 391 : K;
    interp.K = { value: K, status: km < 0.15 ? 'Deficiente' : km < 0.3 ? 'Bajo' : 'Adecuado' };
    if (km < 0.2) recs.push(`K bajo: aplicar 80-120 kg/ha KCl (0-0-60) o K₂SO₄`);
  }
  const MO = n(data.MO ?? data.mo ?? data.materia_organica);
  if (MO != null) {
    interp.MO = { value: MO, unit: '%', status: MO < 1 ? 'Muy bajo' : MO < 2 ? 'Bajo' : MO < 3.5 ? 'Adecuado' : 'Alto' };
    if (MO < 2) recs.push(`MO baja (${MO}%): incorporar compost 5-10 t/ha anualmente`);
  }
  return { crop_type, interpretation: interp, alerts, recommendations: recs, summary: `${alerts.length} alertas, ${recs.length} recomendaciones para ${crop_type}.` };
}

function analyzeFoliarReport({ analysis_data: data = {}, crop_type = '', growth_stage = '' }) {
  const SUFF = {
    N: {min:2.5,max:4.5,unit:'%'}, P: {min:0.20,max:0.50,unit:'%'}, K: {min:2.0,max:4.5,unit:'%'},
    Ca:{min:1.0,max:3.5,unit:'%'}, Mg:{min:0.25,max:0.80,unit:'%'}, Fe:{min:50,max:300,unit:'ppm'},
    Mn:{min:20,max:200,unit:'ppm'}, Zn:{min:20,max:100,unit:'ppm'}, B:{min:25,max:75,unit:'ppm'},
  };
  const defs = [], urgent = [], medium = [], interp = {};
  for (const [k, ref] of Object.entries(SUFF)) {
    const v = +data[k];
    if (isNaN(v)) continue;
    const {min,max,unit} = ref;
    const status = v < min * 0.85 ? 'DEFICIENCIA CRÍTICA' : v < min ? 'Bajo' : v > max * 1.5 ? 'Exceso' : v > max ? 'Alto' : 'Normal';
    interp[k] = {value:v,unit,min,max,status};
    if (v < min*0.85) { defs.push(k); urgent.push(`**${k} crítico (${v}${unit})** — aplicar foliar en 48-72h`); }
    else if (v < min) { defs.push(k); medium.push(`**${k} bajo (${v}${unit})** — corregir esta semana`); }
  }
  return { crop_type, growth_stage, interpretation: interp, deficiencies: defs, corrections_urgent: urgent, corrections_medium_term: medium };
}

function calculateIrrigationPlan({ crop_type='default', growth_stage='mid_season', soil_type='franco', area_ha=1, et0=null, irrigation_system='goteo' }) {
  const KC = { tomate:{initial:0.6,development:0.75,mid_season:1.15,late_season:0.8}, vid:{initial:0.3,development:0.7,mid_season:0.85,late_season:0.45}, maiz:{initial:0.3,development:0.7,mid_season:1.2,late_season:0.6}, default:{initial:0.5,development:0.75,mid_season:1.1,late_season:0.75} };
  const AWC = { arenoso:80, franco_arenoso:120, franco:160, franco_arcilloso:180, arcilloso:200, default:150 };
  const EFF = { goteo:0.90, aspersion:0.78, surcos:0.55, inundacion:0.45, default:0.80 };
  const RDEPTH = { tomate:{initial:0.2,development:0.45,mid_season:0.7,late_season:0.7}, vid:{initial:0.3,development:0.5,mid_season:0.8,late_season:0.8}, default:{initial:0.2,development:0.4,mid_season:0.6,late_season:0.6} };
  const stage = growth_stage.replace(/[áé]/g, c => c==='á'?'a':'e').replace('inicial','initial').replace('desarrollo','development').replace('media_estacion','mid_season').replace('maduracion','late_season');
  const kc = (KC[crop_type] || KC.default)[stage] || 1.0;
  const et0v = et0 ?? 5.0;
  const etc = +(et0v * kc).toFixed(2);
  const awc = (AWC[soil_type] || AWC.default) * ((RDEPTH[crop_type] || RDEPTH.default)[stage] || 0.6);
  const net = +(awc * 0.5).toFixed(1);
  const interval = Math.max(1, Math.round(net / etc));
  const eff = EFF[irrigation_system] || EFF.default;
  const gross = +(net / eff).toFixed(1);
  const vol = +(gross * 10 * area_ha).toFixed(1);
  return { crop_type, kc, et0: et0v, etc_daily_mm: etc, net_irrigation_mm: net, gross_irrigation_mm: gross, interval_days: interval, volume_m3: vol, efficiency_pct: Math.round(eff*100), recommendations: [`Regar cada ${interval} día(s). Volumen: ${vol} m³ para ${area_ha} ha.`] };
}

function calculateFertilizationPlan({ crop_type='default', yield_target=30, soil_analysis={}, area_ha=1, irrigation_type='goteo', cycle_days=120 }) {
  const NPK = { tomate:{N:3,P2O5:1,K2O:5,Ca:1.5,Mg:0.5}, vid:{N:2,P2O5:0.6,K2O:3,Ca:1.2,Mg:0.4}, maiz:{N:18,P2O5:8,K2O:5,Ca:2,Mg:2}, trigo:{N:22,P2O5:8,K2O:6,Ca:1.5,Mg:1.5}, default:{N:3.5,P2O5:1.2,K2O:4.5,Ca:1,Mg:0.4} };
  const req = NPK[crop_type] || NPK.default;
  let N = +(req.N * yield_target).toFixed(1);
  let P = +(req.P2O5 * yield_target).toFixed(1);
  let K = +(req.K2O * yield_target).toFixed(1);
  if (+soil_analysis.P > 40) P = +(P * 0.5).toFixed(1);
  const fert = irrigation_type === 'goteo' ? ['Fertirriego semanal recomendado'] : [];
  return { crop_type, yield_target_t_ha: yield_target, area_ha, total_kg_ha: {N, P2O5: P, K2O: K}, total_kg_field: {N: +(N*area_ha).toFixed(1), P2O5: +(P*area_ha).toFixed(1), K2O: +(K*area_ha).toFixed(1)}, application_program: { preplant: `DAP ${+(P/0.46).toFixed(0)} kg/ha + KCl ${+(K*0.25/0.6).toFixed(0)} kg/ha + Urea ${+(N*0.1/0.46).toFixed(0)} kg/ha`, fertirriego: fert }, notes: ['Ajustar con análisis foliar periódico.'] };
}

async function searchOpenAlex({ query, max_results = 5, year_from = 2010 }) {
  try {
    const filters = [`open_access.is_oa:true`, `publication_year:${year_from}-`];
    const params = new URLSearchParams({
      search: query,
      'per-page': Math.min(+max_results || 5, 10),
      select: 'title,publication_year,doi,authorships,abstract_inverted_index,open_access',
      sort: 'relevance_score:desc',
      filter: filters.join(','),
      mailto: 'agragent@agragent.com',
    });
    const res = await fetch(`https://api.openalex.org/works?${params}`, {
      headers: { 'User-Agent': 'agragent/1.0 (mailto:agragent@agragent.com)' },
      signal: AbortSignal.timeout(12000),
    });
    const data = await res.json();
    const total = data?.meta?.count ?? 0;
    const results = (data.results || []).map(w => {
      // Reconstruct abstract
      let abstract = '';
      const inv = w.abstract_inverted_index || {};
      if (Object.keys(inv).length) {
        const pos = {};
        for (const [word, positions] of Object.entries(inv)) positions.forEach(p => pos[p] = word);
        abstract = Object.keys(pos).sort((a,b)=>a-b).map(p=>pos[p]).join(' ').slice(0,500);
      }
      const authors = (w.authorships||[]).slice(0,3).map(a=>a?.author?.display_name||'').filter(Boolean);
      const doi = w.doi || '';
      const oa_url = w?.open_access?.oa_url || '';
      return { title: w.title||'', year: w.publication_year||'', authors, abstract, doi, url: oa_url||doi };
    });
    return { query, total_available: total, returned: results.length, source: 'OpenAlex (openalex.org) — 250M+ academic works', results };
  } catch(e) { return { error: `OpenAlex error: ${e.message}`, query, results: [] }; }
}

// ── AGRIS (FAO) ────────────────────────────────────────────────────
// Agricultural bibliography, including Latin American grey literature that
// OpenAlex does not index. No authentication required.
async function searchAgris({ query, max_results = 5, year_from }) {
  const limit = Math.max(1, Math.min(+max_results || 5, 10));
  try {
    const params = new URLSearchParams({
      query,
      startIndexSearch: '1',
      outputFormat: 'json',
      sortField: 'score',
      sortOrder: 'desc',
    });
    const r = await fetch(`https://agris.fao.org/agris-search/search.do?${params}`, {
      headers: { 'User-Agent': 'agragent/1.0 (mailto:agragent@agragent.com)' },
      signal: AbortSignal.timeout(15000),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();

    // The response shape has varied across AGRIS versions.
    const raw = data.results || data.hits || data?.response?.docs || [];
    const total = data.totalCount ?? data.total ?? data?.response?.numFound ?? raw.length;

    const results = [];
    for (const item of raw) {
      const yearRaw = item.year || (item.publicationDate || '').slice(0, 4) || (item['dc:date'] || '').slice(0, 4);
      const year = parseInt(yearRaw, 10) || 0;
      if (year_from && year && year < year_from) continue;

      let authors = item.authors || item.creatorPersonal || item['dc:creator'] || [];
      if (typeof authors === 'string') authors = [authors];

      results.push({
        title: item.title || item['dc:title'] || '',
        authors: authors.slice(0, 3),
        year: year || null,
        abstract: (item.abstract || item['dcterms:abstract'] || '').slice(0, 500),
        url: item.url || item.link || item['dc:identifier'] || '',
        source: item.source || item.provider || 'AGRIS (FAO)',
      });
      if (results.length >= limit) break;
    }
    return { query, total_found: total, returned: results.length, results, database: 'AGRIS (FAO)' };
  } catch (e) {
    return {
      error: `Error al consultar AGRIS: ${e.message}`,
      query,
      results: [],
      note: 'AGRIS puede estar temporalmente no disponible. Usa search_openalex como alternativa.',
    };
  }
}

// ── FAOSTAT ────────────────────────────────────────────────────────
// Official FAO agricultural statistics. No authentication required.
const FAOSTAT_BASE = 'https://fenixservices.fao.org/faostat/api/v1';
const FAOSTAT_AREAS = {
  chile: '228', argentina: '9', peru: '180', brasil: '21', brazil: '21',
  mexico: '138', colombia: '44', china: '41', usa: '231',
  'united states': '231', india: '100', world: '5000',
  'south america': '912', 'latin america': '912',
};
const FAOSTAT_ELEMENTS = {
  produccion: '5510', production: '5510',
  rendimiento: '5419', yield: '5419',
  superficie: '5312', area: '5312', 'area harvested': '5312',
};

async function faostatGet(url) {
  const r = await fetch(url, {
    headers: { 'User-Agent': 'agragent/1.0 (mailto:agragent@agragent.com)' },
    signal: AbortSignal.timeout(20000),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function faostatItemCode(cropName) {
  try {
    const data = await faostatGet(`${FAOSTAT_BASE}/en/item/QCL?output_type=json`);
    const items = data.data || [];
    const target = String(cropName || '').toLowerCase();
    const exact = items.find(i => (i.Item || '').toLowerCase() === target);
    if (exact) return exact['Item Code'];
    const partial = items.find(i => (i.Item || '').toLowerCase().includes(target));
    return partial ? partial['Item Code'] : null;
  } catch (e) {
    return null;
  }
}

async function getFaostatData({ crop, country = 'world', element = 'yield', year_from = 2015, year_to = 2023 }) {
  const areaCode = FAOSTAT_AREAS[String(country).toLowerCase().trim()] || '5000';
  const elementCode = FAOSTAT_ELEMENTS[String(element).toLowerCase().trim()] || '5419';

  const itemCode = await faostatItemCode(crop);
  if (!itemCode) {
    return {
      error: `Cultivo '${crop}' no encontrado en FAOSTAT. Prueba con el nombre en inglés (ej: grapes, wheat, maize).`,
      crop, results: [],
    };
  }

  try {
    const params = new URLSearchParams({
      area: areaCode, element: elementCode, item: itemCode,
      year: `${year_from},${year_to}`,
      show_codes: 'True', show_unit: 'True', show_flags: 'False',
      null_values: 'False', output_type: 'json',
    });
    const data = await faostatGet(`${FAOSTAT_BASE}/en/data/QCL?${params}`);
    const rows = data.data || [];
    if (!rows.length) {
      return {
        query: { crop, country, element },
        results: [],
        note: 'Sin datos disponibles para esta combinación cultivo/país/período.',
      };
    }
    const unit = rows[0].Unit || '';
    const series = rows
      .filter(r => r.Value !== null && r.Value !== undefined)
      .map(r => ({ year: parseInt(r.Year, 10) || 0, value: parseFloat(r.Value) }))
      .sort((a, b) => a.year - b.year);
    const mean = series.length
      ? +(series.reduce((s, x) => s + x.value, 0) / series.length).toFixed(1)
      : null;

    return {
      query: { crop, country, element, year_from, year_to },
      unit,
      mean,
      results: series,
      source: 'FAOSTAT (FAO), dominio QCL',
    };
  } catch (e) {
    return { error: `Error al consultar FAOSTAT: ${e.message}`, crop, country, results: [] };
  }
}

// ── NDVI / vegetation indices ──────────────────────────────────────
// This deployment has no Sentinel Hub credentials: the indices are computed
// client-side through Earth Engine and arrive with every message inside the
// [App Context] block. Rather than inventing values, point the model at them.
async function getNdviData({ latitude, longitude, radius_m = 500 }) {
  return {
    status: 'use_app_context',
    location: { latitude, longitude, radius_m },
    note: 'Los índices de vegetación (NDVI, NDRE, EVI, MSAVI, TCARI, NDMI) del campo activo ya están '
        + 'en el bloque [App Context] de este mensaje, calculados con Sentinel-2 sobre el polígono del '
        + 'usuario. Úsalos directamente y menciona que puede verlos en el mapa de la sección Field Map. '
        + 'No inventes valores: si el contexto no los trae, pide al usuario que dibuje o cargue su campo.',
  };
}

async function geocodePlace({ place }) {
  try {
    const url = 'https://nominatim.openstreetmap.org/search?format=jsonv2&limit=3&accept-language=es&q='
      + encodeURIComponent(String(place || '').slice(0, 200));
    const r = await fetch(url, {
      headers: { 'User-Agent': process.env.NOMINATIM_USER_AGENT || 'agragent/2.0 (self-hosted)' },
      signal: AbortSignal.timeout(8000),
    });
    const list = await r.json();
    if (!Array.isArray(list) || !list.length) return { place, error: 'Lugar no encontrado: pide al usuario una referencia más precisa (comuna, ciudad cercana o región).' };
    const top = list[0];
    const lat = +(+top.lat).toFixed(4);
    return {
      place, latitude: lat, longitude: +(+top.lon).toFixed(4), name: top.display_name,
      hemisphere: lat >= 0 ? 'norte' : 'sur',
      note: 'Coordenadas del centro del lugar, no de un campo: los resultados son representativos de la zona, no de un predio.',
    };
  } catch (e) {
    return { place, error: 'No se pudo ubicar el lugar: ' + e.message };
  }
}

async function executeTool(name, input) {
  switch(name) {
    case 'geocode_place':              return geocodePlace(input);
    case 'get_climate_data':           return getClimateData(input);
    case 'search_openalex':            return searchOpenAlex(input);
    case 'search_inia_biblioteca':     return searchIniaLibraria(input);
    case 'analyze_soil_report':        return analyzeSoilReport(input);
    case 'analyze_foliar_report':      return analyzeFoliarReport(input);
    case 'calculate_irrigation_plan':  return calculateIrrigationPlan(input);
    case 'calculate_fertilization_plan': return calculateFertilizationPlan(input);
    case 'get_ndvi_data':              return getNdviData(input);
    case 'search_agris':               return searchAgris(input);
    case 'get_faostat_data':           return getFaostatData(input);
    default: return { error: `Herramienta desconocida: ${name}` };
  }
}

// ── SSE HELPERS ────────────────────────────────────────────────────
function sse(res, obj) {
  res.write(`data: ${JSON.stringify(obj)}\n\n`);
}

// ── MAIN HANDLER ───────────────────────────────────────────────────
module.exports = async function handler(req, res) {
  if (!cors(req, res, 'POST,OPTIONS')) return;
  if (req.method === 'OPTIONS') return res.status(204).end();

  // Identidad antes de abrir el stream, para poder responder 401/404/429 con JSON
  const ident = await requireIdentity(req, res, ['user', 'service', 'anon']);
  if (!ident) return;
  const { conversation_id: reqConvId } = req.body || {};
  if (reqConvId && !(await canUseConversation(ident, reqConvId))) {
    return res.status(404).json({ error: 'Conversation not found' });
  }
  const quota = await checkChatQuota(ident);
  if (!quota.ok) {
    return res.status(429).json({ error: 'Alcanzaste el límite diario de consultas al asistente. Vuelve a intentarlo mañana.' });
  }
  if (req.method !== 'POST')    return res.status(405).end();

  res.setHeader('Content-Type',  'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('X-Accel-Buffering', 'no');
  res.flushHeaders();

  const { conversation_id, message, user_id = 'anonymous', language } = req.body || {};
  if (!message) { sse(res, {type:'error',content:'Missing message'}); return res.end(); }

  // ── Build language directive (overrides any conflicting tone in history) ─
  const LANG_NAMES = { en: 'English', es: 'Spanish (Español)', pt: 'Portuguese (Português)' };
  const langCode = (language && LANG_NAMES[language]) ? language : null;
  const langDirective = langCode
    ? `\n\n## CRITICAL LANGUAGE RULE\nThe user interface is set to **${LANG_NAMES[langCode]}**. You MUST reply ENTIRELY in ${LANG_NAMES[langCode]} — every sentence, every question, every word. Do NOT mix languages. Do NOT switch to Spanish if the user is using English or Portuguese. This rule overrides any default behavior.`
    : `\n\n## LANGUAGE RULE\nDetect the language of the user's most recent message and reply in that exact language. If unclear, default to Spanish. Never mix languages within a single response.`;
  const effectiveSystem = SYSTEM_PROMPT + langDirective;
  const activeTools = GROQ_TOOLS;

  try {
    // ── Manage conversation ────────────────────────────────────────
    let convId = conversation_id;
    if (!convId) {
      const { data: c, error: e } = await supabase.from('conversations')
        .insert({ ...ownerColumns(ident, user_id), title: message.replace(/\[APP CONTEXT\][\s\S]*?\[END CONTEXT\]/i,'').trim().slice(0,60) })
        .select().single();
      if (e) throw e;
      convId = c.id;
    }

    await supabase.from('messages').insert({ conversation_id: convId, role: 'user', content: message });

    const { data: history } = await supabase.from('messages')
      .select('role,content').eq('conversation_id', convId)
      .order('created_at', { ascending: true }).limit(20);

    let messages = [
      { role: 'system', content: effectiveSystem },
      ...(history || []).map(m => ({
        role: m.role === 'assistant' ? 'assistant' : 'user',
        content: m.content || ''
      }))
    ];

    // ── Plan-then-act (ver _planner.js): qué tools hacen falta, decidido antes del loop ──
    // Con plan no vacío, la primera ronda debe llamar al menos una tool (tool_choice 'required'): en la
    // evaluación el agente a veces tenía el plan correcto y aun así pedía el dato o respondía de memoria.
    let planned = [];
    {
      const prev = [...(history || [])].reverse().find(m => m.role === 'assistant');
      planned = await planTools(b => completeLLM(b).then(r => r.message), message, activeTools, prev && prev.content);
      messages[0].content += planDirective(planned);
    }

    // ── Agentic loop (max 6 iterations) — non-streaming + simulated SSE ──
    // Se llama al LLM sin streaming (Cerebras → Groq fallback en _llm.js) y el
    // texto final se re-emite por SSE palabra a palabra, patrón de INIA. Esto
    // hace el fallback robusto (cubre fallos de lectura de body en Vercel) y
    // evita mostrar los tokens de "reasoning" de gpt-oss.
    const toolsUsed = [];
    let iterations  = 0;
    let finalText   = '';

    while (iterations++ < 6) {
      const { message: assistantMsg } = await completeLLM({
        messages,
        tools: activeTools,
        tool_choice: iterations === 1 && planned.length ? 'required' : 'auto',
        max_tokens: 1024,
      });

      const functionCalls = assistantMsg.tool_calls || [];
      const textContent = (assistantMsg.content || '').replace(/<\/?[a-zA-Z][^>]*>/g, '');

      if (functionCalls.length === 0) {
        finalText = textContent;
        break;
      }

      // Add assistant turn with tool_calls in OpenAI format
      messages.push({
        role: 'assistant',
        content: assistantMsg.content || null,
        tool_calls: functionCalls.map(tc => ({
          id: tc.id,
          type: 'function',
          function: { name: tc.function.name, arguments: tc.function.arguments }
        }))
      });

      // Execute tools and add results
      for (const tc of functionCalls) {
        const name = tc.function.name;
        toolsUsed.push(name);
        sse(res, { type: 'tool_start', tool: name });

        let result;
        try { result = await executeTool(name, JSON.parse(tc.function.arguments || '{}')); }
        catch(e) { result = { error: e.message }; }

        sse(res, { type: 'tool_end', tool: name });
        messages.push({ role: 'tool', tool_call_id: tc.id, content: JSON.stringify(result) });
      }
    }

    if (!finalText) finalText = 'No pude completar la respuesta. Intenta nuevamente.';
    // Candados del comité experto (ver _guards.js): sin pregunta de cierre y con aviso de validar con el asesor.
    else finalText = pulirRespuesta(finalText, message, langCode || guessLang(message));

    // Stream the final text word-by-word as SSE (simulated streaming, INIA style)
    const words = finalText.split(/(\s+)/);
    for (let i = 0; i < words.length; i += 4) {
      sse(res, { type: 'text', content: words.slice(i, i + 4).join('') });
    }

    // ── Persist & finish ───────────────────────────────────────────
    await supabase.from('messages').insert({ conversation_id: convId, role: 'assistant', content: finalText });
    await supabase.from('conversations').update({ updated_at: new Date().toISOString() }).eq('id', convId);

    sse(res, { type: 'done', conversation_id: convId, tools_used: toolsUsed });
    res.end();

  } catch (err) {
    console.error('chat-stream error:', err.message);
    sse(res, { type: 'error', content: 'Error interno del asistente' });
    res.end();
  }
};

module.exports.config = { maxDuration: 60 };

// Para eval/: los mismos schemas, prompt e implementaciones que usa el endpoint.
module.exports.internals = { SYSTEM_PROMPT, TOOLS, GROQ_TOOLS, executeTool, calculateIrrigationPlan, calculateFertilizationPlan };
