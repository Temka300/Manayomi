"""Bounded, read-only discovery through Reddit's official OAuth Data API."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from modules.reddit.url_targets import CaptureTarget


TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
API_ORIGIN = "https://oauth.reddit.com"
MAX_LISTING_ITEMS = 1000
MAX_PAGE_SIZE = 100
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
FULLNAME_RE = re.compile(r"^t[13]_[a-z0-9]+$")


class RedditApiError(RuntimeError):
    """Raised when bounded Reddit API discovery cannot complete safely."""


class DiscoveryOutputExistsError(RedditApiError):
    """Raised instead of overwriting an earlier API discovery manifest."""


class _HttpStatusError(RedditApiError):
    def __init__(self, status: int, headers: Mapping[str, str]):
        super().__init__(f"Reddit API returned HTTP {status}")
        self.status = status
        self.headers = {key.casefold(): value for key, value in headers.items()}


@dataclass(frozen=True)
class RedditApiCredentials:
    """OAuth application credentials loaded without command-line exposure."""

    client_id: str
    client_secret: str
    user_agent: str

    def __post_init__(self) -> None:
        if not self.client_id.strip():
            raise ValueError("Reddit OAuth client ID cannot be empty")
        if not self.client_secret:
            raise ValueError("Reddit OAuth client secret cannot be empty")
        user_agent = self.user_agent.strip()
        if len(user_agent) < 10:
            raise ValueError("Reddit User-Agent must be unique and descriptive")
        if user_agent.casefold().startswith(
            ("python", "urllib", "requests", "curl", "wget")
        ):
            raise ValueError("Reddit User-Agent must not be a generic library name")

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> "RedditApiCredentials":
        values = os.environ if environment is None else environment
        missing = [
            name
            for name in (
                "REDDIT_CLIENT_ID",
                "REDDIT_CLIENT_SECRET",
                "REDDIT_USER_AGENT",
            )
            if not values.get(name)
        ]
        if missing:
            raise RedditApiError(
                "Missing Reddit OAuth environment variables: " + ", ".join(missing)
            )
        return cls(
            client_id=values["REDDIT_CLIENT_ID"],
            client_secret=values["REDDIT_CLIENT_SECRET"],
            user_agent=values["REDDIT_USER_AGENT"],
        )


@dataclass(frozen=True)
class DiscoveryItem:
    """The minimum durable handoff from live discovery to a local source."""

    fullname: str
    kind: str
    reddit_id: str
    canonical_url: str


@dataclass(frozen=True)
class DiscoveryResult:
    """One bounded listing traversal and its minimal discovery records."""

    target: dict[str, Any]
    listing_path: str
    retrieved_at: str
    max_items: int
    page_count: int
    item_count: int
    listing_exhausted: bool
    stopped_reason: str
    last_after: str | None
    items: tuple[DiscoveryItem, ...]

    def manifest(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["format"] = "keivotos-reddit-api-discovery-v1"
        return payload


@dataclass(frozen=True)
class DiscoverySelection:
    """Validated ID selection loaded from a prior API discovery manifest."""

    path: str
    sha256: str
    target_url: str
    fullnames: frozenset[str]

    def identity(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "target_url": self.target_url,
            "item_count": len(self.fullnames),
        }


@dataclass(frozen=True)
class _JsonResponse:
    status: int
    headers: dict[str, str]
    payload: Any


Transport = Callable[[Request, float, int], _JsonResponse]


def _default_transport(
    request: Request,
    timeout: float,
    max_response_bytes: int,
) -> _JsonResponse:
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(max_response_bytes + 1)
            if len(body) > max_response_bytes:
                raise RedditApiError("Reddit API response exceeded the size limit")
            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise RedditApiError("Reddit API returned invalid JSON") from exc
            return _JsonResponse(
                status=int(response.status),
                headers={key.casefold(): value for key, value in response.headers.items()},
                payload=payload,
            )
    except HTTPError as exc:
        raise _HttpStatusError(
            int(exc.code),
            {key.casefold(): value for key, value in exc.headers.items()},
        ) from exc
    except URLError as exc:
        raise RedditApiError(f"Reddit API connection failed: {exc.reason}") from exc


def _float_header(headers: Mapping[str, str], name: str) -> float | None:
    value = headers.get(name.casefold())
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def _canonical_item(kind: str, payload: Any) -> DiscoveryItem | None:
    if kind not in {"t1", "t3"} or not isinstance(payload, dict):
        return None
    reddit_id = str(payload.get("id") or "").strip().lower()
    if not reddit_id:
        return None
    fullname = str(payload.get("name") or f"{kind}_{reddit_id}").strip().lower()
    if not fullname.startswith(f"{kind}_"):
        return None

    permalink = payload.get("permalink")
    if isinstance(permalink, str) and permalink.startswith("/"):
        canonical_url = f"https://www.reddit.com{permalink}"
    elif kind == "t3":
        canonical_url = f"https://www.reddit.com/comments/{reddit_id}/"
    else:
        link_id = str(payload.get("link_id") or "").removeprefix("t3_").lower()
        if not link_id:
            return None
        canonical_url = (
            f"https://www.reddit.com/comments/{quote(link_id)}/_/{quote(reddit_id)}/"
        )
    return DiscoveryItem(
        fullname=fullname,
        kind="post" if kind == "t3" else "comment",
        reddit_id=reddit_id,
        canonical_url=canonical_url,
    )


def _listing_request(target: CaptureTarget) -> tuple[str, dict[str, str]]:
    params: dict[str, str] = {"raw_json": "1"}
    if target.kind == "subreddit" and target.subreddit:
        listing = target.sort or "new"
        if listing not in {"new", "hot", "top", "controversial", "rising"}:
            raise RedditApiError(f"Unsupported subreddit listing: {listing}")
        if target.time_filter:
            params["t"] = target.time_filter
        return f"/r/{quote(target.subreddit, safe='')}/{listing}", params

    if target.kind == "search":
        if target.query is None:
            raise RedditApiError("Search discovery requires a query")
        params["q"] = target.query
        if target.subreddit:
            params["restrict_sr"] = "1"
            path = f"/r/{quote(target.subreddit, safe='')}/search"
        else:
            path = "/search"
        if target.sort:
            params["sort"] = target.sort
        if target.time_filter:
            params["t"] = target.time_filter
        return path, params

    if target.kind == "user" and target.username:
        listing = target.sort or "submitted"
        if listing not in {"overview", "submitted", "comments"}:
            raise RedditApiError(f"Unsupported user listing: {listing}")
        return f"/user/{quote(target.username, safe='')}/{listing}", params

    raise RedditApiError(
        "Official API discovery supports subreddit, search, and user listings"
    )


class RedditApiClient:
    """OAuth client that traverses one listing without bypassing its window."""

    def __init__(
        self,
        credentials: RedditApiCredentials,
        *,
        timeout: float = 30.0,
        max_retries: int = 3,
        max_wait_seconds: float = 600.0,
        transport: Transport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("Reddit API timeout must be positive")
        if max_retries < 0:
            raise ValueError("Reddit API max_retries cannot be negative")
        if max_wait_seconds < 0:
            raise ValueError("Reddit API max_wait_seconds cannot be negative")
        self.credentials = credentials
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_wait_seconds = max_wait_seconds
        self.transport = transport or _default_transport
        self.sleep = sleep
        self.now = now or (lambda: datetime.now(timezone.utc))
        self._access_token: str | None = None

    def _retry_delay(self, error: _HttpStatusError, attempt: int) -> float:
        retry_after = _float_header(error.headers, "retry-after")
        value = retry_after if retry_after is not None else float(2**attempt)
        return min(value, self.max_wait_seconds)

    def _send(self, request: Request) -> _JsonResponse:
        for attempt in range(self.max_retries + 1):
            try:
                return self.transport(request, self.timeout, MAX_RESPONSE_BYTES)
            except _HttpStatusError as exc:
                retryable = exc.status == 429 or 500 <= exc.status <= 599
                if not retryable or attempt >= self.max_retries:
                    raise RedditApiError(
                        f"Reddit API request failed with HTTP {exc.status}"
                    ) from exc
                self.sleep(self._retry_delay(exc, attempt))
        raise AssertionError("unreachable")

    def _token(self, *, refresh: bool = False) -> str:
        if self._access_token is not None and not refresh:
            return self._access_token
        basic = base64.b64encode(
            f"{self.credentials.client_id}:{self.credentials.client_secret}".encode(
                "utf-8"
            )
        ).decode("ascii")
        request = Request(
            TOKEN_URL,
            data=urlencode({"grant_type": "client_credentials"}).encode("ascii"),
            method="POST",
            headers={
                "Authorization": f"Basic {basic}",
                "User-Agent": self.credentials.user_agent,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        response = self._send(request)
        if not isinstance(response.payload, dict):
            raise RedditApiError("Reddit OAuth returned an invalid token response")
        token = response.payload.get("access_token")
        token_type = str(response.payload.get("token_type") or "bearer").casefold()
        if not isinstance(token, str) or not token or token_type != "bearer":
            raise RedditApiError("Reddit OAuth did not return a bearer token")
        self._access_token = token
        return token

    def _listing_page(
        self,
        path: str,
        params: Mapping[str, str],
        *,
        refresh_on_unauthorized: bool = True,
    ) -> _JsonResponse:
        query = urlencode(params)
        request = Request(
            f"{API_ORIGIN}{path}?{query}",
            method="GET",
            headers={
                "Authorization": f"Bearer {self._token()}",
                "User-Agent": self.credentials.user_agent,
            },
        )
        try:
            return self._send(request)
        except RedditApiError as exc:
            cause = exc.__cause__
            if (
                refresh_on_unauthorized
                and isinstance(cause, _HttpStatusError)
                and cause.status == 401
            ):
                self._token(refresh=True)
                return self._listing_page(
                    path, params, refresh_on_unauthorized=False
                )
            raise

    def discover(
        self,
        target: CaptureTarget,
        *,
        max_items: int = MAX_LISTING_ITEMS,
    ) -> DiscoveryResult:
        if not 1 <= max_items <= MAX_LISTING_ITEMS:
            raise ValueError(
                f"Reddit API discovery limit must be between 1 and {MAX_LISTING_ITEMS}"
            )
        path, base_params = _listing_request(target)
        after: str | None = None
        seen_cursors: set[str] = set()
        seen_items: set[str] = set()
        items: list[DiscoveryItem] = []
        page_count = 0
        listing_exhausted = False
        stopped_reason = "item_limit"

        while len(items) < max_items:
            params = dict(base_params)
            params["limit"] = str(min(MAX_PAGE_SIZE, max_items - len(items)))
            params["count"] = str(len(items))
            if after:
                params["after"] = after
            response = self._listing_page(path, params)
            page_count += 1
            payload = response.payload
            data = payload.get("data") if isinstance(payload, dict) else None
            children = data.get("children") if isinstance(data, dict) else None
            if not isinstance(children, list):
                raise RedditApiError("Reddit listing response has no children array")

            for child in children:
                if not isinstance(child, dict):
                    continue
                item = _canonical_item(str(child.get("kind") or ""), child.get("data"))
                if item is None or item.fullname in seen_items:
                    continue
                seen_items.add(item.fullname)
                items.append(item)
                if len(items) >= max_items:
                    break

            next_after = data.get("after")
            if not children:
                listing_exhausted = True
                stopped_reason = "empty_page"
                after = None
                break
            if not isinstance(next_after, str) or not next_after:
                listing_exhausted = True
                stopped_reason = "listing_exhausted"
                after = None
                break
            if next_after in seen_cursors:
                stopped_reason = "repeated_cursor"
                after = next_after
                break
            seen_cursors.add(next_after)
            after = next_after

            remaining = _float_header(response.headers, "x-ratelimit-remaining")
            reset = _float_header(response.headers, "x-ratelimit-reset")
            if (
                remaining is not None
                and remaining < 1.0
                and reset is not None
                and len(items) < max_items
            ):
                self.sleep(min(reset, self.max_wait_seconds))

        retrieved_at = self.now().astimezone(timezone.utc).isoformat()
        return DiscoveryResult(
            target=target.as_dict(),
            listing_path=path,
            retrieved_at=retrieved_at,
            max_items=max_items,
            page_count=page_count,
            item_count=len(items),
            listing_exhausted=listing_exhausted,
            stopped_reason=stopped_reason,
            last_after=after,
            items=tuple(items),
        )


def default_discovery_path(
    root: Path,
    target: CaptureTarget,
    *,
    now: datetime | None = None,
) -> Path:
    """Choose a readable, collision-resistant discovery filename."""
    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    identity = target.subreddit or target.username or target.kind
    slug = "".join(character if character.isalnum() else "-" for character in identity)
    slug = slug.strip("-").lower() or "target"
    return (
        Path(root)
        / "discovery"
        / f"{timestamp.strftime('%Y%m%dT%H%M%SZ')}-{slug}-{uuid4().hex[:8]}.json"
    )


def write_discovery_manifest(path: Path, result: DiscoveryResult) -> Path:
    """Write a minimal API discovery manifest without overwriting prior data."""
    path = Path(path).expanduser().resolve(strict=False)
    encoded = (
        json.dumps(result.manifest(), indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise DiscoveryOutputExistsError(
            f"Discovery output already exists and will not be overwritten: {path}"
        ) from exc
    return path


def read_discovery_manifest(
    path: Path,
    *,
    target: CaptureTarget,
) -> DiscoverySelection:
    """Load the minimal ID set used to filter local submission/comment dumps."""
    path = Path(path).expanduser().resolve(strict=True)
    if not path.is_file():
        raise RedditApiError(f"Discovery manifest is not a file: {path}")
    if path.stat().st_size > MAX_RESPONSE_BYTES:
        raise RedditApiError("Discovery manifest exceeds the 16 MiB safety limit")
    encoded = path.read_bytes()
    try:
        payload = json.loads(encoded.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RedditApiError(f"Discovery manifest is invalid JSON: {path}") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("format") != "keivotos-reddit-api-discovery-v1"
    ):
        raise RedditApiError("Unsupported Reddit API discovery manifest format")
    manifest_target = payload.get("target")
    target_url = (
        str(manifest_target.get("canonical_url") or "")
        if isinstance(manifest_target, dict)
        else ""
    )
    if target_url != target.canonical_url:
        raise RedditApiError(
            "Discovery manifest target does not match the local import target"
        )
    values = payload.get("items")
    if not isinstance(values, list):
        raise RedditApiError("Discovery manifest has no items array")
    fullnames: set[str] = set()
    for item in values:
        fullname = (
            str(item.get("fullname") or "").strip().lower()
            if isinstance(item, dict)
            else ""
        )
        if not FULLNAME_RE.fullmatch(fullname):
            raise RedditApiError(
                f"Discovery manifest contains an invalid fullname: {fullname!r}"
            )
        fullnames.add(fullname)
    if len(fullnames) > MAX_LISTING_ITEMS:
        raise RedditApiError("Discovery manifest exceeds the 1000-item safety cap")
    return DiscoverySelection(
        path=str(path),
        sha256=hashlib.sha256(encoded).hexdigest(),
        target_url=target_url,
        fullnames=frozenset(fullnames),
    )
