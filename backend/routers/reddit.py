"""Read-only HTTP surface for the optional local Reddit archive."""
from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

import config
from database import get_user_db
from files_base import index as files_index
from files_base import serving, sources as files_sources
from modules.reddit.archive import ArchiveError
from modules.reddit.arctic_shift_api import ArcticShiftApiClient, ArcticShiftApiError
from modules.reddit.comment_trees import CommentTreeError
from modules.reddit.community import CommunityError
from modules.reddit.direct_capture import capture_direct_target
from modules.reddit.download_jobs import (
    RedditDownloadJobError,
    RedditDownloadJobs,
)
from modules.reddit.library import (
    DEFAULT_MAX_THREAD_COMMENTS,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    RedditLibrary,
    RedditLibraryError,
)
from modules.reddit.links import extract_outbound_links
from modules.reddit.media import (
    DEFAULT_MAX_FILE_BYTES,
    DEFAULT_MAX_FILES,
    DEFAULT_MAX_RUN_BYTES,
    DEFAULT_MIN_FREE_BYTES,
    IMAGE_ROLES,
    LINKED_FILE_ROLES,
    VIDEO_ROLES,
    MediaConfirmationError,
    MediaError,
    MediaLimits,
    build_media_plan,
    download_media,
    ensure_linked_assets,
)
from modules.reddit.url_targets import TargetParseError, parse_capture_target
import suite_modules


router = APIRouter(prefix="/api/reddit", tags=["reddit"])
REDDIT_DESCRIPTOR = config.MODULE_REGISTRY.require("reddit")
MEDIA_ROOT = REDDIT_DESCRIPTOR.home / "media"
_CAPTURE_LOCK = Lock()
_MEDIA_LOCK = Lock()
_DOWNLOAD_JOBS = RedditDownloadJobs()


class RedditFeedResponse(BaseModel):
    format: str
    items: list[dict[str, Any]] = Field(default_factory=list)
    next_cursor: str | None = None
    has_more: bool = False


class RedditSearchResponse(BaseModel):
    format: str
    query: str
    items: list[dict[str, Any]] = Field(default_factory=list)


class RedditPostResponse(BaseModel):
    format: str
    post: dict[str, Any]
    media: dict[str, Any]
    observations: list[dict[str, Any]]
    comment_tree: dict[str, Any]


class RedditCommunityResponse(BaseModel):
    format: str
    subreddit: str
    about: dict[str, Any] | None = None
    rules: dict[str, Any] | None = None
    wiki: list[dict[str, Any]] = Field(default_factory=list)
    moderators: dict[str, Any] | None = None
    media: dict[str, Any]
    history: dict[str, int]


class RedditStatusResponse(BaseModel):
    format: str
    initialized: bool
    database_path: str
    counts: dict[str, int]
    jobs: list[dict[str, Any]] = Field(default_factory=list)
    storage: dict[str, str]
    limits: dict[str, int]
    runtime: dict[str, bool]


class RedditCaptureRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


class RedditCaptureResponse(BaseModel):
    format: str
    capture: dict[str, Any]
    imports: list[dict[str, Any]] = Field(default_factory=list)
    indexed: dict[str, Any]


class RedditMediaSelection(BaseModel):
    target_kind: Literal["post", "subreddit"]
    target_id: str = Field(min_length=1, max_length=100)
    images: bool = False
    videos: bool = False
    linked_files: bool = False
    retry_failed: bool = False


class RedditMediaDownloadRequest(RedditMediaSelection):
    confirm_assets: int = Field(ge=0, le=DEFAULT_MAX_FILES)
    confirm_selection: str = Field(min_length=64, max_length=64)


class RedditMediaPlanResponse(BaseModel):
    format: str
    plan: dict[str, Any]


class RedditMediaDownloadResponse(BaseModel):
    format: str
    plan: dict[str, Any]
    download: dict[str, Any]
    files: dict[str, Any]


def _require_enabled() -> None:
    with get_user_db() as connection:
        suite_modules.ensure_schema(connection)
        enabled = suite_modules.enabled_ids(connection)
    if REDDIT_DESCRIPTOR.slug not in enabled:
        raise HTTPException(status_code=409, detail="Reddit module is disabled")


def _library() -> RedditLibrary:
    return RedditLibrary(REDDIT_DESCRIPTOR.database)


