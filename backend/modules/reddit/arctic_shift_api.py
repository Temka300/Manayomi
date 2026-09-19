"""Bounded structured capture from the public Arctic Shift JSON API.

This adapter accepts only already-parsed Reddit post or subreddit targets. It
does not scrape Reddit HTML, follow arbitrary URLs, or download media. Exact
JSON responses are preserved create-only beside normalized import source files
so the SQLite index remains rebuildable from durable evidence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Callable, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from modules.reddit.url_targets import CaptureTarget


API_ORIGIN = "https://arctic-shift.photon-reddit.com"
DIRECT_CAPTURE_FORMAT = "keivotos-reddit-direct-capture-v1"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RESPONSE_BYTES = 64 * 1024 * 1024
DEFAULT_MAX_RETRIES = 3
DEFAULT_MAX_WAIT_SECONDS = 60.0
DEFAULT_MAX_COMMENTS = 25_000
MAX_COMMENTS = 25_000
DEFAULT_MAX_WIKI_PAGES = 1_000
MAX_WIKI_PAGES = 10_000
WIKI_BATCH_SIZE = 100
USER_AGENT = "desktop:keivotos-reddit-capture:v0.1 (local personal archive)"


class ArcticShiftApiError(RuntimeError):
    """Raised when a bounded Arctic Shift capture cannot complete safely."""


class ArcticShiftOutputExistsError(ArcticShiftApiError):
    """Raised instead of overwriting a prior direct-capture bundle."""


class _HttpStatusError(ArcticShiftApiError):
    def __init__(self, status: int, headers: Mapping[str, str]):
        super().__init__(f"Arctic Shift returned HTTP {status}")
        self.status = status
        self.headers = {key.casefold(): value for key, value in headers.items()}


@dataclass(frozen=True)
class _JsonResponse:
    status: int
    headers: dict[str, str]
    payload: Any


Transport = Callable[[Request, float, int], _JsonResponse]


@dataclass(frozen=True)
class DirectCaptureBundle:
    """Durable exact responses plus generated local-import source files."""

    capture_id: str
    target_kind: str
    target_url: str
    retrieved_at: str
    source_directory: str
    manifest_path: str
    source_files: dict[str, str]
    request_count: int
    post_count: int
    comment_count: int
    placeholder_count: int
    unresolved_comment_ids: int
    wiki_page_count: int
    wiki_pages_truncated: bool
    moderators_available: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _default_transport(
    request: Request,
    timeout: float,
    max_response_bytes: int,
) -> _JsonResponse:
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(max_response_bytes + 1)
            if len(body) > max_response_bytes:
                raise ArcticShiftApiError(
                    "Arctic Shift response exceeded the configured byte limit"
                )
            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ArcticShiftApiError(
                    "Arctic Shift returned invalid UTF-8 JSON"
                ) from exc
            return _JsonResponse(
                status=int(response.status),
                headers={
                    key.casefold(): value for key, value in response.headers.items()
                },
                payload=payload,
            )
    except HTTPError as exc:
        raise _HttpStatusError(
            int(exc.code),
            {key.casefold(): value for key, value in exc.headers.items()},
        ) from exc
    except URLError as exc:
        raise ArcticShiftApiError(
            f"Arctic Shift connection failed: {exc.reason}"
        ) from exc


def _retry_after(headers: Mapping[str, str], fallback: float) -> float:
    value = headers.get("retry-after")
    if value is None:
        return fallback
    try:
        return max(0.0, float(value))
    except ValueError:
        return fallback


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _write_bytes_create_only(path: Path, data: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ArcticShiftOutputExistsError(
            f"Refused to overwrite direct-capture artifact: {path}"
        )
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
    return hashlib.sha256(data).hexdigest()


def _write_json_create_only(path: Path, payload: Any) -> str:
    data = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    return _write_bytes_create_only(path, data)


def _write_jsonl_create_only(path: Path, records: Iterable[Any]) -> str:
    data = "".join(f"{_canonical_json(record)}\n" for record in records).encode(
        "utf-8"
    )
    return _write_bytes_create_only(path, data)


def _response_items(payload: Any) -> list[Any]:
    """Accept the stable Arctic shapes without guessing arbitrary wrappers."""
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("data", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            children = value.get("children")
            if isinstance(children, list):
                return children
            return [value]
    if any(
        key in payload
        for key in ("id", "display_name", "subreddit", "path", "kind", "content")
    ):
        return [payload]
    return []


def _record_data(record: Any) -> dict[str, Any] | None:
    if not isinstance(record, dict):
        return None
    data = record.get("data")
    if isinstance(data, dict) and str(record.get("kind") or "").casefold() in {
        "t1",
        "t3",
        "t5",
    }:
        return data
    return record


def _thing_id(value: Any, prefix: str) -> str:
    result = str(value or "").strip().casefold()
    if result.startswith(f"{prefix}_"):
        result = result[3:]
    return result


def _select_post(payload: Any, post_id: str) -> tuple[Any, dict[str, Any]]:
    for record in _response_items(payload):
        data = _record_data(record)
        if data is not None and _thing_id(data.get("id"), "t3") == post_id:
            return record, data
    raise ArcticShiftApiError(
        f"Arctic Shift returned no post record for Reddit ID {post_id}"
    )


def _tree_records(
    payload: Any,
    post_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Flatten comments once while retaining exact nested response separately."""
    comments: list[dict[str, Any]] = []
    placeholders: list[dict[str, Any]] = []
    seen_comments: set[str] = set()
    seen_placeholders: set[tuple[str, str, tuple[str, ...]]] = set()
    stack: list[Any] = [payload]

    while stack:
        node = stack.pop()
        if isinstance(node, list):
            stack.extend(reversed(node))
            continue
        if not isinstance(node, dict):
            continue

        kind = str(node.get("kind") or "").casefold()
        data = node.get("data") if isinstance(node.get("data"), dict) else node
        if kind == "t1" or (
            kind == "" and "link_id" in data and "body" in data
        ):
            comment_id = _thing_id(data.get("id"), "t1")
            replies = data.get("replies")
            if replies not in (None, ""):
                stack.append(replies)
            if comment_id and comment_id not in seen_comments:
                seen_comments.add(comment_id)
                shallow = dict(data)
                shallow.pop("replies", None)
                shallow.setdefault("link_id", f"t3_{post_id}")
                shallow.setdefault("name", f"t1_{comment_id}")
                comments.append({"kind": "t1", "data": shallow})
            continue

        if kind == "more":
            children = data.get("children")
            child_ids = tuple(
                sorted(
                    {
                        _thing_id(value, "t1")
                        for value in children
                        if _thing_id(value, "t1")
                    }
                )
            ) if isinstance(children, list) else ()
            placeholder_id = _thing_id(data.get("id"), "more")
            parent_id = str(data.get("parent_id") or "").strip()
            identity = (placeholder_id, parent_id, child_ids)
            if identity not in seen_placeholders:
                seen_placeholders.add(identity)
                placeholders.append(
                    {
                        "type": "comment_placeholder",
                        "data": {
                            "id": placeholder_id or None,
                            "link_id": f"t3_{post_id}",
                            "parent_id": parent_id or f"t3_{post_id}",
                            "children": list(child_ids),
                            "count": data.get("count"),
                        },
                    }
                )
            continue

        # Listing and service wrappers only. Arbitrary nested metadata is not
        # traversed, preventing media dictionaries from looking like comments.
        for key in ("children", "replies", "data", "results"):
            value = node.get(key)
            if isinstance(value, (list, dict)):
                stack.append(value)

    comments.sort(
        key=lambda record: (
            float(record["data"].get("created_utc") or 0),
            str(record["data"].get("id") or ""),
        )
    )
    placeholders.sort(
        key=lambda record: (
            str(record["data"].get("parent_id") or ""),
            str(record["data"].get("id") or ""),
        )
    )
    return comments, placeholders


