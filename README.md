# agragent — Computational Crop Monitoring Platform for Viticulture

**agragent** is an open-source precision agriculture platform designed for real-time monitoring of grapevine production systems. It integrates satellite remote sensing, climate analytics, genomic data visualization, computer vision, and an **AI-powered agronomic assistant** into a single web application.

The AI Assistant (AgrAgent) is a conversational agent powered by Claude that provides context-aware agronomic recommendations based on the data the user is currently viewing — satellite imagery, climate KPIs, field polygons, and yield predictions.

Developed as part of a PhD research project in Computer Science at the Pontificia Universidad Católica de Valparaíso (PUCV), Chile, focusing on computational crop monitoring using bioinformatics and machine learning.

---

## Table of Contents

- [Features](#features)
- [WhatsApp Demo](#whatsapp-demo)
- [AI Assistant](#ai-assistant)
- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Data Sources](#data-sources)
- [Getting Started](#getting-started)
- [KML/KMZ Support](#kmlkmz-support)
- [Google Earth Engine Integration](#google-earth-engine-integration)
- [Climate Data Pipeline](#climate-data-pipeline)
- [GDD Comparison Between Dates](#gdd-comparison-between-dates)
- [Field Action Plan](#field-action-plan)
- [Genomic Analysis](#genomic-analysis)
- [Image Analysis — WGISD Dataset](#image-analysis--wgisd-dataset)
- [Vegetation Indices](#vegetation-indices)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Author](#author)
- [Associated Publications](#associated-publications)
- [Citation](#citation)
- [License](#license)

---

## Features

| Module | Description |
|---|---|
| **Login** | Username/password authentication with role-based access (Admin, Viewer) |
| **Dashboard** | Dynamic agronomic overview: 8 KPIs, water balance, risk assessment, alerts, charts, **satellite indices**, and **yield prediction summary** — all derived from the user's polygon |
| **Satellite Maps** | Sentinel-2 imagery via Google Earth Engine (auto-connected via service account) with 13 spectral indices grouped by category, scene browsing, split-screen temporal comparison, **location search** (Nominatim geocoding), and collapsible panels |
| **Climate Data** | Real-time climate analytics from Open-Meteo — temperature, precipitation, humidity, solar radiation, ET₀, GDD, chill hours, frost, heat waves (8 KPIs + 6 charts), **GDD comparison between custom date ranges** |
| **Genomic Analysis** | Real RNA-seq DEG data from Altimiras et al. (2024) — 3,603 DEGs across 8 phenological stages of *Vitis vinifera* |
| **Image Analysis** | Integration with the WGISD dataset (Embrapa) — 300+ grape cluster images with YOLO bounding box annotations |
| **Yield Prediction** | Dynamic yield prediction using PyCaret Extra Trees Regressor (R²=0.972) — yield/ha, total yield, harvest date, feature importance, satellite indices, and multi-model comparison — computed automatically from polygon data |
| **Field Action Plan** | Phenological delay analysis (GDD-based), chill hours assessment, seasonal activity calendar with stage-specific field operations, and climate alerts with agronomic recommendations |
| **AI Assistant** | Context-aware conversational agent (Claude) with access to climate, satellite, soil, irrigation, and fertilization tools |
| **References** | Author info, ORCID, associated publications with DOIs, dataset citations |
| **Multi-language** | English, Spanish, and Portuguese — language persisted in localStorage |

### Authentication

- Login screen with username/password
- Default users: `admin` (full access, GEE credentials auto-filled) and `demo` (viewer)
- Sessions stored in sessionStorage (24h expiry)
- User list stored in localStorage (can be extended)
- Logout button in sidebar

### Dynamic Dashboard

The dashboard starts empty and automatically populates when the user uploads a KML/KMZ file or draws a polygon:

- **Location**: reverse-geocoded name from polygon centroid (via OpenStreetMap Nominatim)
- **Field area**: computed from polygon coordinates (shoelace formula)
- **8 KPI cards**: location, area, GDD, precipitation, chill hours, frost days, heat waves, ET₀
- **Water balance**: visual comparison of precipitation vs evapotranspiration with deficit/surplus indicator
- **Agronomic risk assessment**: color-coded progress bars for chill accumulation, GDD, water balance, frost risk, heat stress
- **Active alerts**: generated from actual climate data (frost, heat waves, drought, low GDD, low chill, high ET₀)
- **Temperature chart**: monthly min/max from Open-Meteo
- **Precipitation vs ET₀ chart**: monthly comparison for irrigation planning
- **Satellite indices**: real-time NDVI, NDRE, MSAVI, TCARI, EVI, NDMI from Sentinel-2 (color-coded)
- **Yield prediction summary**: yield/ha, total yield, harvest date, and model info
- **Polygon table**: list of all loaded polygons with centroids

### Multi-language Support

- Language selector (EN/ES/PT) in the top bar
- All navigation, section headers, KPI labels, chart titles, buttons, and messages are translated
- Language preference saved in localStorage and restored on reload

### Satellite Analysis

- **Median Composite**: cloud-free composite from all Sentinel-2 scenes in a date range
- **Scene Browser**: browse individual acquisitions with cloud cover percentage
- **Date Comparison**: split-screen slider comparing two acquisition dates
- **Vegetation Indices** (13 total, grouped by category):
  - **Vigor**: NDVI, EVI, SAVI, MSAVI
  - **Health**: NDRE, GNDVI, TCARI, CIre (Chlorophyll Index Red Edge)
  - **Water**: NDMI (Moisture), NDWI (Water)
  - **Soil**: BSI (Bare Soil Index)
  - **Visual**: True Color RGB, False Color (NIR-R-G)
- **Cloud Masking**: automatic QA60-based cloud and cirrus removal
- **Polygon Clipping**: imagery rendered only within field boundaries

### Climate Analytics (8 KPIs + 6 Charts)

| KPI | Description |
|---|---|
| **GDD** | Growing Degree Days (base 10°C), accumulated Sep–Mar |
| **Chill Hours** | Hours between 0–7.2°C during dormancy (Apr–Sep) |
| **Frost Days** | Days with Tmin ≤ 0°C, with last frost date |
| **Heat Waves** | Events of ≥3 consecutive days above 35°C |
| **Dry Months** | Months with <30mm precipitation |
| **Humidity** | Average relative humidity (%) |
| **Solar Radiation** | Total shortwave radiation (MJ/m²) |
| **ET₀** | FAO Penman-Monteith reference evapotranspiration (mm) |

Charts: monthly temperature (min/max), precipitation, relative humidity, solar radiation, evapotranspiration, GDD accumulation.

All climate data is fetched dynamically from the [Open-Meteo Archive API](https://open-meteo.com/) based on the polygon centroid — **any location worldwide**.

### GDD Comparison Between Dates

- Select two custom date ranges (Period A and Period B) to compare GDD accumulation
- Fetches data from Open-Meteo in a single optimized request
- Displays 3 KPI cards: total GDD for each period and the absolute/percentage difference
- Overlay line chart showing daily accumulated GDD for both periods aligned by day number
- Interactive tooltips with GDD values per day
- Useful for comparing current vs. previous season, or any two arbitrary periods

### Field Action Plan

A dedicated section for phenological tracking and seasonal planning:

- **Phenological Delay Analysis**: table comparing real GDD accumulation rate against reference thresholds (Coombe 1995, Modified E-L scale) to estimate delays or advances for each of the 10 growth stages (E-L 3 through E-L 41). Shows expected date, status (Reached / On track / Delayed / Advanced), and shift in days.
- **Chill Hours Assessment**: real accumulated chill hours (0–7.2°C, Apr–Sep) vs. the 400–600h typical requirement for *Vitis vinifera*, with status indicator (Sufficient / Marginal / Insufficient) and bud break uniformity recommendation.
- **Seasonal Activity Calendar**: visual timeline of recommended field operations per phenological stage — includes protection, canopy management, nutrition, irrigation, phytosanitary, monitoring, and harvest activities. Current stage highlighted, completed stages dimmed.
- **Climate Alerts & Recommendations**: automatic alerts based on real field data:
  - Slow/fast GDD accumulation (cool vs. warm season)
  - Frost days with protection recommendations
  - Heat waves with irrigation and shade recommendations
  - Insufficient chill hours with cyanamide suggestion
  - Low precipitation with supplementary irrigation planning

### Location Search

- **Search bar** in the Satellite Maps section for quick navigation to any location worldwide
- Autocomplete with debounced requests (350ms) to the Nominatim geocoding API
- Results display location name and administrative details
- Selecting a result triggers a smooth `flyTo` animation with a temporary marker and popup
- Supports Enter key to search and Escape to dismiss results

### Field Management

- Upload KML/KMZ files to define field boundaries
- Draw, edit, and delete polygons directly on the map (Leaflet-Geoman)
- Export polygons as KML
- Multi-polygon support
- Location auto-detection via reverse geocoding
- **Reactive updates**: deleting or editing a polygon recalculates all sections (dashboard, climate, satellite indices, yield prediction); removing all polygons resets the app to empty state

### Yield Prediction

When a polygon is loaded, the system automatically computes yield predictions using climate and satellite data:

- **Satellite indices extraction**: mean NDVI, NDRE, MSAVI, TCARI, EVI, NDMI computed via GEE `reduceRegion` over the polygon area
- **Yield model**: PyCaret Extra Trees Regressor (R²=0.972, MAPE=3.8%) with 15 weighted features:
  - Climate: precipitation, GDD, max temperature, chill hours, humidity, ET₀, solar radiation, frost days, heat waves
  - Satellite: NDVI, NDRE, MSAVI, TCARI, EVI, NDMI
- **Dynamic Feature Importance**: contribution = weight × normalized value, recalculated per prediction
- **Outputs**:
  - Yield per hectare (t/ha) with confidence interval
  - Total yield based on polygon area
  - Estimated harvest date (GDD-based phenological model)
- **Multi-model comparison**: Extra Trees, CatBoost, Random Forest, XGBoost, SVR — each produces its own prediction per polygon
- **Dashboard integration**: satellite indices and yield summary cards update automatically

### Collapsible UI Panels

All map section panels (Sentinel-2 Controls, Layers & Tools, Vegetation Indices) are collapsible on both desktop and mobile for a cleaner interface.

### Genomic Analysis — Gene Ontology & AlphaFold

- **Clickable gene IDs**: Click any VIT_ gene in DEG tables to fetch data from UniProt and AlphaFold
- **Gene Ontology annotations**: Biological Process, Molecular Function, Cellular Component — fetched in real-time from UniProt REST API
- **AlphaFold integration**: Direct links to 3D protein structures, PDB and CIF downloads
- **GO Enrichment**: "Compute from UniProt" button fetches GO terms for all 25 DEGs and shows frequency-ranked bar chart by aspect (BP/MF/CC)

### Image Analysis — YOLOv11 + WGISD

- **WGISD dataset**: 300 images, 5 grape varieties (Chardonnay, Cabernet Franc, Cabernet Sauvignon, Sauvignon Blanc, Syrah)
- **Bounding box visualization**: Color-coded by cluster size, numbered labels, accurate canvas overlay
- **Berry estimation**: Based on bbox area — small clusters ≈ 20 berries, large ≈ 80
- **Upload your own image**: Sends to backend API (`POST /api/detect/`) for real-time YOLOv11 inference
- **Backend**: FastAPI + YOLOv11n deployed on Railway (`agragent-api-production.up.railway.app`)
- **Training script**: `yolo/train_wgisd.py` — downloads WGISD, trains YOLOv11n, exports ONNX

### Farmer-Friendly UX

- **Plain language**: Technical terms replaced with farmer-friendly labels (NDVI → "Plant Health", GDD → "Heat Units", ET₀ → "Water Loss")
- **Larger touch targets**: Min 40-44px buttons on mobile
- **Step-by-step onboarding**: 1-2-3 guide in welcome screen
- **Full i18n**: English, Spanish, Portuguese — ~200 translation keys covering all UI elements
- **Collapsible conversations**: Chat sidebar can be minimized

---

## WhatsApp Demo

`whatsapp-demo.html` is a standalone prototype that simulates how AgrAgent would work as a WhatsApp conversational agent. It is a single HTML file with no build step, connecting directly to the FastAPI backend.

### Purpose

- Test the full agentic loop (Claude + **7 tools**) in a messaging-style UI before integrating with a real WhatsApp Business API
- Demo agronomic conversations with soil/foliar report uploads, field location sharing, INIA bibliography search, and tool call visualization
- Works on desktop and mobile browsers

### Running the demo

```bash
# 1. Start the FastAPI backend
cd backend
python3 -m uvicorn app.main:app --reload --port 8000

# 2. Serve the frontend (from agragent-app/)
cd ..
python3 -m http.server 8080

# 3. Open in browser
open http://localhost:8080/whatsapp-demo.html
```

Or open `whatsapp-demo.html` directly in the browser — the backend has CORS open for `*`, so `file://` also works.

### Features

| Feature | Description |
|---|---|
| **WhatsApp Web UI** | Dark theme, message bubbles, typing indicator, timestamps — fully responsive (mobile + desktop) |
| **Conversation list** | Collapsible sidebar with search and history loaded from Supabase |
| **Projects / folders** | Organize conversations into color-coded folders stored in localStorage; right-click to edit/delete |
| **Rename & delete** | Hover a conversation → inline rename (Enter to save, Esc to cancel) or delete — no page reload |
| **Markdown rendering** | Tables, lists, bold, code blocks in assistant responses |
| **Tool badges** | Each response shows which tools Claude used (🌤️ Climate · 🛰️ NDVI · 🧪 Soil · 💧 Irrigation · 🌱 Fertilization · 📚 INIA) |
| **INIA library search** | Claude can query 19K+ open-access agricultural documents from Biblioteca Digital INIA Chile in real time |
| **File upload (📎)** | Attach PDF or Excel soil/foliar reports — parsed by backend and sent to the agent automatically |
| **Field location (📍)** | Share field location via 4 methods (see below) |
| **Config (⚙️)** | Change backend URL at runtime (useful to point to Railway instead of localhost) |
| **Mobile** | Sidebar as full overlay, hamburger menu, full-screen modals, iOS-safe input font size |

### Field Location Panel (📍)

Clicking the 📍 button opens a panel with four ways to specify the field:

| Tab | How it works |
|---|---|
| **🔍 Buscar** | Type a place name → Nominatim geocoding → pin on map |
| **🛰️ GPS** | Enter latitude/longitude manually + optional area in ha |
| **🗂️ KML/KMZ** | Drag and drop or select a KML/KMZ file → polygons parsed in-browser, area and centroid computed |
| **✏️ Dibujar** | Draw the polygon directly on the map using Leaflet-Geoman tools (free polygon, rectangle, edit, delete) → area and centroid calculated automatically |

On confirm, a structured message is sent to the agent with the centroid coordinates and polygon vertices so Claude can use them in `get_climate_data`, `get_ndvi_data`, and irrigation/fertilization tools.

### Backend requirements

The demo connects to the same FastAPI backend as the main app. Required environment variables in `backend/.env`:

```env
ANTHROPIC_API_KEY=sk-ant-...
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
```

Pull from Vercel automatically:
```bash
cd agragent-api
npx vercel env pull ../agragent-app/backend/.env --environment=production
```

---

## AI Assistant

agragent includes an integrated AI agronomic assistant powered by [Claude](https://www.anthropic.com/claude) (Anthropic) via a FastAPI backend.

### Availability

- **Floating widget**: accessible from any screen via the bottom-right AgrAgent logo button
- **Full-page section**: dedicated "AI Assistant" section in the sidebar with full conversation management

Both views are synchronized — conversations, messages, and state are shared.

### Context-Aware Responses

Every message automatically includes the current application state:

| Context | Data Sent |
|---|---|
| **Field** | Location name, area, polygon coordinates, centroid |
| **Climate** | GDD, chill hours, frost days, heat waves, humidity, ET₀, solar radiation, water balance |
| **Alerts** | Active agronomic alerts (frost, drought, heat stress, low GDD) |
| **Satellite** | GEE connection status, active vegetation index, available Sentinel-2 scenes |
| **Yield** | Predicted yield value |
| **Section** | Which module the user is currently viewing |

### Agent Tools

The backend agent has 6 tools it can invoke autonomously:

| Tool | Description |
|---|---|
| `get_climate_data` | Fetch real-time weather/climate data by coordinates |
| `get_ndvi_data` | Retrieve satellite NDVI data from Sentinel-2 |
| `analyze_soil_report` | Parse and interpret uploaded soil analysis |
| `analyze_foliar_report` | Parse and interpret leaf tissue analysis |
| `calculate_irrigation_plan` | ET₀ × Kc irrigation scheduling |
| `calculate_fertilization_plan` | NPK requirements based on yield target |

### Conversation Management

- Create, rename (✏️), and delete conversations
- Conversation history persisted in Supabase
- Quick-start cards translated to EN/ES/PT
- Markdown rendering with tool-use badges

### Backend

The AI backend is a separate FastAPI service (`agro-agent/`) that communicates with Claude via the Anthropic API with an agentic loop (max 10 iterations per message).

---

## How It Works

1. **Login** with your credentials (default: `admin` / `agragent2026`)
2. **Navigate to Satellite Maps** and upload a KML/KMZ file or draw a polygon
3. The app automatically:
   - Detects the location name via reverse geocoding
   - Fetches climate data from Open-Meteo for that location
   - Computes agronomic indicators (GDD, chill hours, water balance, risk assessment)
   - Updates the Dashboard, Climate, and all sections with real data
4. **Connect to Google Earth Engine** (credentials auto-filled for admin) to view Sentinel-2 satellite imagery clipped to your polygon
5. **Compare dates** using the split-screen slider in Compare mode
6. **Change language** (EN/ES/PT) from the selector in the top bar
7. Explore genomic data, grape images, and yield predictions

---

## Architecture

agragent combines a **single-page frontend** (`index.html`) with an optional **FastAPI backend** for AI assistant capabilities:

- **Frontend**: self-contained SPA with all HTML, CSS, and JS — runs standalone for monitoring features
- **Backend** (`agro-agent/`): FastAPI service providing conversational AI via Claude, with tool-calling and conversation persistence in Supabase
- **Deployment**: frontend on Vercel (`agragent.com`), backend deployable independently

```
┌──────────────────────────────────────────────────────────┐
│                        Browser                            │
│                                                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ Leaflet  │  │ Chart.js │  │ Earth     │  │   AI    │ │
│  │ Map +    │  │10 Charts │  │ Engine JS │  │  Chat   │ │
│  │ Geoman   │  │ + i18n   │  │ (OAuth)   │  │ Widget  │ │
│  └────┬─────┘  └────┬─────┘  └────┬──────┘  └────┬────┘ │
│       └──────────────┼─────────────┘              │      │
│                      │                            │      │
│              index.html (SPA)                     │      │
└──────────────────────┬────────────────────────────┼──────┘
                       │                            │
       ┌───────────────┼───────────────┐     ┌──────┴──────┐
       │               │               │     │  FastAPI     │
  Open-Meteo      Google Earth    Nominatim  │  Backend     │
  Archive API     Engine API      Geocoding  │  (agro-agent)│
  (climate)       (Sentinel-2)    (location) │      │       │
       │                                     │  ┌───┴────┐  │
   WGISD/GitHub                              │  │ Claude │  │
   (grape images)                            │  │  API   │  │
                                             │  └───┬────┘  │
                                             │  ┌───┴────┐  │
                                             │  │Supabase│  │
                                             │  └────────┘  │
                                             └──────────────┘
```

---

## Data Sources

| Source | Type | Access | Usage |
|---|---|---|---|
| [Sentinel-2 SR Harmonized](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED) | Satellite imagery (10m) | Google Earth Engine | Vegetation indices, RGB composites |
| [Open-Meteo Archive API](https://open-meteo.com/en/docs/historical-weather-api) | Historical weather | Free, no API key | Temperature, precipitation, humidity, solar radiation, ET₀, hourly temps |
| [Nominatim](https://nominatim.openstreetmap.org/) | Reverse geocoding | Free, no API key | Location name from polygon centroid |
| [WGISD](https://github.com/thsant/wgisd) (Embrapa) | Grape cluster images | Public dataset | Object detection annotations |
| RNA-seq data (Altimiras et al.) | DEG analysis | Published supplementary | Genomic section: 3,603 DEGs across 8 E-L stages |

---

## Getting Started

### Prerequisites

- A modern web browser (Chrome, Firefox, Edge)
- Python 3.x (for local HTTP server) or any static file server

### Live Demo

The platform is deployed at **[app.agragent.com](https://app.agragent.com)**

### Quick Start (Local)

```bash
# Clone the repository
git clone https://github.com/fjaltimiras/agragent.git
cd agragent

# Start a local HTTP server
python3 -m http.server 8080

# Open in browser
open http://localhost:8080
```

> **Note**: A local HTTP server is required (not `file://`) because the app makes API calls that require proper CORS handling.

### With AI Assistant (Backend)

```bash
# Clone and set up the backend
cd agro-agent
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY and SUPABASE credentials
pip install -r requirements.txt

# Run the backend (serves frontend + API)
uvicorn app.main:app --reload --port 8000

# Open in browser
open http://localhost:8000
```

### Default Login Credentials

| User | Password | Role | GEE Credentials |
|------|----------|------|-----------------|
| `admin` | `agragent2026` | Admin | Full access |
| `demo` | `demo` | Viewer | Demo access |

### Google Earth Engine

Satellite imagery is **auto-connected** via a GEE service account — no user login required. The backend API (`/api/gee-token`) generates access tokens using the service account credentials stored in Vercel environment variables.

For self-hosting, configure these environment variables in your API deployment:
- `GEE_CLIENT_EMAIL` — service account email
- `GEE_PRIVATE_KEY_B64` — base64-encoded private key
- `GEE_PROJECT_ID` — Google Cloud project ID

---

## KML/KMZ Support

agragent supports loading field boundaries from standard KML and KMZ files:

- **KML**: parsed using the DOMParser API and [@mapbox/togeojson](https://github.com/mapbox/togeojson)
- **KMZ**: unzipped in-browser using [JSZip](https://stuk.github.io/jszip/), then KML extracted and parsed
- Polygon coordinates are stored for GEE geometry clipping (`ee.Geometry.Polygon` / `ee.Geometry.MultiPolygon`)
- Altitude values are automatically stripped (GEE requires 2D coordinates)
- Supports multi-polygon KML files (multiple `<Placemark>` elements)
- Uploading a KML/KMZ automatically triggers: reverse geocoding, climate data loading, GEE tile refresh

---

## Google Earth Engine Integration

The app connects to GEE via the [Earth Engine JavaScript API](https://developers.google.com/earth-engine/guides/npm_install) (v0.1.395) using OAuth 2.0 browser authentication.

### Image Processing Pipeline

```
COPERNICUS/S2_SR_HARMONIZED
  → filterDate(startDate, endDate)
  → filterBounds(polygonGeometry)
  → filter(CLOUDY_PIXEL_PERCENTAGE < threshold)
  → map(QA60 cloud mask)
  → median()
  → clip(polygonGeometry)
  → compute vegetation index
  → getMapId(visParams)
  → L.gridLayer with formatTileUrl()
```

### Cloud Masking

Uses the Sentinel-2 QA60 band to mask clouds (bit 10) and cirrus (bit 11):

```javascript
const qa = img.select('QA60');
const mask = qa.bitwiseAnd(1 << 10).eq(0)
  .and(qa.bitwiseAnd(1 << 11).eq(0));
return img.updateMask(mask);
```

---

## Climate Data Pipeline

Climate data is fetched from the [Open-Meteo Archive API](https://open-meteo.com/en/docs/historical-weather-api) — a free, open-source weather API that requires no authentication.

### Variables Fetched

| Variable | Frequency | API Parameter |
|---|---|---|
| Max temperature | Daily | `temperature_2m_max` |
| Min temperature | Daily | `temperature_2m_min` |
| Precipitation | Daily | `precipitation_sum` |
| Relative humidity | Daily | `relative_humidity_2m_mean` |
| Solar radiation | Daily | `shortwave_radiation_sum` |
| Evapotranspiration | Daily | `et0_fao_evapotranspiration` |
| Temperature | Hourly | `temperature_2m` (for chill hours) |

### Processing Pipeline

1. **Centroid extraction**: compute polygon centroid from all loaded coordinates
2. **API request**: fetch daily + hourly data for the growing season (April year N → March year N+1)
3. **Monthly aggregation**: averages (temperature, humidity) and sums (precipitation, solar, ET₀)
4. **GDD computation**: `GDD = max(0, (Tmax + Tmin)/2 - 10)`, accumulated September–March
5. **Chill hours**: count hourly temperatures between 0–7.2°C during dormancy (April–September)
6. **Frost detection**: days with Tmin ≤ 0°C, with last frost date
7. **Heat wave detection**: sequences of ≥3 consecutive days with Tmax > 35°C
8. **Alert generation**: automatic alerts based on thresholds (low GDD, frost, heat waves, drought, high ET₀)

### Season Definition

The agricultural season follows the Southern Hemisphere viticulture calendar:
- **Full season**: April (year N) through March (year N+1)
- **Growing season** (GDD accumulation): September through March
- **Dormancy** (chill hours): April through August

---

## Genomic Analysis

The Genomic Analysis section displays real RNA-seq differential expression data from:

> Altimiras, F. et al. *Transcriptome Data Analysis Applied to Grapevine Growth Stage Identification.* Agronomy, 14(3), 613, 2024.

### Data Summary

- **68 RNA-seq samples** from *Vitis vinifera* (1,336M reads, 87 GB)
- **8 phenological stages** compared against E-L 3 baseline (Modified E-L scale)
- **3,603 unique DEGs** identified (FDR < 0.05, edgeR)
- **5 grape varieties**: Muscat Blanc a Petits Grains, Corvina, Cabernet Sauvignon, Sangiovese, *V. vinifera* sylvestris

### Visualizations

- RNA-seq processing pipeline (Raw Reads → FastQC → Trimmomatic → Salmon → tximeta → edgeR → DEGs → ML Classification)
- DEG bar chart: up/down-regulated genes per developmental stage
- DEG accumulation curve across stages
- Sample composition by variety
- Tabbed DEG tables with real logFC and FDR values for each stage comparison
- Full summary table with counts per comparison

---

## Image Analysis — WGISD Dataset

The Image Analysis module integrates the **Wine Grape Instance Segmentation Dataset** (WGISD) from Embrapa:

- **300+ images** of grape clusters in field conditions
- **5 varieties**: Chardonnay (CDY), Cabernet Franc (CFR), Cabernet Sauvignon (CSV), Sauvignon Blanc (SVB), Syrah (SYH)
- **YOLO-format bounding boxes** fetched live from the [WGISD GitHub repository](https://github.com/thsant/wgisd)
- Annotations rendered as canvas overlays with variety-specific color coding

### Reference

> Santos, T.T.; de Souza, L.L.; dos Santos, A.A.; Avila, S. *Grape detection, segmentation, and tracking using deep neural networks and three-dimensional association.* Computers and Electronics in Agriculture, 2020.

---

## Vegetation Indices

| Index | Formula | Application |
|---|---|---|
**Vigor**
| Index | Formula | Application |
|---|---|---|
| **NDVI** | (NIR − RED) / (NIR + RED) | General vegetation vigor |
| **EVI** | 2.5×(NIR−RED)/(NIR+6×RED−7.5×BLUE+1) | Enhanced VI, no saturation at high biomass |
| **SAVI** | 1.5×(NIR−RED)/(NIR+RED+0.5) | Soil-adjusted, ideal for young crops |
| **MSAVI** | (2×NIR+1 − √((2×NIR+1)²−8(NIR−RED))) / 2 | Modified soil-adjusted VI |

**Health**
| Index | Formula | Application |
|---|---|---|
| **NDRE** | (NIR − RedEdge) / (NIR + RedEdge) | Chlorophyll content, nitrogen status |
| **GNDVI** | (NIR − GREEN) / (NIR + GREEN) | Green NDVI, early stress detection |
| **TCARI** | 3×[(B5−B4) − 0.2×(B5−B3)×(B5/B4)] | Chlorophyll absorption |
| **CIre** | (NIR / RedEdge) − 1 | Chlorophyll Index, correlates with N |

**Water**
| Index | Formula | Application |
|---|---|---|
| **NDMI** | (NIR − SWIR) / (NIR + SWIR) | Moisture/water stress |
| **NDWI** | (GREEN − NIR) / (GREEN + NIR) | Water content in leaves |

**Soil**
| Index | Formula | Application |
|---|---|---|
| **BSI** | ((SWIR+RED)−(NIR+BLUE))/((SWIR+RED)+(NIR+BLUE)) | Bare soil detection |

**Visual**: True Color (B4-B3-B2 RGB), False Color (B8-B4-B3 NIR-R-G)

Sentinel-2 bands used: B2 (Blue, 490nm), B3 (Green, 560nm), B4 (Red, 665nm), B5 (Red Edge, 705nm), B8 (NIR, 842nm), B11 (SWIR, 1610nm).

---

## Technology Stack

**Frontend**

| Component | Library | Version | Purpose |
|---|---|---|---|
| Maps | [Leaflet](https://leafletjs.com/) | 1.9.4 | Interactive map rendering |
| Map editing | [Leaflet-Geoman](https://geoman.io/) | 2.16.0 | Draw, edit, delete polygons |
| Map comparison | [Leaflet Side-by-Side](https://github.com/digidem/leaflet-side-by-side) | 2.2.0 | Split-screen date comparison |
| Charts | [Chart.js](https://www.chartjs.org/) | 4.4.0 | Climate, genomic, and yield charts |
| Satellite | [Google Earth Engine JS API](https://developers.google.com/earth-engine/) | 0.1.395 | Sentinel-2 imagery processing |
| KMZ parsing | [JSZip](https://stuk.github.io/jszip/) | 3.10.1 | Unzip KMZ files in browser |
| KML parsing | [@mapbox/togeojson](https://github.com/mapbox/togeojson) | 0.16.0 | KML to GeoJSON conversion |
| Geocoding | [Nominatim](https://nominatim.openstreetmap.org/) | — | Reverse geocoding (OpenStreetMap) |

Frontend dependencies are loaded via CDN — no build step required.

**Backend (AI Assistant)**

| Component | Library | Version | Purpose |
|---|---|---|---|
| API framework | [FastAPI](https://fastapi.tiangolo.com/) | 0.115.0 | REST API for chat and conversations |
| AI model | [Anthropic Claude](https://www.anthropic.com/) | 0.40.0 | Conversational agent with tool use |
| Database | [Supabase](https://supabase.com/) | 2.10.0 | Conversation and message persistence |
| Earth Engine | [earthengine-api](https://pypi.org/project/earthengine-api/) | 1.6.15 | Server-side satellite data |
| PDF parsing | [pdfplumber](https://github.com/jsvine/pdfplumber) | 0.11.4 | Soil/foliar report extraction |
| Excel parsing | [openpyxl](https://openpyxl.readthedocs.io/) | 3.1.5 | Spreadsheet analysis uploads |

---

## Project Structure

```
agragent/
├── app.html                # Main SPA — all HTML, CSS, and JS
├── whatsapp-demo.html      # WhatsApp prototype for AgrAgent chatbot testing
├── landing.html            # Landing page
├── logo.png                # AgrAgent logo
├── poligono.kml            # Example field boundaries
├── README.md               # This file
├── LICENSE                 # MIT License
└── .gitignore
```

The AI backend (`agro-agent/`) is maintained separately:

```
agro-agent/
├── app/
│   ├── main.py             # FastAPI entry point (serves frontend + API)
│   ├── config.py           # Environment configuration
│   ├── database.py         # Supabase client
│   ├── agent/
│   │   ├── claude.py       # AgroAgent — agentic loop with Claude
│   │   ├── tools.py        # 6 agronomic tools
│   │   └── system_prompt.py
│   ├── routers/
│   │   ├── chat.py         # POST /api/chat, POST /api/chat/new
│   │   ├── conversations.py # CRUD conversations + messages
│   │   └── uploads.py      # File upload and parsing
│   ├── services/
│   │   ├── satellite.py    # GEE server-side queries
│   │   ├── climate.py      # Climate data service
│   │   ├── sentinel.py     # Sentinel-2 processing
│   │   └── document.py     # PDF/Excel parsing
│   └── models/
│       └── schemas.py      # Pydantic schemas
├── frontend/
│   └── index.html          # Original standalone chat UI
├── supabase/
│   └── schema.sql          # Database schema
├── requirements.txt
└── .env.example
```

---

## Author

**Francisco Altimiras**
- ORCID: [0000-0003-1992-8338](https://orcid.org/0000-0003-1992-8338)
- PhD Candidate in Computer Science, Pontificia Universidad Catolica de Valparaiso (PUCV), Chile
- Research focus: Computational crop monitoring using bioinformatics and machine learning

---

## Associated Publications

This platform is part of an ongoing research project. The following peer-reviewed publications provide the scientific foundation:

1. **Altimiras, F. et al.** *Transcriptome Data Analysis Applied to Grapevine Growth Stage Identification.* Agronomy, 14(3), 613, 2024.
   - DOI: [10.3390/agronomy14030613](https://www.mdpi.com/2073-4395/14/3/613)
   - Source of genomic data: RNA-seq pipeline, DEGs, phenological stage comparisons (Tables S1–S5)

2. **Altimiras, F. et al.** *A Computational Framework for Crop Yield Estimation and Phenological Monitoring.* In: Progress in Artificial Intelligence, EPIA 2024. Lecture Notes in Computer Science, vol. 15400. Springer, 2025.
   - DOI: [10.1007/978-3-031-80084-9_14](https://link.springer.com/chapter/10.1007/978-3-031-80084-9_14)

### Datasets

- **WGISD** — Wine Grape Instance Segmentation Dataset (Embrapa): [github.com/thsant/wgisd](https://github.com/thsant/wgisd)
  > Santos, T.T.; de Souza, L.L.; dos Santos, A.A.; Avila, S. *Grape detection, segmentation, and tracking using deep neural networks and three-dimensional association.* Computers and Electronics in Agriculture, 2020.

---

## Citation

If you use agragent in your research, please cite:

```bibtex
@software{agragent2026,
  author = {Altimiras, Francisco},
  title = {agragent: Computational Crop Monitoring Platform for Viticulture},
  year = {2026},
  url = {https://github.com/fjaltimiras/agragent},
  institution = {Pontificia Universidad Cat\'{o}lica de Valpara\'{i}so}
}

@article{altimiras2024bioinformatics,
  author = {Altimiras, Francisco and others},
  title = {Bioinformatics and Machine Learning for Grapevine Phenological Stage Classification},
  journal = {Agronomy},
  volume = {14},
  number = {3},
  pages = {613},
  year = {2024},
  doi = {10.3390/agronomy14030613}
}

@inproceedings{altimiras2025precision,
  author = {Altimiras, Francisco and others},
  title = {A Computational Framework for Crop Yield Estimation and Phenological Monitoring},
  booktitle = {Progress in Artificial Intelligence, EPIA 2024},
  series = {Lecture Notes in Computer Science},
  volume = {15400},
  publisher = {Springer},
  year = {2025},
  doi = {10.1007/978-3-031-80084-9\_14}
}
```

---

## License

This project is released under the [MIT License](LICENSE).

---

## Contributing

Contributions are welcome. Please open an issue first to discuss proposed changes. This project follows standard GitHub flow:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

---

## Acknowledgments

- **Embrapa** — [WGISD](https://github.com/thsant/wgisd) grape image dataset
- **Google Earth Engine** — Sentinel-2 satellite imagery
- **Open-Meteo** — Free historical weather API
- **OpenStreetMap / Nominatim** — Reverse geocoding
- **PUCV** — Pontificia Universidad Catolica de Valparaiso, School of Computer Engineering

---

*Developed by [Francisco Altimiras](https://orcid.org/0000-0003-1992-8338) — PhD Candidate, Computer Science, PUCV, Chile (2026)*
