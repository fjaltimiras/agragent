# agragent

Open-source agentic platform for field-scale crop monitoring with free public data.

agragent combines Sentinel-2 imagery (Google Earth Engine), daily weather (Open-Meteo) and an
LLM assistant that calls tools over those data, in a single browser application. This edition contains
six modules:

| Module | What it does |
|---|---|
| **My fields** | Draw a field, or import KML/KMZ/GeoJSON; fields are stored per user (Supabase, row-level security). |
| **Maps** | 30 spectral layers and ESA SL2P biophysical products (LAI, FAPAR, FCOVER, CCC, CWC), time series, scene explorer, side-by-side comparison, k-means management zones and hotspots computed in Earth Engine. |
| **Climate** | Current-season weather to date: temperature, rainfall, ET₀, water balance, growing degree days, chill hours and the historical record since 2015. |
| **Field plan** | Phenological stages located by thermal time (GDD), with a season calendar that follows the field's hemisphere. |
| **Harvest forecast** | Harvest window and an explainable expert yield estimate for 23 crops (weighted indicators, contributions and sensitivity). **It is not a trained model** and its range is not a confidence interval. |
| **Ask agragent** | Assistant with 11 tools: climate, NDVI, geocoding, irrigation and fertilisation plans, soil and foliar report analysis, FAOSTAT, OpenAlex, AGRIS and the INIA Digital Library. |

The hosted service at [app.agragent.com](https://app.agragent.com) includes further modules that are not
part of this repository.

## Architecture

```
app.html              single-file browser app (vanilla JS, Leaflet, ECharts, Earth Engine JS API)
config.js             public deployment settings read by app.html
assets/indices/       spectral index catalogue and SL2P network weights
api/                  Vercel Functions (Node.js): chat (streaming), conversations, fields,
                      Earth Engine token, weather proxy
supabase/schema.sql   tables, quota function and row-level security
scripts/              account creation
eval/                 tool-selection benchmark and arithmetic check used in the paper
```

There is no build step. The LLM runs on OpenAI-compatible endpoints of open-weight models
(Cerebras `gpt-oss-120b`, with the same model on Groq (`openai/gpt-oss-120b`) as fallback; see `api/_llm.js`).

## Deploy your own instance

You need a Supabase project, a Google Cloud project with Earth Engine enabled and a service account
registered for it, and an API key from Cerebras and/or Groq.

1. **Database.** Run `supabase/schema.sql` in the Supabase SQL Editor. In Authentication → Providers,
   disable public sign-up: accounts are created by an administrator.
2. **Accounts.**
   `SUPABASE_URL=… SUPABASE_SERVICE_ROLE_KEY=… node scripts/create-user.mjs you@example.org <password>`
3. **API.** Create a Vercel project from this repository and set the variables listed in
   [`.env.example`](.env.example). The service_role key and every API key stay on the server.
4. **Browser settings.** Fill in [`config.js`](config.js) with the Supabase URL and its anon key. These
   values are public by design; never put a secret there.
5. Deploy (`vercel --prod`) and add the app's origin to `ALLOWED_ORIGINS`.

Local development: `npm install`, then `vercel dev` with a `.env.local` copied from `.env.example`.

## Reproducing the evaluation

```bash
node eval/verify_arithmetic.mjs                    # irrigation/fertilisation arithmetic, no network
# v2: calculators executed, fixed data for external tools, fidelity check
CEREBRAS_API_KEY=… node eval/run_tool_selection.mjs --provider cerebras --mode planned --stubs fixtures                       # development set
for r in r1 r2 r3; do
  CEREBRAS_API_KEY=… node eval/run_tool_selection.mjs --provider cerebras --mode planned --stubs fixtures --benchmark eval/testset.json --tag $r
done
CEREBRAS_API_KEY=… node eval/run_tool_selection.mjs --provider cerebras --mode planned --stubs fixtures --benchmark eval/askset.json --tag ask
# add --model qwen-3.8-27b for the second model; drop --stubs fixtures for v1 (stub without data, selection only)
```

The assistant plans before it acts (`api/_planner.js`): a short call to the same model decides which tools
a message needs, and the agent loop then calls them. `eval/benchmark.json` (126 queries in English, Spanish
and Portuguese, 16 out of scope) was used to develop the prompt and the planning step; `eval/testset.json`
(36 queries) was written before the planning step. The harness imports the prompt, tool schemas, planner and
loop settings from `api/` and resumes after rate limits. Modes: `planned` (the released agent), `agentic`
(loop without the planning step), `single` (one round) and `router` (planning step alone).

Two versions of the benchmark exist. **v1** replaces every tool result with a stub that carries no data and
measures tool selection only. **v2** (`--stubs fixtures`) runs the four local tools for real, gives the seven
external tools the fixed payloads in `eval/fixtures.json`, and checks every figure and DOI/URL in the answer
against the query, the context, the prompt and the tool results (strict bound, and a lenient bound that forgives
one unit conversion). `eval/askset.json` holds nine queries that must not receive a per-area dose. Each result
records the SHA-256 of the code and data it evaluated. Prompt versions, the revision history and the frozen
test-set hash are in [`eval/PROMPTS.md`](eval/PROMPTS.md); every raw run is in `eval/runs/`, summaries in
`eval/results/`.

v2 results on the test set (three runs, 108 pooled; Cerebras):

| Model | Configuration | Right tools | Right tools and every figure traceable (lenient) | Answers with an unexplained figure |
|---|---|---|---|---|
| `gpt-oss-120b` | loop only | 67.6 % | 46/93 | 19/93 |
| `gpt-oss-120b` | released | 90.7 % | 61/93 | 24/93 |
| `qwen-3.8-27b` | loop only | 87.0 % | 61/93 | 17/93 |
| `qwen-3.8-27b` | released | 94.4 % | 58/93 | 26/93 |

Both models declined every out-of-scope query. The planning step fixes tool selection, mostly for
`gpt-oss-120b`; it does not make answers more faithful. Treat figures the assistant gives as guidance and check
them against the tool output shown in the app.

## Data sources and terms

Copernicus Sentinel-2 via Google Earth Engine, Open-Meteo, Nominatim/OpenStreetMap, OpenAlex, AGRIS,
FAOSTAT (CC BY-NC-SA 3.0 IGO, queried at run time and not redistributed) and the INIA Digital Library.
Whoever runs an instance is responsible for complying with each service's terms. Third-party code is
listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## License

agragent is dual-licensed:

- **Open source:** [GNU AGPL-3.0-only](LICENSE). If you run a modified version as a network service, you
  must offer its users the complete source code of that version (section 13).
- **Commercial:** for hosted subscriptions, white-label offerings or integration into proprietary
  software without the AGPL obligations. Write to **contacto@agragent.com**.

"agragent" and its logo are trademarks and are not licensed under either option. Details in
[LICENSING.md](LICENSING.md). Contributions require a Contributor License Agreement
([CONTRIBUTING.md](CONTRIBUTING.md)).

## How to cite

See [CITATION.cff](CITATION.cff), or:

> Altimiras, F. *agragent: an open-source agentic platform for field-scale crop monitoring* (software,
> version 2.0.0). https://github.com/fjaltimiras/agragent
