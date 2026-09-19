from __future__ import annotations

import sqlite3
from pathlib import Path
import shutil
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from modules.karaoke import catalog, lyrics, storage  # noqa: E402


class KaraokeModuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = ROOT / "tests" / ".tmp-karaoke"
        shutil.rmtree(self.temp, ignore_errors=True)
        self.temp.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_layout_and_containment(self) -> None:
        layout = storage.ensure_layout(self.temp)
        video = layout["library"] / "song" / "video.mp4"
        video.parent.mkdir()
        video.write_bytes(b"video")
        self.assertEqual(
            storage.resolve_within(
                layout["library"], "song/video.mp4", require_file=True
            ),
            video.resolve(),
        )
        with self.assertRaises(storage.KaraokeStorageError):
            storage.resolve_within(layout["library"], "../outside.txt")

    def test_catalog_roundtrip_keeps_tags_and_lyrics(self) -> None:
        with catalog.open_catalog(self.temp / "karaoke.sqlite") as connection:
            catalog.upsert_item(
                connection,
                {
                    "item_id": "kara-moe:one",
                    "provider": "kara-moe",
                    "provider_id": "one",
                    "title": "Song",
                    "subtitle": "Ending from Series",
                    "year": 2026,
                    "duration": 123.0,
                    "primary_video": "one/video.mp4",
                    "thumbnail": None,
                    "metadata_path": "one/source.metadata.json",
                    "receipt_path": "one/acquisition.receipt.json",
                    "primary_sha256": "a" * 64,
                    "metadata": {"kid": "one"},
                },
                {"series": ["Series"], "languages": ["Japanese"]},
                [
                    {
                        "lyric_id": "kara-moe:one:vtt",
                        "label": "Japanese",
                        "language": "ja",
                        "format": "vtt",
                        "source_kind": "generated",
                        "relative_path": "one/lyrics.generated.vtt",
                        "sha256": "b" * 64,
                        "cues": [
                            {"start": 1, "end": 2, "text": "line"},
                            {
                                "start": 2,
                                "end": 3,
                                "text": (
                                    "[{'drawing': [], 'tags': [], 'text': 'Old '}, "
                                    "{'drawing': [], 'tags': [], 'text': 'line'}]"
                                ),
                            },
                        ],
                    }
                ],
            )
            item = catalog.get_item(connection, "kara-moe:one")
        assert item is not None
        self.assertEqual(item["tags"]["series"], ["Series"])
        self.assertEqual(item["lyrics"][0]["cues"][0]["text"], "line")
        self.assertEqual(item["lyrics"][0]["cues"][1]["text"], "Old line")

    def test_precious_state_is_additive_and_immediate(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        catalog.ensure_user_schema(connection)
        self.assertTrue(catalog.set_favorite(connection, "one", "a" * 64, True))
        playlist = catalog.create_playlist(connection, "Favorites", "")
        catalog.add_playlist_item(connection, playlist["playlist_id"], "one", "a" * 64)
        state = catalog.save_playback_state(
            connection,
            "one",
            {
                "file_sha256": "a" * 64,
                "position_seconds": 14,
                "duration_seconds": 100,
                "lyric_offset_seconds": 0.5,
                "repeat_mode": "one",
                "shuffle": False,
            },
        )
        self.assertEqual(catalog.favorite_ids(connection), {"one"})
        self.assertEqual(catalog.list_playlists(connection)[0]["items"][0]["item_key"], "one")
        self.assertEqual(state["position_seconds"], 14)
        self.assertEqual(state["repeat_mode"], "one")
        first_play = catalog.record_play(connection, "one", "a" * 64)
        second_play = catalog.record_play(connection, "one", "a" * 64)
        self.assertEqual(first_play["play_count"], 1)
        self.assertEqual(second_play["play_count"], 2)
        connection.close()

    def test_playlist_management_preserves_media_identity(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        first = catalog.create_playlist(connection, "Original", "Description")
        playlist_id = first["playlist_id"]
        catalog.add_playlist_item(connection, playlist_id, "one", "a" * 64)
        catalog.add_playlist_item(connection, playlist_id, "two", "b" * 64)
        updated = catalog.update_playlist(
            connection, playlist_id, "Renamed", "New description"
        )
        self.assertEqual(updated["name"], "Renamed")
        reordered = catalog.reorder_playlist_items(
            connection, playlist_id, ["two", "one"]
        )
        self.assertEqual(
            [item["item_key"] for item in reordered["items"]],
            ["two", "one"],
        )
        remaining = catalog.remove_playlist_item(connection, playlist_id, "two")
        self.assertEqual(
            [item["item_key"] for item in remaining["items"]], ["one"]
        )
        self.assertTrue(catalog.delete_playlist(connection, playlist_id))
        self.assertEqual(catalog.list_playlists(connection), [])
        connection.close()

    def test_user_subtitle_formats_produce_interactive_cues(self) -> None:
        srt = (
            "1\n00:00:01,000 --> 00:00:02,500\nFirst line\n\n"
            "2\n00:00:03,000 --> 00:00:04,000\nSecond line\n"
        )
        ass = (
            "[Events]\n"
            "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,"
            r"{\k20}Ka{\k20}raoke"
            "\n"
        )
        lrc = "[00:01.00]First line\n[00:03.00]Second line\n"
        self.assertEqual(
            [cue["text"] for cue in lyrics.parse_subtitle_text(srt, "srt")],
            ["First line", "Second line"],
        )
        self.assertEqual(
            lyrics.parse_subtitle_text(ass, "ass")[0]["text"],
            "Karaoke",
        )
        self.assertEqual(
            lyrics.parse_subtitle_text(lrc, "lrc")[0]["end"],
            3.0,
        )

    def test_kara_moe_token_arrays_render_as_text_not_json(self) -> None:
        cues = lyrics.normalize_cues(
            [
                {
                    "start": 1,
                    "end": 3,
                    "fullText": [
                        {"drawing": [], "tags": [], "text": "My "},
                        {"drawing": [], "tags": [], "text": "line"},
                    ],
                }
            ]
        )
        self.assertEqual(cues[0]["text"], "My line")
        self.assertNotIn("drawing", cues[0]["text"])
        preserved_repr = (
            "[{'drawing': [], 'tags': [], 'text': 'My '}, "
            "{'drawing': [], 'tags': [], 'text': 'line'}]"
        )
        self.assertEqual(lyrics.plain_text(preserved_repr), "My line")

    def test_create_only_subtitle_write_never_overwrites(self) -> None:
        destination = self.temp / "lyrics.ass"
        digest, size = storage.write_bytes_create(destination, b"lyrics", 100)
        self.assertEqual(size, 6)
        self.assertEqual(len(digest), 64)
        with self.assertRaises(storage.KaraokeStorageError):
            storage.write_bytes_create(destination, b"changed", 100)
        self.assertEqual(destination.read_bytes(), b"lyrics")

    def test_mp4_integrity_detects_a_truncated_declared_media_box(self) -> None:
        complete = self.temp / "complete.mp4"
        complete.write_bytes(
            b"\x00\x00\x00\x0cftypisom"
            b"\x00\x00\x00\x08moov"
            b"\x00\x00\x00\x0cmdatdata"
        )
        truncated = self.temp / "truncated.mp4"
        truncated.write_bytes(
            b"\x00\x00\x00\x0cftypisom"
            b"\x00\x00\x00\x08moov"
            b"\x00\x00\x00\x20mdatdata"
        )

        self.assertTrue(storage.mp4_integrity(complete)["complete"])
        damaged = storage.mp4_integrity(truncated)
        self.assertFalse(damaged["complete"])
        self.assertEqual(damaged["expected_bytes"], 52)


if __name__ == "__main__":
    unittest.main()
