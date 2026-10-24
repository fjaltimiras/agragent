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
CEREBRAS_API_KEY=… node eval/run_tool_selection.mjs --provider cerebras --mode planned                          # development set
CEREBRAS_API_KEY=… node eval/run_tool_selection.mjs --provider cerebras --mode planned --benchmark eval/testset.json --tag test
```

The assistant plans before it acts (`api/_planner.js`): a short call to the same model decides which tools
a message needs, and the agent loop then calls them. `eval/benchmark.json` (126 queries in English, Spanish
and Portuguese, 16 out of scope) was used to develop the prompt and the planning step; `eval/testset.json`
(36 queries) was written before the planning step and is the held-out estimate. The harness imports the
prompt, tool schemas, planner and loop settings from `api/`, stubs tool execution and resumes after rate
limits. Modes: `planned` (the released agent), `agentic` (loop without the planning step), `single` (one
round) and `router` (planning step alone). Prompt versions and the frozen test-set hash are in
[`eval/PROMPTS.md`](eval/PROMPTS.md); every raw run is in `eval/runs/`.

With `gpt-oss-120b` on Cerebras, the released agent selected the right tools for 91.7 % of the test
queries (33/36) and 91.3 % of the development queries, against 63.9 % and 61.1 % without the planning step,
and called no tool on every out-of-scope query.

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
