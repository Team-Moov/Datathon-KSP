"""
Dual-source connection for the ML bridge.

The bridge reads Ananya's pipeline output. That output can live either in a
Postgres instance (the intended production path, `postgresql://...`) or in the
SQLite database the no-Postgres test harness produces (`.../test.db`). A DB-API
`sqlite3` connection exposes the same cursor().execute()/fetchall() surface the
bridge already uses, so detecting the DSN here keeps the sync scripts unchanged.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from typing import Optional


def open_ml_conn(dsn: str):
    if dsn.endswith(".db") or dsn.startswith("sqlite"):
        path = dsn.replace("sqlite:///", "").replace("sqlite://", "")
        return sqlite3.connect(path)
    import psycopg2

    return psycopg2.connect(dsn)


def as_date(v) -> Optional[date]:
    """SQLite hands dates back as strings; Postgres/asyncpg needs date objects."""
    if v is None or isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def as_dt(v) -> Optional[datetime]:
    if v is None or isinstance(v, datetime):
        return v
    s = str(v)
    for fmt in (s, s[:19], s[:10]):
        try:
            return datetime.fromisoformat(fmt)
        except ValueError:
            continue
    return None
