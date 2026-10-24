# Third-party notices

agragent's own code is licensed as described in [LICENSING.md](LICENSING.md). This file lists the
third-party software and data it uses, with their licenses.

## Bundled in this repository

### SL2P neural-network coefficients (LEAF-Toolbox)

`assets/indices/sl2p-weights.js` contains coefficients transcribed from the LEAF-Toolbox reference
implementation of the ESA SL2P biophysical processor
(<https://github.com/rfernand387/LEAF-Toolbox>), distributed under the following license:

```
MIT License

Copyright (c) Her Majesty the Queen in Right of Canada, as represented by the Treasury Board of Canada Secretariat, 2018

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Loaded at run time from public CDNs (not redistributed here)

| Library | Version | License |
|---|---|---|
| [Leaflet](https://leafletjs.com) | 1.9.4 | BSD-2-Clause |
| [Leaflet-Geoman Free](https://github.com/geoman-io/leaflet-geoman) | 2.16.0 | MIT |
| [leaflet-side-by-side](https://github.com/digidem/leaflet-side-by-side) | commit `cd74619` | MIT |
| [@mapbox/togeojson](https://github.com/mapbox/togeojson) | 0.16.0 | BSD-2-Clause |
| [@mapbox/shp-write](https://github.com/mapbox/shp-write) | 0.4.3 | BSD-3-Clause |
| [JSZip](https://stuk.github.io/jszip/) | 3.10.1 | MIT (dual MIT / GPL-3.0; used under MIT) |
| [Apache ECharts](https://echarts.apache.org) | 5.6.0 | Apache-2.0 |
| [supabase-js](https://github.com/supabase/supabase-js) | 2.117.2 | MIT |
| Google Identity Services | — | Google APIs Terms of Service |

The API functions in `api/` depend on `@supabase/supabase-js` (MIT), installed through npm.

## External services and data

These are queried at run time. They are not part of this repository and keep their own terms:

| Service | Use | Terms |
|---|---|---|
| Google Earth Engine, Copernicus Sentinel-2 SR Harmonized | satellite imagery and indices | Earth Engine terms of service; Copernicus data are free and open |
| AlphaEarth Foundations Satellite Embedding (`GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`) | two exploratory map layers | CC BY 4.0. Attribution: "The AlphaEarth Foundations Satellite Embedding dataset is produced by Google and Google DeepMind." |
| Esri World Imagery, Esri World Boundaries and Places, OpenStreetMap | base map tiles | Esri terms of use; OSM data © OpenStreetMap contributors, ODbL |
| Open-Meteo (ERA5 archive and forecast) | climate | CC BY 4.0 |
| Nominatim | geocoding | OSM Nominatim usage policy; ODbL |
| OpenAlex | scientific literature | CC0 |
| AGRIS (FAO) | agricultural literature | FAO terms of use |
| FAOSTAT | crop statistics | CC BY-NC-SA 3.0 IGO |
| Biblioteca Digital INIA Chile | technical literature metadata | INIA terms of use |
| LLM inference endpoints (Cerebras, Groq) | conversational agent | each provider's terms |
