"""
Local SQLite database adapter that mirrors the Supabase query-builder interface.
Used as a fallback when SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are not set.
"""
import sqlite3
import uuid
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_PATH = Path.home() / ".agro-agent" / "local.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExecuteResult:
    def __init__(self, data):
        self.data = data


class QueryBuilder:
    def __init__(self, conn: sqlite3.Connection, table_name: str):
        self._conn = conn
        self._table = table_name
        self._operation = None
        self._insert_data = None
        self._update_data = None
        self._wheres: list[tuple] = []
        self._order_col = None
        self._order_desc = False
        self._limit_val = None

    # ── Operation setters ──────────────────────────────────────────────────────

    def select(self, cols="*"):
        self._operation = "select"
        return self

    def insert(self, data: dict):
        self._operation = "insert"
        self._insert_data = dict(data)
        return self

    def update(self, data: dict):
        self._operation = "update"
        self._update_data = dict(data)
        return self

    def delete(self):
        self._operation = "delete"
        return self

    # ── Filters / modifiers ───────────────────────────────────────────────────

    def eq(self, col: str, val):
        self._wheres.append((col, val))
        return self

    def order(self, col: str, desc: bool = False):
        self._order_col = col
        self._order_desc = desc
        return self

    def limit(self, n: int):
        self._limit_val = n
        return self

    # ── Execution ─────────────────────────────────────────────────────────────

    def execute(self) -> ExecuteResult:
        if self._operation == "select":
            return self._do_select()
        elif self._operation == "insert":
            return self._do_insert()
        elif self._operation == "update":
            return self._do_update()
        elif self._operation == "delete":
            return self._do_delete()
        raise ValueError(f"Unknown operation: {self._operation}")

    # ── Private helpers ───────────────────────────────────────────────────────

    _JSON_FIELDS = {"tool_calls", "tool_results", "parsed_data"}

    def _deserialize_row(self, row: tuple, description) -> dict:
        cols = [d[0] for d in description]
        d = dict(zip(cols, row))
        for key in self._JSON_FIELDS:
            if key in d and d[key] and isinstance(d[key], str):
                try:
                    d[key] = json.loads(d[key])
                except Exception:
                    pass
        return d

    def _serialize_value(self, key: str, val):
        if key in self._JSON_FIELDS and val is not None and not isinstance(val, str):
            return json.dumps(val)
        return val

    def _table_columns(self) -> list[str]:
        cur = self._conn.cursor()
        cur.execute(f"PRAGMA table_info({self._table})")
        return [row[1] for row in cur.fetchall()]

    def _do_select(self) -> ExecuteResult:
        sql = f"SELECT * FROM {self._table}"
        params = []
        if self._wheres:
            clauses = " AND ".join(f"{col} = ?" for col, _ in self._wheres)
            sql += f" WHERE {clauses}"
            params = [v for _, v in self._wheres]
        if self._order_col:
            direction = "DESC" if self._order_desc else "ASC"
            sql += f" ORDER BY {self._order_col} {direction}"
        if self._limit_val is not None:
            sql += f" LIMIT {self._limit_val}"

        cur = self._conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        return ExecuteResult(data=[self._deserialize_row(r, cur.description) for r in rows])

    def _do_insert(self) -> ExecuteResult:
        data = dict(self._insert_data)
        now = _now()
        existing_cols = self._table_columns()

        if "id" not in data:
            data["id"] = str(uuid.uuid4())
        if "created_at" not in data:
            data["created_at"] = now
        if "updated_at" in existing_cols and "updated_at" not in data:
            data["updated_at"] = now

        # Serialize JSON fields
        for key in list(data.keys()):
            data[key] = self._serialize_value(key, data[key])

        cols = list(data.keys())
        placeholders = ",".join("?" * len(cols))
        sql = f"INSERT INTO {self._table} ({','.join(cols)}) VALUES ({placeholders})"
        cur = self._conn.cursor()
        cur.execute(sql, [data[c] for c in cols])

        # Keep conversations.updated_at fresh on every new message
        if self._table == "messages" and "conversation_id" in data:
            cur.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                [now, data["conversation_id"]],
            )
        self._conn.commit()

        cur.execute(f"SELECT * FROM {self._table} WHERE id = ?", [data["id"]])
        row = cur.fetchone()
        return ExecuteResult(data=[self._deserialize_row(row, cur.description)])

    def _do_update(self) -> ExecuteResult:
        if not self._wheres:
            raise ValueError("UPDATE without WHERE is not allowed")
        data = dict(self._update_data)
        now = _now()
        # Replace Supabase "now()" sentinel
        data = {k: (now if v == "now()" else v) for k, v in data.items()}

        set_clause = ", ".join(f"{col} = ?" for col in data)
        where_clause = " AND ".join(f"{col} = ?" for col, _ in self._wheres)
        sql = f"UPDATE {self._table} SET {set_clause} WHERE {where_clause}"
        params = list(data.values()) + [v for _, v in self._wheres]

        cur = self._conn.cursor()
        cur.execute(sql, params)
        self._conn.commit()

        where_clause2 = " AND ".join(f"{col} = ?" for col, _ in self._wheres)
        cur.execute(f"SELECT * FROM {self._table} WHERE {where_clause2}", [v for _, v in self._wheres])
        rows = cur.fetchall()
        return ExecuteResult(data=[self._deserialize_row(r, cur.description) for r in rows])

    def _do_delete(self) -> ExecuteResult:
        if not self._wheres:
            raise ValueError("DELETE without WHERE is not allowed")
        where_clause = " AND ".join(f"{col} = ?" for col, _ in self._wheres)
        sql = f"DELETE FROM {self._table} WHERE {where_clause}"
        cur = self._conn.cursor()
        cur.execute(sql, [v for _, v in self._wheres])
        self._conn.commit()
        return ExecuteResult(data=[])


