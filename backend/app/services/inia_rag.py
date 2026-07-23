"""
Servicio RAG sobre Biblioteca INIA — AgrAgent Phase 2

Búsqueda semántica sobre el corpus indexado en Supabase pgvector.
Embeds la consulta con OpenAI text-embedding-3-small (1536 dim) y
recupera los chunks más similares vía función RPC `match_inia_chunks`.

Pre-requisito: tener documentos indexados en Supabase
(ejecutar `python scripts/index_inia.py` para poblar la base).
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

EMBED_MODEL = "text-embedding-3-small"


def _embed_query(text: str) -> Optional[list]:
    """Genera el embedding 1536-dim de la consulta usando OpenAI."""
    try:
        from openai import OpenAI
    except ImportError:
        logger.error("openai SDK no instalado. Ejecuta: pip install openai")
        return None

    from app.config import settings
    api_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY no definido")
        return None

    try:
        client = OpenAI(api_key=api_key)
        resp = client.embeddings.create(model=EMBED_MODEL, input=text)
        return resp.data[0].embedding
    except Exception as e:
        logger.error(f"Error en embedding query: {e}")
        return None


def search_inia_rag(query: str, top_k: int = 5,
                    min_similarity: float = 0.25) -> dict:
    """
    Búsqueda semántica RAG sobre el corpus INIA indexado.

    Args:
        query: consulta en lenguaje natural (español)
        top_k: número máximo de chunks a retornar (1-15)
        min_similarity: similitud coseno mínima (0.0-1.0). Default 0.25.

    Returns:
        dict con `results` (lista de chunks con metadata) o `error`.
    """
    top_k = max(1, min(int(top_k), 15))

    # 1. Embed la consulta
    qvec = _embed_query(query)
    if qvec is None:
        return {
            "error": "No se pudo generar embedding (verifica OPENAI_API_KEY).",
            "query": query,
            "results": [],
        }

    # 2. Llamar a la función RPC en Supabase
    try:
        from app.database import get_db
        db = get_db()
        rpc = db.rpc("match_inia_chunks", {
            "query_embedding":      qvec,
            "match_count":          top_k,
            "similarity_threshold": min_similarity,
        }).execute()
    except Exception as e:
        logger.error(f"Error en RPC match_inia_chunks: {e}")
        return {
            "error": f"Error al buscar en pgvector: {e}. ¿Aplicaste el schema y indexaste documentos?",
            "query": query,
            "results": [],
        }

    rows = rpc.data or []

    # 3. Estructurar resultados
    results = []
    for r in rows:
        results.append({
            "title":      r.get("title", ""),
            "year":       r.get("year", ""),
            "authors":    r.get("authors", []) or [],
            "subjects":   r.get("subjects", []) or [],
            "snippet":    (r.get("content") or "")[:1000],
            "similarity": round(float(r.get("similarity", 0.0)), 3),
            "link":       r.get("link", ""),
            "chunk":      r.get("chunk_index", 0),
        })

    return {
        "query":       query,
        "top_k":       top_k,
        "returned":    len(results),
        "source":      "Biblioteca Digital INIA Chile (RAG semántico)",
        "results":     results,
    }
