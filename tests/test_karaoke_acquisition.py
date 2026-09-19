from __future__ import annotations

from pathlib import Path
import shutil
import sys
import threading
import time
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from module_registry import build_registry  # noqa: E402
from modules.karaoke import catalog, kara_moe, lyrics  # noqa: E402
from modules.karaoke.acquisition import (  # noqa: E402
    KaraokeAcquisitionError,
    KaraokeAcquisitionManager,
    _require_free_space,
)


KARA = {
    "kid": "83754e4f-cd58-4e4a-b199-950de1fdc8a3",
    "songname": "Akogare no Zankyô",
    "year": 2026,
    "duration": 260,
    "created_at": "2026-05-10T10:51:58Z",
    "tags": {
        "series": [{"name": "Blue Archive"}],
        "langs": [{"name": "Japanese"}, {"name": "English"}],
        "singers": [{"name": "DAZBEE"}],
        "songwriters": [{"name": "Mitsukiyo"}, {"name": "Yoshimi Yûno"}],
        "creators": [{"name": "Yostar Pictures"}],
        "authors": [{"name": "Nemesise"}],
        "origins": [{"name": "Video Game"}],
        "platforms": [{"name": "Mobile Game"}, {"name": "PC"}],
        "groups": [{"name": "2020s"}],
        "collections": [{"name": "Geek / Otaku"}],
        "franchises": [{"name": "Blue Archive"}],
        "types": [{"name": "Ending"}],
    },
    "lyrics_infos": {"language": "Japanese", "filename": "source.ass"},
    "lyrics": [
        {"start": 1.0, "end": 2.5, "fullText": r"{\k20}A{\k30}ko{\k20}gare"},
        {"start": 3.0, "end": 4.0, "fullText": "next line"},
    ],
    "mediasize": 1024,
}


def complete_mp4(size: int = 1024) -> bytes:
    ftyp = (16).to_bytes(4, "big") + b"ftyp" + b"isom0000"
    moov = (8).to_bytes(4, "big") + b"moov"
    remaining = size - len(ftyp) - len(moov)
    return ftyp + moov + remaining.to_bytes(4, "big") + b"mdat" + bytes(remaining - 8)


class KaraokeAcquisitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = ROOT / "tests" / ".tmp-karaoke-acquisition"
        shutil.rmtree(self.temp, ignore_errors=True)
        self.temp.mkdir(parents=True)
        self.descriptor = build_registry(self.temp, "1.1.2").require("karaoke")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_normalization_matches_metadata_first_detail(self) -> None:
        value = kara_moe.normalize(KARA)
        self.assertEqual(value["title"], "Akogare no Zankyô")
        self.assertEqual(value["subtitle"], "Ending from Blue Archive")
        self.assertEqual(value["tags"]["singers"], ["DAZBEE"])
        self.assertEqual(value["tags"]["platforms"], ["Mobile Game", "PC"])
        cues = lyrics.normalize_cues(KARA["lyrics"])
        self.assertEqual(cues[0]["text"], "Akogare")
        self.assertTrue(lyrics.to_webvtt(cues).startswith("WEBVTT"))
        self.assertIn("[00:01.00]Akogare", lyrics.to_lrc(cues))

    def test_plan_requires_exact_selection_and_authorization(self) -> None:
        manager = KaraokeAcquisitionManager(self.descriptor)
        with patch.object(kara_moe, "detail", return_value=KARA):
            plan = manager.plan(KARA["kid"], max_bytes=4096)
        self.assertEqual(plan["estimated_bytes"], 1024)
        self.assertTrue(plan["authorization_required"])
        with self.assertRaises(KaraokeAcquisitionError):
            manager.start(
                token=plan["token"],
                selection_sha256=plan["selection_sha256"],
                authorized=False,
            )
        with self.assertRaises(KaraokeAcquisitionError):
            manager.start(
                token=plan["token"],
                selection_sha256="0" * 64,
                authorized=True,
            )

    def test_free_space_reserve_is_checked_before_transfer(self) -> None:
        with patch(
            "modules.karaoke.acquisition.shutil.disk_usage",
            return_value=Mock(free=1),
        ):
            with self.assertRaisesRegex(KaraokeAcquisitionError, "safety reserve"):
                _require_free_space(self.temp, 1024)

    def test_worker_publishes_video_receipts_and_generated_lyrics(self) -> None:
        published = Mock()
        manager = KaraokeAcquisitionManager(
            self.descriptor,
            on_complete=published,
        )

        def download(
            provider_id,
            destination,
            *,
            user_agent,
            max_bytes,
            timeout,
            on_progress,
            cancel_event,
        ):
            self.assertEqual(provider_id, KARA["kid"])
            self.assertIsInstance(cancel_event, threading.Event)
            destination.write_bytes(complete_mp4(KARA["mediasize"]))
            on_progress(KARA["mediasize"], KARA["mediasize"])
            return {
                "final_url": "https://kara.moe/hardsubs/song.mp4",
                "content_type": "video/mp4",
                "bytes": KARA["mediasize"],
            }

        with (
            patch.object(kara_moe, "detail", return_value=KARA),
            patch.object(kara_moe, "download_hardsub", side_effect=download),
            patch(
                "modules.karaoke.acquisition.storage.create_video_thumbnail",
                return_value=False,
            ),
        ):
            plan = manager.plan(KARA["kid"], max_bytes=4096)
            job = manager.start(
                token=plan["token"],
                selection_sha256=plan["selection_sha256"],
                authorized=True,
            )
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                current = manager.job(job["job_id"])
                if current["status"] in {"completed", "failed", "cancelled"}:
                    break
                time.sleep(0.02)
            else:
                self.fail("Karaoke acquisition job did not finish")

        self.assertEqual(current["status"], "completed", current.get("error"))
        self.assertEqual(current["item_id"], f"kara-moe:{KARA['kid']}")
        with catalog.open_catalog(self.descriptor.database) as connection:
            item = catalog.get_item(connection, current["item_id"])
        assert item is not None
        self.assertTrue(
            (self.descriptor.home / "media" / "library" / item["primary_video"]).is_file()
        )
        self.assertEqual({track["format"] for track in item["lyrics"]}, {"vtt", "lrc"})
        self.assertTrue(
            (
                self.descriptor.home
                / "media"
                / "library"
                / item["receipt_path"]
            ).is_file()
        )
        published.assert_called_once_with()

    def test_incomplete_provider_media_stays_resumable_and_is_not_published(self) -> None:
        manager = KaraokeAcquisitionManager(self.descriptor)

        def download(_provider_id, destination, **_kwargs):
            destination.write_bytes(b"short")
            return {
                "final_url": "https://kara.moe/hardsubs/song.mp4",
                "content_type": "video/mp4",
                "bytes": 5,
            }

        with (
            patch.object(kara_moe, "detail", return_value=KARA),
            patch.object(kara_moe, "download_hardsub", side_effect=download),
        ):
            plan = manager.plan(KARA["kid"], max_bytes=4096)
            job = manager.start(
                token=plan["token"],
                selection_sha256=plan["selection_sha256"],
                authorized=True,
            )
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                current = manager.job(job["job_id"])
                if current["status"] in {"completed", "failed", "cancelled"}:
                    break
                time.sleep(0.02)

        self.assertEqual(current["status"], "failed")
        self.assertIn("incomplete media file", current["error"])
        partial = (
            self.descriptor.home
            / "staging"
            / job["job_id"]
            / "video.mp4.part"
        )
        self.assertEqual(partial.read_bytes(), b"short")
        self.assertFalse(
            (self.descriptor.home / "media" / "library" / plan["selection"]["destination"]).exists()
        )


if __name__ == "__main__":
    unittest.main()
