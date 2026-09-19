from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import config  # noqa: E402
import database  # noqa: E402
from module_registry import build_registry  # noqa: E402
from routers import language  # noqa: E402
import suite_modules  # noqa: E402


class LanguageApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = ROOT / "tests" / ".tmp-language-api"
        shutil.rmtree(self.temp, ignore_errors=True)
        self.temp.mkdir(parents=True)
        self.registry = build_registry(self.temp / "suite", "1.1.2")
        self.descriptor = self.registry.require("language")
        self.patchers = [
            patch.object(database, "USER_DB_PATH", self.temp / "user.sqlite"),
            patch.object(config, "FILES_DB_PATH", self.temp / "files.sqlite"),
            patch.object(language, "DESCRIPTOR", self.descriptor),
            patch.object(language, "LIBRARY_ROOT", self.descriptor.browsable_roots[0]),
            patch.object(language, "_IMPORT_MANAGER", None),
            patch.object(suite_modules, "MODULE_REGISTRY", self.registry),
        ]
        for patcher in self.patchers:
            patcher.start()
        with database.get_user_db() as connection:
            suite_modules.ensure_schema(connection)
            suite_modules.set_enabled(connection, "language", True)

    def tearDown(self) -> None:
        for patcher in reversed(self.patchers):
            patcher.stop()
        shutil.rmtree(self.temp, ignore_errors=True)

    def words(self, **changes):
        arguments = {
            "query": "",
            "deck": "",
            "tag": "",
            "stage": "",
            "source": "",
            "favorites": False,
            "missing": None,
            "suspended": None,
            "list_id": "",
            "content": "all",
            "sort": "index",
            "descending": False,
            "offset": 0,
            "limit": 60,
        }
        arguments.update(changes)
        return language.words(**arguments)

    def test_status_is_cached_only_and_manual_crud_roundtrips(self) -> None:
        with patch.object(language, "_client", side_effect=AssertionError("network")):
            status = language.status()
        self.assertEqual(status["counts"]["words"], 0)
        self.assertIsNone(status["anki"]["cached_probe"])

        created = language.create_word(
            language.ManualWordPayload(
                headword="안녕",
                senses=[{"lang": "en", "text": "hello"}],
            )
        )
        word_id = created["word"]["word_id"]
        self.assertEqual(self.words(query="hello")["total"], 1)
        updated = language.update_word(
            word_id,
            language.WordUpdatePayload(reading="annyeong"),
        )
        self.assertEqual(updated["word"]["reading"], "annyeong")

        favorite = language.update_favorite(
            word_id,
            language.FavoritePayload(favorite=True),
        )
        self.assertTrue(favorite["favorite"])
        word_list = language.create_list(
            language.WordListPayload(name="Greetings")
        )["item"]
        language.update_list_items(
            word_list["list_id"],
            language.ListMembershipPayload(word_ids=[word_id]),
        )
        listed = self.words(list_id=word_list["list_id"])
        self.assertEqual(listed["total"], 1)

        exported = language.export_library()
        self.assertIn(b"keivotos-language-export-v1", exported.body)
        retired = language.delete_word(word_id)
        self.assertEqual(retired["retired"], word_id)
        self.assertEqual(self.words()["total"], 0)

    def test_disabled_endpoints_reject_without_initializing_storage(self) -> None:
        with database.get_user_db() as connection:
            suite_modules.set_enabled(connection, "language", False)
        with self.assertRaises(Exception) as caught:
            language.status()
        self.assertEqual(caught.exception.status_code, 409)
        self.assertFalse(self.descriptor.database.exists())

    def test_analyzer_api_is_local_until_explicit_dictionary_lookup(self) -> None:
        analyzed = {
            "format": "keivotos-language-analysis-v1",
            "text": "안녕하세요.",
            "romanization": "annyeonghaseyo.",
            "sentences": [],
            "tokens": [],
            "grammar": [],
            "engine": {
                "name": "Kiwi",
                "version": "test",
                "provenance": "Local morphology",
            },
        }
        with patch.object(
            language.analyzer,
            "analyze",
            return_value=(analyzed, False),
        ):
            response = language.analyze_text(
                language.AnalyzerPayload(text="안녕하세요.")
            )

        self.assertEqual(response["text"], "안녕하세요.")
        self.assertEqual(response["library"]["token_matches"], {})
        saved = language.save_analyzer_history(
            language.AnalyzerSavePayload(
                text=response["text"],
                translation_en="Hello.",
                translation_mn="Сайн байна уу.",
                analysis=response,
            )
        )["item"]
        self.assertEqual(
            language.analyzer_history(limit=50)["items"][0]["analysis_id"],
            saved["analysis_id"],
        )
        retired = language.retire_analyzer_history(saved["analysis_id"])
        self.assertEqual(retired["retired"], saved["analysis_id"])
        self.assertEqual(language.analyzer_history(limit=50)["items"], [])

        with patch.object(language, "_krdict_api_key", return_value=(None, "none")):
            with self.assertRaises(Exception) as caught:
                language.dictionary_lookup(
                    language.DictionaryPayload(query="안녕")
                )
        self.assertEqual(caught.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
