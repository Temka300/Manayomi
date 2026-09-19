from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import database  # noqa: E402
import config  # noqa: E402
from modules.reddit import descriptor as reddit_descriptor  # noqa: E402
from modules.reddit.archive import (  # noqa: E402
    CaptureOptions,
    import_local_source,
    open_archive,
)
from modules.reddit.arctic_shift_api import ArcticShiftApiError  # noqa: E402
from modules.reddit.media import DownloadSummary  # noqa: E402
from modules.reddit.download_jobs import RedditDownloadJobs  # noqa: E402
from modules.reddit.url_targets import parse_capture_target  # noqa: E402
from routers import reddit  # noqa: E402
import suite_modules  # noqa: E402


def _request(range_value: str | None = None) -> Request:
    headers = []
    if range_value is not None:
        headers.append((b"range", range_value.encode("ascii")))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": headers,
            "query_string": b"",
            "server": ("test", 80),
            "client": ("test", 1),
            "scheme": "http",
        }
    )


class RedditRuntimeApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory(
            prefix=".tmp-reddit-runtime-",
            dir=ROOT / "tests",
        )
        self.temp = Path(self._temporary_directory.name)
        self.home = self.temp / "modules" / "reddit"
        self.database = self.home / "reddit.sqlite"
        self.user_database = self.temp / "user.sqlite"
        source = self.temp / "post.jsonl"
        source.write_text(
            json.dumps(
                {
                    "id": "abc123",
                    "name": "t3_abc123",
                    "subreddit": "BlueArchive",
                    "author": "sensei",
                    "title": "Runtime post",
                    "selftext": "Runtime body",
                    "created_utc": 1_700_000_000,
                    "score": 42,
                    "upvote_ratio": 0.9,
                    "num_comments": 0,
                    "url": "https://i.redd.it/abc123.jpg",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        import_local_source(
            self.database,
            source,
            parse_capture_target(
                "https://reddit.com/r/BlueArchive/comments/abc123/title/"
            ),
            CaptureOptions(posts_limit=1, save_images="original"),
        )
        descriptor = reddit_descriptor(self.temp, "test")
        self._patches = [
            patch.object(database, "USER_DB_PATH", self.user_database),
            patch.object(config, "FILES_DB_PATH", self.temp / "base" / "files.sqlite"),
            patch.object(reddit, "REDDIT_DESCRIPTOR", descriptor),
            patch.object(reddit, "MEDIA_ROOT", self.home / "media"),
            patch.object(reddit, "_DOWNLOAD_JOBS", RedditDownloadJobs()),
        ]
        for item in self._patches:
            item.start()
        with database.get_user_db() as connection:
            suite_modules.ensure_schema(connection)

    def tearDown(self) -> None:
        for item in reversed(self._patches):
            item.stop()
        self._temporary_directory.cleanup()

    def _enable(self) -> None:
        with database.get_user_db() as connection:
            suite_modules.set_enabled(connection, "reddit", True)

    def test_disabled_module_rejects_read_requests(self) -> None:
        with self.assertRaises(HTTPException) as caught:
            reddit.status()
        self.assertEqual(caught.exception.status_code, 409)

    def test_capture_requires_enablement_and_accepts_user_profiles(self) -> None:
        request = reddit.RedditCaptureRequest(
            url="https://reddit.com/r/BlueArchive/comments/abc123/title/"
        )
        with self.assertRaises(HTTPException) as disabled:
            reddit.capture_link(request)
        self.assertEqual(disabled.exception.status_code, 409)

        self._enable()
        user_result = {
            "format": "keivotos-reddit-direct-capture-result-v1",
            "capture": {
                "target_kind": "user",
                "target_url": "https://www.reddit.com/user/example/",
            },
            "imports": [],
            "indexed": {
                "target_kind": "user",
                "target_id": "example",
                "posts": 2,
                "comments": 4,
            },
        }
        with patch.object(
            reddit,
            "capture_direct_target",
            return_value=user_result,
        ) as capture:
            response = reddit.capture_link(
                reddit.RedditCaptureRequest(url="https://reddit.com/user/example/")
            )
        self.assertEqual(response, user_result)
        self.assertEqual(capture.call_args.args[0].kind, "user")

    def test_capture_uses_descriptor_paths_and_returns_direct_result(self) -> None:
        self._enable()
        result = {
            "format": "keivotos-reddit-direct-capture-result-v1",
            "capture": {
                "capture_id": "capture-1",
                "target_kind": "post",
                "target_url": "https://www.reddit.com/comments/abc123/",
                "post_count": 1,
                "comment_count": 3,
            },
            "imports": [{"posts_imported": 1, "comments_imported": 3}],
            "indexed": {
                "target_kind": "post",
                "target_id": "abc123",
                "posts": 1,
                "comments": 3,
            },
        }
        with patch.object(
            reddit,
            "capture_direct_target",
            return_value=result,
        ) as capture:
            response = reddit.capture_link(
                reddit.RedditCaptureRequest(
                    url="https://reddit.com/r/BlueArchive/comments/abc123/title/"
                )
            )

        self.assertEqual(response, result)
        target = capture.call_args.args[0]
        self.assertEqual((target.kind, target.post_id), ("post", "abc123"))
        self.assertEqual(
            capture.call_args.kwargs["database_path"],
            self.database,
        )
        self.assertEqual(
            capture.call_args.kwargs["output_root"],
            self.home / "archives" / "direct",
        )
        self.assertEqual(
            capture.call_args.kwargs["media_directory"],
            self.home / "media",
        )

    def test_capture_refuses_success_without_indexed_post_evidence(self) -> None:
        self._enable()
        result = {
            "format": "keivotos-reddit-direct-capture-result-v1",
            "capture": {"target_kind": "post"},
            "imports": [{"posts_imported": 0, "comments_imported": 7}],
        }
        with patch.object(
            reddit,
            "capture_direct_target",
            return_value=result,
        ):
            with self.assertRaises(HTTPException) as caught:
                reddit.capture_link(
                    reddit.RedditCaptureRequest(
                        url="https://reddit.com/comments/abc123/title/"
                    )
                )
        self.assertEqual(caught.exception.status_code, 500)
        self.assertIn("without proving", caught.exception.detail)

    def test_capture_maps_upstream_errors_and_releases_serialization_lock(self) -> None:
        self._enable()
        request = reddit.RedditCaptureRequest(
            url="https://reddit.com/r/BlueArchive/"
        )
        with patch.object(
            reddit,
            "capture_direct_target",
            side_effect=ArcticShiftApiError("service unavailable"),
        ):
            with self.assertRaises(HTTPException) as caught:
                reddit.capture_link(request)
        self.assertEqual(caught.exception.status_code, 502)

        result = {
            "format": "keivotos-reddit-direct-capture-result-v1",
            "capture": {},
            "imports": [],
        }
        with patch.object(
            reddit,
            "capture_direct_target",
            return_value=result,
        ):
            self.assertEqual(reddit.capture_link(request), result)

    def test_feed_search_post_community_and_status_use_local_library(self) -> None:
        self._enable()

        feed = reddit.feed(
            limit=25,
            cursor=None,
            subreddit=None,
            author=None,
            flair=None,
            sort="new",
        )
        search = reddit.search(
            q="Runtime",
            limit=25,
            subreddit=None,
            author=None,
            record_type="post",
        )
        post = reddit.post("abc123", max_comments=100)
        community = reddit.community("BlueArchive")
        communities = reddit.communities()
        profiles = reddit.profiles()
        profile = reddit.profile("sensei")
        status = reddit.status()

        self.assertEqual(feed["items"][0]["id"], "abc123")
        self.assertEqual(search["items"][0]["id"], "abc123")
        self.assertEqual(post["post"]["title"], "Runtime post")
        self.assertEqual(community["subreddit"], "bluearchive")
        self.assertEqual(communities["items"][0]["subreddit"], "BlueArchive")
        self.assertEqual(profiles["items"][0]["author"], "sensei")
        self.assertEqual(profile["username"], "sensei")
        self.assertEqual(profile["stats"]["posts"], 1)
        self.assertEqual(status["counts"]["posts"], 1)
        self.assertEqual(status["storage"]["archive"], str(self.home))
        self.assertEqual(
            status["storage"]["files_library"],
            str(self.home / "media" / "library"),
        )
        self.assertGreater(status["limits"]["max_files"], 0)
        self.assertGreater(status["limits"]["max_file_bytes"], 0)
        self.assertFalse(status["runtime"]["capture_busy"])
        self.assertFalse(status["runtime"]["download_busy"])

    def test_media_is_sha_addressed_contained_and_supports_ranges(self) -> None:
        self._enable()
        data = b"local-reddit-media"
        digest = "b" * 64
        object_path = self.home / "media" / "objects" / "sha256" / "bb"
        object_path.mkdir(parents=True)
        media_file = object_path / f"{digest}.jpg"
        media_file.write_bytes(data)
        with open_archive(self.database) as connection:
            asset = connection.execute(
                "SELECT id FROM assets ORDER BY id LIMIT 1"
            ).fetchone()
            self.assertIsNotNone(asset)
            connection.execute(
                """
                INSERT INTO media_objects(
                    sha256, relative_path, byte_size, content_type, created_at
                ) VALUES(?, ?, ?, 'image/jpeg', '2026-07-27T00:00:00+00:00')
                """,
                (
                    digest,
                    media_file.relative_to(self.home / "media").as_posix(),
                    len(data),
                ),
            )
            connection.execute(
                """
                INSERT INTO asset_download_events(
                    attempt_id, asset_id, event_type, engine, source_url,
                    object_sha256, byte_size, created_at
                ) VALUES('runtime', ?, 'complete', 'test',
                         'https://i.redd.it/abc123.jpg', ?, ?,
                         '2026-07-27T00:00:00+00:00')
                """,
                (asset["id"], digest, len(data)),
            )
            connection.execute(
                "UPDATE assets SET status='downloaded', local_path=? WHERE id=?",
                (str(media_file), asset["id"]),
            )
            connection.commit()

        full = reddit.media(digest, _request())
        partial = reddit.media(digest, _request("bytes=0-4"))

        self.assertEqual(full.media_type, "image/jpeg")
        self.assertEqual(partial.status_code, 206)
        self.assertEqual(partial.headers["content-range"], f"bytes 0-4/{len(data)}")
        self.assertEqual(partial.headers["x-content-type-options"], "nosniff")

    def test_media_plan_is_scoped_and_downloads_publish_to_files(self) -> None:
        self._enable()
        selection = reddit.RedditMediaSelection(
            target_kind="post",
            target_id="abc123",
            images=True,
        )
        planned = reddit.media_plan(selection)
        self.assertEqual(planned["plan"]["selected_assets"], 1)

        library = self.home / "media" / "library" / "BlueArchive"
        library.mkdir(parents=True)
        (library / "saved.jpg").write_bytes(b"saved")
        request = reddit.RedditMediaDownloadRequest(
            **selection.model_dump(),
            confirm_assets=planned["plan"]["confirmation"]["confirm_assets"],
            confirm_selection=planned["plan"]["confirmation"]["selection_sha256"],
        )
        with patch.object(
            reddit,
            "download_media",
            return_value=DownloadSummary(
                planned=1,
                attempted=1,
                completed=1,
                published_files=1,
            ),
        ):
            result = reddit.media_download(request)

        self.assertTrue(result["files"]["published"])
        self.assertEqual(result["files"]["scan"]["files"], 1)

    def test_media_job_reports_progress_after_drawer_can_close(self) -> None:
        self._enable()
        selection = reddit.RedditMediaSelection(
            target_kind="post",
            target_id="abc123",
            images=True,
        )
        planned = reddit.media_plan(selection)["plan"]
        request = reddit.RedditMediaDownloadRequest(
            **selection.model_dump(),
            confirm_assets=planned["confirmation"]["confirm_assets"],
            confirm_selection=planned["confirmation"]["selection_sha256"],
        )

        def download(_plan, *, on_progress, **_kwargs):
            on_progress(
                {
                    "phase": "downloading",
                    "planned": 1,
                    "attempted": 1,
                    "completed": 1,
                    "failed": 0,
                    "bytes_acquired": 5,
                }
            )
            return DownloadSummary(
                planned=1,
                attempted=1,
                completed=1,
                published_files=1,
                bytes_acquired=5,
            )

        with (
            patch.object(reddit, "download_media", side_effect=download),
            patch.object(
                reddit,
                "_publish_downloads_to_files",
                return_value={"published": True, "source_id": "reddit", "scan": {}},
            ),
        ):
            started = reddit.start_media_job(request)["job"]
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                current = reddit.media_job(started["job_id"])["job"]
                if current["status"] not in {"queued", "running"}:
                    break
                time.sleep(0.01)

        self.assertEqual(current["status"], "completed")
        self.assertEqual(current["progress"], 1.0)
        self.assertEqual(current["completed"], 1)

    def test_media_outside_module_root_is_rejected(self) -> None:
        self._enable()
        digest = "c" * 64
        outside = self.temp / "outside.jpg"
        outside.write_bytes(b"x")
        with open_archive(self.database) as connection:
            asset = connection.execute(
                "SELECT id FROM assets ORDER BY id LIMIT 1"
            ).fetchone()
            connection.execute(
                """
                INSERT INTO media_objects(
                    sha256, relative_path, byte_size, content_type, created_at
                ) VALUES(?, 'outside.jpg', 1, 'image/jpeg',
                         '2026-07-27T00:00:00+00:00')
                """,
                (digest,),
            )
            connection.execute(
                """
                INSERT INTO asset_download_events(
                    attempt_id, asset_id, event_type, engine, source_url,
                    object_sha256, byte_size, created_at
                ) VALUES('outside', ?, 'complete', 'test',
                         'https://i.redd.it/abc123.jpg', ?, 1,
                         '2026-07-27T00:00:00+00:00')
                """,
                (asset["id"], digest),
            )
            connection.execute(
                "UPDATE assets SET status='downloaded', local_path=? WHERE id=?",
                (str(outside), asset["id"]),
            )
            connection.commit()

        with self.assertRaises(HTTPException) as caught:
            reddit.media(digest, _request())
        self.assertEqual(caught.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