def _translate_library_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/feed", response_model=RedditFeedResponse)
def feed(
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    cursor: str | None = Query(None),
    subreddit: str | None = Query(None),
    author: str | None = Query(None),
    flair: str | None = Query(None),
    sort: Literal["new", "popular"] = Query("new"),
) -> dict[str, Any]:
    _require_enabled()
    try:
        return _library().list_posts(
            limit=limit,
            cursor=cursor,
            subreddit=subreddit,
            author=author,
            flair=flair,
            sort=sort,
        )
    except (RedditLibraryError, ValueError) as exc:
        raise _translate_library_error(exc) from exc


@router.get("/search", response_model=RedditSearchResponse)
def search(
    q: str = Query(..., min_length=1, max_length=500),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    subreddit: str | None = Query(None),
    author: str | None = Query(None),
    record_type: str = Query("all", pattern="^(all|post|comment)$"),
) -> dict[str, Any]:
    _require_enabled()
    try:
        return _library().search(
            q,
            limit=limit,
            subreddit=subreddit,
            author=author,
            record_type=record_type,
        )
    except (RedditLibraryError, ValueError) as exc:
        raise _translate_library_error(exc) from exc


@router.get("/posts/{post_id}", response_model=RedditPostResponse)
def post(
    post_id: str,
    max_comments: int = Query(
        DEFAULT_MAX_THREAD_COMMENTS,
        ge=1,
        le=DEFAULT_MAX_THREAD_COMMENTS,
    ),
) -> dict[str, Any]:
    _require_enabled()
    try:
        result = _library().get_post(post_id, max_comments=max_comments)
    except (CommentTreeError, RedditLibraryError, ValueError) as exc:
        raise _translate_library_error(exc) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Saved Reddit post not found")
    return result


@router.get(
    "/community/{subreddit}",
    response_model=RedditCommunityResponse,
)
def community(subreddit: str) -> dict[str, Any]:
    _require_enabled()
    try:
        return _library().get_community(subreddit)
    except (RedditLibraryError, ValueError) as exc:
        raise _translate_library_error(exc) from exc


@router.get("/communities")
def communities() -> dict[str, Any]:
    _require_enabled()
    return {
        "format": "keivotos-reddit-communities-v1",
        "items": _library().list_communities(),
    }


@router.get("/profiles")
def profiles() -> dict[str, Any]:
    _require_enabled()
    return {
        "format": "keivotos-reddit-profiles-v1",
        "items": _library().list_profiles(),
    }


@router.get("/profiles/{username}")
def profile(username: str) -> dict[str, Any]:
    _require_enabled()
    try:
        return _library().get_profile(username)
    except (RedditLibraryError, ValueError) as exc:
        raise _translate_library_error(exc) from exc


@router.get("/status", response_model=RedditStatusResponse)
def status() -> dict[str, Any]:
    _require_enabled()
    try:
        result = _library().status()
    except RedditLibraryError as exc:
        raise _translate_library_error(exc) from exc
    result["storage"] = {
        "archive": str(REDDIT_DESCRIPTOR.home),
        "media": str(MEDIA_ROOT),
        "files_library": str(MEDIA_ROOT / "library"),
    }
    result["limits"] = {
        "max_files": DEFAULT_MAX_FILES,
        "max_file_bytes": DEFAULT_MAX_FILE_BYTES,
        "max_run_bytes": DEFAULT_MAX_RUN_BYTES,
        "min_free_bytes": DEFAULT_MIN_FREE_BYTES,
        "max_thread_comments": DEFAULT_MAX_THREAD_COMMENTS,
    }
    result["runtime"] = {
        "capture_busy": _CAPTURE_LOCK.locked(),
        "download_busy": _MEDIA_LOCK.locked() or _DOWNLOAD_JOBS.busy(),
    }
    return result


@router.post(
    "/capture",
    response_model=RedditCaptureResponse,
    status_code=201,
)
def capture_link(payload: RedditCaptureRequest) -> dict[str, Any]:
    _require_enabled()
    try:
        target = parse_capture_target(payload.url)
    except TargetParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if target.kind not in {"post", "subreddit", "user"}:
        raise HTTPException(
            status_code=400,
            detail="Enter one Reddit post, subreddit, or public user URL",
        )
    if not _CAPTURE_LOCK.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail="Another Reddit link is already being saved",
        )
    try:
        client = ArcticShiftApiClient()
        result = capture_direct_target(
            target,
            database_path=REDDIT_DESCRIPTOR.database,
            output_root=REDDIT_DESCRIPTOR.home / "archives" / "direct",
            media_directory=MEDIA_ROOT,
            client=client,
        )
        indexed = result.get("indexed") or {}
        if (
            target.kind == "post"
            and (
                indexed.get("target_id") != target.post_id
                or int(indexed.get("posts", 0)) != 1
            )
        ):
            raise ArchiveError(
                "Capture finished without proving that the requested post "
                "was indexed"
            )
        if (
            target.kind == "user"
            and (
                indexed.get("target_kind") != "user"
                or str(indexed.get("target_id", "")).casefold()
                != str(target.username or "").casefold()
            )
        ):
            raise ArchiveError(
                "Capture finished without proving that the requested user "
                "profile was indexed"
            )
        return result
    except (TargetParseError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ArcticShiftApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except (ArchiveError, CommunityError) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Reddit data was preserved but could not be indexed: {exc}",
        ) from exc
    finally:
        _CAPTURE_LOCK.release()


