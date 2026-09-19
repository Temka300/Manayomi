from __future__ import annotations

from contextlib import closing, redirect_stderr, redirect_stdout
import gzip
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

import zstandard


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from modules.reddit import community  # noqa: E402
from modules.reddit.community import (  # noqa: E402
    CommunityError,
    CommunityImportOptions,
    CommunityResumeRequiredError,
    import_community_source,
)
import reddit_community  # noqa: E402


def _about(
    subreddit: str,
    retrieved_on: float,
    *,
    marker: str = "one",
) -> dict:
    return {
        "_meta": {
            "earliest_comment_at": 1_600_000_000,
            "earliest_post_at": 1_590_000_000,
            "num_comments": 123,
            "num_posts": 45,
        },
        "display_name": subreddit,
        "display_name_prefixed": f"r/{subreddit}",
        "id": f"id-{marker}",
        "name": f"t5_{marker}",
        "title": f"{subreddit} title {marker}",
        "public_description": f"Public {marker}",
        "description": f"Long {marker}",
        "created_utc": 1_500_000_000,
        "subscribers": 100,
        "over18": False,
        "subreddit_type": "public",
        "lang": "en",
        "submission_type": "any",
        "wiki_enabled": True,
        "icon_img": (
            f"https://styles.redditmedia.com/{marker}/icon.png"
            "?width=256&amp;format=png"
        ),
        "community_icon": f"https://www.redditstatic.com/{marker}.png",
        "header_img": f"https://styles.redditmedia.com/{marker}/header.png",
        "banner_img": f"https://styles.redditmedia.com/{marker}/banner.png",
        "banner_background_image": "",
        "mobile_banner_image": None,
        "retrieved_on": retrieved_on,
        "url": f"/r/{subreddit}/",
    }


def _rules(subreddit: str, retrieved_on: float, names: list[str]) -> dict:
    return {
        "subreddit": subreddit,
        "retrieved_on": retrieved_on,
        "rules": [
            {
                "created_utc": 1_700_000_000 + index,
                "description": f"Description {name}",
                "kind": "all",
                "priority": index,
                "short_name": name,
                "violation_reason": f"Reason {name}",
            }
            for index, name in enumerate(names)
        ],
    }


def _wiki(
    subreddit: str,
    path: str,
    content: str,
    retrieved_on: float,
) -> dict:
    return {
        "content": content,
        "path": f"/r/{subreddit}/wiki/{path}",
        "retrieved_on": retrieved_on,
        "revision_author": "wiki_mod",
        "revision_author_id": "t2_wiki",
        "revision_date": "2025-01-02T03:04:05+00:00",
        "revision_reason": None,
    }


class RedditCommunityTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory(
            prefix=".tmp-reddit-community-",
            dir=ROOT / "tests",
        )
        self.temp = Path(self._temporary_directory.name)
        self.database = self.temp / "archive" / "reddit.sqlite"

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    def _write_jsonl(self, name: str, values: list[object | str]) -> Path:
        path = self.temp / name
        lines = [
            value if isinstance(value, str) else json.dumps(value)
            for value in values
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def _write_zst(self, name: str, values: list[object | str]) -> Path:
        plain = "\n".join(
            value if isinstance(value, str) else json.dumps(value)
            for value in values
        ) + "\n"
        path = self.temp / name
        path.write_bytes(
            zstandard.ZstdCompressor(level=1).compress(plain.encode("utf-8"))
        )
        return path

    def test_global_about_import_prefilters_raw_and_queues_assets(self) -> None:
        source = self._write_jsonl(
            "subreddits.jsonl",
            [
                _about("AIcrack", 1_737_000_000),
                _about("OtherSub", 1_737_000_001),
                "{bad json",
                "",
            ],
        )
        coverage_path = self.temp / "reports" / "about.json"
        summary = import_community_source(
            self.database,
            source,
            "AIcrack",
            CommunityImportOptions(
                source_type="about",
                source_scope="global",
                chunk_size=1,
            ),
            coverage_path=coverage_path,
        )

        self.assertEqual(summary.status, "complete")
        self.assertEqual(summary.subreddit, "aicrack")
        self.assertEqual(summary.records_scanned, 3)
        self.assertEqual(summary.records_matched, 1)
        self.assertEqual(summary.records_preserved, 1)
        self.assertEqual(summary.records_imported, 1)
        self.assertEqual(summary.invalid_records, 1)
        self.assertEqual(summary.wrong_subreddit_records, 1)
        self.assertEqual(summary.blank_lines, 1)

        raw_files = list(Path(summary.raw_directory).glob("*.jsonl.gz"))
        self.assertEqual(len(raw_files), 1)
        with gzip.open(raw_files[0], "rt", encoding="utf-8") as handle:
            raw_values = [json.loads(line) for line in handle]
        self.assertEqual([value["display_name"] for value in raw_values], ["AIcrack"])

        with closing(sqlite3.connect(self.database)) as connection:
            connection.row_factory = sqlite3.Row
            observation = connection.execute(
                """
                SELECT subreddit, display_name, title, subscribers,
                       metadata_json
                FROM subreddit_observations
                """
            ).fetchone()
            self.assertEqual(
                tuple(observation)[:4],
                ("aicrack", "AIcrack", "AIcrack title one", 100),
            )
            self.assertEqual(
                json.loads(observation["metadata_json"])["_meta"]["num_posts"],
                45,
            )
            assets = connection.execute(
                """
                SELECT role, url, status
                FROM assets
                WHERE owner_type='subreddit' AND owner_id='aicrack'
                ORDER BY id
                """
            ).fetchall()
            self.assertEqual(len(assets), 4)
            self.assertEqual(
                {row["role"] for row in assets},
                {"subreddit-icon", "subreddit-banner"},
            )
            self.assertEqual({row["status"] for row in assets}, {"queued"})

        coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
        self.assertEqual(coverage["coverage"]["about_observations"], 1)
        self.assertEqual(coverage["coverage"]["missing_requested_domains"], [])
        self.assertEqual(coverage["source"]["scope"], "global")

    def test_rule_snapshots_preserve_empty_and_ordered_rule_sets(self) -> None:
        source = self.temp / "rules.json"
        source.write_text(
            json.dumps(
                [
                    _rules("AIcrack", 1_737_000_000, ["First", "Second"]),
                    _rules("AIcrack", 1_737_000_100, []),
                ]
            ),
            encoding="utf-8",
        )
        summary = import_community_source(
            self.database,
            source,
            "r/AIcrack",
            CommunityImportOptions(source_type="rules", chunk_size=1),
        )

        self.assertEqual(summary.records_imported, 2)
        with closing(sqlite3.connect(self.database)) as connection:
            snapshots = connection.execute(
                """
                SELECT id, rule_count, retrieved_utc
                FROM subreddit_rule_snapshots
                ORDER BY retrieved_utc
                """
            ).fetchall()
            self.assertEqual(
                [(row[1], row[2]) for row in snapshots],
                [(2, 1_737_000_000), (0, 1_737_000_100)],
            )
            rules = connection.execute(
                """
                SELECT position, short_name, priority
                FROM subreddit_rule_observations
                ORDER BY position
                """
            ).fetchall()
            self.assertEqual(rules, [(0, "First", 0), (1, "Second", 1)])
        coverage = json.loads(
            Path(summary.coverage_path).read_text(encoding="utf-8")
        )
        self.assertEqual(coverage["coverage"]["rule_snapshots"], 2)
        self.assertEqual(coverage["coverage"]["rules"], 2)

    def test_wiki_nested_paths_keep_distinct_revisions(self) -> None:
        source = self._write_jsonl(
            "wiki.ndjson",
            [
                _wiki("AIcrack", "guides/start", "Version one", 1_737_000_000),
                _wiki("AIcrack", "guides/start", "Version two", 1_737_000_100),
                _wiki("OtherSub", "index", "Wrong sub", 1_737_000_200),
            ],
        )
        summary = import_community_source(
            self.database,
            source,
            "AIcrack",
            CommunityImportOptions(
                source_type="wiki",
                source_scope="global",
            ),
        )

        self.assertEqual(summary.records_imported, 2)
        self.assertEqual(summary.wrong_subreddit_records, 1)
        with closing(sqlite3.connect(self.database)) as connection:
            rows = connection.execute(
                """
                SELECT path, content, content_sha256, revision_author_id
                FROM subreddit_wiki_observations
                ORDER BY retrieved_utc
                """
            ).fetchall()
            self.assertEqual(
                [(row[0], row[1]) for row in rows],
                [
                    ("/r/AIcrack/wiki/guides/start", "Version one"),
                    ("/r/AIcrack/wiki/guides/start", "Version two"),
                ],
            )
            self.assertNotEqual(rows[0][2], rows[1][2])
            self.assertEqual({row[3] for row in rows}, {"t2_wiki"})
        coverage = json.loads(
            Path(summary.coverage_path).read_text(encoding="utf-8")
        )
        self.assertEqual(coverage["coverage"]["wiki_revisions"], 2)
        self.assertEqual(coverage["coverage"]["distinct_wiki_pages"], 1)

    def test_module_owned_moderator_bundle_is_versioned_local_input(self) -> None:
        source = self.temp / "moderators.json"
        source.write_text(
            json.dumps(
                {
                    "format": "keivotos-reddit-moderators-v1",
                    "subreddit": "AIcrack",
                    "retrieved_on": "2025-01-02T03:04:05Z",
                    "source_label": "moderator-provided export",
                    "moderators": [
                        {
                            "name": "mod_one",
                            "id": "t2_one",
                            "permissions": ["all"],
                            "added_utc": 1_700_000_000,
                        },
                        {
                            "name": "mod_two",
                            "permissions": ["posts", "wiki"],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        summary = import_community_source(
            self.database,
            source,
            "AIcrack",
            CommunityImportOptions(source_type="moderators"),
        )

        self.assertEqual(summary.records_imported, 1)
        with closing(sqlite3.connect(self.database)) as connection:
            snapshot = connection.execute(
                """
                SELECT moderator_count, source_label, retrieved_utc
                FROM subreddit_moderator_snapshots
                """
            ).fetchone()
            self.assertEqual(snapshot[0:2], (2, "moderator-provided export"))
            self.assertEqual(
                datetime_from_timestamp(snapshot[2]),
                "2025-01-02T03:04:05+00:00",
            )
            moderators = connection.execute(
                """
                SELECT username, account_id, permissions_json
                FROM subreddit_moderator_observations
                ORDER BY position
                """
            ).fetchall()
            self.assertEqual(moderators[0][0:2], ("mod_one", "t2_one"))
            self.assertEqual(json.loads(moderators[1][2]), ["posts", "wiki"])

    def test_zstandard_source_streams_and_verifies_published_hash(self) -> None:
        source = self._write_zst(
            "wiki.zst",
            [_wiki("AIcrack", "index", "Preserved", 1_737_000_000)],
        )
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        summary = import_community_source(
            self.database,
            source,
            "AIcrack",
            CommunityImportOptions(
                source_type="wiki",
                expected_sha256=digest.upper(),
            ),
        )

        self.assertEqual(summary.records_imported, 1)
        coverage = json.loads(
            Path(summary.coverage_path).read_text(encoding="utf-8")
        )
        self.assertEqual(coverage["source"]["sha256"], digest)
        self.assertEqual(coverage["source"]["kind"], "zstandard-jsonl")

    def test_bad_hash_and_invalid_zstandard_fail_before_database_creation(
        self,
    ) -> None:
        valid = self._write_zst(
            "valid.zst",
            [_wiki("AIcrack", "index", "Preserved", 1_737_000_000)],
        )
        with self.assertRaises(community.arctic_shift.ArcticShiftError):
            import_community_source(
                self.database,
                valid,
                "AIcrack",
                CommunityImportOptions(
                    source_type="wiki",
                    expected_sha256="0" * 64,
                ),
            )
        self.assertFalse(self.database.exists())

        invalid = self.temp / "invalid.zst"
        invalid.write_bytes(b"not zstandard")
        with self.assertRaises(CommunityError):
            import_community_source(
                self.database,
                invalid,
                "AIcrack",
                CommunityImportOptions(source_type="wiki"),
            )
        self.assertFalse(self.database.exists())

    def test_resume_continues_after_last_committed_source_line(self) -> None:
        source = self._write_jsonl(
            "rules.jsonl",
            [
                _rules("AIcrack", 1_737_000_000 + index, [f"Rule {index}"])
                for index in range(3)
            ],
        )
        options = CommunityImportOptions(source_type="rules", chunk_size=1)
        original = community._process_chunk
        calls = 0

        def interrupt(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("simulated interruption")
            return original(*args, **kwargs)

        with (
            patch.object(community, "_process_chunk", side_effect=interrupt),
            self.assertRaisesRegex(RuntimeError, "simulated interruption"),
        ):
            import_community_source(
                self.database,
                source,
                "AIcrack",
                options,
            )

        with closing(sqlite3.connect(self.database)) as connection:
            job = connection.execute(
                """
                SELECT status, last_source_line
                FROM community_import_jobs
                """
            ).fetchone()
            self.assertEqual(job, ("failed", 1))
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM subreddit_rule_snapshots"
                ).fetchone()[0],
                1,
            )

        with self.assertRaises(CommunityResumeRequiredError):
            import_community_source(
                self.database,
                source,
                "AIcrack",
                options,
            )
        summary = import_community_source(
            self.database,
            source,
            "AIcrack",
            options,
            resume=True,
        )
        self.assertEqual(summary.status, "complete")
        self.assertEqual(summary.records_scanned, 3)
        self.assertEqual(summary.records_imported, 3)
        self.assertEqual(summary.last_source_line, 3)
        self.assertEqual(summary.errors, 1)
        repeated = import_community_source(
            self.database,
            source,
            "AIcrack",
            options,
            resume=True,
        )
        self.assertEqual(repeated.records_imported, 3)
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM subreddit_rule_snapshots"
                ).fetchone()[0],
                3,
            )

    def test_scoped_wrong_and_malformed_records_are_raw_evidence(self) -> None:
        source = self._write_jsonl(
            "about.jsonl",
            [_about("OtherSub", 1_737_000_000), ["not", "an", "object"]],
        )
        summary = import_community_source(
            self.database,
            source,
            "AIcrack",
            CommunityImportOptions(source_type="about"),
        )

        self.assertEqual(summary.records_scanned, 2)
        self.assertEqual(summary.records_matched, 0)
        self.assertEqual(summary.records_preserved, 2)
        self.assertEqual(summary.records_imported, 0)
        self.assertEqual(summary.invalid_records, 1)
        self.assertEqual(summary.wrong_subreddit_records, 1)
        with closing(sqlite3.connect(self.database)) as connection:
            errors = [
                row[0]
                for row in connection.execute(
                    """
                    SELECT error FROM community_source_records
                    ORDER BY source_line
                    """
                )
            ]
            self.assertIn("belongs to r/othersub", errors[0])
            self.assertIn("no valid subreddit identity", errors[1])
        coverage = json.loads(
            Path(summary.coverage_path).read_text(encoding="utf-8")
        )
        self.assertEqual(
            coverage["coverage"]["missing_requested_domains"],
            ["about"],
        )

    def test_declared_schema_errors_are_preserved_without_partial_rows(self) -> None:
        source = self._write_jsonl(
            "rules.jsonl",
            [
                {
                    "subreddit": "AIcrack",
                    "retrieved_on": 1_737_000_000,
                    "rules": "not an array",
                }
            ],
        )
        summary = import_community_source(
            self.database,
            source,
            "AIcrack",
            CommunityImportOptions(source_type="rules"),
        )

        self.assertEqual(summary.records_preserved, 1)
        self.assertEqual(summary.records_imported, 0)
        self.assertEqual(summary.invalid_records, 1)
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM subreddit_rule_snapshots"
                ).fetchone()[0],
                0,
            )
            error = connection.execute(
                "SELECT error FROM community_source_records"
            ).fetchone()[0]
            self.assertIn("Invalid declared schema", error)

    def test_existing_coverage_artifact_is_create_only(self) -> None:
        source = self._write_jsonl(
            "wiki.jsonl",
            [_wiki("AIcrack", "index", "Preserved", 1_737_000_000)],
        )
        options = CommunityImportOptions(source_type="wiki")
        summary = import_community_source(
            self.database,
            source,
            "AIcrack",
            options,
        )
        coverage_path = Path(summary.coverage_path)
        original = coverage_path.read_bytes()

        repeated = import_community_source(
            self.database,
            source,
            "AIcrack",
            options,
            resume=True,
        )

        self.assertEqual(repeated.status, "complete")
        self.assertEqual(coverage_path.read_bytes(), original)
        coverage_path.write_text('{"different": true}\n', encoding="utf-8")
        with self.assertRaises(CommunityError):
            import_community_source(
                self.database,
                source,
                "AIcrack",
                options,
                resume=True,
            )

    def test_cli_prints_summary_and_never_creates_media_directory(self) -> None:
        source = self._write_jsonl(
            "about.jsonl",
            [_about("AIcrack", 1_737_000_000)],
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = reddit_community.main(
                [
                    "--subreddit",
                    "AIcrack",
                    "--source-type",
                    "about",
                    "--source-file",
                    str(source),
                    "--database",
                    str(self.database),
                    "--chunk-size",
                    "1",
                ]
            )

        self.assertEqual(code, 0, stderr.getvalue())
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["records_imported"], 1)
        self.assertEqual(payload["source_type"], "about")
        self.assertFalse((self.temp / "media").exists())


def datetime_from_timestamp(value: float) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


if __name__ == "__main__":
    unittest.main()
