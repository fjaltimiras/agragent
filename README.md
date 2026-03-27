# agragent — Computational Crop Monitoring Platform for Viticulture

**agragent** is an open-source, browser-based precision agriculture platform designed for real-time monitoring of grapevine production systems. It integrates satellite remote sensing, climate analytics, genomic data visualization, and computer vision into a single web application — requiring no backend, no installation, and no API keys for core functionality.

Developed as part of a PhD research project in Computer Science at the Pontificia Universidad Católica de Valparaíso (PUCV), Chile, focusing on computational crop monitoring using bioinformatics and machine learning.

---

## Table of Contents

- [Features](#features)
- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Data Sources](#data-sources)
- [Getting Started](#getting-started)
- [KML/KMZ Support](#kmlkmz-support)
- [Google Earth Engine Integration](#google-earth-engine-integration)
- [Climate Data Pipeline](#climate-data-pipeline)
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
| **Dashboard** | Dynamic overview: location, field area, climate summary, alerts — all derived from the user's polygon |
| **Satellite Maps** | Sentinel-2 imagery via Google Earth Engine with 6 vegetation indices, scene browsing, and temporal comparison |
| **Climate Data** | Real-time climate analytics from Open-Meteo — temperature, precipitation, humidity, solar radiation, evapotranspiration, GDD, chill hours, frost, heat waves |
| **Genomic Analysis** | Real RNA-seq DEG data from Altimiras et al. (2024) — 3,603 DEGs across 8 phenological stages of *Vitis vinifera* |
| **Image Analysis** | Integration with the WGISD dataset (Embrapa) — 300+ grape cluster images with YOLO bounding box annotations |
| **Yield Prediction** | Extra Trees Regressor model output with confidence intervals and feature importance |
| **References** | Author info, ORCID, associated publications with DOIs, dataset citations |

### Dynamic Dashboard

The dashboard starts empty and automatically populates when the user uploads a KML/KMZ file or draws a polygon:

- **Location**: reverse-geocoded name from polygon centroid (via OpenStreetMap Nominatim)
- **Field area**: computed from polygon coordinates (shoelace formula)
- **Climate summary**: real temperature, humidity, precipitation, ET₀, solar radiation, GDD, chill hours
- **Active alerts**: generated from actual climate data (frost, heat waves, drought, low GDD)
- **Temperature chart**: monthly min/max from Open-Meteo
- **Polygon table**: list of all loaded polygons with centroids

### Satellite Analysis

- **Median Composite**: cloud-free composite from all Sentinel-2 scenes in a date range
- **Scene Browser**: browse individual acquisitions with cloud cover percentage
- **Date Comparison**: split-screen slider comparing two acquisition dates
- **Vegetation Indices**: NDVI, NDRE, MSAVI, TCARI, True Color RGB, False Color (NIR-R-G)
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

### Field Management

- Upload KML/KMZ files to define field boundaries
- Draw, edit, and delete polygons directly on the map (Leaflet-Geoman)
- Export polygons as KML
- Multi-polygon support
- Location auto-detection via reverse geocoding

---

## How It Works

1. **Open the app** and navigate to Satellite Maps
2. **Upload a KML/KMZ** file or **draw a polygon** on the map
3. The app automatically:
   - Detects the location name via reverse geocoding
   - Fetches climate data from Open-Meteo for that location
   - Updates the Dashboard, Climate, and all sections with real data
4. **Connect to Google Earth Engine** (optional) to view Sentinel-2 satellite imagery clipped to your polygon
5. Explore genomic data, grape images, and yield predictions

---

## Architecture

agragent is a **zero-dependency single-page application** (SPA) — the entire platform is contained in one `index.html` file. This design prioritizes:

- **Portability**: runs on any machine with a browser, no Node.js/Python backend required
- **Reproducibility**: a single file can be shared, archived, or embedded in academic publications
- **Offline capability**: core UI works without internet; only API calls require connectivity

```
┌──────────────────────────────────────────────────────┐
│                      Browser                          │
│                                                       │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────┐ │
│  │ Leaflet  │  │ Chart.js │  │ Earth Engine JS    │ │
│  │ Map +    │  │ 9 Charts │  │ API (OAuth 2.0)    │ │
│  │ Geoman   │  │          │  │                    │ │
│  └────┬─────┘  └────┬─────┘  └──────┬─────────────┘ │
│       │              │               │                │
│       └──────────────┼───────────────┘                │
│                      │                                │
│              index.html (SPA)                         │
└──────────────────────┬────────────────────────────────┘
                       │
       ┌───────────────┼───────────────┐
       │               │               │
  Open-Meteo      Google Earth    Nominatim
  Archive API     Engine API      Geocoding
  (climate)       (Sentinel-2)    (location)
       │
   WGISD/GitHub
   (grape images)
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

### Quick Start

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

### Google Earth Engine (Optional)

To enable satellite imagery:

1. Create a Google Cloud project at [console.cloud.google.com](https://console.cloud.google.com)
2. Enable the **Earth Engine API**
3. Register your project for Earth Engine (noncommercial) at the [EE registration page](https://code.earthengine.google.com/register)
4. Configure **OAuth 2.0 credentials** (Web application type)
5. Add `http://localhost:8080` as an authorized JavaScript origin
6. Add your email as a **test user** in OAuth consent screen → Audience
7. In the app, enter your **Client ID** and **Project ID**, then click Connect

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

> Altimiras, F. et al. *Bioinformatics and Machine Learning for Grapevine Phenological Stage Classification.* Agronomy, 14(3), 613, 2024.

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
| **NDVI** | (NIR - Red) / (NIR + Red) | General vegetation vigor |
| **NDRE** | (NIR - RedEdge) / (NIR + RedEdge) | Chlorophyll content, nitrogen status |
| **MSAVI** | (2×NIR + 1 - sqrt((2×NIR+1)² - 8×(NIR-Red))) / 2 | Soil-adjusted vegetation index |
| **TCARI** | 3×[(RedEdge - Red) - 0.2×(RedEdge - Green)×(RedEdge/Red)] | Chlorophyll absorption |
| **True Color** | B4-B3-B2 (RGB) | Natural color composite |
| **False Color** | B8-B4-B3 (NIR-R-G) | Vegetation highlighted in red |

Sentinel-2 bands used: B2 (Blue, 490nm), B3 (Green, 560nm), B4 (Red, 665nm), B5 (Red Edge, 705nm), B8 (NIR, 842nm).

---

## Technology Stack

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

All dependencies are loaded via CDN — no build step required.

---

## Project Structure

```
agragent/
├── index.html      # Complete SPA — all HTML, CSS, and JS
├── Agrifrut.kml    # Example field boundaries (Los Angeles, Chile)
├── README.md       # This file
├── LICENSE         # MIT License
└── .gitignore
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

1. **Altimiras, F. et al.** *Bioinformatics and Machine Learning for Grapevine Phenological Stage Classification: A Comparative Study of RNA-seq Differential Expression Analysis.* Agronomy, 14(3), 613, 2024.
   - DOI: [10.3390/agronomy14030613](https://www.mdpi.com/2073-4395/14/3/613)
   - Source of genomic data: RNA-seq pipeline, DEGs, phenological stage comparisons (Tables S1–S5)

2. **Altimiras, F. et al.** *Towards Precision Viticulture: Computational Approaches for Grape Production Monitoring.* In: Progress in Artificial Intelligence, EPIA 2024. Lecture Notes in Computer Science, vol. 15400. Springer, 2025.
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
  title = {Towards Precision Viticulture: Computational Approaches for Grape Production Monitoring},
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
