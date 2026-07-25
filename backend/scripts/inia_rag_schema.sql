-- ─────────────────────────────────────────────────────────────────
-- AgrAgent — INIA RAG Schema (Phase 2)
-- Aplicar en Supabase SQL Editor
-- ─────────────────────────────────────────────────────────────────

-- 1) Habilitar extensión pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- (Si ya aplicaste un schema previo con dims diferentes, dropéalo primero:)
DROP TABLE IF EXISTS inia_chunks    CASCADE;
DROP TABLE IF EXISTS inia_documents CASCADE;
DROP FUNCTION IF EXISTS match_inia_chunks(vector, INT, FLOAT) CASCADE;
DROP FUNCTION IF EXISTS inia_rag_stats() CASCADE;

-- 2) Tabla de documentos (metadata)
CREATE TABLE IF NOT EXISTS inia_documents (
  uuid       TEXT PRIMARY KEY,
  title      TEXT NOT NULL,
  year       TEXT,
  authors    TEXT[] DEFAULT '{}',
  subjects   TEXT[] DEFAULT '{}',
  abstract   TEXT,
  doc_type   TEXT,
  link       TEXT,
  text_len   INT,
  indexed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_inia_documents_year     ON inia_documents (year);
CREATE INDEX IF NOT EXISTS idx_inia_documents_subjects ON inia_documents USING GIN (subjects);

-- 3) Tabla de chunks con embeddings
-- 1536 dims = OpenAI text-embedding-3-small
CREATE TABLE IF NOT EXISTS inia_chunks (
  id            BIGSERIAL PRIMARY KEY,
  document_uuid TEXT NOT NULL REFERENCES inia_documents(uuid) ON DELETE CASCADE,
  chunk_index   INT  NOT NULL,
  content       TEXT NOT NULL,
  embedding     vector(1536),
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (document_uuid, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_inia_chunks_doc ON inia_chunks (document_uuid);

-- Índice IVFFlat para búsqueda por similitud (cosine).
-- lists=100 es razonable para hasta ~100K chunks.
CREATE INDEX IF NOT EXISTS idx_inia_chunks_embedding
  ON inia_chunks USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

-- 4) Función RPC: búsqueda por similitud + JOIN con documents
CREATE OR REPLACE FUNCTION match_inia_chunks(
  query_embedding vector(1536),
  match_count     INT DEFAULT 5,
  similarity_threshold FLOAT DEFAULT 0.0
) RETURNS TABLE (
  document_uuid TEXT,
  chunk_index   INT,
  content       TEXT,
  similarity    FLOAT,
  title         TEXT,
  year          TEXT,
  authors       TEXT[],
  subjects      TEXT[],
  link          TEXT
)
LANGUAGE sql STABLE AS $$
  SELECT
    c.document_uuid,
    c.chunk_index,
    c.content,
    1 - (c.embedding <=> query_embedding) AS similarity,
    d.title,
    d.year,
    d.authors,
    d.subjects,
    d.link
  FROM inia_chunks c
  JOIN inia_documents d ON d.uuid = c.document_uuid
  WHERE 1 - (c.embedding <=> query_embedding) >= similarity_threshold
  ORDER BY c.embedding <=> query_embedding
  LIMIT match_count;
$$;

-- 5) Permisos explícitos — RLS habilitado con policies permisivas (funciona con anon key)
ALTER TABLE inia_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE inia_chunks    ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "inia_documents_open" ON inia_documents;
DROP POLICY IF EXISTS "inia_chunks_open"    ON inia_chunks;

CREATE POLICY "inia_documents_open" ON inia_documents
  FOR ALL TO anon, authenticated, service_role
  USING (true) WITH CHECK (true);

CREATE POLICY "inia_chunks_open" ON inia_chunks
  FOR ALL TO anon, authenticated, service_role
  USING (true) WITH CHECK (true);

GRANT ALL PRIVILEGES ON TABLE inia_documents TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON TABLE inia_chunks    TO anon, authenticated, service_role;
GRANT USAGE, SELECT ON SEQUENCE inia_chunks_id_seq TO anon, authenticated, service_role;

-- 6) Función RPC: estadísticas del índice
CREATE OR REPLACE FUNCTION inia_rag_stats()
RETURNS TABLE (
  total_documents BIGINT,
  total_chunks    BIGINT,
  oldest_year     TEXT,
  newest_year     TEXT
)
LANGUAGE sql STABLE AS $$
  SELECT
    (SELECT COUNT(*) FROM inia_documents),
    (SELECT COUNT(*) FROM inia_chunks),
    (SELECT MIN(year) FROM inia_documents WHERE year ~ '^[0-9]{4}$'),
    (SELECT MAX(year) FROM inia_documents WHERE year ~ '^[0-9]{4}$');
$$;
