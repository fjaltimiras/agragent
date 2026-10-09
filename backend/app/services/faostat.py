"""
Servicio FAOSTAT — AgrAgent
Estadísticas agrícolas globales de la FAO (producción, rendimiento, superficie).

FAOSTAT: https://www.fao.org/faostat/en/
- 245 países desde 1961
- Sin autenticación requerida
- Dominio QCL: Crops and livestock products
"""
import ssl
import urllib.request
import urllib.parse
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

BASE_URL = "https://fenixservices.fao.org/faostat/api/v1"

# Códigos de área comunes
AREA_CODES = {
    "chile": "228", "argentina": "9", "peru": "180", "brasil": "21", "brazil": "21",
    "mexico": "138", "colombia": "44", "china": "41", "usa": "231",
    "united states": "231", "india": "100", "world": "5000",
    "south america": "912", "latin america": "912",
}

# Elementos disponibles en QCL
ELEMENTS = {
    "produccion": "5510", "production": "5510",
    "rendimiento": "5419", "yield": "5419",
    "superficie": "5312", "area": "5312", "area harvested": "5312",
}

try:
    import certifi
    _ctx = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _ctx = ssl.create_default_context()


def _get(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "AgrAgent/1.0 (mailto:agragent@agragent.com)"}
    )
    with urllib.request.urlopen(req, timeout=20, context=_ctx) as r:
        return json.loads(r.read())


def _search_item_code(crop_name: str) -> Optional[str]:
    """Busca el código de cultivo en FAOSTAT por nombre."""
    try:
        url = f"{BASE_URL}/en/item/QCL?output_type=json"
        data = _get(url)
        crop_lower = crop_name.lower()
        items = data.get("data") or []
        # Búsqueda exacta primero
        for item in items:
            if item.get("Item", "").lower() == crop_lower:
                return item.get("Item Code")
        # Búsqueda parcial
        for item in items:
            if crop_lower in item.get("Item", "").lower():
                return item.get("Item Code")
        return None
    except Exception as e:
        logger.warning(f"FAOSTAT item search error: {e}")
        return None


def get_faostat_data(
    crop: str,
    country: str = "world",
    element: str = "yield",
    year_from: int = 2015,
    year_to: int = 2023,
) -> dict:
    """
    Obtiene estadísticas de producción agrícola de FAOSTAT (FAO).

    Args:
        crop: nombre del cultivo en inglés (ej: 'grapes', 'wheat', 'maize', 'tomatoes')
        country: país o región en inglés/español (ej: 'chile', 'world', 'argentina')
        element: métrica deseada — 'yield' (rendimiento hg/ha), 'production' (toneladas),
                 'area' (superficie cosechada ha)
        year_from: año inicial del rango (default 2015)
        year_to: año final del rango (default 2023)

    Returns:
        dict con serie temporal de estadísticas, promedio y unidad
    """
    # Resolver código de área
    area_code = AREA_CODES.get(country.lower().strip())
    if not area_code:
        # Intentar búsqueda dinámica de área
        area_code = "5000"  # fallback a World
        logger.info(f"País '{country}' no encontrado, usando World (5000)")

    # Resolver elemento
    element_code = ELEMENTS.get(element.lower().strip(), "5419")  # default: yield

    # Buscar código de cultivo
    item_code = _search_item_code(crop)
    if not item_code:
        return {
            "error": f"Cultivo '{crop}' no encontrado en FAOSTAT. Prueba con el nombre en inglés (ej: 'grapes', 'wheat', 'maize').",
            "crop": crop,
            "results": [],
        }

    params = {
        "area": area_code,
        "element": element_code,
        "item": item_code,
        "year": f"{year_from},{year_to}",
        "show_codes": "True",
        "show_unit": "True",
        "show_flags": "False",
        "null_values": "False",
        "output_type": "json",
    }

    url = f"{BASE_URL}/en/data/QCL?{urllib.parse.urlencode(params)}"

    try:
        data = _get(url)
    except Exception as e:
        logger.error(f"FAOSTAT data error: {e}")
        return {
            "error": f"Error al consultar FAOSTAT: {e}",
            "crop": crop,
            "country": country,
            "results": [],
        }

    rows = data.get("data") or []
    if not rows:
        return {
            "query": {"crop": crop, "country": country, "element": element},
            "results": [],
            "note": "Sin datos disponibles para esta combinación cultivo/país/período.",
        }

    unit = rows[0].get("Unit", "") if rows else ""
    series = [
        {"year": int(r.get("Year", 0)), "value": float(r.get("Value", 0))}
        for r in rows if r.get("Value") is not None
    ]
    series.sort(key=lambda x: x["year"])

    values = [s["value"] for s in series]
    avg = round(sum(values) / len(values), 1) if values else None

    element_labels = {
        "5419": "Rendimiento",
        "5510": "Producción",
        "5312": "Superficie cosechada",
    }

    return {
        "crop": rows[0].get("Item", crop) if rows else crop,
        "country": rows[0].get("Area", country) if rows else country,
        "metric": element_labels.get(element_code, element),
        "unit": unit,
        "period": f"{year_from}–{year_to}",
        "average": avg,
        "series": series,
        "source": "FAOSTAT (FAO) — estadísticas agrícolas globales",
        "total_records": len(series),
    }
