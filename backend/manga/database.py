"""SQLite access for the manga module: disposable index DB + user DB.

Schema changes are additive only (``CREATE TABLE IF NOT EXISTS`` plus
``_ensure_column``); the user DB is never dropped or rebuilt.
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterator

from manga.paths import MANGA_INDEX_DB_PATH, MANGA_USER_DB_PATH, ensure_module_dirs

_init_lock = threading.Lock()
_identity_lock = threading.Lock()
_initialized = False

INDEX_SCHEMA = """
CREATE TABLE IF NOT EXISTS manga (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL DEFAULT 'nhentai',
    gallery_id INTEGER NOT NULL,
    external_id TEXT,
    parent_external_id TEXT,
    media_id TEXT,
    root_id INTEGER,
    file_path TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    title_english TEXT,
    title_japanese TEXT,
    title_pretty TEXT,
    pages INTEGER,
    cover_name TEXT,
    cover_ext TEXT,
    favorites INTEGER,
    scanlator TEXT,
    upload_date INTEGER,
    raw_json TEXT,
    file_size INTEGER,
    matched INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    UNIQUE (source, gallery_id)
);
CREATE INDEX IF NOT EXISTS manga_gallery_idx ON manga (gallery_id);
CREATE INDEX IF NOT EXISTS manga_root_idx ON manga (root_id);
CREATE INDEX IF NOT EXISTS manga_title_idx ON manga (title);
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'tag',
    nh_id INTEGER,
    manga_count INTEGER NOT NULL DEFAULT 0,
    UNIQUE (name, category)
);
CREATE INDEX IF NOT EXISTS tags_category_idx ON tags (category);
CREATE TABLE IF NOT EXISTS manga_tags (
    manga_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (manga_id, tag_id)
);
CREATE INDEX IF NOT EXISTS manga_tags_tag_idx ON manga_tags (tag_id);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

