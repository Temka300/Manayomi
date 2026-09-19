"""Previewed, cancellable, read-only Anki mirroring for Languages."""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import threading
from typing import Any, Callable
import uuid

from module_descriptor import ModuleDescriptor
from modules.language import anki, catalog, library, storage, user_state


BATCH_SIZE = 100
PREVIEW_TTL_MINUTES = 30


class LanguageImportError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _selection_sha256(
    deck_pattern: str,
    note_ids: list[str],
    note_mods: dict[str, Any],
    sync_mode: str,
) -> str:
    payload = json.dumps(
        {
            "deck_pattern": deck_pattern,
            "note_ids": note_ids,
            "note_mods": note_mods,
            "sync_mode": sync_mode,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _batched(values: list[str], size: int = BATCH_SIZE) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def _card_stage(card: dict[str, Any]) -> str:
    interval = int(card.get("interval") or 0)
    queue = int(card.get("queue") or 0)
    card_type = int(card.get("type") or 0)
    if interval >= 21:
        return "mature"
    if interval > 0:
        return "young"
    if queue in {1, 3} or card_type in {1, 3}:
        return "learning"
    return "new"


def _last_reviewed(
    reviews: dict[str, Any],
    card_id: str,
) -> str | None:
    entries = reviews.get(card_id, reviews.get(str(card_id), []))
    if not isinstance(entries, list):
        return None
    timestamps = [
        int(entry.get("id") or 0)
        for entry in entries
        if isinstance(entry, dict) and int(entry.get("id") or 0) > 0
    ]
    if not timestamps:
        return None
    return datetime.fromtimestamp(
        max(timestamps) / 1000,
        tz=timezone.utc,
    ).isoformat()


class LanguageImportManager:
    def __init__(
        self,
        descriptor: ModuleDescriptor,
        *,
        client_factory: Callable[[], Any],
        on_complete: Callable[[], Any] | None = None,
    ) -> None:
        self.descriptor = descriptor
        self.client_factory = client_factory
        self.on_complete = on_complete
        self._lock = threading.RLock()
        self._previews: dict[str, dict[str, Any]] = {}
        self._jobs: dict[str, dict[str, Any]] = {}
        self._cancel: dict[str, threading.Event] = {}

    def preview(self, deck_pattern: str) -> dict[str, Any]:
        clean_deck = deck_pattern.strip()
        if not clean_deck or len(clean_deck) > 500:
            raise LanguageImportError("An Anki deck scope is required")
        client = self.client_factory()
        query = f'deck:"{clean_deck.replace(chr(34), "")}"'
        raw_ids = client.call("findNotes", query=query)
        note_ids = sorted({str(value) for value in (raw_ids or [])})
        mod_rows = client.call(
            "notesModTime",
            notes=[int(value) for value in note_ids],
        )
        note_mods = {
            str(row.get("noteId")): row.get("mod", row.get("lastModified"))
            for row in (mod_rows or [])
            if isinstance(row, dict)
        }
        sync_mode = self._sync_mode()
        existing_by_source: dict[str, dict[str, Any]] = {}
        with catalog.open_catalog(self.descriptor.database) as connection:
            for row in connection.execute(
                "SELECT source_key, anki_mod, note_type, headword "
                "FROM language_words WHERE source='anki'"
            ).fetchall():
                existing_by_source[str(row["source_key"])] = dict(row)
        changed_ids = [
            note_id
            for note_id in note_ids
            if sync_mode == "full"
            or note_id not in existing_by_source
            or existing_by_source[note_id]["anki_mod"] != note_mods.get(note_id)
        ]
        note_infos: list[dict[str, Any]] = []
        for batch in _batched(changed_ids):
            values = client.call("notesInfo", notes=[int(value) for value in batch])
            if isinstance(values, list):
                note_infos.extend(value for value in values if isinstance(value, dict))
        changed_id_set = set(changed_ids)
        unchanged_ids = [value for value in note_ids if value not in changed_id_set]
        note_types = sorted(
            {
                str(value.get("modelName") or "")
                for value in note_infos
                if str(value.get("modelName") or "")
            }
            | {
                str(existing_by_source[value].get("note_type") or "")
                for value in unchanged_ids
                if str(existing_by_source[value].get("note_type") or "")
            }
        )
        profiles = self._profile_map()
        proposed_profiles = []
        for note_type in note_types:
            if note_type in profiles:
                continue
            field_names = client.call(
                "modelFieldNames",
                modelName=note_type,
            )
            proposal = anki.proposed_ko1k_profile(
                note_type,
                field_names if isinstance(field_names, list) else [],
            )
            if proposal is not None:
                proposed_profiles.append(proposal)
        headwords: dict[str, list[str]] = {}
        for note_id in unchanged_ids:
            headword = str(existing_by_source[note_id].get("headword") or "")
            if headword:
                headwords.setdefault(headword.casefold(), []).append(note_id)
        for note in note_infos:
            profile = (
                anki.DEFAULT_KO1K_PROFILE
                if str(note.get("modelName") or "") == "KO1Kv2"
                else profiles.get(str(note.get("modelName") or ""))
            )
            if profile is None:
                continue
            try:
                normalized = anki.normalize_note(note, profile)
            except anki.AnkiConnectError:
                continue
            headwords.setdefault(normalized["headword"].casefold(), []).append(
                normalized["source_key"]
            )
        from database import get_user_db

        duplicates = []
        with get_user_db() as user_connection:
            user_state.ensure_user_schema(user_connection)
            for row in user_connection.execute(
                "SELECT word_id, payload_json FROM language_user_words "
                "WHERE retired_at IS NULL"
            ).fetchall():
                try:
                    payload = json.loads(row["payload_json"])
                except (TypeError, ValueError):
                    continue
                matching = headwords.get(
                    str(payload.get("headword") or "").strip().casefold()
                )
                if matching:
                    duplicates.append(
                        {
                            "manual_word_id": row["word_id"],
                            "headword": payload.get("headword"),
                            "anki_note_ids": matching,
                        }
                    )
        token = uuid.uuid4().hex
        selection = _selection_sha256(
            clean_deck,
            note_ids,
            note_mods,
            sync_mode,
        )
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=PREVIEW_TTL_MINUTES
        )
        preview = {
            "token": token,
            "selection_sha256": selection,
            "deck_pattern": clean_deck,
            "note_ids": note_ids,
            "note_mods": note_mods,
            "note_infos": note_infos,
            "sync_mode": sync_mode,
            "note_count": len(note_ids),
            "changes": {
                "changed": len(changed_ids),
                "unchanged": len(unchanged_ids),
            },
            "note_types": note_types,
            "proposed_profiles": proposed_profiles,
            "duplicates": duplicates,
            "expires_at": expires_at.isoformat(),
        }
        with self._lock:
            self._previews[token] = preview
        private_keys = {"note_ids", "note_mods", "note_infos"}
        return {
            key: value
            for key, value in preview.items()
            if key not in private_keys
        }

    def start(
        self,
        *,
        preview_token: str,
        selection_sha256: str,
        authorized: bool,
        merge_manual_ids: list[str],
    ) -> dict[str, Any]:
        if not authorized:
            raise LanguageImportError("Confirmed authorization is required")
        with self._lock:
            preview = self._previews.get(preview_token)
            if preview is None:
                raise LanguageImportError("Unknown or expired Languages preview")
            if preview["selection_sha256"] != selection_sha256:
                raise LanguageImportError("Languages preview selection changed")
            expires_at = datetime.fromisoformat(preview["expires_at"])
            if datetime.now(timezone.utc) >= expires_at:
                self._previews.pop(preview_token, None)
                raise LanguageImportError("Languages preview expired")
            job_id = uuid.uuid4().hex
            job = {
                "job_id": job_id,
                "status": "queued",
                "phase": "queued",
                "progress": 0.0,
                "processed": 0,
                "total": int(preview["note_count"]),
                "counts": {},
                "error": None,
                "created_at": _now(),
                "updated_at": _now(),
            }
            self._jobs[job_id] = job
            cancel = threading.Event()
            self._cancel[job_id] = cancel
        thread = threading.Thread(
            target=self._run,
            args=(job_id, dict(preview), set(merge_manual_ids), cancel),
            daemon=True,
            name=f"language-import-{job_id[:8]}",
        )
        thread.start()
        return dict(job)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            value = self._jobs.get(job_id)
            return dict(value) if value is not None else None

    def jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                dict(value)
                for value in sorted(
                    self._jobs.values(),
                    key=lambda item: str(item["created_at"]),
                    reverse=True,
                )[:25]
            ]

    def cancel(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            event = self._cancel.get(job_id)
            if job is None or event is None:
                raise LanguageImportError("Unknown Languages import job")
            if job["status"] not in {"queued", "running", "cancelling"}:
                return dict(job)
            event.set()
            job["status"] = "cancelling"
            job["phase"] = "cancelling"
            job["updated_at"] = _now()
            return dict(job)

    def _update_job(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            self._jobs[job_id].update(changes)
            self._jobs[job_id]["updated_at"] = _now()

    def _profile_map(self) -> dict[str, dict[str, Any]]:
        from database import get_user_db

        with get_user_db() as connection:
            user_state.ensure_user_schema(connection)
            values = {}
            for row in connection.execute(
                "SELECT note_type, mapping_json FROM language_profiles"
            ).fetchall():
                try:
                    payload = json.loads(row["mapping_json"])
                except (TypeError, ValueError):
                    continue
                if isinstance(payload, dict):
                    values[str(row["note_type"])] = payload
            return values

    def _sync_mode(self) -> str:
        from database import get_user_db

        with get_user_db() as connection:
            user_state.ensure_user_schema(connection)
            row = connection.execute(
                "SELECT sync_mode FROM language_anki_settings WHERE singleton=1"
            ).fetchone()
        value = str(row["sync_mode"]) if row is not None else "incremental"
        return value if value in {"incremental", "full"} else "incremental"

    def _run(
        self,
        job_id: str,
        preview: dict[str, Any],
        merge_manual_ids: set[str],
        cancel: threading.Event,
    ) -> None:
        try:
            self._update_job(job_id, status="running", phase="reading notes")
            self._import(job_id, preview, merge_manual_ids, cancel)
            if cancel.is_set():
                self._update_job(job_id, status="cancelled", phase="cancelled")
            else:
                self._update_job(
                    job_id,
                    status="completed",
                    phase="completed",
                    progress=1.0,
                )
                if self.on_complete is not None:
                    self.on_complete()
        except Exception as exc:  # noqa: BLE001 - retained in bounded job state.
            self._update_job(
                job_id,
                status="failed",
                phase="failed",
                error=str(exc)[:2000],
            )

    def _import(
        self,
        job_id: str,
        preview: dict[str, Any],
        merge_manual_ids: set[str],
        cancel: threading.Event,
    ) -> None:
        profiles = self._profile_map()
        missing_profiles = [
            note_type
            for note_type in preview["note_types"]
            if note_type not in profiles
        ]
        if missing_profiles:
            raise LanguageImportError(
                "Confirm field profiles before import: "
                + ", ".join(missing_profiles)
            )
        client = self.client_factory()
        note_ids = [str(value) for value in preview["note_ids"]]
        deck_query = f'deck:"{preview["deck_pattern"].replace(chr(34), "")}"'
        due_ids = {
            str(value)
            for value in (
                client.call("findCards", query=f"{deck_query} is:due") or []
            )
        }
        card_ids = sorted(
            {
                str(value)
                for value in (client.call("findCards", query=deck_query) or [])
            }
        )
        mod_rows = client.call(
            "notesModTime",
            notes=[int(value) for value in note_ids],
        )
        mod_by_note = {
            str(row.get("noteId")): row.get("mod", row.get("lastModified"))
            for row in (mod_rows or [])
            if isinstance(row, dict)
        }
        if mod_by_note != preview["note_mods"]:
            raise LanguageImportError(
                "Anki notes changed after preview; build a fresh preview"
            )
        cards: dict[str, dict[str, Any]] = {}
        reviews: dict[str, Any] = {}
        for card_batch in _batched(card_ids):
            card_infos = client.call(
                "cardsInfo",
                cards=[int(value) for value in card_batch],
            )
            cards.update(
                {
                    str(value.get("cardId")): value
                    for value in (card_infos or [])
                    if isinstance(value, dict)
                }
            )
            batch_reviews = client.call(
                "getReviewsOfCards",
                cards=[int(value) for value in card_batch],
            )
            if isinstance(batch_reviews, dict):
                reviews.update(batch_reviews)
        cards_by_note: dict[str, list[str]] = {}
        for card_id, card in cards.items():
            note_id = str(card.get("note") or "")
            if note_id:
                cards_by_note.setdefault(note_id, []).append(card_id)
        existing_cards_by_note: dict[str, list[str]] = {}
        with catalog.open_catalog(self.descriptor.database) as connection:
            for row in connection.execute(
                "SELECT words.source_key, progress.card_id "
                "FROM language_words AS words "
                "JOIN language_progress AS progress "
                "ON progress.word_id=words.word_id "
                "WHERE words.source='anki'"
            ).fetchall():
                existing_cards_by_note.setdefault(
                    str(row["source_key"]),
                    [],
                ).append(str(row["card_id"]))
        note_info_by_id = {
            str(value.get("noteId")): value
            for value in preview["note_infos"]
            if isinstance(value, dict)
        }
        layout = storage.ensure_layout(self.descriptor.home)
        run_id = uuid.uuid4().hex
        counts = {
            "notes": 0,
            "created": 0,
            "updated": 0,
            "unchanged": 0,
            "media": 0,
            "missing": 0,
            "merged": 0,
            "duplicates": 0,
        }
        from database import get_user_db

        with catalog.open_catalog(self.descriptor.database) as catalog_connection:
            catalog_connection.execute(
                "INSERT INTO language_sync_runs"
                "(run_id, status, scope_json) VALUES (?, 'running', ?)",
                (
                    run_id,
                    json.dumps(
                        {
                            "deck_pattern": preview["deck_pattern"],
                            "sync_mode": preview["sync_mode"],
                            "selection_sha256": preview["selection_sha256"],
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            catalog_connection.commit()
        for batch in _batched(note_ids):
            if cancel.is_set():
                break
            with (
                catalog.open_catalog(self.descriptor.database) as catalog_connection,
                get_user_db() as user_connection,
            ):
                user_state.ensure_user_schema(user_connection)
                for note_id in batch:
                    if cancel.is_set():
                        break
                    note_card_ids = cards_by_note.get(
                        note_id,
                        existing_cards_by_note.get(note_id, []),
                    )
                    note = note_info_by_id.get(note_id)
                    if note is not None:
                        normalized = anki.normalize_note(
                            note,
                            profiles[str(note.get("modelName") or "")],
                        )
                        normalized["anki_mod"] = mod_by_note.get(
                            normalized["source_key"],
                            normalized["anki_mod"],
                        )
                        if note_card_ids:
                            normalized["card_ids"] = note_card_ids
                        self._upsert_note(
                            client,
                            catalog_connection,
                            user_connection,
                            layout["library"],
                            run_id,
                            preview["deck_pattern"],
                            normalized,
                            cards,
                            reviews,
                            due_ids,
                            merge_manual_ids,
                            counts,
                            force_refresh=preview["sync_mode"] == "full",
                        )
                    else:
                        self._refresh_unchanged_word(
                            catalog_connection,
                            source_key=note_id,
                            card_ids=note_card_ids,
                            cards=cards,
                            reviews=reviews,
                            due_ids=due_ids,
                            counts=counts,
                        )
                    counts["notes"] += 1
                    processed = counts["notes"]
                    self._update_job(
                        job_id,
                        phase="mirroring",
                        processed=processed,
                        progress=processed / max(1, len(note_ids)),
                        counts=dict(counts),
                    )
                catalog_connection.commit()
                user_connection.commit()
        with catalog.open_catalog(self.descriptor.database) as catalog_connection:
            placeholders = ",".join("?" for _ in note_ids)
            if note_ids:
                stale = catalog_connection.execute(
                    f"SELECT word_id FROM language_words WHERE source='anki' "
                    f"AND source_key NOT IN ({placeholders})",
                    note_ids,
                ).fetchall()
            else:
                stale = catalog_connection.execute(
                    "SELECT word_id FROM language_words WHERE source='anki'"
                ).fetchall()
            counts["missing"] = len(stale)
            for row in stale:
                catalog_connection.execute(
                    "UPDATE language_words SET missing=1, updated_at=? "
                    "WHERE word_id=?",
                    (_now(), row["word_id"]),
                )
            status = "cancelled" if cancel.is_set() else "completed"
            catalog_connection.execute(
                "UPDATE language_sync_runs SET status=?, counts_json=?, "
                "finished_at=? WHERE run_id=?",
                (
                    status,
                    json.dumps(counts, sort_keys=True),
                    _now(),
                    run_id,
                ),
            )
            catalog_connection.commit()
        self._update_job(job_id, counts=dict(counts))

    def _upsert_note(
        self,
        client: Any,
        catalog_connection: Any,
        user_connection: Any,
        library_root: Path,
        run_id: str,
        deck_pattern: str,
        note: dict[str, Any],
        cards: dict[str, dict[str, Any]],
        reviews: dict[str, Any],
        due_ids: set[str],
        merge_manual_ids: set[str],
        counts: dict[str, int],
        *,
        force_refresh: bool = False,
    ) -> None:
        word_id = catalog.word_id_for_source("anki", note["source_key"])
        existing = catalog_connection.execute(
            "SELECT anki_mod, media_dir_rel FROM language_words WHERE word_id=?",
            (word_id,),
        ).fetchone()
        changed = (
            force_refresh
            or existing is None
            or existing["anki_mod"] != note["anki_mod"]
        )
        if existing is None:
            media_dir_rel = library._allocate_media_dir(
                catalog_connection,
                note["lang"],
                note["headword"],
            )
            counts["created"] += 1
        else:
            media_dir_rel = existing["media_dir_rel"]
            counts["updated" if changed else "unchanged"] += 1
        card_values = [
            cards[card_id]
            for card_id in note["card_ids"]
            if card_id in cards
        ]
        deck = next(
            (
                str(value.get("deckName") or "")
                for value in card_values
                if value.get("deckName")
            ),
            deck_pattern,
        )
        suspended = bool(card_values) and all(
            int(value.get("queue") or 0) == -1
            for value in card_values
        )
        catalog_connection.execute(
            """INSERT INTO language_words
               (word_id, lang, headword, sentence_form, reading, source,
                source_key, note_type, deck, sort_index, fields_json,
                media_dir_rel, anki_mod, missing, suspended, updated_at)
               VALUES (?, ?, ?, ?, ?, 'anki', ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
               ON CONFLICT(word_id) DO UPDATE SET
                 lang=excluded.lang, headword=excluded.headword,
                 sentence_form=excluded.sentence_form, reading=excluded.reading,
                 note_type=excluded.note_type, deck=excluded.deck,
                 sort_index=excluded.sort_index, fields_json=excluded.fields_json,
                 media_dir_rel=excluded.media_dir_rel,
                 anki_mod=excluded.anki_mod, missing=0,
                 suspended=excluded.suspended, updated_at=excluded.updated_at""",
            (
                word_id,
                note["lang"],
                note["headword"],
                note["sentence_form"],
                note["reading"],
                note["source_key"],
                note["note_type"],
                deck,
                note["sort_index"],
                json.dumps(note["fields"], ensure_ascii=False, sort_keys=True),
                media_dir_rel,
                note["anki_mod"],
                int(suspended),
                _now(),
            ),
        )
        if changed:
            library._replace_projection_children(
                catalog_connection,
                word_id,
                note,
            )
            self._mirror_media(
                client,
                catalog_connection,
                library_root,
                word_id,
                media_dir_rel,
                note,
                counts,
            )
            receipt = {
                "format": "keivotos-language-note-receipt-v1",
                "run_id": run_id,
                "note": note,
                "cards": card_values,
            }
            receipt_path = storage.resolve_within(
                library_root,
                (
                    Path(media_dir_rel)
                    / storage.metadata_receipt_name(run_id)
                ).as_posix(),
            )
            storage.write_json_create(receipt_path, receipt)
        self._write_progress(
            catalog_connection,
            word_id=word_id,
            card_ids=note["card_ids"],
            cards=cards,
            reviews=reviews,
            due_ids=due_ids,
        )
        manual_rows = user_connection.execute(
            "SELECT word_id, payload_json FROM language_user_words "
            "WHERE retired_at IS NULL"
        ).fetchall()
        for manual in manual_rows:
            try:
                payload = json.loads(manual["payload_json"])
            except (TypeError, ValueError):
                continue
            if (
                str(payload.get("lang") or "ko").casefold() != note["lang"].casefold()
                or str(payload.get("headword") or "").strip().casefold()
                != note["headword"].casefold()
            ):
                continue
            manual_id = str(manual["word_id"])
            if manual_id in merge_manual_ids:
                for field in library.EDITABLE_FIELDS - {"personal_note"}:
                    if field in payload and payload[field] not in (None, "", [], {}):
                        user_connection.execute(
                            "INSERT INTO language_user_overrides"
                            "(word_id, field, value_json, updated_at) "
                            "VALUES (?, ?, ?, ?) ON CONFLICT(word_id, field) "
                            "DO UPDATE SET value_json=excluded.value_json, "
                            "updated_at=excluded.updated_at",
                            (
                                word_id,
                                field,
                                json.dumps(
                                    payload[field],
                                    ensure_ascii=False,
                                    sort_keys=True,
                                ),
                                _now(),
                            ),
                        )
                user_connection.execute(
                    "UPDATE language_user_media SET word_id=? WHERE word_id=? "
                    "AND NOT EXISTS (SELECT 1 FROM language_user_media target "
                    "WHERE target.word_id=? "
                    "AND target.role=language_user_media.role "
                    "AND target.position=language_user_media.position "
                    "AND target.sha256=language_user_media.sha256)",
                    (word_id, manual_id, word_id),
                )
                user_connection.execute(
                    "UPDATE language_user_media SET active=0, retired_at=? "
                    "WHERE word_id=?",
                    (_now(), manual_id),
                )
                manual_note = user_connection.execute(
                    "SELECT body FROM language_user_notes "
                    "WHERE word_id=? AND retired_at IS NULL",
                    (manual_id,),
                ).fetchone()
                target_note = user_connection.execute(
                    "SELECT body FROM language_user_notes "
                    "WHERE word_id=? AND retired_at IS NULL",
                    (word_id,),
                ).fetchone()
                if manual_note is not None and target_note is None:
                    user_connection.execute(
                        "UPDATE language_user_notes SET word_id=? WHERE word_id=?",
                        (word_id, manual_id),
                    )
                elif manual_note is not None:
                    manual_body = str(manual_note["body"])
                    target_body = str(target_note["body"])
                    combined = (
                        target_body
                        if manual_body == target_body
                        else f"{target_body}\n\n{manual_body}"
                    )
                    user_connection.execute(
                        "UPDATE language_user_notes SET body=?, updated_at=? "
                        "WHERE word_id=?",
                        (combined, _now(), word_id),
                    )
                    user_connection.execute(
                        "UPDATE language_user_notes SET retired_at=?, "
                        "merged_into_word_id=?, updated_at=? WHERE word_id=?",
                        (_now(), word_id, _now(), manual_id),
                    )
                favorite = user_connection.execute(
                    "SELECT 1 FROM language_favorites WHERE word_id=?",
                    (manual_id,),
                ).fetchone()
                if favorite is not None:
                    user_connection.execute(
                        "INSERT OR IGNORE INTO language_favorites(word_id) VALUES (?)",
                        (word_id,),
                    )
                for membership in user_connection.execute(
                    "SELECT list_id, position FROM language_word_list_items "
                    "WHERE word_id=? AND retired_at IS NULL",
                    (manual_id,),
                ).fetchall():
                    user_connection.execute(
                        "INSERT INTO language_word_list_items"
                        "(list_id, word_id, position, retired_at) "
                        "VALUES (?, ?, ?, NULL) "
                        "ON CONFLICT(list_id, word_id) DO UPDATE SET retired_at=NULL",
                        (membership["list_id"], word_id, membership["position"]),
                    )
                user_connection.execute(
                    "UPDATE language_word_list_items SET retired_at=? "
                    "WHERE word_id=? AND retired_at IS NULL",
                    (_now(), manual_id),
                )
                user_connection.execute(
                    "UPDATE language_user_words SET retired_at=?, "
                    "merged_into_word_id=?, updated_at=? WHERE word_id=?",
                    (_now(), word_id, _now(), manual_id),
                )
                catalog_connection.execute(
                    "DELETE FROM language_words WHERE word_id=?",
                    (manual_id,),
                )
                counts["merged"] += 1
            else:
                catalog_connection.execute(
                    "UPDATE language_words SET possible_duplicate=1 "
                    "WHERE word_id IN (?, ?)",
                    (word_id, manual_id),
                )
                counts["duplicates"] += 1

    def _refresh_unchanged_word(
        self,
        catalog_connection: Any,
        *,
        source_key: str,
        card_ids: list[str],
        cards: dict[str, dict[str, Any]],
        reviews: dict[str, Any],
        due_ids: set[str],
        counts: dict[str, int],
    ) -> None:
        word_id = catalog.word_id_for_source("anki", source_key)
        existing = catalog_connection.execute(
            "SELECT 1 FROM language_words WHERE word_id=? AND source='anki'",
            (word_id,),
        ).fetchone()
        if existing is None:
            raise LanguageImportError(
                "Anki preview no longer matches the local catalog"
            )
        card_values = [
            cards[card_id]
            for card_id in card_ids
            if card_id in cards
        ]
        if card_values:
            deck = next(
                (
                    str(value.get("deckName") or "")
                    for value in card_values
                    if value.get("deckName")
                ),
                "",
            )
            suspended = all(
                int(value.get("queue") or 0) == -1
                for value in card_values
            )
            catalog_connection.execute(
                "UPDATE language_words SET deck=CASE WHEN ?='' THEN deck ELSE ? END, "
                "suspended=?, missing=0, updated_at=? WHERE word_id=?",
                (deck, deck, int(suspended), _now(), word_id),
            )
        else:
            catalog_connection.execute(
                "UPDATE language_words SET missing=0, updated_at=? WHERE word_id=?",
                (_now(), word_id),
            )
        self._write_progress(
            catalog_connection,
            word_id=word_id,
            card_ids=card_ids,
            cards=cards,
            reviews=reviews,
            due_ids=due_ids,
        )
        counts["unchanged"] += 1

    def _write_progress(
        self,
        catalog_connection: Any,
        *,
        word_id: str,
        card_ids: list[str],
        cards: dict[str, dict[str, Any]],
        reviews: dict[str, Any],
        due_ids: set[str],
    ) -> None:
        catalog_connection.execute(
            "DELETE FROM language_progress WHERE word_id=?",
            (word_id,),
        )
        for card_id in card_ids:
            card = cards.get(card_id)
            if card is None:
                continue
            catalog_connection.execute(
                """INSERT INTO language_progress
                   (word_id, card_id, interval, due, reps, lapses, queue, type,
                    stage, card_mod, due_now, last_reviewed_at, synced_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    word_id,
                    card_id,
                    int(card.get("interval") or 0),
                    card.get("due"),
                    int(card.get("reps") or 0),
                    int(card.get("lapses") or 0),
                    card.get("queue"),
                    card.get("type"),
                    _card_stage(card),
                    card.get("mod"),
                    int(card_id in due_ids),
                    _last_reviewed(reviews, card_id),
                    _now(),
                ),
            )

    def _mirror_media(
        self,
        client: Any,
        connection: Any,
        library_root: Path,
        word_id: str,
        media_dir_rel: str,
        note: dict[str, Any],
        counts: dict[str, int],
    ) -> None:
        connection.execute(
            "UPDATE language_media SET active=0 WHERE word_id=?",
            (word_id,),
        )
        for role, filenames in note["media_filenames"].items():
            for position, filename in enumerate(filenames):
                encoded = client.call(
                    "retrieveMediaFile",
                    filename=filename,
                )
                if not isinstance(encoded, str) or not encoded:
                    continue
                try:
                    payload = base64.b64decode(encoded, validate=True)
                except ValueError:
                    continue
                if not payload:
                    continue
                digest = hashlib.sha256(payload).hexdigest()
                relative_path = (
                    Path(media_dir_rel)
                    / storage.versioned_media_name(role, digest, filename)
                ).as_posix()
                destination = storage.resolve_within(library_root, relative_path)
                if destination.exists():
                    existing_digest, existing_bytes = storage.hash_file(destination)
                    if existing_digest != digest or existing_bytes != len(payload):
                        raise LanguageImportError(
                            "Existing Languages media failed its content check"
                        )
                else:
                    storage.write_bytes_create(destination, payload)
                media_id = hashlib.sha256(
                    f"{word_id}\0{role}\0{position}\0{digest}".encode("utf-8")
                ).hexdigest()
                connection.execute(
                    """INSERT INTO language_media
                       (media_id, word_id, role, position, relative_path, sha256,
                        bytes, origin_filename, active)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                       ON CONFLICT(media_id) DO UPDATE SET active=1""",
                    (
                        media_id,
                        word_id,
                        role,
                        position,
                        relative_path,
                        digest,
                        len(payload),
                        Path(filename).name,
                    ),
                )
                counts["media"] += 1
