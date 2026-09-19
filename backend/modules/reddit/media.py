"""Bounded acquisition of already-queued Reddit-hosted media assets."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from email.message import Message
import hashlib
import html
import ipaddress
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
from typing import Any, Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

from mediafire_dl.http import HttpClient as MediafireHttpClient
from mediafire_dl.mediafire import MediafireClient
from PIL import Image, UnidentifiedImageError

from modules.reddit.archive import open_archive
from modules.reddit.links import is_mediafire_host, link_urls
from services import yt_dlp as yt_dlp_service
from thumbnails import resolve_ffmpeg_executable


DEFAULT_MAX_FILES = 100
DEFAULT_MAX_FILE_BYTES = 2 * 1024 * 1024 * 1024
DEFAULT_MAX_RUN_BYTES = 10 * 1024 * 1024 * 1024
DEFAULT_MIN_FREE_BYTES = 5 * 1024 * 1024 * 1024
DEFAULT_TIMEOUT = 30.0
DEFAULT_PROCESS_TIMEOUT = 3600.0
DEFAULT_RETRIES = 3
MEDIA_USER_AGENT = "desktop:keivotos-reddit-media:v0.1 (local archive)"

IMAGE_ROLES = {
    "avatar",
    "embedded-image",
    "flair-emoji",
    "gallery-original",
    "image-original",
    "preview-resolution",
    "preview-source",
    "subreddit-banner",
    "subreddit-icon",
    "thumbnail",
}
VIDEO_ROLES = {
    "embedded-video",
    "video-dash",
    "video-file",
    "video-hls",
    "video-scrubber",
}
LINKED_FILE_ROLES = {"linked-file"}
GALLERY_DL_IMAGE_HOSTS = {"i.redd.it", "preview.redd.it"}
EXACT_REDDIT_IMAGE_HOSTS = {
    "external-preview.redd.it",
    "i.redd.it",
    "preview.redd.it",
    "www.redditstatic.com",
}
REDDIT_IMAGE_HOST_SUFFIXES = (".redditmedia.com", ".redditstatic.com")
VIDEO_HOSTS = {"v.redd.it"}
SAFE_IMAGE_EXTENSIONS = {
    ".avif",
    ".gif",
    ".jpeg",
    ".jpg",
    ".png",
    ".webp",
}
SAFE_VIDEO_EXTENSIONS = {".m4v", ".mkv", ".mov", ".mp4", ".webm"}
SAFE_STAGE_SUFFIX = re.compile(r"^\.[A-Za-z0-9][A-Za-z0-9._+-]{0,15}$")


class MediaError(RuntimeError):
    """Base error for Reddit media planning and acquisition."""


class MediaConfirmationError(MediaError):
    """Raised when a download is not confirmed against its current plan."""


class MediaPolicyError(MediaError):
    """Raised when a queued URL is outside the approved Slice 2 boundary."""


@dataclass(frozen=True)
class MediaLimits:
    max_files: int = DEFAULT_MAX_FILES
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES
    max_run_bytes: int = DEFAULT_MAX_RUN_BYTES
    min_free_bytes: int = DEFAULT_MIN_FREE_BYTES

    def __post_init__(self) -> None:
        if self.max_files <= 0:
            raise ValueError("max_files must be positive")
        if self.max_file_bytes <= 0:
            raise ValueError("max_file_bytes must be positive")
        if self.max_run_bytes <= 0:
            raise ValueError("max_run_bytes must be positive")
        if self.min_free_bytes < 0:
            raise ValueError("min_free_bytes cannot be negative")


@dataclass(frozen=True)
class MediaCandidate:
    asset_id: int
    owner_type: str
    owner_id: str
    role: str
    url: str
    engine: str
    status: str

    def selection_identity(self) -> str:
        return (
            f"{self.asset_id}\0{self.owner_type}\0{self.owner_id}\0"
            f"{self.role}\0{self.url}\0{self.engine}"
        )


@dataclass(frozen=True)
class MediaPlan:
    database_path: str
    destination: str
    limits: MediaLimits
    queued_assets: int
    already_downloaded: int
    failed_not_selected: int
    rejected_external: int
    rejected_policy: int
    eligible_assets: int
    selected_assets: int
    selection_sha256: str
    available_bytes: int
    required_start_bytes: int
    can_start: bool
    candidates: tuple[MediaCandidate, ...]

    def summary(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("candidates")
        by_engine: dict[str, int] = {}
        by_host: dict[str, int] = {}
        by_role: dict[str, int] = {}
        preview = []
        for candidate in self.candidates:
            host = (urlsplit(candidate.url).hostname or "").casefold()
            by_engine[candidate.engine] = by_engine.get(candidate.engine, 0) + 1
            by_host[host] = by_host.get(host, 0) + 1
            by_role[candidate.role] = by_role.get(candidate.role, 0) + 1
            if len(preview) < 25:
                preview.append(
                    {
                        "asset_id": candidate.asset_id,
                        "owner_type": candidate.owner_type,
                        "owner_id": candidate.owner_id,
                        "role": candidate.role,
                        "host": host,
                        "engine": candidate.engine,
                    }
                )
        payload["selected_by_engine"] = dict(sorted(by_engine.items()))
        payload["selected_by_host"] = dict(sorted(by_host.items()))
        payload["selected_by_role"] = dict(sorted(by_role.items()))
        payload["selection_preview"] = preview
        payload["selection_preview_truncated"] = len(preview) < self.selected_assets
        payload["unknown_size_assets"] = self.selected_assets
        payload["confirmation"] = {
            "confirm_assets": self.selected_assets,
            "selection_sha256": self.selection_sha256,
        }
        return payload


@dataclass(frozen=True)
class EngineResult:
    path: Path
    final_url: str
    content_type: str | None = None
    suggested_name: str | None = None


@dataclass(frozen=True)
class StoredObject:
    sha256: str
    path: Path
    relative_path: str
    byte_size: int
    content_type: str | None
    deduplicated: bool


@dataclass
class DownloadSummary:
    planned: int
    attempted: int = 0
    completed: int = 0
    failed: int = 0
    deduplicated: int = 0
    bytes_acquired: int = 0
    new_object_bytes: int = 0
    published_files: int = 0
    publication_failed: int = 0
    stop_reason: str = "complete"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


GalleryRunner = Callable[
    [MediaCandidate, Path, int, float, float, int], EngineResult
]
VideoRunner = Callable[
    [MediaCandidate, Path, int, float, float, int], EngineResult
]
HttpRunner = Callable[
    [MediaCandidate, Path, int, float, int], EngineResult
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _nearest_existing_parent(path: Path) -> Path:
    candidate = Path(path).expanduser().resolve(strict=False)
    while not candidate.exists():
        parent = candidate.parent
        if parent == candidate:
            raise MediaError(f"No existing parent is available for {path}")
        candidate = parent
    return candidate


def _disk_free(path: Path) -> int:
    return int(shutil.disk_usage(_nearest_existing_parent(path)).free)


def _is_reddit_image_host(host: str) -> bool:
    return host in EXACT_REDDIT_IMAGE_HOSTS or host.endswith(
        REDDIT_IMAGE_HOST_SUFFIXES
    )


def classify_asset(role: str, url: str) -> tuple[str | None, str | None]:
    """Return the approved engine or a stable rejection reason."""
    if role == "external":
        return None, "external"
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").casefold()
        port = parsed.port
    except ValueError:
        return None, "invalid-url"
    if (
        parsed.scheme.casefold() != "https"
        or not host
        or port not in {None, 443}
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None, "non-https-or-custom-port"
    if role in LINKED_FILE_ROLES:
        if is_mediafire_host(host):
            if parsed.path.casefold().startswith("/file/"):
                return "mediafire", None
            return None, "unsupported-linked-folder-or-page"
        return "http-file", None
    if role in IMAGE_ROLES and _is_reddit_image_host(host):
        return (
            "gallery-dl" if host in GALLERY_DL_IMAGE_HOSTS else "http",
            None,
        )
    if role in VIDEO_ROLES and host in VIDEO_HOSTS:
        return "yt-dlp", None
    return None, "unsupported-role-or-host"


def _network_url(candidate: MediaCandidate) -> str:
    """Undo Reddit's legacy JSON HTML escaping, then re-check the boundary."""
    url = html.unescape(candidate.url)
    engine, rejection = classify_asset(candidate.role, url)
    if engine != candidate.engine:
        raise MediaPolicyError(
            "Decoded media URL is outside the approved policy "
            f"({rejection or 'engine mismatch'})"
        )
    return url


