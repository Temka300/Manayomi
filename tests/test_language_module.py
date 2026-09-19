from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import database  # noqa: E402
import suite_modules  # noqa: E402
from files_base import sources  # noqa: E402
from module_registry import build_registry  # noqa: E402
from modules.language import catalog, storage, user_state  # noqa: E402


class LanguageModuleFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = ROOT / "tests" / ".tmp-language-module"
        shutil.rmtree(self.temp, ignore_errors=True)
        self.temp.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_descriptor_has_isolated_paths_and_hooks(self) -> None:
        descriptor = build_registry(self.temp / "suite", "1.1.2").require("language")
        expected_home = (self.temp / "suite" / "modules" / "language").resolve()

        self.assertEqual(descriptor.name, "Languages")
        self.assertEqual(descriptor.home, expected_home)
        self.assertEqual(descriptor.database, expected_home / "language.sqlite")
        self.assertEqual(
            descriptor.credentials,
            expected_home / "language_credentials.json",
        )
        self.assertEqual(descriptor.api_prefix, "/api/language")
        self.assertEqual(
            descriptor.browsable_roots,
            (expected_home / "media" / "library",),
        )
        self.assertTrue(descriptor.disableable)
        self.assertIsNotNone(descriptor.adopt_hook)
        self.assertIsNotNone(descriptor.release_hook)

    def test_publish_initializes_foundation_and_preserves_study_folders(self) -> None:
        descriptor = build_registry(self.temp / "suite", "1.1.2").require("language")
        study_folder = self.temp / "study"
        study_folder.mkdir()
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        sources.ensure_sources_schema(connection)
        study_source = sources.register_source(
            connection,
            study_folder,
            "Korean textbooks",
            role="language",
        )

        descriptor.publish(connection)
        published = sources.list_sources(connection)
        table_names = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        connection.close()

        self.assertTrue(descriptor.database.is_file())
        self.assertTrue(descriptor.browsable_roots[0].is_dir())
        self.assertIn("language_user_words", table_names)
        self.assertEqual(
            {source.source_id for source in published},
            {
                study_source.source_id,
                sources.deterministic_source_id(descriptor.browsable_roots[0]),
            },
        )
        self.assertEqual(
            {source.role for source in published},
            {"language"},
        )

    def test_disposable_catalog_has_stable_source_identity(self) -> None:
        database_path = self.temp / "language.sqlite"
        stable_id = catalog.word_id_for_source("anki", 12345)
        self.assertEqual(stable_id, catalog.word_id_for_source("ANKI", "12345"))
        self.assertNotEqual(stable_id, catalog.word_id_for_source("anki", 12346))

        with catalog.open_catalog(database_path) as connection:
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            connection.execute(
                "INSERT INTO language_words"
                "(word_id, lang, headword, sentence_form, source, source_key) "
                "VALUES (?, 'ko', '축하하다', '축하해요', 'anki', '12345')",
                (stable_id,),
            )
            connection.commit()

        self.assertTrue(
            {
                "language_words",
                "language_senses",
                "language_examples",
                "language_notes_text",
                "language_tags",
                "language_media",
                "language_progress",
                "language_sync_runs",
                "language_analysis_cache",
                "language_dictionary_cache",
            }.issubset(tables)
        )
        self.assertNotIn("language_profiles", tables)
        with catalog.open_catalog(database_path) as connection:
            row = connection.execute(
                "SELECT headword FROM language_words WHERE word_id=?",
                (stable_id,),
            ).fetchone()
        self.assertEqual(row["headword"], "축하하다")

    def test_precious_schema_is_additive_and_idempotent(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.execute("CREATE TABLE sentinel(value TEXT NOT NULL)")
        connection.execute("INSERT INTO sentinel(value) VALUES ('keep')")

        user_state.ensure_user_schema(connection)
        connection.execute(
            "INSERT INTO language_user_words(word_id, payload_json) VALUES (?, ?)",
            ("manual-one", json.dumps({"headword": "단어"})),
        )
        connection.commit()
        user_state.ensure_user_schema(connection)

        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        sentinel = connection.execute("SELECT value FROM sentinel").fetchone()
        authored = connection.execute(
            "SELECT payload_json, retired_at FROM language_user_words "
            "WHERE word_id='manual-one'"
        ).fetchone()
        list_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(language_word_lists)"
            ).fetchall()
        }
        connection.close()

        self.assertEqual(sentinel["value"], "keep")
        self.assertEqual(json.loads(authored["payload_json"])["headword"], "단어")
        self.assertIsNone(authored["retired_at"])
        self.assertIn("retired_at", list_columns)
        self.assertTrue(
            {
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
            }.issubset(tables)
        )

    def test_disable_preserves_catalog_and_precious_rows(self) -> None:
        descriptor = build_registry(self.temp / "suite", "1.1.2").require("language")
        user_database = self.temp / "user.sqlite"
        connection = sqlite3.connect(user_database)
        connection.row_factory = sqlite3.Row
        suite_modules.ensure_schema(connection)
        descriptor.publish(connection)
        connection.execute(
            "INSERT INTO language_user_words(word_id, payload_json) "
            "VALUES ('manual-one', '{\"headword\":\"단어\"}')"
        )
        connection.commit()

        with patch.object(suite_modules, "MODULE_REGISTRY", build_registry(self.temp / "suite", "1.1.2")):
            suite_modules.set_enabled(connection, "language", True)
            suite_modules.set_enabled(connection, "language", False)

        row = connection.execute(
            "SELECT payload_json FROM language_user_words WHERE word_id='manual-one'"
        ).fetchone()
        connection.close()

        self.assertIsNotNone(row)
        self.assertTrue(descriptor.database.is_file())
        self.assertTrue(descriptor.browsable_roots[0].is_dir())

    def test_storage_is_contained_versioned_and_create_only(self) -> None:
        layout = storage.ensure_layout(self.temp / "module")
        source = self.temp / "source.mp3"
        source.write_bytes(b"first")
        digest = "a" * 64
        name = storage.versioned_media_name("word audio", digest, "clip.MP3")
        destination = layout["library"] / "ko" / "단어" / name

        copied_digest, copied_bytes = storage.copy_file_create(source, destination)
        self.assertEqual(copied_digest, storage.hash_file(source)[0])
        self.assertEqual(copied_bytes, 5)
        self.assertEqual(destination.read_bytes(), b"first")
        self.assertEqual(name, f"word-audio.{digest[:12]}.mp3")
        self.assertEqual(
            storage.metadata_receipt_name("sync 42"),
            "note.sync-42.metadata.json",
        )

        source.write_bytes(b"second")
        with self.assertRaises(storage.LanguageStorageError):
            storage.copy_file_create(source, destination)
        self.assertEqual(destination.read_bytes(), b"first")
        with self.assertRaises(storage.LanguageStorageError):
            storage.resolve_within(layout["library"], "..\\outside.txt")


if __name__ == "__main__":
    unittest.main()
