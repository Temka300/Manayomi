"""Local Reddit archive and rebuildable SQLite search index.

The archive accepts user-supplied local sources. It preserves selected source
records in atomic gzip-compressed JSONL chunks, records their provenance in a
rebuildable SQLite index, normalizes posts/comments, and queues desired assets
without downloading them.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Generator, Iterable, Iterator
from urllib.parse import urlsplit
from uuid import uuid4

from modules.reddit.arctic_shift import (
    ArcticShiftCoverage,
    iter_zst_records,
    normalize_sha256,
    verify_sha256,
)
from modules.reddit.reddit_api import DiscoverySelection
from modules.reddit.links import link_urls
from modules.reddit.url_targets import CaptureTarget


ARCHIVE_SCHEMA_VERSION = 2
MEDIA_SCHEMA_VERSION = 1
COMMUNITY_SCHEMA_VERSION = 1
DEFAULT_CHUNK_SIZE = 500
IMAGE_SUFFIXES = {".avif", ".gif", ".jpeg", ".jpg", ".png", ".webp"}
REDDIT_MEDIA_HOSTS = {
    "i.redd.it",
    "v.redd.it",
    "preview.redd.it",
    "external-preview.redd.it",
}
URL_RE = re.compile(r"https?://[^\s<>()\"']+")


class ArchiveError(RuntimeError):
    """Base error for an offline archive operation."""


class UnsupportedSourceError(ArchiveError):
    """Raised when no current local reader supports the selected format."""


class ResumeRequiredError(ArchiveError):
    """Raised when an existing job would be reused without explicit consent."""


@dataclass(frozen=True)
class LocalSourceOptions:
    """Filtering and integrity policy for a local Arctic Shift source."""

    source_scope: str = "scoped"
    after_utc: float | None = None
    before_utc: float | None = None
    expected_sha256: str | None = None
    discovery: DiscoverySelection | None = None

    def __post_init__(self) -> None:
        if self.source_scope not in {"scoped", "global"}:
            raise ValueError("source_scope must be 'scoped' or 'global'")
        if (
            self.after_utc is not None
            and self.before_utc is not None
            and self.after_utc >= self.before_utc
        ):
            raise ValueError("--after must be earlier than --before")
        if self.expected_sha256 is not None:
            object.__setattr__(
                self, "expected_sha256", normalize_sha256(self.expected_sha256)
            )

    def manifest(self) -> dict[str, Any]:
        payload = {
            "source_scope": self.source_scope,
            "after_utc": self.after_utc,
            "before_utc": self.before_utc,
            "expected_sha256": self.expected_sha256,
        }
        if self.discovery is not None:
            payload["discovery"] = self.discovery.identity()
        return payload


@dataclass(frozen=True)
class CaptureOptions:
    """User-selected scope and future acquisition policies."""

    posts_limit: int | None = None
    comments: str = "all"
    save_images: str = "none"
    save_videos: str = "none"
    save_avatars: bool = False
    save_subreddit_assets: bool = False
    save_wiki: bool = False
    save_rules: bool = False
    save_mod_list: bool = False
    save_external_assets: bool = False
    external_domains: tuple[str, ...] = ()
    save_linked_files: bool = False
    media_directory: str | None = None
    chunk_size: int = DEFAULT_CHUNK_SIZE

    def __post_init__(self) -> None:
        if self.posts_limit is not None and self.posts_limit <= 0:
            raise ValueError("posts_limit must be positive or None")
        if self.comments not in {"none", "all"}:
            raise ValueError("comments must be 'none' or 'all'")
        if self.save_images not in {"none", "preview", "original", "both"}:
            raise ValueError("Invalid image preservation policy")
        if self.save_videos not in {"none", "manifest", "full"}:
            raise ValueError("Invalid video preservation policy")
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if self.save_external_assets and not self.external_domains:
            raise ValueError(
                "External asset capture requires at least one allowlisted domain"
            )

    def manifest(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ImportSummary:
    """Stable summary returned for a new, resumed, or already-complete job."""

    job_id: str
    status: str
    source_path: str
    database_path: str
    raw_directory: str
    records_seen: int
    records_imported: int
    posts_imported: int
    comments_imported: int
    records_skipped: int
    errors: int
    last_source_line: int


@dataclass(frozen=True)
class RawRecord:
    source_line: int
    raw_text: str
    payload: Any | None
    error: str | None = None


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS archive_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS capture_jobs (
    id TEXT PRIMARY KEY,
    target_kind TEXT NOT NULL,
    target_url TEXT NOT NULL,
    target_json TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_size INTEGER NOT NULL,
    source_mtime_ns INTEGER NOT NULL,
    posts_limit INTEGER,
    comments_policy TEXT NOT NULL,
    policy_json TEXT NOT NULL,
    status TEXT NOT NULL,
    last_source_line INTEGER NOT NULL DEFAULT 0,
    records_seen INTEGER NOT NULL DEFAULT 0,
    records_imported INTEGER NOT NULL DEFAULT 0,
    posts_imported INTEGER NOT NULL DEFAULT 0,
    comments_imported INTEGER NOT NULL DEFAULT 0,
    records_skipped INTEGER NOT NULL DEFAULT 0,
    errors INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS capture_chunks (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES capture_jobs(id),
    first_source_line INTEGER NOT NULL,
    last_source_line INTEGER NOT NULL,
    record_count INTEGER NOT NULL,
    raw_path TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(job_id, first_source_line, last_source_line)
);

CREATE TABLE IF NOT EXISTS source_records (
    id INTEGER PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES capture_jobs(id),
    source_line INTEGER NOT NULL,
    raw_chunk_id TEXT NOT NULL REFERENCES capture_chunks(id),
    raw_index INTEGER NOT NULL,
    record_sha256 TEXT NOT NULL,
    record_kind TEXT NOT NULL,
    reddit_id TEXT,
    normalized INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    imported_at TEXT NOT NULL,
    UNIQUE(job_id, source_line)
);

CREATE TABLE IF NOT EXISTS capture_job_posts (
    job_id TEXT NOT NULL REFERENCES capture_jobs(id),
    post_id TEXT NOT NULL,
    selected_at TEXT NOT NULL,
    PRIMARY KEY(job_id, post_id)
);

CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    fullname TEXT,
    subreddit TEXT,
    author TEXT,
    author_id TEXT,
    title TEXT,
    selftext TEXT,
    selftext_html TEXT,
    created_utc REAL,
    edited_utc REAL,
    permalink TEXT,
    url TEXT,
    domain TEXT,
    flair_text TEXT,
    score INTEGER,
    upvote_ratio REAL,
    num_comments INTEGER,
    is_self INTEGER,
    nsfw INTEGER,
    spoiler INTEGER,
    stickied INTEGER,
    locked INTEGER,
    archived INTEGER,
    distinguished TEXT,
    removed_by_category TEXT,
    thumbnail_url TEXT,
    first_observed_at TEXT NOT NULL,
    latest_observed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS post_observations (
    id INTEGER PRIMARY KEY,
    post_id TEXT NOT NULL REFERENCES posts(id),
    source_record_id INTEGER NOT NULL UNIQUE REFERENCES source_records(id),
    observed_at TEXT NOT NULL,
    score INTEGER,
    upvote_ratio REAL,
    num_comments INTEGER,
    edited_utc REAL,
    author TEXT,
    removed_by_category TEXT,
    my_vote INTEGER,
    reddit_saved INTEGER,
    vote_fields_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS comments (
    id TEXT PRIMARY KEY,
    fullname TEXT,
    post_id TEXT NOT NULL,
    parent_id TEXT,
    subreddit TEXT,
    author TEXT,
    body TEXT,
    body_html TEXT,
    created_utc REAL,
    edited_utc REAL,
    score INTEGER,
    depth INTEGER,
    is_submitter INTEGER,
    distinguished TEXT,
    stickied INTEGER,
    score_hidden INTEGER,
    controversiality INTEGER,
    permalink TEXT,
    first_observed_at TEXT NOT NULL,
    latest_observed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS comment_observations (
    id INTEGER PRIMARY KEY,
    comment_id TEXT NOT NULL REFERENCES comments(id),
    source_record_id INTEGER NOT NULL UNIQUE REFERENCES source_records(id),
    observed_at TEXT NOT NULL,
    score INTEGER,
    edited_utc REAL,
    author TEXT,
    my_vote INTEGER,
    vote_fields_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS comment_placeholders (
    id INTEGER PRIMARY KEY,
    post_id TEXT NOT NULL,
    source_record_id INTEGER NOT NULL UNIQUE REFERENCES source_records(id),
    placeholder_id TEXT,
    parent_id TEXT,
    child_ids_json TEXT NOT NULL,
    declared_count INTEGER,
    observed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY,
    owner_type TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    role TEXT NOT NULL,
    url TEXT NOT NULL,
    desired_policy TEXT NOT NULL,
    local_path TEXT,
    status TEXT NOT NULL DEFAULT 'queued',
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    UNIQUE(owner_type, owner_id, role, url)
);

CREATE TABLE IF NOT EXISTS media_objects (
    sha256 TEXT PRIMARY KEY,
    relative_path TEXT NOT NULL UNIQUE,
    byte_size INTEGER NOT NULL,
    content_type TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS asset_download_events (
    id INTEGER PRIMARY KEY,
    attempt_id TEXT NOT NULL,
    asset_id INTEGER NOT NULL REFERENCES assets(id),
    event_type TEXT NOT NULL,
    engine TEXT NOT NULL,
    source_url TEXT NOT NULL,
    final_url TEXT,
    object_sha256 TEXT REFERENCES media_objects(sha256),
    byte_size INTEGER,
    manifest_path TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(attempt_id, event_type)
);

CREATE TABLE IF NOT EXISTS community_import_jobs (
    id TEXT PRIMARY KEY,
    subreddit TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_scope TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_size INTEGER NOT NULL,
    source_mtime_ns INTEGER NOT NULL,
    source_sha256 TEXT,
    status TEXT NOT NULL,
    last_source_line INTEGER NOT NULL DEFAULT 0,
    records_scanned INTEGER NOT NULL DEFAULT 0,
    records_matched INTEGER NOT NULL DEFAULT 0,
    records_imported INTEGER NOT NULL DEFAULT 0,
    invalid_records INTEGER NOT NULL DEFAULT 0,
    wrong_subreddit_records INTEGER NOT NULL DEFAULT 0,
    blank_lines INTEGER NOT NULL DEFAULT 0,
    errors INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS community_chunks (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES community_import_jobs(id),
    first_source_line INTEGER NOT NULL,
    last_source_line INTEGER NOT NULL,
    record_count INTEGER NOT NULL,
    raw_path TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(job_id, first_source_line, last_source_line)
);

CREATE TABLE IF NOT EXISTS community_source_records (
    id INTEGER PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES community_import_jobs(id),
    source_line INTEGER NOT NULL,
    raw_chunk_id TEXT NOT NULL REFERENCES community_chunks(id),
    raw_index INTEGER NOT NULL,
    record_sha256 TEXT NOT NULL,
    source_type TEXT NOT NULL,
    subreddit TEXT,
    error TEXT,
    imported_at TEXT NOT NULL,
    UNIQUE(job_id, source_line)
);

CREATE TABLE IF NOT EXISTS subreddit_observations (
    id INTEGER PRIMARY KEY,
    subreddit TEXT NOT NULL,
    source_record_id INTEGER NOT NULL UNIQUE
        REFERENCES community_source_records(id),
    observed_at TEXT NOT NULL,
    retrieved_utc REAL,
    reddit_id TEXT,
    fullname TEXT,
    display_name TEXT,
    title TEXT,
    public_description TEXT,
    description TEXT,
    created_utc REAL,
    subscribers INTEGER,
    over18 INTEGER,
    subreddit_type TEXT,
    language TEXT,
    submission_type TEXT,
    wiki_enabled INTEGER,
    icon_url TEXT,
    community_icon_url TEXT,
    header_url TEXT,
    banner_url TEXT,
    banner_background_url TEXT,
    mobile_banner_url TEXT,
    metadata_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subreddit_rule_snapshots (
    id INTEGER PRIMARY KEY,
    subreddit TEXT NOT NULL,
    source_record_id INTEGER NOT NULL UNIQUE
        REFERENCES community_source_records(id),
    observed_at TEXT NOT NULL,
    retrieved_utc REAL,
    rule_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS subreddit_rule_observations (
    id INTEGER PRIMARY KEY,
    snapshot_id INTEGER NOT NULL REFERENCES subreddit_rule_snapshots(id),
    position INTEGER NOT NULL,
    priority INTEGER,
    short_name TEXT,
    description TEXT,
    kind TEXT,
    violation_reason TEXT,
    created_utc REAL,
    content_sha256 TEXT NOT NULL,
    UNIQUE(snapshot_id, position)
);

CREATE TABLE IF NOT EXISTS subreddit_wiki_observations (
    id INTEGER PRIMARY KEY,
    subreddit TEXT NOT NULL,
    source_record_id INTEGER NOT NULL UNIQUE
        REFERENCES community_source_records(id),
    observed_at TEXT NOT NULL,
    retrieved_utc REAL,
    path TEXT NOT NULL,
    content TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    revision_author TEXT,
    revision_author_id TEXT,
    revision_date TEXT,
    revision_reason TEXT
);

CREATE TABLE IF NOT EXISTS subreddit_moderator_snapshots (
    id INTEGER PRIMARY KEY,
    subreddit TEXT NOT NULL,
    source_record_id INTEGER NOT NULL UNIQUE
        REFERENCES community_source_records(id),
    observed_at TEXT NOT NULL,
    retrieved_utc REAL,
    moderator_count INTEGER NOT NULL,
    source_label TEXT
);

CREATE TABLE IF NOT EXISTS subreddit_moderator_observations (
    id INTEGER PRIMARY KEY,
    snapshot_id INTEGER NOT NULL REFERENCES subreddit_moderator_snapshots(id),
    position INTEGER NOT NULL,
    username TEXT NOT NULL,
    account_id TEXT,
    permissions_json TEXT NOT NULL,
    added_utc REAL,
    UNIQUE(snapshot_id, position)
);

CREATE TABLE IF NOT EXISTS community_import_errors (
    id INTEGER PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES community_import_jobs(id),
    source_line INTEGER,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS capture_errors (
    id INTEGER PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES capture_jobs(id),
    source_line INTEGER,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_capture_jobs_status
    ON capture_jobs(status, updated_at);
CREATE INDEX IF NOT EXISTS idx_source_records_job_kind
    ON source_records(job_id, record_kind, source_line);
CREATE INDEX IF NOT EXISTS idx_posts_subreddit_created
    ON posts(subreddit, created_utc DESC);
CREATE INDEX IF NOT EXISTS idx_posts_author_created
    ON posts(author, created_utc DESC);
CREATE INDEX IF NOT EXISTS idx_posts_score
    ON posts(score DESC);
CREATE INDEX IF NOT EXISTS idx_comments_post_parent
    ON comments(post_id, parent_id, created_utc);
CREATE INDEX IF NOT EXISTS idx_comments_author_created
    ON comments(author, created_utc DESC);
CREATE INDEX IF NOT EXISTS idx_comment_placeholders_post
    ON comment_placeholders(post_id, parent_id, id);
CREATE INDEX IF NOT EXISTS idx_assets_owner
    ON assets(owner_type, owner_id, role);
CREATE INDEX IF NOT EXISTS idx_asset_download_events_asset
    ON asset_download_events(asset_id, id);
CREATE INDEX IF NOT EXISTS idx_community_jobs_target
    ON community_import_jobs(subreddit, source_type, status);
CREATE INDEX IF NOT EXISTS idx_community_source_job
    ON community_source_records(job_id, source_line);
CREATE INDEX IF NOT EXISTS idx_subreddit_observations_target
    ON subreddit_observations(subreddit, retrieved_utc);
CREATE INDEX IF NOT EXISTS idx_subreddit_rules_target
    ON subreddit_rule_snapshots(subreddit, retrieved_utc);
CREATE INDEX IF NOT EXISTS idx_subreddit_wikis_target
    ON subreddit_wiki_observations(subreddit, path, retrieved_utc);
CREATE INDEX IF NOT EXISTS idx_subreddit_moderators_target
    ON subreddit_moderator_snapshots(subreddit, retrieved_utc);
"""

FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5(
    post_id UNINDEXED,
    title,
    selftext,
    author,
    subreddit,
    flair_text,
    url,
    tokenize = 'unicode61'
);

CREATE VIRTUAL TABLE IF NOT EXISTS comments_fts USING fts5(
    comment_id UNINDEXED,
    post_id UNINDEXED,
    body,
    author,
    subreddit,
    tokenize = 'unicode61'
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        for key in ("name", "display_name", "id"):
            if value.get(key) is not None:
                return str(value[key])
        return _json(value)
    return str(value)


def _optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None if value is None else int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None or value is False:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_bool(value: Any) -> int | None:
    if value is None:
        return None
    return int(bool(value))


def _thing_id(value: Any, prefix: str | None = None) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    if "_" in result:
        thing_prefix, remainder = result.split("_", 1)
        if thing_prefix in {"t1", "t2", "t3", "t5"}:
            if prefix is not None and thing_prefix != prefix:
                return None
            result = remainder
    return result.lower() or None


def _author(payload: dict[str, Any]) -> str | None:
    return _optional_text(payload.get("author"))


def _subreddit(payload: dict[str, Any]) -> str | None:
    value = payload.get("subreddit")
    if value is None:
        value = payload.get("subreddit_name_prefixed")
    result = _optional_text(value)
    if result and result.lower().startswith("r/"):
        return result[2:]
    return result


def _unwrap_record(payload: Any) -> tuple[str, dict[str, Any] | None]:
    if not isinstance(payload, dict):
        return "unknown", None

    outer_kind = str(payload.get("kind") or "").lower()
    data = payload.get("data")
    if outer_kind in {"t1", "t3", "t5", "more"} and isinstance(data, dict):
        if outer_kind == "more":
            return "comment_placeholder", data
        return {"t1": "comment", "t3": "post", "t5": "subreddit"}[outer_kind], data

    envelope_kind = str(payload.get("type") or payload.get("record_type") or "").lower()
    if isinstance(data, dict) and envelope_kind in {
        "comment",
        "comment_placeholder",
        "post",
        "submission",
        "subreddit",
    }:
        return ("post" if envelope_kind == "submission" else envelope_kind), data

    if "link_id" in payload and ("body" in payload or "parent_id" in payload):
        return "comment", payload
    if "id" in payload and any(
        key in payload for key in ("title", "selftext", "num_comments", "is_self")
    ):
        return "post", payload
    if "display_name" in payload and any(
        key in payload for key in ("public_description", "subscribers", "description")
    ):
        return "subreddit", payload
    return "unknown", payload


def _edited_timestamp(value: Any) -> float | None:
    if value is None or value is False or value == 0 or value == "0" or value == "":
        return None
    return _optional_float(value)


def _vote_state(value: Any) -> int | None:
    if value is True:
        return 1
    if value is False:
        return -1
    return None


def _vote_fields(payload: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "ups",
        "downs",
        "score",
        "upvote_ratio",
        "likes",
        "saved",
        "score_hidden",
        "controversiality",
    )
    return {key: payload[key] for key in keys if key in payload}


def _source_kind(path: Path) -> str:
    lowered = path.name.lower()
    if lowered.endswith(".zst"):
        return "zstandard"
    if lowered.endswith((".warc", ".warc.gz", ".wacz")):
        return "web-archive"
    if lowered.endswith((".jsonl.gz", ".ndjson.gz", ".gz")):
        return "jsonl-gzip"
    if lowered.endswith((".jsonl", ".ndjson")):
        return "jsonl"
    if lowered.endswith(".json"):
        return "json"
    return "unknown"


def iter_source_records(
    path: Path,
    *,
    target: CaptureTarget | None = None,
    source_options: LocalSourceOptions | None = None,
    coverage: ArcticShiftCoverage | None = None,
) -> Iterator[RawRecord]:
    """Yield local JSON records without loading JSONL inputs into memory."""
    path = Path(path)
    kind = _source_kind(path)
    if kind == "zstandard":
        if target is None or source_options is None or coverage is None:
            raise ArchiveError(
                "Arctic Shift sources require a target, source options, and coverage"
            )
        records = iter_zst_records(
            path,
            coverage=coverage,
            after_utc=source_options.after_utc,
            before_utc=source_options.before_utc,
        )
        for record in records:
            raw_record = RawRecord(
                source_line=record.source_line,
                raw_text=record.raw_text,
                payload=record.payload,
                error=record.error,
            )
            record_kind, payload = _unwrap_record(record.payload)
            if source_options.discovery is not None:
                if payload is None or record_kind not in {"post", "comment"}:
                    continue
                record_id = _thing_id(payload.get("id"))
                own_fullname = (
                    f"t3_{record_id}"
                    if record_kind == "post" and record_id
                    else f"t1_{record_id}"
                    if record_id
                    else None
                )
                related_fullnames = {own_fullname} if own_fullname else set()
                if record_kind == "comment":
                    link_id = _thing_id(payload.get("link_id"), "t3")
                    if link_id:
                        related_fullnames.add(f"t3_{link_id}")
                if not (
                    related_fullnames & source_options.discovery.fullnames
                ):
                    continue
            if source_options.source_scope == "global":
                if (
                    payload is None
                    or record_kind not in {"post", "comment"}
                    or not _target_matches(target, record_kind, payload)
                ):
                    continue
            coverage.records_selected += 1
            coverage.note_kind(
                "invalid" if record.error else record_kind,
                selected=True,
            )
            yield raw_record
        return
    if kind == "web-archive":
        raise UnsupportedSourceError(
            "WARC/WACZ and related web-archive sources are outside this module"
        )
    if kind == "unknown":
        raise UnsupportedSourceError(
            "Supported sources are .json, .jsonl, .ndjson, .jsonl.gz, and .zst"
        )

    if kind == "json":
        with path.open("r", encoding="utf-8-sig") as handle:
            payload = json.load(handle)
        values = payload if isinstance(payload, list) else [payload]
        for source_line, value in enumerate(values, start=1):
            yield RawRecord(
                source_line=source_line,
                raw_text=_json(value),
                payload=value,
            )
        return

    opener = gzip.open if kind == "jsonl-gzip" else open
    with opener(path, "rt", encoding="utf-8-sig") as handle:
        for source_line, line in enumerate(handle, start=1):
            raw_text = line.rstrip("\r\n")
            if not raw_text.strip():
                continue
            try:
                payload = json.loads(raw_text)
            except json.JSONDecodeError as exc:
                yield RawRecord(
                    source_line=source_line,
                    raw_text=raw_text,
                    payload=None,
                    error=f"Invalid JSON: {exc.msg}",
                )
                continue
            yield RawRecord(
                source_line=source_line,
                raw_text=raw_text,
                payload=payload,
            )


def _chunk_digest(records: Iterable[RawRecord]) -> str:
    digest = hashlib.sha256()
    for record in records:
        digest.update(record.raw_text.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _verify_chunk(path: Path, expected_digest: str) -> None:
    digest = hashlib.sha256()
    with gzip.open(path, "rb") as handle:
        for line in handle:
            digest.update(line)
    if digest.hexdigest() != expected_digest:
        raise ArchiveError(f"Existing raw chunk failed verification: {path}")


def _write_chunk(
    raw_root: Path,
    job_id: str,
    records: list[RawRecord],
) -> tuple[str, Path, str]:
    first_line = records[0].source_line
    last_line = records[-1].source_line
    digest = _chunk_digest(records)
    chunk_id = hashlib.sha256(
        f"{job_id}:{first_line}:{last_line}:{digest}".encode("utf-8")
    ).hexdigest()[:32]
    job_root = raw_root / job_id
    job_root.mkdir(parents=True, exist_ok=True)
    filename = f"{first_line:012d}-{last_line:012d}-{digest[:16]}.jsonl.gz"
    destination = job_root / filename
    if destination.exists():
        _verify_chunk(destination, digest)
        return chunk_id, destination, digest

    temporary = job_root / f".{filename}.{uuid4().hex}.tmp"
    try:
        with temporary.open("xb") as raw_handle:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                fileobj=raw_handle,
                mtime=0,
            ) as compressed:
                for record in records:
                    compressed.write(record.raw_text.encode("utf-8"))
                    compressed.write(b"\n")
            raw_handle.flush()
            os.fsync(raw_handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    _verify_chunk(destination, digest)
    return chunk_id, destination, digest


def _stable_job_id(
    source_path: Path,
    source_size: int,
    source_mtime_ns: int,
    target: CaptureTarget,
    options: CaptureOptions,
    source_options: LocalSourceOptions | None,
) -> str:
    identity = {
        "schema": ARCHIVE_SCHEMA_VERSION,
        "source_path": str(source_path),
        "source_size": source_size,
        "source_mtime_ns": source_mtime_ns,
        "target": target.as_dict(),
        "options": options.manifest(),
    }
    if source_options is not None:
        identity["source_options"] = source_options.manifest()
    return hashlib.sha256(_json(identity).encode("utf-8")).hexdigest()[:32]


def _write_job_manifest(
    raw_root: Path,
    job_id: str,
    source_path: Path,
    source_kind: str,
    source_size: int,
    source_mtime_ns: int,
    target: CaptureTarget,
    options: CaptureOptions,
    source_options: LocalSourceOptions | None,
    verified_sha256: str | None,
) -> Path:
    """Create or verify the durable manifest needed to rebuild the index."""
    job_root = raw_root / job_id
    job_root.mkdir(parents=True, exist_ok=True)
    path = job_root / "manifest.json"
    payload = {
        "archive_schema_version": ARCHIVE_SCHEMA_VERSION,
        "job_id": job_id,
        "source": {
            "path": str(source_path),
            "kind": source_kind,
            "size": source_size,
            "mtime_ns": source_mtime_ns,
        },
        "target": target.as_dict(),
        "options": options.manifest(),
    }
    if verified_sha256 is not None:
        payload["source"]["sha256"] = verified_sha256
    if source_options is not None:
        payload["source_options"] = source_options.manifest()
    encoded = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )
    if path.exists():
        if path.read_bytes() != encoded:
            raise ArchiveError(f"Existing capture manifest does not match: {path}")
        return path

    temporary = job_root / f".manifest.{uuid4().hex}.tmp"
    try:
        with temporary.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return path


def _write_json_create_or_verify(path: Path, payload: dict[str, Any]) -> Path:
    """Create a deterministic JSON artifact without overwriting another file."""
    path = Path(path).expanduser().resolve(strict=False)
    encoded = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )
    if path.exists():
        if not path.is_file() or path.read_bytes() != encoded:
            raise ArchiveError(f"Existing JSON artifact does not match: {path}")
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{uuid4().hex}.tmp"
    try:
        with temporary.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return path