def _read_assets(
    database_path: Path,
    *,
    scope_type: str | None = None,
    scope_id: str | None = None,
) -> list[sqlite3.Row]:
    database_path = Path(database_path).expanduser().resolve(strict=True)
    if not database_path.is_file():
        raise MediaError(f"Reddit archive database is not a file: {database_path}")
    uri = database_path.as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        if (scope_type is None) != (scope_id is None):
            raise ValueError("scope_type and scope_id must be supplied together")
        if scope_type is None:
            where = ""
            params: tuple[str, ...] = ()
        elif scope_type == "post":
            where = """
            WHERE (owner_type='post' AND owner_id=?)
               OR (owner_type='comment' AND owner_id IN (
                    SELECT id FROM comments WHERE post_id=?
               ))
            """
            params = (scope_id or "", scope_id or "")
        elif scope_type == "subreddit":
            where = "WHERE owner_type='subreddit' AND owner_id=? COLLATE NOCASE"
            params = (scope_id or "",)
        else:
            raise ValueError("scope_type must be 'post', 'subreddit', or omitted")
        return connection.execute(
            f"""
            SELECT id, owner_type, owner_id, role, url, status, local_path
            FROM assets
            {where}
            ORDER BY id
            """,
            params,
        ).fetchall()
    except sqlite3.OperationalError as exc:
        raise MediaError("Reddit archive has no Slice 0 asset queue") from exc
    finally:
        connection.close()


