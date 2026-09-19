"""Bounded yt-dlp metadata/search adapter and local thumbnail cache."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
from pathlib import Path
import socket
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from services import yt_dlp as yt_dlp_service


SEARCH_LIMIT_MAX = 30
MAX_THUMBNAIL_BYTES = 2 * 1024 * 1024
YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
}


class YouTubeProviderError(RuntimeError):
    pass


def validate_video_id(video_id: str) -> str:
    clean = video_id.strip()
    if len(clean) != 11 or any(
        not (character.isalnum() or character in "_-") for character in clean
    ):
        raise ValueError("Invalid YouTube video id")
    return clean


def watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={validate_video_id(video_id)}"


def validate_youtube_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").casefold()
        port = parsed.port
    except ValueError as exc:
        raise YouTubeProviderError("Invalid YouTube URL") from exc
    if (
        parsed.scheme.casefold() != "https"
        or host not in YOUTUBE_HOSTS
        or port not in {None, 443}
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise YouTubeProviderError("Only public HTTPS YouTube video URLs are allowed")
    return url


def video_id_from_url(url: str) -> str:
    """Extract one public video id from a supported YouTube URL."""
    clean = validate_youtube_url(url.strip())
    parsed = urlsplit(clean)
    host = (parsed.hostname or "").casefold()
    if host == "youtu.be":
        candidate = parsed.path.strip("/").split("/", 1)[0]
    else:
        parts = [part for part in parsed.path.split("/") if part]
        if parsed.path.rstrip("/") == "/watch":
            candidate = parse_qs(parsed.query).get("v", [""])[0]
        elif len(parts) >= 2 and parts[0] in {"shorts", "live", "embed"}:
            candidate = parts[1]
        else:
            candidate = ""
    try:
        return validate_video_id(candidate)
    except ValueError as exc:
        raise YouTubeProviderError(
            "Paste a single YouTube watch, short, live, or youtu.be URL"
        ) from exc


def _json_command(target: str, *, search: bool = False) -> list[str]:
    values = [
        *yt_dlp_service.resolve_command(error_type=YouTubeProviderError),
        "--ignore-config",
        *yt_dlp_service.javascript_runtime_args(),
        "--dump-single-json",
        "--skip-download",
        "--no-warnings",
    ]
    if search:
        values.extend(["--flat-playlist", "--playlist-end", str(SEARCH_LIMIT_MAX)])
    else:
        values.append("--no-playlist")
    values.append(target)
    return values


def _run_json(command: list[str], timeout: float) -> dict[str, Any]:
    result = yt_dlp_service.run_process(
        command,
        timeout=timeout,
        label="yt-dlp metadata",
        error_type=YouTubeProviderError,
    )
    try:
        value = json.loads(result.output)
    except ValueError as exc:
        raise YouTubeProviderError("yt-dlp returned invalid metadata JSON") from exc
    if not isinstance(value, dict):
        raise YouTubeProviderError("yt-dlp metadata is not an object")
    return value


def _sanitized_string(value: Any, limit: int = 20_000) -> str:
    return str(value or "")[:limit]


def sanitize_metadata(value: Any) -> Any:
    secret_parts = (
        "authorization",
        "cookie",
        "credential",
        "header",
        "password",
        "proxy",
        "token",
    )
    if isinstance(value, dict):
        return {
            str(key): sanitize_metadata(child)
            for key, child in value.items()
            if not any(part in str(key).casefold() for part in secret_parts)
            and str(key) not in {"formats", "requested_formats", "thumbnails"}
        }
    if isinstance(value, list):
        return [sanitize_metadata(child) for child in value[:500]]
    if isinstance(value, str):
        return value[:20_000]
    return value


def _entry(value: dict[str, Any]) -> dict[str, Any]:
    video_id = validate_video_id(_sanitized_string(value.get("id"), 32))
    webpage_url = value.get("webpage_url") or value.get("url")
    if not isinstance(webpage_url, str) or not webpage_url.startswith("http"):
        webpage_url = watch_url(video_id)
    validate_youtube_url(webpage_url)
    thumbnails = value.get("thumbnails")
    thumbnail = value.get("thumbnail")
    if not thumbnail and isinstance(thumbnails, list):
        thumbnail = next(
            (
                candidate.get("url")
                for candidate in reversed(thumbnails)
                if isinstance(candidate, dict) and candidate.get("url")
            ),
            None,
        )
    return {
        "video_id": video_id,
        "title": _sanitized_string(value.get("title") or video_id, 300),
        "channel": _sanitized_string(
            value.get("channel") or value.get("uploader") or "", 200
        ),
        "duration": value.get("duration"),
        "view_count": value.get("view_count"),
        "upload_date": value.get("upload_date"),
        "webpage_url": webpage_url,
        "thumbnail_url": thumbnail if isinstance(thumbnail, str) else None,
        "categories": [
            _sanitized_string(category, 80)
            for category in value.get("categories", [])
            if isinstance(category, str)
        ][:20],
        "live_status": _sanitized_string(value.get("live_status"), 40),
    }


def search(query: str, *, limit: int = 20, timeout: float = 45) -> list[dict[str, Any]]:
    clean = query.strip()
    if not clean:
        raise ValueError("YouTube search query is required")
    limit = max(1, min(int(limit), SEARCH_LIMIT_MAX))
    payload = _run_json(
        _json_command(f"ytsearch{limit}:{clean}", search=True),
        timeout,
    )
    entries = payload.get("entries")
    if not isinstance(entries, list):
        return []
    results = []
    for value in entries[:limit]:
        if not isinstance(value, dict):
            continue
        try:
            results.append(_entry(value))
        except (ValueError, YouTubeProviderError):
            continue
    return results


def _format(value: dict[str, Any]) -> dict[str, Any] | None:
    format_id = _sanitized_string(value.get("format_id"), 80)
    if not format_id:
        return None
    filesize = value.get("filesize") or value.get("filesize_approx")
    return {
        "format_id": format_id,
        "ext": _sanitized_string(value.get("ext"), 12),
        "width": value.get("width"),
        "height": value.get("height"),
        "fps": value.get("fps"),
        "vcodec": _sanitized_string(value.get("vcodec") or "none", 80),
        "acodec": _sanitized_string(value.get("acodec") or "none", 80),
        "filesize": int(filesize) if isinstance(filesize, (int, float)) else None,
        "tbr": value.get("tbr"),
        "abr": value.get("abr"),
        "format_note": _sanitized_string(value.get("format_note"), 100),
        "resolution": _sanitized_string(value.get("resolution"), 40),
    }


def _subtitle_map(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, list[str]] = {}
    for language, tracks in value.items():
        if not isinstance(tracks, list):
            continue
        formats = []
        for track in tracks:
            if isinstance(track, dict):
                ext = _sanitized_string(track.get("ext"), 12)
                if ext and ext not in formats:
                    formats.append(ext)
        result[_sanitized_string(language, 40)] = formats
    return result


def inspect(video_id: str, *, timeout: float = 45) -> dict[str, Any]:
    value = _run_json(_json_command(watch_url(video_id)), timeout)
    normalized = _entry(value)
    formats = [
        item
        for entry in value.get("formats", [])
        if isinstance(entry, dict) and (item := _format(entry)) is not None
    ]
    heights = sorted(
        {
            int(entry["height"])
            for entry in formats
            if isinstance(entry.get("height"), (int, float))
            and entry["vcodec"] != "none"
        }
    )
    normalized.update(
        {
            "description": _sanitized_string(value.get("description"), 20_000),
            "formats": formats,
            "available_resolutions": heights,
            "subtitles": _subtitle_map(value.get("subtitles")),
            "automatic_captions": _subtitle_map(value.get("automatic_captions")),
            "sanitized_metadata": sanitize_metadata(value),
        }
    )
    return normalized


def _is_compatible_video(value: dict[str, Any]) -> bool:
    codec = str(value.get("vcodec", "")).casefold()
    return value.get("ext") == "mp4" and (
        codec.startswith("avc") or codec.startswith("h264")
    )


def _is_compatible_audio(value: dict[str, Any]) -> bool:
    codec = str(value.get("acodec", "")).casefold()
    return value.get("ext") in {"m4a", "mp4"} or codec.startswith("mp4a")


def select_formats(
    metadata: dict[str, Any],
    *,
    resolution: str,
    compatibility: bool,
) -> dict[str, Any]:
    formats = metadata.get("formats", [])
    videos = [value for value in formats if value.get("vcodec") != "none"]
    if not videos:
        raise YouTubeProviderError("No downloadable video format was reported")
    target: int | None
    if resolution == "highest":
        target = None
    else:
        try:
            target = int(resolution)
        except ValueError as exc:
            raise ValueError("Invalid video resolution preset") from exc
        if target not in {480, 720, 1080, 1440, 2160}:
            raise ValueError("Unsupported video resolution preset")
    eligible = [
        value
        for value in videos
        if target is None
        or not isinstance(value.get("height"), (int, float))
        or int(value["height"]) <= target
    ]
    if not eligible:
        eligible = sorted(
            videos,
            key=lambda value: int(value.get("height") or 1_000_000),
        )[:1]
    selected_video = max(
        eligible,
        key=lambda value: (
            int(value.get("height") or 0),
            int(_is_compatible_video(value)) if compatibility else 0,
            float(value.get("fps") or 0),
            float(value.get("tbr") or 0),
        ),
    )
    selected_audio = None
    if selected_video.get("acodec") == "none":
        audios = [
            value
            for value in formats
            if value.get("vcodec") == "none" and value.get("acodec") != "none"
        ]
        if not audios:
            raise YouTubeProviderError("No audio stream was reported for this video")
        selected_audio = max(
            audios,
            key=lambda value: (
                int(_is_compatible_audio(value)) if compatibility else 0,
                float(value.get("abr") or value.get("tbr") or 0),
            ),
        )
    selector = selected_video["format_id"]
    selected = [selected_video]
    if selected_audio is not None:
        selector += f"+{selected_audio['format_id']}"
        selected.append(selected_audio)
    estimated = sum(
        int(value.get("filesize") or 0) for value in selected
    ) or None
    height = selected_video.get("height")
    quality_label = f"{int(height)}p" if isinstance(height, (int, float)) else resolution
    return {
        "selector": selector,
        "video": selected_video,
        "audio": selected_audio,
        "selected": selected,
        "estimated_bytes": estimated,
        "quality_label": quality_label,
    }


def _assert_thumbnail_url(url: str) -> None:
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").casefold()
        port = parsed.port
    except ValueError as exc:
        raise YouTubeProviderError("Invalid YouTube thumbnail URL") from exc
    if (
        parsed.scheme.casefold() != "https"
        or not (host == "ytimg.com" or host.endswith(".ytimg.com"))
        or port not in {None, 443}
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise YouTubeProviderError("Thumbnail is outside the approved YouTube CDN")
    try:
        addresses = {
            result[4][0]
            for result in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        }
    except OSError as exc:
        raise YouTubeProviderError(f"Could not resolve YouTube thumbnail host: {exc}") from exc
    if not addresses or any(
        not ipaddress.ip_address(address).is_global for address in addresses
    ):
        raise YouTubeProviderError("YouTube thumbnail host is not publicly routed")


class _ThumbnailRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _assert_thumbnail_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def cache_thumbnail(
    url: str,
    cache_directory: Path,
    *,
    user_agent: str,
    timeout: float = 15,
) -> str:
    _assert_thumbnail_url(url)
    cache_directory.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    existing = next(cache_directory.glob(f"{key}.*"), None)
    if existing is not None and existing.is_file():
        return existing.name
    request = Request(
        url,
        headers={"Accept": "image/*", "User-Agent": user_agent},
    )
    try:
        with build_opener(_ThumbnailRedirectHandler()).open(
            request, timeout=timeout
        ) as response:
            _assert_thumbnail_url(response.geturl())
            content_type = (response.headers.get("Content-Type") or "").casefold()
            if not content_type.startswith("image/"):
                raise YouTubeProviderError("YouTube thumbnail is not an image")
            data = response.read(MAX_THUMBNAIL_BYTES + 1)
    except YouTubeProviderError:
        raise
    except (HTTPError, URLError, OSError) as exc:
        raise YouTubeProviderError(f"YouTube thumbnail request failed: {exc}") from exc
    if not data or len(data) > MAX_THUMBNAIL_BYTES:
        raise YouTubeProviderError("YouTube thumbnail is empty or too large")
    extension = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/avif": ".avif",
    }.get(content_type.partition(";")[0], ".img")
    if extension == ".img":
        raise YouTubeProviderError("Unsupported YouTube thumbnail format")
    path = cache_directory / f"{key}{extension}"
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    return path.name
