// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 Francisco Altimiras. See LICENSING.md.
/**
 * agragent — LLM provider fallback (shared helper)
 *
 * OpenAI-compatible providers tried in priority order. Patrón replicado del
 * proyecto INIA (api/_agent.js): se llama SIN streaming y el body se lee DENTRO
 * del loop de fallback, de modo que tanto un fallo de conexión como un fallo de
 * lectura del body caen al siguiente proveedor (Vercel a veces entrega headers
 * OK pero rompe al leer el body — "TypeError: fetch failed").
 *
 * Orden: Cerebras (gpt-oss-120b) primario → Groq (openai/gpt-oss-120b) fallback: the same open-weight model on a second provider.
 *
 * Reglas de fallback:
 *   - Salta el proveedor si no tiene API key configurada.
 *   - Reintenta 1 vez SOLO ante 429 (rate-limit), tras 1,5 s.
 *   - 401/403 (credenciales inválidas) → siguiente proveedor (antes abortaba y Groq nunca se probaba).
 *   - Timeout de 20 s por intento: con maxDuration de 30/60 s el fallback tiene que alcanzar a correr.
 *   - Cualquier otro fallo/no-ok/error de body → pasa al siguiente proveedor.
 */

const PROVIDERS = [
  { name: 'cerebras', url: 'https://api.cerebras.ai/v1/chat/completions', key: () => process.env.CEREBRAS_API_KEY, model: 'gpt-oss-120b' },
  { name: 'groq',     url: 'https://api.groq.com/openai/v1/chat/completions', key: () => process.env.GROQ_API_KEY, model: 'openai/gpt-oss-120b' },
];

const REQUEST_TIMEOUT_MS = 20000;
const MAX_ATTEMPTS = 2;

function causeStr(e) {
  const c = e && e.cause;
  if (!c) return e && e.message ? e.message : String(e);
  return `${e.message} (${c.code || c.message || c})`;
}

/**
 * Llama a chat/completions recorriendo los proveedores con fallback.
 * Devuelve el objeto `message` (choices[0].message) del primer proveedor que
 * responde y cuyo body se lee correctamente, junto con el nombre del proveedor.
 * @returns {Promise<{message: object, provider: string}>}
 */
async function completeLLM(body) {
  const errors = [];

  for (const provider of PROVIDERS) {
    if (!provider.key()) { errors.push(`${provider.name}: sin API key`); continue; }

    let served = false;
    for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
      try {
        const res = await fetch(provider.url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${provider.key()}`,
          },
          body: JSON.stringify({ ...body, model: provider.model, stream: false }),
          signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
        });

        if (res.status === 429) {
          errors.push(`${provider.name}: 429 (intento ${attempt})`);
          if (attempt < MAX_ATTEMPTS) { await new Promise(ok => setTimeout(ok, 1500)); continue; }
          break; // agotados los reintentos → siguiente proveedor
        }

        if (res.status === 401 || res.status === 403) {
          errors.push(`${provider.name}: auth error ${res.status}`);
          break; // credencial inválida → siguiente proveedor
        }

        if (!res.ok) {
          const t = await res.text().catch(() => '');
          errors.push(`${provider.name}: ${res.status} ${t.slice(0, 120)}`);
          break; // siguiente proveedor
        }

        // Body read DENTRO del try → un fallo de lectura también cae al fallback
        const data = await res.json();
        const message = data.choices?.[0]?.message;
        if (!message) { errors.push(`${provider.name}: respuesta sin message`); break; }
        served = true;
        return { message, provider: provider.name };
      } catch (e) {
        errors.push(`${provider.name}: ${causeStr(e)}`);
        break; // error de red/body → siguiente proveedor
      }
    }
    if (served) break;
  }

  throw new Error(`No LLM provider available — ${errors.join(' | ')}`);
}

module.exports = { PROVIDERS, completeLLM };
