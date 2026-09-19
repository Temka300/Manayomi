from __future__ import annotations

import json
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
from modules.youtube import catalog, provider  # noqa: E402
from modules.youtube.acquisition import (  # noqa: E402
    YouTubeAcquisitionError,
    YouTubeAcquisitionManager,
    _require_free_space,
)
from services.yt_dlp import ProcessResult  # noqa: E402


METADATA = {
    "video_id": "abc123xyz00",
    "title": "Local Song",
    "channel": "Artist",
    "duration": 240,
    "upload_date": "20260728",
    "view_count": 1234,
    "webpage_url": "https://www.youtube.com/watch?v=abc123xyz00",
    "thumbnail_url": "https://i.ytimg.com/vi/abc123xyz00/hqdefault.jpg",
    "formats": [
        {
            "format_id": "22",
            "ext": "mp4",
            "width": 1280,
            "height": 720,
            "fps": 30,
            "vcodec": "avc1.64001F",
            "acodec": "mp4a.40.2",
            "filesize": 1000,
            "tbr": 1000,
            "abr": 128,
            "format_note": "720p",
            "resolution": "1280x720",
        },
        {
            "format_id": "137",
            "ext": "mp4",
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "vcodec": "avc1.640028",
            "acodec": "none",
            "filesize": 2000,
            "tbr": 2000,
            "abr": None,
            "format_note": "1080p",
            "resolution": "1920x1080",
        },
        {
            "format_id": "140",
            "ext": "m4a",
            "width": None,
            "height": None,
            "fps": None,
            "vcodec": "none",
            "acodec": "mp4a.40.2",
            "filesize": 500,
            "tbr": 128,
            "abr": 128,
            "format_note": "medium",
            "resolution": "audio only",
        },
    ],
    "available_resolutions": [720, 1080],
    "subtitles": {"en": ["vtt"], "ja": ["ass", "vtt"]},
    "automatic_captions": {"fr": ["vtt"]},
    "description": "A test song",
    "sanitized_metadata": {
        "id": "abc123xyz00",
        "title": "Local Song",
        "channel": "Artist",
    },
}


class YouTubeModuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = ROOT / "tests" / ".tmp-youtube"
        shutil.rmtree(self.temp, ignore_errors=True)
        self.temp.mkdir(parents=True)
        self.descriptor = build_registry(self.temp, "1.1.2").require("youtube")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_search_uses_bounded_machine_readable_yt_dlp(self) -> None:
        output = json.dumps(
            {
                "entries": [
                    {
                        "id": "abc123xyz00",
                        "title": "Local Song",
                        "uploader": "Artist",
                        "duration": 240,
                        "url": "abc123xyz00",
                        "thumbnail": "https://i.ytimg.com/test.jpg",
                    }
                ]
            }
        )
        with patch.object(
            provider.yt_dlp_service,
            "run_process",
            return_value=ProcessResult(0, output),
        ) as run:
            values = provider.search("local song", limit=1)
        command = run.call_args.args[0]
        self.assertIn("--dump-single-json", command)
        self.assertIn("--flat-playlist", command)
        self.assertEqual(command[-1], "ytsearch1:local song")
        self.assertEqual(values[0]["video_id"], "abc123xyz00")
        self.assertEqual(values[0]["webpage_url"], provider.watch_url("abc123xyz00"))

    def test_format_selection_is_actual_and_resolution_bounded(self) -> None:
        selected = provider.select_formats(
            METADATA,
            resolution="1080",
            compatibility=True,
        )
        self.assertEqual(selected["selector"], "137+140")
        self.assertEqual(selected["quality_label"], "1080p")
        self.assertEqual(selected["estimated_bytes"], 2500)

    def test_public_youtube_urls_are_normalized_to_one_video_id(self) -> None:
        self.assertEqual(
            provider.video_id_from_url(
                "https://www.youtube.com/watch?v=abc123xyz00&t=10"
            ),
            "abc123xyz00",
        )
        self.assertEqual(
            provider.video_id_from_url("https://youtu.be/abc123xyz00"),
            "abc123xyz00",
        )
        self.assertEqual(
            provider.video_id_from_url(
                "https://www.youtube.com/shorts/abc123xyz00"
            ),
            "abc123xyz00",
        )
        with self.assertRaises(provider.YouTubeProviderError):
            provider.video_id_from_url("https://example.com/watch?v=abc123xyz00")

    def test_resolution_wins_before_container_compatibility(self) -> None:
        metadata = {
            **METADATA,
            "formats": [
                *METADATA["formats"],
                {
                    "format_id": "308",
                    "ext": "webm",
                    "width": 2560,
                    "height": 1440,
                    "fps": 60,
                    "vcodec": "vp9",
                    "acodec": "none",
                    "filesize": 3000,
                    "tbr": 3000,
                    "abr": None,
                    "format_note": "1440p",
                    "resolution": "2560x1440",
                },
            ],
        }
        selected = provider.select_formats(
            metadata,
            resolution="1440",
            compatibility=True,
        )
        self.assertEqual(selected["selector"], "308+140")
        self.assertEqual(selected["quality_label"], "1440p")

    def test_plan_requires_authorization_and_selects_caption_languages(self) -> None:
        manager = YouTubeAcquisitionManager(self.descriptor)
        with patch.object(provider, "inspect", return_value=METADATA):
            plan = manager.plan(
                video_id="abc123xyz00",
                resolution="1080",
                compatibility=True,
                audio_format="mp3",
                audio_quality="192K",
                subtitle_languages=["en", "fr", "missing"],
                automatic_captions=False,
                karaoke_intent=True,
                max_bytes=4096,
            )
        self.assertEqual(plan["selection"]["format_ids"], ["137", "140"])
        self.assertEqual(plan["selection"]["subtitle_languages"], ["en"])
        self.assertEqual(plan["selection"]["subtitle_sources"], {"en": "manual"})
        self.assertTrue(plan["files"]["companion_audio"])
        with self.assertRaises(YouTubeAcquisitionError):
            manager.start(
                token=plan["token"],
                selection_sha256=plan["selection_sha256"],
                authorized=False,
            )

    def test_plan_labels_automatic_captions_separately(self) -> None:
        manager = YouTubeAcquisitionManager(self.descriptor)
        with patch.object(provider, "inspect", return_value=METADATA):
            plan = manager.plan(
                video_id="abc123xyz00",
                resolution="720",
                compatibility=True,
                audio_format="none",
                audio_quality="192K",
                subtitle_languages=["en", "fr"],
                automatic_captions=True,
                karaoke_intent=False,
                max_bytes=4096,
            )
        self.assertEqual(
            plan["selection"]["subtitle_sources"],
            {"en": "manual", "fr": "automatic"},
        )
        command = manager._subtitle_command(plan, self.temp / "stage")
        assert command is not None
        self.assertIn("--write-auto-subs", command)
        self.assertIn("--sleep-subtitles", command)
        self.assertNotIn("--write-auto-subs", manager._media_command(plan, self.temp / "stage"))

    def test_existing_variant_gets_a_clean_replacement_destination(self) -> None:
        manager = YouTubeAcquisitionManager(self.descriptor)
        arguments = {
            "video_id": "abc123xyz00",
            "resolution": "720",
            "compatibility": True,
            "audio_format": "none",
            "audio_quality": "192K",
            "subtitle_languages": [],
            "automatic_captions": False,
            "karaoke_intent": False,
            "max_bytes": 4096,
        }
        with patch.object(provider, "inspect", return_value=METADATA):
            original = manager.plan(**arguments)
            (
                self.descriptor.home
                / "media"
                / "library"
                / original["destination"]
            ).mkdir(parents=True)
            replacement = manager.plan(**arguments)

        self.assertTrue(replacement["replacement"])
        self.assertIn("replacement-", replacement["destination"])

    def test_free_space_reserve_includes_post_processing(self) -> None:
        plan = {
            "estimated_bytes": 1024,
            "selection": {"audio_format": "mp3"},
        }
        with patch(
            "modules.youtube.acquisition.shutil.disk_usage",
            return_value=Mock(free=1),
        ):
            with self.assertRaisesRegex(
                YouTubeAcquisitionError, "post-processing"
            ):
                _require_free_space(self.temp, plan)

    def test_worker_publishes_local_video_for_files_handoff(self) -> None:
        published = Mock()
        manager = YouTubeAcquisitionManager(
            self.descriptor,
            on_complete=published,
        )

        def process(
            command,
            *,
            timeout,
            on_line,
            cancel_event,
            label,
            error_type,
        ):
            output = Path(command[command.index("--output") + 1])
            output.parent.mkdir(parents=True, exist_ok=True)
            (output.parent / "media.mp4").write_bytes(b"video")
            (output.parent / "media.en.vtt").write_text(
                "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nLine\n",
                encoding="utf-8",
            )
            (output.parent / "media.jpg").write_bytes(b"image")
            on_line("keivotos-progress:downloading|5|5|1|0")
            return ProcessResult(0, "")

        with (
            patch.object(provider, "inspect", return_value=METADATA),
            patch(
                "modules.youtube.acquisition.resolve_ffmpeg_executable",
                return_value="ffmpeg",
            ),
            patch.object(
                provider.yt_dlp_service,
                "run_streaming_process",
                side_effect=process,
            ),
        ):
            plan = manager.plan(
                video_id="abc123xyz00",
                resolution="1080",
                compatibility=True,
                audio_format="none",
                audio_quality="192K",
                subtitle_languages=["en"],
                automatic_captions=False,
                karaoke_intent=True,
                max_bytes=4096,
            )
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
                self.fail("YouTube acquisition job did not finish")

        self.assertEqual(current["status"], "completed", current.get("error"))
        with catalog.open_catalog(self.descriptor.database) as connection:
            item = catalog.get_item(connection, current["item_id"])
        assert item is not None
        self.assertTrue(
            (self.descriptor.home / "media" / "library" / item["video_path"]).is_file()
        )
        self.assertTrue(item["karaoke_intent"])
        self.assertEqual(item["subtitles"][0]["format"], "vtt")
        self.assertFalse(item["subtitles"][0]["automatic"])
        published.assert_called_once_with()

    def test_second_download_is_queued_while_first_is_active(self) -> None:
        manager = YouTubeAcquisitionManager(self.descriptor)
        entered = threading.Event()
        release = threading.Event()
        media_calls = 0

        def process(command, **_kwargs):
            nonlocal media_calls
            output = Path(command[command.index("--output") + 1])
            output.parent.mkdir(parents=True, exist_ok=True)
            (output.parent / "media.mp4").write_bytes(b"video")
            (output.parent / "media.jpg").write_bytes(b"image")
            media_calls += 1
            if media_calls == 1:
                entered.set()
                release.wait(5)
            return ProcessResult(0, "")

        with (
            patch.object(provider, "inspect", return_value=METADATA),
            patch(
                "modules.youtube.acquisition.resolve_ffmpeg_executable",
                return_value="ffmpeg",
            ),
            patch.object(
                provider.yt_dlp_service,
                "run_streaming_process",
                side_effect=process,
            ),
        ):
            first_plan = manager.plan(
                video_id="abc123xyz00",
                resolution="720",
                compatibility=True,
                audio_format="none",
                audio_quality="192K",
                subtitle_languages=[],
                automatic_captions=False,
                karaoke_intent=False,
                max_bytes=4096,
            )
            second_plan = manager.plan(
                video_id="abc123xyz00",
                resolution="1080",
                compatibility=True,
                audio_format="none",
                audio_quality="192K",
                subtitle_languages=[],
                automatic_captions=False,
                karaoke_intent=False,
                max_bytes=4096,
            )
            first = manager.start(
                token=first_plan["token"],
                selection_sha256=first_plan["selection_sha256"],
                authorized=True,
            )
            self.assertTrue(entered.wait(2))
            second = manager.start(
                token=second_plan["token"],
                selection_sha256=second_plan["selection_sha256"],
                authorized=True,
            )
            self.assertEqual(manager.job(second["job_id"])["status"], "queued")
            release.set()
            deadline = time.monotonic() + 5
            pending_ids = {first["job_id"], second["job_id"]}
            while time.monotonic() < deadline and pending_ids:
                pending_ids = {
                    job_id
                    for job_id in pending_ids
                    if manager.job(job_id)["status"]
                    not in {"completed", "failed", "cancelled"}
                }
                if pending_ids:
                    time.sleep(0.02)
            self.assertFalse(pending_ids, "Queued YouTube jobs did not settle")


if __name__ == "__main__":
    unittest.main()
