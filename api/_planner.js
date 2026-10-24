// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 Francisco Altimiras. See LICENSING.md.
/**
 * agragent — plan-then-act: decide qué tools hacen falta antes del loop del agente.
 *
 * Por qué existe: en la evaluación, el mismo modelo, preguntado solo "¿qué herramientas responden esto?",
 * acierta casi siempre; dentro del agente, con las reglas de prudencia del comité de agrónomos, muchas
 * veces no llama la herramienta y le pide el dato al usuario o responde de memoria. Separar las dos
 * decisiones deja la prudencia donde corresponde (cómo se presenta la respuesta) y no en si se consultan
 * los datos.
 *
 * El planificador es una llamada corta al mismo LLM, sin el prompt del asistente, con el catálogo de tools.
 * Si falla o no devuelve nada útil, el agente sigue igual que antes (falla abierto).
 * Lo usan api/chat-stream.js, api/chat.js y eval/run_tool_selection.mjs (mismo código en la evaluación).
 */

const PLANNER_PROMPT = catalogue => 'You are an intent router for an agronomic assistant. Given a user question, decide which of '
  + `the following tools should be called to answer it.\n\n${catalogue}\n\nReply with a JSON array of tool names and nothing `
  + 'else, for example ["get_climate_data"]. If the question is a greeting, off-topic, or answerable without any of these '
  + 'tools, reply with an empty array [].';

// Catálogo compacto: nombre + primera línea de la descripción (como en el router evaluado).
function catalogueOf(tools) {
  return tools.map(t => `- ${t.function.name}: ${t.function.description.split('\n')[0].slice(0, 150)}`).join('\n');
}

/**
 * @param {(body:object)=>Promise<object>} complete  función que recibe el body de chat/completions y
 *        devuelve el `message` de la respuesta (choices[0].message)
 * @param {string} userMessage  último mensaje del usuario, con su bloque [App Context] si lo trae
 * @param {Array} tools  tools en formato OpenAI ({type:'function', function:{name, description, …}})
 * @param {string} [previous]  respuesta anterior del asistente, para preguntas de seguimiento
 * @returns {Promise<string[]>} nombres de tools, solo los que existen
 */
async function planTools(complete, userMessage, tools, previous) {
  const names = tools.map(t => t.function.name);
  const messages = [{ role: 'system', content: PLANNER_PROMPT(catalogueOf(tools)) }];
  if (previous) messages.push({ role: 'assistant', content: String(previous).slice(0, 600) });
  messages.push({ role: 'user', content: userMessage });
  try {
    const msg = await complete({ messages, max_tokens: 1024 });
    const text = String((msg && msg.content) || '');
    return names.filter(n => new RegExp(`\\b${n}\\b`).test(text));
  } catch (e) {
    return [];
  }
}

// Instrucción que se agrega al prompt del sistema en este turno cuando el plan no está vacío.
function planDirective(planned) {
  if (!planned || !planned.length) return '';
  return '\n\n## Plan para este mensaje\n'
    + `Un paso de planificación determinó que responder este mensaje requiere: ${planned.map(n => '`' + n + '`').join(', ')}. `
    + 'Llama esas herramientas ahora, con los argumentos que salen del mensaje y del [App Context] (ubicación, cultivo, '
    + 'etapa, suelo, sistema de riego, valores de análisis que el usuario escribió). No le pidas al usuario un dato que '
    + 'una herramienta trae o que ya está en el mensaje o el contexto. Si a una herramienta le falta un valor no esencial, '
    + 'llámala con un supuesto razonable y decláralo en la respuesta. Las reglas de prudencia siguen valiendo para cómo '
    + 'presentas el resultado: orienta, separa medido de inferido y entrega los planes como estimación a validar con el asesor.';
}

module.exports = { planTools, planDirective, PLANNER_PROMPT, catalogueOf };
