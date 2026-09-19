"""Bounded Kara.moe API client and official hardsub acquisition."""
from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path
import socket
import threading
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


API_BASE = "https://kara.moe/api"
MAX_METADATA_BYTES = 8 * 1024 * 1024
ALLOWED_HOSTS = {"kara.moe", "www.kara.moe", "api.karaokes.moe"}
ALLOWED_SUFFIXES = (".karaokes.moe",)


class KaraMoeError(RuntimeError):
    pass


def _assert_provider_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").casefold()
        port = parsed.port
    except ValueError as exc:
        raise KaraMoeError("Kara.moe returned an invalid URL") from exc
    allowed = host in ALLOWED_HOSTS or any(
        host.endswith(suffix) for suffix in ALLOWED_SUFFIXES
    )
    if (
        parsed.scheme.casefold() != "https"
        or not allowed
        or port not in {None, 443}
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise KaraMoeError("Kara.moe redirected outside its approved hosts")
    try:
        addresses = {
            result[4][0]
            for result in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        }
    except OSError as exc:
        raise KaraMoeError(f"Could not resolve Kara.moe host {host}: {exc}") from exc
    if not addresses:
        raise KaraMoeError(f"Kara.moe host did not resolve: {host}")
    if any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise KaraMoeError("Kara.moe resolved to a non-public address")
    return host


class _ProviderRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _assert_provider_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open_url(request: Request, timeout: float):
    return build_opener(_ProviderRedirectHandler()).open(request, timeout=timeout)


def _read_json(url: str, *, user_agent: str, timeout: float) -> Any:
    _assert_provider_url(url)
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": user_agent},
    )
    try:
        with _open_url(request, timeout) as response:
            content_type = (response.headers.get("Content-Type") or "").casefold()
            if "json" not in content_type:
                raise KaraMoeError("Kara.moe returned non-JSON metadata")
            data = response.read(MAX_METADATA_BYTES + 1)
    except KaraMoeError:
        raise
    except (HTTPError, URLError, OSError) as exc:
        raise KaraMoeError(f"Kara.moe request failed: {exc}") from exc
    if len(data) > MAX_METADATA_BYTES:
        raise KaraMoeError("Kara.moe metadata exceeded the response limit")
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise KaraMoeError("Kara.moe returned invalid JSON") from exc


