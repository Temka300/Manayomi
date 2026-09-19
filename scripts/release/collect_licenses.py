"""Collect installed dependency license files for a binary distribution."""
from __future__ import annotations

import argparse
import shutil
from importlib import metadata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

DISTRIBUTIONS = (
    "aiosqlite",
    "fastapi",
    "gallery-dl",
    "imageio-ffmpeg",
    "kiwipiepy",
    "kiwipiepy-model",
    "koroman",
    "mfget",
    "numpy",
    "pillow",
    "tqdm",
    "uvicorn",
    "yt-dlp",
    "zstandard",
)

LICENSE_FALLBACKS = {
    "kiwipiepy-model": ("kiwipiepy",),
    "tqdm": (ROOT / "packaging" / "windows" / "licenses" / "tqdm-LICENCE",),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    missing: list[str] = []
    for name in DISTRIBUTIONS:
        distribution = metadata.distribution(name)
        candidates = [
            Path(distribution.locate_file(item))
            for item in (distribution.files or [])
            if Path(str(item)).name.lower().startswith(("license", "copying", "notice"))
        ]
        files = [path for path in candidates if path.is_file()]
        if not files:
            for fallback in LICENSE_FALLBACKS.get(name, ()):
                if isinstance(fallback, str):
                    fallback_distribution = metadata.distribution(fallback)
                    files.extend(
                        Path(fallback_distribution.locate_file(item))
                        for item in (fallback_distribution.files or [])
                        if Path(str(item)).name.lower().startswith(
                            ("license", "copying", "notice")
                        )
                        and Path(fallback_distribution.locate_file(item)).is_file()
                    )
                elif fallback.is_file():
                    files.append(fallback)
        if not files:
            missing.append(name)
            continue
        target = args.output / f"{name}-{distribution.version}"
        target.mkdir(parents=True, exist_ok=True)
        for source in files:
            shutil.copy2(source, target / source.name)
    if missing:
        raise SystemExit(f"No installed license file found for: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
