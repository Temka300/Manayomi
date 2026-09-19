"""Guarded yt-dlp command construction and process execution.

The service owns the subprocess boundary shared by optional modules. Domain
modules still own provider policy, output templates, plan confirmation, and
the interpretation of completed files.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from typing import Callable, Iterable


class YtDlpError(RuntimeError):
    """Raised when the guarded yt-dlp process cannot complete."""


ErrorFactory = Callable[[str], Exception]
LineHandler = Callable[[str], None]


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    output: str


def resolve_command(*, error_type: ErrorFactory = YtDlpError) -> list[str]:
    """Resolve the locked-environment or source-tree yt-dlp command."""
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve().parent / "yt-dlp.exe"
        if not executable.is_file():
            raise error_type(
                f"Portable yt-dlp.exe is missing beside Keivotos.exe: {executable}"
            )
        return [str(executable)]
    # Source runs must use the project-locked module. A random PATH executable
    # can be months behind the lock and causes extractor regressions that are
    # exceptionally hard to diagnose from the UI.
    return [sys.executable, "-m", "yt_dlp"]


def javascript_runtime_args() -> list[str]:
    """Return an explicit yt-dlp EJS runtime when a supported one is present."""
    node = shutil.which("node")
    if node:
        return ["--js-runtimes", f"node:{Path(node).resolve()}"]
    deno = shutil.which("deno")
    if deno:
        return ["--js-runtimes", f"deno:{Path(deno).resolve()}"]
    return []


def common_download_args(
    *,
    retries: int,
    socket_timeout: float,
    ffmpeg_executable: str,
    resume: bool = True,
) -> list[str]:
    """Return the invariant guarded arguments for one bounded download."""
    if retries < 0:
        raise ValueError("retries cannot be negative")
    if socket_timeout <= 0:
        raise ValueError("socket_timeout must be positive")
    if not ffmpeg_executable:
        raise ValueError("ffmpeg_executable is required")
    values = [
        "--ignore-config",
        "--no-playlist",
        "--no-overwrites",
        *javascript_runtime_args(),
    ]
    if resume:
        # yt-dlp documents --no-overwrites as implying --no-continue. Keep the
        # explicit resume flag after it so partials remain resumable.
        values.append("--continue")
    values.extend(
        [
            "--retries",
            str(retries),
            "--fragment-retries",
            str(retries),
            "--socket-timeout",
            str(socket_timeout),
            "--ffmpeg-location",
            ffmpeg_executable,
        ]
    )
    return values


def _creation_flags() -> int:
    return (
        getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if sys.platform == "win32"
        else 0
    )


def _bounded_output(value: str, limit: int = 4000) -> str:
    value = value.strip()
    return value[-limit:] if len(value) > limit else value


def run_process(
    command: list[str],
    *,
    timeout: float,
    label: str = "yt-dlp",
    error_type: ErrorFactory = YtDlpError,
) -> ProcessResult:
    """Run a finite process without a shell and retain a bounded error tail."""
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=_creation_flags(),
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise error_type(f"{label} could not complete: {exc}") from exc
    output = result.stdout or ""
    if result.returncode:
        tail = _bounded_output(output)
        raise error_type(
            f"{label} failed with exit code {result.returncode}"
            + (f": {tail}" if tail else "")
        )
    return ProcessResult(result.returncode, output)


def run_streaming_process(
    command: list[str],
    *,
    timeout: float,
    on_line: LineHandler,
    cancel_event: threading.Event | None = None,
    label: str = "yt-dlp",
    error_type: ErrorFactory = YtDlpError,
) -> ProcessResult:
    """Run yt-dlp with line progress, finite timeout, and cooperative cancel."""
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    started = time.monotonic()
    output: list[str] = []
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_creation_flags(),
            shell=False,
        )
    except OSError as exc:
        raise error_type(f"{label} could not start: {exc}") from exc

    assert process.stdout is not None
    try:
        while True:
            if cancel_event is not None and cancel_event.is_set():
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                raise error_type(f"{label} was cancelled")
            if time.monotonic() - started > timeout:
                process.kill()
                process.wait(timeout=5)
                raise error_type(f"{label} exceeded its {timeout:g}-second timeout")
            line = process.stdout.readline()
            if line:
                clean = line.rstrip("\r\n")
                output.append(clean)
                if len(output) > 200:
                    output = output[-200:]
                on_line(clean)
                continue
            if process.poll() is not None:
                break
            time.sleep(0.05)
    finally:
        process.stdout.close()

    joined = "\n".join(output)
    if process.returncode:
        tail = _bounded_output(joined)
        raise error_type(
            f"{label} failed with exit code {process.returncode}"
            + (f": {tail}" if tail else "")
        )
    return ProcessResult(process.returncode or 0, joined)


def redact_command(command: Iterable[str]) -> tuple[str, ...]:
    """Return a log-safe command with known credential-bearing args removed."""
    values = list(command)
    redacted: list[str] = []
    skip_value = False
    secret_options = {
        "--add-header",
        "--cookies",
        "--cookies-from-browser",
        "--password",
        "--proxy",
        "--username",
    }
    for value in values:
        if skip_value:
            redacted.append("<redacted>")
            skip_value = False
            continue
        redacted.append(value)
        if value in secret_options:
            skip_value = True
    return tuple(redacted)
