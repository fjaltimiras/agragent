"""
Servicio de búsqueda en la Biblioteca Digital INIA Chile
API: DSpace 7 REST — https://biblioteca.inia.cl/server/api
Sin autenticación requerida (open access).
"""

import ssl
import json
import urllib.request
import urllib.parse
import logging

logger = logging.getLogger(__name__)

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE

BASE_API = "https://biblioteca.inia.cl/server/api"


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "AgrAgent/1.0"})
    with urllib.request.urlopen(req, timeout=15, context=_ctx) as r:
        return json.loads(r.read())


def search_inia_biblioteca(query: str, max_results: int = 5) -> dict:
    """
    Busca documentos en la Biblioteca Digital INIA Chile.
    Devuelve lista de documentos con título, resumen, año, autores y enlace.
    """
    try:
        url = (
            f"{BASE_API}/discover/search/objects"
            f"?query={urllib.parse.quote(query)}"
            f"&dsoType=item&size={max_results}&sort=score,desc"
        )
        data = _get(url)

        sr      = data["_embedded"]["searchResult"]
        total   = sr["page"]["totalElements"]
        objects = sr["_embedded"].get("objects", [])

        results = []
        for obj in objects:
            item = obj["_embedded"].get("indexableObject", {})
            meta = item.get("metadata", {})

            def mv(field: str) -> str:
                vals = meta.get(field, [])
                return vals[0]["value"] if vals else ""

            def mvall(field: str) -> list:
                return [v["value"] for v in meta.get(field, [])]

            uuid     = item.get("uuid", "")
            title    = mv("dc.title")
            year     = mv("dc.date.issued")[:4]
            authors  = mvall("dc.contributor.author")[:3]
            subjects = mvall("dc.subject")[:5]
            abstract = mv("dc.description.abstract")[:600]
            link     = f"https://biblioteca.inia.cl/items/{uuid}" if uuid else ""
            doc_type = mv("dc.type") or mv("dc.description.series")

            if not title:
                continue

            results.append({
                "title":    title,
                "year":     year,
                "authors":  authors,
                "subjects": subjects,
                "abstract": abstract,
                "type":     doc_type,
                "link":     link,
            })

        return {
            "total_available": total,
            "returned": len(results),
            "query": query,
            "source": "Biblioteca Digital INIA Chile (biblioteca.inia.cl)",
            "results": results,
        }

    except Exception as e:
        logger.error(f"INIA search error: {e}")
        return {
            "error": f"No se pudo conectar con la Biblioteca INIA: {e}",
            "query": query,
            "results": [],
        }
