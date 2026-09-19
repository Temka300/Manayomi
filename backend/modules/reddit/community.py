"""Offline import of subreddit metadata, rules, wiki, and moderator snapshots."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterable, Iterator
from urllib.parse import urlsplit

from modules.reddit import arctic_shift
from modules.reddit.archive import (
    ArchiveError,
    COMMUNITY_SCHEMA_VERSION,
    RawRecord,
    _json,
    _now,
    _write_chunk,
    _write_json_create_or_verify,
    open_archive,
)
from modules.reddit.arctic_shift import normalize_sha256, verify_sha256


COMMUNITY_SOURCE_TYPES = {"about", "rules", "wiki", "moderators"}
COMMUNITY_SOURCE_SCOPES = {"scoped", "global"}
MODERATOR_BUNDLE_FORMAT = "keivotos-reddit-moderators-v1"
DEFAULT_CHUNK_SIZE = 500
SUBREDDIT_RE = re.compile(r"^[A-Za-z0-9_]{2,21}$")
WIKI_PATH_RE = re.compile(
    r"^/r/(?P<subreddit>[A-Za-z0-9_]{2,21})/wiki(?:/|$)",
    re.IGNORECASE,
)


class CommunityError(RuntimeError):
    """Raised when a community snapshot cannot be imported safely."""


class CommunityResumeRequiredError(CommunityError):
    """Raised when an existing community job needs explicit resume."""


class CommunityRecordError(CommunityError):
    """Raised when one selected source record violates its declared schema."""


@dataclass(frozen=True)
class CommunityImportOptions:
    source_type: str
    source_scope: str = "scoped"
    chunk_size: int = DEFAULT_CHUNK_SIZE
    expected_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.source_type not in COMMUNITY_SOURCE_TYPES:
            raise ValueError(
                "source_type must be about, rules, wiki, or moderators"
            )
        if self.source_scope not in COMMUNITY_SOURCE_SCOPES:
            raise ValueError("source_scope must be scoped or global")
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if self.expected_sha256 is not None:
            object.__setattr__(
                self,
                "expected_sha256",
                normalize_sha256(self.expected_sha256),
            )

    def manifest(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CommunityScan:
    records_scanned: int = 0
    records_matched: int = 0
    invalid_records: int = 0
    wrong_subreddit_records: int = 0
    blank_lines: int = 0


@dataclass(frozen=True)
class CommunityImportSummary:
    job_id: str
    status: str
    subreddit: str
    source_type: str
    source_path: str
    database_path: str
    raw_directory: str
    coverage_path: str
    records_scanned: int
    records_matched: int
    records_preserved: int
    records_imported: int
    invalid_records: int
    wrong_subreddit_records: int
    blank_lines: int
    last_source_line: int
    errors: int


def normalize_subreddit(value: str) -> str:
    normalized = value.strip()
    if normalized.casefold().startswith("r/"):
        normalized = normalized[2:]
    if not SUBREDDIT_RE.fullmatch(normalized):
        raise ValueError(
            "subreddit must contain 2-21 letters, numbers, or underscores"
        )
    return normalized.casefold()


def _source_kind(path: Path) -> str:
    name = path.name.casefold()
    if name.endswith(".zst"):
        return "zstandard-jsonl"
    if name.endswith((".jsonl.gz", ".ndjson.gz")):
        return "gzip-jsonl"
    if name.endswith((".jsonl", ".ndjson")):
        return "jsonl"
    if name.endswith(".json"):
        return "json"
    raise CommunityError(
        "Supported community sources are .json, .jsonl, .ndjson, "
        ".jsonl.gz, .ndjson.gz, and .zst"
    )


def _iter_json_values(path: Path) -> Iterator[RawRecord]:
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            payload = json.load(handle)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CommunityError(f"Invalid community JSON source: {exc}") from exc
    values = payload if isinstance(payload, list) else [payload]
    for source_line, value in enumerate(values, start=1):
        yield RawRecord(
            source_line=source_line,
            raw_text=_json(value),
            payload=value,
        )


def _iter_text_lines(
    text_reader: Iterable[str],
    scan: CommunityScan,
) -> Iterator[RawRecord]:
    for source_line, line in enumerate(text_reader, start=1):
        raw_text = line.rstrip("\r\n")
        if not raw_text.strip():
            scan.blank_lines += 1
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


def _iter_zstandard(path: Path, scan: CommunityScan) -> Iterator[RawRecord]:
    if arctic_shift.zstandard is None:
        raise CommunityError(
            "The zstandard package is required for community .zst sources"
        )
    try:
        with path.open("rb") as compressed:
            decompressor = arctic_shift.zstandard.ZstdDecompressor()
            with decompressor.stream_reader(
                compressed,
                read_across_frames=True,
            ) as binary_reader:
                with io.TextIOWrapper(
                    binary_reader,
                    encoding="utf-8-sig",
                    errors="strict",
                    newline="",
                ) as text_reader:
                    yield from _iter_text_lines(text_reader, scan)
    except UnicodeDecodeError as exc:
        raise CommunityError(
            f"Community .zst source is not UTF-8 near byte {exc.start}"
        ) from exc
    except arctic_shift.zstandard.ZstdError as exc:
        raise CommunityError(
            f"Invalid or truncated community .zst source: {path}"
        ) from exc


def iter_community_source(
    path: Path,
    scan: CommunityScan,
) -> Iterator[RawRecord]:
    """Stream one supported local community source without network access."""
    kind = _source_kind(path)
    if kind == "json":
        yield from _iter_json_values(path)
        return
    if kind == "zstandard-jsonl":
        yield from _iter_zstandard(path, scan)
        return
    opener = gzip.open if kind == "gzip-jsonl" else open
    try:
        with opener(path, "rt", encoding="utf-8-sig") as handle:
            yield from _iter_text_lines(handle, scan)
    except UnicodeDecodeError as exc:
        raise CommunityError(
            f"Community JSONL source is not UTF-8 near byte {exc.start}"
        ) from exc


def _wiki_path(value: str) -> str:
    parsed = urlsplit(value)
    path = parsed.path if parsed.scheme else value
    path = "/" + path.lstrip("/")
    return path.rstrip("/") or "/"


def _record_subreddit(source_type: str, payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    if source_type == "about":
        value = payload.get("display_name")
        if value is None:
            prefixed = payload.get("display_name_prefixed")
            value = (
                str(prefixed)[2:]
                if isinstance(prefixed, str)
                and prefixed.casefold().startswith("r/")
                else None
            )
        if value is None and isinstance(payload.get("url"), str):
            match = re.match(
                r"^/?r/([A-Za-z0-9_]{2,21})(?:/|$)",
                payload["url"],
                flags=re.IGNORECASE,
            )
            value = match.group(1) if match else None
    elif source_type in {"rules", "moderators"}:
        value = payload.get("subreddit")
    else:
        path = payload.get("path")
        if not isinstance(path, str):
            return None
        match = WIKI_PATH_RE.match(_wiki_path(path))
        value = match.group("subreddit") if match else None
    if not isinstance(value, str):
        return None
    try:
        return normalize_subreddit(value)
    except ValueError:
        return None


def _selected_records(
    records: Iterable[RawRecord],
    *,
    target: str,
    source_type: str,
    source_scope: str,
    scan: CommunityScan,
) -> Iterator[RawRecord]:
    for record in records:
        scan.records_scanned += 1
        if record.error is not None:
            scan.invalid_records += 1
            if source_scope == "scoped":
                yield record
            continue
        record_subreddit = _record_subreddit(source_type, record.payload)
        if record_subreddit is None:
            scan.invalid_records += 1
            if source_scope == "scoped":
                yield RawRecord(
                    source_line=record.source_line,
                    raw_text=record.raw_text,
                    payload=record.payload,
                    error=(
                        f"Record has no valid subreddit identity for "
                        f"{source_type}"
                    ),
                )
            continue
        if record_subreddit != target:
            scan.wrong_subreddit_records += 1
            if source_scope == "scoped":
                yield RawRecord(
                    source_line=record.source_line,
                    raw_text=record.raw_text,
                    payload=record.payload,
                    error=(
                        f"Record belongs to r/{record_subreddit}, "
                        f"expected r/{target}"
                    ),
                )
            continue
        scan.records_matched += 1
        yield record


def _batched(
    records: Iterable[RawRecord],
    *,
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


def _stable_job_id(
    source_path: Path,
    source_size: int,
    source_mtime_ns: int,
    subreddit: str,
    options: CommunityImportOptions,
    verified_sha256: str | None,
) -> str:
    identity = {
        "community_schema": COMMUNITY_SCHEMA_VERSION,
        "source_path": str(source_path),
        "source_size": source_size,
        "source_mtime_ns": source_mtime_ns,
        "source_sha256": verified_sha256,
        "subreddit": subreddit,
        "options": options.manifest(),
    }
    return hashlib.sha256(_json(identity).encode("utf-8")).hexdigest()[:32]


def _write_manifest(
    raw_root: Path,
    job_id: str,
    *,
    source_path: Path,
    source_kind: str,
    source_size: int,
    source_mtime_ns: int,
    verified_sha256: str | None,
    subreddit: str,
    options: CommunityImportOptions,
) -> Path:
    payload: dict[str, Any] = {
        "format": "keivotos-reddit-community-import-v1",
        "community_schema_version": COMMUNITY_SCHEMA_VERSION,
        "job_id": job_id,
        "subreddit": subreddit,
        "source": {
            "path": str(source_path),
            "kind": source_kind,
            "size": source_size,
            "mtime_ns": source_mtime_ns,
        },
        "options": options.manifest(),
    }
    if verified_sha256 is not None:
        payload["source"]["sha256"] = verified_sha256
    return _write_community_json(
        raw_root / job_id / "manifest.json",
        payload,
    )


def _write_community_json(path: Path, payload: dict[str, Any]) -> Path:
    try:
        return _write_json_create_or_verify(path, payload)
    except ArchiveError as exc:
        raise CommunityError(str(exc)) from exc


def _optional_text(value: Any) -> str | None:
    return None if value is None else str(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_bool(value: Any) -> int | None:
    return None if value is None else int(bool(value))


def _retrieved_utc(value: Any, *, required: bool = True) -> float | None:
    numeric = _optional_float(value)
    if numeric is not None:
        return numeric
    if isinstance(value, str):
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            parsed = None
        if parsed is not None:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.timestamp()
    if required:
        raise CommunityRecordError("retrieved_on must be a timestamp")
    return None


def _record_digest(payload: Any) -> str:
    return hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()


def _content_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _queue_subreddit_asset(
    connection: sqlite3.Connection,
    *,
    subreddit: str,
    role: str,
    value: Any,
    observed_at: str,
) -> None:
    if not isinstance(value, str):
        return
    url = value.strip()
    if not url.startswith(("https://", "http://")):
        return
    connection.execute(
        """
        INSERT INTO assets(
            owner_type, owner_id, role, url, desired_policy,
            first_seen_at, last_seen_at
        ) VALUES('subreddit', ?, ?, ?, 'original', ?, ?)
        ON CONFLICT(owner_type, owner_id, role, url) DO UPDATE SET
            desired_policy=excluded.desired_policy,
            last_seen_at=excluded.last_seen_at
        """,
        (subreddit, role, url, observed_at, observed_at),
    )


def _normalize_about(
    connection: sqlite3.Connection,
    *,
    source_record_id: int,
    subreddit: str,
    payload: dict[str, Any],
    observed_at: str,
) -> None:
    retrieved = _retrieved_utc(payload.get("retrieved_on"))
    display_name = payload.get("display_name")
    if not isinstance(display_name, str):
        raise CommunityRecordError("about record requires display_name")
    metadata_keys = (
        "_meta",
        "allow_discovery",
        "allow_galleries",
        "allow_images",
        "allow_polls",
        "allow_videos",
        "allowed_media_in_comments",
        "banner_background_color",
        "content_category",
        "emojis_enabled",
        "link_flair_enabled",
        "primary_color",
        "quarantine",
        "restrict_commenting",
        "restrict_posting",
        "show_media",
        "show_media_preview",
        "spoilers_enabled",
        "suggested_comment_sort",
    )
    metadata = {
        key: payload[key]
        for key in metadata_keys
        if key in payload
    }
    values = (
        subreddit,
        source_record_id,
        observed_at,
        retrieved,
        _optional_text(payload.get("id")),
        _optional_text(payload.get("name")),
        display_name,
        _optional_text(payload.get("title")),
        _optional_text(payload.get("public_description")),
        _optional_text(payload.get("description")),
        _optional_float(payload.get("created_utc")),
        _optional_int(payload.get("subscribers")),
        _optional_bool(payload.get("over18")),
        _optional_text(payload.get("subreddit_type")),
        _optional_text(payload.get("lang")),
        _optional_text(payload.get("submission_type")),
        _optional_bool(payload.get("wiki_enabled")),
        _optional_text(payload.get("icon_img")),
        _optional_text(payload.get("community_icon")),
        _optional_text(payload.get("header_img")),
        _optional_text(payload.get("banner_img")),
        _optional_text(payload.get("banner_background_image")),
        _optional_text(payload.get("mobile_banner_image")),
        _json(metadata),
    )
    connection.execute(
        """
        INSERT INTO subreddit_observations(
            subreddit, source_record_id, observed_at, retrieved_utc,
            reddit_id, fullname, display_name, title, public_description,
            description, created_utc, subscribers, over18, subreddit_type,
            language, submission_type, wiki_enabled, icon_url,
            community_icon_url, header_url, banner_url,
            banner_background_url, mobile_banner_url, metadata_json
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                 ?, ?, ?, ?, ?)
        """,
        values,
    )
    for value in (payload.get("icon_img"), payload.get("community_icon")):
        _queue_subreddit_asset(
            connection,
            subreddit=subreddit,
            role="subreddit-icon",
            value=value,
            observed_at=observed_at,
        )
    for value in (
        payload.get("header_img"),
        payload.get("banner_img"),
        payload.get("banner_background_image"),
        payload.get("mobile_banner_image"),
    ):
        _queue_subreddit_asset(
            connection,
            subreddit=subreddit,
            role="subreddit-banner",
            value=value,
            observed_at=observed_at,
        )


def _normalize_rules(
    connection: sqlite3.Connection,
    *,
    source_record_id: int,
    subreddit: str,
    payload: dict[str, Any],
    observed_at: str,
) -> None:
    retrieved = _retrieved_utc(payload.get("retrieved_on"))
    rules = payload.get("rules")
    if not isinstance(rules, list) or not all(
        isinstance(rule, dict) for rule in rules
    ):
        raise CommunityRecordError("rules record requires a rules object array")
    cursor = connection.execute(
        """
        INSERT INTO subreddit_rule_snapshots(
            subreddit, source_record_id, observed_at, retrieved_utc, rule_count
        ) VALUES(?, ?, ?, ?, ?)
        """,
        (subreddit, source_record_id, observed_at, retrieved, len(rules)),
    )
    snapshot_id = int(cursor.lastrowid)
    for position, rule in enumerate(rules):
        connection.execute(
            """
            INSERT INTO subreddit_rule_observations(
                snapshot_id, position, priority, short_name, description,
                kind, violation_reason, created_utc, content_sha256
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                position,
                _optional_int(rule.get("priority")),
                _optional_text(rule.get("short_name")),
                _optional_text(rule.get("description")),
                _optional_text(rule.get("kind")),
                _optional_text(rule.get("violation_reason")),
                _optional_float(rule.get("created_utc")),
                _record_digest(rule),
            ),
        )