def _subreddit_record(
    payload: Any,
    subreddit: str,
) -> dict[str, Any]:
    target = subreddit.casefold()
    for record in _response_items(payload):
        data = _record_data(record)
        if data is None:
            continue
        value = str(
            data.get("display_name")
            or data.get("subreddit")
            or data.get("display_name_prefixed")
            or ""
        ).strip()
        if value.casefold().startswith("r/"):
            value = value[2:]
        if value.casefold() == target:
            return dict(data)
    raise ArcticShiftApiError(
        f"Arctic Shift returned no about record for r/{subreddit}"
    )


def _rules_record(payload: Any, subreddit: str) -> dict[str, Any]:
    target = subreddit.casefold()
    if isinstance(payload, dict) and isinstance(payload.get(subreddit), list):
        return {"subreddit": subreddit, "rules": payload[subreddit]}
    for record in _response_items(payload):
        data = _record_data(record)
        if data is None:
            continue
        value = str(data.get("subreddit") or subreddit).strip()
        if value.casefold().startswith("r/"):
            value = value[2:]
        if value.casefold() == target and isinstance(data.get("rules"), list):
            return dict(data)
    # An empty published rules response is a meaningful snapshot.
    if payload in ({}, [], None) or _response_items(payload) == []:
        return {"subreddit": subreddit, "rules": []}
    raise ArcticShiftApiError(
        f"Arctic Shift returned an invalid rules record for r/{subreddit}"
    )


