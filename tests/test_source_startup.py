"""Cross-platform startup and non-destructive portable-home selection."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PortableHomeTests(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "Checks the non-Windows helper response")
    def test_windows_picker_helper_reaches_its_platform_check(self) -> None:
        result = subprocess.run(
            [sys.executable, "-B", str(ROOT / "scripts" / "windows_folder_picker.py")],
            capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Windows", result.stderr)
        self.assertNotIn("Buffer size", result.stderr)

    def resolve(self, appdir: Path, **overrides: str) -> subprocess.CompletedProcess[str]:
        environment = {
            key: value for key, value in os.environ.items()
            if key not in {"KEIVOTOS_HOME", "KEIVOTOS_MIGRATE_LEGACY_HOME"}
        }
        environment.update(overrides)
        code = (
            "import ctypes, json, sys; sys.frozen = True; "
            f"sys.executable = {str(appdir / 'Keivotos.exe')!r}; "
            f"sys.path.insert(0, {str(ROOT / 'backend')!r}); "
            "import config; "
            "print(json.dumps({'home': str(config.SUITE_HOME), "
            "'guid_size': ctypes.sizeof(config._Guid)}))"
        )
        return subprocess.run(
            [sys.executable, "-B", "-c", code], env=environment,
            capture_output=True, text=True, check=False,
        )

    def test_windows_copied_data_is_reused_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            appdir = Path(temporary)
            (appdir / "portable.txt").touch()
            (appdir / "Data").mkdir()
            marker = appdir / "Data" / "user.sqlite"
            marker.write_bytes(b"preserved user database")
            before = sorted(appdir.rglob("*"))
            result = self.resolve(appdir)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(Path(payload["home"]), appdir / "Data")
            self.assertEqual(payload["guid_size"], 16)
            self.assertEqual(sorted(appdir.rglob("*")), before)
            self.assertEqual(marker.read_bytes(), b"preserved user database")

    @unittest.skipIf(os.name == "nt", "Requires case-sensitive paths")
    def test_distinct_data_directories_require_an_explicit_choice(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            appdir = Path(temporary)
            (appdir / "portable.txt").touch()
            (appdir / "Data").mkdir()
            (appdir / "data").mkdir(exist_ok=True)
            if (appdir / "Data").samefile(appdir / "data"):
                self.skipTest("Filesystem is case insensitive")
            result = self.resolve(appdir)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Both data and Data exist", result.stderr)
            result = self.resolve(appdir, KEIVOTOS_HOME=str(appdir / "Data"))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["home"], str(appdir / "Data"))


@unittest.skipIf(os.name == "nt" or not shutil.which("bash"), "Bash launcher runs on Unix")
class BashLauncherTests(unittest.TestCase):
    def launch(self, uv_exit: int) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory(prefix="keivotos launcher ") as temporary:
            root = Path(temporary)
            shutil.copyfile(ROOT / "run.sh", root / "run.sh")
            (root / "frontend" / "dist").mkdir(parents=True)
            (root / "frontend" / "dist" / "index.html").touch()
            scripts = root / ".venv" / "bin"
            scripts.mkdir(parents=True)
            (scripts / "python").symlink_to(sys.executable)
            uv = scripts / "uv"
            uv.write_text(
                '#!/bin/sh\n[ "$*" = "sync --locked --python 3.11" ] || exit 99\n'
                f"exit {uv_exit}\n", encoding="utf-8",
            )
            uv.chmod(0o755)
            (root / "app.py").write_text(
                "import json, pathlib, sys\n"
                "print(json.dumps([str(pathlib.Path.cwd()), sys.argv[1:]]))\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [shutil.which("bash"), str(root / "run.sh"), "--no-browser", "a spaced argument"],
                cwd=ROOT,
                env={**os.environ, "PATH": str(scripts) + os.pathsep + os.defpath},
                text=True, capture_output=True, check=False,
            )
            if uv_exit == 0:
                self.assertEqual(result.returncode, 0, result.stderr)
                directory, arguments = json.loads(result.stdout.splitlines()[-1])
                self.assertEqual(directory, str(root))
                self.assertEqual(arguments, ["--no-browser", "a spaced argument"])
            return result

    def test_prebuilt_frontend_launches_from_another_directory_with_arguments(self) -> None:
        self.launch(0)

    def test_local_lan_wrapper_forwards_marker_arguments_and_exit_status(self) -> None:
        with tempfile.TemporaryDirectory(prefix="keivotos lan launcher ") as temporary:
            root = Path(temporary)
            wrapper = root / "run-lan-local.sh"
            shutil.copyfile(ROOT / "run-lan-local.sh", wrapper)
            (root / "run.sh").write_text(
                '#!/usr/bin/env bash\n'
                'printf "%s\\n" "$KEIVOTOS_DEVELOPER_LAN" "$@"\n'
                'exit 7\n',
                encoding="utf-8",
            )
            for explicit_lan in ([], ["--lan"]):
                with self.subTest(explicit_lan=explicit_lan):
                    arguments = [*explicit_lan, "--port", "54326", "--no-browser", "a spaced argument"]
                    result = subprocess.run(
                        [shutil.which("bash"), str(wrapper), *arguments],
                        cwd=ROOT,
                        env={**os.environ, "KEIVOTOS_DEVELOPER_LAN": "0"},
                        text=True, capture_output=True, check=False,
                    )
                    self.assertEqual(result.returncode, 7, result.stderr)
                    self.assertEqual(result.stdout.splitlines(), ["1", "--lan", *arguments])

    def test_dependency_failure_stops_before_starting_the_app(self) -> None:
        result = self.launch(7)
        self.assertEqual(result.returncode, 7)
        self.assertNotIn("[RUN]", result.stdout)


if __name__ == "__main__":
    unittest.main()
