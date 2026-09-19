from __future__ import annotations

import json
from pathlib import Path
import shutil
import sqlite3
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from modules.language import catalog, library, storage, user_state  # noqa: E402


class LanguageLibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = ROOT / "tests" / ".tmp-language-library"
        shutil.rmtree(self.temp, ignore_errors=True)
        self.temp.mkdir(parents=True)
        self.catalog_context = catalog.open_catalog(self.temp / "language.sqlite")
        self.catalog = self.catalog_context.__enter__()
        self.user = sqlite3.connect(self.temp / "user.sqlite")
        self.user.row_factory = sqlite3.Row
        user_state.ensure_user_schema(self.user)
        self.library_root = storage.ensure_layout(self.temp / "module")["library"]

    def tearDown(self) -> None:
        self.catalog_context.__exit__(None, None, None)
        self.user.close()
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_manual_word_edit_media_lists_practice_export_and_retirement(self) -> None:
        word_id = library.create_manual_word(
            self.catalog,
            self.user,
            {
                "headword": "축하하다",
                "sentence_form": "축하해요",
                "senses": [
                    {"lang": "en", "text": "to congratulate"},
                    {"lang": "mn", "text": "Баяр хүргэх"},
                ],
                "examples": [
                    {
                        "sentence": "생일 축하해요!",
                        "translations": [{"lang": "en", "text": "Happy birthday!"}],
                    }
                ],
                "tags": ["KO1K"],
                "personal_note": "Remember the 하다 form.",
            },
        )
        word = library.effective_word(self.catalog, self.user, word_id)
        self.assertEqual(word["headword"], "축하하다")
        self.assertEqual(word["senses"][1]["lang"], "mn")
        self.assertEqual(word["personal_note"], "Remember the 하다 form.")

        library.update_word(
            self.catalog,
            self.user,
            word_id,
            {"reading": "chukhahada", "personal_note": "edited"},
        )
        edited = library.effective_word(self.catalog, self.user, word_id)
        self.assertEqual(edited["reading"], "chukhahada")
        self.assertEqual(edited["personal_note"], "edited")

        media = library.attach_media(
            self.catalog,
            self.user,
            self.library_root,
            word_id=word_id,
            role="word_audio",
            filename="word.mp3",
            payload=b"audio-one",
        )
        self.assertTrue((self.library_root / media["relative_path"]).is_file())
        attached = library.effective_word(self.catalog, self.user, word_id)
        self.assertEqual(attached["media_by_role"]["word_audio"]["sha256"], media["sha256"])

        word_list = library.create_word_list(self.user, "Known", "Study set")
        library.set_list_membership(self.user, word_list["list_id"], [word_id], True)
        self.assertEqual(library.list_word_lists(self.user)[0]["word_ids"], [word_id])
        session = library.create_practice_session(
            self.user,
            mode="ko_meaning",
            word_ids=[word_id],
            length=20,
        )
        library.answer_practice(
            self.user,
            session_id=session["session_id"],
            word_id=word_id,
            correct=True,
            finish=True,
        )
        practiced = library.effective_word(self.catalog, self.user, word_id)
        self.assertEqual(practiced["practice"]["accuracy"], 1.0)
        stats = library.practice_stats(self.user)
        self.assertEqual(stats["totals"]["completed_sessions"], 1)
        self.assertEqual(stats["totals"]["answers"], 1)
        self.assertEqual(stats["totals"]["accuracy"], 1.0)
        self.assertEqual(stats["streak"]["current_days"], 1)
        self.assertEqual(stats["activity"][0]["answers"], 1)
        self.assertEqual(stats["words"][0]["word_id"], word_id)

        exported = library.export_payload(self.catalog, self.user)
        self.assertEqual(exported["format"], "keivotos-language-export-v1")
        self.assertEqual(exported["words"][0]["word_id"], word_id)
        json.dumps(exported, ensure_ascii=False)

        library.retire_manual_word(self.catalog, self.user, word_id)
        precious = self.user.execute(
            "SELECT retired_at, payload_json FROM language_user_words WHERE word_id=?",
            (word_id,),
        ).fetchone()
        self.assertIsNotNone(precious["retired_at"])
        self.assertIn("축하하다", precious["payload_json"])
        self.assertIsNone(library.effective_word(self.catalog, self.user, word_id))
        self.assertTrue((self.library_root / media["relative_path"]).is_file())

    def test_mirrored_edits_are_overrides_and_revert_to_mirror(self) -> None:
        word_id = catalog.word_id_for_source("anki", 42)
        self.catalog.execute(
            "INSERT INTO language_words"
            "(word_id, lang, headword, sentence_form, source, source_key, "
            "note_type, deck, fields_json) "
            "VALUES (?, 'ko', '단어', '단어', 'anki', '42', 'KO1Kv2', "
            "'Deck', '{}')",
            (word_id,),
        )
        self.catalog.commit()

        library.update_word(
            self.catalog,
            self.user,
            word_id,
            {"headword": "내 단어", "senses": [{"lang": "en", "text": "word"}]},
        )
        mirrored = self.catalog.execute(
            "SELECT headword FROM language_words WHERE word_id=?",
            (word_id,),
        ).fetchone()
        effective = library.effective_word(self.catalog, self.user, word_id)
        self.assertEqual(mirrored["headword"], "단어")
        self.assertEqual(effective["headword"], "내 단어")
        self.assertTrue(effective["edited"])

        library.revert_overrides(self.user, word_id)
        reverted = library.effective_word(self.catalog, self.user, word_id)
        self.assertEqual(reverted["headword"], "단어")
        self.assertFalse(reverted["edited"])
        with self.assertRaises(ValueError):
            library.retire_manual_word(self.catalog, self.user, word_id)

    def test_filtering_uses_effective_values_and_weakest_card(self) -> None:
        first = library.create_manual_word(
            self.catalog,
            self.user,
            {
                "headword": "하나",
                "senses": [{"lang": "en", "text": "one"}],
                "tags": ["number"],
                "sort_index": 1,
            },
        )
        second = library.create_manual_word(
            self.catalog,
            self.user,
            {
                "headword": "둘",
                "senses": [{"lang": "en", "text": "two"}],
                "sort_index": 2,
            },
        )
        sentence_word = library.create_manual_word(
            self.catalog,
            self.user,
            {
                "headword": "셋",
                "senses": [{"lang": "en", "text": "three"}],
                "examples": [{"sentence": "셋이에요.", "translations": []}],
                "notes_text": [{"kind": "grammar", "body": "Copula form"}],
                "sort_index": 3,
            },
        )
        self.catalog.execute(
            "INSERT INTO language_progress"
            "(word_id, card_id, interval, stage, synced_at) "
            "VALUES (?, '1', 30, 'mature', datetime('now'))",
            (first,),
        )
        self.catalog.execute(
            "INSERT INTO language_progress"
            "(word_id, card_id, interval, stage, synced_at) "
            "VALUES (?, '2', 5, 'young', datetime('now'))",
            (first,),
        )
        self.catalog.commit()
        items, total = library.list_words(
            self.catalog,
            self.user,
            query="one",
            tag="number",
            stage="young",
            offset=0,
            limit=60,
        )
        self.assertEqual(total, 1)
        self.assertEqual(items[0]["word_id"], first)
        self.assertEqual(items[0]["weakest_interval"], 5)
        all_items, _ = library.list_words(
            self.catalog,
            self.user,
            offset=0,
            limit=60,
        )
        self.assertEqual(
            [item["word_id"] for item in all_items],
            [first, second, sentence_word],
        )
        sentence_items, sentence_total = library.list_words(
            self.catalog,
            self.user,
            content="sentences",
            offset=0,
            limit=1,
        )
        grammar_items, grammar_total = library.list_words(
            self.catalog,
            self.user,
            content="grammar",
            offset=0,
            limit=1,
        )
        self.assertEqual(sentence_total, 1)
        self.assertEqual(sentence_items[0]["word_id"], sentence_word)
        self.assertEqual(grammar_total, 1)
        self.assertEqual(grammar_items[0]["word_id"], sentence_word)

    def test_language_sorts_are_alphabetical_and_keep_missing_senses_last(self) -> None:
        values = [
            ("바나나", "banana", "гадил"),
            ("사과", "apple", "алим"),
            ("물", "", ""),
        ]
        for index, (headword, english, mongolian) in enumerate(values, start=1):
            library.create_manual_word(
                self.catalog,
                self.user,
                {
                    "headword": headword,
                    "sort_index": index,
                    "senses": [
                        *([{"lang": "en", "text": english}] if english else []),
                        *([{"lang": "mn", "text": mongolian}] if mongolian else []),
                    ],
                },
            )

        english, _ = library.list_words(
            self.catalog,
            self.user,
            sort="english",
            offset=0,
            limit=60,
        )
        english_reverse, _ = library.list_words(
            self.catalog,
            self.user,
            sort="english",
            descending=True,
            offset=0,
            limit=60,
        )
        mongolian, _ = library.list_words(
            self.catalog,
            self.user,
            sort="mongolian",
            offset=0,
            limit=60,
        )
        korean, _ = library.list_words(
            self.catalog,
            self.user,
            sort="korean",
            offset=0,
            limit=60,
        )

        self.assertEqual([word["headword"] for word in english], ["사과", "바나나", "물"])
        self.assertEqual([word["headword"] for word in english_reverse], ["바나나", "사과", "물"])
        self.assertEqual([word["headword"] for word in mongolian], ["사과", "바나나", "물"])
        self.assertEqual([word["headword"] for word in korean], ["물", "바나나", "사과"])


if __name__ == "__main__":
    unittest.main()
