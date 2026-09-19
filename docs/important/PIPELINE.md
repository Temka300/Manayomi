# Keivotos — The Data Pipeline

How an image goes from Danbooru to the browser, and which store owns what along
the way. This is the operational view; the *why* behind each stage is in
[DESIGN-PHILOSOPHY.md](./DESIGN-PHILOSOPHY.md), the component layout in
[ARCHITECTURE.md](./ARCHITECTURE.md).

Current release context: see [ROADMAP.md](./ROADMAP.md#current-cycle). This file describes source
behavior found by static inspection. Focused tests exist for many stages, but
the current clean suite, real-data operations, network stages, and runtime UI
were not exercised during the documentation audit.

```
 acquire            enrich                index                    serve
gallery-dl  ──►  media folders  ──►  .danbooru.json /  ──►  danbooru.sqlite  ──►  FastAPI ──► Svelte UI
(optional)       (always in place,    .tags.txt sidecars      (disposable          (domain API,
                  usually external)   under Local AppData/     incremental          thumbnails on
                                      Keivotos)                index)               demand)
                                                              via sync_manifest)
                                                                   ▲
                                                       user.sqlite ┘ (attached; favorites,
                                                       collections, follows … — irreplaceable)
```

All stages run through **one script** — `scripts/danbooru_gallery_dl.py`.
Acquisition remains an optional CLI capability; existing external folders are
the normal input. Settings exposes one four-phase bulk import, ordinary
incremental Re-scan, and a local-only watcher.

---

## Stage 1 — Acquire (`download`)

gallery-dl (installed in the locked uv environment) downloads posts into a
selected destination, commonly a top-level folder under `data_root`. The
shipped configuration does not contain developer-specific default scan-folder
names. The wrapper sets the filename format to
**`{id}_{md5}.{extension}`** — the MD5 baked into the filename is what lets
every later stage identify the file without re-hashing it.

```powershell
.venv\Scripts\python.exe scripts\danbooru_gallery_dl.py download "1girl rating:general" --folder Danbooru --limit 50
```

For direct CLI use, the default work location is the git-ignored
`_gallery-dl/`. The application passes its configured external work directory,
which defaults to
`<Local AppData known folder>/Keivotos/modules/danbooru/gallery-dl`.
Authenticated transient configs are deleted after each run.
After gallery-dl exits, its flat JSON is normalized into the canonical
`<metadata>/sidecars/roots/<root-id>/<relative-path>` wrapper with categorized tags, rating, post
data, and the real local path. Download stops there; importing those sidecars
into SQLite is a separate explicit tool.
See [gallery-dl.md](./gallery-dl.md) for the full command reference.

## Stage 2 — Enrich (`backfill`)

For every media file that lacks a sidecar, `backfill` queries Danbooru
(by the filename MD5 first, computed MD5 otherwise) and writes two sidecars to
the stable root-based location:

- `<name>.danbooru.json` — the full post payload (tags, rating, score, source,
  dates, relationships; optionally notes/commentary/parent/children/uploader
  with `--extra-metadata`).
- `<name>.tags.txt` — the flat tag list.

Sidecars are **the durable metadata store**. Refreshing them (`refresh-tags`
tool) archives the replaced sidecars instead of destroying them. Rate limiting,
retries and the optional `DANBOORU_USERNAME`/`DANBOORU_API_KEY` credentials all
live here.

Settings can save Danbooru credentials with Windows DPAPI protection;
environment variables override saved values, and child tools receive secrets
only through their process environment.

When the library watcher is enabled, `backend/automation.py` runs at the chosen
5/15/30/60-minute interval and compares media mtime/size with `sync_manifest`.
It starts only the ordinary local incremental `sync`; it never starts Danbooru
matching. Network enrichment remains an explicit click.

## Bulk import — four resumable phases

1. **Discover:** stat-only path inventory and stable root/relative identities;
   file contents are not opened.
2. **Hash & Inspect:** 1–8 bounded workers (3 by default) compute content MD5
   and dimensions once, recording per-file failures without stopping the run.
3. **Danbooru Metadata:** explicit, confirmed, rate-limited network work. It
   reuses the indexed MD5 rather than hashing again and writes durable sidecars.
4. **Finalize:** the ordinary incremental sync imports new sidecars and marks
   the phase ledger complete.

`ingest_state` makes each phase restartable. During Phase 3, Settings pins the
current filename above the progress bar and separates Matched, No match, and
Failed results. Those item outcomes remain in the phase ledger even after
Finalize, so a network miss is not disguised as a successful match.

## Stage 3 — Index (`sync`) — the default path

`sync` is an **incremental delta import** driven by the `sync_manifest` table
(mtime + size per file) in `danbooru.sqlite`:

- unchanged files are skipped **without being opened**;
- new/changed sidecars are (re)imported;
- media without sidecars is indexed minimally (dimensions, dates, content MD5,
  no tags; shown and filtered as **Unrated** rather than General);
- rows for deleted files are pruned.

Folder add / per-folder Rescan in Settings → Library uses this same scoped
incremental sync. The old full rebuild
(`sqlite --replace`) still exists but is **recovery only** — never wired into
a routine flow. `clean-sidecars` removes orphaned sidecars whose media is gone, but
skips an entire media root when that root is unavailable or unplugged.
Removing a registered root first previews exact index and current-sidecar
counts. **Un-index only** keeps all sidecars; the explicit
**Delete sidecars & un-index** mode deletes only current central sidecars for
that stable root. External images, adjacent preservation copies, and archived
sidecar history remain untouched in either mode.
Registered roots are scoped by stable `root_id`. Relocate updates the absolute
root and indexed/user-data file paths while retaining that ID, so canonical
sidecars remain under the same root namespace. Equal display names on different
drives remain separate roots.

## Stage 4 — Serve

`app.py` → uvicorn → `backend/server.py` (FastAPI) serves the built frontend
from `frontend/dist` at `http://localhost:54325/` plus the domain `/api/*`
surface. Static inspection found 95 route decorators across the backend; this
count includes non-API and helper-facing routes and is not a compatibility
guarantee by itself.
The launcher binds only to loopback, and middleware accepts browser requests
only from the exact active Keivotos origin.
Queries that need user data `ATTACH` `user.sqlite` and join on **file identity**
(`user_file_match`), never on rebuildable row ids. A verified `user.sqlite`
checkpoint is made on startup and after every successful sync; unchanged states
are skipped and only the newest five remain under `local_recovery/user_database`.
Originals are served from their real paths; thumbnails are generated on demand into the configured
module metadata root in fixed 300/600/1200 WebP tiers (content MD5 key; videos
use a local frame). Stale entries can be cleaned and oldest entries are pruned
to the configured limit.

## Stage 5 — User data (writes go to `user.sqlite` only)

Favorites, collections, favorite tags/combos, blacklist, user-added tags,
view/heart counts, tag wiki cache, artist follows + tracked post IDs, archived
artist profile media, registered folders, and removed-upstream tag history
captured after manual metadata refreshes. This DB is **never dropped, never
rebuilt** — schema changes are additive migrations (`_ensure_column` /
`CREATE TABLE IF NOT EXISTS` in `backend/database.py`).

---

## Who owns what

| Store | Role | Lost it? |
| --- | --- | --- |
| Media files (data_root + registered folders) | primary — your archive | gone; back up the folders |
| Sidecars (`<metadata>/sidecars/roots/...`) | durable metadata | re-fetchable via `backfill` (slow) |
| `user.sqlite` | **authoritative user data** | **unrecoverable — back this up** |
| `danbooru.sqlite` | disposable incremental index | rebuild: `sqlite --replace` + `sync` |
| `thumbnails/` | derived cache | regenerated on demand |

The portable app backup is deliberately manual: choose components in Safety &
Recovery, review the estimate, then create a verified `.keivotosbk` in the
fixed suite backup directory. Automatic local-recovery checkpoints protect `user.sqlite` on the
same device; they do not replace a portable backup.
Original media and thumbnails are never put in that bundle. Back up external
media separately when preservation of the image bytes matters. DPAPI credential
files are never included; restore cannot transfer another user's credentials.

## The everyday loop

```powershell
# 1. grab or copy in new posts
.venv\Scripts\python.exe scripts\danbooru_gallery_dl.py download "your_tag" --folder Danbooru

# 2. use Re-scan for an ordinary delta, or run all four import phases in Settings
.venv\Scripts\python.exe scripts\danbooru_gallery_dl.py sync

# 3. backfill/network metadata is always explicit
.venv\Scripts\python.exe scripts\danbooru_gallery_dl.py backfill

# 4. browse at http://localhost:54325/
```

The backend preserves five maintenance operations for compatibility: Sync
Database, Backfill Metadata, Rebuild Database (Recovery), Clean Orphan
Sidecars, and Update Danbooru Tags. The primary Settings flow presents routine
Re-scan, the four-phase import (whose Phase 3 replaces the old standalone Fill
missing metadata/tag-update cards), and the two uncommon recovery tools.
Update Tags still archives replaced sidecars and records removed upstream tags
when invoked through the compatibility API. Jobs share progress, cancellation,
and the one-at-a-time lock.