def _normalize_wiki(
    connection: sqlite3.Connection,
    *,
    source_record_id: int,
    subreddit: str,
    payload: dict[str, Any],
    observed_at: str,
) -> None:
    retrieved = _retrieved_utc(payload.get("retrieved_on"))
    path_value = payload.get("path")
    content = payload.get("content")
    if not isinstance(path_value, str) or not isinstance(content, str):
        raise CommunityRecordError("wiki record requires string path and content")
    path = _wiki_path(path_value)
    if _record_subreddit("wiki", {"path": path}) != subreddit:
        raise CommunityRecordError("wiki path does not match the target subreddit")
    connection.execute(
        """
        INSERT INTO subreddit_wiki_observations(
            subreddit, source_record_id, observed_at, retrieved_utc, path,
            content, content_sha256, revision_author, revision_author_id,
            revision_date, revision_reason
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            subreddit,
            source_record_id,
            observed_at,
            retrieved,
            path,
            content,
            _content_digest(content),
            _optional_text(payload.get("revision_author")),
            _optional_text(payload.get("revision_author_id")),
            _optional_text(payload.get("revision_date")),
            _optional_text(payload.get("revision_reason")),
        ),
    )


def _normalize_moderators(
    connection: sqlite3.Connection,
    *,
    source_record_id: int,
    subreddit: str,
    payload: dict[str, Any],
    observed_at: str,
) -> None:
    if payload.get("format") != MODERATOR_BUNDLE_FORMAT:
        raise CommunityRecordError(
            f"moderator bundle format must be {MODERATOR_BUNDLE_FORMAT}"
        )
    retrieved = _retrieved_utc(payload.get("retrieved_on"))
    moderators = payload.get("moderators")
    if not isinstance(moderators, list) or not all(
        isinstance(moderator, dict) for moderator in moderators
    ):
        raise CommunityRecordError(
            "moderator bundle requires a moderators object array"
        )
    for moderator in moderators:
        if not isinstance(moderator.get("name"), str):
            raise CommunityRecordError("every moderator requires a name")
        permissions = moderator.get("permissions", [])
        if not isinstance(permissions, list) or not all(
            isinstance(permission, str) for permission in permissions
        ):
            raise CommunityRecordError(
                "moderator permissions must be a string array"
            )
    cursor = connection.execute(
        """
        INSERT INTO subreddit_moderator_snapshots(
            subreddit, source_record_id, observed_at, retrieved_utc,
            moderator_count, source_label
        ) VALUES(?, ?, ?, ?, ?, ?)
        """,
        (
            subreddit,
            source_record_id,
            observed_at,
            retrieved,
            len(moderators),
            _optional_text(payload.get("source_label")),
        ),
    )
    snapshot_id = int(cursor.lastrowid)
    for position, moderator in enumerate(moderators):
        connection.execute(
            """
            INSERT INTO subreddit_moderator_observations(
                snapshot_id, position, username, account_id,
                permissions_json, added_utc
            ) VALUES(?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                position,
                moderator["name"],
                _optional_text(moderator.get("id")),
                _json(moderator.get("permissions", [])),
                _optional_float(moderator.get("added_utc")),
            ),
        )


