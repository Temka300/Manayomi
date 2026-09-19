"""Disposable Languages mirror and read-model catalog."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
from pathlib import Path
import sqlite3
from typing import Generator


SCHEMA = """
CREATE TABLE IF NOT EXISTS language_words (
    word_id TEXT PRIMARY KEY,
    lang TEXT NOT NULL,
    headword TEXT NOT NULL,
    sentence_form TEXT NOT NULL,
    reading TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL,
    source_key TEXT NOT NULL,
    note_type TEXT NOT NULL DEFAULT '',
    deck TEXT NOT NULL DEFAULT '',
    sort_index INTEGER,
    fields_json TEXT NOT NULL DEFAULT '{}',
    media_dir_rel TEXT,
    anki_mod INTEGER,
    missing INTEGER NOT NULL DEFAULT 0,
    suspended INTEGER NOT NULL DEFAULT 0,
    possible_duplicate INTEGER NOT NULL DEFAULT 0,
    added_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(source, source_key)
);
CREATE INDEX IF NOT EXISTS idx_language_words_order
    ON language_words(sort_index, headword COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_language_words_deck
    ON language_words(deck, sort_index);

CREATE TABLE IF NOT EXISTS language_senses (
    word_id TEXT NOT NULL,
    lang TEXT NOT NULL,
    position INTEGER NOT NULL,
    text TEXT NOT NULL,
    PRIMARY KEY(word_id, lang, position),
    FOREIGN KEY(word_id) REFERENCES language_words(word_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS language_examples (
    word_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    sentence TEXT NOT NULL,
    translation_json TEXT NOT NULL DEFAULT '[]',
    audio_rel TEXT,
    PRIMARY KEY(word_id, position),
    FOREIGN KEY(word_id) REFERENCES language_words(word_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS language_notes_text (
    word_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    body TEXT NOT NULL,
    PRIMARY KEY(word_id, kind, position),
    FOREIGN KEY(word_id) REFERENCES language_words(word_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS language_tags (
    word_id TEXT NOT NULL,
    name TEXT NOT NULL,
    PRIMARY KEY(word_id, name),
    FOREIGN KEY(word_id) REFERENCES language_words(word_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS language_media (
    media_id TEXT PRIMARY KEY,
    word_id TEXT NOT NULL,
    role TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    relative_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    bytes INTEGER NOT NULL,
    origin_filename TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    imported_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(word_id, role, position, sha256),
    FOREIGN KEY(word_id) REFERENCES language_words(word_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS language_progress (
    word_id TEXT NOT NULL,
    card_id TEXT NOT NULL,
    interval INTEGER NOT NULL DEFAULT 0,
    due INTEGER,
    reps INTEGER NOT NULL DEFAULT 0,
    lapses INTEGER NOT NULL DEFAULT 0,
    queue INTEGER,
    type INTEGER,
    stage TEXT NOT NULL DEFAULT 'new',
    card_mod INTEGER,
    due_now INTEGER NOT NULL DEFAULT 0,
    last_reviewed_at TEXT,
    synced_at TEXT NOT NULL,
    PRIMARY KEY(word_id, card_id),
    FOREIGN KEY(word_id) REFERENCES language_words(word_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS language_sync_runs (
    run_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    scope_json TEXT NOT NULL,
    counts_json TEXT NOT NULL DEFAULT '{}',
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS language_analysis_cache (
    cache_key TEXT PRIMARY KEY,
    source_text TEXT NOT NULL,
    engine_version TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS language_dictionary_cache (
    cache_key TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    query TEXT NOT NULL,
    response_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def word_id_for_source(source: str, source_key: str | int) -> str:
    """Return a stable identity unaffected by editable note fields."""
    normalized_source = source.strip().casefold()
    normalized_key = str(source_key).strip()
    if not normalized_source or not normalized_key:
        raise ValueError("Language word identities require a source and source key")
    identity = f"language-word\0{normalized_source}\0{normalized_key}".encode("utf-8")
    return hashlib.sha256(identity).hexdigest()


@contextmanager
def open_catalog(path: Path) -> Generator[sqlite3.Connection, None, None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.executescript(SCHEMA)
        connection.commit()
        yield connection
    finally:
        connection.close()
