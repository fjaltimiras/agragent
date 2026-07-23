# Supabase AgrAgent — runbook de respaldo + limpieza (Fair Use / DB Size Exceeded)

Proyecto: `mnaudtbccxicavonswzn` · cuenta `contacto@shemoves.cl` (compartida con SheMoves).
Situación: restricción de Fair Use por tamaño de DB > límite del plan free (500 MB). La API REST
responde 402 / DNS retirado, pero **el SQL Editor del dashboard y la conexión por pooler siguen
funcionando**. Objetivo: bajar de 500 MB para que la restricción se levante sola.

> Orden seguro: **1) MEDIR → 2) RESPALDAR → 3) BORRAR → 4) VACUUM/TRUNCATE**. No borrar nada
> antes de tener el respaldo confirmado.

---

## 1. MEDIR — Dashboard → SQL Editor (funciona aunque la API esté restringida)

```sql
-- Tamaño total de la base
SELECT pg_size_pretty(pg_database_size(current_database())) AS db_total;

-- Tamaño y filas por tabla (mayor a menor)
SELECT
  n.nspname AS schema,
  c.relname AS tabla,
  pg_size_pretty(pg_total_relation_size(c.oid)) AS tamano,
  pg_total_relation_size(c.oid) AS bytes,
  c.reltuples::bigint AS filas_aprox
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'r' AND n.nspname NOT IN ('pg_catalog','information_schema')
ORDER BY pg_total_relation_size(c.oid) DESC
LIMIT 30;
```

Pegar aquí el resultado para decidir qué purgar. Sospechosos habituales en AgrAgent:
- **Embeddings INIA RAG** (tabla con columna `vector`, ej. `inia_chunks`) → **REGENERABLE** con
  `scripts/index_inia.py`; NO necesita respaldo, es el mejor candidato a borrar.
- `aes_flights` / `aes_images` (JSONB de detecciones YOLO) → datos del POC AES.
- `messages` / `conversations` (historial de chat).

---

## 2. RESPALDAR (solo lo NO regenerable; los embeddings se re-indexan, no se respaldan)

### Opción A — pg_dump por el pooler (recomendado; requiere la password de la DB)

Copiar el connection string exacto desde **Dashboard → Settings → Database → Connection string →
"Session pooler"** (esa página funciona restringida). Tiene la forma:

```
postgresql://postgres.mnaudtbccxicavonswzn:[DB_PASSWORD]@aws-0-<region>.pooler.supabase.com:5432/postgres
```

Backup completo (esquema + datos) a un archivo local:

```bash
# Instalar client si falta: brew install libpq  (luego pg_dump en /opt/homebrew/opt/libpq/bin)
pg_dump "postgresql://postgres.mnaudtbccxicavonswzn:[DB_PASSWORD]@aws-0-<region>.pooler.supabase.com:5432/postgres" \
  --no-owner --no-privileges \
  -f agragent_supabase_backup_$(date +%Y%m%d).sql
```

Backup selectivo (solo las tablas de negocio, excluyendo embeddings pesados regenerables):

```bash
pg_dump "postgresql://postgres.mnaudtbccxicavonswzn:[DB_PASSWORD]@aws-0-<region>.pooler.supabase.com:5432/postgres" \
  --no-owner --no-privileges \
  -t public.conversations -t public.messages -t public.aes_flights -t public.aes_images \
  -f agragent_business_backup_$(date +%Y%m%d).sql
```

### Opción B — Export CSV por tabla (si el pooler no conecta)

Dashboard → **Table Editor** → seleccionar tabla → **Export → CSV**. Hacerlo para
`conversations`, `messages`, `aes_flights`, `aes_images`. (No exportar la tabla de embeddings:
es grande y regenerable.)

---

## 3. BORRAR (después de confirmar respaldo) — SQL Editor

> `DELETE` solo NO libera disco (deja tuplas muertas). Para reclamar espacio de verdad:
> `TRUNCATE` (instantáneo, para vaciar toda una tabla) o `VACUUM FULL` (tras un DELETE parcial).

```sql
-- Ejemplo: vaciar embeddings INIA (REGENERABLE con index_inia.py). Ajustar nombre real.
TRUNCATE TABLE inia_chunks;

-- Ejemplo: purgar detecciones AES antiguas (ajustar tabla/condición tras ver los tamaños)
-- DELETE FROM aes_flights WHERE created_at < now() - interval '90 days';
-- VACUUM FULL aes_flights;
```

Tras vaciar, re-medir con el bloque del paso 1. Cuando `db_total` baje de ~500 MB, la restricción
de Fair Use se levanta sola (puede tardar unos minutos).

---

## 4. Reconstruir embeddings (cuando la DB vuelva a estar operativa)

```bash
cd agragent-app/backend
python3 scripts/index_inia.py --topic "vid OR uva OR vino" --limit 50
```

## Nota estratégica

Esta Supabase es **compartida con SheMoves (producción)**. Si SheMoves crece, conviene separarlo a
su propio proyecto o pasar la cuenta a Pro para no que un pico de datos de un proyecto tumbe al otro.