def _normalize_record(
    connection: sqlite3.Connection,
    *,
    source_type: str,
    source_record_id: int,
    subreddit: str,
    payload: Any,
    observed_at: str,
) -> None:
    if not isinstance(payload, dict):
        raise CommunityRecordError("selected record must be a JSON object")
    handlers = {
        "about": _normalize_about,
        "rules": _normalize_rules,
        "wiki": _normalize_wiki,
        "moderators": _normalize_moderators,
    }
    handlers[source_type](
        connection,
        source_record_id=source_record_id,
        subreddit=subreddit,
        payload=payload,
        observed_at=observed_at,
    )


def _set_job_counts(
    connection: sqlite3.Connection,
    *,
    job_id: str,
    scan: CommunityScan,
    last_source_line: int | None = None,
) -> None:
    imported = connection.execute(
        """
        SELECT COUNT(*)
        FROM community_source_records
        WHERE job_id=? AND error IS NULL
        """,
        (job_id,),
    ).fetchone()[0]
    schema_invalid = connection.execute(
        """
        SELECT COUNT(*)
        FROM community_source_records
        WHERE job_id=? AND error LIKE 'Invalid declared schema:%'
        """,
        (job_id,),
    ).fetchone()[0]
    assignments = """
        records_scanned=?, records_matched=?, records_imported=?,
        invalid_records=?, wrong_subreddit_records=?, blank_lines=?,
        updated_at=?
    """
    values: list[Any] = [
        scan.records_scanned,
        scan.records_matched,
        int(imported),
        scan.invalid_records + int(schema_invalid),
        scan.wrong_subreddit_records,
        scan.blank_lines,
        _now(),
    ]
    if last_source_line is not None:
        assignments += ", last_source_line=?"
        values.append(last_source_line)
    values.append(job_id)
    connection.execute(
        f"UPDATE community_import_jobs SET {assignments} WHERE id=?",
        values,
    )


