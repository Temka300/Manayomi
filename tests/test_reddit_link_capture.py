from __future__ import annotations

from contextlib import closing, redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from modules.reddit.archive import CaptureOptions, import_local_source  # noqa: E402
from modules.reddit.arctic_shift_api import (  # noqa: E402
    ArcticShiftApiClient,
    DirectCaptureBundle,
    _JsonResponse,
)
from modules.reddit.comment_trees import build_comment_tree  # noqa: E402
from modules.reddit.community import (  # noqa: E402
    CommunityImportOptions,
    import_community_source,
)
from modules.reddit.url_targets import parse_capture_target  # noqa: E402
import reddit_capture  # noqa: E402


FIXED_NOW = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)


def _post(post_id: str = "abc123") -> dict:
    return {
        "kind": "t3",
        "data": {
            "id": post_id,
            "name": f"t3_{post_id}",
            "subreddit": "BlueArchive",
            "author": "sensei",
            "title": "A preserved direct-link post",
            "selftext": "Body",
            "created_utc": 1_700_000_000,
            "score": 42,
            "upvote_ratio": 0.91,
            "num_comments": 3,
            "url": f"https://i.redd.it/{post_id}.jpg",
            "permalink": f"/r/BlueArchive/comments/{post_id}/title/",
            "link_flair_text": "News",
        },
    }


def _comment(comment_id: str, post_id: str, replies=None) -> dict:
    return {
        "kind": "t1",
        "data": {
            "id": comment_id,
            "name": f"t1_{comment_id}",
            "link_id": f"t3_{post_id}",
            "parent_id": f"t3_{post_id}",
            "subreddit": "BlueArchive",
            "author": "student",
            "body": f"Comment {comment_id}",
            "created_utc": 1_700_000_100,
            "score": 7,
            "replies": replies,
        },
    }


class FakeTransport:
    def __init__(self, responses: dict[str, object]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, list[str]], int]] = []

    def __call__(self, request, timeout: float, max_bytes: int) -> _JsonResponse:
        parsed = urlsplit(request.full_url)
        self.calls.append((parsed.path, parse_qs(parsed.query), max_bytes))
        return _JsonResponse(
            status=200,
            headers={"content-type": "application/json"},
            payload=self.responses[parsed.path],
        )


class RedditDirectLinkCaptureTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory(
            prefix=".tmp-reddit-link-",
            dir=ROOT / "tests",
        )
        self.temp = Path(self._temporary_directory.name)
        self.database = self.temp / "archive" / "reddit.sqlite"

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    def test_post_capture_preserves_exact_responses_and_more_placeholders(self) -> None:
        post_id = "abc123"
        comments_response = {
            "kind": "Listing",
            "data": {
                "children": [
                    _comment(
                        "c1",
                        post_id,
                        {
                            "kind": "Listing",
                            "data": {
                                "children": [
                                    {
                                        "kind": "more",
                                        "data": {
                                            "id": "more1",
                                            "parent_id": "t1_c1",
                                            "children": ["missing2", "missing1"],
                                            "count": 2,
                                        },
                                    }
                                ]
                            },
                        },
                    )
                ]
            },
        }
        transport = FakeTransport(
            {
                "/api/posts/ids": {"data": [_post(post_id)]},
                "/api/comments/tree": comments_response,
            }
        )
        target = parse_capture_target(
            f"https://www.reddit.com/r/BlueArchive/comments/{post_id}/title/"
        )
        client = ArcticShiftApiClient(
            transport=transport,
            now=lambda: FIXED_NOW,
            id_factory=lambda: "fixed",
        )

        bundle = client.capture(target, self.temp / "direct")

        self.assertEqual(bundle.post_count, 1)
        self.assertEqual(bundle.comment_count, 1)
        self.assertEqual(bundle.placeholder_count, 1)
        self.assertEqual(bundle.unresolved_comment_ids, 2)
        self.assertEqual(
            [call[0] for call in transport.calls],
            ["/api/posts/ids", "/api/comments/tree"],
        )
        self.assertEqual(
            transport.calls[0][1],
            {"ids": [post_id], "md2html": ["false"]},
        )
        source_dir = Path(bundle.source_directory)
        self.assertEqual(
            json.loads(
                (source_dir / "comments-tree-response.json").read_text(
                    encoding="utf-8"
                )
            ),
            comments_response,
        )
        manifest = json.loads(
            Path(bundle.manifest_path).read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["source_adapter"], "arctic-shift-api")
        self.assertEqual(manifest["coverage"]["comment_placeholders"], 1)
        self.assertFalse(manifest["coverage"]["moderators"]["available"])

        summary = import_local_source(
            self.database,
            Path(bundle.source_files["records"]),
            target,
            CaptureOptions(
                posts_limit=1,
                save_images="both",
                save_videos="full",
                save_avatars=True,
            ),
        )
        self.assertEqual(summary.records_imported, 3)
        self.assertEqual(summary.posts_imported, 1)
        self.assertEqual(summary.comments_imported, 1)
        tree = build_comment_tree(self.database, post_id)
        self.assertEqual(
            tree["coverage"]["placeholder_coverage"]["collapsed_more_nodes"],
            1,
        )
        self.assertEqual(
            tree["coverage"]["placeholder_coverage"]["unresolved_comment_ids"],
            2,
        )
        self.assertEqual(tree["placeholders"][0]["kind"], "captured-more")
        self.assertEqual(
            tree["placeholders"][0]["child_ids"],
            ["missing1", "missing2"],
        )

    def test_subreddit_capture_uses_only_community_endpoints(self) -> None:
        subreddit = "BlueArchive"
        about = {
            "display_name": subreddit,
            "display_name_prefixed": f"r/{subreddit}",
            "title": "Blue Archive",
            "public_description": "Community",
            "description": "Long description",
            "created_utc": 1_500_000_000,
            "subscribers": 100,
            "icon_img": "https://styles.redditmedia.com/icon.png",
        }
        rule = {
            "short_name": "Be kind",
            "description": "No harassment",
            "kind": "all",
            "priority": 0,
        }
        wiki = {
            "path": f"/r/{subreddit}/wiki/index",
            "content": "Welcome",
        }
        transport = FakeTransport(
            {
                "/api/subreddits/search": {"data": [about]},
                "/api/subreddits/rules": {
                    "data": [{"subreddit": subreddit, "rules": [rule]}]
                },
                "/api/subreddits/wikis/list": {
                    "data": [{"path": wiki["path"]}]
                },
                "/api/subreddits/wikis": {"data": [wiki]},
            }
        )
        target = parse_capture_target(f"https://reddit.com/r/{subreddit}/")
        client = ArcticShiftApiClient(
            transport=transport,
            now=lambda: FIXED_NOW,
            id_factory=lambda: "fixed",
        )

        bundle = client.capture(target, self.temp / "direct")

        self.assertEqual(
            [call[0] for call in transport.calls],
            [
                "/api/subreddits/search",
                "/api/subreddits/rules",
                "/api/subreddits/wikis/list",
                "/api/subreddits/wikis",
            ],
        )
        self.assertNotIn("/api/posts/search", [call[0] for call in transport.calls])
        self.assertEqual(bundle.wiki_page_count, 1)
        self.assertFalse(bundle.moderators_available)
        for source_type in ("about", "rules", "wiki"):
            summary = import_community_source(
                self.database,
                Path(bundle.source_files[source_type]),
                subreddit,
                CommunityImportOptions(source_type=source_type),
            )
            self.assertEqual(summary.status, "complete")
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM subreddit_observations"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM subreddit_rule_observations"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM subreddit_wiki_observations"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM posts").fetchone()[0],
                0,
            )

    def test_user_capture_preserves_bounded_post_and_comment_searches(self) -> None:
        post = _post("owned1")
        post["data"]["author"] = "ProfileOwner"
        comment = _comment("owned-comment", "someone-elses-post")
        comment["data"]["author"] = "ProfileOwner"
        transport = FakeTransport(
            {
                "/api/posts/search": {"data": [post]},
                "/api/comments/search": {"data": [comment]},
            }
        )
        target = parse_capture_target(
            "https://www.reddit.com/user/ProfileOwner/"
        )
        client = ArcticShiftApiClient(
            transport=transport,
            now=lambda: FIXED_NOW,
            id_factory=lambda: "profile-fixed",
        )

        bundle = client.capture(target, self.temp / "direct")

        self.assertEqual(bundle.target_kind, "user")
        self.assertEqual(bundle.post_count, 1)
        self.assertEqual(bundle.comment_count, 1)
        self.assertEqual(
            [call[0] for call in transport.calls],
            ["/api/posts/search", "/api/comments/search"],
        )
        for _, query, _ in transport.calls:
            self.assertEqual(query["author"], ["ProfileOwner"])
            self.assertEqual(query["limit"], ["100"])
        records = [
            json.loads(line)
            for line in Path(bundle.source_files["records"]).read_text(
                encoding="utf-8"
            ).splitlines()
        ]
        self.assertEqual([record["kind"] for record in records], ["t3", "t1"])
        coverage = json.loads(
            Path(bundle.source_files["coverage"]).read_text(encoding="utf-8")
        )
        self.assertTrue(coverage["bounded"])
        self.assertEqual(coverage["limit_per_record_type"], 100)

    def test_cli_routes_direct_capture_without_real_network(self) -> None:
        source_dir = self.temp / "direct" / "capture"
        source_dir.mkdir(parents=True)
        records = source_dir / "records.jsonl"
        records.write_text(
            json.dumps(_post()) + "\n",
            encoding="utf-8",
        )
        bundle = DirectCaptureBundle(
            capture_id="capture",
            target_kind="post",
            target_url="https://www.reddit.com/comments/abc123/",
            retrieved_at=FIXED_NOW.isoformat(),
            source_directory=str(source_dir),
            manifest_path=str(source_dir / "manifest.json"),
            source_files={
                "records": str(records),
                "coverage": str(source_dir / "coverage.json"),
            },
            request_count=2,
            post_count=1,
            comment_count=0,
            placeholder_count=0,
            unresolved_comment_ids=0,
            wiki_page_count=0,
            wiki_pages_truncated=False,
            moderators_available=False,
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch(
                "reddit_capture.ArcticShiftApiClient.capture",
                return_value=bundle,
            ) as capture,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            result = reddit_capture.main(
                [
                    "--url",
                    "https://reddit.com/comments/abc123/title/",
                    "--arctic-shift-api",
                    "--database",
                    str(self.database),
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(result, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(payload["mode"], "arctic-shift-direct-capture")
        self.assertEqual(payload["imports"][0]["posts_imported"], 1)
        capture.assert_called_once()


if __name__ == "__main__":
    unittest.main()
