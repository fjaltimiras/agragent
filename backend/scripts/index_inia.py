#!/usr/bin/env python3
"""
INIA RAG Indexer — AgrAgent Phase 2

Indexa documentos de la Biblioteca Digital INIA Chile en Supabase pgvector
para búsqueda semántica desde el agente Claude.

Estrategia:
  1. Buscar documentos en INIA por tema (search API)
  2. Para cada documento: descargar bundle TEXT (texto pre-extraído por DSpace)
  3. Trocear (chunks de ~500 tokens con overlap)
  4. Embedder con OpenAI text-embedding-3-small (1536 dim)
  5. Guardar en Supabase (inia_documents + inia_chunks)

Uso:
  # Test pequeño (50 docs viticultura, ~5 min, ~$0.05)
  python scripts/index_inia.py --topic "vid OR uva OR vino" --limit 50

  # Indexación masiva (todo viticultura, ~45 min, ~$0.50)
  python scripts/index_inia.py --topic "vid OR uva OR vino" --limit 2500

  # Reindexar un tema específico
  python scripts/index_inia.py --topic riego --limit 500

Variables de entorno requeridas (en backend/.env):
  - OPENAI_API_KEY
  - SUPABASE_URL
  - SUPABASE_KEY  (o SUPABASE_SERVICE_ROLE_KEY)

Pre-requisito: aplicar scripts/inia_rag_schema.sql en Supabase.
"""

import os
import sys
import ssl
import json
import time
import argparse
import re
import urllib.request
import urllib.parse
from pathlib import Path

# Cargar .env del backend
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

# ── CONFIG ────────────────────────────────────────────────────────
INIA_API = "https://biblioteca.inia.cl/server/api"
EMBED_MODEL = "text-embedding-3-small"  # 1536 dim
EMBED_DIMS = 1536
CHUNK_CHARS = 1800   # ~450 tokens
CHUNK_OVERLAP = 200
DELAY = 0.3          # segundos entre requests a INIA
BATCH_EMBED = 50     # batch chunks por request OpenAI

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


# ── HTTP HELPERS ──────────────────────────────────────────────────
def http_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "AgrAgent-Indexer/1.0"})
    with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
        return json.loads(r.read())

def http_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "AgrAgent-Indexer/1.0"})
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
        return r.read().decode("utf-8", errors="ignore")