USER_SCHEMA = """
CREATE TABLE IF NOT EXISTS roots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    label TEXT,
    added_at INTEGER NOT NULL,
    last_scan_at INTEGER
);
CREATE TABLE IF NOT EXISTS favorites (
    source TEXT NOT NULL,
    gallery_id INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (source, gallery_id)
);
CREATE TABLE IF NOT EXISTS pins (
    source TEXT NOT NULL,
    gallery_id INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (source, gallery_id)
);
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    position INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS category_items (
    category_id INTEGER NOT NULL,
    source TEXT NOT NULL,
    gallery_id INTEGER NOT NULL,
    PRIMARY KEY (category_id, source, gallery_id)
);
CREATE TABLE IF NOT EXISTS library_additions (
    source TEXT NOT NULL,
    gallery_id INTEGER NOT NULL,
    added_at INTEGER NOT NULL,
    PRIMARY KEY (source, gallery_id)
);
CREATE TABLE IF NOT EXISTS series (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS series_items (
    series_id INTEGER NOT NULL,
    source TEXT NOT NULL,
    gallery_id INTEGER NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    added_at INTEGER NOT NULL,
    PRIMARY KEY (source, gallery_id)
);
CREATE INDEX IF NOT EXISTS series_items_series_idx ON series_items (series_id, position);
CREATE TABLE IF NOT EXISTS reading_history (
    source TEXT NOT NULL,
    gallery_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    cover_path TEXT,
    last_page INTEGER NOT NULL DEFAULT 0,
    page_count INTEGER NOT NULL DEFAULT 0,
    started_at INTEGER NOT NULL,
    last_read_at INTEGER NOT NULL,
    completed_at INTEGER,
    PRIMARY KEY (source, gallery_id)
);
CREATE INDEX IF NOT EXISTS reading_history_recent_idx
    ON reading_history (last_read_at DESC, gallery_id DESC);
CREATE TABLE IF NOT EXISTS remote_identities (
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    gallery_id INTEGER NOT NULL UNIQUE,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (source, external_id)
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _configure(connection: sqlite3.Connection) -> sqlite3.Connection:
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def _initialize() -> None:
    global _initialized
    with _init_lock:
        if _initialized:
            return
        ensure_module_dirs()
        for path, schema in (
            (MANGA_INDEX_DB_PATH, INDEX_SCHEMA),
            (MANGA_USER_DB_PATH, USER_SCHEMA),
        ):
            connection = sqlite3.connect(path)
            try:
                connection.execute("PRAGMA journal_mode = WAL")
                connection.executescript(schema)
                connection.commit()
            finally:
                connection.close()
        index_connection = sqlite3.connect(MANGA_INDEX_DB_PATH)
        user_connection = sqlite3.connect(MANGA_USER_DB_PATH)
        try:
            # Additive migration: records when each manga joined a category so the
            # Library can offer a "recently added to category" sort. Rows written
            # before this column existed keep NULL and sort last.
            _ensure_column(user_connection, "category_items", "added_at", "INTEGER")
            _ensure_column(index_connection, "manga", "external_id", "TEXT")
            _ensure_column(index_connection, "manga", "parent_external_id", "TEXT")
            index_connection.execute(
                "CREATE INDEX IF NOT EXISTS manga_external_idx ON manga (source, external_id)"
            )
            index_connection.execute(
                "CREATE INDEX IF NOT EXISTS manga_parent_external_idx"
                " ON manga (source, parent_external_id)"
            )
            existing_additions = index_connection.execute(
                "SELECT source, gallery_id, created_at FROM manga"
            ).fetchall()
            user_connection.executemany(
                "INSERT OR IGNORE INTO library_additions (source, gallery_id, added_at)"
                " VALUES (?, ?, ?)",
                existing_additions,
            )
            user_connection.commit()
            index_connection.commit()
        finally:
            index_connection.close()
            user_connection.close()
        _initialized = True


def index_db() -> sqlite3.Connection:
    """Open a connection to the disposable manga index database."""
    _initialize()
    return _configure(sqlite3.connect(MANGA_INDEX_DB_PATH))


def user_db() -> sqlite3.Connection:
    """Open a connection to the irreplaceable manga user database."""
    _initialize()
    return _configure(sqlite3.connect(MANGA_USER_DB_PATH))


@contextmanager
def index_session() -> Iterator[sqlite3.Connection]:
    """Index-DB connection that commits on success and always closes."""
    connection = index_db()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


@contextmanager
def user_session() -> Iterator[sqlite3.Connection]:
    """User-DB connection that commits on success and always closes."""
    connection = user_db()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def get_setting(key: str, default: str | None = None) -> str | None:
    with user_session() as connection:
        row = connection.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row[0] if row is not None else default


def set_setting(key: str, value: str) -> None:
    with user_session() as connection:
        connection.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def get_meta(key: str, default: str | None = None) -> str | None:
    with index_session() as connection:
        row = connection.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row is not None else default


def set_meta(key: str, value: str) -> None:
    with index_session() as connection:
        connection.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def remote_gallery_id(source: str, external_id: str, *, create: bool = False) -> int | None:
    """Resolve an opaque provider ID to a stable negative local gallery key.

    The mapping lives in the preserved user database so rebuilding the disposable
    manga index never changes reading history, favourites, pins, or categories.
    Positive numeric nHentai IDs remain completely separate.
    """
    cleaned_source = (source or "").strip().lower()
    cleaned_id = (external_id or "").strip().lower()
    if not cleaned_source or not cleaned_id:
        return None
    with _identity_lock:
        with user_session() as connection:
            row = connection.execute(
                "SELECT gallery_id FROM remote_identities WHERE source = ? AND external_id = ?",
                (cleaned_source, cleaned_id),
            ).fetchone()
            if row is not None:
                return int(row[0])
            if not create:
                return None
            minimum = connection.execute(
                "SELECT MIN(gallery_id) FROM remote_identities"
            ).fetchone()[0]
            gallery_id = -1 if minimum is None or int(minimum) >= 0 else int(minimum) - 1
            connection.execute(
                "INSERT INTO remote_identities (source, external_id, gallery_id, created_at)"
                " VALUES (?, ?, ?, CAST(strftime('%s', 'now') AS INTEGER) * 1000)",
                (cleaned_source, cleaned_id, gallery_id),
            )
            return gallery_id


def remote_external_id(source: str, gallery_id: int) -> str | None:
    """Return the opaque provider ID belonging to a local negative key."""
    with user_session() as connection:
        row = connection.execute(
            "SELECT external_id FROM remote_identities WHERE source = ? AND gallery_id = ?",
            ((source or "").strip().lower(), int(gallery_id)),
        ).fetchone()
    return str(row[0]) if row is not None else None
