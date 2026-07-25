"""
Servicio OpenAlex — AgrAgent
Búsqueda de publicaciones científicas agrícolas en acceso abierto.

OpenAlex: https://docs.openalex.org
- 250M+ trabajos académicos indexados
- Sin autenticación requerida (polite pool con email)
- Filtros: open_access, año, tema, autor, institución
"""

import ssl
import urllib.request
import urllib.parse
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

BASE_URL = "https://api.openalex.org"
MAILTO  = "agragent@agragent.com"

# macOS Python 3.9 may not have updated CA certs — use system SSL context
try:
    import certifi
    _ctx = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _ctx = ssl.create_default_context()


def _get(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": f"AgrAgent/1.0 (mailto:{MAILTO})"}
    )
    with urllib.request.urlopen(req, timeout=15, context=_ctx) as r:
        return json.loads(r.read())


def search_openalex(
    query: str,
    max_results: int = 5,
    open_access_only: bool = True,
    year_from: Optional[int] = 2010,
) -> dict:
    """
    Busca publicaciones científicas en OpenAlex.
    Prioriza artículos en acceso abierto con abstract disponible.

    Args:
        query: términos de búsqueda en inglés o español
        max_results: número de resultados (1-15)
        open_access_only: filtrar solo open access (default True)
        year_from: año mínimo de publicación (default 2010)

    Returns:
        dict con lista de resultados: title, year, authors, abstract, doi, url
    """
    max_results = max(1, min(int(max_results), 15))

    filters = []
    if open_access_only:
        filters.append("open_access.is_oa:true")
    if year_from:
        filters.append(f"publication_year:{year_from}-")

    params = {
        "search": query,
        "per-page": max_results,
        "select": "title,publication_year,doi,authorships,abstract_inverted_index,primary_location,open_access",
        "sort": "relevance_score:desc",
    }
    if filters:
        params["filter"] = ",".join(filters)

    url = f"{BASE_URL}/works?{urllib.parse.urlencode(params)}"

    try:
        data = _get(url)
    except Exception as e:
        logger.error(f"OpenAlex search error: {e}")
        return {"error": f"Error al consultar OpenAlex: {e}", "query": query, "results": []}

    total = data.get("meta", {}).get("count", 0)
    results = []

    for work in data.get("results", []):
        # Reconstruir abstract desde el índice invertido
        abstract = ""
        inv = work.get("abstract_inverted_index") or {}
        if inv:
            positions = {}
            for word, pos_list in inv.items():
                for pos in pos_list:
                    positions[pos] = word
            abstract = " ".join(positions[p] for p in sorted(positions))[:600]

        # Autores
        authors = [
            a.get("author", {}).get("display_name", "")
            for a in (work.get("authorships") or [])[:3]
        ]

        # DOI / URL
        doi = work.get("doi") or ""
        loc = (work.get("primary_location") or {})
        oa_url = (work.get("open_access") or {}).get("oa_url") or ""
        url_doc = oa_url or doi or ""

        results.append({
            "title":    work.get("title", ""),
            "year":     work.get("publication_year", ""),
            "authors":  [a for a in authors if a],
            "abstract": abstract,
            "doi":      doi,
            "url":      url_doc,
            "open_access": bool((work.get("open_access") or {}).get("is_oa")),
        })

    return {
        "query":           query,
        "total_available": total,
        "returned":        len(results),
        "source":          "OpenAlex (openalex.org) — 250M+ academic works",
        "results":         results,
    }
