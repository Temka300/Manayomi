"""Additive precious-data schema for the Languages module."""
from __future__ import annotations

import sqlite3


USER_SCHEMA = """
CREATE TABLE IF NOT EXISTS language_user_words (
    word_id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    retired_at TEXT,
    merged_into_word_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS language_user_overrides (
    word_id TEXT NOT NULL,
    field TEXT NOT NULL,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY(word_id, field)
);

CREATE TABLE IF NOT EXISTS language_user_notes (
    word_id TEXT PRIMARY KEY,
    body TEXT NOT NULL,
    retired_at TEXT,
    merged_into_word_id TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS language_user_media (
    media_id TEXT PRIMARY KEY,
    word_id TEXT NOT NULL,
    role TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    relative_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    bytes INTEGER NOT NULL,
    origin_filename TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    retired_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(word_id, role, position, sha256)
);

CREATE TABLE IF NOT EXISTS language_favorites (
    word_id TEXT PRIMARY KEY,
    added_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS language_word_lists (
    list_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    retired_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS language_word_list_items (
    list_id TEXT NOT NULL,
    word_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    retired_at TEXT,
    added_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY(list_id, word_id)
);

CREATE TABLE IF NOT EXISTS language_sync_scope (
    deck_pattern TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS language_profiles (
    note_type TEXT PRIMARY KEY,
    mapping_json TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS language_anki_settings (
    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
    port INTEGER NOT NULL DEFAULT 8765,
    sync_mode TEXT NOT NULL DEFAULT 'incremental',
    cached_probe_json TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS language_practice_sessions (
    session_id TEXT PRIMARY KEY,
    mode TEXT NOT NULL,
    set_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS language_practice_results (
    result_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    word_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    correct INTEGER NOT NULL,
    answered_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_language_practice_results_word
    ON language_practice_results(word_id, answered_at);

CREATE TABLE IF NOT EXISTS language_analyzer_saved (
    analysis_id TEXT PRIMARY KEY,
    source_text TEXT NOT NULL,
    translation_en TEXT NOT NULL DEFAULT '',
    translation_mn TEXT NOT NULL DEFAULT '',
    analysis_json TEXT NOT NULL,
    retired_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_language_analyzer_saved_active
    ON language_analyzer_saved(retired_at, updated_at);
"""


def ensure_user_schema(connection: sqlite3.Connection) -> None:
    """Create Languages-owned user tables without rewriting existing rows."""
    connection.executescript(USER_SCHEMA)
    note_columns: set[str] = set()
    for row in connection.execute(
        "PRAGMA table_info(language_user_notes)"
    ).fetchall():
        try:
            note_columns.add(str(row["name"]))
        except (KeyError, TypeError):
            note_columns.add(str(row[1]))
    if "retired_at" not in note_columns:
        connection.execute(
            "ALTER TABLE language_user_notes ADD COLUMN retired_at TEXT"
        )
    if "merged_into_word_id" not in note_columns:
        connection.execute(
            "ALTER TABLE language_user_notes ADD COLUMN merged_into_word_id TEXT"
        )
    connection.commit()
