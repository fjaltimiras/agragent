import httpx
import time
import math
import logging
from typing import Optional

logger = logging.getLogger(__name__)

TOKEN_URL = "https://services.sentinel-hub.com/auth/realms/main/protocol/openid-connect/token"
STATS_URL = "https://services.sentinel-hub.com/api/v1/statistics"


def _ndvi_interpretation(ndvi: float) -> str:
    """Return a human-readable interpretation of an NDVI value."""
    if ndvi < 0.1:
        return "Suelo desnudo o sin vegetación"
    elif ndvi < 0.2:
        return "Vegetación muy escasa o cultivo recién emergido"
    elif ndvi < 0.35:
        return "Estrés severo de vegetación — revisar urgente"
    elif ndvi < 0.5:
        return "Estrés moderado de vegetación"
    elif ndvi < 0.65:
        return "Vegetación en buen estado"
    elif ndvi < 0.8:
        return "Vegetación vigorosa y saludable"
    else:
        return "Vegetación excelente — máximo vigor"


def _bbox_from_point(lat: float, lng: float, radius_m: float):
    """
    Calculate a bounding box (min_lng, min_lat, max_lng, max_lat)
    from a center point and radius in meters.
    """
    # Degrees per meter (approximate)
    lat_deg = radius_m / 111320.0
    lng_deg = radius_m / (111320.0 * math.cos(math.radians(lat)))
    return [
        round(lng - lng_deg, 6),
        round(lat - lat_deg, 6),
        round(lng + lng_deg, 6),
        round(lat + lat_deg, 6),
    ]