@router.post("/posts/{post_id}/refresh", response_model=RedditCaptureResponse)
def refresh_post(post_id: str) -> dict[str, Any]:
    _require_enabled()
    return capture_link(
        RedditCaptureRequest(
            url=f"https://www.reddit.com/comments/{post_id.strip()}/"
        )
    )


@router.post(
    "/community/{subreddit}/refresh",
    response_model=RedditCaptureResponse,
)
def refresh_community(subreddit: str) -> dict[str, Any]:
    _require_enabled()
    return capture_link(
        RedditCaptureRequest(
            url=f"https://www.reddit.com/r/{subreddit.strip()}/"
        )
    )


def _media_roles(payload: RedditMediaSelection) -> set[str]:
    roles: set[str] = set()
    if payload.images:
        roles.update(IMAGE_ROLES)
    if payload.videos:
        roles.update(VIDEO_ROLES)
    if payload.linked_files:
        roles.update(LINKED_FILE_ROLES)
    if not roles:
        raise HTTPException(
            status_code=400,
            detail="Select images/GIFs, videos, or linked files",
        )
    return roles


def _media_plan(payload: RedditMediaSelection):
    roles = _media_roles(payload)
    target_id = payload.target_id.strip()
    if payload.linked_files:
        ensure_linked_assets(
            REDDIT_DESCRIPTOR.database,
            scope_type=payload.target_kind,
            scope_id=target_id,
        )
    return build_media_plan(
        REDDIT_DESCRIPTOR.database,
        MEDIA_ROOT,
        MediaLimits(
            max_files=DEFAULT_MAX_FILES,
            max_file_bytes=DEFAULT_MAX_FILE_BYTES,
            max_run_bytes=DEFAULT_MAX_RUN_BYTES,
            min_free_bytes=DEFAULT_MIN_FREE_BYTES,
        ),
        roles=roles,
        retry_failed=payload.retry_failed,
        scope_type=payload.target_kind,
        scope_id=target_id,
    )


def _publish_downloads_to_files() -> dict[str, Any]:
    library_root = MEDIA_ROOT / "library"
    if not library_root.is_dir():
        return {"published": False, "source_id": None, "scan": None}
    with get_user_db() as user_connection:
        REDDIT_DESCRIPTOR.publish(user_connection)
        source_id = files_sources.deterministic_source_id(library_root)
        source = files_sources.get_source(user_connection, source_id)
        all_sources = files_sources.list_sources(user_connection)
    if source is None:
        return {"published": False, "source_id": None, "scan": None}
    excluded = [
        Path(candidate.path)
        for candidate in files_sources.descendant_sources(source, all_sources)
    ]
    with files_index.open_index(config.FILES_DB_PATH) as index_connection:
        scan = files_index.scan_source(
            index_connection,
            source.source_id,
            Path(source.path),
            excluded_roots=excluded,
        )
    return {"published": True, "source_id": source.source_id, "scan": scan}


@router.post("/media/plan", response_model=RedditMediaPlanResponse)
def media_plan(payload: RedditMediaSelection) -> dict[str, Any]:
    _require_enabled()
    try:
        plan = _media_plan(payload)
    except (MediaError, OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "format": "keivotos-reddit-media-plan-v1",
        "plan": plan.summary(),
    }


