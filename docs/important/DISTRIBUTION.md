# Running & distributing Keivotos (Danbooru)

## Current release state

The current cycle is named in [ROADMAP.md](./ROADMAP.md#current-cycle). Runtime,
Python package and `uv.lock`, frontend package, Windows version resources, and
OpenAPI all report the same number from one release-bump workflow —
**`backend/product.py` is the value to read**, never a number repeated in prose.

Set a release version and refresh every tracked version fact with (substitute
the real `X.Y.Z`):

```powershell
.venv\Scripts\python.exe scripts\release\set_version.py X.Y.Z
.venv\Scripts\python.exe -m unittest discover -s tests
```

The Windows build reads its artifact version from `backend/product.py`, rejects
an explicitly mismatched `-Version`, and resolves uv by full path even when the
current terminal has a stale `PATH`.

## Source launch on WSL2/Linux

Run `bash run.sh --no-browser`, then open `http://localhost:53325/` in your
browser. It synchronizes locked Python 3.11 dependencies with Linux uv, uses
`.venv/bin/python`, and builds missing frontend output with npm. Use `npm run
check` and `npm run build` in `frontend/` for development. Windows packaging
remains a separate Windows workflow.

For maintainer LAN access, use `bash run-lan-local.sh --lan --no-browser`.
Like the ignored Windows wrapper, this ignored local script sets the developer
marker, enables LAN by default, and forwards additional flags to `run.sh`.
The app displays the detected private IPv4 URL. Access from other devices
depends on the host/WSL network configuration; the wrapper does not change it.

An empty `portable.txt` reuses an existing adjacent `Data/` when lowercase
`data/` is absent. It never merges or renames data directories. Distinct
existing `Data/` and `data/` require an explicit home. Without portable mode,
Linux uses `$XDG_DATA_HOME/Keivotos` or `~/.local/share/Keivotos`; backups remain
under the selected suite home. Saved Windows library paths require verified
relocation to accessible Linux paths. See [source.md](../build/source.md).

## Easiest on Windows: double-click `run.bat`

On any Windows machine with **[uv](https://docs.astral.sh/uv/)** installed,
double-click **`run.bat`**. First run: it creates `.venv` with Python 3.11,
uses the locked `pyproject.toml`/`uv.lock` environment to install the backend
dependencies (`fastapi`, `uvicorn`, `aiosqlite`, `Pillow`, `gallery-dl`, and
the local Languages Analyzer's locked Kiwi/romanization packages, plus the
packaged FFmpeg helper), and starts the application. Every run after that
synchronizes the locked environment, builds the frontend only when
`frontend/dist/index.html` is absent, and opens the app at
`http://localhost:53325/`. Close the console window to stop.

Flags pass through: `run.bat --dev` (auto-reload) and
`run.bat --port 54326`. Maintainer checkouts may use the ignored
`run-lan.local.bat` for trusted devices on the same private network. It displays
the exact private IPv4 URL, binds only that adapter, remains same-origin, and
lasts only while that source process runs. Ordinary source and portable
`Keivotos.exe` builds remain loopback-only.

The repository includes the built **`frontend/dist/`**, so a fresh clone runs
with only uv. If that directory is missing, `run.bat` builds it automatically
when npm is available; otherwise it stops with an actionable error. Developers
can rebuild it explicitly with:

```powershell
cd frontend
npm.cmd install
npm.cmd run build
```

That's the whole thing for your own use. The rest of this doc is about
sharing it.

## The good news vs. the old stack

The retired SvelteKit rebuild fought native Node modules (`better-sqlite3`,
`sharp`) that made packaging painful. This stack has no runtime Node
dependency: the frontend compiles to static files. The Languages Analyzer does
add Kiwi's maintained native Python wheel and local model data. Source runs
receive the exact wheel/model through `uv.lock`; the Windows PyInstaller spec
collects Kiwi's binaries, hidden modules, and data explicitly. Distribution
remains "code + prebuilt `dist/` + a launcher" — uv fetches Python itself.

## Making a release bundle (for someone without Node)

Goal: a source zip that runs with only uv installed, or the separately produced
one-folder Windows portable package.

1. Build the frontend: `npm.cmd run build` in `frontend/`.
2. Zip the repo **plus** `frontend/dist/`, **minus** all data and caches:

   ```
   Keivotos/
   ├─ run.bat
   ├─ app.py
   ├─ config.json            ← repo-local defaults (no personal paths)
   ├─ backend/               (no __pycache__)
   ├─ scripts/               (no __pycache__)
   ├─ frontend/dist/         ← prebuilt UI (the only frontend part needed to run)
   ├─ docs/  README.md  CHANGELOG.md  LICENSE
   └─ (NO data/, NO _gallery-dl/, NO .venv/, NO media)
   ```

3. The recipient unzips, installs uv, double-clicks `run.bat`, and registers
   their own image folders in Settings → Library.

> The hoard never ships: generated `%LOCALAPPDATA%/Keivotos`, the preserved
> repo `data/`, `_gallery-dl/`, the fixed backup directory, and media folders must
> never be committed or bundled.

Manual backups intentionally stay at
`%LOCALAPPDATA%/Keivotos/backups`, in the suite root and on the
same default drive as Keivotos application data. External media-library paths
do not relocate backups. The retired `backup_destination` key is ignored and
removed the next time runtime configuration is saved.

## GitHub release process

The **user** owns commits, pushes, tags, and releases. The assistant does not
perform or prescribe those actions unless the user separately requests them.
When the user chooses to publish, attach the verified source or portable
artifact and its checksum to the release they create.

Release-notes style: plain imperative bullets, no emoji, no category headers.
Use the user-defined release identity; do not label the current state as V1.10
or a completed post-V1.0 release.

## Later options (when the suite stabilizes)

Everything in this section is future-only. No item is scheduled merely because
it is documented here.

- **Docker / native Linux desktop integrations** — Bash source launch exists;
  container distribution remains future-only. The modern Explorer folder picker is Windows-specific,
  so non-Windows users enter library paths manually; `open file location` can
  likewise degrade gracefully. A future suite shell can provide a platform
  picker. This is old FUTURE item 00; do it once, for the suite, not per-module.
- **Optional Windows installer (deferred and unlikely)** — the supported
  Windows deliverable remains the one-folder portable build containing
  `Keivotos.exe`. An installer would only wrap that folder with shortcuts and
  uninstall metadata; it would not solve code signing, port ownership, or data
  migration. Reconsider it only if portable extraction becomes a real user
  problem. Do not replace the portable build with a one-file executable.
- **A real window** — pywebview (Python-native, tiny) over the running
  server, instead of the old Electron/Tauri plans. Polish, not priority.
