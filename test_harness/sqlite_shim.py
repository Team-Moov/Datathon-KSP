"""
sqlite_shim.py
===============
TEST-ONLY. Monkeypatches psycopg2 so every training/inference script runs
completely unmodified against a local SQLite file instead of a real
Postgres server. This is how the ML logic gets validated without Postgres
installed -- it is NOT a substitute for running against real Postgres
before deploying: SQLite here is missing pgvector entirely (the
narrative_chunk table is skipped), doesn't enforce foreign keys the same
way, and this shim only translates the specific SQL patterns this
codebase actually uses (%s placeholders, execute_values bulk insert) --
it is not a general Postgres-to-SQLite translator.

Usage: import and call install(sqlite_path) BEFORE the target script's
own `import psycopg2` executes anything -- since Python caches imported
modules, patching psycopg2.connect here affects every subsequent
`import psycopg2` in the same process, including ones inside the target
script.
"""

import re
import sqlite3
from datetime import date, datetime

import psycopg2
import psycopg2.extras

sqlite3.register_converter("DATE", lambda b: date.fromisoformat(b.decode()))
sqlite3.register_converter("TIMESTAMP", lambda b: datetime.fromisoformat(b.decode().split(".")[0]))


class _FakeCursor:
    def __init__(self, raw_cursor):
        self._cur = raw_cursor

    def execute(self, query, params=None):
        q = query.replace("%s", "?")
        self._cur.execute(q, params or [])
        return self

    def fetchall(self):
        return self._cur.fetchall()

    def fetchone(self):
        return self._cur.fetchone()

    def close(self):
        self._cur.close()


class _FakeConn:
    def __init__(self, sqlite_path):
        self._conn = sqlite3.connect(sqlite_path, detect_types=sqlite3.PARSE_DECLTYPES)

    def cursor(self):
        return _FakeCursor(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def _fake_execute_values(cur, query, rows):
    if not rows:
        return
    n_cols = len(rows[0])
    placeholders = "(" + ",".join(["?"] * n_cols) + ")"
    q = re.sub(r"VALUES\s*%s", f"VALUES {placeholders}", query)
    q = q.replace("%s", "?")  # in case any non-VALUES %s remains
    cur._cur.executemany(q, rows)


def install(sqlite_path: str):
    psycopg2.connect = lambda *a, **kw: _FakeConn(sqlite_path)
    psycopg2.extras.execute_values = _fake_execute_values