def _process_chunk(
    connection: sqlite3.Connection,
    *,
    raw_root: Path,
    job_id: str,
    subreddit: str,
    source_type: str,
    records: list[RawRecord],
    scan: CommunityScan,
) -> None:
    try:
        chunk_id, chunk_path, digest = _write_chunk(raw_root, job_id, records)
    except ArchiveError as exc:
        raise CommunityError(str(exc)) from exc
    observed_at = _now()
    connection.execute(
        """
        INSERT OR IGNORE INTO community_chunks(
            id, job_id, first_source_line, last_source_line, record_count,
            raw_path, content_sha256, created_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            chunk_id,
            job_id,
            records[0].source_line,
            records[-1].source_line,
            len(records),
            str(chunk_path),
            digest,
            observed_at,
        ),
    )
    row = connection.execute(
        """
        SELECT job_id, first_source_line, last_source_line, record_count,
               raw_path, content_sha256
        FROM community_chunks WHERE id=?
        """,
        (chunk_id,),
    ).fetchone()
    expected = (
        job_id,
        records[0].source_line,
        records[-1].source_line,
        len(records),
        str(chunk_path),
        digest,
    )
    if row is None or tuple(row) != expected:
        raise CommunityError(f"Community chunk ledger conflict: {chunk_id}")

    for raw_index, record in enumerate(records):
        record_subreddit = _record_subreddit(source_type, record.payload)
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO community_source_records(
                job_id, source_line, raw_chunk_id, raw_index, record_sha256,
                source_type, subreddit, error, imported_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                record.source_line,
                chunk_id,
                raw_index,
                hashlib.sha256(record.raw_text.encode("utf-8")).hexdigest(),
                source_type,
                record_subreddit,
                record.error,
                observed_at,
            ),
        )
        source_record_id = int(cursor.lastrowid)
        if source_record_id == 0:
            existing = connection.execute(
                """
                SELECT id FROM community_source_records
                WHERE job_id=? AND source_line=?
                """,
                (job_id, record.source_line),
            ).fetchone()
            if existing is None:
                raise CommunityError("Community source-record ledger conflict")
            source_record_id = int(existing["id"])
        if record.error is not None:
            continue
        try:
            _normalize_record(
                connection,
                source_type=source_type,
                source_record_id=source_record_id,
                subreddit=subreddit,
                payload=record.payload,
                observed_at=observed_at,
            )
        except CommunityRecordError as exc:
            connection.execute(
                """
                UPDATE community_source_records
                SET error=?
                WHERE id=?
                """,
                (f"Invalid declared schema: {exc}", source_record_id),
            )

    _set_job_counts(
        connection,
        job_id=job_id,
        scan=scan,
        last_source_line=records[-1].source_line,
    )
    connection.commit()


def _job_coverage(
    connection: sqlite3.Connection,
    *,
    job_id: str,
) -> dict[str, Any]:
    job = connection.execute(
        "SELECT * FROM community_import_jobs WHERE id=?",
        (job_id,),
    ).fetchone()
    if job is None:
        raise CommunityError(f"Unknown community import job: {job_id}")

    def scalar(sql: str) -> int:
        return int(connection.execute(sql, (job_id,)).fetchone()[0])

    about_count = scalar(
        """
        SELECT COUNT(*) FROM subreddit_observations o
        JOIN community_source_records r ON r.id=o.source_record_id
        WHERE r.job_id=?
        """
    )
    rule_snapshot_count = scalar(
        """
        SELECT COUNT(*) FROM subreddit_rule_snapshots s
        JOIN community_source_records r ON r.id=s.source_record_id
        WHERE r.job_id=?
        """
    )
    rule_count = scalar(
        """
        SELECT COUNT(*) FROM subreddit_rule_observations o
        JOIN subreddit_rule_snapshots s ON s.id=o.snapshot_id
        JOIN community_source_records r ON r.id=s.source_record_id
        WHERE r.job_id=?
        """
    )
    wiki_count = scalar(
        """
        SELECT COUNT(*) FROM subreddit_wiki_observations o
        JOIN community_source_records r ON r.id=o.source_record_id
        WHERE r.job_id=?
        """
    )
    distinct_wiki_pages = scalar(
        """
        SELECT COUNT(DISTINCT o.path) FROM subreddit_wiki_observations o
        JOIN community_source_records r ON r.id=o.source_record_id
        WHERE r.job_id=?
        """
    )
    moderator_snapshot_count = scalar(
        """
        SELECT COUNT(*) FROM subreddit_moderator_snapshots s
        JOIN community_source_records r ON r.id=s.source_record_id
        WHERE r.job_id=?
        """
    )
    moderator_count = scalar(
        """
        SELECT COUNT(*) FROM subreddit_moderator_observations o
        JOIN subreddit_moderator_snapshots s ON s.id=o.snapshot_id
        JOIN community_source_records r ON r.id=s.source_record_id
        WHERE r.job_id=?
        """
    )
    retrieved_rows = connection.execute(
        """
        SELECT retrieved_utc FROM subreddit_observations o
        JOIN community_source_records r ON r.id=o.source_record_id
        WHERE r.job_id=?
        UNION ALL
        SELECT retrieved_utc FROM subreddit_rule_snapshots s
        JOIN community_source_records r ON r.id=s.source_record_id
        WHERE r.job_id=?
        UNION ALL
        SELECT retrieved_utc FROM subreddit_wiki_observations o
        JOIN community_source_records r ON r.id=o.source_record_id
        WHERE r.job_id=?
        UNION ALL
        SELECT retrieved_utc FROM subreddit_moderator_snapshots s
        JOIN community_source_records r ON r.id=s.source_record_id
        WHERE r.job_id=?
        """,
        (job_id, job_id, job_id, job_id),
    ).fetchall()
    retrieved = [
        float(row[0])
        for row in retrieved_rows
        if row[0] is not None
    ]
    records_preserved = scalar(
        "SELECT COUNT(*) FROM community_source_records WHERE job_id=?"
    )
    records_imported = int(job["records_imported"])
    return {
        "format": "keivotos-reddit-community-coverage-v1",
        "community_schema_version": COMMUNITY_SCHEMA_VERSION,
        "job_id": job_id,
        "subreddit": job["subreddit"],
        "source": {
            "path": job["source_path"],
            "kind": job["source_kind"],
            "type": job["source_type"],
            "scope": job["source_scope"],
            "size": int(job["source_size"]),
            "mtime_ns": int(job["source_mtime_ns"]),
            "sha256": job["source_sha256"],
        },
        "coverage": {
            "records_scanned": int(job["records_scanned"]),
            "records_matched": int(job["records_matched"]),
            "records_preserved": records_preserved,
            "records_imported": records_imported,
            "invalid_records": int(job["invalid_records"]),
            "wrong_subreddit_records": int(job["wrong_subreddit_records"]),
            "blank_lines": int(job["blank_lines"]),
            "about_observations": about_count,
            "rule_snapshots": rule_snapshot_count,
            "rules": rule_count,
            "wiki_revisions": wiki_count,
            "distinct_wiki_pages": distinct_wiki_pages,
            "moderator_snapshots": moderator_snapshot_count,
            "moderators": moderator_count,
            "earliest_retrieved_utc": min(retrieved) if retrieved else None,
            "latest_retrieved_utc": max(retrieved) if retrieved else None,
            "missing_requested_domains": (
                [job["source_type"]] if records_imported == 0 else []
            ),
        },
    }


def _summary(
    connection: sqlite3.Connection,
    *,
    database_path: Path,
    raw_root: Path,
    job_id: str,
) -> CommunityImportSummary:
    job = connection.execute(
        "SELECT * FROM community_import_jobs WHERE id=?",
        (job_id,),
    ).fetchone()
    if job is None:
        raise CommunityError(f"Unknown community import job: {job_id}")
    records_preserved = connection.execute(
        "SELECT COUNT(*) FROM community_source_records WHERE job_id=?",
        (job_id,),
    ).fetchone()[0]
    job_root = raw_root / job_id
    return CommunityImportSummary(
        job_id=job_id,
        status=job["status"],
        subreddit=job["subreddit"],
        source_type=job["source_type"],
        source_path=job["source_path"],
        database_path=str(database_path),
        raw_directory=str(job_root),
        coverage_path=str(job_root / "coverage.json"),
        records_scanned=int(job["records_scanned"]),
        records_matched=int(job["records_matched"]),
        records_preserved=int(records_preserved),
        records_imported=int(job["records_imported"]),
        invalid_records=int(job["invalid_records"]),
        wrong_subreddit_records=int(job["wrong_subreddit_records"]),
        blank_lines=int(job["blank_lines"]),
        last_source_line=int(job["last_source_line"]),
        errors=int(job["errors"]),
    )


def import_community_source(
    database_path: Path,
    source_path: Path,
    subreddit: str,
    options: CommunityImportOptions,
    *,
    resume: bool = False,
    coverage_path: Path | None = None,
) -> CommunityImportSummary:
    """Import one explicit local community domain into versioned observations."""
    database_path = Path(database_path).expanduser().resolve(strict=False)
    source_path = Path(source_path).expanduser().resolve(strict=True)
    if not source_path.is_file():
        raise CommunityError(f"Community source is not a file: {source_path}")
    subreddit = normalize_subreddit(subreddit)
    source_kind = _source_kind(source_path)
    stat_result = source_path.stat()
    verified_sha256 = (
        verify_sha256(source_path, options.expected_sha256)
        if options.expected_sha256 is not None
        else None
    )

    # Decode the first record before creating archive state. Invalid JSONL
    # records are evidence and may be preserved; codec/JSON-container failures
    # fail here.
    probe_scan = CommunityScan()
    probe = iter_community_source(source_path, probe_scan)
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
        subreddit,
        options,
        verified_sha256,
    )
    raw_root = database_path.parent / "archives" / "community"
    _write_manifest(
        raw_root,
        job_id,
        source_path=source_path,
        source_kind=source_kind,
        source_size=int(stat_result.st_size),
        source_mtime_ns=int(stat_result.st_mtime_ns),
        verified_sha256=verified_sha256,
        subreddit=subreddit,
        options=options,
    )

    with open_archive(database_path) as connection:
        existing = connection.execute(
            "SELECT * FROM community_import_jobs WHERE id=?",
            (job_id,),
        ).fetchone()
        if existing is not None and not resume:
            raise CommunityResumeRequiredError(
                f"Community job {job_id} exists; pass --resume to reuse it"
            )
        if existing is not None and existing["status"] == "complete":
            default_coverage = raw_root / job_id / "coverage.json"
            payload = _job_coverage(
                connection,
                job_id=job_id,
            )
            _write_community_json(default_coverage, payload)
            if coverage_path is not None:
                _write_community_json(coverage_path, payload)
            return _summary(
                connection,
                database_path=database_path,
                raw_root=raw_root,
                job_id=job_id,
            )

        now = _now()
        if existing is None:
            connection.execute(
                """
                INSERT INTO community_import_jobs(
                    id, subreddit, source_type, source_scope, source_path,
                    source_kind, source_size, source_mtime_ns, source_sha256,
                    status, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, 'running', ?, ?)
                """,
                (
                    job_id,
                    subreddit,
                    options.source_type,
                    options.source_scope,
                    str(source_path),
                    source_kind,
                    int(stat_result.st_size),
                    int(stat_result.st_mtime_ns),
                    verified_sha256,
                    now,
                    now,
                ),
            )
            last_source_line = 0
        else:
            last_source_line = int(existing["last_source_line"])
            connection.execute(
                """
                UPDATE community_import_jobs
                SET status='running', updated_at=?
                WHERE id=?
                """,
                (now, job_id),
            )
        connection.commit()

        scan = CommunityScan()
        try:
            selected = _selected_records(
                iter_community_source(source_path, scan),
                target=subreddit,
                source_type=options.source_type,
                source_scope=options.source_scope,
                scan=scan,
            )
            for chunk in _batched(
                selected,
                size=options.chunk_size,
                after_line=last_source_line,
            ):
                _process_chunk(
                    connection,
                    raw_root=raw_root,
                    job_id=job_id,
                    subreddit=subreddit,
                    source_type=options.source_type,
                    records=chunk,
                    scan=scan,
                )
            _set_job_counts(connection, job_id=job_id, scan=scan)
            completed_at = _now()
            connection.execute(
                """
                UPDATE community_import_jobs
                SET status='complete', updated_at=?, completed_at=?
                WHERE id=?
                """,
                (completed_at, completed_at, job_id),
            )
            connection.commit()
            payload = _job_coverage(
                connection,
                job_id=job_id,
            )
            default_coverage = raw_root / job_id / "coverage.json"
            _write_community_json(default_coverage, payload)
            if coverage_path is not None:
                requested = Path(coverage_path).expanduser().resolve(strict=False)
                if requested != default_coverage.resolve(strict=False):
                    _write_community_json(requested, payload)
        except Exception as exc:
            connection.rollback()
            failed_at = _now()
            connection.execute(
                """
                UPDATE community_import_jobs
                SET status='failed', errors=errors + 1, updated_at=?
                WHERE id=?
                """,
                (failed_at, job_id),
            )
            connection.execute(
                """
                INSERT INTO community_import_errors(
                    job_id, message, created_at
                ) VALUES(?, ?, ?)
                """,
                (job_id, str(exc), failed_at),
            )
            connection.commit()
            raise
        return _summary(
            connection,
            database_path=database_path,
            raw_root=raw_root,
            job_id=job_id,
        )