def _wiki_paths(payload: Any, subreddit: str) -> list[str]:
    prefix = f"/r/{subreddit}/wiki/".casefold()
    values: list[str] = []
    candidates = _response_items(payload)
    if isinstance(payload, dict):
        for key in ("paths", "wikis"):
            if isinstance(payload.get(key), list):
                candidates.extend(payload[key])
    for item in candidates:
        value = item.get("path") if isinstance(item, dict) else item
        if not isinstance(value, str):
            continue
        normalized = "/" + value.lstrip("/")
        if normalized.casefold().startswith(prefix):
            values.append(normalized)
    return sorted(set(values), key=str.casefold)


def _wiki_records(payload: Any, subreddit: str) -> list[dict[str, Any]]:
    prefix = f"/r/{subreddit}/wiki/".casefold()
    result: list[dict[str, Any]] = []
    for record in _response_items(payload):
        data = _record_data(record)
        if data is None:
            continue
        path = data.get("path")
        content = data.get("content")
        if not isinstance(path, str) or not isinstance(content, str):
            continue
        normalized = "/" + path.lstrip("/")
        if normalized.casefold().startswith(prefix):
            item = dict(data)
            item["path"] = normalized
            result.append(item)
    result.sort(key=lambda value: str(value["path"]).casefold())
    return result