def _write_arctic_shift_coverage(
    path: Path,
    *,
    job_id: str,
    target: CaptureTarget,
    source_options: LocalSourceOptions,
    coverage: ArcticShiftCoverage,
) -> Path:
    return _write_json_create_or_verify(
        path,
        {
            "format": "keivotos-reddit-arctic-shift-coverage-v1",
            "job_id": job_id,
            "target": target.as_dict(),
            "source_options": source_options.manifest(),
            "coverage": coverage.as_dict(),
        },
    )


def _batched(
    records: Iterable[RawRecord],
    size: int,
    after_line: int,
) -> Iterator[list[RawRecord]]:
    batch: list[RawRecord] = []
    for record in records:
        if record.source_line <= after_line:
            continue
        batch.append(record)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def ensure_archive_schema(connection: sqlite3.Connection) -> None:
    """Create the additive standalone Reddit index schema and FTS tables."""
    connection.executescript(SCHEMA_SQL)
    connection.executescript(INDEX_SQL)
    try:
        connection.executescript(FTS_SQL)
    except sqlite3.OperationalError as exc:
        raise ArchiveError("This SQLite build does not provide required FTS5 support") from exc
    connection.execute(
        """
        INSERT INTO archive_meta(key, value) VALUES('schema_version', ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """,
        (str(ARCHIVE_SCHEMA_VERSION),),
    )
    connection.execute(
        """
        INSERT INTO archive_meta(key, value) VALUES('media_schema_version', ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """,
        (str(MEDIA_SCHEMA_VERSION),),
    )
    connection.execute(
        """
        INSERT INTO archive_meta(key, value) VALUES('community_schema_version', ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """,
        (str(COMMUNITY_SCHEMA_VERSION),),
    )
    connection.commit()


