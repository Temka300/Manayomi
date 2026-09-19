"""Import local subreddit community snapshots without network access."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from modules.reddit.arctic_shift import ArcticShiftError  # noqa: E402
from modules.reddit.community import (  # noqa: E402
    COMMUNITY_SOURCE_SCOPES,
    COMMUNITY_SOURCE_TYPES,
    DEFAULT_CHUNK_SIZE,
    CommunityError,
    CommunityImportOptions,
    CommunityResumeRequiredError,
    import_community_source,
)
from config import MODULE_REGISTRY  # noqa: E402


REDDIT_MODULE = MODULE_REGISTRY.require("reddit")


def path_arg(value: str) -> Path:
    return Path(value).expanduser()


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be an integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _project_path(value: Path) -> Path:
    return value if value.is_absolute() else PROJECT_ROOT / value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Import user-supplied local subreddit about, rules, wiki, or "
            "moderator snapshots. This command never opens a network URL."
        )
    )
    parser.add_argument(
        "--subreddit",
        required=True,
        help="Target subreddit name, with or without r/.",
    )
    parser.add_argument(
        "--source-type",
        required=True,
        choices=tuple(sorted(COMMUNITY_SOURCE_TYPES)),
        help="Declared schema for every record in this source.",
    )
    parser.add_argument(
        "--source-file",
        required=True,
        type=path_arg,
        help="Local .json, JSONL/NDJSON, gzip JSONL, or Arctic Shift .zst.",
    )
    parser.add_argument(
        "--source-scope",
        choices=tuple(sorted(COMMUNITY_SOURCE_SCOPES)),
        default="scoped",
        help=(
            "Use scoped for a target-only source, or global to discard other "
            "subreddits before raw preservation."
        ),
    )
    parser.add_argument(
        "--database",
        type=path_arg,
        default=REDDIT_MODULE.database,
        help="Rebuildable Reddit SQLite index. Relative paths use project root.",
    )
    parser.add_argument(
        "--expected-sha256",
        help="Verify this 64-digit source digest before archive writes.",
    )
    parser.add_argument(
        "--coverage-json",
        type=path_arg,
        help=(
            "Also create the deterministic coverage report at this path. "
            "Every job keeps its own coverage.json beside raw chunks."
        ),
    )
    parser.add_argument(
        "--chunk-size",
        type=positive_int,
        default=DEFAULT_CHUNK_SIZE,
        help=f"Selected records per atomic raw chunk. Default: {DEFAULT_CHUNK_SIZE}.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume or inspect the same source/target/options job.",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    options = CommunityImportOptions(
        source_type=args.source_type,
        source_scope=args.source_scope,
        chunk_size=args.chunk_size,
        expected_sha256=args.expected_sha256,
    )
    summary = import_community_source(
        _project_path(args.database).resolve(strict=False),
        _project_path(args.source_file).resolve(strict=False),
        args.subreddit,
        options,
        resume=args.resume,
        coverage_path=(
            _project_path(args.coverage_json).resolve(strict=False)
            if args.coverage_json is not None
            else None
        ),
    )
    print(json.dumps(asdict(summary), indent=2, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (
        ArcticShiftError,
        CommunityError,
        CommunityResumeRequiredError,
        OSError,
        ValueError,
    ) as exc:
        print(f"reddit_community: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
