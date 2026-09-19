from __future__ import annotations

from contextlib import closing, redirect_stderr, redirect_stdout
import io
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from modules.reddit.archive import open_archive  # noqa: E402
from modules.reddit import media  # noqa: E402
from modules.reddit.media import (  # noqa: E402
    EngineResult,
    MediaConfirmationError,
    MediaError,
    MediaLimits,
    build_media_plan,
    classify_asset,
    download_media,
    ensure_linked_assets,
)
import reddit_media  # noqa: E402


class RedditMediaTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory(
            prefix=".tmp-reddit-media-",
            dir=ROOT / "tests",
        )
        self.temp = Path(self._temporary_directory.name)
        self.database = self.temp / "archive" / "reddit.sqlite"
        self.destination = self.temp / "media"
        with open_archive(self.database):
            pass

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    def _asset(
        self,
        role: str,
        url: str,
        *,
        owner_id: str | None = None,
        status: str = "queued",
        local_path: str | None = None,
    ) -> int:
        with open_archive(self.database) as connection:
            cursor = connection.execute(
                """
                INSERT INTO assets(
                    owner_type, owner_id, role, url, desired_policy,
                    local_path, status, first_seen_at, last_seen_at
                ) VALUES('post', ?, ?, ?, 'selected', ?, ?, ?, ?)
                """,
                (
                    owner_id or f"post-{role}-{url}",
                    role,
                    url,
                    local_path,
                    status,
                    "2026-07-27T00:00:00+00:00",
                    "2026-07-27T00:00:00+00:00",
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def _plan(
        self,
        *,
        max_files: int = 100,
        max_file_bytes: int = 1024 * 1024,
        max_run_bytes: int = 10 * 1024 * 1024,
        min_free_bytes: int = 0,
        retry_failed: bool = False,
    ):
        limits = MediaLimits(
            max_files=max_files,
            max_file_bytes=max_file_bytes,
            max_run_bytes=max_run_bytes,
            min_free_bytes=min_free_bytes,
        )
        with patch.object(media, "_disk_free", return_value=100 * 1024 * 1024):
            return build_media_plan(
                self.database,
                self.destination,
                limits,
                retry_failed=retry_failed,
            )

    def test_plan_is_offline_bounded_and_rejects_external_assets(self) -> None:
        self._asset("image-original", "https://i.redd.it/one.png")
        self._asset("subreddit-icon", "https://www.redditstatic.com/icon.png")
        self._asset("video-dash", "https://v.redd.it/video/DASHPlaylist.mpd")
        self._asset("external", "https://example.com/file.png")
        self._asset("image-original", "https://example.com/file.png")
        self._asset(
            "image-original",
            "https://i.redd.it/failed.png",
            status="failed",
        )
        self._asset(
            "image-original",
            "https://i.redd.it/saved.png",
            status="downloaded",
            local_path="objects/saved.png",
        )

        plan = self._plan(max_files=2, max_file_bytes=4096)

        self.assertEqual(plan.selected_assets, 2)
        self.assertEqual(plan.eligible_assets, 3)
        self.assertEqual(plan.failed_not_selected, 1)
        self.assertEqual(plan.already_downloaded, 1)
        self.assertEqual(plan.rejected_external, 1)
        self.assertEqual(plan.rejected_policy, 1)
        self.assertEqual(
            [candidate.engine for candidate in plan.candidates],
            ["gallery-dl", "http"],
        )
        self.assertEqual(plan.required_start_bytes, 4096)
        self.assertTrue(plan.can_start)
        self.assertFalse(self.destination.exists())
        self.assertEqual(len(plan.selection_sha256), 64)
        summary = plan.summary()
        self.assertEqual(
            summary["selected_by_engine"],
            {"gallery-dl": 1, "http": 1},
        )
        self.assertEqual(
            summary["selected_by_host"],
            {"i.redd.it": 1, "www.redditstatic.com": 1},
        )
        self.assertEqual(
            [item["asset_id"] for item in summary["selection_preview"]],
            [plan.candidates[0].asset_id, plan.candidates[1].asset_id],
        )
        self.assertFalse(summary["selection_preview_truncated"])

    def test_role_filter_applies_to_every_plan_status_count(self) -> None:
        self._asset(
            "image-original",
            "https://i.redd.it/saved.png",
            status="downloaded",
            local_path="objects/saved.png",
        )
        self._asset(
            "video-file",
            "https://v.redd.it/video/DASH_720.mp4",
            status="failed",
        )

        limits = MediaLimits(
            max_files=10,
            max_file_bytes=100,
            max_run_bytes=100,
            min_free_bytes=0,
        )
        with patch.object(media, "_disk_free", return_value=1000):
            plan = build_media_plan(
                self.database,
                self.destination,
                limits,
                roles=["image-original"],
            )

        self.assertEqual(plan.already_downloaded, 1)
        self.assertEqual(plan.failed_not_selected, 0)

    def test_policy_rejects_credentials_custom_ports_and_wrong_hosts(self) -> None:
        rejected = (
            ("image-original", "https://user:secret@i.redd.it/image.png"),
            ("image-original", "https://i.redd.it:444/image.png"),
            ("image-original", "http://i.redd.it/image.png"),
            ("video-dash", "https://example.com/DASHPlaylist.mpd"),
        )
        for role, url in rejected:
            with self.subTest(url=url):
                self.assertIsNone(classify_asset(role, url)[0])

    def test_linked_files_use_generic_and_mediafire_engines(self) -> None:
        self.assertEqual(
            classify_asset(
                "linked-file",
                "https://www.mediafire.com/file/key/package.deb/file",
            ),
            ("mediafire", None),
        )
        self.assertEqual(
            classify_asset(
                "linked-file",
                "https://downloads.example.com/archive.zip",
            ),
            ("http-file", None),
        )
        self.assertIsNone(
            classify_asset(
                "linked-file",
                "https://www.mediafire.com/folder/key/files",
            )[0]
        )

    def test_existing_post_and_comment_links_can_be_queued_offline(self) -> None:
        with open_archive(self.database) as connection:
            connection.execute(
                """
                INSERT INTO posts(
                    id, title, selftext, url, first_observed_at, latest_observed_at
                ) VALUES('post1', 'Post', 'See https://files.example/a.zip',
                         'https://www.mediafire.com/file/key/package.deb/file',
                         '2026-07-27T00:00:00+00:00',
                         '2026-07-27T00:00:00+00:00')
                """
            )
            connection.execute(
                """
                INSERT INTO comments(
                    id, post_id, body, first_observed_at, latest_observed_at
                ) VALUES('comment1', 'post1',
                         'Mirror: https://files.example/b.7z',
                         '2026-07-27T00:00:00+00:00',
                         '2026-07-27T00:00:00+00:00')
                """
            )
            connection.commit()

        inserted = ensure_linked_assets(
            self.database,
            scope_type="post",
            scope_id="post1",
        )
        repeated = ensure_linked_assets(
            self.database,
            scope_type="post",
            scope_id="post1",
        )

        self.assertEqual(inserted, 3)
        self.assertEqual(repeated, 0)
        with open_archive(self.database) as connection:
            rows = connection.execute(
                "SELECT owner_type, role, url FROM assets ORDER BY id"
            ).fetchall()
        self.assertEqual(
            [(row["owner_type"], row["role"]) for row in rows],
            [
                ("post", "linked-file"),
                ("post", "linked-file"),
                ("comment", "linked-file"),
            ],
        )

    def test_linked_download_is_content_addressed_and_published_with_name(
        self,
    ) -> None:
        self._asset(
            "linked-file",
            "https://downloads.example.com/package",
            owner_id="linked-post",
        )
        plan = self._plan()

        def runner(candidate, stage, max_bytes, timeout, retries):
            stage.mkdir(parents=True, exist_ok=True)
            path = stage / f"asset-{candidate.asset_id}.deb"
            path.write_bytes(b"package bytes")
            return EngineResult(
                path,
                candidate.url,
                "application/vnd.debian.binary-package",
                suggested_name="example-package.deb",
            )

        summary = download_media(
            plan,
            confirm_assets=1,
            confirm_selection=plan.selection_sha256,
            linked_runner=runner,
            disk_free=lambda path: 100 * 1024 * 1024,
        )

        self.assertEqual(summary.completed, 1)
        self.assertEqual(summary.published_files, 1)
        published = list(
            (self.destination / "library").rglob("*example-package.deb")
        )
        self.assertEqual(len(published), 1)
        self.assertEqual(published[0].read_bytes(), b"package bytes")
        objects = list((self.destination / "objects" / "sha256").rglob("*.deb"))
        self.assertEqual(len(objects), 1)

    def test_reddit_json_html_escaping_is_removed_only_after_policy_check(
        self,
    ) -> None:
        candidate = media.MediaCandidate(
            1,
            "post",
            "one",
            "image-original",
            "https://i.redd.it/one.png?width=640&amp;format=png",
            "gallery-dl",
            "queued",
        )

        self.assertEqual(
            media._network_url(candidate),
            "https://i.redd.it/one.png?width=640&format=png",
        )

    def test_confirmation_must_match_count_and_selection_without_writes(self) -> None:
        self._asset("image-original", "https://i.redd.it/one.png")
        plan = self._plan()

        with self.assertRaises(MediaConfirmationError):
            download_media(
                plan,
                confirm_assets=0,
                confirm_selection=plan.selection_sha256,
            )
        with self.assertRaises(MediaConfirmationError):
            download_media(
                plan,
                confirm_assets=1,
                confirm_selection="0" * 64,
            )

        self.assertFalse(self.destination.exists())
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM asset_download_events"
                ).fetchone()[0],
                0,
            )

    def test_identical_images_are_hash_deduplicated_with_create_only_manifests(
        self,
    ) -> None:
        first_id = self._asset(
            "image-original", "https://i.redd.it/one.png", owner_id="one"
        )
        second_id = self._asset(
            "image-original", "https://i.redd.it/two.png", owner_id="two"
        )
        plan = self._plan()

        def runner(candidate, stage, max_bytes, timeout, process_timeout, retries):
            stage.mkdir(parents=True, exist_ok=True)
            path = stage / f"asset-{candidate.asset_id}.png"
            Image.new("RGB", (4, 4), "blue").save(path)
            return EngineResult(path, candidate.url, "image/png")

        summary = download_media(
            plan,
            confirm_assets=2,
            confirm_selection=plan.selection_sha256,
            gallery_runner=runner,
            disk_free=lambda path: 100 * 1024 * 1024,
        )

        self.assertEqual(summary.completed, 2)
        self.assertEqual(summary.failed, 0)
        self.assertEqual(summary.deduplicated, 1)
        objects = list((self.destination / "objects" / "sha256").rglob("*.png"))
        manifests = list((self.destination / "manifests").rglob("*.json"))
        self.assertEqual(len(objects), 1)
        self.assertEqual(len(manifests), 2)
        for manifest in manifests:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(payload["format"], "keivotos-reddit-media-observation-v1")
            self.assertEqual(payload["object"]["sha256"], objects[0].stem)

        with open_archive(self.database) as connection:
            statuses = connection.execute(
                "SELECT id, status, local_path FROM assets ORDER BY id"
            ).fetchall()
            self.assertEqual([row["id"] for row in statuses], [first_id, second_id])
            self.assertEqual([row["status"] for row in statuses], ["downloaded"] * 2)
            self.assertEqual(statuses[0]["local_path"], statuses[1]["local_path"])
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM media_objects"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM asset_download_events"
                ).fetchone()[0],
                4,
            )

    def test_partial_is_retained_and_failed_asset_requires_retry_flag(self) -> None:
        asset_id = self._asset(
            "image-original", "https://i.redd.it/partial.png"
        )
        plan = self._plan()

        def runner(candidate, stage, max_bytes, timeout, process_timeout, retries):
            stage.mkdir(parents=True, exist_ok=True)
            (stage / f"asset-{candidate.asset_id}.png.part").write_bytes(b"partial")
            raise MediaError("simulated interruption")

        summary = download_media(
            plan,
            confirm_assets=1,
            confirm_selection=plan.selection_sha256,
            gallery_runner=runner,
            disk_free=lambda path: 100 * 1024 * 1024,
        )

        self.assertEqual((summary.attempted, summary.failed), (1, 1))
        self.assertTrue(
            (
                self.destination
                / ".staging"
                / str(asset_id)
                / f"asset-{asset_id}.png.part"
            ).is_file()
        )
        self.assertEqual(self._plan().selected_assets, 0)
        retry_plan = self._plan(retry_failed=True)
        self.assertEqual(retry_plan.selected_assets, 1)

    def test_invalid_completed_image_is_preserved_outside_resumable_stage(self) -> None:
        asset_id = self._asset(
            "image-original", "https://i.redd.it/invalid.jpg"
        )
        plan = self._plan()

        def runner(candidate, stage, max_bytes, timeout, process_timeout, retries):
            stage.mkdir(parents=True, exist_ok=True)
            path = stage / f"asset-{candidate.asset_id}.jpg"
            path.write_bytes(b"not an image")
            return EngineResult(path, candidate.url, "image/jpeg")

        summary = download_media(
            plan,
            confirm_assets=1,
            confirm_selection=plan.selection_sha256,
            gallery_runner=runner,
            disk_free=lambda path: 100 * 1024 * 1024,
        )

        self.assertEqual(summary.failed, 1)
        self.assertFalse(
            (
                self.destination
                / ".staging"
                / str(asset_id)
                / f"asset-{asset_id}.jpg"
            ).exists()
        )
        preserved = list(
            (self.destination / "failed" / str(asset_id)).rglob(
                f"asset-{asset_id}.jpg"
            )
        )
        self.assertEqual(len(preserved), 1)

    def test_post_download_size_check_preserves_oversize_output(self) -> None:
        asset_id = self._asset(
            "image-original", "https://i.redd.it/oversize.png"
        )
        plan = self._plan(max_file_bytes=16, max_run_bytes=16)

        def runner(candidate, stage, max_bytes, timeout, process_timeout, retries):
            stage.mkdir(parents=True, exist_ok=True)
            path = stage / f"asset-{candidate.asset_id}.png"
            path.write_bytes(b"x" * 17)
            return EngineResult(path, candidate.url, "image/png")

        summary = download_media(
            plan,
            confirm_assets=1,
            confirm_selection=plan.selection_sha256,
            gallery_runner=runner,
            disk_free=lambda path: 100 * 1024 * 1024,
        )

        self.assertEqual(summary.failed, 1)
        preserved = list(
            (self.destination / "oversize" / str(asset_id)).rglob(
                f"asset-{asset_id}.png"
            )
        )
        self.assertEqual(len(preserved), 1)
        self.assertEqual(preserved[0].stat().st_size, 17)

    def test_library_aliases_converge_by_owner_and_content_hash(self) -> None:
        payload = b"one image referenced by several Reddit asset roles"
        digest = hashlib.sha256(payload).hexdigest()
        stored_path = self.destination / "objects" / f"{digest}.png"
        stored_path.parent.mkdir(parents=True)
        stored_path.write_bytes(payload)
        stored = media.StoredObject(
            sha256=digest,
            path=stored_path,
            relative_path=f"objects/{digest}.png",
            byte_size=len(payload),
            content_type="image/png",
            deduplicated=False,
        )
        engine_result = EngineResult(
            path=stored_path,
            final_url="https://i.redd.it/repeated.png",
            content_type="image/png",
            suggested_name="repeated.png",
        )
        candidates = [
            media.MediaCandidate(
                1, "post", "same-post", "image-preview",
                "https://i.redd.it/preview.png", "gallery-dl", "queued",
            ),
            media.MediaCandidate(
                2, "post", "same-post", "image-original",
                "https://i.redd.it/original.png", "gallery-dl", "queued",
            ),
        ]
        with open_archive(self.database) as connection:
            first = media._materialize_library_file(
                connection,
                candidate=candidates[0],
                engine_result=engine_result,
                stored=stored,
                destination=self.destination,
            )
            second = media._materialize_library_file(
                connection,
                candidate=candidates[1],
                engine_result=engine_result,
                stored=stored,
                destination=self.destination,
            )

        self.assertEqual(first, second)
        self.assertEqual(
            list((self.destination / "library").rglob("*.png")),
            [first],
        )

    def test_free_space_guard_stops_before_creating_destination(self) -> None:
        self._asset("image-original", "https://i.redd.it/one.png")
        plan = self._plan(max_file_bytes=100, max_run_bytes=100, min_free_bytes=50)

        with self.assertRaises(MediaError):
            download_media(
                plan,
                confirm_assets=1,
                confirm_selection=plan.selection_sha256,
                disk_free=lambda path: 149,
            )

        self.assertFalse(self.destination.exists())

    def test_engine_commands_use_only_stored_url_and_finite_limits(self) -> None:
        image = media.MediaCandidate(
            7,
            "post",
            "one",
            "image-original",
            "https://i.redd.it/one.png",
            "gallery-dl",
            "queued",
        )
        video = media.MediaCandidate(
            8,
            "post",
            "two",
            "video-dash",
            "https://v.redd.it/two/DASHPlaylist.mpd",
            "yt-dlp",
            "queued",
        )
        commands: list[list[str]] = []

        def process(command, *, timeout, label, **_kwargs):
            commands.append(command)
            asset_id = 7 if label == "gallery-dl" else 8
            extension = "png" if label == "gallery-dl" else "mp4"
            (self.temp / label).mkdir(parents=True, exist_ok=True)
            (self.temp / label / f"asset-{asset_id}.{extension}").write_bytes(b"x")

        with (
            patch.object(media, "_gallery_dl_command", return_value=["gallery-dl"]),
            patch.object(media, "_yt_dlp_command", return_value=["yt-dlp"]),
            patch.object(media, "resolve_ffmpeg_executable", return_value="ffmpeg"),
            patch.object(media, "_run_process", side_effect=process),
            patch.object(media.yt_dlp_service, "run_process", side_effect=process),
        ):
            media.run_gallery_dl(image, self.temp / "gallery-dl", 123, 4, 5, 2)
            media.run_yt_dlp(video, self.temp / "yt-dlp", 456, 6, 7, 3)

        gallery_command, video_command = commands
        self.assertEqual(gallery_command[-1], image.url)
        self.assertIn("--config-ignore", gallery_command)
        self.assertEqual(
            gallery_command[gallery_command.index("--filesize-max") + 1],
            "123",
        )
        self.assertEqual(video_command[-1], video.url)
        self.assertIn("--ignore-config", video_command)
        self.assertIn("--no-playlist", video_command)
        self.assertLess(
            video_command.index("--no-overwrites"),
            video_command.index("--continue"),
        )
        self.assertEqual(
            video_command[video_command.index("--max-filesize") + 1],
            "456",
        )
        self.assertEqual(
            video_command[video_command.index("--ffmpeg-location") + 1],
            "ffmpeg",
        )

    def test_cli_plan_prints_confirmation_without_network_or_destination(self) -> None:
        self._asset("image-original", "https://i.redd.it/one.png")
        stdout = io.StringIO()
        stderr = io.StringIO()

        with (
            patch.object(media, "_disk_free", return_value=100 * 1024 * 1024),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            code = reddit_media.main(
                [
                    "plan",
                    "--database",
                    str(self.database),
                    "--destination",
                    str(self.destination),
                    "--max-file-bytes",
                    "1MiB",
                    "--max-run-bytes",
                    "2MiB",
                    "--min-free-bytes",
                    "0",
                ]
            )

        self.assertEqual(code, 0, stderr.getvalue())
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["selected_assets"], 1)
        self.assertEqual(payload["confirmation"]["confirm_assets"], 1)
        self.assertEqual(len(payload["confirmation"]["selection_sha256"]), 64)
        self.assertFalse(self.destination.exists())


if __name__ == "__main__":
    unittest.main()
