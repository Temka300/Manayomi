"""Streaming readers and integrity helpers for local Arctic Shift dumps."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
from typing import Any, Iterator

try:
    import zstandard
except ImportError:  # pragma: no cover - exercised only in a broken environment
    zstandard = None


SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class ArcticShiftError(RuntimeError):
    """Raised when a local Arctic Shift source cannot be read safely."""


@dataclass(frozen=True)
class ArcticShiftRecord:
    """One physical JSONL record from a decompressed Arctic Shift stream."""

    source_line: int
    raw_text: str
    payload: Any | None
    error: str | None = None


@dataclass
class ArcticShiftCoverage:
    """Counters that explain exactly what a filtered dump import observed."""

    source_path: str
    source_size: int
    source_sha256: str | None = None
    source_records_scanned: int = 0
    blank_lines: int = 0
    invalid_records: int = 0
    records_without_created_utc: int = 0
    records_in_date_range: int = 0
    records_selected: int = 0
    earliest_created_utc: float | None = None
    latest_created_utc: float | None = None
    kinds_scanned: dict[str, int] = field(default_factory=dict)
    kinds_selected: dict[str, int] = field(default_factory=dict)

    def note_kind(self, kind: str, *, selected: bool = False) -> None:
        target = self.kinds_selected if selected else self.kinds_scanned
        target[kind] = target.get(kind, 0) + 1

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_utc_boundary(value: str) -> float:
    """Parse a YYYY-MM-DD boundary as midnight UTC."""
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValueError(f"Invalid UTC date {value!r}; expected YYYY-MM-DD") from exc
    return parsed.timestamp()


def normalize_sha256(value: str) -> str:
    """Validate and normalize a user-provided SHA-256 digest."""
    normalized = value.strip().lower()
    if not SHA256_RE.fullmatch(normalized):
        raise ValueError("expected SHA-256 must contain exactly 64 hexadecimal digits")
    return normalized


def sha256_file(path: Path, *, block_size: int = 8 * 1024 * 1024) -> str:
    """Hash a source in bounded blocks without loading it into memory."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while block := handle.read(block_size):
            digest.update(block)
    return digest.hexdigest()


def verify_sha256(path: Path, expected: str) -> str:
    """Verify a local dump before any archive database is created."""
    expected = normalize_sha256(expected)
    actual = sha256_file(path)
    if actual != expected:
        raise ArcticShiftError(
            f"SHA-256 mismatch for {Path(path)}: expected {expected}, got {actual}"
        )
    return actual


def _record_kind(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "unknown"
    outer_kind = str(payload.get("kind") or "").lower()
    if outer_kind == "t1":
        return "comment"
    if outer_kind == "t3":
        return "post"
    if "link_id" in payload and ("body" in payload or "parent_id" in payload):
        return "comment"
    if "id" in payload and any(
        key in payload for key in ("title", "selftext", "num_comments", "is_self")
    ):
        return "post"
    return "unknown"


def _payload_data(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    outer_kind = str(payload.get("kind") or "").lower()
    data = payload.get("data")
    if outer_kind in {"t1", "t3"} and isinstance(data, dict):
        return data
    return payload


def _created_utc(payload: Any) -> float | None:
    payload = _payload_data(payload)
    if not isinstance(payload, dict):
        return None
    value = payload.get("created_utc")
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def iter_zst_records(
    path: Path,
    *,
    coverage: ArcticShiftCoverage,
    after_utc: float | None = None,
    before_utc: float | None = None,
) -> Iterator[ArcticShiftRecord]:
    """Stream newline-delimited JSON from one standard ``.zst`` dump.

    ``after_utc`` is inclusive and ``before_utc`` is exclusive. Records without
    a usable timestamp are retained only when no date boundary was requested.
    """
    if zstandard is None:
        raise ArcticShiftError(
            "The zstandard package is required for Arctic Shift .zst sources"
        )
    if after_utc is not None and before_utc is not None and after_utc >= before_utc:
        raise ValueError("--after must be earlier than --before")

    path = Path(path)
    try:
        with path.open("rb") as compressed:
            decompressor = zstandard.ZstdDecompressor()
            with decompressor.stream_reader(
                compressed, read_across_frames=True
            ) as binary_reader:
                with io.TextIOWrapper(
                    binary_reader,
                    encoding="utf-8-sig",
                    errors="strict",
                    newline="",
                ) as text_reader:
                    for source_line, line in enumerate(text_reader, start=1):
                        raw_text = line.rstrip("\r\n")
                        if not raw_text.strip():
                            coverage.blank_lines += 1
                            continue

                        coverage.source_records_scanned += 1
                        try:
                            payload = json.loads(raw_text)
                        except json.JSONDecodeError as exc:
                            coverage.invalid_records += 1
                            coverage.note_kind("invalid")
                            if after_utc is None and before_utc is None:
                                coverage.records_in_date_range += 1
                                yield ArcticShiftRecord(
                                    source_line=source_line,
                                    raw_text=raw_text,
                                    payload=None,
                                    error=f"Invalid JSON: {exc.msg}",
                                )
                            continue

                        kind = _record_kind(payload)
                        coverage.note_kind(kind)
                        created_utc = _created_utc(payload)
                        if created_utc is None:
                            coverage.records_without_created_utc += 1
                            if after_utc is not None or before_utc is not None:
                                continue
                        else:
                            if (
                                coverage.earliest_created_utc is None
                                or created_utc < coverage.earliest_created_utc
                            ):
                                coverage.earliest_created_utc = created_utc
                            if (
                                coverage.latest_created_utc is None
                                or created_utc > coverage.latest_created_utc
                            ):
                                coverage.latest_created_utc = created_utc
                            if after_utc is not None and created_utc < after_utc:
                                continue
                            if before_utc is not None and created_utc >= before_utc:
                                continue

                        coverage.records_in_date_range += 1
                        yield ArcticShiftRecord(
                            source_line=source_line,
                            raw_text=raw_text,
                            payload=payload,
                        )
    except UnicodeDecodeError as exc:
        raise ArcticShiftError(
            f"Arctic Shift source is not valid UTF-8 near byte {exc.start}"
        ) from exc
    except zstandard.ZstdError as exc:
        raise ArcticShiftError(f"Invalid or truncated zstandard source: {path}") from exc