@router.post("/media/download", response_model=RedditMediaDownloadResponse)
def media_download(payload: RedditMediaDownloadRequest) -> dict[str, Any]:
    _require_enabled()
    if not _MEDIA_LOCK.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail="Another Reddit media download is already running",
        )
    try:
        plan = _media_plan(payload)
        summary = download_media(
            plan,
            confirm_assets=payload.confirm_assets,
            confirm_selection=payload.confirm_selection,
        )
        files = _publish_downloads_to_files()
        return {
            "format": "keivotos-reddit-media-download-v1",
            "plan": plan.summary(),
            "download": summary.as_dict(),
            "files": files,
        }
    except MediaConfirmationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (MediaError, OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        _MEDIA_LOCK.release()


@router.post("/media/jobs", status_code=202)
def start_media_job(payload: RedditMediaDownloadRequest) -> dict[str, Any]:
    """Start a confirmed transfer whose progress survives closing the drawer."""
    _require_enabled()
    if _MEDIA_LOCK.locked():
        raise HTTPException(
            status_code=409,
            detail="Another Reddit media download is already running",
        )
    try:
        plan = _media_plan(payload)
        if payload.confirm_assets != plan.selected_assets:
            raise MediaConfirmationError(
                f"Plan currently selects {plan.selected_assets} assets; "
                f"confirmation selected {payload.confirm_assets}"
            )
        if (
            payload.confirm_selection.casefold()
            != plan.selection_sha256.casefold()
        ):
            raise MediaConfirmationError(
                "The selected asset set changed; review the download plan again"
            )
        if not plan.can_start:
            raise MediaError("Free-space guard prevents starting this media run")

        def run(progress):
            if not _MEDIA_LOCK.acquire(blocking=False):
                raise MediaError(
                    "Another Reddit media download is already running"
                )
            try:
                summary = download_media(
                    plan,
                    confirm_assets=payload.confirm_assets,
                    confirm_selection=payload.confirm_selection,
                    on_progress=progress,
                )
                files = _publish_downloads_to_files()
                return {
                    "format": "keivotos-reddit-media-download-v1",
                    "plan": plan.summary(),
                    "download": summary.as_dict(),
                    "files": files,
                }
            finally:
                _MEDIA_LOCK.release()

        job = _DOWNLOAD_JOBS.start(
            target_kind=payload.target_kind,
            target_id=payload.target_id,
            planned=plan.selected_assets,
            runner=run,
        )
    except MediaConfirmationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RedditDownloadJobError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (MediaError, OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"format": "keivotos-reddit-media-job-v1", "job": job}


@router.get("/media/jobs")
def media_jobs() -> dict[str, Any]:
    _require_enabled()
    return {
        "format": "keivotos-reddit-media-jobs-v1",
        "jobs": _DOWNLOAD_JOBS.jobs(),
    }


@router.get("/media/jobs/{job_id}")
def media_job(job_id: str) -> dict[str, Any]:
    _require_enabled()
    try:
        job = _DOWNLOAD_JOBS.job(job_id)
    except RedditDownloadJobError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"format": "keivotos-reddit-media-job-v1", "job": job}


def _media_path(record: dict[str, Any]) -> Path:
    root = MEDIA_ROOT.resolve(strict=False)
    local_path = record.get("local_path")
    candidate = (
        Path(str(local_path))
        if local_path
        else root / str(record["relative_path"])
    )
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=404,
            detail="Local Reddit media is unavailable",
        ) from exc
    if not resolved.is_file() or resolved.stat().st_size != int(record["byte_size"]):
        raise HTTPException(
            status_code=404,
            detail="Local Reddit media is unavailable",
        )
    return resolved


@router.get("/media/{sha256}")
def media(sha256: str, request: Request):
    _require_enabled()
    try:
        record = _library().media_object(sha256)
    except (RedditLibraryError, ValueError) as exc:
        raise _translate_library_error(exc) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Local Reddit media not found")
    resolved = _media_path(record)
    content_type = str(record.get("content_type") or "application/octet-stream")
    inline = content_type.startswith(("image/", "video/", "audio/"))
    source_links = (
        extract_outbound_links(record.get("url"), None)
        if record.get("url")
        else ()
    )
    download_name = (
        source_links[0].label
        if source_links
        else resolved.name
    )
    if not Path(download_name).suffix and resolved.suffix:
        download_name += resolved.suffix
    headers = {
        "Accept-Ranges": "bytes",
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": serving.content_disposition(
            download_name,
            inline=inline,
        ),
        "Cache-Control": "private, max-age=31536000, immutable",
    }
    file_size = resolved.stat().st_size
    range_header = request.headers.get("range")
    byte_range = serving.parse_range_header(range_header, file_size)
    if range_header and byte_range is None:
        return Response(
            status_code=416,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Range": f"bytes */{file_size}",
            },
        )
    if byte_range is not None:
        start, end = byte_range
        return StreamingResponse(
            serving.file_range_iter(resolved, start, end),
            status_code=206,
            media_type=content_type,
            headers={
                **headers,
                "Content-Length": str(end - start + 1),
                "Content-Range": f"bytes {start}-{end}/{file_size}",
            },
        )
    return FileResponse(
        resolved,
        media_type=content_type,
        headers=headers,
    )