@contextmanager
def open_archive(database_path: Path) -> Generator[sqlite3.Connection, None, None]:
    """Open the rebuildable Reddit index with WAL and foreign keys enabled."""
    database_path = Path(database_path).expanduser().resolve(strict=False)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=60)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA foreign_keys = ON")
        ensure_archive_schema(connection)
        yield connection
    finally:
        connection.close()


def _target_matches(
    target: CaptureTarget,
    record_kind: str,
    payload: dict[str, Any],
) -> bool:
    subreddit = _subreddit(payload)
    author = _author(payload)
    record_id = _thing_id(payload.get("id"))
    post_id = (
        record_id
        if record_kind == "post"
        else _thing_id(payload.get("link_id"), "t3")
    )

    if target.kind in {"subreddit", "search"} and target.subreddit:
        if not subreddit or subreddit.casefold() != target.subreddit.casefold():
            return False
    if target.kind == "post" and target.post_id:
        if post_id != target.post_id.lower():
            return False
    if target.kind == "user" and target.username:
        if not author or author.casefold() != target.username.casefold():
            return False
    if target.kind == "search" and target.query:
        haystack = " ".join(
            str(payload.get(key) or "")
            for key in ("title", "selftext", "body", "author", "link_flair_text")
        )
        if target.query.casefold() not in haystack.casefold():
            return False
    if target.kind in {"asset", "external"}:
        source_url = _optional_text(
            payload.get("url_overridden_by_dest") or payload.get("url")
        )
        if source_url != target.canonical_url:
            return False
    return True


