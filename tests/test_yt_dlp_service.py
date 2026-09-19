from __future__ import annotations

import subprocess
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from services import yt_dlp


class YtDlpServiceTests(unittest.TestCase):
    def test_common_args_keep_resume_after_no_overwrites(self) -> None:
        values = yt_dlp.common_download_args(
            retries=3,
            socket_timeout=12,
            ffmpeg_executable="ffmpeg",
        )
        self.assertLess(values.index("--no-overwrites"), values.index("--continue"))
        self.assertIn("--ignore-config", values)
        self.assertIn("--no-playlist", values)
        self.assertEqual(values[values.index("--retries") + 1], "3")
        self.assertEqual(values[values.index("--socket-timeout") + 1], "12")
        self.assertEqual(values[values.index("--ffmpeg-location") + 1], "ffmpeg")

    def test_process_never_uses_a_shell_and_returns_output(self) -> None:
        completed = subprocess.CompletedProcess(["yt-dlp"], 0, "ready\n")
        with patch.object(yt_dlp.subprocess, "run", return_value=completed) as run:
            result = yt_dlp.run_process(["yt-dlp", "--version"], timeout=4)
        self.assertEqual(result.output, "ready\n")
        self.assertFalse(run.call_args.kwargs["shell"])

    def test_process_error_is_bounded_and_uses_requested_error(self) -> None:
        completed = subprocess.CompletedProcess(["yt-dlp"], 2, "x" * 5000)
        custom = Mock(side_effect=ValueError)
        with (
            patch.object(yt_dlp.subprocess, "run", return_value=completed),
            self.assertRaises(ValueError),
        ):
            yt_dlp.run_process(
                ["yt-dlp"],
                timeout=4,
                error_type=custom,
            )
        message = custom.call_args.args[0]
        self.assertIn("exit code 2", message)
        self.assertLess(len(message), 4100)

    def test_redaction_removes_known_secret_values(self) -> None:
        self.assertEqual(
            yt_dlp.redact_command(
                ["yt-dlp", "--cookies", "private.txt", "--format", "best"]
            ),
            ("yt-dlp", "--cookies", "<redacted>", "--format", "best"),
        )


if __name__ == "__main__":
    unittest.main()