# ── INIA: buscar documentos ───────────────────────────────────────
def search_documents(query, limit):
    """Devuelve lista de UUIDs ordenados por relevancia."""
    page_size = 100
    pages = max(1, (limit + page_size - 1) // page_size)
    docs = []

    for page in range(pages):
        size = min(page_size, limit - len(docs))
        if size <= 0: break

        url = (f"{INIA_API}/discover/search/objects"
               f"?query={urllib.parse.quote(query)}"
               f"&dsoType=item&size={size}&page={page}&sort=score,desc")
        try:
            data = http_json(url)
            time.sleep(DELAY)
        except Exception as e:
            print(f"  ⚠️  Error en página {page}: {e}")
            break

        for obj in data["_embedded"]["searchResult"]["_embedded"].get("objects", []):
            item = obj["_embedded"].get("indexableObject", {})
            meta = item.get("metadata", {})
            uuid = item.get("uuid", "")
            if not uuid: continue

            def mv(f):
                vs = meta.get(f, [])
                return vs[0]["value"] if vs else ""
            def mvall(f):
                return [v["value"] for v in meta.get(f, [])]

            docs.append({
                "uuid":     uuid,
                "title":    mv("dc.title"),
                "year":     (mv("dc.date.issued") or "")[:4],
                "authors":  mvall("dc.contributor.author")[:5],
                "subjects": mvall("dc.subject")[:8],
                "abstract": (mv("dc.description.abstract") or "")[:1500],
                "doc_type": mv("dc.type") or mv("dc.description.series"),
                "link":     mv("dc.identifier.uri") or f"https://biblioteca.inia.cl/items/{uuid}",
            })

        if len(data["_embedded"]["searchResult"]["_embedded"].get("objects", [])) < size:
            break

    return docs[:limit]


def fetch_text(uuid):
    """
    Descarga el texto del documento INIA.
    Estrategia:
      1. Probar bundle TEXT (texto pre-extraído por DSpace, rápido)
      2. Si no hay TEXT, descargar el PDF y extraerlo con pdfplumber
    """
    try:
        bundles = http_json(f"{INIA_API}/core/items/{uuid}/bundles")
        time.sleep(DELAY)
    except Exception:
        return None

    text_bundle = original_bundle = None
    for b in bundles["_embedded"]["bundles"]:
        if b.get("name") == "TEXT":
            text_bundle = b
        elif b.get("name") == "ORIGINAL":
            original_bundle = b

    # Estrategia 1: bundle TEXT
    if text_bundle:
        try:
            bits = http_json(text_bundle["_links"]["bitstreams"]["href"])
            time.sleep(DELAY)
            for bit in bits["_embedded"]["bitstreams"]:
                url = bit["_links"]["content"]["href"]
                text = http_text(url)
                time.sleep(DELAY)
                if text and len(text) > 200:
                    return text
        except Exception:
            pass

    # Estrategia 2: descargar PDF y parsearlo con pdfplumber
    if original_bundle:
        try:
            bits = http_json(original_bundle["_links"]["bitstreams"]["href"])
            time.sleep(DELAY)
            for bit in bits["_embedded"]["bitstreams"]:
                fname = (bit.get("name") or "").lower()
                if not fname.endswith(".pdf"):
                    continue
                url = bit["_links"]["content"]["href"]
                req = urllib.request.Request(url, headers={"User-Agent": "AgrAgent-Indexer/1.0"})
                with urllib.request.urlopen(req, timeout=120, context=ctx) as r:
                    pdf_bytes = r.read()
                time.sleep(DELAY)
                # parsear con pdfplumber
                try:
                    import pdfplumber, io
                    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                        text = "\n\n".join(
                            page.extract_text() or "" for page in pdf.pages
                        )
                    if text and len(text) > 200:
                        return text
                except Exception:
                    continue
        except Exception:
            pass

    return None


# ── CHUNKING ──────────────────────────────────────────────────────
def clean_text(text):
    """Normalización mínima: quita líneas en blanco repetidas y espacios extra."""
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()

def chunk_text(text, size=CHUNK_CHARS, overlap=CHUNK_OVERLAP):
    """Trocea por párrafos, manteniendo coherencia semántica."""
    text = clean_text(text)
    if len(text) < 100:
        return []

    chunks = []
    paragraphs = text.split("\n\n")
    buf = ""

    for p in paragraphs:
        if len(buf) + len(p) <= size:
            buf += ("\n\n" if buf else "") + p
        else:
            if buf:
                chunks.append(buf.strip())
            # si el párrafo es más grande que size, partirlo
            while len(p) > size:
                chunks.append(p[:size].strip())
                p = p[size - overlap:]
            buf = p

    if buf:
        chunks.append(buf.strip())

    # Filtra chunks muy cortos
    return [c for c in chunks if len(c) >= 50]


# ── EMBEDDINGS ────────────────────────────────────────────────────
def embed_batch(client, texts):
    """Embed un batch de strings con OpenAI."""
    resp = client.embeddings.create(
        model=EMBED_MODEL,
        input=texts,
    )
    return [d.embedding for d in resp.data]


# ── MAIN ──────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default="vid OR uva OR vino", help="Búsqueda en INIA")
    ap.add_argument("--limit", type=int, default=50, help="Máximo de documentos")
    ap.add_argument("--skip-existing", action="store_true",
                    help="Saltar documentos ya indexados (default: True)")
    args = ap.parse_args()

    # Validar credenciales
    openai_key   = os.getenv("OPENAI_API_KEY")
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY")
                    or os.getenv("SUPABASE_KEY"))

    if not openai_key:
        print("❌ Falta OPENAI_API_KEY en backend/.env")
        sys.exit(1)
    if not supabase_url or not supabase_key:
        print("❌ Faltan SUPABASE_URL / SUPABASE_KEY en backend/.env")
        sys.exit(1)

    try:
        from openai import OpenAI
        from supabase import create_client
    except ImportError as e:
        print(f"❌ Falta dependencia: {e}")
        print("   Ejecuta: python3 -m pip install openai supabase")
        sys.exit(1)

    openai = OpenAI(api_key=openai_key)
    sb     = create_client(supabase_url, supabase_key)

    print(f"🔍 Buscando en INIA: '{args.topic}' (limit {args.limit})")
    docs = search_documents(args.topic, args.limit)
    print(f"   {len(docs)} documentos encontrados\n")

    # Ver cuáles ya están indexados
    if args.skip_existing or True:  # default
        try:
            existing = sb.table("inia_documents").select("uuid").execute()
            indexed_uuids = {r["uuid"] for r in existing.data}
            new_docs = [d for d in docs if d["uuid"] not in indexed_uuids]
            print(f"   {len(indexed_uuids)} ya indexados, procesando {len(new_docs)} nuevos\n")
            docs = new_docs
        except Exception as e:
            print(f"   ⚠️  No se pudo leer índice existente: {e}")

    if not docs:
        print("✓ Nada que indexar. Saliendo.")
        return

    total_chunks = 0
    skipped_no_text = 0

    for i, doc in enumerate(docs, 1):
        title = doc["title"][:60] + "…" if len(doc["title"]) > 60 else doc["title"]
        print(f"[{i:>3}/{len(docs)}] {title}")

        text = fetch_text(doc["uuid"])
        if not text:
            print(f"           ⚠️  Sin bundle TEXT, saltando")
            skipped_no_text += 1
            continue

        chunks = chunk_text(text)
        if not chunks:
            print(f"           ⚠️  Sin chunks aprovechables")
            continue

        print(f"           📄 {len(text)} chars → {len(chunks)} chunks", end="", flush=True)

        # Embed en batches
        try:
            all_embeds = []
            for b_start in range(0, len(chunks), BATCH_EMBED):
                batch = chunks[b_start:b_start + BATCH_EMBED]
                all_embeds.extend(embed_batch(openai, batch))
        except Exception as e:
            print(f"\n           ❌ Error en embedding: {e}")
            continue

        # Insertar documento
        try:
            sb.table("inia_documents").upsert({
                "uuid":     doc["uuid"],
                "title":    doc["title"],
                "year":     doc["year"],
                "authors":  doc["authors"],
                "subjects": doc["subjects"],
                "abstract": doc["abstract"],
                "doc_type": doc["doc_type"],
                "link":     doc["link"],
                "text_len": len(text),
            }).execute()
        except Exception as e:
            print(f"\n           ❌ Error insertando documento: {e}")
            continue

        # Insertar chunks
        try:
            chunk_rows = [
                {"document_uuid": doc["uuid"], "chunk_index": idx,
                 "content": c, "embedding": e}
                for idx, (c, e) in enumerate(zip(chunks, all_embeds))
            ]
            # Borrar chunks viejos del documento (por si re-indexamos)
            sb.table("inia_chunks").delete().eq("document_uuid", doc["uuid"]).execute()
            # Insertar nuevos
            for j in range(0, len(chunk_rows), 50):
                sb.table("inia_chunks").insert(chunk_rows[j:j+50]).execute()
            total_chunks += len(chunks)
            print(f" ✓")
        except Exception as e:
            print(f"\n           ❌ Error insertando chunks: {e}")
            continue

    print()
    print("─" * 50)
    print(f"✅ Indexación completa")
    print(f"   Documentos procesados:     {len(docs)}")
    print(f"   Sin bundle TEXT (skipped): {skipped_no_text}")
    print(f"   Chunks creados:            {total_chunks}")

    # Stats del índice
    try:
        stats = sb.rpc("inia_rag_stats").execute()
        if stats.data:
            s = stats.data[0]
            print(f"\n📊 Estado del índice INIA:")
            print(f"   Documentos totales: {s['total_documents']}")
            print(f"   Chunks totales:     {s['total_chunks']}")
            print(f"   Años:               {s['oldest_year']} – {s['newest_year']}")
    except Exception:
        pass


if __name__ == "__main__":
    main()
