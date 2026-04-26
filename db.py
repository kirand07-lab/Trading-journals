import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

from flask import current_app, g


def get_db() -> sqlite3.Connection:
    """
    Get a per-request SQLite connection.

    We store it in Flask's `g` so multiple route handlers can reuse it safely
    within the same request.
    """
    if "db" not in g:
        conn = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        g.db = conn
    return g.db


def close_db(_e: Optional[BaseException] = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    """Initialize the SQLite database using `schema.sql`."""
    db = get_db()
    schema_path = Path(current_app.root_path) / "schema.sql"
    db.executescript(schema_path.read_text(encoding="utf-8"))
    db.commit()


def query_one(sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
    cur = get_db().execute(sql, params)
    row = cur.fetchone()
    cur.close()
    return row


def query_all(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    cur = get_db().execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return rows


def execute(sql: str, params: tuple = ()) -> int:
    cur = get_db().execute(sql, params)
    get_db().commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id

