# agragent

An agentic multimodal platform for crop monitoring and decision support. It combines Sentinel-2 imagery,
climate reanalysis, genomic data visualisation and computer vision behind a conversational agent that
selects its own tools.

Built entirely on free public data of moderate spatial resolution. It is an operational research prototype:
its outputs are interpretive guidance, not agronomic prescriptions, and it is designed as the entry tier of a
stepwise monitoring strategy, establishing a baseline and showing which questions its data cannot settle.

**Live platform:** [app.agragent.com](https://app.agragent.com) (demo account `demo` / `demo33`)

---

## Modules

| Module | What it does |
|---|---|
| Satellite | Sentinel-2 via Google Earth Engine, 13 spectral indices, scene browsing, temporal comparison |
| Climate | Open-Meteo reanalysis: GDD, chill hours, frost, heat waves, ET₀, water balance, risk profile |
| Genomics | RNA-seq differential expression across *Vitis vinifera* phenological stages |
| Vision | YOLO26m fine-tuned on WGISD for grape cluster detection |
| Yield | Heuristic weighted estimate, with a panel reporting measured accuracy on three public datasets |
| Assistant | Conversational agent with 11 autonomous tools over six scientific data sources |

The agent runs **open-weight LLMs** (`gpt-oss-120b`, `gemma-4-31b`, `zai-glm-4.7`) through OpenAI-compatible
endpoints, so the inference layer is self-hostable and not tied to a proprietary vendor.

## Repository layout

```
app.html          single-page frontend (satellite, climate, genomics, vision, yield, assistant)
poligono.kml      sample field boundary, so the workflow can be exercised without drawing one
backend/          FastAPI orchestration service: agent loop, tool schemas, system prompts
  app/agent/      the agentic loop and the eleven tool definitions
  app/services/   domain services (climate, satellite, INIA RAG, AGRIS, FAOSTAT, OpenAlex)
  eval/           evaluation harnesses, benchmark and results
yolo/             train_yolo26_wgisd.py: fine-tunes YOLO26m on the official WGISD split
```

This repository is scoped to what reproduces the paper. The marketing landing page served at
`agragent.com`, and the institutional logos it uses, are deliberately not included; the platform itself is
`app.html`, which is the frontend the manuscript describes. The deployment therefore contains files this
repository does not, and `vercel.json` here differs accordingly: it simply serves `app.html`.

## Running it locally

The frontend is self-contained and needs only a static server (not `file://`, because of CORS):

```bash
git clone https://github.com/fjaltimiras/agragent.git
cd agragent
python3 -m http.server 8080     # then open http://localhost:8080/app.html
```

The assistant additionally needs the backend:

```bash
cd backend
cp .env.example .env            # fill in CEREBRAS_API_KEY / GROQ_API_KEY and Supabase credentials
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Authentication is client-side only and the role label carries no server-side enforcement. Deployments that
need real access control must add it.

## Evaluation and reproducibility

Everything below lives in `backend/eval/` and can be re-run.

| Evaluation | Result |
|---|---|
| Tool selection, 63 queries, 3 open-weight models | 69.8% / 73.0% / 73.0% query accuracy; 100% abstention on out-of-scope |
| Non-agentic ablations (single-call, router, no-tools) | Accuracy statistically indistinguishable; the loop buys coverage on compound queries, not better per-tool choice |
| Calculator arithmetic (FAO-56 irrigation, N balance) | 12/12 |
| Cluster detection, YOLO26m on the official WGISD split | mAP50 0.880, mAP50-95 0.581 |
| Yield, three public datasets | FAOSTAT grapes R²=0.92; CropNet maize counties R²=0.41; within-field vineyard R²=-0.12 (MAPE 53%, operationally unusable), 0.38 adding inflorescence counts |

The arithmetic check needs no API key and no network:

```bash
cd backend && python3 eval/verify_arithmetic.py
```

The tool-selection benchmark drives the production agent stack against an OpenAI-compatible endpoint,
one model pinned per run, with tool execution stubbed to isolate selection:

```bash
cd backend
python3 eval/run_eval_openweight.py --provider cerebras --model gpt-oss-120b --sleep 0.5 --timeout 90
python3 eval/run_eval_openweight.py --provider cerebras --model zai-glm-4.7 --mode router   # ablation
python3 eval/run_eval_openweight.py --provider cerebras --dry-run                            # no API calls
```

Model identifiers are reproduced verbatim as the endpoint advertises them. No sampling parameter is
overridden and no seed is set, so runs are not bitwise reproducible; the archived per-model results in
`backend/eval/` are the ones reported in the manuscript.

Predictability is scale-dependent: the platform reports this rather than quoting a single accuracy figure.
The yield estimate is a weighted heuristic, **not** a trained model, and no accuracy figure is claimed for it.

An expert-panel rating instrument for recommendation quality is released in `backend/eval/expert_panel/`.
It has **not** been executed: tool selection is not the same thing as advice quality.

## Data sources

Sentinel-2 via [Google Earth Engine](https://earthengine.google.com) · [Open-Meteo](https://open-meteo.com) ·
[OpenAlex](https://openalex.org) · [AGRIS FAO](https://agris.fao.org) · Biblioteca Digital INIA Chile ·
[FAOSTAT](https://www.fao.org/faostat) · [WGISD](https://github.com/thsant/wgisd) (Embrapa)

## License

[GNU Affero General Public License v3.0](LICENSE). The network-use clause is deliberate: anyone running a
modified version as a network service must publish their changes. Both the frontend and the backend
orchestration layer are covered.

## Citation

```bibtex
@software{agragent2026,
  author = {Altimiras, Francisco},
  title = {agragent: An Agentic Multimodal Architecture for Crop Monitoring and Decision Support},
  year = {2026},
  url = {https://github.com/fjaltimiras/agragent},
  institution = {N\'{u}cleo de Investigaci\'{o}n en Data Science, Facultad de Ingenier\'{i}a y Negocios, Universidad de las Am\'{e}ricas}
}
```

The genomic module builds on Altimiras et al. (2024),
[doi:10.3390/agronomy14030613](https://doi.org/10.3390/agronomy14030613).

## Author

**Francisco Altimiras** — ORCID [0000-0003-1992-8338](https://orcid.org/0000-0003-1992-8338)
Núcleo de Investigación en Data Science, Facultad de Ingeniería y Negocios,
Universidad de las Américas, Chile
