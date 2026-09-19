# Keivotos — Architecture & Decision Log

The actionable spec: what the system is, and the decisions that are considered
**locked** unless the user explicitly reopens them. Rationale lives in
[DESIGN-PHILOSOPHY.md](./DESIGN-PHILOSOPHY.md); the data flow in
[PIPELINE.md](./PIPELINE.md); the behavior contract per feature in
[FEATURES.md](FEATURES.md) (required reading before any feature change).

## Current-state boundary

- Release identity is not repeated here. The current cycle is named in
  [ROADMAP.md](./ROADMAP.md#current-cycle); the shipped semantic version is
  `backend/product.py`, written only by `scripts/release/set_version.py`.
- V1.10 and post-V1.0 material are future ideas, not the current release.
  Historical folder names and changelog headings remain historical evidence
  and are not retroactively renamed.
- This document describes the implementation found by the 2026-07-16 static
  audit. Unless a behavior is explicitly marked otherwise, "implemented"
  means present in source, not freshly exercised in the running application.
- The Danbooru sidebar animation was manually confirmed working 2026-07-25.
  Manayomi is now an integrated optional module; its focused module, scan,
  blacklist, relocation, browse-paging, and reader tests pass.

---

## A. Project context

- **Keivotos** is the suite ("All in one application for hoarding data").
  Its first and main module is **Danbooru** — a personal, self-hosted,
  single-user, local-first Danbooru-style booru. Reddit, Karaoke, YouTube,
  Languages, and **Manayomi** are additional optional local-first modules.
  Manayomi indexes and reads existing CBZ manga libraries in place.
- This codebase is the reconstructed original booru line (Python +
  Svelte), resurrected from raw Codex session logs after the source was lost —
  see
  [RECONSTRUCTION_LEDGER.md](archive/RECONSTRUCTION_LEDGER.md). An intermediate
  from-scratch SvelteKit rebuild reached ~0.3 and is retired; these
  docs are the adapted successors of its `docs/` set.
- A 97-file source/test/configuration sample from the current checkout is
  byte-identical to
  `D:\Kivotos\Github_Wakaru\V1.0.0 - (Release soon 1) - from zero`.
  That archive name is lineage evidence, not the current public release name.

## B. Component map

```
app.py                    entry point → uvicorn → backend/server.py; --dev / --port / --host
run.bat                   uv launcher: sync locked Python 3.11 env; build dist if absent; run
config.json               paths plus watcher, backup, and cache preferences
backend/
  server.py               FastAPI/router/static composition; serves frontend/dist
  app_factory.py          the FastAPI application object and HTTP middleware
  lifecycle.py            startup maintenance, module-gated background work, lifespan
  module_descriptor.py    typed suite/base/module identity and integration boundary
  module_registry.py      static Files + six optional-module descriptors
  modules/                descriptor-owned module definitions, behavior, and hooks
  files_base/             isolated neutral source/index/hash/filesystem layer
  services/               Shared query/domain services and guarded yt-dlp execution
  routers/                domain API endpoints (images, discovery, tags, artists, folders,
                          user library, collections, stats, tools, Reddit, Karaoke, YouTube, Manayomi)
  backup_bundle.py        manual verified ZIP64 backup + rollback-safe restore
  local_recovery.py       verified five-slot user.sqlite checkpoint rotation
  automation.py           low-frequency local-only change watcher
  database.py             Danbooru/shared-user DB access + idempotent migrations
  schema.py               authoritative data-DB schema and high-value indexes
  storage_layout.py       stable registered-root identity + canonical sidecar paths
  models.py               Pydantic response models — the API contract
  product.py              suite identity, semantic version, default origin
  config.py               path resolution (DATA_ROOT, METADATA_DIR, SIDECAR_DIR, DB paths…)
  thumbnails.py           300/600/1200 WebP tiers, cleanup, and bounded cache
scripts/
  danbooru_gallery_dl.py  incremental sync plus discover/enrich/metadata/finalize
  benchmark_library.py    read-only representative query timings and plans
  init_metadata_db.py     optional/manual bootstrap; lifespan is authoritative
frontend/                 Vite 8 + Svelte 5 + TypeScript + Tailwind 4
  src/lib/api.ts          typed API client (the consumer of models.py)
  src/lib/stores.ts       state + refresh tokens + persistedWritable settings
  src/modules/            module-owned surfaces, identity, UI descriptor registry
<Windows Local AppData known folder>/Keivotos/
                          user.sqlite, config.json, backups/, logs/, base/files.sqlite
<Windows Local AppData known folder>/Keivotos/modules/danbooru/
                          sidecars/, danbooru.sqlite, credentials, thumbnails/,
                          artist_profile_archive/, local_recovery/, gallery-dl/ (default)
<Windows Local AppData known folder>/Keivotos/modules/reddit/
                          reddit.sqlite, archives/, media/, discovery/ (default)
<Windows Local AppData known folder>/Keivotos/modules/karaoke/
                          karaoke.sqlite, media/library/, staging/ (default)
<Windows Local AppData known folder>/Keivotos/modules/youtube/
                          youtube.sqlite, media/library/, staging/, cache/ (default)
<suite home>/modules/manga/
                          manga.sqlite, user.sqlite, covers/, downloads/ (preserved Manayomi home)
data/                     preserved former metadata/direct-CLI location (git-ignored)
_gallery-dl/              preserved direct-CLI work location (git-ignored)
```

### B.1 `core.py` is gone

`backend/core.py` no longer exists. It was a 3,231-line compatibility facade that
every domain router imported with `from core import *`; it was reduced to zero
behavior and deleted on 2026-07-25.

- Composition now runs `app.py` -> `backend/server.py` -> `backend/app_factory.py`
  (the FastAPI object and middleware) with startup in `backend/lifecycle.py`.
- No module wildcard-imports anything. Every router names what it uses and takes
  it from the module that owns it.
- Danbooru behavior lives under `backend/modules/danbooru/`: `client.py` (the
  credentialed HTTP boundary), `relations.py`, `tag_wiki.py`, `tags.py`,
  `search.py`, `tools.py`, `paths.py`, `media_files.py`, `duplicate_review.py`,
  `image_activity.py`, `image_queries.py`, `artist_profiles.py`,
  `artist_follows.py`, `folder_registry.py`.
- Reddit behavior lives under `backend/modules/reddit/`: structured
  local/Arctic/API adapters, archive normalization, community and media
  persistence, comment-tree projection, and read-only library queries. Its
  endpoint bodies live in `backend/routers/reddit.py`.
- Karaoke behavior lives under `backend/modules/karaoke/`: its descriptor,
  contained/create-only storage, rebuildable catalog, lyric parsing and
  derivatives, Kara.moe client, and acquisition manager. Endpoint bodies live
  in `backend/routers/karaoke.py`.
- YouTube behavior lives under `backend/modules/youtube/`: its descriptor,
  storage/catalog, strict yt-dlp provider adapter, actual format selection, and
  acquisition manager. Endpoint bodies live in `backend/routers/youtube.py`.
- Languages behavior lives under `backend/modules/language/`: its descriptor
  and non-destructive Files hooks, contained versioned create-only storage,
  rebuildable word/progress catalog, precious authored-library projection,
  strict read-only AnkiConnect adapter, and cancellable import manager. Endpoint
  bodies live in `backend/routers/language.py`; the frontend remains
  module-owned under `frontend/src/modules/language/`.
- Shared, non-module helpers live in `backend/services/`: `query_helpers.py`,
  `value_helpers.py`, `tag_names.py`, `home.py`, `challenges.py`,
  `collections.py`, `profile.py`, `user_library.py`, `secret_store.py`, and
  `yt_dlp.py`. The secret store is the generic Windows DPAPI boundary; yt-dlp
  owns only safe process mechanics. Modules retain provider, destination,
  credential-location, and output policy.
- Put new endpoint bodies in `backend/routers/` and cohesive behavior in a module
  or service. Nothing should grow a new catch-all module.

Two latent bugs were found by this work and fixed separately, each with a
regression test: an undefined `SIDECAR_SUFFIXES` that made every image folder
move fail, and a `__file__`-relative lookup for the bundled gallery-dl that broke
when its code moved. Both are recorded in MODULAR_ARCHITECTURE_PLAN.md.

## C. Storage model (locked)

1. **Images stay in place.** Never copied or moved on ingest; originals served
   from their real paths. Media roots = `data_root` subfolders + any
   **registered folders** (existing directories registered by absolute path;
   registration never creates directories). Root removal either un-indexes
   only or, after an exact-count preview, deletes that root's current central
   sidecars and un-indexes. Neither mode touches original images, adjacent
   preservation sidecars, or archived sidecar history.
   A registered root is identified by stable `root_id`, not its display name,
   so duplicate leaf names are valid. Relocation updates stored/indexed paths
   in place while preserving the root ID and canonical sidecar namespace.
   Nested Files sources use deepest-root ownership: a parent scan records the
   nested root as a visible directory boundary but never indexes below it;
   parent-scoped search includes its registered descendants. Forgetting a
   nested source drops only its disposable rows and rescans the nearest
   remaining ancestor so no original is moved, copied, or deleted.
2. **Sidecars are the durable metadata store.** `.danbooru.json` + `.tags.txt`
   live below the configured metadata directory as
   `sidecars/roots/<stable-root-id>/<relative-path>`. Sidecar refreshes
   **archive** the replaced files, never destroy them. The approved transition
   copies and verifies legacy sidecars into this layout and deliberately leaves
   every legacy source in place.
3. **One precious database plus disposable indexes:**
   - `files.sqlite` — the Files base's disposable, type-agnostic index of cheap
     filesystem facts and lazily requested hashes. It authors no metadata.
   - `danbooru.sqlite` — the *data* DB: posts/files/tags + `sync_manifest` +
     resumable `ingest_state`.
     Disposable; rebuilt from sidecars in recovery, updated incrementally by
     `sync` in normal life.
   - `reddit.sqlite`, `karaoke.sqlite`, `youtube.sqlite`, `language.sqlite`, and
     `modules/manga/manga.sqlite` — module-owned rebuildable indexes for local
     evidence/artifacts, jobs, or mirrored study data. Durable raw evidence,
     media, metadata, and receipts stay as files beside them.
   - `user.sqlite` — the *user* DB: favorites, collections, collection_items,
     favorite_tags, favorite_tag_combos, blacklist_tags, user_image_tags,
     image_views, tag_wiki_cache, artist_follows, artist_follow_posts,
     artist_profile_assets, registered_folders, tag_removals, the shared
     `files_sources` registry, Karaoke favorites/playlists/playback, Languages
     authored words/overrides/lists/profiles/practice, and enabled-module
     state. Manayomi's historical precious roots, favorites, pins, categories,
     and settings remain in `modules/manga/user.sqlite`. The suite database lives at the suite
     root. **Irreplaceable — never dropped, never rebuilt.**
4. **Cross-DB joins on file identity**, not row ids: queries attach `userdb`
   and match via `user_file_match`, so user data survives full data-DB
   rebuilds and re-scans.
5. **Schema changes are additive.** `backend/schema.py` owns the data schema
   and indexes; user tables migrate via `_ensure_column` /
   `CREATE TABLE IF NOT EXISTS`. New columns arrive with a migration or
   backfill, never by recreating user tables.

## D. Current indexing contract

- **`sync` is the default indexing path** — incremental delta import driven by
  the `sync_manifest` (mtime/size) table; unchanged files are never opened;
  deleted files' rows are pruned; folder add/rescan sync only that folder.
- **Full sidecar→SQLite rebuild is recovery only** ("Rebuild Database
  (Recovery)" tool, chained with a sync so the manifest is rebuilt). Never wire
  it into a routine flow.
- Media without sidecars is indexed minimally (dimensions, dates, content MD5,
  no tags) with rating **Unrated** (`u`). General filters match only explicit
  `g` metadata.
- Bulk import is one four-phase resumable workflow: stat-only discovery;
  bounded hash/dimension enrichment; explicitly confirmed Danbooru matching
  that reuses indexed MD5; and incremental finalization. Phase 3 emits the
  current filename plus matched/no-match/error item results, persisted in
  `ingest_state` for review.
- The opt-in 5/15/30/60-minute watcher compares media stat signatures to the
  manifest and launches only the ordinary local incremental `sync`. Folder add
  and per-folder Rescan use the same path. The watcher never invokes the network
  metadata phase or the recovery rebuild.

These behaviors are implemented and have focused tests in the tree, but the
current clean test/build baseline and real-data runtime behavior have not been
rerun as part of the documentation audit.

## E. Acquisition (locked)

- gallery-dl does the downloading; the app never scrapes Danbooru pages itself.
  It is bundled in the venv and orchestrated by `scripts/danbooru_gallery_dl.py`
  (filename format `{id}_{md5}.{extension}` — MD5 is the content key end-to-end).
- Danbooru API traffic (backfill, wiki fetch, artist checks) is rate-limited
  and credentialed via `DANBOORU_USERNAME`/`DANBOORU_API_KEY` when provided.
- **No hotlinking, no surprise downloads.** Remote posts render as placeholders
  or `#id` chips; bytes are fetched only on explicit user action
  (profile-media archiving). Notification polling records post IDs only.
- Reddit and YouTube share `backend/services/yt_dlp.py` for shell-free command
  resolution, invariant safety arguments, finite process execution, progress,
  cancellation, and redaction. That service is deliberately provider-neutral:
  each module still owns its accepted URLs, selection policy, destination,
  receipts, and completed-file interpretation.
- Karaoke queries structured Kara.moe metadata first and acquires only the
  provider's official hardsub endpoint after an exact plan and authorization
  confirmation. YouTube uses bounded yt-dlp search/inspection and actual
  reported format IDs after the same plan-confirm boundary. Provider media is
  never streamed into the frontend; only completed contained local bytes play.
- Every new acquisition is create-only. Plans bind source, selection, limits,
  destination, and SHA-256; jobs preserve resumable partials and publish only
  declared library roots to Files. Real provider traffic remains an explicit
  user action and is not part of automated verification.

## F. Frontend architecture (locked)

- **No client router yet.** The suite-level `activeModule` resolves against
  descriptors in `App.svelte`; each module owns its surface/chrome. Inside
  Danbooru, `viewMode` still drives views and `ImageDetail` remains an overlay
  (`selectedImageId` / `selectedArtistProfileAsset`).
- **Immediate UI updates.** Mutations update the initiating component's local
  state first; refresh tokens (`imageRefreshToken`, `collectionRefreshToken`,
  `tagRefreshToken`, `artistFollowRefreshToken`) reconcile *other* views in the
  background. The initiating view never waits for a reload.
- **Settings persistence** via `persistedWritable` + normalizer. Suite-owned
  localStorage keys use `keivotos:`; recognized legacy module-prefixed values
  are copied forward when the suite key is absent, without deleting the source.
  Reddit capture defaults and YouTube confirmation-sheet defaults use the same
  suite prefix. Karaoke favorites, playlists, and playback state are precious
  SQLite data rather than presentation preferences.
- The shared local media player is module-neutral. It consumes only contained
  local media/track URLs, renders ASS/SSA with locally bundled JASSUB/libass,
  uses native WebVTT where available, and owns the Mouse-1/idle-hide/keyboard/
  lyrics/PiP/fullscreen interaction contract.
- Browser-local Daily Challenge progress is keyed by challenge ID. It is UI
  state tied to the browser origin, not authoritative library/user SQLite data.
- Top-bar layout, search syntax, sorting, and the view inventory are
  user-facing contracts — the authoritative list is in
  [FEATURES.md](FEATURES.md).
- Motion and animation are part of that contract. Static source assertions do
  not prove transition timing, reversal, dragging, delayed reveal, scrolling,
  or restoration. The sidebar must receive browser characterization before its
  implementation is restored or refactored.

## G. Local-first (locked)

Single user, self-hosted, offline-capable. No accounts, login, logout, cloud
sync, or remote-user assumptions. Profile is a local-library page. Everything
lives on your own disk in open formats: plain files + JSON sidecars + SQLite.
This manga-focused checkout defaults to `http://localhost:53325` and binds only to loopback.
Host validation blocks DNS-rebinding
style non-loopback hosts; Fetch Metadata blocks cross-site subresources; and
browser requests must use the exact active Keivotos origin. Wildcard CORS is
forbidden because local APIs can move/delete files and operate on backups,
tools, and credentials.

Runtime logs are written both to the console and to dated, suite-owned
files under `<suite-home>/logs`: `keivotos-runtime-...log` keeps startup,
mutations, failed reads, background work, warnings, and errors, while
`keivotos-access-...log` keeps every local HTTP method, path, and status.
Successful read-only traffic is excluded from the runtime file. Each stream
rolls over at 5 MB with five chunks and retains its 30 most recent files.

## H. Durability & backup

- The one thing that cannot be regenerated or re-fetched is **`user.sqlite`**.
  It receives a verified rotating local checkpoint on startup and after each
  successful sync. Identical snapshots are skipped and only five are retained.
  Settings uses the fixed suite backup destination and lets the user include
  either database, current sidecars, sidecar history, and artist
  profile archives. Original images, derived thumbnails, and credential files
  are excluded.
- `.keivotosbk` bundles are CRC checked, contain a manifest and SQLite snapshots,
  and are validated before completion. Backup and restore use deterministic
  staging children under the destination and metadata directory respectively;
  the existing process lock makes stale crash remnants safe to replace on the
  next attempt. Restore validates into staging first, checkpoints live
  databases, preserves the previous metadata under `local_recovery/`, and
  requires restart.
- The module directory is the default metadata root. Startup safely flattens
  the former `modules/danbooru/metadata/` wrapper, removes only identical
  duplicates, and fails closed on conflicts instead of overwriting data.
- The default follows the Windows Local AppData Known Folder API so live SQLite
  stays machine-local. A normal launch copies and verifies the former Documents
  suite home before configuration loads, atomically installs the completed copy,
  and preserves the original. A configured prior module tree is copied and
  verified into `modules/danbooru` before its config paths are rebased; its
  source remains untouched. `KEIVOTOS_HOME` still isolates tests and tools.
- Deleting a post, folder, or root must **never** delete in-place originals
  unless the user explicitly asked for a disk delete — and destructive bulk
  actions warn with counts first.

## I. Configuration

`config.json` (repo-local template): relative defaults resolved beneath the
Windows Local AppData known folder's `Keivotos` suite home: `data_root`
(`modules/danbooru/library`), `metadata_dir` (`modules/danbooru`), and
`gallery_dl_dir` (`modules/danbooru/gallery-dl`), watcher
interval, backup components, and thumbnail-cache
limit. Optional `scan_folders` narrows the neutral library root to named child
folders; no personal/developer folder names are built into the shipped default.
Paths may be absolute — never assume the repo root contains the images.

## J. Current implementation versus proposed modular target

The following are current facts:

- configured application locations are centered in `backend/config.py`;
- suite identity is owned by `backend/product.py`; Files, Danbooru, Reddit,
  Karaoke, YouTube, Languages, and Manayomi identity,
  homes, databases, credentials, declared API/log prefixes, user agents,
  lifecycle flags, and publication hooks are represented by immutable
  `ModuleDescriptor` entries in a static registry;
- Files is the one required non-disableable base; Danbooru, Reddit, Karaoke,
  YouTube, Languages, and Manayomi are optional entries. The frontend
  application/drawer resolves all seven implemented surfaces without hard-coded
  module branches;
- `user.sqlite`, backup destination, log directory/names, and browser storage
  prefix are suite-owned. The Danbooru DB, credential file, API identity, and
  user agent remain module-owned. Migrations copy/verify/preserve legacy user DB,
  module-scoped backups, and recognized browser values. Reddit's archive index,
  raw structured evidence, manifests, and local media live beneath its
  descriptor-owned module home. Karaoke and YouTube likewise own rebuildable
  indexes, create-only libraries, staging, receipts, and declared Files
  publication roots beneath their homes. Languages owns the same isolated
  shape for its mirror while keeping all authored state in `user.sqlite`; its
  page-load reads are local, and AnkiConnect is contacted only by explicit
  user probe/preview/import actions through a read-only allowlist. Manayomi
  keeps its established `modules/manga` databases, publishes verified external
  roots to Files, and gates `/api/manga/*` through descriptor enablement;
- `files_sources` is the shared registry. Its additive `visible` column filters
  the Files sidebar and its canonical role selects exactly one descriptor;
  adopt/release operations discard only disposable indexes and keep originals
  and sidecars;
- stable root identity and canonical sidecar construction are centered in
  `backend/storage_layout.py`;
- path containment, move/delete destinations, helper locations, folder-target
  resolution, and direct CLI defaults remain distributed;
- no router depends on a wildcard facade; every one imports its real owners
  explicitly, and `backend/core.py` has been deleted;
- Danbooru's physical implementation is partly behind its own boundary. Its HTTP
  client, post relations, tag wiki, user-tag listing, artist profile archive, and
  artist follows, the search grammar, and the tool runner now live in
  `backend/modules/danbooru/`. Some image behavior, configured paths, and
  lifecycle composition remain outside that directory, so removing its
  descriptor directory alone is still not a full
  module uninstall boundary.

The following remain proposed refactor directions, not current architecture:

1. Replace wildcard router imports one domain at a time with explicit
   dependencies.
2. Characterize the affected API, persistence, path, and browser behavior
   before extracting it.
3. Keep compatibility exports until every caller, test, packaged helper, and
   background worker is migrated.
4. Separate configured locations, resource locations, root identity, sidecar
   identity, containment policy, and folder-target resolution rather than
   replacing them with one new giant path module.
5. Restore lost behavior, beginning with the sidebar motion contract, before
   reorganizing its implementation.
6. Move the remaining Danbooru implementation behind its descriptor boundary
   incrementally; do not claim directory-only removal until all callers and
   compatibility exports have moved.
7. Keep Danbooru's grandfathered API routes stable. Descriptor `api_prefix`
   values are declared in V1.1.0; route prefixing is deferred.
