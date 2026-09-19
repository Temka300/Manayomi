#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

if ! command -v uv >/dev/null 2>&1; then
    echo "[ERROR] uv is required to run Keivotos from source." >&2
    echo "[ERROR] Install it from https://docs.astral.sh/uv/" >&2
    exit 1
fi

echo "[SETUP] Synchronizing the locked Python 3.11 environment..."
uv sync --locked --python 3.11

if [[ ! -f frontend/dist/index.html ]]; then
    if ! command -v npm >/dev/null 2>&1; then
        echo "[ERROR] The frontend is not built. Install Node.js and npm, then run bash run.sh again." >&2
        exit 1
    fi
    (
        cd frontend
        echo "[SETUP] Installing locked frontend dependencies..."
        npm ci --no-audit --no-fund
        npm run build
    )
fi

echo "[RUN] Starting Keivotos..."
exec .venv/bin/python app.py "$@"
