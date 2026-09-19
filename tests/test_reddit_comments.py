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

from modules.reddit.archive import open_archive  # noqa: E402
from modules.reddit.comment_trees import (  # noqa: E402
    CommentTreeExportError,
    CommentTreeLimitError,
    CommentTreeOptions,
    build_comment_tree,
    export_comment_tree,
    normalize_post_id,
    summarize_comment_tree,
)
import reddit_comments  # noqa: E402


class RedditCommentTreeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory(
            prefix=".tmp-reddit-comments-",
            dir=ROOT / "tests",
        )
        self.temp = Path(self._temporary_directory.name)
        self.database = self.temp / "reddit.sqlite"
        with open_archive(self.database):
            pass

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    def _post(self, post_id: str, *, num_comments: int | None = None) -> None:
        with open_archive(self.database) as connection:
            connection.execute(
                """
                INSERT INTO posts(
                    id, fullname, subreddit, title, num_comments,
                    first_observed_at, latest_observed_at
                ) VALUES(?, ?, 'AIcrack', ?, ?, '2026-01-01', '2026-01-02')
                """,
                (post_id, f"t3_{post_id}", f"Post {post_id}", num_comments),
            )
            connection.commit()

    def _comment(
        self,
        comment_id: str,
        post_id: str,
        parent_id: str | None,
        *,
        body: str | None = None,
        depth: int | None = None,
        created_utc: float | None = None,
        fullname: str | None = None,
    ) -> None:
        with open_archive(self.database) as connection:
            connection.execute(
                """
                INSERT INTO comments(
                    id, fullname, post_id, parent_id, subreddit, author, body,
                    created_utc, depth, first_observed_at, latest_observed_at
                ) VALUES(?, ?, ?, ?, 'AIcrack', 'archivist', ?, ?, ?,
                         '2026-01-01', '2026-01-02')
                """,
                (
                    comment_id,
                    fullname or f"t1_{comment_id}",
                    post_id,
                    parent_id,
                    body if body is not None else f"Comment {comment_id}",
                    created_utc,
                    depth,
                ),
            )
            connection.commit()

    def _post_observation(
        self,
        post_id: str,
        num_comments: int,
        observed_at: str,
        marker: str,
    ) -> None:
        with open_archive(self.database) as connection:
            connection.execute(
                """
                INSERT INTO capture_jobs(
                    id, target_kind, target_url, target_json, source_path,
                    source_kind, source_size, source_mtime_ns, comments_policy,
                    policy_json, status, created_at, updated_at
                ) VALUES(?, 'post', ?, '{}', ?, 'jsonl', 1, 1, 'all', '{}',
                         'complete', ?, ?)
                """,
                (
                    f"job-{marker}",
                    f"https://www.reddit.com/comments/{post_id}/",
                    f"source-{marker}.jsonl",
                    observed_at,
                    observed_at,
                ),
            )
            connection.execute(
                """
                INSERT INTO capture_chunks(
                    id, job_id, first_source_line, last_source_line,
                    record_count, raw_path, content_sha256, created_at
                ) VALUES(?, ?, 1, 1, 1, ?, ?, ?)
                """,
                (
                    f"chunk-{marker}",
                    f"job-{marker}",
                    f"raw-{marker}.jsonl.gz",
                    marker * 64,
                    observed_at,
                ),
            )
            cursor = connection.execute(
                """
                INSERT INTO source_records(
                    job_id, source_line, raw_chunk_id, raw_index,
                    record_sha256, record_kind, reddit_id, normalized,
                    imported_at
                ) VALUES(?, 1, ?, 0, ?, 'post', ?, 1, ?)
                """,
                (
                    f"job-{marker}",
                    f"chunk-{marker}",
                    marker * 64,
                    post_id,
                    observed_at,
                ),
            )
            connection.execute(
                """
                INSERT INTO post_observations(
                    post_id, source_record_id, observed_at, num_comments,
                    vote_fields_json
                ) VALUES(?, ?, ?, ?, '{}')
                """,
                (post_id, int(cursor.lastrowid), observed_at, num_comments),
            )
            connection.commit()

    @staticmethod
    def _flatten(payload: dict) -> list[dict]:
        found: list[dict] = []
        pending = list(
            reversed(payload["root_comments"] + payload["detached_comments"])
        )
        while pending:
            node = pending.pop()
            found.append(node)
            pending.extend(reversed(node["children"]))
        return found

    def test_normal_tree_is_deterministic_and_compares_declared_count(self) -> None:
        self._post("abc", num_comments=3)
        self._comment("later", "abc", "t3_abc", depth=0, created_utc=20)
        self._comment("first", "abc", "t3_abc", depth=0, created_utc=10)
        self._comment("reply", "abc", "t1_first", depth=1, created_utc=30)

        before = self.database.read_bytes()
        first = build_comment_tree(self.database, "t3_ABC")
        second = build_comment_tree(self.database, "abc")

        self.assertEqual(first, second)
        self.assertEqual(before, self.database.read_bytes())
        self.assertEqual([node["id"] for node in first["root_comments"]], ["first", "later"])
        self.assertEqual(first["root_comments"][0]["children"][0]["id"], "reply")
        self.assertEqual(first["coverage"]["observed_comments"], 3)
        self.assertEqual(first["coverage"]["declared_num_comments"], 3)
        self.assertTrue(first["coverage"]["count_matches_declared"])
        self.assertEqual(first["coverage"]["integrity"]["total_issues"], 0)

    def test_malformed_graph_is_reported_and_projected_without_data_loss(self) -> None:
        self._post("abc", num_comments=20)
        self._comment("root", "abc", "t3_abc", depth=0)
        self._comment("orphan", "abc", "t1_missing", depth=2)
        self._comment("cross", "abc", "t3_other", depth=0)
        self._comment("invalid", "abc", "t2_user", depth=-1)
        self._comment("blank", "abc", None, depth=None)
        self._comment("self", "abc", "t1_self", depth=0)
        self._comment("cyclea", "abc", "t1_cycleb", depth=7)
        self._comment("cycleb", "abc", "t1_cyclea", depth=8)

        payload = build_comment_tree(self.database, "abc")
        counts = payload["coverage"]["integrity"]["counts"]
        flattened = self._flatten(payload)

        self.assertEqual(len(flattened), 8)
        self.assertEqual(len({node["id"] for node in flattened}), 8)
        self.assertEqual(counts["missing_parent_references"], 1)
        self.assertEqual(counts["cross_post_parent_references"], 1)
        self.assertEqual(counts["invalid_parent_references"], 1)
        self.assertEqual(counts["missing_parent_values"], 1)
        self.assertEqual(counts["self_parent_references"], 1)
        self.assertEqual(counts["cycles"], 2)
        self.assertEqual(counts["cycle_comments"], 3)
        self.assertEqual(counts["negative_depths"], 1)
        self.assertEqual(payload["placeholders"][0]["id"], "t1_missing")
        cycle_breaks = {
            node["id"]
            for node in flattened
            if node["integrity"]["cycle_break"]
        }
        self.assertEqual(cycle_breaks, {"cyclea", "self"})

    def test_unknown_post_removed_bodies_and_duplicate_fullnames_are_explicit(self) -> None:
        self._comment(
            "deleted",
            "ghost",
            "t3_ghost",
            body="[deleted]",
            depth=0,
            fullname="t1_duplicate",
        )
        self._comment(
            "removed",
            "ghost",
            "t3_ghost",
            body="[removed]",
            depth=0,
            fullname="t1_duplicate",
        )

        payload = build_comment_tree(self.database, "ghost")
        coverage = payload["coverage"]
        states = coverage["body_states"]

        self.assertFalse(coverage["post_exists"])
        self.assertEqual(coverage["integrity"]["counts"]["unknown_post"], 1)
        self.assertEqual(coverage["integrity"]["counts"]["duplicate_fullnames"], 1)
        self.assertEqual(states["deleted"], 1)
        self.assertEqual(states["removed"], 1)
        self.assertIsNone(coverage["count_matches_declared"])
        bodies = {node["id"]: node["body"] for node in self._flatten(payload)}
        self.assertEqual(bodies, {"deleted": "[deleted]", "removed": "[removed]"})

    def test_comment_limit_fails_before_loading_a_larger_thread(self) -> None:
        self._post("abc", num_comments=2)
        self._comment("one", "abc", "t3_abc", depth=0)
        self._comment("two", "abc", "t3_abc", depth=0)

        with self.assertRaisesRegex(CommentTreeLimitError, "has 2 comments"):
            build_comment_tree(
                self.database,
                "abc",
                CommentTreeOptions(max_comments=1),
            )

    def test_latest_supplied_comment_count_comes_from_observations(self) -> None:
        self._post("abc", num_comments=99)
        self._post_observation("abc", 7, "2026-01-03T00:00:00Z", "a")
        self._post_observation("abc", 5, "2026-01-04T00:00:00Z", "b")
        self._comment("one", "abc", "t3_abc", depth=0)

        payload = build_comment_tree(self.database, "abc")

        self.assertEqual(payload["coverage"]["declared_num_comments"], 5)
        self.assertEqual(payload["coverage"]["declared_unobserved_count"], 4)
        self.assertEqual(
            payload["latest_declared_comment_observation"]["source"],
            "post_observations",
        )

    def test_create_only_export_verifies_repeat_and_refuses_mismatch(self) -> None:
        self._post("abc", num_comments=1)
        self._comment("one", "abc", "t3_abc", depth=0)
        output = self.temp / "exports" / "abc.json"

        first = export_comment_tree(self.database, "abc", output)
        original = output.read_bytes()
        second = export_comment_tree(self.database, "abc", output)

        self.assertEqual(first.output_bytes, len(original))
        self.assertEqual(first, second)
        self.assertEqual(json.loads(original)["post_id"], "abc")
        output.write_text('{"different":true}\n', encoding="utf-8")
        with self.assertRaisesRegex(CommentTreeExportError, "does not match"):
            export_comment_tree(self.database, "abc", output)
        self.assertEqual(output.read_text(encoding="utf-8"), '{"different":true}\n')

    def test_output_byte_cap_preserves_no_partial_destination(self) -> None:
        self._post("abc", num_comments=1)
        self._comment("one", "abc", "t3_abc", body="x" * 500, depth=0)
        output = self.temp / "too-small.json"

        with self.assertRaisesRegex(CommentTreeLimitError, "max-output-bytes"):
            export_comment_tree(
                self.database,
                "abc",
                output,
                max_output_bytes=100,
            )
        self.assertFalse(output.exists())
        self.assertEqual(list(self.temp.glob(".*.tmp")), [])

    def test_deep_thread_builds_and_exports_without_recursion(self) -> None:
        depth = 1_500
        self._post("deep", num_comments=depth)
        with open_archive(self.database) as connection:
            connection.executemany(
                """
                INSERT INTO comments(
                    id, fullname, post_id, parent_id, body, created_utc, depth,
                    first_observed_at, latest_observed_at
                ) VALUES(?, ?, 'deep', ?, ?, ?, ?, '2026-01-01', '2026-01-02')
                """,
                [
                    (
                        f"d{index:04d}",
                        f"t1_d{index:04d}",
                        "t3_deep" if index == 0 else f"t1_d{index - 1:04d}",
                        f"Depth {index}",
                        float(index),
                        index,
                    )
                    for index in range(depth)
                ],
            )
            connection.commit()

        output = self.temp / "deep.json"
        result = export_comment_tree(
            self.database,
            "deep",
            output,
            options=CommentTreeOptions(max_comments=2_000),
            max_output_bytes=20 * 1024 * 1024,
        )

        self.assertEqual(result.observed_comments, depth)
        self.assertEqual(result.integrity_issues, 0)
        self.assertIn(b'"id":"d1499"', output.read_bytes())

    def test_summary_and_cli_inspect_and_export_are_bounded(self) -> None:
        self._post("abc", num_comments=2)
        self._comment("one", "abc", "t3_abc", depth=0)
        summary = summarize_comment_tree(build_comment_tree(self.database, "abc"))
        self.assertEqual(summary["declared_unobserved_count"], 1)

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = reddit_comments.main(
                [
                    "inspect",
                    "--database",
                    str(self.database),
                    "--post-id",
                    "abc",
                ]
            )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["observed_comments"], 1)

        output = self.temp / "cli.json"
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = reddit_comments.main(
                [
                    "export",
                    "--database",
                    str(self.database),
                    "--post-id",
                    "abc",
                    "--output",
                    str(output),
                    "--max-output-bytes",
                    "1MiB",
                ]
            )
        self.assertEqual(code, 0)
        self.assertTrue(output.is_file())
        self.assertEqual(json.loads(stdout.getvalue())["post_id"], "abc")

        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = reddit_comments.main(
                [
                    "inspect",
                    "--database",
                    str(self.temp / "missing.sqlite"),
                    "--post-id",
                    "abc",
                ]
            )
        self.assertEqual(code, 2)
        self.assertIn("does not exist", stderr.getvalue())
        self.assertFalse((self.temp / "missing.sqlite").exists())

    def test_post_id_validation(self) -> None:
        self.assertEqual(normalize_post_id(" T3_AbC "), "abc")
        for value in ("", "r/test", "two words"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_post_id(value)


if __name__ == "__main__":
    unittest.main()
