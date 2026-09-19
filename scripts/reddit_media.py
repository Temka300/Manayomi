"""Plan or explicitly run bounded Reddit-hosted media acquisition."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from modules.reddit.media import (  # noqa: E402
    DEFAULT_MAX_FILE_BYTES,
    DEFAULT_MAX_FILES,
    DEFAULT_MAX_RUN_BYTES,
    DEFAULT_MIN_FREE_BYTES,
    DEFAULT_PROCESS_TIMEOUT,
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT,
    MediaConfirmationError,
    MediaError,
    MediaLimits,
    build_media_plan,
    download_media,
)
from config import MODULE_REGISTRY  # noqa: E402


REDDIT_MODULE = MODULE_REGISTRY.require("reddit")


SIZE_RE = re.compile(
    r"^(?P<number>\d+)(?P<unit>b|kb|kib|mb|mib|gb|gib|tb|tib)?$",
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
    "tb": 1000**4,
    "tib": 1024**4,
}


def path_arg(value: str) -> Path:
    return Path(value).expanduser()


def size_arg(value: str) -> int:
    match = SIZE_RE.fullmatch(value.strip())
    if not match:
        raise argparse.ArgumentTypeError(
            "size must be an integer with an optional B, KB, KiB, MB, MiB, "
            "GB, GiB, TB, or TiB suffix"
        )
    return int(match.group("number")) * SIZE_MULTIPLIERS[
        (match.group("unit") or "").casefold() or None
    ]


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be an integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def nonnegative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be an integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("value cannot be negative")
    return parsed


def _project_path(value: Path) -> Path:
    return value if value.is_absolute() else PROJECT_ROOT / value


def _add_selection_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--database",
        type=path_arg,
        default=REDDIT_MODULE.database,
        help="Slices 0-2 Reddit archive database.",
    )
    parser.add_argument(
        "--destination",
        type=path_arg,
        default=REDDIT_MODULE.home / "media",
        help="Create-only content-addressed media root.",
    )
    parser.add_argument(
        "--max-files",
        type=positive_int,
        default=DEFAULT_MAX_FILES,
        help=f"Maximum assets selected in this run. Default: {DEFAULT_MAX_FILES}.",
    )
    parser.add_argument(
        "--max-file-bytes",
        type=size_arg,
        default=DEFAULT_MAX_FILE_BYTES,
        help="Per-file cap. Default: 2GiB.",
    )
    parser.add_argument(
        "--max-run-bytes",
        type=size_arg,
        default=DEFAULT_MAX_RUN_BYTES,
        help="Cumulative acquired-byte cap. Default: 10GiB.",
    )
    parser.add_argument(
        "--min-free-bytes",
        type=size_arg,
        default=DEFAULT_MIN_FREE_BYTES,
        help="Stop before disk free space drops below this guard. Default: 5GiB.",
    )
    parser.add_argument(
        "--role",
        action="append",
        default=[],
        help="Restrict to one queued asset role. Repeatable.",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Include assets whose previous attempt failed.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Plan or explicitly download already-queued Reddit images, videos, "
            "and supported linked files."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan = subparsers.add_parser(
        "plan",
        help="Read the queue and disk state without opening a network URL.",
    )
    _add_selection_arguments(plan)

    download = subparsers.add_parser(
        "download",
        help="Run the current bounded plan after confirming its count and hash.",
    )
    _add_selection_arguments(download)
    download.add_argument(
        "--confirm-assets",
        type=nonnegative_int,
        required=True,
        help="Must equal selected_assets from a plan using the same options.",
    )
    download.add_argument(
        "--confirm-selection",
        required=True,
        help="Must equal selection_sha256 from the matching offline plan.",
    )
    download.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="Per-request socket timeout in seconds. Default: 30.",
    )
    download.add_argument(
        "--process-timeout",
        type=float,
        default=DEFAULT_PROCESS_TIMEOUT,
        help="Per-asset engine timeout in seconds. Default: 3600.",
    )
    download.add_argument(
        "--retries",
        type=nonnegative_int,
        default=DEFAULT_RETRIES,
        help=f"Finite engine/request retries. Default: {DEFAULT_RETRIES}.",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    database = _project_path(args.database).resolve(strict=False)
    destination = _project_path(args.destination).resolve(strict=False)
    limits = MediaLimits(
        max_files=args.max_files,
        max_file_bytes=args.max_file_bytes,
        max_run_bytes=args.max_run_bytes,
        min_free_bytes=args.min_free_bytes,
    )
    plan = build_media_plan(
        database,
        destination,
        limits,
        roles=args.role,
        retry_failed=args.retry_failed,
    )
    if args.command == "plan":
        print(json.dumps(plan.summary(), indent=2, ensure_ascii=False))
        return 0

    result = download_media(
        plan,
        confirm_assets=args.confirm_assets,
        confirm_selection=args.confirm_selection,
        timeout=args.timeout,
        process_timeout=args.process_timeout,
        retries=args.retries,
    )
    print(
        json.dumps(
            {
                "plan": plan.summary(),
                "download": result.as_dict(),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if result.failed == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (MediaConfirmationError, MediaError, OSError, ValueError) as exc:
        print(f"reddit_media: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
