"""
Google Earth Engine satellite service.
Provides NDVI, EVI and other vegetation indices from Sentinel-2 and Landsat.
Requires a GEE service account JSON key at the path configured in settings.
Falls back to mock data if credentials are not configured.
"""
import asyncio
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy GEE initialization — only runs once
_gee_initialized = False
_gee_error: Optional[str] = None


def _init_gee(credentials_path: Optional[str], project_id: Optional[str]) -> Optional[str]:
    """
    Initialize Earth Engine with service account credentials.
    Returns None on success, error message on failure.
    """
    global _gee_initialized, _gee_error
    if _gee_initialized:
        return _gee_error
    try:
        import ee
        if credentials_path:
            import json
            with open(credentials_path) as f:
                creds_data = json.load(f)
            service_account = creds_data.get("client_email")
            credentials = ee.ServiceAccountCredentials(service_account, credentials_path)
            ee.Initialize(credentials, project=project_id)
        else:
            # Try application default credentials (useful for local dev with gcloud auth)
            ee.Initialize(project=project_id)
        _gee_initialized = True
        _gee_error = None
        logger.info("Google Earth Engine initialized successfully")
        return None
    except Exception as e:
        _gee_error = str(e)
        _gee_initialized = False
        logger.warning(f"GEE initialization failed: {e}")
        return str(e)


def _ndvi_interpretation(ndvi: float) -> str:
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


def _get_ndvi_sync(
    lat: float,
    lng: float,
    radius_m: float,
    date_from: str,
    date_to: str,
    source: str = "sentinel2",
) -> dict:
    """
    Blocking GEE call — run in executor to avoid blocking the event loop.
    source: 'sentinel2' | 'landsat'
    """
    import ee

    point = ee.Geometry.Point([lng, lat])
    region = point.buffer(radius_m)

    if source == "landsat":
        # Landsat 8/9 Collection 2 Level-2
        collection_id = "LANDSAT/LC09/C02/T1_L2"
        nir_band, red_band = "SR_B5", "SR_B4"
        green_band, blue_band = "SR_B3", "SR_B2"
        cloud_property = "CLOUD_COVER"
    else:
        # Sentinel-2 Surface Reflectance Harmonized
        collection_id = "COPERNICUS/S2_SR_HARMONIZED"
        nir_band, red_band = "B8", "B4"
        green_band, blue_band = "B3", "B2"
        cloud_property = "CLOUDY_PIXEL_PERCENTAGE"

    def add_ndvi(img):
        ndvi = img.normalizedDifference([nir_band, red_band]).rename("NDVI")
        evi = (
            img.expression(
                "2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))",
                {"NIR": img.select(nir_band), "RED": img.select(red_band), "BLUE": img.select(blue_band)},
            )
            .rename("EVI")
        )
        return img.addBands([ndvi, evi])

    collection = (
        ee.ImageCollection(collection_id)
        .filterDate(date_from, date_to)
        .filterBounds(region)
        .filter(ee.Filter.lt(cloud_property, 30))
        .map(add_ndvi)
    )

    count = collection.size().getInfo()
    if count == 0:
        # Relax cloud filter and try again
        collection = (
            ee.ImageCollection(collection_id)
            .filterDate(date_from, date_to)
            .filterBounds(region)
            .filter(ee.Filter.lt(cloud_property, 70))
            .map(add_ndvi)
        )
        count = collection.size().getInfo()

    if count == 0:
        return {
            "error": False,
            "message": "No se encontraron imágenes para el período y zona indicados. Prueba ampliar el rango de fechas.",
            "latitude": lat,
            "longitude": lng,
            "date_range": {"from": date_from, "to": date_to},
            "images_found": 0,
        }

    # Use mosaic of the period (median composite for robustness)
    composite = collection.select(["NDVI", "EVI"]).median()

    stats = composite.reduceRegion(
        reducer=ee.Reducer.mean()
            .combine(ee.Reducer.min(), sharedInputs=True)
            .combine(ee.Reducer.max(), sharedInputs=True)
            .combine(ee.Reducer.stdDev(), sharedInputs=True),
        geometry=region,
        scale=10,
        maxPixels=1e9,
        bestEffort=True,
    ).getInfo()

    mean_ndvi = stats.get("NDVI_mean")
    min_ndvi = stats.get("NDVI_min")
    max_ndvi = stats.get("NDVI_max")
    std_ndvi = stats.get("NDVI_stdDev")
    mean_evi = stats.get("EVI_mean")

    if mean_ndvi is None:
        return {
            "error": False,
            "message": "No se pudieron calcular estadísticas NDVI para esta zona.",
            "latitude": lat,
            "longitude": lng,
            "date_range": {"from": date_from, "to": date_to},
        }

    mean_ndvi = round(mean_ndvi, 4)
    return {
        "mean_ndvi": mean_ndvi,
        "min_ndvi": round(min_ndvi, 4) if min_ndvi is not None else None,
        "max_ndvi": round(max_ndvi, 4) if max_ndvi is not None else None,
        "std_ndvi": round(std_ndvi, 4) if std_ndvi is not None else None,
        "mean_evi": round(mean_evi, 4) if mean_evi is not None else None,
        "interpretation": _ndvi_interpretation(mean_ndvi),
        "date_range": {"from": date_from, "to": date_to},
        "images_used": count,
        "composite_method": "mediana del período",
        "radius_m": radius_m,
        "source": "Sentinel-2 L2A" if source == "sentinel2" else "Landsat 9 C2",
        "data_source": "Google Earth Engine",
        "latitude": lat,
        "longitude": lng,
    }


