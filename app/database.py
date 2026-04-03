from __future__ import annotations

import logging
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

try:
    from fastapi import FastAPI
except Exception:  # pragma: no cover - FastAPI may be unavailable in isolated tests
    FastAPI = Any  # type: ignore[misc,assignment]


logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data" / "private"
DATABASE_PATH = DATA_DIR / "tax_rag.db"
DB_PATH = DATABASE_PATH
TABLE_NAME = "documents"
FAVORITES_TABLE_NAME = "favorite_sources"

SCHEMA_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    is_private INTEGER NOT NULL DEFAULT 1,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    content TEXT NOT NULL,
    practical TEXT,
    date TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_documents_category ON {TABLE_NAME}(category);
CREATE INDEX IF NOT EXISTS idx_documents_date ON {TABLE_NAME}(date);
CREATE INDEX IF NOT EXISTS idx_documents_updated_at ON {TABLE_NAME}(updated_at);

CREATE TABLE IF NOT EXISTS {FAVORITES_TABLE_NAME} (
    favorite_id TEXT PRIMARY KEY,
    source_id TEXT,
    category TEXT NOT NULL,
    source_type TEXT,
    is_private INTEGER NOT NULL DEFAULT 0,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    reference TEXT,
    citation TEXT,
    detail_link TEXT,
    summary TEXT,
    date TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_favorite_sources_category ON {FAVORITES_TABLE_NAME}(category);
CREATE INDEX IF NOT EXISTS idx_favorite_sources_created_at ON {FAVORITES_TABLE_NAME}(created_at DESC);
"""


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    ensure_data_dir()
    connection = sqlite3.connect(DATABASE_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    try:
        ensure_data_dir()
        with closing(get_connection()) as connection:
            with connection:
                connection.executescript(SCHEMA_SQL)
    except sqlite3.Error as exc:
        logger.exception("Failed to initialize SQLite database at %s", DATABASE_PATH)
        raise RuntimeError("Failed to initialize SQLite database.") from exc


def init_db_on_startup() -> None:
    init_db()


def register_startup(app: FastAPI) -> None:
    @app.on_event("startup")
    def _initialize_database() -> None:
        init_db()


init_db()
