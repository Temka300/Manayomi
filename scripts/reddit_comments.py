"""Inspect or export an archived Reddit comment tree without network access."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import re
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from modules.reddit.comment_trees import (  # noqa: E402
    DEFAULT_MAX_COMMENTS,
    DEFAULT_MAX_OUTPUT_BYTES,
    CommentTreeError,
    CommentTreeOptions,
    build_comment_tree,
    export_comment_tree,
    summarize_comment_tree,
)
from config import MODULE_REGISTRY  # noqa: E402


REDDIT_MODULE = MODULE_REGISTRY.require("reddit")


SIZE_RE = re.compile(
    r"^(?P<number>\d+)(?P<unit>b|kb|kib|mb|mib|gb|gib)?$",
    re.IGNORECASE,
)
SIZE_MULTIPLIERS = {
    None: 1,
    "b": 1,
    "kb": 1000,
    "kib": 1024,
    "mb": 1000**2,
    "mib": 1024**2,
    "gb": 1000**3,
    "gib": 1024**3,
}


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


def size_arg(value: str) -> int:
    match = SIZE_RE.fullmatch(value.strip())
    if not match:
        raise argparse.ArgumentTypeError(
            "size must be an integer with an optional B, KB, KiB, MB, MiB, "
            "GB, or GiB suffix"
        )
    return int(match.group("number")) * SIZE_MULTIPLIERS[
        (match.group("unit") or "").casefold() or None
    ]


def _project_path(value: Path) -> Path:
    return value if value.is_absolute() else PROJECT_ROOT / value


def _add_read_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--database",
        type=path_arg,
        default=REDDIT_MODULE.database,
        help="Existing Slices 0-3 Reddit archive. Opened read-only.",
    )
    parser.add_argument(
        "--post-id",
        required=True,
        help="Bare Reddit post ID or t3_<id>.",
    )
    parser.add_argument(
        "--max-comments",
        type=positive_int,
        default=DEFAULT_MAX_COMMENTS,
        help=(
            "Fail before loading a larger thread. "
            f"Default: {DEFAULT_MAX_COMMENTS}."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect or create-only export one deterministic comment tree from "
            "an existing local Reddit archive. This command never opens a "
            "network URL or mutates the SQLite index."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect = subparsers.add_parser(
        "inspect",
        help="Print bounded integrity and completeness coverage.",
    )
    _add_read_arguments(inspect)

    export = subparsers.add_parser(
        "export",
        help="Install one deterministic nested JSON tree create-only.",
    )
    _add_read_arguments(export)
    export.add_argument(
        "--output",
        required=True,
        type=path_arg,
        help="Destination JSON file; an unlike existing file is never replaced.",
    )
    export.add_argument(
        "--max-output-bytes",
        type=size_arg,
        default=DEFAULT_MAX_OUTPUT_BYTES,
        help="Fail before installing a larger JSON file. Default: 1GiB.",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    database = _project_path(args.database).resolve(strict=False)
    options = CommentTreeOptions(max_comments=args.max_comments)
    if args.command == "inspect":
        result = summarize_comment_tree(
            build_comment_tree(database, args.post_id, options)
        )
    else:
        result = asdict(
            export_comment_tree(
                database,
                args.post_id,
                _project_path(args.output).resolve(strict=False),
                options=options,
                max_output_bytes=args.max_output_bytes,
            )
        )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (CommentTreeError, OSError, ValueError) as exc:
        print(f"reddit_comments: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