class _MockStorageBucket:
    """Minimal storage mock — saves nothing, returns fake URLs."""
    def upload(self, path: str, file_bytes: bytes, file_options=None):
        return type("R", (), {"data": {"path": path}, "error": None})()

    def get_public_url(self, path: str) -> str:
        return f"local://{path}"


class _MockStorage:
    def from_(self, bucket: str):
        return _MockStorageBucket()


class LocalDB:
    """Thread-safe SQLite client with a Supabase-compatible query-builder API."""

    _instance = None
    _lock = threading.Lock()

    def __init__(self, db_path: Optional[Path] = None):
        path = db_path or DB_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(path),
            check_same_thread=False,
            isolation_level=None,  # autocommit off; we commit manually
        )
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def _init_schema(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id          TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                field_id    TEXT,
                title       TEXT NOT NULL DEFAULT 'Nueva consulta',
                created_at  TEXT,
                updated_at  TEXT
            );

            CREATE TABLE IF NOT EXISTS messages (
                id                TEXT PRIMARY KEY,
                conversation_id   TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                role              TEXT NOT NULL,
                content           TEXT,
                tool_calls        TEXT,
                tool_results      TEXT,
                created_at        TEXT
            );

            CREATE TABLE IF NOT EXISTS field_analyses (
                id             TEXT PRIMARY KEY,
                user_id        TEXT NOT NULL,
                field_id       TEXT,
                type           TEXT NOT NULL,
                file_url       TEXT,
                file_name      TEXT,
                parsed_data    TEXT,
                analysis_date  TEXT,
                notes          TEXT,
                created_at     TEXT
            );

            CREATE TABLE IF NOT EXISTS fields (
                id          TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                name        TEXT NOT NULL,
                crop_type   TEXT,
                area_ha     REAL,
                notes       TEXT,
                created_at  TEXT,
                updated_at  TEXT
            );
        """)

    def table(self, name: str) -> QueryBuilder:
        return QueryBuilder(self._conn, name)

    @property
    def storage(self):
        return _MockStorage()


def get_local_db() -> LocalDB:
    """Return a singleton LocalDB instance."""
    with LocalDB._lock:
        if LocalDB._instance is None:
            LocalDB._instance = LocalDB()
    return LocalDB._instance