class EarthEngineService:
    def __init__(
        self,
        credentials_path: Optional[str] = None,
        project_id: Optional[str] = None,
    ):
        self.credentials_path = credentials_path
        self.project_id = project_id

    def _ensure_initialized(self) -> Optional[str]:
        return _init_gee(self.credentials_path, self.project_id)

    async def get_ndvi(
        self,
        lat: float,
        lng: float,
        radius_m: float = 500,
        date_from: str = "",
        date_to: str = "",
        source: str = "sentinel2",
    ) -> dict:
        """
        Async wrapper for GEE NDVI query.
        Returns mock data with a note if GEE is not configured.
        """
        # Auto-fill dates if not provided (last 30 days)
        if not date_from or not date_to:
            today = datetime.now(timezone.utc)
            date_to = today.strftime("%Y-%m-%d")
            date_from = (today - timedelta(days=30)).strftime("%Y-%m-%d")

        err = self._ensure_initialized()
        if err:
            return self._mock_data(lat, lng, date_from, date_to, err)

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: _get_ndvi_sync(lat, lng, radius_m, date_from, date_to, source),
            )
            return result
        except Exception as e:
            logger.error(f"GEE NDVI error: {e}")
            return {
                "error": True,
                "message": f"Error al consultar Google Earth Engine: {str(e)}",
                "latitude": lat,
                "longitude": lng,
            }

    def _mock_data(self, lat: float, lng: float, date_from: str, date_to: str, error: str) -> dict:
        mock_ndvi = 0.62
        return {
            "mean_ndvi": mock_ndvi,
            "min_ndvi": 0.45,
            "max_ndvi": 0.78,
            "std_ndvi": 0.08,
            "mean_evi": 0.48,
            "interpretation": _ndvi_interpretation(mock_ndvi),
            "date_range": {"from": date_from, "to": date_to},
            "data_source": "DATOS DE EJEMPLO — Google Earth Engine no está configurado",
            "note": (
                "Para datos satelitales reales, configura GEE_CREDENTIALS_PATH y GEE_PROJECT_ID "
                "en el archivo .env con las credenciales de tu Service Account de Google Cloud."
            ),
            "mock": True,
            "gee_error": error,
            "latitude": lat,
            "longitude": lng,
        }