def _select_job_post(
    connection: sqlite3.Connection,
    job_id: str,
    post_id: str,
    posts_limit: int | None,
    observed_at: str,
) -> bool:
    existing = connection.execute(
        "SELECT 1 FROM capture_job_posts WHERE job_id=? AND post_id=?",
        (job_id, post_id),
    ).fetchone()
    if existing is not None:
        return True
    if posts_limit is not None:
        count = connection.execute(
            "SELECT COUNT(*) FROM capture_job_posts WHERE job_id=?",
            (job_id,),
        ).fetchone()[0]
        if count >= posts_limit:
            return False
    connection.execute(
        "INSERT INTO capture_job_posts(job_id, post_id, selected_at) VALUES(?, ?, ?)",
        (job_id, post_id, observed_at),
    )
    return True


def _refresh_post_fts(connection: sqlite3.Connection, post_id: str) -> None:
    row = connection.execute("SELECT * FROM posts WHERE id=?", (post_id,)).fetchone()
    if row is None:
        return
    connection.execute("DELETE FROM posts_fts WHERE post_id=?", (post_id,))
    connection.execute(
        """
        INSERT INTO posts_fts(
            post_id, title, selftext, author, subreddit, flair_text, url
        ) VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        (
            post_id,
            row["title"] or "",
            row["selftext"] or "",
            row["author"] or "",
            row["subreddit"] or "",
            row["flair_text"] or "",
            row["url"] or "",
        ),
    )


def _refresh_comment_fts(connection: sqlite3.Connection, comment_id: str) -> None:
    row = connection.execute(
        "SELECT * FROM comments WHERE id=?", (comment_id,)
    ).fetchone()
    if row is None:
        return
    connection.execute("DELETE FROM comments_fts WHERE comment_id=?", (comment_id,))
    connection.execute(
        """
        INSERT INTO comments_fts(comment_id, post_id, body, author, subreddit)
        VALUES(?, ?, ?, ?, ?)
        """,
        (
            comment_id,
            row["post_id"],
            row["body"] or "",
            row["author"] or "",
            row["subreddit"] or "",
        ),
    )


def _allowed_external(url: str, domains: tuple[str, ...]) -> bool:
    try:
        host = (urlsplit(url).hostname or "").casefold()
    except ValueError:
        return False
    for domain in domains:
        allowed = domain.casefold().lstrip(".")
        if host == allowed or host.endswith(f".{allowed}"):
            return True
    return False


def _image_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    return (
        (parsed.hostname or "").casefold() in REDDIT_MEDIA_HOSTS
        or Path(parsed.path).suffix.casefold() in IMAGE_SUFFIXES
    )


def _video_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").casefold()
    suffix = Path(parsed.path).suffix.casefold()
    return host == "v.redd.it" or suffix in {".m3u8", ".mp4", ".mpd", ".webm"}


def _asset_candidates(
    payload: dict[str, Any],
    owner_type: str,
    owner_id: str,
    options: CaptureOptions,
) -> list[tuple[str, str, str]]:
    candidates: dict[tuple[str, str], str] = {}

    def add(role: str, value: Any, policy: str) -> None:
        if not isinstance(value, str) or not value.startswith(("http://", "https://")):
            return
        candidates[(role, value)] = policy

    if options.save_images in {"original", "both"}:
        primary = payload.get("url_overridden_by_dest") or payload.get("url")
        if isinstance(primary, str) and _image_url(primary):
            add("image-original", primary, options.save_images)
        media_metadata = payload.get("media_metadata")
        if isinstance(media_metadata, dict):
            for media in media_metadata.values():
                if not isinstance(media, dict):
                    continue
                source = media.get("s")
                if isinstance(source, dict):
                    add("gallery-original", source.get("u"), options.save_images)

    if options.save_images in {"preview", "both"}:
        add("thumbnail", payload.get("thumbnail"), options.save_images)
        preview = payload.get("preview")
        if isinstance(preview, dict):
            for image in preview.get("images") or []:
                if not isinstance(image, dict):
                    continue
                source = image.get("source")
                if isinstance(source, dict):
                    add("preview-source", source.get("url"), options.save_images)
                for resolution in image.get("resolutions") or []:
                    if isinstance(resolution, dict):
                        add("preview-resolution", resolution.get("url"), options.save_images)

    if options.save_videos != "none":
        media_blocks = [payload.get("media"), payload.get("secure_media")]
        for media in media_blocks:
            if not isinstance(media, dict):
                continue
            video = media.get("reddit_video")
            if not isinstance(video, dict):
                continue
            add("video-dash", video.get("dash_url"), options.save_videos)
            add("video-hls", video.get("hls_url"), options.save_videos)
            if options.save_videos == "full":
                add("video-file", video.get("fallback_url"), options.save_videos)
                add(
                    "video-scrubber",
                    video.get("scrubber_media_url"),
                    options.save_videos,
                )

    if options.save_avatars:
        for key in ("author_icon_img", "icon_img", "snoovatar_img"):
            add("avatar", payload.get(key), "original")

    body = str(payload.get("body") or payload.get("selftext") or "")
    body_urls = [url.rstrip(".,;:!?)]}") for url in URL_RE.findall(body)]
    if options.save_images in {"original", "both"}:
        for url in body_urls:
            if _image_url(url):
                add("embedded-image", url, options.save_images)
    if options.save_videos != "none":
        for url in body_urls:
            if _video_url(url):
                add("embedded-video", url, options.save_videos)

    if options.save_external_assets:
        outbound = payload.get("url_overridden_by_dest") or payload.get("url")
        if isinstance(outbound, str) and _allowed_external(
            outbound, options.external_domains
        ):
            add("external", outbound, "linked-media")
        for url in body_urls:
            if _allowed_external(url, options.external_domains):
                add("external", url, "linked-media")

    if options.save_linked_files:
        existing_urls = {url for _role, url in candidates}
        primary = payload.get("url_overridden_by_dest") or payload.get("url")
        for url in link_urls(
            primary if isinstance(primary, str) else None,
            body,
            excluding=existing_urls,
        ):
            add("linked-file", url, "linked-file")

    return [(role, url, policy) for (role, url), policy in candidates.items()]


def _queue_assets(
    connection: sqlite3.Connection,
    owner_type: str,
    owner_id: str,
    payload: dict[str, Any],
    options: CaptureOptions,
    observed_at: str,
) -> None:
    for role, url, policy in _asset_candidates(
        payload, owner_type, owner_id, options
    ):
        connection.execute(
            """
            INSERT INTO assets(
                owner_type, owner_id, role, url, desired_policy,
                first_seen_at, last_seen_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(owner_type, owner_id, role, url) DO UPDATE SET
                desired_policy=excluded.desired_policy,
                last_seen_at=excluded.last_seen_at
            """,
            (owner_type, owner_id, role, url, policy, observed_at, observed_at),
        )


def _upsert_post(
    connection: sqlite3.Connection,
    payload: dict[str, Any],
    source_record_id: int,
    observed_at: str,
    options: CaptureOptions,
) -> str | None:
    post_id = _thing_id(payload.get("id"), "t3")
    if post_id is None:
        return None
    values = {
        "id": post_id,
        "fullname": _optional_text(payload.get("name")) or f"t3_{post_id}",
        "subreddit": _subreddit(payload),
        "author": _author(payload),
        "author_id": _thing_id(payload.get("author_fullname"), "t2"),
        "title": _optional_text(payload.get("title")),
        "selftext": _optional_text(payload.get("selftext")),
        "selftext_html": _optional_text(payload.get("selftext_html")),
        "created_utc": _optional_float(payload.get("created_utc")),
        "edited_utc": _edited_timestamp(payload.get("edited")),
        "permalink": _optional_text(payload.get("permalink")),
        "url": _optional_text(
            payload.get("url_overridden_by_dest") or payload.get("url")
        ),
        "domain": _optional_text(payload.get("domain")),
        "flair_text": _optional_text(payload.get("link_flair_text")),
        "score": _optional_int(payload.get("score")),
        "upvote_ratio": _optional_float(payload.get("upvote_ratio")),
        "num_comments": _optional_int(payload.get("num_comments")),
        "is_self": _optional_bool(payload.get("is_self")),
        "nsfw": _optional_bool(payload.get("over_18")),
        "spoiler": _optional_bool(payload.get("spoiler")),
        "stickied": _optional_bool(payload.get("stickied")),
        "locked": _optional_bool(payload.get("locked")),
        "archived": _optional_bool(payload.get("archived")),
        "distinguished": _optional_text(payload.get("distinguished")),
        "removed_by_category": _optional_text(payload.get("removed_by_category")),
        "thumbnail_url": _optional_text(payload.get("thumbnail")),
    }
    columns = list(values)
    placeholders = ", ".join("?" for _ in columns)
    assignments = ", ".join(
        f"{column}=COALESCE(excluded.{column}, posts.{column})"
        for column in columns
        if column != "id"
    )
    connection.execute(
        f"""
        INSERT INTO posts(
            {", ".join(columns)}, first_observed_at, latest_observed_at
        ) VALUES({placeholders}, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            {assignments},
            latest_observed_at=excluded.latest_observed_at
        """,
        (*[values[column] for column in columns], observed_at, observed_at),
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO post_observations(
            post_id, source_record_id, observed_at, score, upvote_ratio,
            num_comments, edited_utc, author, removed_by_category,
            my_vote, reddit_saved, vote_fields_json
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            post_id,
            source_record_id,
            observed_at,
            values["score"],
            values["upvote_ratio"],
            values["num_comments"],
            values["edited_utc"],
            values["author"],
            values["removed_by_category"],
            _vote_state(payload.get("likes")),
            _optional_bool(payload.get("saved")),
            _json(_vote_fields(payload)),
        ),
    )
    _queue_assets(connection, "post", post_id, payload, options, observed_at)
    _refresh_post_fts(connection, post_id)
    return post_id


def _upsert_comment(
    connection: sqlite3.Connection,
    payload: dict[str, Any],
    source_record_id: int,
    observed_at: str,
    options: CaptureOptions,
) -> str | None:
    comment_id = _thing_id(payload.get("id"), "t1")
    post_id = _thing_id(payload.get("link_id"), "t3")
    if comment_id is None or post_id is None:
        return None
    values = {
        "id": comment_id,
        "fullname": _optional_text(payload.get("name")) or f"t1_{comment_id}",
        "post_id": post_id,
        "parent_id": _optional_text(payload.get("parent_id")),
        "subreddit": _subreddit(payload),
        "author": _author(payload),
        "body": _optional_text(payload.get("body")),
        "body_html": _optional_text(payload.get("body_html")),
        "created_utc": _optional_float(payload.get("created_utc")),
        "edited_utc": _edited_timestamp(payload.get("edited")),
        "score": _optional_int(payload.get("score")),
        "depth": _optional_int(payload.get("depth")),
        "is_submitter": _optional_bool(payload.get("is_submitter")),
        "distinguished": _optional_text(payload.get("distinguished")),
        "stickied": _optional_bool(payload.get("stickied")),
        "score_hidden": _optional_bool(payload.get("score_hidden")),
        "controversiality": _optional_int(payload.get("controversiality")),
        "permalink": _optional_text(payload.get("permalink")),
    }
    columns = list(values)
    placeholders = ", ".join("?" for _ in columns)
    assignments = ", ".join(
        f"{column}=COALESCE(excluded.{column}, comments.{column})"
        for column in columns
        if column != "id"
    )
    connection.execute(
        f"""
        INSERT INTO comments(
            {", ".join(columns)}, first_observed_at, latest_observed_at
        ) VALUES({placeholders}, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            {assignments},
            latest_observed_at=excluded.latest_observed_at
        """,
        (*[values[column] for column in columns], observed_at, observed_at),
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO comment_observations(
            comment_id, source_record_id, observed_at, score, edited_utc,
            author, my_vote, vote_fields_json
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            comment_id,
            source_record_id,
            observed_at,
            values["score"],
            values["edited_utc"],
            values["author"],
            _vote_state(payload.get("likes")),
            _json(_vote_fields(payload)),
        ),
    )
    _queue_assets(connection, "comment", comment_id, payload, options, observed_at)
    _refresh_comment_fts(connection, comment_id)
    return comment_id


def _insert_comment_placeholder(
    connection: sqlite3.Connection,
    payload: dict[str, Any],
    source_record_id: int,
    observed_at: str,
) -> str | None:
    post_id = _thing_id(payload.get("link_id"), "t3")
    if post_id is None:
        return None
    children = payload.get("children")
    child_ids = sorted(
        {
            child_id
            for value in children
            if (child_id := _thing_id(value, "t1")) is not None
        }
    ) if isinstance(children, list) else []
    connection.execute(
        """
        INSERT OR IGNORE INTO comment_placeholders(
            post_id, source_record_id, placeholder_id, parent_id,
            child_ids_json, declared_count, observed_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        (
            post_id,
            source_record_id,
            _thing_id(payload.get("id"), "more"),
            _optional_text(payload.get("parent_id")),
            _json(child_ids),
            _optional_int(payload.get("count")),
            observed_at,
        ),
    )
    return post_id


def _process_chunk(
    connection: sqlite3.Connection,
    database_path: Path,
    job_id: str,
    target: CaptureTarget,
    options: CaptureOptions,
    records: list[RawRecord],
    raw_root: Path,
) -> dict[str, int]:
    chunk_id, chunk_path, chunk_digest = _write_chunk(raw_root, job_id, records)
    observed_at = _now()
    relative_chunk = chunk_path.relative_to(database_path.parent).as_posix()
    counts = {
        "records_seen": len(records),
        "records_imported": 0,
        "posts_imported": 0,
        "comments_imported": 0,
        "records_skipped": 0,
        "errors": 0,
    }
    first_line = records[0].source_line
    last_line = records[-1].source_line

    with connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO capture_chunks(
                id, job_id, first_source_line, last_source_line, record_count,
                raw_path, content_sha256, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chunk_id,
                job_id,
                first_line,
                last_line,
                len(records),
                relative_chunk,
                chunk_digest,
                observed_at,
            ),
        )
        for raw_index, record in enumerate(records):
            record_kind, payload = _unwrap_record(record.payload)
            reddit_id = None
            if isinstance(payload, dict):
                reddit_id = _thing_id(payload.get("id"))
            record_digest = hashlib.sha256(
                record.raw_text.encode("utf-8")
            ).hexdigest()
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO source_records(
                    job_id, source_line, raw_chunk_id, raw_index,
                    record_sha256, record_kind, reddit_id, error, imported_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    record.source_line,
                    chunk_id,
                    raw_index,
                    record_digest,
                    "invalid" if record.error else record_kind,
                    reddit_id,
                    record.error,
                    observed_at,
                ),
            )
            if cursor.rowcount == 0:
                counts["records_skipped"] += 1
                continue
            source_record_id = int(cursor.lastrowid)

            if record.error:
                counts["errors"] += 1
                connection.execute(
                    """
                    INSERT INTO capture_errors(job_id, source_line, message, created_at)
                    VALUES(?, ?, ?, ?)
                    """,
                    (job_id, record.source_line, record.error, observed_at),
                )
                continue
            if payload is None or record_kind not in {
                "post",
                "comment",
                "comment_placeholder",
            }:
                counts["records_skipped"] += 1
                continue
            if not _target_matches(target, record_kind, payload):
                counts["records_skipped"] += 1
                continue
            if (
                record_kind in {"comment", "comment_placeholder"}
                and options.comments == "none"
            ):
                counts["records_skipped"] += 1
                continue

            post_id = (
                _thing_id(payload.get("id"), "t3")
                if record_kind == "post"
                else _thing_id(payload.get("link_id"), "t3")
            )
            if post_id is None or not _select_job_post(
                connection,
                job_id,
                post_id,
                options.posts_limit,
                observed_at,
            ):
                counts["records_skipped"] += 1
                continue

            if record_kind == "post":
                normalized_id = _upsert_post(
                    connection,
                    payload,
                    source_record_id,
                    observed_at,
                    options,
                )
            elif record_kind == "comment":
                normalized_id = _upsert_comment(
                    connection,
                    payload,
                    source_record_id,
                    observed_at,
                    options,
                )
            else:
                normalized_id = _insert_comment_placeholder(
                    connection,
                    payload,
                    source_record_id,
                    observed_at,
                )
            if normalized_id is None:
                counts["errors"] += 1
                connection.execute(
                    """
                    INSERT INTO capture_errors(job_id, source_line, message, created_at)
                    VALUES(?, ?, ?, ?)
                    """,
                    (
                        job_id,
                        record.source_line,
                        f"{record_kind} record is missing required IDs",
                        observed_at,
                    ),
                )
                continue
            connection.execute(
                "UPDATE source_records SET normalized=1 WHERE id=?",
                (source_record_id,),
            )
            counts["records_imported"] += 1
            if record_kind in {"post", "comment"}:
                counts[f"{record_kind}s_imported"] += 1

        connection.execute(
            """
            UPDATE capture_jobs SET
                status='running',
                last_source_line=?,
                records_seen=records_seen + ?,
                records_imported=records_imported + ?,
                posts_imported=posts_imported + ?,
                comments_imported=comments_imported + ?,
                records_skipped=records_skipped + ?,
                errors=errors + ?,
                updated_at=?
            WHERE id=?
            """,
            (
                last_line,
                counts["records_seen"],
                counts["records_imported"],
                counts["posts_imported"],
                counts["comments_imported"],
                counts["records_skipped"],
                counts["errors"],
                observed_at,
                job_id,
            ),
        )
    return counts


def _summary(
    connection: sqlite3.Connection,
    database_path: Path,
    raw_root: Path,
    job_id: str,
) -> ImportSummary:
    row = connection.execute(
        "SELECT * FROM capture_jobs WHERE id=?", (job_id,)
    ).fetchone()
    if row is None:
        raise ArchiveError(f"Capture job disappeared: {job_id}")
    return ImportSummary(
        job_id=job_id,
        status=row["status"],
        source_path=row["source_path"],
        database_path=str(database_path),
        raw_directory=str(raw_root / job_id),
        records_seen=row["records_seen"],
        records_imported=row["records_imported"],
        posts_imported=row["posts_imported"],
        comments_imported=row["comments_imported"],
        records_skipped=row["records_skipped"],
        errors=row["errors"],
        last_source_line=row["last_source_line"],
    )


def import_local_source(
    database_path: Path,
    source_path: Path,
    target: CaptureTarget,
    options: CaptureOptions,
    *,
    resume: bool = False,
    source_options: LocalSourceOptions | None = None,
    coverage_path: Path | None = None,
) -> ImportSummary:
    """Import one local source into atomic raw chunks and the FTS index."""
    database_path = Path(database_path).expanduser().resolve(strict=False)
    source_path = Path(source_path).expanduser().resolve(strict=True)
    if not source_path.is_file():
        raise ArchiveError(f"Source is not a file: {source_path}")
    source_kind = _source_kind(source_path)
    if source_kind in {"web-archive", "unknown"}:
        # Fail before creating a database/job for a format Slice 1 cannot read.
        next(iter_source_records(source_path))
    if source_kind == "zstandard":
        source_options = source_options or LocalSourceOptions()
    elif source_options is not None or coverage_path is not None:
        raise ArchiveError(
            "source scope, date, hash, and coverage options apply only to .zst sources"
        )

    stat_result = source_path.stat()
    verified_sha256 = None
    if source_options is not None and source_options.expected_sha256 is not None:
        verified_sha256 = verify_sha256(
            source_path, source_options.expected_sha256
        )

    coverage = None
    if source_kind == "zstandard":
        coverage = ArcticShiftCoverage(
            source_path=str(source_path),
            source_size=int(stat_result.st_size),
            source_sha256=verified_sha256,
        )
        # Open and decode the first record before creating archive state. Date
        # filtering is intentionally omitted so a far-future boundary does not
        # force a full validation pass here.
        probe_coverage = ArcticShiftCoverage(
            source_path=str(source_path),
            source_size=int(stat_result.st_size),
            source_sha256=verified_sha256,
        )
        probe = iter_zst_records(source_path, coverage=probe_coverage)
        try:
            next(probe)
        except StopIteration:
            pass
        finally:
            probe.close()

    job_id = _stable_job_id(
        source_path,
        int(stat_result.st_size),
        int(stat_result.st_mtime_ns),
        target,
        options,
        source_options,
    )
    raw_root = database_path.parent / "archives" / "raw"
    _write_job_manifest(
        raw_root,
        job_id,
        source_path,
        source_kind,
        int(stat_result.st_size),
        int(stat_result.st_mtime_ns),
        target,
        options,
        source_options,
        verified_sha256,
    )

    with open_archive(database_path) as connection:
        existing = connection.execute(
            "SELECT * FROM capture_jobs WHERE id=?", (job_id,)
        ).fetchone()
        if existing is not None and not resume:
            raise ResumeRequiredError(
                f"Capture job {job_id} already exists; pass --resume to reuse it"
            )
        now = _now()
        if existing is None:
            connection.execute(
                """
                INSERT INTO capture_jobs(
                    id, target_kind, target_url, target_json, source_path,
                    source_kind, source_size, source_mtime_ns, posts_limit,
                    comments_policy, policy_json, status, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'running', ?, ?)
                """,
                (
                    job_id,
                    target.kind,
                    target.canonical_url,
                    _json(target.as_dict()),
                    str(source_path),
                    source_kind,
                    int(stat_result.st_size),
                    int(stat_result.st_mtime_ns),
                    options.posts_limit,
                    options.comments,
                    _json(options.manifest()),
                    now,
                    now,
                ),
            )
            connection.commit()
            last_source_line = 0
        else:
            if existing["status"] == "complete":
                if coverage_path is not None:
                    default_coverage = raw_root / job_id / "coverage.json"
                    if not default_coverage.is_file():
                        raise ArchiveError(
                            f"Completed job has no coverage report: {default_coverage}"
                        )
                    _write_json_create_or_verify(
                        coverage_path,
                        json.loads(default_coverage.read_text(encoding="utf-8")),
                    )
                return _summary(connection, database_path, raw_root, job_id)
            last_source_line = int(existing["last_source_line"])
            connection.execute(
                "UPDATE capture_jobs SET status='running', updated_at=? WHERE id=?",
                (now, job_id),
            )
            connection.commit()

        try:
            records = iter_source_records(
                source_path,
                target=target,
                source_options=source_options,
                coverage=coverage,
            )
            for chunk in _batched(records, options.chunk_size, last_source_line):
                _process_chunk(
                    connection,
                    database_path,
                    job_id,
                    target,
                    options,
                    chunk,
                    raw_root,
                )
            finished_at = _now()
            connection.execute(
                """
                UPDATE capture_jobs
                SET status='complete', updated_at=?, completed_at=?
                WHERE id=?
                """,
                (finished_at, finished_at, job_id),
            )
            connection.commit()
            if coverage is not None and source_options is not None:
                default_coverage = raw_root / job_id / "coverage.json"
                _write_arctic_shift_coverage(
                    default_coverage,
                    job_id=job_id,
                    target=target,
                    source_options=source_options,
                    coverage=coverage,
                )
                if coverage_path is not None:
                    requested_coverage = Path(coverage_path).expanduser().resolve(
                        strict=False
                    )
                    if requested_coverage != default_coverage.resolve(strict=False):
                        _write_arctic_shift_coverage(
                            requested_coverage,
                            job_id=job_id,
                            target=target,
                            source_options=source_options,
                            coverage=coverage,
                        )
        except Exception as exc:
            failed_at = _now()
            connection.execute(
                """
                UPDATE capture_jobs
                SET status='failed', errors=errors + 1, updated_at=?
                WHERE id=?
                """,
                (failed_at, job_id),
            )
            connection.execute(
                """
                INSERT INTO capture_errors(job_id, message, created_at)
                VALUES(?, ?, ?)
                """,
                (job_id, str(exc), failed_at),
            )
            connection.commit()
            raise
        return _summary(connection, database_path, raw_root, job_id)


def _fts_query(value: str) -> str:
    terms = re.findall(r"[\w-]+", value, flags=re.UNICODE)
    if not terms:
        raise ValueError("Search query has no searchable terms")
    return " AND ".join(f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms)


def search_archive(
    connection: sqlite3.Connection,
    query: str,
    *,
    limit: int = 50,
    subreddit: str | None = None,
    author: str | None = None,
    record_type: str = "all",
) -> list[dict[str, Any]]:
    """Search indexed post/comment text without reading raw artifacts."""
    if limit <= 0:
        raise ValueError("limit must be positive")
    if record_type not in {"all", "post", "comment"}:
        raise ValueError("record_type must be all, post, or comment")
    match = _fts_query(query)
    rows: list[dict[str, Any]] = []

    if record_type in {"all", "post"}:
        clauses = ["posts_fts MATCH ?"]
        params: list[Any] = [match]
        if subreddit:
            clauses.append("p.subreddit = ? COLLATE NOCASE")
            params.append(subreddit)
        if author:
            clauses.append("p.author = ? COLLATE NOCASE")
            params.append(author)
        params.append(limit)
        post_rows = connection.execute(
            f"""
            SELECT
                'post' AS record_type,
                p.id,
                p.id AS post_id,
                p.subreddit,
                p.author,
                p.title,
                p.selftext AS body,
                p.score,
                p.created_utc,
                p.latest_observed_at,
                bm25(posts_fts) AS rank
            FROM posts_fts
            JOIN posts p ON p.id=posts_fts.post_id
            WHERE {" AND ".join(clauses)}
            ORDER BY rank
            LIMIT ?
            """,
            params,
        ).fetchall()
        rows.extend(dict(row) for row in post_rows)

    if record_type in {"all", "comment"}:
        clauses = ["comments_fts MATCH ?"]
        params = [match]
        if subreddit:
            clauses.append("c.subreddit = ? COLLATE NOCASE")
            params.append(subreddit)
        if author:
            clauses.append("c.author = ? COLLATE NOCASE")
            params.append(author)
        params.append(limit)
        comment_rows = connection.execute(
            f"""
            SELECT
                'comment' AS record_type,
                c.id,
                c.post_id,
                c.subreddit,
                c.author,
                NULL AS title,
                c.body,
                c.score,
                c.created_utc,
                c.latest_observed_at,
                bm25(comments_fts) AS rank
            FROM comments_fts
            JOIN comments c ON c.id=comments_fts.comment_id
            WHERE {" AND ".join(clauses)}
            ORDER BY rank
            LIMIT ?
            """,
            params,
        ).fetchall()
        rows.extend(dict(row) for row in comment_rows)

    rows.sort(key=lambda row: (float(row["rank"]), row["record_type"], row["id"]))
    return rows[:limit]
