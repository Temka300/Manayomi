# Running Keivotos from source

## Requirements

- Windows 10 or later, or WSL2/Linux for source development
- [uv](https://docs.astral.sh/uv/)
- Node.js 24 or another version accepted by the locked frontend toolchain
- Git only when using a clone; a source ZIP works too

Python itself can be provisioned by uv.

## One-command launch

From the repository root:

```powershell
.\run.bat
```

`run.bat` synchronizes Python 3.11 from `pyproject.toml` and `uv.lock`. If the committed frontend output is unavailable, it installs from `package-lock.json` and builds it. The launcher window uses the Keivotos icon and title while keeping setup, runtime, LAN-address, and error output visible. The browser then opens at <http://localhost:53325/>.

On WSL2/Linux, use the Bash launcher from the repository root:

```bash
bash run.sh --no-browser
```

Open <http://localhost:53325/> in your Windows browser. The launcher uses Linux
uv and `.venv/bin/python`, installs the locked Python 3.11 environment, and
builds missing frontend output with Linux npm. Flags such as `--dev` and
`--port 54326` pass through. Stop it with Ctrl+C. Without `--no-browser`, the
app asks Python's browser integration to open the URL; availability depends on
your WSL desktop setup.

Create dependencies in Linux; do not reuse a Windows `.venv` or `node_modules`.
For separate frontend development, run `npm ci`, then `npm run dev` in
`frontend/`, alongside `bash run.sh --dev --no-browser`. After frontend edits,
use `npm run build` to update the UI served by the backend.

An empty `portable.txt` selects `data/` beside the project. When a copied
Windows installation already has `Data/` and no lowercase `data/`, it reuses
`Data/` without moving anything. If both are distinct directories, startup
requires `KEIVOTOS_HOME` or an absolute path in `portable.txt` to select one.
Without portable mode, Linux uses `$XDG_DATA_HOME/Keivotos` or
`~/.local/share/Keivotos`.

Saved `D:\...` library paths are not Linux paths. Confirm the actual mounted
media location before relocating registrations; never rescan an unavailable
root as a migration step. Windows folder dialogs and saved Windows-encrypted
credentials remain platform-specific; use the existing folder fallback and
credential environment variables on Linux.

## Trusted devices on the same network

Source runs can explicitly allow phones, tablets, and other computers on the same private network. The flag is double opt-in: it only exists when the `KEIVOTOS_DEVELOPER_LAN` environment variable is set:

```powershell
$env:KEIVOTOS_DEVELOPER_LAN = "1"
.\run.bat --lan
```

Keivotos continues to open `http://localhost:53325/` on the PC and prints a second address such as `http://192.168.1.25:53325/` for the other devices. Combine it with a custom port when needed:

```powershell
.\run.bat --lan --port 53326
```

The PC and other device must be on the same private network. Windows Firewall may ask whether Python can accept Private-network connections. LAN mode has no login or device-level permission boundary, so every device that can reach the displayed address can use the current Keivotos controls; enable it only on a trusted network and close the process when finished.

`--lan` is source-only. It is absent from packaged `Keivotos.exe` launchers, which remain loopback-only.

## Manual development setup

```powershell
uv sync --locked --python 3.11

Set-Location frontend
npm.cmd ci
npm.cmd run build
Set-Location ..

uv run python app.py
```

For separate live-reload processes:

```powershell
uv run python app.py --dev --no-browser
```

```powershell
Set-Location frontend
npm.cmd run dev
```

The backend remains on port 53325. Vite reports its own development URL.

## Checks

```powershell
uv run python -m compileall -q .\backend .\scripts .\app.py
uv run python -m unittest discover -s tests -v

Set-Location frontend
npm.cmd run check
npm.cmd run build
```

Set `KEIVOTOS_HOME` to an empty temporary directory for isolated runtime or CI checks. This redirects all default writable paths without editing `config.json`.

WSL2/Linux equivalents:

```bash
.venv/bin/python -m compileall -q backend scripts app.py
KEIVOTOS_HOME="$(mktemp -d /tmp/keivotos-check.XXXXXX)" .venv/bin/python -m unittest discover -s tests -v
cd frontend
npm run check
npm run build
```

Remove only the scratch directory created for the check after verification.