class SentinelHubService:
    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0

    async def _get_token(self) -> str:
        """Fetch or return cached OAuth2 Bearer token from Sentinel Hub."""
        if self._token and time.time() < self._token_expiry - 60:
            return self._token

        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(TOKEN_URL, data=data)
            response.raise_for_status()
            token_data = response.json()

        self._token = token_data["access_token"]
        self._token_expiry = time.time() + token_data.get("expires_in", 3600)
        return self._token

    async def get_ndvi(
        self,
        lat: float,
        lng: float,
        radius_m: float = 500,
        date_from: str = "",
        date_to: str = "",
    ) -> dict:
        """
        Get NDVI and vegetation indices from Sentinel-2 via Sentinel Hub Statistical API.
        Returns mock data with a note if credentials are not configured.
        """
        if not self.client_id or not self.client_secret:
            return self._mock_ndvi_data(lat, lng, date_from, date_to)

        try:
            token = await self._get_token()
            bbox = _bbox_from_point(lat, lng, radius_m)

            evalscript = """
//VERSION=3
function setup() {
  return {
    input: [{
      bands: ["B04", "B08", "B02", "B03", "CLM"],
      units: "REFLECTANCE"
    }],
    output: [
      { id: "ndvi", bands: 1 },
      { id: "evi", bands: 1 },
      { id: "cloud", bands: 1 }
    ]
  };
}

function evaluatePixel(sample) {
  let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04 + 0.0001);
  let evi = 2.5 * (sample.B08 - sample.B04) / (sample.B08 + 6 * sample.B04 - 7.5 * sample.B02 + 1 + 0.0001);
  let cloud = sample.CLM;
  return {
    ndvi: [ndvi],
    evi: [evi],
    cloud: [cloud]
  };
}
"""

            payload = {
                "input": {
                    "bounds": {
                        "bbox": bbox,
                        "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
                    },
                    "data": [
                        {
                            "dataFilter": {
                                "timeRange": {
                                    "from": f"{date_from}T00:00:00Z",
                                    "to": f"{date_to}T23:59:59Z",
                                },
                                "maxCloudCoverage": 80,
                            },
                            "type": "sentinel-2-l2a",
                        }
                    ],
                },
                "aggregation": {
                    "timeRange": {
                        "from": f"{date_from}T00:00:00Z",
                        "to": f"{date_to}T23:59:59Z",
                    },
                    "aggregationInterval": {"of": "P1D"},
                    "evalscript": evalscript,
                    "resx": 10,
                    "resy": 10,
                },
                "calculations": {
                    "ndvi": {
                        "statistics": {
                            "default": {
                                "percentiles": {"k": [25, 50, 75]},
                                "noDataPixels": True,
                            }
                        }
                    },
                    "evi": {
                        "statistics": {
                            "default": {
                                "percentiles": {"k": [50]},
                                "noDataPixels": True,
                            }
                        }
                    },
                    "cloud": {
                        "statistics": {
                            "default": {"noDataPixels": True}
                        }
                    },
                },
            }

            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(STATS_URL, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()

            # Parse the statistics response
            data_items = result.get("data", [])
            if not data_items:
                return {
                    "error": False,
                    "message": "No se encontraron imágenes sin nubes para el período seleccionado.",
                    "latitude": lat,
                    "longitude": lng,
                    "date_range": {"from": date_from, "to": date_to},
                }

            # Use the most recent valid data point
            ndvi_values = []
            evi_values = []
            cloud_values = []

            for item in data_items:
                outputs = item.get("outputs", {})
                ndvi_stats = outputs.get("ndvi", {}).get("bands", {}).get("B0", {}).get("stats", {})
                evi_stats = outputs.get("evi", {}).get("bands", {}).get("B0", {}).get("stats", {})
                cloud_stats = outputs.get("cloud", {}).get("bands", {}).get("B0", {}).get("stats", {})

                if ndvi_stats.get("mean") is not None:
                    ndvi_values.append(ndvi_stats)
                if evi_stats.get("mean") is not None:
                    evi_values.append(evi_stats)
                if cloud_stats.get("mean") is not None:
                    cloud_values.append(cloud_stats.get("mean", 0))

            if not ndvi_values:
                return {
                    "error": False,
                    "message": "No hay datos NDVI válidos (posiblemente cobertura de nubes alta) para el período.",
                    "latitude": lat,
                    "longitude": lng,
                    "date_range": {"from": date_from, "to": date_to},
                }

            latest_ndvi = ndvi_values[-1]
            latest_evi = evi_values[-1] if evi_values else {}
            avg_cloud = round(sum(cloud_values) / len(cloud_values) * 100, 1) if cloud_values else None

            mean_ndvi = round(latest_ndvi.get("mean", 0), 4)
            min_ndvi = round(latest_ndvi.get("min", 0), 4)
            max_ndvi = round(latest_ndvi.get("max", 0), 4)
            mean_evi = round(latest_evi.get("mean", 0), 4) if latest_evi else None

            return {
                "mean_ndvi": mean_ndvi,
                "min_ndvi": min_ndvi,
                "max_ndvi": max_ndvi,
                "mean_evi": mean_evi,
                "cloud_coverage_pct": avg_cloud,
                "date_range": {"from": date_from, "to": date_to},
                "interpretation": _ndvi_interpretation(mean_ndvi),
                "bbox_analyzed": bbox,
                "radius_m": radius_m,
                "data_source": "Sentinel-2 L2A via Sentinel Hub",
                "images_analyzed": len(ndvi_values),
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"Sentinel Hub API error: {e.response.status_code} - {e.response.text}")
            return {
                "error": True,
                "message": f"Error al consultar Sentinel Hub: HTTP {e.response.status_code}",
                "latitude": lat,
                "longitude": lng,
            }
        except Exception as e:
            logger.error(f"Sentinel Hub unexpected error: {str(e)}")
            return {
                "error": True,
                "message": f"Error al obtener datos satelitales: {str(e)}",
                "latitude": lat,
                "longitude": lng,
            }

    def _mock_ndvi_data(self, lat: float, lng: float, date_from: str, date_to: str) -> dict:
        """Return mock NDVI data when Sentinel Hub is not configured."""
        mock_ndvi = 0.62
        return {
            "mean_ndvi": mock_ndvi,
            "min_ndvi": 0.45,
            "max_ndvi": 0.78,
            "mean_evi": 0.48,
            "cloud_coverage_pct": 15.0,
            "date_range": {"from": date_from, "to": date_to},
            "interpretation": _ndvi_interpretation(mock_ndvi),
            "data_source": "DATOS DE EJEMPLO — Sentinel Hub no está configurado",
            "note": (
                "Estos son datos de ejemplo. Para obtener datos reales de imágenes satelitales "
                "Sentinel-2, configura las variables SENTINEL_CLIENT_ID y SENTINEL_CLIENT_SECRET "
                "en el archivo .env. Regístrate gratis en https://www.sentinel-hub.com/"
            ),
            "mock": True,
            "latitude": lat,
            "longitude": lng,
        }
