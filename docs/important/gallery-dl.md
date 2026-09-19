# Acquiring with gallery-dl

Current release context: see [ROADMAP.md](./ROADMAP.md#current-cycle). The commands and code paths
below exist in source, but no network-heavy acquisition job was run during the
documentation audit.

[gallery-dl](https://github.com/mikf/gallery-dl) is the acquisition engine.
Unlike the retired rebuild — where it was a fully external tool the app knew
nothing about — here it is installed into the locked uv environment
(`gallery-dl==1.32.6` in `pyproject.toml`/`uv.lock`) and is orchestrated by
**`scripts/danbooru_gallery_dl.py`**, the same script that powers the in-app
tools runner. It still does one thing well: download; everything after that is
the pipeline ([PIPELINE.md](./PIPELINE.md)).

The link between stages is the **MD5 in the filename**: downloads are named
`{id}_{md5}.{extension}`, so backfill/sync/duplicate-review identify every
file without re-hashing it.

## Setup

Nothing to install — `run.bat` already put gallery-dl in `.venv`. Optional
Danbooru credentials (higher rate limits, restricted posts) can be saved in
Settings → Library with Windows DPAPI protection, or supplied through
environment variables/CLI flags:

```powershell
$env:DANBOORU_USERNAME = "YOUR_NAME"
$env:DANBOORU_API_KEY  = "YOUR_KEY"
```

gallery-dl's download archive lives in `_gallery-dl/` (git-ignored; override
with `--gallery-dl-dir`) when the script is invoked directly with its defaults.
The application passes the configured external work directory, which defaults
to `<Local AppData known folder>/Keivotos/modules/danbooru/gallery-dl`.
Per-run configs are private temporary files and are removed after gallery-dl
exits because authenticated configs contain the key.

## The everyday loop

```powershell
# 1. download a tag search into a top-level folder under data_root
.venv\Scripts\python.exe scripts\danbooru_gallery_dl.py download "1girl rating:general" --folder Danbooru --limit 50

# 2. fold new/changed files into the index; download already normalized metadata
.venv\Scripts\python.exe scripts\danbooru_gallery_dl.py sync

# 3. backfill only pre-existing files that have no sidecars
.venv\Scripts\python.exe scripts\danbooru_gallery_dl.py backfill
```

Then browse at `http://localhost:54325/`. Only new files cost API calls —
everything already indexed is skipped without being opened.

## Subcommand reference

Global options (before the subcommand): `--root` (workspace root, default:
project root) · `--gallery-dl-dir` · `--sidecar-dir` (default
`data/sidecars` for direct CLI use) · `--user-db` (default
`data/user.sqlite`, used for stable registered-root identities). The app
explicitly supplies its configured external gallery-dl, sidecar, user-DB, and
data-DB paths. Direct CLI defaults are compatibility defaults and must not be
mistaken for the application's current Local AppData layout.

| Command | What it does | Useful flags |
| --- | --- | --- |
| `download <tags…>` | gallery-dl tag-search download; normalizes gallery metadata into canonical central JSON/tag sidecars | `--folder` (default `Danbooru`), `--tag-folder` (default: sanitized query), `--destination` (exact output directory), `--filename` (default `{id}_{md5}.{extension}`), `--limit`, `--sleep-request 1.0-2.0`, `--sleep-429 60-120`, `--retries 5`, `--metadata-includes`, `--ugoira-zip`, `--external`, `--dry-run` |
| `backfill [paths…]` | write sidecars for existing media via Danbooru MD5 lookup (defaults to the configured Danbooru folders) | `--delay 1.0`, `--limit`, `--overwrite`, `--archive-replaced-sidecars` (+ `--sidecar-archive-dir`, default `data/sidecar_archive/<timestamp>`), `--filename-md5-only`, `--extra-metadata` (notes/commentary/parent/children/uploader), `--index-jsonl`, `--dry-run` |
| `sync [paths…]` | **the default indexing path** — incremental delta import via `sync_manifest`: new/changed sidecars imported, sidecar-less media indexed minimally, deleted files' rows pruned; no rebuild | `--output` (default `data/danbooru.sqlite`), `--no-raw-json` |
| `beta-discover [paths…]` | Phase 1: stat-only discovery and stable root/relative identities; does not open media contents | `--output` |
| `beta-enrich [paths…]` | Phase 2: bounded-worker MD5 and dimension enrichment with per-file resumable errors | `--output`, `--workers 3` |
| `beta-finalize [paths…]` | Phase 4: incremental sidecar import and final phase-ledger update | `--output`, `--no-raw-json` |
| `sqlite [paths…]` | full sidecar→SQLite build — **recovery only**, chain with `sync` afterwards to rebuild the manifest | `--replace`, `--extra-root` (repeatable, for registered external folders), `--commit-every 5000`, `--include-missing-media`, `--no-raw-json` |
| `clean-sidecars [paths…]` | delete orphan sidecars whose media file is gone | `--dry-run`, `--limit` |
| `index [paths…]` | one central JSON search index from sidecars (legacy/inspection aid) | `--output`, `--pretty`, `--full` |
| `search <terms…>` | query the SQLite DB from the CLI (`tag -tag artist:x rating:s ext:jpg 2160x3840 dim:>=1920x1080 orientation:portrait`) | `--database`, `--limit 50`, `--json`. Note: partially reimplemented post-reconstruction; bare numeric filters default to `>=` (see archive/RECONSTRUCTION_LEDGER.md) |

## In-app equivalents

Settings presents routine incremental **Re-scan**, a four-phase resumable
import flow, **Clean orphan sidecars**, and **Rebuild database (recovery)**.
The backend compatibility API still exposes the original five tool IDs:
**sync**, **backfill**, **sqlite**, **clean-sidecars**, and **refresh-tags**.
The current UI does not present the old Legacy/Beta selector or standalone
backfill/refresh cards.

Import Phase 3 uses the existing `backfill` path with explicit network
confirmation and indexed-MD5 reuse. One tool runs at a time to prevent
concurrent sidecar/database writes, with progress, recent output, and
cancellation. Sidecars go to the configured sidecar directory. Do not start
long network-heavy backfills or refreshes casually; they can issue a Danbooru
request for every eligible file.

## Other sources (future)

gallery-dl also speaks Pixiv, Twitter/X, Kemono and many more — that's the
possible future path for additional suite modules ([FUTURE.md](./FUTURE.md)).
The policy stays: external CLI tools do the fetching; the app enriches,
indexes, and browses. No additional module is currently scheduled.
