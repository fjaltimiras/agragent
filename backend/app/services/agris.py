"""
Servicio AGRIS (FAO) — AgrAgent
Búsqueda bibliográfica en AGRIS, la base de datos agrícola global de la FAO.

AGRIS: https://agris.fao.org
- 16.5M+ registros desde 1975, 258 idiomas, 2,000+ proveedores
- Sin autenticación requerida
- Cobertura especial: literatura gris latinoamericana y publicaciones locales
"""
import ssl
import urllib.request
import urllib.parse
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

BASE_URL = "https://agris.fao.org/agris-search/search.do"

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
    with urllib.request.urlopen(req, timeout=15, context=_ctx) as r:
        raw = r.read()
        return json.loads(raw)


def search_agris(
    query: str,
    max_results: int = 5,
    year_from: Optional[int] = None,
) -> dict:
    """
    Busca publicaciones en AGRIS (FAO) — literatura agrícola global incluyendo
    publicaciones latinoamericanas y literatura gris no indexada en otras bases.

    Args:
        query: términos de búsqueda (español o inglés)
        max_results: resultados a retornar (1-10)
        year_from: año mínimo de publicación (opcional)

    Returns:
        dict con resultados: título, autores, año, resumen, URL, proveedor
    """
    max_results = max(1, min(int(max_results), 10))

    params = {
        "query": query,
        "startIndexSearch": 1,
        "outputFormat": "json",
        "sortField": "score",
        "sortOrder": "desc",
    }

    url = f"{BASE_URL}?{urllib.parse.urlencode(params)}"

    try:
        data = _get(url)
    except Exception as e:
        logger.error(f"AGRIS search error: {e}")
        return {
            "error": f"Error al consultar AGRIS: {e}",
            "query": query,
            "results": [],
            "note": "AGRIS puede estar temporalmente no disponible. Intenta search_openalex como alternativa.",
        }

    # AGRIS puede devolver resultados en distintas claves según versión de API
    raw_results = (
        data.get("results")
        or data.get("hits")
        or data.get("response", {}).get("docs")
        or []
    )
    total = (
        data.get("totalCount")
        or data.get("total")
        or data.get("response", {}).get("numFound")
        or len(raw_results)
    )

    results = []
    for item in raw_results[:max_results]:
        year_raw = (
            item.get("year")
            or item.get("publicationDate", "")[:4]
            or item.get("dc:date", "")[:4]
            or ""
        )
        try:
            year_int = int(year_raw)
        except (ValueError, TypeError):
            year_int = 0

        if year_from and year_int and year_int < year_from:
            continue

        authors = item.get("authors") or item.get("creatorPersonal") or item.get("dc:creator") or []
        if isinstance(authors, str):
            authors = [authors]

        results.append({
            "title": item.get("title") or item.get("dc:title") or "",
            "year": str(year_int) if year_int else year_raw,
            "authors": authors[:3],
            "abstract": (item.get("description") or item.get("abstract") or item.get("dc:description") or "")[:600],
            "url": item.get("url") or item.get("identifier") or item.get("dc:identifier") or "",
            "provider": item.get("provider") or item.get("dataProvider") or "",
            "language": item.get("language") or item.get("dc:language") or "",
        })

    return {
        "query": query,
        "total_available": total,
        "returned": len(results),
        "source": "AGRIS (FAO) — 16.5M+ registros agrícolas globales",
        "results": results,
    }
