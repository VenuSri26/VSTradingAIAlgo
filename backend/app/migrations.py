"""Small transaction-safe SQLite migration runner."""
from __future__ import annotations
from pathlib import Path
import sqlite3

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


def apply_migrations(conn: sqlite3.Connection) -> list[str]:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    applied = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
    installed: list[str] = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = path.stem
        if version in applied:
            continue
        conn.executescript(path.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))
        installed.append(version)
    return installed
