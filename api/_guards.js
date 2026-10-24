// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 Francisco Altimiras. See LICENSING.md.
// Candados de salida del asistente, portados de Avisa (INIA, `api/_agent.js`) tras la evaluación por
// comité experto (consenso de tres agrónomos, 100 casos, 2026). El comité puntuó bien las respuestas que
// explican y castigó las que prescriben, y casi siempre por la misma cadena: el bot cerraba ofreciendo
// aterrizar la respuesta ("¿Te armo el plan de riego?"), el usuario aceptaba y en el turno siguiente
// recibía dosis o láminas sin que nadie validara el predio.
//
//   quitarPreguntaDeCierre  borra la pregunta u oferta final de una respuesta ya completa. Respeta la
//                           que pide el dato que falta ("¿qué cultivo?", "¿en qué etapa?").
//   avisarConsultarAsesor   cierra con "confírmalo con tu asesor" cuando la respuesta prescribe (dosis,
//                           lámina, "te recomiendo") o el tema es sensible (nutrición, fitosanitarios,
//                           síntomas, riego).
//
// A diferencia de Avisa (solo español), agragent responde en ES/EN/PT: cada patrón cubre los tres.

const PIDE_DATO_RE = new RegExp([
  // es
  'cu[aá]l(es)? de (tus|sus|esos|estos|ellos)', 'te refieres a', 'quisiste decir',
  'qu[eé] (cultivo|variedad|s[ií]ntoma|etapa|producto|plaga|superficie|sistema de riego|tipo de suelo)',
  'en qu[eé] (etapa|zona|comuna|regi[oó]n|lugar)', 'd[oó]nde (est[aá]|queda)', 'me (dices|cuentas|confirmas|pasas|indicas)',
  'cu[aá]nt[oa]s? (a[nñ]os|ha\\b|hect[aá]reas|plantas)',
  // en
  'which (crop|variety|stage|field|one|of your)', 'what (crop|variety|stage|symptom|product|irrigation system|soil)',
  'where (is|are) (the|your)', 'do you mean', 'could you (tell|share|confirm)', 'how (many|old)',
  // pt
  'qual (cultura|variedade|etapa|est[aá]gio|sintoma|produto|sistema de irriga[cç][aã]o)', 'em que (etapa|regi[aã]o|munic[ií]pio)',
  'voc[eê] (quer dizer|pode (me )?(dizer|confirmar|informar))', 'quant[oa]s (anos|hectares|plantas)',
].join('|'), 'i');

// Prescripción en la RESPUESTA: una dosis, una lámina, un "aplica tantos", "te recomiendo".
const PRESCRIPCION_RE = new RegExp([
  '\\d+(?:[.,]\\d+)?\\s*(kg|kilos?|g|gr|gramos?|grams?|l|lt|litros?|liters?|litres?|cc|ml|mm|m3|m³|unidades?|units?|lb|lbs)\\s*(\\/|\\s+(por|per|a)\\s+)\\s*(ha|hect[aá]rea|hectare|acre|planta|plant|[aá]rbol|[aá]rvore|tree|d[ií]a|day|dia|semana|week)',
  '\\bdosis\\b', '\\bdose\\b', '\\bdosage\\b', '\\bl[aá]mina\\b', '\\bl[aâ]mina de (riego|irriga)',
  '\\bte recomiendo\\b', '\\brecomiendo\\b', '\\bI recommend\\b', '\\byou should (apply|irrigate|fertili[sz]e|spray)', '\\brecomendo\\b',
  '\\bdeber[ií]as (aplicar|regar|fertilizar|podar)', '\\bvoc[eê] deve (aplicar|irrigar|adubar)', '\\baplica(r|le)? \\d', '\\bapply \\d',
].join('|'), 'i');