def ensure_linked_assets(
    database_path: Path,
    *,
    scope_type: str,
    scope_id: str,
) -> int:
    """Queue stored outbound HTTPS links without opening any network URL."""
    if scope_type != "post":
        return 0
    inserted = 0
    with open_archive(Path(database_path)) as connection:
        records = [
            *connection.execute(
                """
                SELECT 'post' AS owner_type, id AS owner_id, url AS primary_url,
                       selftext AS body, latest_observed_at AS observed_at
                FROM posts WHERE id=?
                """,
                (scope_id,),
            ).fetchall(),
            *connection.execute(
                """
                SELECT 'comment' AS owner_type, id AS owner_id,
                       NULL AS primary_url, body, latest_observed_at AS observed_at
                FROM comments WHERE post_id=?
                """,
                (scope_id,),
            ).fetchall(),
        ]
        for record in records:
            existing = {
                str(row["url"])
                for row in connection.execute(
                    "SELECT url FROM assets WHERE owner_type=? AND owner_id=?",
                    (record["owner_type"], record["owner_id"]),
                ).fetchall()
            }
            for url in link_urls(
                record["primary_url"],
                record["body"],
                excluding=existing,
            ):
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO assets(
                        owner_type, owner_id, role, url, desired_policy,
                        first_seen_at, last_seen_at
                    ) VALUES(?, ?, 'linked-file', ?, 'linked-file', ?, ?)
                    """,
                    (
                        record["owner_type"],
                        record["owner_id"],
                        url,
                        record["observed_at"],
                        record["observed_at"],
                    ),
                )
                inserted += max(int(cursor.rowcount), 0)
        connection.commit()
    return inserted


def build_media_plan(
    database_path: Path,
    destination: Path,
    limits: MediaLimits,
    *,
    roles: Iterable[str] | None = None,
    retry_failed: bool = False,
    scope_type: str | None = None,
    scope_id: str | None = None,
) -> MediaPlan:
    """Build a deterministic queue plan without opening any network URL."""
    database_path = Path(database_path).expanduser().resolve(strict=True)
    destination = Path(destination).expanduser().resolve(strict=False)
    selected_roles = {value for value in (roles or ()) if value}
    rows = _read_assets(
        database_path,
        scope_type=scope_type,
        scope_id=scope_id,
    )
    counts = {
        "queued": 0,
        "downloaded": 0,
        "failed": 0,
        "external": 0,
        "policy": 0,
    }
    eligible: list[MediaCandidate] = []

    for row in rows:
        if selected_roles and row["role"] not in selected_roles:
            continue
        status = str(row["status"] or "queued")
        if status == "downloaded" and row["local_path"]:
            counts["downloaded"] += 1
            continue
        if status == "failed" and not retry_failed:
            counts["failed"] += 1
            continue
        counts["queued"] += 1
        engine, reason = classify_asset(row["role"], row["url"])
        if engine is None:
            if reason == "external":
                counts["external"] += 1
            else:
                counts["policy"] += 1
            continue
        eligible.append(
            MediaCandidate(
                asset_id=int(row["id"]),
                owner_type=row["owner_type"],
                owner_id=row["owner_id"],
                role=row["role"],
                url=row["url"],
                engine=engine,
                status=status,
            )
        )

    candidates = tuple(eligible[: limits.max_files])
    digest = hashlib.sha256()
    for candidate in candidates:
        digest.update(candidate.selection_identity().encode("utf-8"))
        digest.update(b"\n")
    available = _disk_free(destination)
    required_start = limits.min_free_bytes
    if candidates:
        required_start += min(limits.max_file_bytes, limits.max_run_bytes)
    return MediaPlan(
        database_path=str(database_path),
        destination=str(destination),
        limits=limits,
        queued_assets=counts["queued"],
        already_downloaded=counts["downloaded"],
        failed_not_selected=counts["failed"],
        rejected_external=counts["external"],
        rejected_policy=counts["policy"],
        eligible_assets=len(eligible),
        selected_assets=len(candidates),
        selection_sha256=digest.hexdigest(),
        available_bytes=available,
        required_start_bytes=required_start,
        can_start=not candidates or available >= required_start,
        candidates=candidates,
    )


def _run_process(
    command: list[str],
    *,
    timeout: float,
    label: str,
) -> None:
    creationflags = (
        getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if sys.platform == "win32"
        else 0
    )
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=creationflags,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MediaError(f"{label} could not complete: {exc}") from exc
    if result.returncode:
        output = (result.stdout or "").strip()
        if len(output) > 4000:
            output = output[-4000:]
        raise MediaError(
            f"{label} failed with exit code {result.returncode}"
            + (f": {output}" if output else "")
        )


def _gallery_dl_command() -> list[str]:
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve().parent / "gallery-dl.exe"
        if not executable.is_file():
            raise MediaError(
                f"Portable gallery-dl.exe is missing beside Keivotos.exe: {executable}"
            )
        return [str(executable)]
    executable = shutil.which("gallery-dl")
    return [executable] if executable else [sys.executable, "-m", "gallery_dl"]


def _yt_dlp_command() -> list[str]:
    return yt_dlp_service.resolve_command(error_type=MediaError)


def _finished_stage_file(stage: Path, asset_id: int) -> Path | None:
    prefix = f"asset-{asset_id}"
    values = [
        path
        for path in stage.iterdir()
        if path.is_file()
        and path.name.startswith(prefix + ".")
        and not path.name.endswith((".part", ".ytdl"))
        and ".f" not in path.stem[len(prefix) :]
    ]
    if len(values) > 1:
        raise MediaError(f"Downloader produced multiple final files for asset {asset_id}")
    return values[0] if values else None


def run_gallery_dl(
    candidate: MediaCandidate,
    stage: Path,
    max_bytes: int,
    timeout: float,
    process_timeout: float,
    retries: int,
) -> EngineResult:
    """Download one direct Reddit image through the existing gallery-dl engine."""
    stage.mkdir(parents=True, exist_ok=True)
    if existing := _finished_stage_file(stage, candidate.asset_id):
        return EngineResult(existing, candidate.url)
    url = _network_url(candidate)
    command = [
        *_gallery_dl_command(),
        "--config-ignore",
        "--no-input",
        "--no-colors",
        "--no-mtime",
        "--directory",
        str(stage),
        "--filename",
        f"asset-{candidate.asset_id}.{{extension}}",
        "--filesize-max",
        str(max_bytes),
        "--retries",
        str(retries),
        "--http-timeout",
        str(timeout),
        "--user-agent",
        MEDIA_USER_AGENT,
        url,
    ]
    _run_process(command, timeout=process_timeout, label="gallery-dl")
    result = _finished_stage_file(stage, candidate.asset_id)
    if result is None:
        raise MediaError(
            "gallery-dl completed without a file; the URL may be unavailable "
            "or larger than the configured cap"
        )
    return EngineResult(result, url)


def run_yt_dlp(
    candidate: MediaCandidate,
    stage: Path,
    max_bytes: int,
    timeout: float,
    process_timeout: float,
    retries: int,
) -> EngineResult:
    """Download one stored Reddit video URL through yt-dlp and FFmpeg."""
    stage.mkdir(parents=True, exist_ok=True)
    if existing := _finished_stage_file(stage, candidate.asset_id):
        return EngineResult(existing, candidate.url)
    url = _network_url(candidate)
    command = [
        *_yt_dlp_command(),
        *yt_dlp_service.common_download_args(
            retries=retries,
            socket_timeout=timeout,
            ffmpeg_executable=resolve_ffmpeg_executable(),
        ),
        "--no-progress",
        "--max-filesize",
        str(max_bytes),
        "--output",
        str(stage / f"asset-{candidate.asset_id}.%(ext)s"),
        url,
    ]
    yt_dlp_service.run_process(
        command,
        timeout=process_timeout,
        label="yt-dlp",
        error_type=MediaError,
    )
    result = _finished_stage_file(stage, candidate.asset_id)
    if result is None:
        raise MediaError(
            "yt-dlp completed without a merged file; inspect retained partials"
        )
    return EngineResult(result, url)


def _assert_safe_reddit_image_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").casefold()
        port = parsed.port
    except ValueError as exc:
        raise MediaPolicyError(f"Invalid Reddit image URL: {url}") from exc
    if (
        parsed.scheme.casefold() != "https"
        or not _is_reddit_image_host(host)
        or port not in {None, 443}
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise MediaPolicyError(f"HTTP fallback rejected non-Reddit URL: {url}")

    try:
        addresses = {
            result[4][0]
            for result in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        }
    except OSError as exc:
        raise MediaError(f"Could not resolve approved Reddit host {host}: {exc}") from exc
    if not addresses:
        raise MediaError(f"Approved Reddit host did not resolve: {host}")
    for value in addresses:
        address = ipaddress.ip_address(value)
        if not address.is_global:
            raise MediaPolicyError(
                f"Reddit image host resolved to a non-public address: {host}"
            )
    return host


class _RedditRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _assert_safe_reddit_image_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _image_extension(url: str, content_type: str | None) -> str:
    suffix = Path(urlsplit(url).path).suffix.casefold()
    if suffix in SAFE_IMAGE_EXTENSIONS:
        return ".jpg" if suffix == ".jpeg" else suffix
    mime = (content_type or "").partition(";")[0].strip().casefold()
    guessed = mimetypes.guess_extension(mime) or ""
    guessed = ".jpg" if guessed in {".jpe", ".jpeg"} else guessed
    if guessed not in SAFE_IMAGE_EXTENSIONS:
        raise MediaError(f"Unsupported image content type: {content_type or 'unknown'}")
    return guessed


def run_http_image(
    candidate: MediaCandidate,
    stage: Path,
    max_bytes: int,
    timeout: float,
    retries: int,
) -> EngineResult:
    """Bounded HTTP fallback for direct, publicly routed Reddit CDN images."""
    url = _network_url(candidate)
    _assert_safe_reddit_image_url(url)
    stage.mkdir(parents=True, exist_ok=True)
    if existing := _finished_stage_file(stage, candidate.asset_id):
        return EngineResult(existing, candidate.url)
    partial = stage / f"asset-{candidate.asset_id}.download.part"
    opener = build_opener(_RedditRedirectHandler())
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        offset = partial.stat().st_size if partial.exists() else 0
        if offset > max_bytes:
            raise MediaError("Retained image partial already exceeds the byte cap")
        headers = {
            "Accept": "image/*",
            "User-Agent": MEDIA_USER_AGENT,
        }
        if offset:
            headers["Range"] = f"bytes={offset}-"
        request = Request(url, headers=headers)
        try:
            with opener.open(request, timeout=timeout) as response:
                final_url = response.geturl()
                _assert_safe_reddit_image_url(final_url)
                content_type = response.headers.get("Content-Type")
                if not (content_type or "").casefold().startswith("image/"):
                    raise MediaError(
                        f"Reddit CDN returned non-image content: {content_type or 'unknown'}"
                    )
                content_length = response.headers.get("Content-Length")
                expected = int(content_length) if content_length else None
                append = offset > 0 and int(getattr(response, "status", 200)) == 206
                if not append:
                    offset = 0
                if expected is not None and offset + expected > max_bytes:
                    raise MediaError("Image exceeds the configured per-file byte cap")

                mode = "ab" if append else "wb"
                total = offset
                with partial.open(mode) as handle:
                    while chunk := response.read(64 * 1024):
                        total += len(chunk)
                        if total > max_bytes:
                            handle.flush()
                            os.fsync(handle.fileno())
                            raise MediaError(
                                "Image stream exceeded the per-file byte cap; "
                                "the resumable partial was retained"
                            )
                        handle.write(chunk)
                    handle.flush()
                    os.fsync(handle.fileno())
                if total == 0:
                    raise MediaError("Reddit CDN returned an empty image")
                extension = _image_extension(final_url, content_type)
                completed = stage / f"asset-{candidate.asset_id}{extension}"
                if completed.exists():
                    raise MediaError(f"Completed stage path already exists: {completed}")
                os.replace(partial, completed)
                return EngineResult(completed, final_url, content_type)
        except MediaError:
            raise
        except (HTTPError, URLError, OSError, ValueError) as exc:
            last_error = exc
            if attempt >= retries:
                break
            time.sleep(min(2**attempt, 30))
    raise MediaError(f"Reddit image download failed: {last_error}") from last_error


def _assert_safe_public_https_url(url: str) -> str:
    """Reject credentials, custom ports, and non-public DNS destinations."""
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").casefold().rstrip(".")
        port = parsed.port
    except ValueError as exc:
        raise MediaPolicyError(f"Invalid linked-file URL: {url}") from exc
    if (
        parsed.scheme.casefold() != "https"
        or not host
        or port not in {None, 443}
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise MediaPolicyError("Linked-file downloads require ordinary HTTPS URLs")
    try:
        addresses = {
            result[4][0]
            for result in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        }
    except OSError as exc:
        raise MediaError(f"Could not resolve linked-file host {host}: {exc}") from exc
    if not addresses:
        raise MediaError(f"Linked-file host did not resolve: {host}")
    for value in addresses:
        if not ipaddress.ip_address(value).is_global:
            raise MediaPolicyError(
                f"Linked-file host resolved to a non-public address: {host}"
            )
    return host


class _PublicHttpsRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _assert_safe_public_https_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _response_filename(headers: Any, final_url: str) -> str | None:
    disposition = headers.get("Content-Disposition")
    if disposition:
        message = Message()
        message["content-disposition"] = disposition
        filename = message.get_filename()
        if filename:
            return Path(filename.replace("\\", "/")).name
    try:
        name = Path(unquote(urlsplit(final_url).path)).name
    except ValueError:
        return None
    return name or None


def _stage_extension(name: str | None, content_type: str | None) -> str:
    suffix = Path(name or "").suffix
    if SAFE_STAGE_SUFFIX.fullmatch(suffix):
        return suffix.casefold()
    guessed = mimetypes.guess_extension(
        (content_type or "").partition(";")[0].strip().casefold()
    ) or ""
    return guessed.casefold() if SAFE_STAGE_SUFFIX.fullmatch(guessed) else ".bin"


def _download_public_file(
    candidate: MediaCandidate,
    url: str,
    stage: Path,
    max_bytes: int,
    timeout: float,
    retries: int,
    *,
    suggested_name: str | None = None,
) -> EngineResult:
    _assert_safe_public_https_url(url)
    stage.mkdir(parents=True, exist_ok=True)
    if existing := _finished_stage_file(stage, candidate.asset_id):
        return EngineResult(existing, url, suggested_name=suggested_name)
    partial = stage / f"asset-{candidate.asset_id}.download.part"
    opener = build_opener(_PublicHttpsRedirectHandler())
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        offset = partial.stat().st_size if partial.exists() else 0
        if offset > max_bytes:
            raise MediaError("Retained linked-file partial exceeds the byte cap")
        headers = {"Accept": "*/*", "User-Agent": MEDIA_USER_AGENT}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        try:
            with opener.open(Request(url, headers=headers), timeout=timeout) as response:
                final_url = response.geturl()
                _assert_safe_public_https_url(final_url)
                content_type = response.headers.get("Content-Type")
                mime = (content_type or "").partition(";")[0].strip().casefold()
                if mime in {"text/html", "application/xhtml+xml"}:
                    raise MediaError(
                        "The linked URL returned a web page, not downloadable file bytes"
                    )
                content_length = response.headers.get("Content-Length")
                expected = int(content_length) if content_length else None
                append = offset > 0 and int(getattr(response, "status", 200)) == 206
                if not append:
                    offset = 0
                if expected is not None and offset + expected > max_bytes:
                    raise MediaError("Linked file exceeds the per-file byte cap")

                total = offset
                with partial.open("ab" if append else "wb") as handle:
                    while chunk := response.read(64 * 1024):
                        total += len(chunk)
                        if total > max_bytes:
                            handle.flush()
                            os.fsync(handle.fileno())
                            raise MediaError(
                                "Linked-file stream exceeded the per-file byte cap; "
                                "the resumable partial was retained"
                            )
                        handle.write(chunk)
                    handle.flush()
                    os.fsync(handle.fileno())
                if total == 0:
                    raise MediaError("Linked-file host returned an empty file")
                name = suggested_name or _response_filename(
                    response.headers,
                    final_url,
                )
                completed = stage / (
                    f"asset-{candidate.asset_id}"
                    f"{_stage_extension(name, content_type)}"
                )
                if completed.exists():
                    raise MediaError(f"Completed stage path already exists: {completed}")
                os.replace(partial, completed)
                return EngineResult(
                    completed,
                    final_url,
                    content_type,
                    suggested_name=name,
                )
        except MediaError:
            raise
        except (HTTPError, URLError, OSError, ValueError) as exc:
            last_error = exc
            if attempt >= retries:
                break
            time.sleep(min(2**attempt, 30))
    raise MediaError(f"Linked-file download failed: {last_error}") from last_error


def run_http_file(
    candidate: MediaCandidate,
    stage: Path,
    max_bytes: int,
    timeout: float,
    retries: int,
) -> EngineResult:
    """Download one user-confirmed public HTTPS URL with strict byte bounds."""
    return _download_public_file(
        candidate,
        _network_url(candidate),
        stage,
        max_bytes,
        timeout,
        retries,
    )


def run_mediafire_file(
    candidate: MediaCandidate,
    stage: Path,
    max_bytes: int,
    timeout: float,
    retries: int,
) -> EngineResult:
    """Resolve one MediaFire file page, then use the bounded HTTPS downloader."""
    page_url = _network_url(candidate)
    _assert_safe_public_https_url(page_url)
    mediafire_http = MediafireHttpClient(timeout=max(1, int(timeout)))
    mediafire_http.opener = build_opener(_PublicHttpsRedirectHandler())
    client = MediafireClient(mediafire_http)
    plan = client.build_plan(page_url)
    if plan.is_folder or len(plan.files) != 1:
        raise MediaPolicyError(
            "Linked-file folders are shown as links but are not downloaded"
        )
    item = plan.files[0]
    if item.size is not None and item.size > max_bytes:
        raise MediaError("Linked file exceeds the configured per-file byte cap")
    _assert_safe_public_https_url(item.page_url)
    direct_url = client.http.find_public_download_url(item.page_url)
    return _download_public_file(
        candidate,
        direct_url,
        stage,
        max_bytes,
        timeout,
        retries,
        suggested_name=item.name,
    )


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with Path(path).open("rb") as handle:
        while block := handle.read(8 * 1024 * 1024):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def _validate_image(path: Path) -> None:
    try:
        with Image.open(path) as image:
            image.verify()
    except (OSError, UnidentifiedImageError) as exc:
        raise MediaError(f"Downloaded image failed validation: {path.name}") from exc


def _content_type(path: Path, engine_result: EngineResult) -> str | None:
    if engine_result.content_type:
        return engine_result.content_type.partition(";")[0].strip().casefold()
    return mimetypes.guess_type(path.name)[0]


def _safe_object_extension(path: Path, content_type: str | None) -> str:
    suffix = path.suffix.casefold()
    allowed = SAFE_IMAGE_EXTENSIONS | SAFE_VIDEO_EXTENSIONS
    if suffix in allowed:
        return ".jpg" if suffix == ".jpeg" else suffix
    if SAFE_STAGE_SUFFIX.fullmatch(suffix):
        return suffix
    guessed = mimetypes.guess_extension(content_type or "") or ""
    guessed = ".jpg" if guessed in {".jpe", ".jpeg"} else guessed
    return guessed if guessed in allowed else ".bin"


_UNSAFE_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED = {
    "aux",
    "con",
    "nul",
    "prn",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}


def _safe_library_name(value: str | None, fallback: str, limit: int = 96) -> str:
    cleaned = _UNSAFE_FILENAME.sub("-", (value or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    if not cleaned:
        cleaned = fallback
    stem = Path(cleaned).stem.casefold()
    if stem in _WINDOWS_RESERVED:
        cleaned = "_" + cleaned
    if len(cleaned) > limit:
        suffix = Path(cleaned).suffix
        keep = max(1, limit - len(suffix))
        cleaned = cleaned[:keep].rstrip(" .") + suffix[:16]
    return cleaned


def _library_owner(
    connection: sqlite3.Connection,
    candidate: MediaCandidate,
) -> tuple[str, str]:
    if candidate.owner_type == "post":
        row = connection.execute(
            "SELECT subreddit, title FROM posts WHERE id=?",
            (candidate.owner_id,),
        ).fetchone()
        return (
            str(row["subreddit"] if row and row["subreddit"] else "unknown"),
            str(row["title"] if row and row["title"] else candidate.owner_id),
        )
    if candidate.owner_type == "comment":
        row = connection.execute(
            """
            SELECT p.subreddit, p.title
            FROM comments c LEFT JOIN posts p ON p.id=c.post_id
            WHERE c.id=?
            """,
            (candidate.owner_id,),
        ).fetchone()
        return (
            str(row["subreddit"] if row and row["subreddit"] else "unknown"),
            str(row["title"] if row and row["title"] else candidate.owner_id),
        )
    return candidate.owner_id, candidate.owner_id


def _materialize_library_file(
    connection: sqlite3.Connection,
    *,
    candidate: MediaCandidate,
    engine_result: EngineResult,
    stored: StoredObject,
    destination: Path,
) -> Path:
    subreddit, title = _library_owner(connection, candidate)
    owner_folder = _safe_library_name(
        f"{candidate.owner_id} - {title}",
        candidate.owner_id,
        limit=120,
    )
    suggested = engine_result.suggested_name
    if not suggested:
        suggested = Path(urlsplit(engine_result.final_url).path).name
    filename = _safe_library_name(
        suggested,
        f"{candidate.role}{stored.path.suffix}",
        limit=120,
    )
    if not Path(filename).suffix and stored.path.suffix:
        filename += stored.path.suffix
    # One readable alias per owner/content hash. Several Reddit asset roles
    # can point at identical bytes (preview, gallery, original); asset-id
    # filenames used to publish the same image repeatedly. Existing aliases
    # remain untouched as archive evidence, while future runs converge here.
    extension = Path(filename).suffix or stored.path.suffix or ".bin"
    if not Path(filename).suffix:
        filename += extension
    target_parent = (
        destination
        / "library"
        / _safe_library_name(subreddit, "unknown")
        / owner_folder
    )
    hash_prefix = stored.sha256[:20]
    target = target_parent / f"{hash_prefix}-{filename}"
    target.parent.mkdir(parents=True, exist_ok=True)
    # The first published alias keeps a readable source name. Later asset
    # roles for the same owner/content hash reuse it even when Reddit supplied
    # a different preview filename.
    existing_aliases = sorted(target_parent.glob(f"{hash_prefix}-*"))
    if existing_aliases:
        for existing in existing_aliases:
            digest, size = _hash_file(existing)
            if digest == stored.sha256 and size == stored.byte_size:
                return existing
        raise MediaError(
            f"Published Reddit hash prefix conflicts in {target_parent}"
        )
    if target.exists():
        digest, size = _hash_file(target)
        if digest != stored.sha256 or size != stored.byte_size:
            raise MediaError(f"Published Reddit file conflicts with {target}")
        return target
    try:
        os.link(stored.path, target)
    except OSError:
        temporary = target.parent / f".{target.name}.{uuid4().hex}.tmp"
        try:
            with stored.path.open("rb") as source, temporary.open("xb") as output:
                shutil.copyfileobj(source, output, length=8 * 1024 * 1024)
                output.flush()
                os.fsync(output.fileno())
            digest, size = _hash_file(temporary)
            if digest != stored.sha256 or size != stored.byte_size:
                raise MediaError(
                    f"Published Reddit file copy failed verification: {target}"
                )
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()
    return target


def _install_object(
    staged: Path,
    destination: Path,
    *,
    content_type: str | None,
) -> StoredObject:
    digest, size = _hash_file(staged)
    object_parent = destination / "objects" / "sha256" / digest[:2]
    object_parent.mkdir(parents=True, exist_ok=True)
    existing_values = sorted(object_parent.glob(f"{digest}.*"))
    if len(existing_values) > 1:
        raise MediaError(f"Multiple media objects already use SHA-256 {digest}")
    if existing_values:
        existing = existing_values[0]
        existing_digest, existing_size = _hash_file(existing)
        if existing_digest != digest or existing_size != size:
            raise MediaError(f"Existing media object failed verification: {existing}")
        # This is downloader scratch, not an installed archive object. Its
        # verified bytes already exist at the content-addressed destination.
        staged.unlink()
        object_path = existing
        deduplicated = True
    else:
        extension = _safe_object_extension(staged, content_type)
        object_path = object_parent / f"{digest}{extension}"
        os.replace(staged, object_path)
        deduplicated = False
    relative = object_path.relative_to(destination).as_posix()
    return StoredObject(
        sha256=digest,
        path=object_path,
        relative_path=relative,
        byte_size=size,
        content_type=content_type,
        deduplicated=deduplicated,
    )


def _manifest_path(destination: Path, asset_id: int, attempt_id: str) -> Path:
    return destination / "manifests" / str(asset_id) / f"{attempt_id}.json"


def _write_manifest(
    path: Path,
    *,
    candidate: MediaCandidate,
    attempt_id: str,
    engine_result: EngineResult,
    stored: StoredObject,
    created_at: str,
) -> None:
    payload = {
        "format": "keivotos-reddit-media-observation-v1",
        "attempt_id": attempt_id,
        "asset": {
            "id": candidate.asset_id,
            "owner_type": candidate.owner_type,
            "owner_id": candidate.owner_id,
            "role": candidate.role,
            "source_url": candidate.url,
        },
        "engine": candidate.engine,
        "final_url": engine_result.final_url,
        "object": {
            "sha256": stored.sha256,
            "relative_path": stored.relative_path,
            "byte_size": stored.byte_size,
            "content_type": stored.content_type,
        },
        "created_at": created_at,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )
    try:
        with path.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise MediaError(f"Media observation manifest already exists: {path}") from exc


def _insert_event(
    connection: sqlite3.Connection,
    *,
    attempt_id: str,
    candidate: MediaCandidate,
    event_type: str,
    created_at: str,
    final_url: str | None = None,
    stored: StoredObject | None = None,
    manifest_path: str | None = None,
    error: str | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO asset_download_events(
            attempt_id, asset_id, event_type, engine, source_url, final_url,
            object_sha256, byte_size, manifest_path, error, created_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            attempt_id,
            candidate.asset_id,
            event_type,
            candidate.engine,
            candidate.url,
            final_url,
            stored.sha256 if stored else None,
            stored.byte_size if stored else None,
            manifest_path,
            error,
            created_at,
        ),
    )


def _record_complete(
    connection: sqlite3.Connection,
    *,
    candidate: MediaCandidate,
    attempt_id: str,
    engine_result: EngineResult,
    stored: StoredObject,
    manifest_path: Path,
    created_at: str,
) -> None:
    connection.execute(
        """
        INSERT OR IGNORE INTO media_objects(
            sha256, relative_path, byte_size, content_type, created_at
        ) VALUES(?, ?, ?, ?, ?)
        """,
        (
            stored.sha256,
            stored.relative_path,
            stored.byte_size,
            stored.content_type,
            created_at,
        ),
    )
    row = connection.execute(
        "SELECT relative_path, byte_size FROM media_objects WHERE sha256=?",
        (stored.sha256,),
    ).fetchone()
    if row is None or (
        row["relative_path"] != stored.relative_path
        or int(row["byte_size"]) != stored.byte_size
    ):
        raise MediaError(f"Media object ledger conflict for {stored.sha256}")
    _insert_event(
        connection,
        attempt_id=attempt_id,
        candidate=candidate,
        event_type="complete",
        created_at=created_at,
        final_url=engine_result.final_url,
        stored=stored,
        manifest_path=str(manifest_path),
    )
    connection.execute(
        "UPDATE assets SET status='downloaded', local_path=? WHERE id=?",
        (str(stored.path), candidate.asset_id),
    )


def _preserve_failed_output(
    staged: Path,
    destination: Path,
    candidate: MediaCandidate,
    attempt_id: str,
    category: str,
) -> Path:
    target = (
        destination
        / category
        / str(candidate.asset_id)
        / attempt_id
        / staged.name
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise MediaError(f"Failure preservation path already exists: {target}")
    os.replace(staged, target)
    return target


def download_media(
    plan: MediaPlan,
    *,
    confirm_assets: int,
    confirm_selection: str,
    timeout: float = DEFAULT_TIMEOUT,
    process_timeout: float = DEFAULT_PROCESS_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    gallery_runner: GalleryRunner = run_gallery_dl,
    video_runner: VideoRunner = run_yt_dlp,
    http_runner: HttpRunner = run_http_image,
    linked_runner: HttpRunner = run_http_file,
    mediafire_runner: HttpRunner = run_mediafire_file,
    disk_free: Callable[[Path], int] = _disk_free,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
) -> DownloadSummary:
    """Execute one confirmed plan sequentially and preserve every completed file."""
    if confirm_assets != plan.selected_assets:
        raise MediaConfirmationError(
            f"Plan currently selects {plan.selected_assets} assets; "
            f"--confirm-assets was {confirm_assets}"
        )
    if confirm_selection.casefold() != plan.selection_sha256:
        raise MediaConfirmationError(
            "The selected asset set changed; run plan again and pass its "
            "selection_sha256 to --confirm-selection"
        )
    if timeout <= 0 or process_timeout <= 0:
        raise ValueError("download timeouts must be positive")
    if retries < 0:
        raise ValueError("retries cannot be negative")
    if plan.selected_assets == 0:
        return DownloadSummary(planned=0)
    destination = Path(plan.destination)
    if disk_free(destination) < plan.required_start_bytes:
        raise MediaError("Free-space guard prevents starting this media run")
    destination.mkdir(parents=True, exist_ok=True)
    summary = DownloadSummary(planned=plan.selected_assets)

    def report(phase: str) -> None:
        if on_progress is None:
            return
        try:
            on_progress({**summary.as_dict(), "phase": phase})
        except Exception:
            # UI progress must never interrupt a confirmed transfer.
            pass

    report("starting")

    with open_archive(Path(plan.database_path)) as connection:
        for candidate in plan.candidates:
            if summary.bytes_acquired >= plan.limits.max_run_bytes:
                summary.stop_reason = "run-byte-limit"
                break

            remaining = plan.limits.max_run_bytes - summary.bytes_acquired
            effective_max = min(plan.limits.max_file_bytes, remaining)
            if disk_free(destination) < plan.limits.min_free_bytes + effective_max:
                summary.stop_reason = "free-space-guard"
                break
            expected_engine, rejection = classify_asset(
                candidate.role, candidate.url
            )
            if expected_engine != candidate.engine:
                raise MediaPolicyError(
                    "Confirmed plan contains an asset outside the current "
                    f"media policy ({rejection or 'engine mismatch'})"
                )
            attempt_id = uuid4().hex
            started_at = _now()
            _insert_event(
                connection,
                attempt_id=attempt_id,
                candidate=candidate,
                event_type="started",
                created_at=started_at,
            )
            connection.execute(
                "UPDATE assets SET status='downloading' WHERE id=?",
                (candidate.asset_id,),
            )
            connection.commit()
            summary.attempted += 1
            report("downloading")
            stage = destination / ".staging" / str(candidate.asset_id)
            completed_stage: Path | None = None

            try:
                if candidate.engine == "gallery-dl":
                    result = gallery_runner(
                        candidate,
                        stage,
                        effective_max,
                        timeout,
                        process_timeout,
                        retries,
                    )
                elif candidate.engine == "yt-dlp":
                    result = video_runner(
                        candidate,
                        stage,
                        effective_max,
                        timeout,
                        process_timeout,
                        retries,
                    )
                elif candidate.engine == "http":
                    result = http_runner(
                        candidate,
                        stage,
                        effective_max,
                        timeout,
                        retries,
                    )
                elif candidate.engine == "http-file":
                    result = linked_runner(
                        candidate,
                        stage,
                        effective_max,
                        timeout,
                        retries,
                    )
                elif candidate.engine == "mediafire":
                    result = mediafire_runner(
                        candidate,
                        stage,
                        effective_max,
                        timeout,
                        retries,
                    )
                else:
                    raise MediaPolicyError(
                        f"Unsupported media engine: {candidate.engine}"
                    )

                staged = Path(result.path).resolve(strict=True)
                completed_stage = staged
                stage_root = stage.resolve(strict=True)
                if staged.parent != stage_root:
                    raise MediaError("Downloader returned a file outside its stage")
                size = staged.stat().st_size
                summary.bytes_acquired += size
                if size > effective_max:
                    preserved = _preserve_failed_output(
                        staged,
                        destination,
                        candidate,
                        attempt_id,
                        "oversize",
                    )
                    raise MediaError(
                        f"Downloader exceeded the byte cap; file preserved at {preserved}"
                    )
                if candidate.role in IMAGE_ROLES:
                    _validate_image(staged)
                content_type = _content_type(staged, result)
                stored = _install_object(
                    staged,
                    destination,
                    content_type=content_type,
                )
                completed_at = _now()
                manifest_path = _manifest_path(
                    destination, candidate.asset_id, attempt_id
                )
                _write_manifest(
                    manifest_path,
                    candidate=candidate,
                    attempt_id=attempt_id,
                    engine_result=result,
                    stored=stored,
                    created_at=completed_at,
                )
                _record_complete(
                    connection,
                    candidate=candidate,
                    attempt_id=attempt_id,
                    engine_result=result,
                    stored=stored,
                    manifest_path=manifest_path,
                    created_at=completed_at,
                )
                connection.commit()
                summary.completed += 1
                if stored.deduplicated:
                    summary.deduplicated += 1
                else:
                    summary.new_object_bytes += stored.byte_size
                try:
                    _materialize_library_file(
                        connection,
                        candidate=candidate,
                        engine_result=result,
                        stored=stored,
                        destination=destination,
                    )
                    summary.published_files += 1
                except (MediaError, OSError):
                    summary.publication_failed += 1
                report("downloading")
            except Exception as exc:
                connection.rollback()
                failed_at = _now()
                message = str(exc)
                if completed_stage is not None and completed_stage.is_file():
                    try:
                        preserved = _preserve_failed_output(
                            completed_stage,
                            destination,
                            candidate,
                            attempt_id,
                            "failed",
                        )
                        message = f"{message}; output preserved at {preserved}"
                    except (MediaError, OSError) as preserve_exc:
                        message = (
                            f"{message}; output preservation also failed: "
                            f"{preserve_exc}"
                        )
                if len(message) > 2000:
                    message = message[-2000:]
                _insert_event(
                    connection,
                    attempt_id=attempt_id,
                    candidate=candidate,
                    event_type="failed",
                    created_at=failed_at,
                    error=message,
                )
                connection.execute(
                    "UPDATE assets SET status='failed' WHERE id=?",
                    (candidate.asset_id,),
                )
                connection.commit()
                summary.failed += 1
                report("downloading")

    report("finalizing")
    return summary
