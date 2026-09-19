from __future__ import annotations

import json
from pathlib import Path
import shutil
import sqlite3
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from modules.language import analyzer, catalog, dictionary, library, user_state  # noqa: E402
from services import secret_store  # noqa: E402


class LanguageAnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = ROOT / "tests" / ".tmp-language-analyzer"
        shutil.rmtree(self.temp, ignore_errors=True)
        self.temp.mkdir(parents=True)
        self.catalog_context = catalog.open_catalog(self.temp / "language.sqlite")
        self.catalog = self.catalog_context.__enter__()
        self.user = sqlite3.connect(self.temp / "user.sqlite")
        self.user.row_factory = sqlite3.Row
        user_state.ensure_user_schema(self.user)

    def tearDown(self) -> None:
        self.catalog_context.__exit__(None, None, None)
        self.user.close()
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_kiwi_golden_analysis_is_cached_and_explainable(self) -> None:
        text = "비록 우리가 예상했던 것보다 상황이 복잡했지만 괜찮아요."
        result, cached = analyzer.analyze(self.catalog, text)
        second, second_cached = analyzer.analyze(self.catalog, text)

        self.assertFalse(cached)
        self.assertTrue(second_cached)
        self.assertEqual(second, result)
        self.assertEqual(result["engine"]["name"], "Kiwi")
        self.assertIn("uriga", result["romanization"])
        token_pairs = [(token["surface"], token["tag"]) for token in result["tokens"]]
        self.assertIn(("가", "JKS"), token_pairs)
        self.assertIn(("보다", "JKB"), token_pairs)
        self.assertIn(("지만", "EC"), token_pairs)
        expected = next(
            token for token in result["tokens"] if token["surface"] == "예상"
        )
        self.assertEqual(expected["group_lemma"], "예상하다")
        grammar_patterns = {rule["pattern"] for rule in result["grammar"]}
        self.assertTrue({"이/가", "-았/었-", "-던", "보다", "-지만"}.issubset(grammar_patterns))

    def test_analyzer_matches_effective_library_and_exact_translation(self) -> None:
        sentence = "우리가 예상했던 것보다 복잡했어요."
        word_id = library.create_manual_word(
            self.catalog,
            self.user,
            {
                "headword": "예상하다",
                "sentence_form": "예상했던",
                "senses": [
                    {"lang": "en", "text": "to expect"},
                    {"lang": "mn", "text": "таамаглах"},
                ],
                "examples": [
                    {
                        "sentence": sentence,
                        "translations": [
                            {"lang": "en", "text": "It was more complicated than we expected."},
                            {"lang": "mn", "text": "Бидний бодсоноос илүү төвөгтэй байлаа."},
                        ],
                    }
                ],
            },
        )
        result, _ = analyzer.analyze(self.catalog, sentence)
        context = library.analyzer_library_context(
            self.catalog,
            self.user,
            source_text=sentence,
            tokens=result["tokens"],
        )

        matches = [
            match
            for values in context["token_matches"].values()
            for match in values
        ]
        self.assertTrue(any(match["word_id"] == word_id for match in matches))
        self.assertEqual(context["exact_example"]["word_id"], word_id)
        self.assertEqual(
            context["exact_example"]["translations"][0]["lang"],
            "en",
        )

    def test_saved_analysis_is_precious_additive_and_soft_retired(self) -> None:
        result, _ = analyzer.analyze(self.catalog, "오늘은 날씨가 좋아요.")
        saved = library.save_analysis(
            self.user,
            source_text=result["text"],
            translation_en="The weather is nice today.",
            translation_mn="Өнөөдөр цаг агаар сайхан байна.",
            analysis=result,
        )
        updated = library.save_analysis(
            self.user,
            source_text=result["text"],
            translation_en="Today's weather is nice.",
            translation_mn="Өнөөдөр цаг агаар сайхан байна.",
            analysis=result,
            analysis_id=saved["analysis_id"],
        )

        self.assertEqual(len(library.list_saved_analyses(self.user)), 1)
        self.assertEqual(updated["translation_en"], "Today's weather is nice.")
        library.retire_saved_analysis(self.user, saved["analysis_id"])
        self.assertEqual(library.list_saved_analyses(self.user), [])
        preserved = self.user.execute(
            "SELECT source_text, analysis_json, retired_at "
            "FROM language_analyzer_saved WHERE analysis_id=?",
            (saved["analysis_id"],),
        ).fetchone()
        self.assertEqual(preserved["source_text"], result["text"])
        self.assertIsNotNone(preserved["retired_at"])
        self.assertEqual(json.loads(preserved["analysis_json"])["format"], result["format"])

    def test_krdict_lookup_is_explicit_bounded_and_cached(self) -> None:
        calls: list[str] = []

        def fake_remote(*, query: str, language: str, api_key: str, user_agent: str):
            self.assertEqual(api_key, "secret")
            self.assertEqual(user_agent, "Keivotos/test")
            calls.append(language)
            return [
                {
                    "word": query,
                    "part_of_speech": "verb",
                    "language": language,
                    "translated_word": "",
                    "definition": "expect" if language == "en" else "таамаглах",
                    "sense_order": 1,
                    "target_code": 42,
                }
            ]

        with patch.object(dictionary, "_remote_lookup", side_effect=fake_remote):
            first = dictionary.lookup(
                self.catalog,
                query="예상하다",
                api_key="secret",
                user_agent="Keivotos/test",
            )
        with patch.object(
            dictionary,
            "_remote_lookup",
            side_effect=AssertionError("network"),
        ):
            second = dictionary.lookup(
                self.catalog,
                query="예상하다",
                api_key="secret",
                user_agent="Keivotos/test",
            )

        self.assertEqual(calls, ["en", "mn"])
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])
        self.assertEqual({entry["language"] for entry in second["entries"]}, {"en", "mn"})

    def test_secret_file_preserves_independent_anki_and_dictionary_keys(self) -> None:
        path = self.temp / "language_credentials.json"
        with (
            patch.object(secret_store, "protect", side_effect=lambda value, _description: f"protected:{value}"),
            patch.object(secret_store, "unprotect", side_effect=lambda value: value.removeprefix("protected:")),
        ):
            secret_store.save_secret(path, "api_key_dpapi", "anki", "Anki")
            secret_store.save_secret(
                path,
                "krdict_api_key_dpapi",
                "dictionary",
                "KRDICT",
            )
            self.assertEqual(secret_store.load_secret(path, "api_key_dpapi"), "anki")
            self.assertEqual(
                secret_store.load_secret(path, "krdict_api_key_dpapi"),
                "dictionary",
            )
            secret_store.clear_secret_key(path, "api_key_dpapi")
            self.assertIsNone(secret_store.load_secret(path, "api_key_dpapi"))
            self.assertEqual(
                secret_store.load_secret(path, "krdict_api_key_dpapi"),
                "dictionary",
            )


if __name__ == "__main__":
    unittest.main()