def _content(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [value for value in payload if isinstance(value, dict)]
    if isinstance(payload, dict):
        for key in ("content", "karas", "results", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [entry for entry in value if isinstance(entry, dict)]
    return []


def _names(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    results = []
    for entry in value:
        if isinstance(entry, str):
            name = entry
        elif isinstance(entry, dict):
            name = entry.get("name") or entry.get("tag") or entry.get("title")
            if isinstance(name, dict):
                name = next((v for v in name.values() if v), "")
        else:
            continue
        clean = str(name or "").strip()
        if clean and clean not in results:
            results.append(clean)
    return results


TAG_KEYS = {
    "series": ("series",),
    "languages": ("langs", "languages"),
    "singers": ("singers",),
    "songwriters": ("songwriters", "composers"),
    "creators": ("creators",),
    "karaoke_authors": ("authors", "karaoke_authors"),
    "video_content": ("versions", "video_contents"),
    "origins": ("origins",),
    "platforms": ("platforms",),
    "groups": ("groups",),
    "collections": ("collections",),
    "franchises": ("franchises",),
    "song_types": ("types", "songtypes"),
}


def tags(record: dict[str, Any]) -> dict[str, list[str]]:
    source = record.get("tags") if isinstance(record.get("tags"), dict) else record
    values: dict[str, list[str]] = {}
    for category, keys in TAG_KEYS.items():
        merged: list[str] = []
        for key in keys:
            for name in _names(source.get(key)):
                if name not in merged:
                    merged.append(name)
        if merged:
            values[category] = merged
    return values


def title(record: dict[str, Any]) -> str:
    direct = str(record.get("songname") or record.get("title") or "").strip()
    if direct:
        return direct
    titles = record.get("titles")
    if isinstance(titles, dict):
        return str(next((value for value in titles.values() if value), "Untitled"))
    return "Untitled"


def normalize(record: dict[str, Any]) -> dict[str, Any]:
    provider_id = str(record.get("kid") or record.get("id") or "").strip()
    if not provider_id:
        raise KaraMoeError("Kara.moe result is missing its stable id")
    tag_values = tags(record)
    song_type = (tag_values.get("song_types") or [""])[0]
    series = (tag_values.get("series") or [""])[0]
    subtitle = " ".join(
        part for part in (song_type, f"from {series}" if series else "") if part
    )
    return {
        "provider": "kara-moe",
        "provider_id": provider_id,
        "item_id": f"kara-moe:{provider_id}",
        "title": title(record),
        "subtitle": subtitle,
        "year": record.get("year"),
        "duration": record.get("duration"),
        "created_at": record.get("created_at") or record.get("createdAt"),
        "tags": tag_values,
        "lyrics": record.get("lyrics"),
        "lyrics_infos": record.get("lyrics_infos") or record.get("lyricsInfos"),
    }


def search(
    query: str,
    *,
    user_agent: str,
    size: int = 20,
    timeout: float = 20,
) -> list[dict[str, Any]]:
    clean = query.strip()
    if not clean:
        raise ValueError("Search query is required")
    size = max(1, min(int(size), 50))
    url = f"{API_BASE}/karas/search?{urlencode({'filter': clean, 'size': size})}"
    return [normalize(entry) for entry in _content(
        _read_json(url, user_agent=user_agent, timeout=timeout)
    )]


def detail(
    provider_id: str,
    *,
    user_agent: str,
    timeout: float = 20,
) -> dict[str, Any]:
    if not provider_id or any(character not in "0123456789abcdef-" for character in provider_id.casefold()):
        raise ValueError("Invalid Kara.moe id")
    payload = _read_json(
        f"{API_BASE}/karas/{provider_id}",
        user_agent=user_agent,
        timeout=timeout,
    )
    if not isinstance(payload, dict):
        raise KaraMoeError("Kara.moe returned an invalid detail record")
    return payload


def sanitized_metadata(value: Any) -> Any:
    secret_parts = ("cookie", "header", "password", "token", "authorization")
    if isinstance(value, dict):
        return {
            str(key): sanitized_metadata(child)
            for key, child in value.items()
            if not any(part in str(key).casefold() for part in secret_parts)
        }
    if isinstance(value, list):
        return [sanitized_metadata(child) for child in value]
    if isinstance(value, str):
        return value[:20_000]
    return value


def estimated_media_bytes(record: dict[str, Any]) -> int | None:
    for key in ("mediasize", "media_size", "filesize", "file_size"):
        value = record.get(key)
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            return parsed
    return None


def download_hardsub(
    provider_id: str,
    destination: Path,
    *,
    user_agent: str,
    max_bytes: int,
    timeout: float,
    on_progress: Callable[[int, int | None], None],
    cancel_event: threading.Event,
) -> dict[str, Any]:
    url = f"{API_BASE}/karas/{provider_id}/hardsub"
    _assert_provider_url(url)
    partial = destination.with_name(destination.name + ".part")
    destination.parent.mkdir(parents=True, exist_ok=True)
    offset = partial.stat().st_size if partial.exists() else 0
    if offset > max_bytes:
        raise KaraMoeError("Retained hardsub partial exceeds the byte limit")
    headers = {
        "Accept": "video/mp4,video/*;q=0.9",
        "User-Agent": user_agent,
    }
    if offset:
        headers["Range"] = f"bytes={offset}-"
    request = Request(url, headers=headers)
    try:
        with _open_url(request, timeout) as response:
            final_url = response.geturl()
            _assert_provider_url(final_url)
            status = int(getattr(response, "status", 200))
            append = offset > 0 and status == 206
            if not append:
                offset = 0
            content_type = (response.headers.get("Content-Type") or "").casefold()
            if not content_type.startswith("video/"):
                raise KaraMoeError("Kara.moe hardsub response is not a video")
            length = response.headers.get("Content-Length")
            expected = offset + int(length) if length else None
            if expected is not None and expected > max_bytes:
                raise KaraMoeError("Kara.moe hardsub exceeds the byte limit")
            total = offset
            with partial.open("ab" if append else "wb") as handle:
                while chunk := response.read(256 * 1024):
                    if cancel_event.is_set():
                        handle.flush()
                        os.fsync(handle.fileno())
                        raise KaraMoeError("Kara.moe download was cancelled")
                    total += len(chunk)
                    if total > max_bytes:
                        handle.flush()
                        os.fsync(handle.fileno())
                        raise KaraMoeError(
                            "Kara.moe hardsub stream exceeded the byte limit"
                        )
                    handle.write(chunk)
                    on_progress(total, expected)
                handle.flush()
                os.fsync(handle.fileno())
    except KaraMoeError:
        raise
    except (HTTPError, URLError, OSError, ValueError) as exc:
        raise KaraMoeError(f"Kara.moe hardsub download failed: {exc}") from exc
    if total <= 0:
        raise KaraMoeError("Kara.moe returned an empty hardsub")
    if destination.exists():
        raise KaraMoeError("Refusing to replace an existing hardsub")
    os.replace(partial, destination)
    return {
        "final_url": final_url,
        "content_type": content_type.partition(";")[0],
        "bytes": total,
    }
