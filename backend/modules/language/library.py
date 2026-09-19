"""Languages read model, precious mutations, and local practice."""
from __future__ import annotations

import base64
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any
import uuid

from modules.language import catalog, storage, user_state


EDITABLE_FIELDS = {
    "lang",
    "headword",
    "sentence_form",
    "reading",
    "deck",
    "sort_index",
    "senses",
    "examples",
    "notes_text",
    "tags",
    "personal_note",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _loads(value: str | None, fallback: Any) -> Any:
    try:
        return json.loads(value) if value else fallback
    except (TypeError, ValueError):
        return fallback


def _row_dict(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    return dict(row)


def _allocate_media_dir(
    connection: sqlite3.Connection,
    lang: str,
    headword: str,
) -> str:
    clean_lang = storage.safe_word_key(lang, "und", 16).casefold()
    clean_word = storage.safe_word_key(headword, "word")
    base = f"{clean_lang}/{clean_word}"
    used = {
        str(row["media_dir_rel"])
        for row in connection.execute(
            "SELECT media_dir_rel FROM language_words "
            "WHERE media_dir_rel IS NOT NULL AND media_dir_rel<>''"
        ).fetchall()
    }
    if base not in used:
        return base
    suffix = 2
    while f"{base} {suffix}" in used:
        suffix += 1
    return f"{base} {suffix}"


def _payload_defaults(payload: dict[str, Any]) -> dict[str, Any]:
    headword = str(payload.get("headword") or "").strip()
    if not headword:
        raise ValueError("Headword is required")
    lang = str(payload.get("lang") or "ko").strip().casefold() or "ko"
    sentence_form = str(payload.get("sentence_form") or "").strip() or headword
    senses = payload.get("senses") if isinstance(payload.get("senses"), list) else []
    examples = payload.get("examples") if isinstance(payload.get("examples"), list) else []
    notes_text = (
        payload.get("notes_text") if isinstance(payload.get("notes_text"), list) else []
    )
    tags = payload.get("tags") if isinstance(payload.get("tags"), list) else []
    return {
        "lang": lang[:16],
        "headword": headword[:300],
        "sentence_form": sentence_form[:300],
        "reading": str(payload.get("reading") or "").strip()[:300],
        "deck": str(payload.get("deck") or "Keivotos").strip()[:500] or "Keivotos",
        "sort_index": payload.get("sort_index"),
        "senses": [
            {
                "lang": str(value.get("lang") or "und").strip().casefold()[:16],
                "text": str(value.get("text") or "").strip(),
            }
            for value in senses
            if isinstance(value, dict) and str(value.get("text") or "").strip()
        ],
        "examples": [
            {
                "sentence": str(value.get("sentence") or "").strip(),
                "translations": [
                    {
                        "lang": str(item.get("lang") or "und").strip().casefold()[:16],
                        "text": str(item.get("text") or "").strip(),
                    }
                    for item in value.get("translations", [])
                    if isinstance(item, dict) and str(item.get("text") or "").strip()
                ],
            }
            for value in examples
            if isinstance(value, dict) and str(value.get("sentence") or "").strip()
        ],
        "notes_text": [
            {
                "kind": str(value.get("kind") or "usage").strip().casefold()[:40],
                "body": str(value.get("body") or "").strip(),
            }
            for value in notes_text
            if isinstance(value, dict) and str(value.get("body") or "").strip()
        ],
        "tags": sorted(
            {
                str(value).strip()
                for value in tags
                if str(value).strip()
            },
            key=str.casefold,
        ),
        "personal_note": str(payload.get("personal_note") or "").strip(),
    }


def _replace_projection_children(
    connection: sqlite3.Connection,
    word_id: str,
    payload: dict[str, Any],
) -> None:
    for table in (
        "language_senses",
        "language_examples",
        "language_notes_text",
        "language_tags",
    ):
        connection.execute(f"DELETE FROM {table} WHERE word_id=?", (word_id,))
    for position, sense in enumerate(payload["senses"]):
        connection.execute(
            "INSERT INTO language_senses(word_id, lang, position, text) "
            "VALUES (?, ?, ?, ?)",
            (word_id, sense["lang"], position, sense["text"]),
        )
    for position, example in enumerate(payload["examples"]):
        connection.execute(
            "INSERT INTO language_examples"
            "(word_id, position, sentence, translation_json) VALUES (?, ?, ?, ?)",
            (
                word_id,
                position,
                example["sentence"],
                json.dumps(example["translations"], ensure_ascii=False),
            ),
        )
    for position, note in enumerate(payload["notes_text"]):
        connection.execute(
            "INSERT INTO language_notes_text(word_id, kind, position, body) "
            "VALUES (?, ?, ?, ?)",
            (word_id, note["kind"], position, note["body"]),
        )
    for tag in payload["tags"]:
        connection.execute(
            "INSERT INTO language_tags(word_id, name) VALUES (?, ?)",
            (word_id, tag),
        )


def project_manual_word(
    connection: sqlite3.Connection,
    word_id: str,
    payload: dict[str, Any],
) -> None:
    normalized = _payload_defaults(payload)
    existing = connection.execute(
        "SELECT media_dir_rel, added_at FROM language_words WHERE word_id=?",
        (word_id,),
    ).fetchone()
    media_dir_rel = (
        existing["media_dir_rel"]
        if existing is not None and existing["media_dir_rel"]
        else _allocate_media_dir(
            connection,
            normalized["lang"],
            normalized["headword"],
        )
    )
    added_at = existing["added_at"] if existing is not None else _now()
    connection.execute(
        """INSERT INTO language_words
           (word_id, lang, headword, sentence_form, reading, source, source_key,
            note_type, deck, sort_index, fields_json, media_dir_rel,
            added_at, updated_at)
           VALUES (?, ?, ?, ?, ?, 'manual', ?, 'Keivotos', ?, ?, '{}', ?, ?, ?)
           ON CONFLICT(word_id) DO UPDATE SET
             lang=excluded.lang, headword=excluded.headword,
             sentence_form=excluded.sentence_form, reading=excluded.reading,
             deck=excluded.deck, sort_index=excluded.sort_index,
             media_dir_rel=excluded.media_dir_rel, missing=0,
             suspended=0, updated_at=excluded.updated_at""",
        (
            word_id,
            normalized["lang"],
            normalized["headword"],
            normalized["sentence_form"],
            normalized["reading"],
            word_id,
            normalized["deck"],
            normalized["sort_index"],
            media_dir_rel,
            added_at,
            _now(),
        ),
    )
    _replace_projection_children(connection, word_id, normalized)
    connection.commit()


def reconcile_manual_projections(
    catalog_connection: sqlite3.Connection,
    user_connection: sqlite3.Connection,
) -> None:
    user_state.ensure_user_schema(user_connection)
    active_ids: set[str] = set()
    for row in user_connection.execute(
        "SELECT word_id, payload_json FROM language_user_words "
        "WHERE retired_at IS NULL"
    ).fetchall():
        active_ids.add(str(row["word_id"]))
        project_manual_word(
            catalog_connection,
            str(row["word_id"]),
            _loads(row["payload_json"], {}),
        )
    rows = catalog_connection.execute(
        "SELECT word_id FROM language_words WHERE source='manual'"
    ).fetchall()
    for row in rows:
        if str(row["word_id"]) not in active_ids:
            catalog_connection.execute(
                "DELETE FROM language_words WHERE word_id=?",
                (row["word_id"],),
            )
    catalog_connection.commit()


def create_manual_word(
    catalog_connection: sqlite3.Connection,
    user_connection: sqlite3.Connection,
    payload: dict[str, Any],
) -> str:
    user_state.ensure_user_schema(user_connection)
    normalized = _payload_defaults(payload)
    source_key = uuid.uuid4().hex
    word_id = catalog.word_id_for_source("manual", source_key)
    user_connection.execute(
        "INSERT INTO language_user_words(word_id, payload_json) VALUES (?, ?)",
        (
            word_id,
            json.dumps(normalized, ensure_ascii=False, sort_keys=True),
        ),
    )
    if normalized["personal_note"]:
        user_connection.execute(
            "INSERT INTO language_user_notes(word_id, body) VALUES (?, ?)",
            (word_id, normalized["personal_note"]),
        )
    user_connection.commit()
    project_manual_word(catalog_connection, word_id, normalized)
    return word_id


def _child_rows(
    connection: sqlite3.Connection,
    word_id: str,
) -> dict[str, Any]:
    senses = [
        _row_dict(row)
        for row in connection.execute(
            "SELECT lang, position, text FROM language_senses "
            "WHERE word_id=? ORDER BY position",
            (word_id,),
        ).fetchall()
    ]
    examples = []
    for row in connection.execute(
        "SELECT position, sentence, translation_json, audio_rel "
        "FROM language_examples WHERE word_id=? ORDER BY position",
        (word_id,),
    ).fetchall():
        value = _row_dict(row)
        value["translations"] = _loads(value.pop("translation_json"), [])
        examples.append(value)
    notes_text = [
        _row_dict(row)
        for row in connection.execute(
            "SELECT kind, position, body FROM language_notes_text "
            "WHERE word_id=? ORDER BY kind, position",
            (word_id,),
        ).fetchall()
    ]
    tags = [
        str(row["name"])
        for row in connection.execute(
            "SELECT name FROM language_tags WHERE word_id=? "
            "ORDER BY name COLLATE NOCASE",
            (word_id,),
        ).fetchall()
    ]
    media = [
        _row_dict(row)
        for row in connection.execute(
            "SELECT media_id, role, position, relative_path, sha256, bytes, "
            "origin_filename, active, imported_at FROM language_media "
            "WHERE word_id=? AND active<>0 ORDER BY role, position, imported_at",
            (word_id,),
        ).fetchall()
    ]
    progress = [
        _row_dict(row)
        for row in connection.execute(
            "SELECT card_id, interval, due, reps, lapses, queue, type, stage, "
            "card_mod, due_now, last_reviewed_at, synced_at "
            "FROM language_progress WHERE word_id=? ORDER BY card_id",
            (word_id,),
        ).fetchall()
    ]
    return {
        "senses": senses,
        "examples": examples,
        "notes_text": notes_text,
        "tags": tags,
        "media": media,
        "progress": progress,
    }


def _weakest_stage(progress: list[dict[str, Any]]) -> tuple[str, int]:
    if not progress:
        return "new", 0
    weakest = min(progress, key=lambda row: int(row.get("interval") or 0))
    return str(weakest.get("stage") or "new"), int(weakest.get("interval") or 0)


def effective_word(
    catalog_connection: sqlite3.Connection,
    user_connection: sqlite3.Connection,
    word_id: str,
) -> dict[str, Any] | None:
    row = catalog_connection.execute(
        "SELECT * FROM language_words WHERE word_id=?",
        (word_id,),
    ).fetchone()
    if row is None:
        return None
    value = _row_dict(row)
    value["fields"] = _loads(value.pop("fields_json"), {})
    value.update(_child_rows(catalog_connection, word_id))
    overrides: dict[str, Any] = {}
    for override in user_connection.execute(
        "SELECT field, value_json FROM language_user_overrides WHERE word_id=?",
        (word_id,),
    ).fetchall():
        overrides[str(override["field"])] = _loads(override["value_json"], None)
    for field, override_value in overrides.items():
        if field in EDITABLE_FIELDS and field != "personal_note":
            value[field] = override_value
    note = user_connection.execute(
        "SELECT body FROM language_user_notes "
        "WHERE word_id=? AND retired_at IS NULL",
        (word_id,),
    ).fetchone()
    value["personal_note"] = str(note["body"]) if note is not None else ""
    value["favorite"] = (
        user_connection.execute(
            "SELECT 1 FROM language_favorites WHERE word_id=?",
            (word_id,),
        ).fetchone()
        is not None
    )
    value["overridden_fields"] = sorted(overrides)
    value["edited"] = bool(overrides)
    manual_media = [
        _row_dict(media)
        for media in user_connection.execute(
            "SELECT media_id, role, position, relative_path, sha256, bytes, "
            "origin_filename, active, created_at AS imported_at "
            "FROM language_user_media WHERE word_id=? AND active<>0 "
            "ORDER BY role, position, created_at",
            (word_id,),
        ).fetchall()
    ]
    manual_media_ids = {str(media["media_id"]) for media in manual_media}
    value["media"] = [
        *manual_media,
        *[
            media
            for media in value["media"]
            if str(media["media_id"]) not in manual_media_ids
        ],
    ]
    value["media_by_role"] = {
        role: next(
            (
                media
                for media in value["media"]
                if str(media.get("role")) == role and bool(media.get("active"))
            ),
            None,
        )
        for role in ("word_audio", "sentence_audio", "image")
    }
    stage, weakest_interval = _weakest_stage(value["progress"])
    value["stage"] = stage
    value["weakest_interval"] = weakest_interval
    value["due_now"] = any(bool(row.get("due_now")) for row in value["progress"])
    value["last_reviewed_at"] = max(
        (
            str(row["last_reviewed_at"])
            for row in value["progress"]
            if row.get("last_reviewed_at")
        ),
        default=None,
    )
    stats = user_connection.execute(
        "SELECT COUNT(*) AS answers, "
        "SUM(CASE WHEN correct<>0 THEN 1 ELSE 0 END) AS correct "
        "FROM language_practice_results WHERE word_id=?",
        (word_id,),
    ).fetchone()
    answers = int(stats["answers"] or 0)
    correct = int(stats["correct"] or 0)
    value["practice"] = {
        "answers": answers,
        "correct": correct,
        "accuracy": (correct / answers) if answers else None,
    }
    for key in ("missing", "suspended", "possible_duplicate"):
        value[key] = bool(value[key])
    return value


def list_words(
    catalog_connection: sqlite3.Connection,
    user_connection: sqlite3.Connection,
    *,
    query: str = "",
    deck: str = "",
    tag: str = "",
    stage: str = "",
    source: str = "",
    favorites: bool = False,
    missing: bool | None = None,
    suspended: bool | None = None,
    list_id: str = "",
    content: str = "all",
    sort: str = "index",
    descending: bool = False,
    offset: int = 0,
    limit: int = 60,
) -> tuple[list[dict[str, Any]], int]:
    if content not in {"all", "sentences", "grammar"}:
        raise ValueError("content must be all, sentences, or grammar")
    reconcile_manual_projections(catalog_connection, user_connection)
    rows = catalog_connection.execute(
        "SELECT word_id FROM language_words"
    ).fetchall()
    list_members: set[str] | None = None
    if list_id:
        list_members = {
            str(row["word_id"])
            for row in user_connection.execute(
                "SELECT word_id FROM language_word_list_items "
                "WHERE list_id=? AND retired_at IS NULL",
                (list_id,),
            ).fetchall()
        }
    needle = query.strip().casefold()
    words: list[dict[str, Any]] = []
    for row in rows:
        word = effective_word(
            catalog_connection,
            user_connection,
            str(row["word_id"]),
        )
        if word is None:
            continue
        searchable = " ".join(
            [
                str(word.get("headword") or ""),
                str(word.get("sentence_form") or ""),
                str(word.get("reading") or ""),
                " ".join(str(value.get("text") or "") for value in word["senses"]),
                " ".join(word["tags"]),
            ]
        ).casefold()
        if needle and needle not in searchable:
            continue
        if deck and word["deck"] != deck:
            continue
        if tag and tag not in word["tags"]:
            continue
        if stage and word["stage"] != stage:
            continue
        if source and word["source"] != source:
            continue
        if favorites and not word["favorite"]:
            continue
        if missing is not None and bool(word["missing"]) != missing:
            continue
        if suspended is not None and bool(word["suspended"]) != suspended:
            continue
        if list_members is not None and word["word_id"] not in list_members:
            continue
        if content == "sentences" and not word["examples"]:
            continue
        if content == "grammar" and not any(
            note.get("kind") == "grammar" for note in word["notes_text"]
        ):
            continue
        words.append(word)
    def sense_text(word: dict[str, Any], language: str) -> str:
        return next(
            (
                str(sense.get("text") or "").strip()
                for sense in word["senses"]
                if str(sense.get("lang") or "") == language
            ),
            "",
        )

    sorters = {
        "headword": lambda word: str(word["headword"]).casefold(),
        "korean": lambda word: str(word["headword"]).casefold(),
        "sentence_form": lambda word: str(word["sentence_form"]).casefold(),
        "source": lambda word: (
            str(word["source"]).casefold(),
            str(word["headword"]).casefold(),
        ),
        "note_type": lambda word: (
            str(word["note_type"]).casefold(),
            str(word["headword"]).casefold(),
        ),
        "updated": lambda word: str(word["updated_at"]),
        "interval": lambda word: int(word["weakest_interval"]),
        "due": lambda word: (
            not bool(word["due_now"]),
            min(
                (
                    int(progress["due"])
                    for progress in word["progress"]
                    if progress.get("due") is not None
                ),
                default=10**12,
            ),
        ),
        "media": lambda word: sum(
            bool(word["media_by_role"].get(role))
            for role in ("word_audio", "sentence_audio", "image")
        ),
        "flags": lambda word: (
            bool(word["missing"]),
            bool(word["suspended"]),
            bool(word["edited"]),
        ),
        "deck": lambda word: (str(word["deck"]).casefold(), word["sort_index"] or 10**9),
        "index": lambda word: (
            word["sort_index"] is None,
            word["sort_index"] if word["sort_index"] is not None else 10**9,
            str(word["headword"]).casefold(),
        ),
    }
    if sort in {"english", "mongolian"}:
        language = "en" if sort == "english" else "mn"
        present = [word for word in words if sense_text(word, language)]
        absent = [word for word in words if not sense_text(word, language)]
        present.sort(
            key=lambda word: (
                sense_text(word, language).casefold(),
                str(word["headword"]).casefold(),
            ),
            reverse=descending,
        )
        absent.sort(key=lambda word: str(word["headword"]).casefold())
        words = [*present, *absent]
    else:
        words.sort(key=sorters.get(sort, sorters["index"]), reverse=descending)
    total = len(words)
    return words[offset : offset + limit], total


def update_word(
    catalog_connection: sqlite3.Connection,
    user_connection: sqlite3.Connection,
    word_id: str,
    changes: dict[str, Any],
) -> None:
    current = effective_word(catalog_connection, user_connection, word_id)
    if current is None:
        raise ValueError("Unknown Languages word")
    selected = {key: value for key, value in changes.items() if key in EDITABLE_FIELDS}
    if not selected:
        raise ValueError("No editable fields were supplied")
    if current["source"] == "manual":
        row = user_connection.execute(
            "SELECT payload_json FROM language_user_words "
            "WHERE word_id=? AND retired_at IS NULL",
            (word_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Manual word source is unavailable")
        payload = _loads(row["payload_json"], {})
        payload.update({key: value for key, value in selected.items() if key != "personal_note"})
        normalized = _payload_defaults(payload)
        user_connection.execute(
            "UPDATE language_user_words SET payload_json=?, updated_at=? "
            "WHERE word_id=?",
            (
                json.dumps(normalized, ensure_ascii=False, sort_keys=True),
                _now(),
                word_id,
            ),
        )
        project_manual_word(catalog_connection, word_id, normalized)
    else:
        for field, value in selected.items():
            if field == "personal_note":
                continue
            user_connection.execute(
                "INSERT INTO language_user_overrides(word_id, field, value_json, updated_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(word_id, field) DO UPDATE SET "
                "value_json=excluded.value_json, updated_at=excluded.updated_at",
                (
                    word_id,
                    field,
                    json.dumps(value, ensure_ascii=False, sort_keys=True),
                    _now(),
                ),
            )
    if "personal_note" in selected:
        body = str(selected["personal_note"] or "").strip()
        if body:
            user_connection.execute(
                "INSERT INTO language_user_notes"
                "(word_id, body, retired_at, merged_into_word_id, updated_at) "
                "VALUES (?, ?, NULL, NULL, ?) ON CONFLICT(word_id) DO UPDATE SET "
                "body=excluded.body, retired_at=NULL, merged_into_word_id=NULL, "
                "updated_at=excluded.updated_at",
                (word_id, body, _now()),
            )
        else:
            user_connection.execute(
                "UPDATE language_user_notes SET retired_at=?, updated_at=? "
                "WHERE word_id=? AND retired_at IS NULL",
                (_now(), _now(), word_id),
            )
    user_connection.commit()


def revert_overrides(
    user_connection: sqlite3.Connection,
    word_id: str,
    field: str | None = None,
) -> int:
    if field:
        changed = user_connection.execute(
            "DELETE FROM language_user_overrides WHERE word_id=? AND field=?",
            (word_id, field),
        ).rowcount
    else:
        changed = user_connection.execute(
            "DELETE FROM language_user_overrides WHERE word_id=?",
            (word_id,),
        ).rowcount
    user_connection.commit()
    return max(changed, 0)


def retire_manual_word(
    catalog_connection: sqlite3.Connection,
    user_connection: sqlite3.Connection,
    word_id: str,
) -> None:
    row = catalog_connection.execute(
        "SELECT source FROM language_words WHERE word_id=?",
        (word_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Unknown Languages word")
    if row["source"] != "manual":
        raise ValueError("Mirrored Anki words cannot be deleted")
    changed = user_connection.execute(
        "UPDATE language_user_words SET retired_at=?, updated_at=? "
        "WHERE word_id=? AND retired_at IS NULL",
        (_now(), _now(), word_id),
    ).rowcount
    if changed != 1:
        raise ValueError("Manual word is already retired")
    user_connection.execute(
        "UPDATE language_user_media SET active=0, retired_at=? "
        "WHERE word_id=? AND retired_at IS NULL",
        (_now(), word_id),
    )
    user_connection.commit()
    catalog_connection.execute(
        "DELETE FROM language_words WHERE word_id=?",
        (word_id,),
    )
    catalog_connection.commit()


def set_favorite(
    user_connection: sqlite3.Connection,
    word_id: str,
    favorite: bool,
) -> bool:
    user_state.ensure_user_schema(user_connection)
    if favorite:
        user_connection.execute(
            "INSERT OR IGNORE INTO language_favorites(word_id) VALUES (?)",
            (word_id,),
        )
    else:
        user_connection.execute(
            "DELETE FROM language_favorites WHERE word_id=?",
            (word_id,),
        )
    user_connection.commit()
    return favorite


def list_word_lists(user_connection: sqlite3.Connection) -> list[dict[str, Any]]:
    user_state.ensure_user_schema(user_connection)
    values = []
    for row in user_connection.execute(
        "SELECT list_id, name, description, created_at, updated_at "
        "FROM language_word_lists WHERE retired_at IS NULL "
        "ORDER BY updated_at DESC, name COLLATE NOCASE"
    ).fetchall():
        item = _row_dict(row)
        item["word_ids"] = [
            str(child["word_id"])
            for child in user_connection.execute(
                "SELECT word_id FROM language_word_list_items "
                "WHERE list_id=? AND retired_at IS NULL ORDER BY position",
                (row["list_id"],),
            ).fetchall()
        ]
        values.append(item)
    return values


def create_word_list(
    user_connection: sqlite3.Connection,
    name: str,
    description: str,
) -> dict[str, Any]:
    clean = name.strip()
    if not clean:
        raise ValueError("List name is required")
    list_id = uuid.uuid4().hex
    user_connection.execute(
        "INSERT INTO language_word_lists(list_id, name, description) "
        "VALUES (?, ?, ?)",
        (list_id, clean, description.strip()),
    )
    user_connection.commit()
    return next(
        value
        for value in list_word_lists(user_connection)
        if value["list_id"] == list_id
    )


def update_word_list(
    user_connection: sqlite3.Connection,
    list_id: str,
    *,
    name: str,
    description: str,
) -> dict[str, Any]:
    clean = name.strip()
    if not clean:
        raise ValueError("List name is required")
    changed = user_connection.execute(
        "UPDATE language_word_lists SET name=?, description=?, updated_at=? "
        "WHERE list_id=? AND retired_at IS NULL",
        (clean, description.strip(), _now(), list_id),
    ).rowcount
    if changed != 1:
        raise ValueError("Unknown Languages list")
    user_connection.commit()
    return next(
        value
        for value in list_word_lists(user_connection)
        if value["list_id"] == list_id
    )


def retire_word_list(user_connection: sqlite3.Connection, list_id: str) -> None:
    changed = user_connection.execute(
        "UPDATE language_word_lists SET retired_at=?, updated_at=? "
        "WHERE list_id=? AND retired_at IS NULL",
        (_now(), _now(), list_id),
    ).rowcount
    if changed != 1:
        raise ValueError("Unknown Languages list")
    user_connection.execute(
        "UPDATE language_word_list_items SET retired_at=? "
        "WHERE list_id=? AND retired_at IS NULL",
        (_now(), list_id),
    )
    user_connection.commit()


def set_list_membership(
    user_connection: sqlite3.Connection,
    list_id: str,
    word_ids: list[str],
    member: bool,
) -> int:
    exists = user_connection.execute(
        "SELECT 1 FROM language_word_lists "
        "WHERE list_id=? AND retired_at IS NULL",
        (list_id,),
    ).fetchone()
    if exists is None:
        raise ValueError("Unknown Languages list")
    changed = 0
    for word_id in dict.fromkeys(word_ids):
        if member:
            position = user_connection.execute(
                "SELECT COALESCE(MAX(position), -1)+1 AS position "
                "FROM language_word_list_items "
                "WHERE list_id=? AND retired_at IS NULL",
                (list_id,),
            ).fetchone()["position"]
            user_connection.execute(
                "INSERT INTO language_word_list_items"
                "(list_id, word_id, position, retired_at) VALUES (?, ?, ?, NULL) "
                "ON CONFLICT(list_id, word_id) DO UPDATE SET "
                "position=excluded.position, retired_at=NULL",
                (list_id, word_id, int(position)),
            )
        else:
            user_connection.execute(
                "UPDATE language_word_list_items SET retired_at=? "
                "WHERE list_id=? AND word_id=? AND retired_at IS NULL",
                (_now(), list_id, word_id),
            )
        changed += 1
    user_connection.execute(
        "UPDATE language_word_lists SET updated_at=? WHERE list_id=?",
        (_now(), list_id),
    )
    user_connection.commit()
    return changed


def attach_media(
    catalog_connection: sqlite3.Connection,
    user_connection: sqlite3.Connection,
    library_root: Path,
    *,
    word_id: str,
    role: str,
    filename: str,
    payload: bytes,
) -> dict[str, Any]:
    if role not in {"word_audio", "sentence_audio", "image"}:
        raise ValueError("Unsupported Languages media role")
    word = catalog_connection.execute(
        "SELECT word_id, media_dir_rel FROM language_words WHERE word_id=?",
        (word_id,),
    ).fetchone()
    if word is None:
        raise ValueError("Unknown Languages word")
    digest = hashlib.sha256(payload).hexdigest()
    relative_path = (
        Path(str(word["media_dir_rel"]))
        / storage.versioned_media_name(role, digest, filename)
    ).as_posix()
    destination = storage.resolve_within(library_root, relative_path)
    if destination.exists():
        existing_digest, existing_bytes = storage.hash_file(destination)
        if existing_digest != digest or existing_bytes != len(payload):
            raise storage.LanguageStorageError(
                "Existing Languages media does not match the requested bytes"
            )
    else:
        storage.write_bytes_create(destination, payload)
    user_connection.execute(
        "UPDATE language_user_media SET active=0, retired_at=? "
        "WHERE word_id=? AND role=? AND active<>0",
        (_now(), word_id, role),
    )
    catalog_connection.execute(
        "UPDATE language_media SET active=0 WHERE word_id=? AND role=? AND active<>0",
        (word_id, role),
    )
    media_id = uuid.uuid4().hex
    user_connection.execute(
        """INSERT INTO language_user_media
           (media_id, word_id, role, position, relative_path, sha256, bytes,
            origin_filename, active)
           VALUES (?, ?, ?, 0, ?, ?, ?, ?, 1)""",
        (
            media_id,
            word_id,
            role,
            relative_path,
            digest,
            len(payload),
            Path(filename).name,
        ),
    )
    catalog_connection.execute(
        """INSERT INTO language_media
           (media_id, word_id, role, position, relative_path, sha256, bytes,
            origin_filename, active)
           VALUES (?, ?, ?, 0, ?, ?, ?, ?, 1)""",
        (
            media_id,
            word_id,
            role,
            relative_path,
            digest,
            len(payload),
            Path(filename).name,
        ),
    )
    user_connection.commit()
    catalog_connection.commit()
    return {
        "media_id": media_id,
        "word_id": word_id,
        "role": role,
        "relative_path": relative_path,
        "sha256": digest,
        "bytes": len(payload),
        "origin_filename": Path(filename).name,
    }


def media_for_role(
    catalog_connection: sqlite3.Connection,
    user_connection: sqlite3.Connection,
    word_id: str,
    role: str,
) -> dict[str, Any] | None:
    row = user_connection.execute(
        "SELECT media_id, relative_path, sha256, bytes, origin_filename "
        "FROM language_user_media WHERE word_id=? AND role=? AND active<>0 "
        "ORDER BY created_at DESC LIMIT 1",
        (word_id, role),
    ).fetchone()
    if row is not None:
        return _row_dict(row)
    row = catalog_connection.execute(
        "SELECT media_id, relative_path, sha256, bytes, origin_filename "
        "FROM language_media WHERE word_id=? AND role=? AND active<>0 "
        "ORDER BY imported_at DESC LIMIT 1",
        (word_id, role),
    ).fetchone()
    return _row_dict(row) if row is not None else None


def create_practice_session(
    user_connection: sqlite3.Connection,
    *,
    mode: str,
    word_ids: list[str],
    length: int | None,
) -> dict[str, Any]:
    if mode not in {"ko_meaning", "meaning_ko", "audio_meaning", "cloze"}:
        raise ValueError("Unknown practice mode")
    unique = list(dict.fromkeys(word_ids))
    if length is not None:
        unique = unique[:length]
    if not unique:
        raise ValueError("Practice needs at least one word")
    session_id = uuid.uuid4().hex
    user_connection.execute(
        "INSERT INTO language_practice_sessions"
        "(session_id, mode, set_json, status) VALUES (?, ?, ?, 'active')",
        (session_id, mode, json.dumps(unique)),
    )
    user_connection.commit()
    return {
        "session_id": session_id,
        "mode": mode,
        "word_ids": unique,
        "status": "active",
    }


def answer_practice(
    user_connection: sqlite3.Connection,
    *,
    session_id: str,
    word_id: str,
    correct: bool,
    finish: bool,
) -> dict[str, Any]:
    session = user_connection.execute(
        "SELECT mode, status FROM language_practice_sessions WHERE session_id=?",
        (session_id,),
    ).fetchone()
    if session is None:
        raise ValueError("Unknown practice session")
    result_id = uuid.uuid4().hex
    user_connection.execute(
        "INSERT INTO language_practice_results"
        "(result_id, session_id, word_id, mode, correct) VALUES (?, ?, ?, ?, ?)",
        (result_id, session_id, word_id, session["mode"], int(correct)),
    )
    if finish:
        user_connection.execute(
            "UPDATE language_practice_sessions SET status='completed', "
            "finished_at=? WHERE session_id=?",
            (_now(), session_id),
        )
    user_connection.commit()
    return {
        "result_id": result_id,
        "session_id": session_id,
        "word_id": word_id,
        "correct": correct,
        "finished": finish,
    }


def practice_stats(user_connection: sqlite3.Connection) -> dict[str, Any]:
    rows = user_connection.execute(
        "SELECT word_id, COUNT(*) AS answers, "
        "SUM(CASE WHEN correct<>0 THEN 1 ELSE 0 END) AS correct, "
        "MAX(answered_at) AS last_answered_at "
        "FROM language_practice_results GROUP BY word_id"
    ).fetchall()
    summary = user_connection.execute(
        """
        SELECT COUNT(*) AS answers,
               SUM(CASE WHEN correct<>0 THEN 1 ELSE 0 END) AS correct,
               COUNT(DISTINCT word_id) AS practiced_words
        FROM language_practice_results
        """
    ).fetchone()
    sessions = user_connection.execute(
        "SELECT COUNT(*) AS sessions, "
        "SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS completed "
        "FROM language_practice_sessions"
    ).fetchone()
    activity_rows = user_connection.execute(
        """
        SELECT date(answered_at) AS day, COUNT(*) AS answers,
               SUM(CASE WHEN correct<>0 THEN 1 ELSE 0 END) AS correct
        FROM language_practice_results
        GROUP BY date(answered_at)
        ORDER BY day DESC
        LIMIT 365
        """
    ).fetchall()
    activity = [
        {
            "date": str(row["day"]),
            "answers": int(row["answers"]),
            "correct": int(row["correct"] or 0),
            "accuracy": (
                int(row["correct"] or 0) / int(row["answers"])
                if int(row["answers"])
                else None
            ),
        }
        for row in activity_rows
    ]
    active_days = {entry["date"] for entry in activity}
    cursor: date = datetime.now(timezone.utc).date()
    current_streak = 0
    while cursor.isoformat() in active_days:
        current_streak += 1
        cursor -= timedelta(days=1)
    answers = int(summary["answers"] or 0)
    correct = int(summary["correct"] or 0)
    return {
        "totals": {
            "sessions": int(sessions["sessions"] or 0),
            "completed_sessions": int(sessions["completed"] or 0),
            "answers": answers,
            "correct": correct,
            "accuracy": correct / answers if answers else None,
            "practiced_words": int(summary["practiced_words"] or 0),
        },
        "activity": activity,
        "streak": {
            "current_days": current_streak,
            "active_days": len(active_days),
        },
        "words": [
            {
                "word_id": row["word_id"],
                "answers": int(row["answers"]),
                "correct": int(row["correct"] or 0),
                "accuracy": (
                    int(row["correct"] or 0) / int(row["answers"])
                    if int(row["answers"])
                    else None
                ),
                "last_answered_at": row["last_answered_at"],
            }
            for row in rows
        ]
    }


def analyzer_library_context(
    catalog_connection: sqlite3.Connection,
    user_connection: sqlite3.Connection,
    *,
    source_text: str,
    tokens: list[dict[str, Any]],
) -> dict[str, Any]:
    """Match analyzed lemmas to the effective local library in one pass."""
    candidates_by_token = {
        int(token["token_index"]): {
            str(token.get("surface") or "").strip().casefold(),
            str(token.get("form") or "").strip().casefold(),
            str(token.get("lemma") or "").strip().casefold(),
            str(token.get("group_lemma") or "").strip().casefold(),
        }
        for token in tokens
    }
    all_candidates = {
        candidate
        for candidates in candidates_by_token.values()
        for candidate in candidates
        if candidate
    }
    token_matches: dict[str, list[dict[str, Any]]] = {
        str(index): [] for index in candidates_by_token
    }
    exact_example: dict[str, Any] | None = None
    normalized_text = " ".join(source_text.split()).casefold()
    word_ids = [
        str(row["word_id"])
        for row in catalog_connection.execute(
            "SELECT word_id FROM language_words"
        ).fetchall()
    ]
    for word_id in word_ids:
        word = effective_word(catalog_connection, user_connection, word_id)
        if word is None:
            continue
        names = {
            str(word.get("headword") or "").strip().casefold(),
            str(word.get("sentence_form") or "").strip().casefold(),
        }
        if names & all_candidates:
            english = next(
                (
                    str(sense.get("text") or "")
                    for sense in word["senses"]
                    if sense.get("lang") == "en"
                ),
                "",
            )
            mongolian = next(
                (
                    str(sense.get("text") or "")
                    for sense in word["senses"]
                    if sense.get("lang") == "mn"
                ),
                "",
            )
            summary = {
                "word_id": word_id,
                "headword": word["headword"],
                "sentence_form": word["sentence_form"],
                "english": english,
                "mongolian": mongolian,
                "source": word["source"],
                "stage": word["stage"],
                "has_word_audio": bool(word["media_by_role"]["word_audio"]),
                "has_sentence_audio": bool(word["media_by_role"]["sentence_audio"]),
                "provenance": "Local Anki mirror" if word["source"] == "anki" else "Keivotos word",
            }
            for token_index, candidates in candidates_by_token.items():
                if names & candidates and len(token_matches[str(token_index)]) < 3:
                    token_matches[str(token_index)].append(summary)
        if exact_example is None:
            for example in word["examples"]:
                if " ".join(str(example.get("sentence") or "").split()).casefold() != normalized_text:
                    continue
                exact_example = {
                    "word_id": word_id,
                    "headword": word["headword"],
                    "translations": example.get("translations") or [],
                    "has_sentence_audio": bool(word["media_by_role"]["sentence_audio"]),
                    "provenance": "Local Anki mirror" if word["source"] == "anki" else "Keivotos word",
                }
                break
    return {
        "token_matches": token_matches,
        "exact_example": exact_example,
    }


def save_analysis(
    user_connection: sqlite3.Connection,
    *,
    source_text: str,
    translation_en: str,
    translation_mn: str,
    analysis: dict[str, Any],
    analysis_id: str | None = None,
) -> dict[str, Any]:
    text = source_text.strip()
    if not text:
        raise ValueError("Saved analysis needs source text")
    selected_id = analysis_id or uuid.uuid4().hex
    user_connection.execute(
        "INSERT INTO language_analyzer_saved"
        "(analysis_id, source_text, translation_en, translation_mn, analysis_json, "
        "retired_at, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, NULL, datetime('now'), datetime('now')) "
        "ON CONFLICT(analysis_id) DO UPDATE SET "
        "source_text=excluded.source_text, "
        "translation_en=excluded.translation_en, "
        "translation_mn=excluded.translation_mn, "
        "analysis_json=excluded.analysis_json, retired_at=NULL, "
        "updated_at=datetime('now')",
        (
            selected_id,
            text,
            translation_en.strip(),
            translation_mn.strip(),
            json.dumps(analysis, ensure_ascii=False, sort_keys=True),
        ),
    )
    user_connection.commit()
    return get_saved_analysis(user_connection, selected_id)


def get_saved_analysis(
    user_connection: sqlite3.Connection,
    analysis_id: str,
) -> dict[str, Any]:
    row = user_connection.execute(
        "SELECT analysis_id, source_text, translation_en, translation_mn, "
        "analysis_json, created_at, updated_at "
        "FROM language_analyzer_saved WHERE analysis_id=? AND retired_at IS NULL",
        (analysis_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Unknown saved analysis")
    value = _row_dict(row)
    value["analysis"] = _loads(value.pop("analysis_json"), {})
    return value


def list_saved_analyses(
    user_connection: sqlite3.Connection,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    rows = user_connection.execute(
        "SELECT analysis_id, source_text, translation_en, translation_mn, "
        "analysis_json, created_at, updated_at "
        "FROM language_analyzer_saved WHERE retired_at IS NULL "
        "ORDER BY updated_at DESC, analysis_id LIMIT ?",
        (limit,),
    ).fetchall()
    values: list[dict[str, Any]] = []
    for row in rows:
        value = _row_dict(row)
        value["analysis"] = _loads(value.pop("analysis_json"), {})
        values.append(value)
    return values


def retire_saved_analysis(
    user_connection: sqlite3.Connection,
    analysis_id: str,
) -> None:
    cursor = user_connection.execute(
        "UPDATE language_analyzer_saved SET retired_at=datetime('now'), "
        "updated_at=datetime('now') WHERE analysis_id=? AND retired_at IS NULL",
        (analysis_id,),
    )
    if cursor.rowcount != 1:
        raise ValueError("Unknown saved analysis")
    user_connection.commit()


def export_payload(
    catalog_connection: sqlite3.Connection,
    user_connection: sqlite3.Connection,
) -> dict[str, Any]:
    reconcile_manual_projections(catalog_connection, user_connection)
    table_names = [
        "language_user_words",
        "language_user_overrides",
        "language_user_notes",
        "language_user_media",
        "language_favorites",
        "language_word_lists",
        "language_word_list_items",
        "language_sync_scope",
        "language_profiles",
        "language_anki_settings",
        "language_practice_sessions",
        "language_practice_results",
        "language_analyzer_saved",
    ]
    user_data = {
        table: [
            _row_dict(row)
            for row in user_connection.execute(f"SELECT * FROM {table}").fetchall()
        ]
        for table in table_names
    }
    word_ids = [
        str(row["word_id"])
        for row in catalog_connection.execute(
            "SELECT word_id FROM language_words ORDER BY added_at, word_id"
        ).fetchall()
    ]
    return {
        "format": "keivotos-language-export-v1",
        "exported_at": _now(),
        "words": [
            effective_word(catalog_connection, user_connection, word_id)
            for word_id in word_ids
        ],
        "user_data": user_data,
    }


def decode_media_payload(content_base64: str, max_bytes: int = 32 * 1024 * 1024) -> bytes:
    if len(content_base64) > ((max_bytes * 4) // 3) + 16:
        raise ValueError("Languages media exceeds the 32 MiB limit")
    try:
        payload = base64.b64decode(content_base64, validate=True)
    except ValueError as exc:
        raise ValueError("Languages media is not valid base64") from exc
    if not payload or len(payload) > max_bytes:
        raise ValueError("Languages media must be between 1 byte and 32 MiB")
    return payload
