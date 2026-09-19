from __future__ import annotations

from contextlib import closing, redirect_stderr, redirect_stdout
import gzip
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from modules.reddit import archive  # noqa: E402
from modules.reddit.archive import (  # noqa: E402
    CaptureOptions,
    ResumeRequiredError,
    UnsupportedSourceError,
    import_local_source,
    open_archive,
    search_archive,
)
from modules.reddit.url_targets import (  # noqa: E402
    TargetParseError,
    parse_capture_target,
)
import reddit_capture  # noqa: E402


def _post(
    post_id: str,
    *,
    subreddit: str = "BlueArchive",
    author: str = "sensei",
    title: str | None = None,
) -> dict:
    return {
        "id": post_id,
        "name": f"t3_{post_id}",
        "subreddit": subreddit,
        "author": author,
        "title": title or f"Post {post_id}",
        "selftext": f"Archive text for {post_id}",
        "created_utc": 1_700_000_000,
        "edited": False,
        "score": 42,
        "upvote_ratio": 0.9,
        "num_comments": 2,
        "permalink": f"/r/{subreddit}/comments/{post_id}/sample/",
        "url": f"https://i.redd.it/{post_id}.jpg",
        "domain": "i.redd.it",
        "is_self": False,
        "over_18": False,
        "spoiler": False,
        "stickied": False,
        "locked": False,
        "archived": False,
        "link_flair_text": "News",
        "thumbnail": f"https://preview.redd.it/{post_id}.jpg",
        "preview": {
            "images": [
                {
                    "source": {
                        "url": f"https://preview.redd.it/{post_id}-source.jpg"
                    },
                    "resolutions": [
                        {
                            "url": (
                                f"https://preview.redd.it/{post_id}-small.jpg"
                            )
                        }
                    ],
                }
            ]
        },
        "media": {
            "reddit_video": {
                "dash_url": f"https://v.redd.it/{post_id}/DASHPlaylist.mpd",
                "hls_url": f"https://v.redd.it/{post_id}/HLSPlaylist.m3u8",
                "fallback_url": f"https://v.redd.it/{post_id}/DASH_720.mp4",
            }
        },
        "likes": True,
        "saved": True,
    }


def _comment(
    comment_id: str,
    post_id: str,
    *,
    subreddit: str = "BlueArchive",
    parent_id: str | None = None,
    author: str = "student",
) -> dict:
    return {
        "id": comment_id,
        "name": f"t1_{comment_id}",
        "link_id": f"t3_{post_id}",
        "parent_id": parent_id or f"t3_{post_id}",
        "subreddit": subreddit,
        "author": author,
        "body": f"Nested searchable comment {comment_id}",
        "body_html": f"<p>Nested searchable comment {comment_id}</p>",
        "created_utc": 1_700_000_100,
        "edited": False,
        "score": 7,
        "depth": 0 if parent_id is None else 1,
        "is_submitter": False,
        "distinguished": None,
        "stickied": False,
        "score_hidden": False,
        "controversiality": 0,
        "permalink": f"/r/{subreddit}/comments/{post_id}/_/{comment_id}/",
        "likes": None,
    }


class RedditTargetTests(unittest.TestCase):
    def test_subreddit_name_and_listing_url_are_canonicalized(self) -> None:
        by_name = parse_capture_target("r/BlueArchive")
        listing = parse_capture_target(
            "http://old.reddit.com/r/BlueArchive/top/?t=year#ignored"
        )

        self.assertEqual(by_name.kind, "subreddit")
        self.assertEqual(by_name.subreddit, "BlueArchive")
        self.assertEqual(
            by_name.canonical_url, "https://www.reddit.com/r/BlueArchive/"
        )
        self.assertEqual(listing.sort, "top")
        self.assertEqual(listing.time_filter, "year")
        self.assertEqual(
            listing.canonical_url,
            "https://www.reddit.com/r/BlueArchive/top/?t=year",
        )

    def test_post_user_search_and_asset_urls_are_identified(self) -> None:
        post = parse_capture_target(
            "https://www.reddit.com/r/BlueArchive/comments/abc123/title/def456/"
        )
        user = parse_capture_target("https://reddit.com/u/Sensei/comments/")
        search = parse_capture_target(
            "https://www.reddit.com/r/BlueArchive/search/?q=archive&sort=new&t=year"
        )
        asset = parse_capture_target("https://i.redd.it/example.png?width=800")
        self.assertEqual((post.kind, post.post_id, post.comment_id), ("post", "abc123", "def456"))
        self.assertEqual((user.kind, user.username, user.sort), ("user", "Sensei", "comments"))
        self.assertEqual((search.kind, search.query, search.subreddit), ("search", "archive", "BlueArchive"))
        self.assertEqual(asset.kind, "asset")

    def test_web_archive_urls_are_explicitly_rejected(self) -> None:
        for value in (
            "https://web.archive.org/web/20250102030405/"
            "https://www.reddit.com/r/BlueArchive/comments/abc123/title/",
            "https://example.com/export.warc",
            "https://example.com/export.warc.gz",
            "https://example.com/export.wacz",
        ):
            with self.subTest(value=value):
                with self.assertRaisesRegex(TargetParseError, "outside this module"):
                    parse_capture_target(value)

    def test_unbounded_home_credentials_and_bad_names_are_rejected(self) -> None:
        for value in (
            "https://www.reddit.com/",
            "https://user:secret@reddit.com/r/test/",
            "r/not valid",
        ):
            with self.subTest(value=value):
                with self.assertRaises(TargetParseError):
                    parse_capture_target(value)


class RedditArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory(
            prefix=".tmp-reddit-capture-",
            dir=ROOT / "tests",
        )
        self.temp = Path(self._temporary_directory.name)
        self.database = self.temp / "archive" / "reddit.sqlite"
        self.target = parse_capture_target("https://reddit.com/r/BlueArchive/")

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    def _write_jsonl(self, name: str, records: list[object], *, invalid: bool = False) -> Path:
        path = self.temp / name
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False))
                handle.write("\n")
            if invalid:
                handle.write("{broken json\n")
        return path

    def test_stream_import_preserves_raw_chunks_indexes_threads_and_queues_assets(self) -> None:
        first_post = _post("p1", title="Aru preservation guide")
        first_post["selftext"] += " https://cdn.example.com/reference.png"
        embedded_media_comment = _comment("c1", "p1")
        embedded_media_comment["body"] += " https://i.redd.it/comment-media.png"
        records = [
            first_post,
            _post("p2", title="Hina archive"),
            embedded_media_comment,
            _comment("c2", "p1", parent_id="t1_c1"),
            _comment("c3", "p2"),
            _post("other", subreddit="OtherSub"),
            _comment("otherc", "other", subreddit="OtherSub"),
            {"unrecognized": True},
        ]
        source = self._write_jsonl("records.jsonl", records, invalid=True)
        options = CaptureOptions(
            posts_limit=2,
            comments="all",
            save_images="both",
            save_videos="manifest",
            save_external_assets=True,
            external_domains=("example.com",),
            media_directory=str(self.temp / "media"),
            chunk_size=3,
        )

        summary = import_local_source(
            self.database, source, self.target, options
        )

        self.assertEqual(summary.status, "complete")
        self.assertEqual(summary.records_seen, 9)
        self.assertEqual(summary.posts_imported, 2)
        self.assertEqual(summary.comments_imported, 3)
        self.assertEqual(summary.records_imported, 5)
        self.assertEqual(summary.records_skipped, 3)
        self.assertEqual(summary.errors, 1)
        raw_files = sorted(Path(summary.raw_directory).glob("*.jsonl.gz"))
        self.assertEqual(len(raw_files), 3)
        manifest = json.loads(
            (Path(summary.raw_directory) / "manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifest["target"]["subreddit"], "BlueArchive")
        self.assertEqual(manifest["options"]["posts_limit"], 2)
        raw_lines = []
        for raw_file in raw_files:
            with gzip.open(raw_file, "rt", encoding="utf-8") as handle:
                raw_lines.extend(handle.readlines())
        self.assertEqual(len(raw_lines), 9)

        with open_archive(self.database) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM posts").fetchone()[0],
                2,
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM comments").fetchone()[0],
                3,
            )
            nested = connection.execute(
                "SELECT post_id, parent_id, depth FROM comments WHERE id='c2'"
            ).fetchone()
            self.assertEqual(
                (nested["post_id"], nested["parent_id"], nested["depth"]),
                ("p1", "t1_c1", 1),
            )
            observation = connection.execute(
                "SELECT my_vote, reddit_saved FROM post_observations WHERE post_id='p1'"
            ).fetchone()
            self.assertEqual((observation["my_vote"], observation["reddit_saved"]), (1, 1))
            queued_roles = {
                row["role"]
                for row in connection.execute("SELECT role FROM assets").fetchall()
            }
            self.assertTrue(
                {
                    "image-original",
                    "thumbnail",
                    "preview-source",
                    "video-dash",
                    "video-hls",
                    "embedded-image",
                    "external",
                }
                <= queued_roles
            )
            post_hits = search_archive(connection, "Aru preservation")
            comment_hits = search_archive(
                connection, "searchable comment c2", record_type="comment"
            )
            self.assertEqual(post_hits[0]["id"], "p1")
            self.assertEqual(comment_hits[0]["id"], "c2")

    def test_existing_job_requires_resume_and_resume_is_idempotent(self) -> None:
        source = self._write_jsonl(
            "resume.jsonl",
            [_post("p1"), _comment("c1", "p1")],
        )
        options = CaptureOptions(posts_limit=5, chunk_size=1)
        first = import_local_source(self.database, source, self.target, options)

        with self.assertRaises(ResumeRequiredError):
            import_local_source(self.database, source, self.target, options)
        resumed = import_local_source(
            self.database, source, self.target, options, resume=True
        )

        self.assertEqual(resumed, first)
        with open_archive(self.database) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM source_records").fetchone()[0],
                2,
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM post_observations").fetchone()[0],
                1,
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM comment_observations").fetchone()[0],
                1,
            )

    def test_failed_chunk_run_resumes_from_last_committed_line(self) -> None:
        source = self._write_jsonl(
            "interrupted.jsonl",
            [_post("p1"), _post("p2"), _post("p3"), _post("p4")],
        )
        options = CaptureOptions(posts_limit=None, chunk_size=2)
        real_process_chunk = archive._process_chunk
        calls = 0

        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("simulated interruption")
            return real_process_chunk(*args, **kwargs)

        with patch("modules.reddit.archive._process_chunk", side_effect=fail_second):
            with self.assertRaisesRegex(RuntimeError, "simulated interruption"):
                import_local_source(self.database, source, self.target, options)

        resumed = import_local_source(
            self.database, source, self.target, options, resume=True
        )

        self.assertEqual(resumed.status, "complete")
        self.assertEqual(resumed.records_seen, 4)
        self.assertEqual(resumed.posts_imported, 4)
        with open_archive(self.database) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM posts").fetchone()[0],
                4,
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM source_records").fetchone()[0],
                4,
            )

    def test_post_limit_applies_to_comment_only_sources(self) -> None:
        source = self._write_jsonl(
            "comments.jsonl",
            [
                _comment("c1", "p1"),
                _comment("c2", "p2"),
                _comment("c3", "p3"),
                _comment("c4", "p1"),
            ],
        )
        options = CaptureOptions(posts_limit=2)

        summary = import_local_source(
            self.database, source, self.target, options
        )

        self.assertEqual(summary.comments_imported, 3)
        with open_archive(self.database) as connection:
            post_ids = {
                row["post_id"]
                for row in connection.execute(
                    "SELECT post_id FROM capture_job_posts"
                ).fetchall()
            }
            self.assertEqual(post_ids, {"p1", "p2"})
            self.assertIsNone(
                connection.execute("SELECT id FROM comments WHERE id='c3'").fetchone()
            )

    def test_comments_none_keeps_raw_record_without_indexing_it(self) -> None:
        source = self._write_jsonl(
            "no-comments.jsonl",
            [_post("p1"), _comment("c1", "p1")],
        )
        options = CaptureOptions(posts_limit=5, comments="none")

        summary = import_local_source(
            self.database, source, self.target, options
        )

        self.assertEqual(summary.records_seen, 2)
        self.assertEqual(summary.posts_imported, 1)
        self.assertEqual(summary.comments_imported, 0)
        with open_archive(self.database) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM source_records").fetchone()[0],
                2,
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM comments").fetchone()[0],
                0,
            )

    def test_gzip_jsonl_is_streamed_and_warc_fails_before_database_creation(self) -> None:
        gzip_source = self.temp / "records.jsonl.gz"
        with gzip.open(gzip_source, "wt", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(_post("p1")))
            handle.write("\n")
        summary = import_local_source(
            self.database,
            gzip_source,
            self.target,
            CaptureOptions(posts_limit=1),
        )
        self.assertEqual(summary.posts_imported, 1)

        unsupported_db = self.temp / "unsupported" / "reddit.sqlite"
        warc_source = self.temp / "records.warc.gz"
        warc_source.write_bytes(b"not a real WARC")
        with self.assertRaises(UnsupportedSourceError):
            import_local_source(
                unsupported_db,
                warc_source,
                self.target,
                CaptureOptions(),
            )
        self.assertFalse(unsupported_db.exists())

    def test_search_filters_by_subreddit_author_and_record_type(self) -> None:
        source = self._write_jsonl(
            "search.jsonl",
            [
                _post("p1", author="Sensei", title="Unique archive subject"),
                _comment("c1", "p1", author="Student"),
            ],
        )
        import_local_source(
            self.database, source, self.target, CaptureOptions(posts_limit=1)
        )

        with open_archive(self.database) as connection:
            self.assertEqual(
                [row["id"] for row in search_archive(
                    connection,
                    "archive subject",
                    subreddit="bluearchive",
                    author="sensei",
                    record_type="post",
                )],
                ["p1"],
            )
            self.assertEqual(
                search_archive(
                    connection,
                    "archive subject",
                    author="student",
                    record_type="post",
                ),
                [],
            )

    def test_cli_writes_json_summary_without_creating_media_directory(self) -> None:
        source = self._write_jsonl("cli.jsonl", [_post("p1")])
        database = self.temp / "cli" / "reddit.sqlite"
        media = self.temp / "future-media"
        stdout = io.StringIO()
        stderr = io.StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = reddit_capture.main(
                [
                    "--subreddit",
                    "BlueArchive",
                    "--source-file",
                    str(source),
                    "--posts",
                    "500000",
                    "--database",
                    str(database),
                    "--media-directory",
                    str(media),
                    "--save-images",
                    "original",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(result, 0)
        self.assertEqual(payload["posts_imported"], 1)
        self.assertEqual(stderr.getvalue(), "")
        self.assertFalse(media.exists())
        with closing(sqlite3.connect(database)) as connection:
            policy = json.loads(
                connection.execute(
                    "SELECT policy_json FROM capture_jobs"
                ).fetchone()[0]
            )
        self.assertEqual(policy["posts_limit"], 500000)
        self.assertEqual(policy["save_images"], "original")


if __name__ == "__main__":
    unittest.main()