class ArcticShiftApiClient:
    """Finite, sequential JSON client for one explicit post or subreddit."""

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        max_retries: int = DEFAULT_MAX_RETRIES,
        max_wait_seconds: float = DEFAULT_MAX_WAIT_SECONDS,
        transport: Transport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("Arctic Shift timeout must be positive")
        if max_response_bytes <= 0:
            raise ValueError("Arctic Shift response-byte limit must be positive")
        if max_retries < 0:
            raise ValueError("Arctic Shift max_retries cannot be negative")
        if max_wait_seconds < 0:
            raise ValueError("Arctic Shift max_wait_seconds cannot be negative")
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes
        self.max_retries = max_retries
        self.max_wait_seconds = max_wait_seconds
        self.transport = transport or _default_transport
        self.sleep = sleep
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory or (lambda: uuid4().hex[:10])
        self.requests: list[dict[str, Any]] = []

    def _request(self, path: str, params: Mapping[str, Any]) -> Any:
        if not path.startswith("/api/"):
            raise ArcticShiftApiError("Refused non-API Arctic Shift path")
        query = urlencode(params)
        request = Request(
            f"{API_ORIGIN}{path}?{query}",
            method="GET",
            headers={
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            },
        )
        for attempt in range(self.max_retries + 1):
            try:
                response = self.transport(
                    request,
                    self.timeout,
                    self.max_response_bytes,
                )
                self.requests.append(
                    {
                        "path": path,
                        "query": {
                            key: str(value)
                            for key, value in sorted(params.items())
                        },
                        "status": int(response.status),
                    }
                )
                return response.payload
            except _HttpStatusError as exc:
                retryable = exc.status == 429 or 500 <= exc.status <= 599
                if not retryable or attempt >= self.max_retries:
                    raise ArcticShiftApiError(
                        f"Arctic Shift request failed with HTTP {exc.status}"
                    ) from exc
                delay = min(
                    _retry_after(exc.headers, float(2**attempt)),
                    self.max_wait_seconds,
                )
                self.sleep(delay)
        raise AssertionError("unreachable")

    def capture(
        self,
        target: CaptureTarget,
        destination_root: Path,
        *,
        max_comments: int = DEFAULT_MAX_COMMENTS,
        max_wiki_pages: int = DEFAULT_MAX_WIKI_PAGES,
    ) -> DirectCaptureBundle:
        if target.kind not in {"post", "subreddit", "user"}:
            raise ArcticShiftApiError(
                "Direct capture accepts only a Reddit post, subreddit, or user URL"
            )
        if not 1 <= max_comments <= MAX_COMMENTS:
            raise ValueError(
                f"max_comments must be between 1 and {MAX_COMMENTS}"
            )
        if not 0 <= max_wiki_pages <= MAX_WIKI_PAGES:
            raise ValueError(
                f"max_wiki_pages must be between 0 and {MAX_WIKI_PAGES}"
            )

        now = self.now().astimezone(timezone.utc)
        retrieved_at = now.isoformat()
        target_hash = hashlib.sha256(
            target.canonical_url.encode("utf-8")
        ).hexdigest()[:12]
        capture_id = (
            f"{now:%Y%m%dT%H%M%S%fZ}-{target.kind}-{target_hash}-"
            f"{self.id_factory()}"
        )
        destination_root = destination_root.expanduser().resolve(strict=False)
        destination = destination_root / capture_id
        staging = destination_root / f".{capture_id}.staging"
        if destination.exists() or staging.exists():
            raise ArcticShiftOutputExistsError(
                f"Direct-capture destination already exists: {destination}"
            )
        staging.mkdir(parents=True, exist_ok=False)
        hashes: dict[str, str] = {}
        source_files: dict[str, str] = {}
        post_count = comment_count = placeholder_count = 0
        unresolved_comment_ids = wiki_page_count = 0
        wiki_pages_truncated = False

        try:
            if target.kind == "post":
                (
                    hashes,
                    source_files,
                    post_count,
                    comment_count,
                    placeholder_count,
                    unresolved_comment_ids,
                ) = self._capture_post(
                    target,
                    staging,
                    retrieved_at=retrieved_at,
                    max_comments=max_comments,
                )
            elif target.kind == "subreddit":
                (
                    hashes,
                    source_files,
                    wiki_page_count,
                    wiki_pages_truncated,
                ) = self._capture_subreddit(
                    target,
                    staging,
                    retrieved_at=retrieved_at,
                    max_wiki_pages=max_wiki_pages,
                )
            else:
                (
                    hashes,
                    source_files,
                    post_count,
                    comment_count,
                ) = self._capture_user(
                    target,
                    staging,
                    retrieved_at=retrieved_at,
                )

            manifest = {
                "format": DIRECT_CAPTURE_FORMAT,
                "capture_id": capture_id,
                "source_adapter": "arctic-shift-api",
                "source_origin": API_ORIGIN,
                "target": target.as_dict(),
                "retrieved_at": retrieved_at,
                "limits": {
                    "max_comments": max_comments,
                    "max_wiki_pages": max_wiki_pages,
                    "max_response_bytes": self.max_response_bytes,
                    "timeout_seconds": self.timeout,
                    "max_retries": self.max_retries,
                },
                "coverage": {
                    "posts": post_count,
                    "comments": comment_count,
                    "comment_placeholders": placeholder_count,
                    "unresolved_comment_ids": unresolved_comment_ids,
                    "wiki_pages": wiki_page_count,
                    "wiki_pages_truncated": wiki_pages_truncated,
                    "moderators": {
                        "available": False,
                        "reason": (
                            "Arctic Shift does not provide current moderator "
                            "membership; use a local moderator snapshot bundle."
                        ),
                    },
                },
                "requests": self.requests,
                "files": {
                    name: {"sha256": digest}
                    for name, digest in sorted(hashes.items())
                },
            }
            hashes["manifest.json"] = _write_json_create_only(
                staging / "manifest.json",
                manifest,
            )
            staging.replace(destination)
        except BaseException:
            # A failed staging directory is evidence. It is deliberately left
            # in place rather than recursively deleted.
            raise

        resolved_sources = {
            key: str(destination / value)
            for key, value in source_files.items()
        }
        return DirectCaptureBundle(
            capture_id=capture_id,
            target_kind=target.kind,
            target_url=target.canonical_url,
            retrieved_at=retrieved_at,
            source_directory=str(destination),
            manifest_path=str(destination / "manifest.json"),
            source_files=resolved_sources,
            request_count=len(self.requests),
            post_count=post_count,
            comment_count=comment_count,
            placeholder_count=placeholder_count,
            unresolved_comment_ids=unresolved_comment_ids,
            wiki_page_count=wiki_page_count,
            wiki_pages_truncated=wiki_pages_truncated,
            moderators_available=False,
        )

    def _capture_post(
        self,
        target: CaptureTarget,
        staging: Path,
        *,
        retrieved_at: str,
        max_comments: int,
    ) -> tuple[dict[str, str], dict[str, str], int, int, int, int]:
        if target.post_id is None:
            raise ArcticShiftApiError("Post target has no Reddit post ID")
        post_response = self._request(
            "/api/posts/ids",
            {"ids": target.post_id, "md2html": "false"},
        )
        post_record, post_data = _select_post(post_response, target.post_id)
        comments_response = self._request(
            "/api/comments/tree",
            {
                "link_id": f"t3_{target.post_id}",
                "limit": max_comments,
                "start_breadth": max_comments,
                "start_depth": max_comments,
                "md2html": "false",
            },
        )
        comments, placeholders = _tree_records(
            comments_response,
            target.post_id,
        )
        records = [post_record, *comments, *placeholders]
        hashes = {
            "post-response.json": _write_json_create_only(
                staging / "post-response.json",
                post_response,
            ),
            "comments-tree-response.json": _write_json_create_only(
                staging / "comments-tree-response.json",
                comments_response,
            ),
            "records.jsonl": _write_jsonl_create_only(
                staging / "records.jsonl",
                records,
            ),
        }
        unresolved_ids = {
            child_id
            for placeholder in placeholders
            for child_id in placeholder["data"]["children"]
        }
        declared = post_data.get("num_comments")
        coverage = {
            "format": "keivotos-reddit-direct-post-coverage-v1",
            "target_url": target.canonical_url,
            "post_id": target.post_id,
            "retrieved_at": retrieved_at,
            "declared_num_comments": declared,
            "observed_comments": len(comments),
            "comment_placeholders": len(placeholders),
            "unresolved_comment_ids": sorted(unresolved_ids),
            "complete": len(placeholders) == 0 and (
                not isinstance(declared, int) or declared <= len(comments)
            ),
        }
        hashes["coverage.json"] = _write_json_create_only(
            staging / "coverage.json",
            coverage,
        )
        return (
            hashes,
            {"records": "records.jsonl", "coverage": "coverage.json"},
            1,
            len(comments),
            len(placeholders),
            len(unresolved_ids),
        )

    def _capture_subreddit(
        self,
        target: CaptureTarget,
        staging: Path,
        *,
        retrieved_at: str,
        max_wiki_pages: int,
    ) -> tuple[dict[str, str], dict[str, str], int, bool]:
        if target.subreddit is None:
            raise ArcticShiftApiError("Subreddit target has no subreddit name")
        subreddit = target.subreddit
        about_response = self._request(
            "/api/subreddits/search",
            {"subreddit": subreddit, "limit": 1},
        )
        rules_response = self._request(
            "/api/subreddits/rules",
            {"subreddits": subreddit},
        )
        wiki_list_response = self._request(
            "/api/subreddits/wikis/list",
            {"subreddit": subreddit},
        )
        about = _subreddit_record(about_response, subreddit)
        rules = _rules_record(rules_response, subreddit)
        about.setdefault("retrieved_on", retrieved_at)
        rules.setdefault("retrieved_on", retrieved_at)

        all_paths = _wiki_paths(wiki_list_response, subreddit)
        selected_paths = all_paths[:max_wiki_pages]
        truncated = len(all_paths) > len(selected_paths)
        wiki_records: list[dict[str, Any]] = []
        wiki_responses: list[tuple[str, Any]] = []
        for index in range(0, len(selected_paths), WIKI_BATCH_SIZE):
            batch = selected_paths[index : index + WIKI_BATCH_SIZE]
            response = self._request(
                "/api/subreddits/wikis",
                {"paths": ",".join(batch)},
            )
            name = f"wiki-batch-{index // WIKI_BATCH_SIZE + 1:04d}-response.json"
            wiki_responses.append((name, response))
            wiki_records.extend(_wiki_records(response, subreddit))
        for record in wiki_records:
            record.setdefault("retrieved_on", retrieved_at)

        hashes = {
            "about-response.json": _write_json_create_only(
                staging / "about-response.json",
                about_response,
            ),
            "rules-response.json": _write_json_create_only(
                staging / "rules-response.json",
                rules_response,
            ),
            "wiki-list-response.json": _write_json_create_only(
                staging / "wiki-list-response.json",
                wiki_list_response,
            ),
            "about.json": _write_json_create_only(
                staging / "about.json",
                about,
            ),
            "rules.json": _write_json_create_only(
                staging / "rules.json",
                rules,
            ),
            "wiki.jsonl": _write_jsonl_create_only(
                staging / "wiki.jsonl",
                wiki_records,
            ),
        }
        for name, response in wiki_responses:
            hashes[name] = _write_json_create_only(staging / name, response)
        coverage = {
            "format": "keivotos-reddit-direct-community-coverage-v1",
            "target_url": target.canonical_url,
            "subreddit": subreddit,
            "retrieved_at": retrieved_at,
            "about_records": 1,
            "rule_count": len(rules["rules"]),
            "wiki_paths_reported": len(all_paths),
            "wiki_pages_requested": len(selected_paths),
            "wiki_pages_received": len(wiki_records),
            "wiki_pages_truncated": truncated,
            "moderators": {
                "available": False,
                "reason": (
                    "Arctic Shift does not provide current moderator membership."
                ),
            },
        }
        hashes["coverage.json"] = _write_json_create_only(
            staging / "coverage.json",
            coverage,
        )
        return (
            hashes,
            {
                "about": "about.json",
                "rules": "rules.json",
                "wiki": "wiki.jsonl",
                "coverage": "coverage.json",
            },
            len(wiki_records),
            truncated,
        )

    def _capture_user(
        self,
        target: CaptureTarget,
        staging: Path,
        *,
        retrieved_at: str,
    ) -> tuple[dict[str, str], dict[str, str], int, int]:
        if target.username is None:
            raise ArcticShiftApiError("User target has no Reddit username")
        common = {
            "author": target.username,
            "limit": 100,
            "sort": "desc",
            "md2html": "false",
        }
        posts_response = self._request("/api/posts/search", common)
        comments_response = self._request("/api/comments/search", common)
        posts = [
            {"kind": "t3", "data": data}
            for record in _response_items(posts_response)
            if (data := _record_data(record)) is not None
            and str(data.get("author") or "").casefold()
            == target.username.casefold()
        ]
        comments = [
            {"kind": "t1", "data": data}
            for record in _response_items(comments_response)
            if (data := _record_data(record)) is not None
            and str(data.get("author") or "").casefold()
            == target.username.casefold()
        ]
        records = [*posts, *comments]
        hashes = {
            "posts-response.json": _write_json_create_only(
                staging / "posts-response.json", posts_response
            ),
            "comments-response.json": _write_json_create_only(
                staging / "comments-response.json", comments_response
            ),
            "records.jsonl": _write_jsonl_create_only(
                staging / "records.jsonl", records
            ),
        }
        coverage = {
            "format": "keivotos-reddit-direct-user-coverage-v1",
            "target_url": target.canonical_url,
            "username": target.username,
            "retrieved_at": retrieved_at,
            "posts": len(posts),
            "comments": len(comments),
            "bounded": True,
            "limit_per_record_type": 100,
        }
        hashes["coverage.json"] = _write_json_create_only(
            staging / "coverage.json", coverage
        )
        return (
            hashes,
            {"records": "records.jsonl", "coverage": "coverage.json"},
            len(posts),
            len(comments),
        )
