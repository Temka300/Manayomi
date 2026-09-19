"""Build a searchable Reddit archive from a URL or local source.

Direct post/subreddit capture uses bounded Arctic Shift JSON endpoints and
preserves every response before feeding generated sources through the same
local archive importers. The optional official Reddit API mode saves only a
minimal ID/URL discovery manifest. No mode downloads media.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys


DEFAULT_LOCAL_POSTS = 5000
DEFAULT_POSTS_SENTINEL = object()


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from modules.reddit.archive import (  # noqa: E402
    ArchiveError,
    CaptureOptions,
    LocalSourceOptions,
    ResumeRequiredError,
    import_local_source,
)
from config import MODULE_REGISTRY  # noqa: E402
from modules.reddit.arctic_shift import (  # noqa: E402
    ArcticShiftError,
    parse_utc_boundary,
)
from modules.reddit.arctic_shift_api import (  # noqa: E402
    DEFAULT_MAX_COMMENTS as DEFAULT_ARCTIC_MAX_COMMENTS,
    DEFAULT_MAX_RESPONSE_BYTES as DEFAULT_ARCTIC_MAX_RESPONSE_BYTES,
    DEFAULT_MAX_WIKI_PAGES as DEFAULT_ARCTIC_MAX_WIKI_PAGES,
    DEFAULT_TIMEOUT as DEFAULT_ARCTIC_TIMEOUT,
    MAX_COMMENTS as MAX_ARCTIC_COMMENTS,
    MAX_WIKI_PAGES as MAX_ARCTIC_WIKI_PAGES,
    ArcticShiftApiClient,
    ArcticShiftApiError,
)
from modules.reddit.community import (  # noqa: E402
    CommunityError,
)
from modules.reddit.direct_capture import capture_direct_target  # noqa: E402
from modules.reddit.reddit_api import (  # noqa: E402
    MAX_LISTING_ITEMS,
    RedditApiClient,
    RedditApiCredentials,
    RedditApiError,
    default_discovery_path,
    read_discovery_manifest,
    write_discovery_manifest,
)
from modules.reddit.url_targets import (  # noqa: E402
    TargetParseError,
    parse_capture_target,
)


REDDIT_MODULE = MODULE_REGISTRY.require("reddit")


def path_arg(value: str) -> Path:
    return Path(value).expanduser()


def post_limit_arg(value: str) -> int | None:
    if value.casefold() == "all":
        return None
    try:
        limit = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("posts must be a positive integer or 'all'") from exc
    if limit <= 0:
        raise argparse.ArgumentTypeError("posts must be a positive integer or 'all'")
    return limit


def positive_int_arg(value: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be a positive integer") from exc
    if result <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return result


def nonnegative_int_arg(value: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "value must be a non-negative integer"
        ) from exc
    if result < 0:
        raise argparse.ArgumentTypeError("value must be a non-negative integer")
    return result


def _project_path(value: Path) -> Path:
    if value.is_absolute():
        return value
    return PROJECT_ROOT / value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Capture one Reddit post or one subreddit's community metadata "
            "through Arctic Shift, import local JSON/.zst evidence, or discover "
            "a bounded official API listing."
        )
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument(
        "--url",
        help=(
            "Reddit, redd.it, asset, or external URL that defines the "
            "capture scope. Web-archive URLs are rejected."
        ),
    )
    target.add_argument(
        "--subreddit",
        help="Subreddit name, with or without an r/ prefix.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--source-file",
        type=path_arg,
        help=(
            "Local .json, .jsonl, .ndjson, gzip JSONL, or Arctic Shift .zst "
            "source."
        ),
    )
    source.add_argument(
        "--arctic-shift-api",
        action="store_true",
        help=(
            "Capture one post or subreddit community snapshot from bounded "
            "Arctic Shift JSON endpoints, preserving exact responses first."
        ),
    )
    source.add_argument(
        "--reddit-api",
        action="store_true",
        help=(
            "Use the official OAuth API only to save a minimal current "
            "ID/URL discovery manifest."
        ),
    )
    parser.add_argument(
        "--arctic-output-root",
        type=path_arg,
        help=(
            "Create-only direct-response bundle root. Default: "
            "<database directory>/archives/direct."
        ),
    )
    parser.add_argument(
        "--arctic-timeout",
        type=float,
        default=DEFAULT_ARCTIC_TIMEOUT,
        help=f"Arctic Shift request timeout. Default: {DEFAULT_ARCTIC_TIMEOUT:g}.",
    )
    parser.add_argument(
        "--arctic-max-response-bytes",
        type=positive_int_arg,
        default=DEFAULT_ARCTIC_MAX_RESPONSE_BYTES,
        help="Maximum bytes accepted from any one Arctic Shift response.",
    )
    parser.add_argument(
        "--arctic-max-comments",
        type=positive_int_arg,
        default=DEFAULT_ARCTIC_MAX_COMMENTS,
        help=f"Maximum requested comment-tree size, capped at {MAX_ARCTIC_COMMENTS}.",
    )
    parser.add_argument(
        "--arctic-max-wiki-pages",
        type=nonnegative_int_arg,
        default=DEFAULT_ARCTIC_MAX_WIKI_PAGES,
        help=f"Maximum wiki pages, capped at {MAX_ARCTIC_WIKI_PAGES}.",
    )
    parser.add_argument(
        "--posts",
        type=post_limit_arg,
        default=DEFAULT_POSTS_SENTINEL,
        help=(
            "Maximum distinct post IDs for local import, or 'all'. "
            f"Default: {DEFAULT_LOCAL_POSTS}. In API mode an explicit integer "
            "also sets the discovery limit, capped at 1000."
        ),
    )
    parser.add_argument(
        "--comments",
        choices=("none", "all"),
        default="all",
        help="Normalize all matching comments or preserve them only as raw records.",
    )
    parser.add_argument(
        "--save-images",
        choices=("none", "preview", "original", "both"),
        default="none",
        help="Record the desired image policy; local import queues but never downloads.",
    )
    parser.add_argument(
        "--save-videos",
        choices=("none", "manifest", "full"),
        default="none",
        help="Record the desired video policy; local import queues but never downloads.",
    )
    parser.add_argument("--save-avatars", action="store_true")
    parser.add_argument("--save-subreddit-assets", action="store_true")
    parser.add_argument("--save-wiki", action="store_true")
    parser.add_argument("--save-rules", action="store_true")
    parser.add_argument("--save-mod-list", action="store_true")
    parser.add_argument(
        "--save-external-assets",
        action="store_true",
        help="Queue only URLs whose host matches an --external-domain allowlist.",
    )
    parser.add_argument(
        "--external-domain",
        action="append",
        default=[],
        help="Allowlisted external host or parent domain. Repeatable.",
    )
    parser.add_argument(
        "--database",
        type=path_arg,
        default=REDDIT_MODULE.database,
        help="Rebuildable SQLite index. Relative paths use the project root.",
    )
    parser.add_argument(
        "--media-directory",
        type=path_arg,
        default=REDDIT_MODULE.home / "media",
        help=(
            "Future media destination stored in the job manifest. "
            "The current capture slices do not create or write it."
        ),
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume or inspect the same source/target/options job.",
    )
    parser.add_argument(
        "--source-format",
        choices=("auto", "arctic-zst"),
        default="auto",
        help="Validate automatic source detection or require an Arctic Shift .zst.",
    )
    parser.add_argument(
        "--source-scope",
        choices=("scoped", "global"),
        default="scoped",
        help=(
            "For .zst: preserve every date-matching record from an already "
            "scoped dump, or pre-filter a global dump to the target."
        ),
    )
    parser.add_argument(
        "--after",
        metavar="YYYY-MM-DD",
        help="For .zst: include records at or after midnight UTC.",
    )
    parser.add_argument(
        "--before",
        metavar="YYYY-MM-DD",
        help="For .zst: exclude records at or after midnight UTC.",
    )
    parser.add_argument(
        "--expected-sha256",
        help="For .zst: verify this 64-digit source digest before archive writes.",
    )
    parser.add_argument(
        "--coverage-json",
        type=path_arg,
        help=(
            "For .zst: additionally create this coverage report. Every job "
            "also keeps coverage.json beside its raw chunks."
        ),
    )
    parser.add_argument(
        "--discovery-manifest",
        type=path_arg,
        help=(
            "For .zst: preserve only posts named by this official API "
            "discovery file, plus comments whose link_id names those posts."
        ),
    )
    parser.add_argument(
        "--reddit-max-items",
        type=int,
        help="Official API discovery limit, 1-1000. Default: 1000.",
    )
    parser.add_argument(
        "--reddit-api-output",
        type=path_arg,
        help=(
            "Create the API discovery JSON at this path. The default is a "
            "unique file under the Reddit module's discovery directory."
        ),
    )
    parser.add_argument(
        "--reddit-timeout",
        type=float,
        default=30.0,
        help="Official API request timeout in seconds. Default: 30.",
    )
    return parser


def _run_api_discovery(
    args: argparse.Namespace,
    capture_target,
) -> int:
    if args.resume:
        raise RedditApiError("--resume applies only to local archive imports")
    if any(
        (
            args.arctic_output_root is not None,
            args.arctic_timeout != DEFAULT_ARCTIC_TIMEOUT,
            args.arctic_max_response_bytes != DEFAULT_ARCTIC_MAX_RESPONSE_BYTES,
            args.arctic_max_comments != DEFAULT_ARCTIC_MAX_COMMENTS,
            args.arctic_max_wiki_pages != DEFAULT_ARCTIC_MAX_WIKI_PAGES,
            args.source_format != "auto",
            args.source_scope != "scoped",
            args.after is not None,
            args.before is not None,
            args.expected_sha256 is not None,
            args.coverage_json is not None,
            args.discovery_manifest is not None,
        )
    ):
        raise RedditApiError(
            "Local source format, scope, date, hash, coverage, and discovery flags "
            "cannot be used with --reddit-api"
        )
    if (
        args.reddit_max_items is not None
        and args.posts is not DEFAULT_POSTS_SENTINEL
    ):
        raise RedditApiError(
            "Use either --posts or --reddit-max-items for API discovery, not both"
        )
    if any(
        (
            args.comments != "all",
            args.save_images != "none",
            args.save_videos != "none",
            args.save_avatars,
            args.save_subreddit_assets,
            args.save_wiki,
            args.save_rules,
            args.save_mod_list,
            args.save_external_assets,
            bool(args.external_domain),
        )
    ):
        raise RedditApiError(
            "Media, comment, and community preservation flags require a local "
            "archive source; API mode saves only IDs and URLs"
        )
    if args.reddit_max_items is not None:
        max_items = args.reddit_max_items
    elif args.posts is DEFAULT_POSTS_SENTINEL or args.posts is None:
        max_items = MAX_LISTING_ITEMS
    else:
        max_items = args.posts

    credentials = RedditApiCredentials.from_environment()
    client = RedditApiClient(credentials, timeout=args.reddit_timeout)
    result = client.discover(capture_target, max_items=max_items)
    output_path = (
        _project_path(args.reddit_api_output).resolve(strict=False)
        if args.reddit_api_output is not None
        else default_discovery_path(
            REDDIT_MODULE.home, capture_target
        ).resolve(strict=False)
    )
    write_discovery_manifest(output_path, result)
    print(
        json.dumps(
            {
                "mode": "reddit-api-discovery",
                "output_path": str(output_path),
                "page_count": result.page_count,
                "item_count": result.item_count,
                "max_items": result.max_items,
                "listing_exhausted": result.listing_exhausted,
                "stopped_reason": result.stopped_reason,
                "last_after": result.last_after,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def _external_domains(args: argparse.Namespace) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                value.strip().casefold().lstrip(".")
                for value in args.external_domain
                if value.strip()
            }
        )
    )


def _reject_non_arctic_flags(args: argparse.Namespace) -> None:
    if args.resume:
        raise ArcticShiftApiError(
            "--resume is not used for atomic direct-response bundles"
        )
    if args.posts is not DEFAULT_POSTS_SENTINEL:
        raise ArcticShiftApiError(
            "--posts does not apply to one-post or community-only direct capture"
        )
    if any(
        (
            args.source_format != "auto",
            args.source_scope != "scoped",
            args.after is not None,
            args.before is not None,
            args.expected_sha256 is not None,
            args.coverage_json is not None,
            args.discovery_manifest is not None,
        )
    ):
        raise ArcticShiftApiError(
            "Local source format, scope, date, hash, coverage, and discovery "
            "flags cannot be used with --arctic-shift-api"
        )
    if any(
        (
            args.reddit_max_items is not None,
            args.reddit_api_output is not None,
            args.reddit_timeout != 30.0,
        )
    ):
        raise ArcticShiftApiError(
            "Official Reddit API flags cannot be used with --arctic-shift-api"
        )


def _run_arctic_shift_capture(
    args: argparse.Namespace,
    capture_target,
) -> int:
    _reject_non_arctic_flags(args)
    if capture_target.kind not in {"post", "subreddit"}:
        raise ArcticShiftApiError(
            "--arctic-shift-api accepts only a Reddit post or subreddit URL"
        )
    if capture_target.kind == "subreddit" and any(
        (
            args.comments != "all",
            args.save_images != "none",
            args.save_videos != "none",
            args.save_external_assets,
            bool(args.external_domain),
        )
    ):
        raise ArcticShiftApiError(
            "Post/comment/media policy flags do not apply to a "
            "community-only subreddit capture"
        )
    database_path = _project_path(args.database).resolve(strict=False)
    output_root = (
        _project_path(args.arctic_output_root).resolve(strict=False)
        if args.arctic_output_root is not None
        else database_path.parent / "archives" / "direct"
    )
    client = ArcticShiftApiClient(
        timeout=args.arctic_timeout,
        max_response_bytes=args.arctic_max_response_bytes,
    )
    result = capture_direct_target(
        capture_target,
        database_path=database_path,
        output_root=output_root,
        media_directory=_project_path(args.media_directory).resolve(strict=False),
        client=client,
        max_comments=args.arctic_max_comments,
        max_wiki_pages=args.arctic_max_wiki_pages,
        comments=args.comments,
        save_external_assets=args.save_external_assets,
        external_domains=_external_domains(args),
    )

    print(
        json.dumps(
            {
                "mode": "arctic-shift-direct-capture",
                **result,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def _run_local_import(
    args: argparse.Namespace,
    capture_target,
) -> int:
    database_path = _project_path(args.database).resolve(strict=False)
    source_path = _project_path(args.source_file).resolve(strict=False)
    is_zst = source_path.name.casefold().endswith(".zst")
    if args.source_format == "arctic-zst" and not is_zst:
        raise ArchiveError("--source-format arctic-zst requires a .zst source file")
    zst_flags_requested = any(
        (
            args.source_format == "arctic-zst",
            args.source_scope != "scoped",
            args.after is not None,
            args.before is not None,
            args.expected_sha256 is not None,
            args.coverage_json is not None,
            args.discovery_manifest is not None,
        )
    )
    if zst_flags_requested and not is_zst:
        raise ArchiveError(
            "source scope, date, hash, and coverage flags require a .zst source"
        )
    source_options = None
    coverage_path = None
    if is_zst:
        discovery = (
            read_discovery_manifest(
                _project_path(args.discovery_manifest).resolve(strict=False),
                target=capture_target,
            )
            if args.discovery_manifest is not None
            else None
        )
        source_options = LocalSourceOptions(
            source_scope=args.source_scope,
            after_utc=parse_utc_boundary(args.after) if args.after else None,
            before_utc=parse_utc_boundary(args.before) if args.before else None,
            expected_sha256=args.expected_sha256,
            discovery=discovery,
        )
        if args.coverage_json is not None:
            coverage_path = _project_path(args.coverage_json).resolve(strict=False)
    if (
        args.reddit_max_items is not None
        or args.reddit_api_output is not None
        or args.reddit_timeout != 30.0
    ):
        raise ArchiveError(
            "Reddit API limit, output, and timeout flags require --reddit-api"
        )
    if any(
        (
            args.arctic_output_root is not None,
            args.arctic_timeout != DEFAULT_ARCTIC_TIMEOUT,
            args.arctic_max_response_bytes != DEFAULT_ARCTIC_MAX_RESPONSE_BYTES,
            args.arctic_max_comments != DEFAULT_ARCTIC_MAX_COMMENTS,
            args.arctic_max_wiki_pages != DEFAULT_ARCTIC_MAX_WIKI_PAGES,
        )
    ):
        raise ArchiveError(
            "Arctic Shift API output and limit flags require --arctic-shift-api"
        )

    media_directory = _project_path(args.media_directory).resolve(strict=False)
    external_domains = _external_domains(args)
    posts_limit = (
        DEFAULT_LOCAL_POSTS
        if args.posts is DEFAULT_POSTS_SENTINEL
        else args.posts
    )
    options = CaptureOptions(
        posts_limit=posts_limit,
        comments=args.comments,
        save_images=args.save_images,
        save_videos=args.save_videos,
        save_avatars=args.save_avatars,
        save_subreddit_assets=args.save_subreddit_assets,
        save_wiki=args.save_wiki,
        save_rules=args.save_rules,
        save_mod_list=args.save_mod_list,
        save_external_assets=args.save_external_assets,
        external_domains=external_domains,
        media_directory=str(media_directory),
    )
    summary = import_local_source(
        database_path,
        source_path,
        capture_target,
        options,
        resume=args.resume,
        source_options=source_options,
        coverage_path=coverage_path,
    )
    print(json.dumps(asdict(summary), indent=2, ensure_ascii=False))
    return 0


def run(args: argparse.Namespace) -> int:
    target_value = args.url if args.url is not None else args.subreddit
    capture_target = parse_capture_target(target_value)
    if args.arctic_shift_api:
        return _run_arctic_shift_capture(args, capture_target)
    if args.reddit_api:
        return _run_api_discovery(args, capture_target)
    return _run_local_import(args, capture_target)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (
        ArchiveError,
        ArcticShiftError,
        ArcticShiftApiError,
        CommunityError,
        RedditApiError,
        ResumeRequiredError,
        TargetParseError,
        OSError,
        ValueError,
    ) as exc:
        print(f"reddit_capture: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
