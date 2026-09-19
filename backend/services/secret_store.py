"""Small DPAPI-backed secret files for local optional modules."""
from __future__ import annotations

import base64
import ctypes
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_ulong),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _blob(data: bytes) -> tuple[_DataBlob, Any]:
    buffer = ctypes.create_string_buffer(data)
    return (
        _DataBlob(
            len(data),
            ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
        ),
        buffer,
    )


def protect(value: str, description: str) -> str:
    if os.name != "nt":
        raise RuntimeError(
            "Saving secrets requires Windows DPAPI; use an environment variable "
            "on this platform"
        )
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    source, source_buffer = _blob(value.encode("utf-8"))
    output = _DataBlob()
    if not crypt32.CryptProtectData(
        ctypes.byref(source),
        description,
        None,
        None,
        None,
        0,
        ctypes.byref(output),
    ):
        raise ctypes.WinError()
    try:
        return base64.b64encode(
            ctypes.string_at(output.pbData, output.cbData)
        ).decode("ascii")
    finally:
        _ = source_buffer
        kernel32.LocalFree(output.pbData)


def unprotect(value: str) -> str:
    if os.name != "nt":
        raise RuntimeError("Saved secret can only be decrypted by Windows DPAPI")
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    source, source_buffer = _blob(base64.b64decode(value))
    output = _DataBlob()
    if not crypt32.CryptUnprotectData(
        ctypes.byref(source),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(output),
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output.pbData, output.cbData).decode("utf-8")
    finally:
        _ = source_buffer
        kernel32.LocalFree(output.pbData)


def load_secret(path: Path, key: str) -> str | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        protected = str(payload.get(key) or "").strip()
        return unprotect(protected) if protected else None
    except (OSError, ValueError, TypeError):
        return None


def _write_payload(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".writing")
    if temporary.exists():
        raise RuntimeError(f"Credential staging file already exists: {temporary}")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            temporary.chmod(0o600)
        except OSError:
            pass
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def save_secret(path: Path, key: str, value: str, description: str) -> None:
    clean = value.strip()
    if not clean:
        raise ValueError("Secret value cannot be blank")
    try:
        existing = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        payload = existing if isinstance(existing, dict) else {}
    except (OSError, ValueError, TypeError):
        payload = {}
    payload[key] = protect(clean, description)
    payload["saved_at"] = datetime.now().astimezone().isoformat()
    _write_payload(path, payload)


def clear_secret_key(path: Path, key: str) -> None:
    """Remove one encrypted value without discarding sibling module secrets."""
    if not path.is_file():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return
    if not isinstance(payload, dict) or key not in payload:
        return
    payload.pop(key, None)
    payload["saved_at"] = datetime.now().astimezone().isoformat()
    if not any(name != "saved_at" for name in payload):
        path.unlink(missing_ok=True)
        return
    _write_payload(path, payload)


def clear_secret(path: Path) -> None:
    path.unlink(missing_ok=True)
