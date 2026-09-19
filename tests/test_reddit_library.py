from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from modules.reddit.archive import (  # noqa: E402
    CaptureOptions,
    import_local_source,
    open_archive,
)
from modules.reddit.community import (  # noqa: E402
    CommunityImportOptions,
    import_community_source,
)
from modules.reddit.library import (  # noqa: E402
    InvalidCursorError,
    RedditLibrary,
)
from modules.reddit.url_targets import parse_capture_target  # noqa: E402
import reddit_library  # noqa: E402


def _post(index: int) -> dict:
    post_id = f"p{index:04d}"
    return {
        "id": post_id,
        "name": f"t3_{post_id}",
        "subreddit": "BlueArchive" if index % 2 else "OtherSub",
        "author": "sensei" if index % 3 else "student",
        "title": f"Saved post {index}",
        "selftext": f"Searchable body {index}",
        "created_utc": 1_700_000_000 + index,
        "score": index,
        "upvote_ratio": 0.9,
        "num_comments": 1 if index == 149 else 0,
        "permalink": f"/r/BlueArchive/comments/{post_id}/title/",
        "url": f"https://i.redd.it/{post_id}.jpg",
        "link_flair_text": "News" if index % 2 else "Art",
    }


def _comment(post_id: str) -> dict:
    return {
        "id": "comment1",
        "name": "t1_comment1",
        "link_id": f"t3_{post_id}",
        "parent_id": f"t3_{post_id}",
        "subreddit": "BlueArchive",
        "author": "student",
        "body": "Deeply searchable saved reply",
        "created_utc": 1_700_001_000,
        "score": 3,
    }


class RedditLibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory(
            prefix=".tmp-reddit-library-",
            dir=ROOT / "tests",
        )
        self.temp = Path(self._temporary_directory.name)
        self.database = self.temp / "archive" / "reddit.sqlite"
        self.source = self.temp / "posts.jsonl"
        records = [_post(index) for index in range(150)]
        records.append(_comment("p0149"))
        self.source.write_text(
            "".join(f"{json.dumps(record)}\n" for record in records),
            encoding="utf-8",
        )
        import_local_source(
            self.database,
            self.source,
            parse_capture_target("https://reddit.com/r/BlueArchive/"),
            CaptureOptions(posts_limit=None, save_images="original"),
        )
        self.library = RedditLibrary(self.database)

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    def test_feed_uses_stable_bounded_cursor_and_local_media_identity(self) -> None:
        digest = "a" * 64
        with open_archive(self.database) as connection:
            asset = connection.execute(
                """
                SELECT id FROM assets
                WHERE owner_type='post' AND owner_id='p0149'
                ORDER BY id LIMIT 1
                """
            ).fetchone()
            self.assertIsNotNone(asset)
            connection.execute(
                """
                INSERT INTO media_objects(
                    sha256, relative_path, byte_size, content_type, created_at
                ) VALUES(?, ?, ?, ?, ?)
                """,
                (
                    digest,
                    f"objects/sha256/aa/{digest}.jpg",
                    123,
                    "image/jpeg",
                    "2026-07-27T00:00:00+00:00",
                ),
            )
            connection.execute(
                """
                INSERT INTO asset_download_events(
                    attempt_id, asset_id, event_type, engine, source_url,
                    object_sha256, byte_size, created_at
                ) VALUES('attempt', ?, 'complete', 'test', 'https://i.redd.it/x',
                         ?, 123, '2026-07-27T00:00:00+00:00')
                """,
                (asset["id"], digest),
            )
            connection.execute(
                "UPDATE assets SET status='downloaded' WHERE id=?",
                (asset["id"],),
            )
            connection.commit()

        first = self.library.list_posts(limit=100)
        second = self.library.list_posts(
            limit=100,
            cursor=first["next_cursor"],
        )

        self.assertEqual(len(first["items"]), 75)
        self.assertFalse(first["has_more"])
        filtered_first = self.library.list_posts(
            limit=40,
            subreddit="BlueArchive",
        )
        filtered_second = self.library.list_posts(
            limit=40,
            subreddit="BlueArchive",
            cursor=filtered_first["next_cursor"],
        )
        self.assertEqual(len(filtered_first["items"]), 40)
        self.assertEqual(len(filtered_second["items"]), 35)
        self.assertEqual(
            len(
                {
                    item["id"]
                    for item in [
                        *filtered_first["items"],
                        *filtered_second["items"],
                    ]
                }
            ),
            75,
        )
        top = filtered_first["items"][0]
        self.assertEqual(top["id"], "p0149")
        self.assertEqual(top["archived_comment_count"], 1)
        self.assertEqual(top["links"][0]["host"], "i.redd.it")
        self.assertEqual(top["media"]["local"][0]["sha256"], digest)
        self.assertEqual(top["media"]["local"][0]["display_name"], "p0149.jpg")
        self.assertNotIn("url", top["media"]["local"][0])

    def test_invalid_cursor_filters_and_search_are_bounded(self) -> None:
        with self.assertRaises(InvalidCursorError):
            self.library.list_posts(cursor="not-a-cursor")
        filtered = self.library.list_posts(
            limit=10,
            subreddit="BlueArchive",
            author="sensei",
            flair="News",
        )
        self.assertTrue(filtered["items"])
        self.assertTrue(
            all(item["author"] == "sensei" for item in filtered["items"])
        )
        search = self.library.search(
            "Deeply searchable",
            record_type="comment",
        )
        self.assertEqual(search["items"][0]["id"], "comment1")

    def test_popular_community_and_profile_indexes_use_local_records(self) -> None:
        popular = self.library.list_posts(limit=5, sort="popular")
        communities = self.library.list_communities()
        profiles = self.library.list_profiles()
        profile = self.library.get_profile("student")

        self.assertEqual(popular["items"][0]["id"], "p0149")
        self.assertFalse(popular["has_more"])
        self.assertEqual(popular["next_cursor"], None)
        self.assertEqual(communities[0]["subreddit"], "BlueArchive")
        self.assertEqual(communities[0]["posts"], 75)
        self.assertEqual(communities[0]["comments"], 1)
        self.assertEqual(profiles[0]["author"], "sensei")
        self.assertGreater(profiles[0]["posts"], 0)
        self.assertEqual(profile["username"], "student")
        self.assertEqual(profile["stats"]["comments"], 1)
        self.assertEqual(profile["comments"][0]["id"], "comment1")

    def test_post_detail_includes_observations_and_comment_tree(self) -> None:
        detail = self.library.get_post("t3_p0149")

        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(detail["post"]["id"], "p0149")
        self.assertEqual(len(detail["observations"]), 1)
        self.assertEqual(
            detail["comment_tree"]["root_comments"][0]["id"],
            "comment1",
        )
        self.assertIsNone(self.library.get_post("missing"))

    def test_community_latest_snapshots_and_status_are_read_only(self) -> None:
        about = self.temp / "about.json"
        about.write_text(
            json.dumps(
                {
                    "display_name": "BlueArchive",
                    "title": "Blue Archive",
                    "public_description": "Community",
                    "retrieved_on": 1_700_000_000,
                }
            ),
            encoding="utf-8",
        )
        rules = self.temp / "rules.json"
        rules.write_text(
            json.dumps(
                {
                    "subreddit": "BlueArchive",
                    "retrieved_on": 1_700_000_000,
                    "rules": [{"short_name": "Be kind", "priority": 0}],
                }
            ),
            encoding="utf-8",
        )
        for source_type, source in (("about", about), ("rules", rules)):
            import_community_source(
                self.database,
                source,
                "BlueArchive",
                CommunityImportOptions(source_type=source_type),
            )

        community = self.library.get_community("r/BlueArchive")
        status = self.library.status()

        self.assertEqual(community["about"]["title"], "Blue Archive")
        self.assertEqual(
            community["rules"]["items"][0]["short_name"],
            "Be kind",
        )
        self.assertIsNone(community["moderators"])
        self.assertEqual(status["counts"]["posts"], 75)
        self.assertEqual(status["counts"]["comments"], 1)
        self.assertEqual(status["counts"]["communities"], 1)
        self.assertEqual(status["counts"]["duplicate_alias_candidates"], 0)

    def test_missing_database_status_and_cli_are_clean(self) -> None:
        missing = RedditLibrary(self.temp / "missing.sqlite")
        self.assertFalse(missing.status()["initialized"])
        self.assertEqual(missing.list_posts()["items"], [])
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = reddit_library.main(
                ["status", "--database", str(self.database)]
            )
        self.assertEqual(result, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertTrue(json.loads(stdout.getvalue())["initialized"])


if __name__ == "__main__":
    unittest.main()
