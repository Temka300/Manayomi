"""Inspect the local Reddit library without network access or database writes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from modules.reddit.comment_trees import CommentTreeError  # noqa: E402
from config import MODULE_REGISTRY  # noqa: E402
from modules.reddit.library import (  # noqa: E402
    DEFAULT_MAX_THREAD_COMMENTS,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    RedditLibrary,
    RedditLibraryError,
)


REDDIT_MODULE = MODULE_REGISTRY.require("reddit")


def _path(value: str) -> Path:
    return Path(value).expanduser()


def _positive(value: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be a positive integer") from exc
    if result <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return result


def _add_database(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--database",
        type=_path,
        default=REDDIT_MODULE.database,
        help="Existing Reddit SQLite index. Opened read-only.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read the local Reddit library without opening network URLs."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    feed = commands.add_parser("feed", help="List saved posts by stable cursor.")
    _add_database(feed)
    feed.add_argument("--limit", type=_positive, default=DEFAULT_PAGE_SIZE)
    feed.add_argument("--cursor")
    feed.add_argument("--subreddit")
    feed.add_argument("--author")
    feed.add_argument("--flair")

    search = commands.add_parser("search", help="Search saved posts/comments.")
    _add_database(search)
    search.add_argument("query")
    search.add_argument("--limit", type=_positive, default=DEFAULT_PAGE_SIZE)
    search.add_argument("--subreddit")
    search.add_argument("--author")
    search.add_argument(
        "--record-type",
        choices=("all", "post", "comment"),
        default="all",
    )

    post = commands.add_parser("post", help="Read one post and comment tree.")
    _add_database(post)
    post.add_argument("post_id")
    post.add_argument(
        "--max-comments",
        type=_positive,
        default=DEFAULT_MAX_THREAD_COMMENTS,
    )

    community = commands.add_parser(
        "community",
        help="Read latest local about/rules/wiki/moderator snapshots.",
    )
    _add_database(community)
    community.add_argument("subreddit")

    status = commands.add_parser("status", help="Read local archive counts/jobs.")
    _add_database(status)
    return parser


def _project_path(value: Path) -> Path:
    return value if value.is_absolute() else PROJECT_ROOT / value


def run(args: argparse.Namespace) -> int:
    library = RedditLibrary(
        _project_path(args.database).resolve(strict=False)
    )
    if args.command == "feed":
        if args.limit > MAX_PAGE_SIZE:
            raise ValueError(f"limit cannot exceed {MAX_PAGE_SIZE}")
        result = library.list_posts(
            limit=args.limit,
            cursor=args.cursor,
            subreddit=args.subreddit,
            author=args.author,
            flair=args.flair,
        )
    elif args.command == "search":
        if args.limit > MAX_PAGE_SIZE:
            raise ValueError(f"limit cannot exceed {MAX_PAGE_SIZE}")
        result = library.search(
            args.query,
            limit=args.limit,
            subreddit=args.subreddit,
            author=args.author,
            record_type=args.record_type,
        )
    elif args.command == "post":
        result = library.get_post(
            args.post_id,
            max_comments=args.max_comments,
        )
        if result is None:
            raise RedditLibraryError(f"Unknown saved Reddit post: {args.post_id}")
    elif args.command == "community":
        result = library.get_community(args.subreddit)
    else:
        result = library.status()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except (CommentTreeError, RedditLibraryError, OSError, ValueError) as exc:
        print(f"reddit_library: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
