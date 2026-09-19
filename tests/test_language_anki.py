from __future__ import annotations

import base64
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import database  # noqa: E402
from module_registry import build_registry  # noqa: E402
from modules.language import anki, catalog, library, storage, user_state  # noqa: E402
from modules.language.imports import LanguageImportManager  # noqa: E402


NOTE = {
    "noteId": 101,
    "modelName": "KO1Kv2",
    "mod": 10,
    "tags": ["KO1K", "lesson-1"],
    "cards": [201, 202],
    "fields": {
        "Index": {"value": "1"},
        "Word": {"value": "축하하다"},
        "Word Audio": {"value": "[sound:word.mp3]"},
        "Definition": {"value": "to congratulate<br>Баяр хүргэх"},
        "Word in Sentence Form": {"value": "축하해요"},
        "Example Sentence": {"value": "생일 축하해요!"},
        "Sentence Audio": {"value": "[sound:sentence.mp3]"},
        "Sentence Translation": {"value": "Happy birthday!<br>Төрсөн өдрийн мэнд!"},
        "Image": {"value": '<img src="image.jpg">'},
        "Grammar Notes": {"value": "하다 verb"},
        "Pronunciation": {"value": ""},
    },
}


class StubAnkiClient:
    def __init__(self) -> None:
        self.actions: list[str] = []
        self.note_mod = 10
        self.model_name = "KO1Kv2"

    def call(self, action: str, **params):
        self.actions.append(action)
        if action == "findNotes":
            return [101]
        if action == "notesInfo":
            return [{**NOTE, "modelName": self.model_name}]
        if action == "modelFieldNames":
            return list(NOTE["fields"])
        if action == "notesModTime":
            return [{"noteId": 101, "mod": self.note_mod}]
        if action == "findCards":
            return [202] if "is:due" in params["query"] else [201, 202]
        if action == "cardsInfo":
            return [
                {
                    "cardId": 201,
                    "note": 101,
                    "deckName": "한국어::2. Refold KO1K v2",
                    "interval": 30,
                    "due": 2000,
                    "reps": 20,
                    "lapses": 1,
                    "queue": 2,
                    "type": 2,
                    "mod": 11,
                    "question": "front",
                    "answer": "back",
                    "css": ".card{}",
                },
                {
                    "cardId": 202,
                    "note": 101,
                    "deckName": "한국어::2. Refold KO1K v2",
                    "interval": 4,
                    "due": 5,
                    "reps": 3,
                    "lapses": 0,
                    "queue": 2,
                    "type": 2,
                    "mod": 12,
                    "question": "front 2",
                    "answer": "back 2",
                    "css": ".card{}",
                },
            ]
        if action == "getReviewsOfCards":
            return {"201": [{"id": 1720000000000}], "202": []}
        if action == "retrieveMediaFile":
            return base64.b64encode(f"bytes:{params['filename']}".encode()).decode()
        raise AssertionError(f"Unexpected action: {action}")


class LanguageAnkiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = ROOT / "tests" / ".tmp-language-anki"
        shutil.rmtree(self.temp, ignore_errors=True)
        self.temp.mkdir(parents=True)
        self.user_db = self.temp / "user.sqlite"
        self.descriptor = build_registry(self.temp / "suite", "1.1.2").require("language")
        self.stub = StubAnkiClient()
        self.database_patch = patch.object(database, "USER_DB_PATH", self.user_db)
        self.database_patch.start()
        with database.get_user_db() as connection:
            user_state.ensure_user_schema(connection)

    def tearDown(self) -> None:
        self.database_patch.stop()
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_profile_normalization_handles_language_scripts_and_media(self) -> None:
        normalized = anki.normalize_note(NOTE, anki.DEFAULT_KO1K_PROFILE)
        self.assertEqual(normalized["headword"], "축하하다")
        self.assertEqual(normalized["sentence_form"], "축하해요")
        self.assertEqual(
            [sense["lang"] for sense in normalized["senses"]],
            ["en", "mn"],
        )
        self.assertEqual(normalized["media_filenames"]["word_audio"], ["word.mp3"])
        self.assertEqual(normalized["media_filenames"]["image"], ["image.jpg"])
        reordered = anki.split_language_block("Монгол\nEnglish", ["en", "mn"])
        self.assertEqual([value["lang"] for value in reordered], ["mn", "en"])
        single = anki.split_language_block("only one", ["en", "mn"])
        self.assertEqual(single, [{"lang": "en", "text": "only one"}])

    def test_preview_proposes_mapping_for_field_compatible_ko1kv2_variant(
        self,
    ) -> None:
        self.stub.model_name = "KO1Kv2+"
        manager = LanguageImportManager(
            self.descriptor,
            client_factory=lambda: self.stub,
        )

        preview = manager.preview("한국어::2. Refold KO1K v2")

        self.assertEqual(preview["note_types"], ["KO1Kv2+"])
        self.assertEqual(
            preview["proposed_profiles"][0]["note_type"],
            "KO1Kv2+",
        )
        self.assertIn("modelFieldNames", self.stub.actions)

    def test_client_source_contains_only_the_read_allowlist(self) -> None:
        source = (ROOT / "backend" / "modules" / "language" / "anki.py").read_text(
            encoding="utf-8"
        )
        forbidden = [
            "add" + "Note",
            "update" + "NoteFields",
            "delete" + "Notes",
            "store" + "MediaFile",
            "delete" + "MediaFile",
            "gui" + "DeckReview",
        ]
        for name in forbidden:
            self.assertNotIn(name, source)
        self.assertEqual(
            anki.READ_ACTIONS,
            {
                "requestPermission",
                "version",
                "deckNames",
                "modelNames",
                "modelFieldNames",
                "findNotes",
                "notesModTime",
                "notesInfo",
                "cardsInfo",
                "findCards",
                "getReviewsOfCards",
                "getMediaDirPath",
                "retrieveMediaFile",
            },
        )
        client = anki.AnkiConnectClient()
        with self.assertRaises(anki.AnkiConnectError):
            client.call("add" + "Note")

    def test_preview_and_background_import_use_stub_only(self) -> None:
        manager = LanguageImportManager(
            self.descriptor,
            client_factory=lambda: self.stub,
        )
        preview = manager.preview("한국어::2. Refold KO1K v2")
        self.assertEqual(preview["note_count"], 1)
        self.assertEqual(preview["note_types"], ["KO1Kv2"])
        self.assertEqual(preview["proposed_profiles"][0]["note_type"], "KO1Kv2")

        with database.get_user_db() as connection:
            connection.execute(
                "INSERT INTO language_profiles(note_type, mapping_json) VALUES (?, ?)",
                (
                    "KO1Kv2",
                    json.dumps(anki.DEFAULT_KO1K_PROFILE, ensure_ascii=False),
                ),
            )
            connection.commit()
        job = manager.start(
            preview_token=preview["token"],
            selection_sha256=preview["selection_sha256"],
            authorized=True,
            merge_manual_ids=[],
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            current = manager.get_job(job["job_id"])
            if current["status"] in {"completed", "failed", "cancelled"}:
                break
            time.sleep(0.02)
        self.assertEqual(current["status"], "completed", current)

        word_id = catalog.word_id_for_source("anki", 101)
        with (
            catalog.open_catalog(self.descriptor.database) as catalog_connection,
            database.get_user_db() as user_connection,
        ):
            word = library.effective_word(
                catalog_connection,
                user_connection,
                word_id,
            )
        self.assertEqual(word["headword"], "축하하다")
        self.assertEqual(word["stage"], "young")
        self.assertTrue(word["due_now"])
        self.assertEqual(len(word["media"]), 3)
        self.assertIsNotNone(word["last_reviewed_at"])
        self.assertTrue(
            (self.descriptor.home / "media" / "library").is_dir()
        )
        receipts = list(
            (self.descriptor.home / "media" / "library").rglob(
                "note.*.metadata.json"
            )
        )
        self.assertEqual(len(receipts), 1)
        self.assertIn("getReviewsOfCards", self.stub.actions)
        self.assertIn("findCards", self.stub.actions)

        self.stub.actions.clear()
        incremental = manager.preview("í•œêµ­ì–´::2. Refold KO1K v2")
        self.assertEqual(incremental["changes"], {"changed": 0, "unchanged": 1})
        self.assertIn("notesModTime", self.stub.actions)
        self.assertNotIn("notesInfo", self.stub.actions)
        incremental_job = manager.start(
            preview_token=incremental["token"],
            selection_sha256=incremental["selection_sha256"],
            authorized=True,
            merge_manual_ids=[],
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            current = manager.get_job(incremental_job["job_id"])
            if current["status"] in {"completed", "failed", "cancelled"}:
                break
            time.sleep(0.02)
        self.assertEqual(current["status"], "completed", current)
        self.assertEqual(current["counts"]["unchanged"], 1)
        self.assertNotIn("notesInfo", self.stub.actions)

        with database.get_user_db() as connection:
            connection.execute(
                "INSERT INTO language_anki_settings(singleton, sync_mode) "
                "VALUES (1, 'full') ON CONFLICT(singleton) DO UPDATE SET "
                "sync_mode=excluded.sync_mode"
            )
            connection.commit()
        self.stub.actions.clear()
        full = manager.preview("í•œêµ­ì–´::2. Refold KO1K v2")
        self.assertEqual(full["changes"], {"changed": 1, "unchanged": 0})
        self.assertIn("notesInfo", self.stub.actions)

    def test_import_rejects_notes_changed_after_preview(self) -> None:
        manager = LanguageImportManager(
            self.descriptor,
            client_factory=lambda: self.stub,
        )
        preview = manager.preview("í•œêµ­ì–´::2. Refold KO1K v2")
        with database.get_user_db() as connection:
            connection.execute(
                "INSERT INTO language_profiles(note_type, mapping_json) VALUES (?, ?)",
                (
                    "KO1Kv2",
                    json.dumps(anki.DEFAULT_KO1K_PROFILE, ensure_ascii=False),
                ),
            )
            connection.commit()
        self.stub.note_mod = 11
        job = manager.start(
            preview_token=preview["token"],
            selection_sha256=preview["selection_sha256"],
            authorized=True,
            merge_manual_ids=[],
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            current = manager.get_job(job["job_id"])
            if current["status"] in {"completed", "failed", "cancelled"}:
                break
            time.sleep(0.02)
        self.assertEqual(current["status"], "failed")
        self.assertIn("fresh preview", current["error"])

    def test_cancel_is_cooperative_and_preserves_job_result(self) -> None:
        manager = LanguageImportManager(
            self.descriptor,
            client_factory=lambda: self.stub,
        )
        preview = manager.preview("한국어::2. Refold KO1K v2")
        with database.get_user_db() as connection:
            connection.execute(
                "INSERT INTO language_profiles(note_type, mapping_json) VALUES (?, ?)",
                (
                    "KO1Kv2",
                    json.dumps(anki.DEFAULT_KO1K_PROFILE, ensure_ascii=False),
                ),
            )
            connection.commit()
        job = manager.start(
            preview_token=preview["token"],
            selection_sha256=preview["selection_sha256"],
            authorized=True,
            merge_manual_ids=[],
        )
        cancelled = manager.cancel(job["job_id"])
        self.assertIn(cancelled["status"], {"cancelling", "completed"})
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            current = manager.get_job(job["job_id"])
            if current["status"] in {"completed", "failed", "cancelled"}:
                break
            time.sleep(0.02)
        self.assertIn(current["status"], {"completed", "cancelled"})

    def test_confirmed_duplicate_merge_preserves_all_authored_state(self) -> None:
        layout = storage.ensure_layout(self.descriptor.home)
        with (
            catalog.open_catalog(self.descriptor.database) as catalog_connection,
            database.get_user_db() as user_connection,
        ):
            manual_id = library.create_manual_word(
                catalog_connection,
                user_connection,
                {
                    "headword": NOTE["fields"]["Word"]["value"],
                    "senses": [{"lang": "en", "text": "my authored meaning"}],
                    "tags": ["personal"],
                    "personal_note": "keep this private note",
                },
            )
            manual_media = library.attach_media(
                catalog_connection,
                user_connection,
                layout["library"],
                word_id=manual_id,
                role="word_audio",
                filename="my-recording.wav",
                payload=b"my irreplaceable recording",
            )
            library.set_favorite(user_connection, manual_id, True)
            word_list = library.create_word_list(
                user_connection,
                "Merge preservation",
                "",
            )
            library.set_list_membership(
                user_connection,
                word_list["list_id"],
                [manual_id],
                True,
            )

        manager = LanguageImportManager(
            self.descriptor,
            client_factory=lambda: self.stub,
        )
        preview = manager.preview("í•œêµ­ì–´::2. Refold KO1K v2")
        self.assertEqual(
            [value["manual_word_id"] for value in preview["duplicates"]],
            [manual_id],
        )
        with database.get_user_db() as connection:
            connection.execute(
                "INSERT INTO language_profiles(note_type, mapping_json) VALUES (?, ?)",
                (
                    "KO1Kv2",
                    json.dumps(anki.DEFAULT_KO1K_PROFILE, ensure_ascii=False),
                ),
            )
            connection.commit()
        job = manager.start(
            preview_token=preview["token"],
            selection_sha256=preview["selection_sha256"],
            authorized=True,
            merge_manual_ids=[manual_id],
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            current = manager.get_job(job["job_id"])
            if current["status"] in {"completed", "failed", "cancelled"}:
                break
            time.sleep(0.02)
        self.assertEqual(current["status"], "completed", current)
        self.assertEqual(current["counts"]["merged"], 1)

        mirrored_id = catalog.word_id_for_source("anki", 101)
        with (
            catalog.open_catalog(self.descriptor.database) as catalog_connection,
            database.get_user_db() as user_connection,
        ):
            merged = library.effective_word(
                catalog_connection,
                user_connection,
                mirrored_id,
            )
            retired = user_connection.execute(
                "SELECT retired_at, merged_into_word_id, payload_json "
                "FROM language_user_words WHERE word_id=?",
                (manual_id,),
            ).fetchone()
            membership = user_connection.execute(
                "SELECT retired_at FROM language_word_list_items "
                "WHERE list_id=? AND word_id=?",
                (word_list["list_id"], mirrored_id),
            ).fetchone()

        self.assertEqual(merged["senses"][0]["text"], "my authored meaning")
        self.assertEqual(merged["personal_note"], "keep this private note")
        self.assertTrue(merged["favorite"])
        self.assertEqual(
            merged["media_by_role"]["word_audio"]["sha256"],
            manual_media["sha256"],
        )
        self.assertIsNotNone(retired["retired_at"])
        self.assertEqual(retired["merged_into_word_id"], mirrored_id)
        self.assertIn("my authored meaning", retired["payload_json"])
        self.assertIsNotNone(membership)
        self.assertIsNone(membership["retired_at"])


if __name__ == "__main__":
    unittest.main()
