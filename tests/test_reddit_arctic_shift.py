from __future__ import annotations

from contextlib import closing
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

import zstandard


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from modules.reddit.archive import (  # noqa: E402
    CaptureOptions,
    LocalSourceOptions,
    import_local_source,
)
from modules.reddit.arctic_shift import (  # noqa: E402
    ArcticShiftError,
    parse_utc_boundary,
)
from modules.reddit.reddit_api import (  # noqa: E402
    DiscoveryItem,
    DiscoveryResult,
    read_discovery_manifest,
    write_discovery_manifest,
)
from modules.reddit.url_targets import parse_capture_target  # noqa: E402


def _post(post_id: str, subreddit: str, created_utc: float) -> dict:
    return {
        "id": post_id,
        "name": f"t3_{post_id}",
        "subreddit": subreddit,
        "author": "archivist",
        "title": f"Post {post_id}",
        "selftext": "preserved body",
        "created_utc": created_utc,
        "score": 10,
        "num_comments": 1,
        "permalink": f"/r/{subreddit}/comments/{post_id}/example/",
        "url": f"https://www.reddit.com/r/{subreddit}/comments/{post_id}/",
    }


def _comment(
    comment_id: str,
    post_id: str,
    subreddit: str,
    created_utc: float,
) -> dict:
    return {
        "id": comment_id,
        "name": f"t1_{comment_id}",
        "link_id": f"t3_{post_id}",
        "parent_id": f"t3_{post_id}",
        "subreddit": subreddit,
        "author": "commenter",
        "body": "preserved comment",
        "created_utc": created_utc,
        "score": 3,
        "permalink": (
            f"/r/{subreddit}/comments/{post_id}/example/{comment_id}/"
        ),
    }


class ArcticShiftImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory(
            prefix=".tmp-reddit-arctic-",
            dir=ROOT / "tests",
        )
        self.temp = Path(self._temporary_directory.name)
        self.database = self.temp / "archive" / "reddit.sqlite"
        self.target = parse_capture_target("r/AIcrack")

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    def _write_zst(self, name: str, records: list[object | str]) -> Path:
        source = self.temp / name
        lines = []
        for record in records:
            lines.append(
                record
                if isinstance(record, str)
                else json.dumps(record, ensure_ascii=False)
            )
        plain = ("\n".join(lines) + "\n").encode("utf-8")
        source.write_bytes(zstandard.ZstdCompressor(level=1).compress(plain))
        return source

    def test_global_dump_is_filtered_before_raw_preservation(self) -> None:
        january = parse_utc_boundary("2025-01-10")
        march = parse_utc_boundary("2025-03-01")
        source = self._write_zst(
            "global.zst",
            [
                _post("p1", "AIcrack", january),
                _comment("c1", "p1", "AIcrack", january + 1),
                _post("other", "OtherSub", january),
                _post("late", "AIcrack", march),
                "{broken json",
            ],
        )
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        requested_coverage = self.temp / "reports" / "coverage.json"

        summary = import_local_source(
            self.database,
            source,
            self.target,
            CaptureOptions(posts_limit=None, chunk_size=1),
            source_options=LocalSourceOptions(
                source_scope="global",
                after_utc=parse_utc_boundary("2025-01-01"),
                before_utc=parse_utc_boundary("2025-02-01"),
                expected_sha256=digest.upper(),
            ),
            coverage_path=requested_coverage,
        )

        self.assertEqual(summary.records_seen, 2)
        self.assertEqual(summary.posts_imported, 1)
        self.assertEqual(summary.comments_imported, 1)
        raw_lines: list[str] = []
        for path in Path(summary.raw_directory).glob("*.jsonl.gz"):
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                raw_lines.extend(handle.readlines())
        self.assertEqual(len(raw_lines), 2)
        self.assertNotIn("OtherSub", "".join(raw_lines))
        self.assertNotIn("late", "".join(raw_lines))

        default_coverage = Path(summary.raw_directory) / "coverage.json"
        self.assertEqual(
            requested_coverage.read_bytes(),
            default_coverage.read_bytes(),
        )
        report = json.loads(default_coverage.read_text(encoding="utf-8"))
        counters = report["coverage"]
        self.assertEqual(counters["source_records_scanned"], 5)
        self.assertEqual(counters["records_in_date_range"], 3)
        self.assertEqual(counters["records_selected"], 2)
        self.assertEqual(counters["invalid_records"], 1)
        self.assertEqual(counters["source_sha256"], digest)
        manifest = json.loads(
            (Path(summary.raw_directory) / "manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifest["source"]["sha256"], digest)
        self.assertEqual(manifest["source_options"]["source_scope"], "global")

    def test_scoped_dump_preserves_nonmatching_raw_records(self) -> None:
        source = self._write_zst(
            "scoped.zst",
            [
                _post("p1", "AIcrack", 1_700_000_000),
                _post("other", "OtherSub", 1_700_000_001),
                "{broken json",
            ],
        )

        summary = import_local_source(
            self.database,
            source,
            self.target,
            CaptureOptions(posts_limit=None),
            source_options=LocalSourceOptions(source_scope="scoped"),
        )

        self.assertEqual(summary.records_seen, 3)
        self.assertEqual(summary.posts_imported, 1)
        self.assertEqual(summary.records_skipped, 1)
        self.assertEqual(summary.errors, 1)
        report = json.loads(
            (Path(summary.raw_directory) / "coverage.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(report["coverage"]["records_selected"], 3)
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM posts").fetchone()[0],
                1,
            )

    def test_discovery_manifest_selects_posts_and_their_comments(self) -> None:
        source = self._write_zst(
            "discovery-filtered.zst",
            [
                _post("p1", "AIcrack", 1_700_000_000),
                _comment("c1", "p1", "AIcrack", 1_700_000_001),
                _post("p2", "AIcrack", 1_700_000_002),
                _comment("c2", "p2", "AIcrack", 1_700_000_003),
            ],
        )
        discovery_path = self.temp / "discovery.json"
        write_discovery_manifest(
            discovery_path,
            DiscoveryResult(
                target=self.target.as_dict(),
                listing_path="/r/AIcrack/new",
                retrieved_at="2026-07-27T00:00:00+00:00",
                max_items=1,
                page_count=1,
                item_count=1,
                listing_exhausted=False,
                stopped_reason="item_limit",
                last_after="t3_p1",
                items=(
                    DiscoveryItem(
                        fullname="t3_p1",
                        kind="post",
                        reddit_id="p1",
                        canonical_url="https://www.reddit.com/comments/p1/",
                    ),
                ),
            ),
        )
        discovery = read_discovery_manifest(
            discovery_path,
            target=self.target,
        )

        summary = import_local_source(
            self.database,
            source,
            self.target,
            CaptureOptions(posts_limit=None),
            source_options=LocalSourceOptions(discovery=discovery),
        )

        self.assertEqual(summary.records_seen, 2)
        self.assertEqual(summary.posts_imported, 1)
        self.assertEqual(summary.comments_imported, 1)
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(
                connection.execute("SELECT id FROM posts").fetchall(),
                [("p1",)],
            )
            self.assertEqual(
                connection.execute("SELECT id FROM comments").fetchall(),
                [("c1",)],
            )

    def test_bad_hash_and_invalid_zst_fail_before_database_creation(self) -> None:
        valid_source = self._write_zst(
            "valid.zst", [_post("p1", "AIcrack", 1_700_000_000)]
        )
        with self.assertRaisesRegex(ArcticShiftError, "SHA-256 mismatch"):
            import_local_source(
                self.database,
                valid_source,
                self.target,
                CaptureOptions(),
                source_options=LocalSourceOptions(expected_sha256="0" * 64),
            )
        self.assertFalse(self.database.exists())

        invalid_source = self.temp / "invalid.zst"
        invalid_source.write_bytes(b"not zstandard")
        with self.assertRaisesRegex(ArcticShiftError, "Invalid or truncated"):
            import_local_source(
                self.database,
                invalid_source,
                self.target,
                CaptureOptions(),
                source_options=LocalSourceOptions(),
            )
        self.assertFalse(self.database.exists())


if __name__ == "__main__":
    unittest.main()