// Tema sensible en la PREGUNTA: aunque la respuesta esquive el número, el usuario se va con la idea de que
// ya tiene su indicación.
const TEMA_SENSIBLE_RE = new RegExp([
  'dosis', 'fertiliz', 'urea', 'nitr[oó]geno', 'f[oó]sforo', 'potasio', 'abon', 'plaguicida', 'fungicida', 'insecticida',
  'herbicida', 'pesticida', 'agroqu[ií]mico', 'qu[eé] (le )?(pasa|tiene|podr[ií]a ser)', 'manchas?', 's[ií]ntoma', 'enfermedad',
  'plaga', 'l[aá]mina', 'rieg', 'regar',
  'dose', 'dosage', 'fertili[sz]', 'nitrogen', 'phosph', 'potassium', 'pesticide', 'fungicide', 'insecticide', 'herbicide',
  'spray', 'disease', 'symptom', 'spots?', 'pest', 'irrigat', 'what.?s wrong',
  'aduba', 'nitrog[eê]nio', 'f[oó]sforo', 'pot[aá]ssio', 'agrot[oó]xico', 'defensivo', 'doen[cç]a', 'praga', 'irriga', 'regar',
].map(w => '\\b' + w).join('|'), 'i');

// Pedir publicaciones no es pedir una recomendación: la respuesta son referencias.
const PIDE_REFERENCIAS_RE = /\b(publicaci|bolet[ií]n|documento|referencia|art[ií]culo|estudio|manual|paper|publication|reference|article|study|literature|refer[eê]ncia|artigo|estudo)/i;

// Ya deriva por su cuenta: no repetir el aviso.
const YA_DERIVA_RE = /\b(asesor|consultor|agr[oó]nomo|etiqueta (del producto|autorizada)|advisor|adviser|consultant|agronomist|product label|consultor|agr[oô]nomo|r[oó]tulo|bula)/i;

const AVISO_ASESOR = {
  es: 'Esto es orientación general: confírmalo con tu asesor o consultor, que conoce tu campo, antes de aplicarlo.',
  en: 'This is general guidance: confirm it with your advisor or consultant, who knows your field, before applying it.',
  pt: 'Isto é uma orientação geral: confirme com seu consultor ou agrônomo, que conhece sua área, antes de aplicar.',
};

// Lo que el usuario preguntó, sin el bloque de contexto que la app agrega después de la pregunta.
function preguntaSinContexto(message) {
  return String(message || '').replace(/\[(App Context|APP CONTEXT)[\s\S]*$/i, '').trim();
}

function quitarPreguntaDeCierre(text) {
  if (!text) return text;
  const t = text.trim();
  const partes = t.split(/(?<=[.!?…])\s+/).filter(Boolean);
  if (partes.length < 2) return t;                  // toda la respuesta es la pregunta: es clarificación
  const ultima = partes[partes.length - 1].trim();
  if (!/\?\s*\**\s*$/.test(ultima)) return t;
  if (PIDE_DATO_RE.test(ultima)) return t;
  // Cortar por posición (no re-unir las partes) conserva saltos de línea, tablas y citas con URL.
  const out = t.slice(0, t.lastIndexOf(ultima)).trim();
  return out.length >= 12 ? out : t;
}

function avisarConsultarAsesor(text, message, lang) {
  if (!text || YA_DERIVA_RE.test(text)) return text;
  const pregunta = preguntaSinContexto(message);
  if (PIDE_REFERENCIAS_RE.test(pregunta)) return text;
  const prescribe = PRESCRIPCION_RE.test(text);
  // Si la respuesta todavía pide el dato que falta, no hay nada que aplicar.
  if (!prescribe && (PIDE_DATO_RE.test(text) || /\?\s*\**\s*$/.test(text.trim()))) return text;
  if (!prescribe && !TEMA_SENSIBLE_RE.test(pregunta)) return text;
  return `${text.trim()}\n\n${AVISO_ASESOR[lang] || AVISO_ASESOR.es}`;
}

// Orden: primero se limpia el cierre y al final se suma el aviso, para que quede como última frase.
function pulirRespuesta(text, message, lang) {
  return avisarConsultarAsesor(quitarPreguntaDeCierre(text), message, lang);
}

module.exports = { pulirRespuesta, quitarPreguntaDeCierre, avisarConsultarAsesor, AVISO_ASESOR };
