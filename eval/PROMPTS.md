# Prompt versions used in the evaluation

The system prompt lives in `api/chat-stream.js` (`SYSTEM_PROMPT`). Two versions were benchmarked:

- **Prompt A** — runs tagged `_promptA`. The prompt as of 2026-10-23, before the tool-use revision.
- **Prompt B** — the released prompt (untagged runs). Prompt A with the four rules below rewritten after
  the prompt-A benchmark showed that the assistant asked users for NDVI values, interpreted laboratory
  values without the analysis tools and asked which crop to use when the question named one. The revision
  was informed by the benchmark failures, so prompt-B results are optimistic for this benchmark.

To reproduce a prompt-A run, replace each prompt-B rule below with its prompt-A text and run with `--tag promptA`.

## Change 1

Prompt A:

> 2. **Antes de prescribir, verifica lo que falta.** Una dosis o lámina depende de datos que a menudo no tienes (análisis de suelo, sistema de riego, etapa confirmada en terreno, rendimiento objetivo). Si falta algo que cambia la recomendación, pregúntalo en una línea, en lenguaje natural ("¿qué tipo de suelo tiene y riega por goteo?", nunca nombres internos como franco_arenoso), en vez de asumirlo. Si igual das una cifra, di qué supuesto usaste.

Prompt B:

> 2. **Antes de prescribir, verifica lo que falta.** Una dosis o lámina depende de datos que a menudo no tienes (análisis de suelo, sistema de riego, etapa confirmada en terreno, rendimiento objetivo). Primero busca esos datos en el mensaje y en el contexto: si el usuario pidió el plan y ahí están el cultivo y lo esencial (rendimiento objetivo para fertilizar; sistema de riego para regar), **llama la calculadora** y declara los supuestos que usaste. Pregunta solo lo que falte de verdad y cambie la recomendación, en una línea y en lenguaje natural ("¿qué tipo de suelo tiene y riega por goteo?", nunca nombres internos como franco_arenoso).

## Change 2

Prompt A:

> 4. **Nunca pidas al usuario un dato que puedes consultar** (ET₀, lluvia, temperatura, pronóstico, NDVI): llama la herramienta.

Prompt B:

> 4. **Nunca pidas al usuario un dato que puedes consultar** (ET₀, lluvia, temperatura, pronóstico, NDVI u otro índice satelital, de hoy, de un período o para comparar fechas): llama la herramienta (`get_climate_data`, `get_ndvi_data`). Si el contexto no trae el valor, consúltalo; nunca le pidas al usuario que te lo dé.

## Change 3

Prompt A:

> 5. **Ubicación y cultivo:** si el usuario nombra un lugar

Prompt B:

> 5. **Ubicación y cultivo:** si el mensaje nombra un cultivo, ese manda sobre el del contexto (el contexto describe el campo seleccionado, no limita la pregunta); no preguntes cuál de los dos. Si el usuario nombra un lugar

## Change 4

Prompt A:

> 6. **Suelo o foliar:** si el usuario los menciona, pide el análisis adjunto (botón 📎).

Prompt B:

> 6. **Suelo o foliar:** si el usuario escribe valores de un análisis (pH, CE, N, P, K, micronutrientes…), interprétalos con `analyze_soil_report` o `analyze_foliar_report`, no de memoria. Si solo menciona que tiene un análisis, sin valores, pídelo (botón 📎).

## Plan-then-act (released agent)

The released agent adds a planning step before the loop (`api/_planner.js`): one short call to the same model,
without the assistant prompt, returns the tools the message needs; when that list is not empty, a paragraph
naming them is appended to the system prompt for that turn (`planDirective`). If the planning call fails, the
agent runs exactly as prompt B. With a non-empty plan, the first round is called with `tool_choice: 'required'` (at least one
tool call); later rounds use `auto`. That was added after the first plan-then-act run on the development set
(86.5 %, `_planned_auto` files), in which most remaining failures had a correct plan that the agent did not act on. It was introduced because the router ablation selected the right tools far more
often than the agent did under the prudence rules. Harness: `--mode planned` (released agent),
`--mode agentic` (prompt B without the planning step).

In the same revision, the `Rendimiento` paragraph stopped quoting scale-dependent R² values (country ≈ 0.92,
county ≈ 0.41), which have no source in this repository; it now says only that predictability drops at finer scales.
That paragraph is not reached by any benchmark query.

## Development set and test set

`benchmark.json` (126 queries) was used to develop prompt B and the planning step, so results on it are
development-set results. `testset.json` (36 queries, T01–T36) was written and labelled on 2026-10-23 before the
planning step was implemented and is not edited afterwards; SHA-256 of the file as frozen:
`8fe2c4342b62e8be52c3dea11ec0b9f4b6b92709093bfdc4fd9d2b4e893a844d`. Results on it are reported as the
held-out estimate.

## Revision after the internal review (2026-10-24): target yield and benchmark v2

An internal review of the first plan-then-act runs found two problems that the selection score could not show:

1. `calculate_fertilization_plan` defaulted to a target yield of 30 t/ha when none was given (meaningless for
   grapevine), and the planning directive told the assistant to call a tool "with a reasonable assumption". The
   default was removed: without a target yield the calculator returns `missing_input` and the assistant must ask.
   The schema and the planning directive now say that a datum that fixes the dose is not an assumption.
2. With the empty stub, answers cannot contain tool data, so any figure in them is invented. Benchmark v2
   (`--stubs fixtures`) gives the external tools the fixed payloads of `fixtures.json` and runs the four local tools,
   and measures **fidelity**: figures and references in the answer that cannot be traced to the query, the context,
   the system prompt or a tool result (strict bound), and the subset not explained by one unit or area conversion
   (lenient bound). `askset.json` (A1–A9) adds queries whose safe answer gives no dose.

The test set was not edited. Because these changes came after the test set had been run once, results on it with
the revised code are reported as a second evaluation of a revised system, alongside the first. Each test-set
configuration is run three times (`--tag r1|r2|r3`); every result file records the SHA-256 of the code and data it
evaluated.
