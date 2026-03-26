# agragent — Computational Crop Monitoring Platform for Viticulture

**agragent** is an open-source, browser-based precision agriculture platform designed for real-time monitoring of grapevine production systems. It integrates satellite remote sensing, climate analytics, genomic data visualization, and computer vision into a single web application — requiring no backend, no installation, and no API keys for core functionality.

Developed as part of a PhD research project in Computer Science at the Pontificia Universidad Católica de Valparaíso (PUCV), Chile, focusing on computational crop monitoring using bioinformatics and machine learning.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Data Sources](#data-sources)
- [Getting Started](#getting-started)
- [KML/KMZ Support](#kmlkmz-support)
- [Google Earth Engine Integration](#google-earth-engine-integration)
- [Climate Data Pipeline](#climate-data-pipeline)
- [Image Analysis — WGISD Dataset](#image-analysis--wgisd-dataset)
- [Vegetation Indices](#vegetation-indices)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Citation](#citation)
- [License](#license)

---

## Features

| Module | Description |
|---|---|
| **Dashboard** | Overview KPIs: NDVI trends, active alerts, growth stage, vineyard area |
| **Satellite Maps** | Sentinel-2 imagery via Google Earth Engine with 6 vegetation indices, scene browsing, and temporal comparison |
| **Climate Data** | Real-time climate analytics from Open-Meteo Archive API — temperature, precipitation, GDD accumulation |
| **Genomic Analysis** | Vitis vinifera gene expression heatmaps, SNP variant explorer, metabolic pathway visualization |
| **Image Analysis** | Integration with the WGISD dataset (Embrapa) — 300+ grape cluster images with YOLO bounding box annotations |
| **Yield Prediction** | Extra Trees Regressor model output with confidence intervals and feature importance |

### Satellite Analysis Capabilities

- **Median Composite**: Cloud-free composite from all available Sentinel-2 scenes in a date range
- **Scene Browser**: Browse individual Sentinel-2 acquisitions with cloud cover percentage
- **Date Comparison**: Split-screen slider (side-by-side) comparing two different acquisition dates
- **Vegetation Indices**: NDVI, NDRE, MSAVI, TCARI, True Color RGB, False Color (NIR-R-G)
- **Cloud Masking**: Automatic QA60-based cloud and cirrus removal
- **Polygon Clipping**: Imagery rendered only within field boundaries for fast loading

### Climate Analytics

- Monthly temperature profiles (min/max) computed from daily observations
- Monthly precipitation totals with drought highlighting
- Growing Degree Days (GDD, base 10°C) accumulation curve from September through harvest
- Automatic KPI computation: total GDD, dry months count, last frost date, heat stress days (>35°C)
- Dynamic alerts based on real climate conditions

### Field Management

- Upload KML/KMZ files to define field boundaries
- Draw, edit, and delete polygons directly on the map using Leaflet-Geoman
- Export current polygons as GeoJSON
- Multi-sector support (e.g., Sector 1, Sector 2 from a single KML)

---

## Architecture

agragent is a **zero-dependency single-page application** (SPA) — the entire platform is contained in one `index.html` file (~145 KB). This design choice prioritizes:

- **Portability**: runs on any machine with a browser, no Node.js/Python backend required
- **Reproducibility**: a single file can be shared, archived, or embedded in academic publications
- **Offline capability**: core UI works without internet; only API calls require connectivity

```
┌─────────────────────────────────────────────────┐
│                   Browser                        │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐ │
│  │ Leaflet  │  │ Chart.js │  │ Earth Engine  │ │
│  │ Map +    │  │ Climate  │  │ JS API        │ │
│  │ Geoman   │  │ Charts   │  │ (OAuth 2.0)   │ │
│  └────┬─────┘  └────┬─────┘  └──────┬────────┘ │
│       │              │               │           │
│       └──────────────┼───────────────┘           │
│                      │                           │
│              index.html (SPA)                    │
└──────────────────────┬───────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         │             │             │
    Open-Meteo    Google Earth   WGISD/GitHub
    Archive API   Engine API     (Embrapa)
```

---

## Data Sources

| Source | Type | Access | Usage |
|---|---|---|---|
| [Sentinel-2 SR Harmonized](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED) | Satellite imagery (10m) | Google Earth Engine | Vegetation indices, RGB composites |
| [Open-Meteo Archive API](https://open-meteo.com/en/docs/historical-weather-api) | Historical weather | Free, no API key | Temperature, precipitation, GDD |
| [WGISD](https://github.com/thsant/wgisd) (Embrapa) | Grape cluster images | Public dataset | Object detection annotations |
| [Agrifrut.kml](./Agrifrut.kml) | Field boundaries | Local file | Polygon geometry for analysis |

### Study Site

The default study site is a vineyard located in **Los Angeles, Biobio Region, Chile** (approximately 38.34°S, 73.29°W), managed by Patricia Medina. The KML file defines two sectors with polygon boundaries used for satellite clipping and climate data extraction.

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

> **Note**: A local HTTP server is required (not `file://`) because the app fetches the KML file and makes API calls that require proper CORS handling.

### Google Earth Engine (Optional)

To enable satellite imagery:

1. Create a Google Cloud project at [console.cloud.google.com](https://console.cloud.google.com)
2. Enable the Earth Engine API
3. Configure OAuth 2.0 credentials (Web application type)
4. Add `http://localhost:8080` as an authorized JavaScript origin
5. Register your project for Earth Engine at [code.earthengine.google.com/register](https://code.earthengine.google.com/register)
6. Enter your Client ID and Project ID in the app's Satellite Maps section

---

## KML/KMZ Support

agragent supports loading field boundaries from standard KML and KMZ files:

- **KML**: parsed directly using the DOMParser API and [@mapbox/togeojson](https://github.com/mapbox/togeojson)
- **KMZ**: unzipped in-browser using [JSZip](https://stuk.github.io/jszip/), then KML extracted and parsed
- Polygon coordinates are stored for GEE geometry clipping (`ee.Geometry.Polygon` / `ee.Geometry.MultiPolygon`)
- Supports multi-polygon KML files (multiple `<Placemark>` elements)

---

## Google Earth Engine Integration

The app connects to GEE via the [Earth Engine JavaScript API](https://developers.google.com/earth-engine/guides/npm_install) using OAuth 2.0 browser authentication.

### Image Processing Pipeline

```
COPERNICUS/S2_SR_HARMONIZED
  → filterDate(startDate, endDate)
  → filterBounds(polygonGeometry)
  → filter(CLOUDY_PIXEL_PERCENTAGE < threshold)
  → map(QA60 cloud mask)
  → median() or select(specific date)
  → clip(polygonGeometry)
  → compute vegetation index
  → getMap({min, max, palette})
  → L.tileLayer(tileUrl)
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

### Data Flow

1. **Centroid extraction**: compute polygon centroid from loaded KML coordinates
2. **API request**: fetch daily `temperature_2m_max`, `temperature_2m_min`, `precipitation_sum` for the growing season (April–March)
3. **Monthly aggregation**: group daily values by month, compute averages (temperature) and sums (precipitation)
4. **GDD computation**: Growing Degree Days with base temperature 10°C: `GDD = max(0, (Tmax + Tmin)/2 - 10)`, accumulated from September through March
5. **KPI derivation**: total GDD, dry months (<30mm), last frost date (Tmin <= 0°C), heat stress days (Tmax > 35°C)

### Season Definition

The agricultural season follows the Southern Hemisphere viticulture calendar:
- **Full season**: April (year N) through March (year N+1)
- **Growing season** (GDD accumulation): September through March
- **Dormancy**: April through August

---

## Image Analysis — WGISD Dataset

The Image Analysis module integrates the **Wine Grape Instance Segmentation Dataset** (WGISD) from Embrapa:

- **300+ images** of grape clusters in field conditions
- **5 varieties**: Chardonnay (CDY), Cabernet Franc (CFR), Cabernet Sauvignon (CSV), Sauvignon Blanc (SVB), Syrah (SYH)
- **YOLO-format bounding boxes** fetched from the [WGISD GitHub repository](https://github.com/thsant/wgisd)
- Annotations rendered as canvas overlays with variety-specific color coding

### Reference

> Santos, T.T.; de Souza, L.L.; dos Santos, A.A.; Avila, S. *Grape detection, segmentation, and tracking using deep neural networks and three-dimensional association*. Computers and Electronics in Agriculture, 2020.

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
| Charts | [Chart.js](https://www.chartjs.org/) | 4.4.0 | Climate and yield charts |
| Satellite | [Google Earth Engine JS API](https://developers.google.com/earth-engine/) | 0.1.395 | Sentinel-2 imagery |
| KMZ parsing | [JSZip](https://stuk.github.io/jszip/) | 3.10.1 | Unzip KMZ files in browser |
| KML parsing | [@mapbox/togeojson](https://github.com/mapbox/togeojson) | 0.16.0 | KML to GeoJSON conversion |

All dependencies are loaded via CDN — no build step required.

---

## Project Structure

```
agragent/
├── index.html      # Complete SPA (~145 KB) — all HTML, CSS, and JS
├── Agrifrut.kml    # Default field boundaries (2 sectors, Los Angeles, Chile)
├── README.md       # This file
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
   - Genomic data in the app (DEGs, phenological stages, RNA-seq pipeline) comes from this study

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
- **PUCV** — Pontificia Universidad Catolica de Valparaiso, School of Computer Engineering

---

*Developed by [Francisco Altimiras](https://orcid.org/0000-0003-1992-8338) — PhD Candidate, Computer Science, PUCV, Chile (2026)*
