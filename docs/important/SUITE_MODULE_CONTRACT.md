# Keivotos — Suite / Base / Module Contract (V1.1.0 direction)

Plan date: **2026-07-21**
Target release: **V1.1.0** (feature: the **Files** base + the module framework)

This is a **decisions-only** design contract. It records the architecture agreed
for turning Keivotos from "an app that *is* Danbooru" into "a suite with an
always-on file base and optional modules." It authorizes **no application-code
change**; each build step remains a separate, permission-gated change.

It complements, and does not replace:

- [ARCHITECTURE.md](./ARCHITECTURE.md) — current locked decisions for the
  Danbooru module.
- [MODULAR_ARCHITECTURE_PLAN.md](./MODULAR_ARCHITECTURE_PLAN.md) — the internal
  `core.py` untangling plan. That work was deferred here (see §13) and later
  carried out: `core.py` was deleted on 2026-07-25. This contract never
  depended on it.
- [FUTURE.md](./FUTURE.md) — this contract answers its open questions #1 and #2.
- [ROADMAP.md](./ROADMAP.md) — the "agree the modular target" step.

---

## 1. Vocabulary (use these words exactly)

| Term | Meaning |
|---|---|
| **Suite** | Keivotos itself — the whole product / the running application. |
| **Base** | **Files** — the always-on, neutral file layer. Cannot be turned off. It *is* the app's ground floor. **Not a module.** |
| **Module** | An optional, enable-able floor built on top of the base (Danbooru, Reddit, Karaoke, YouTube, Languages, and Manayomi today; anime, music, 3D/Live2D/MMD, and other archives later). |

The single most important reframe: **Files is the base, not the first module.**
Danbooru and everything after it are modules the user adds.

Current extension: the original V1.1.0 examples below remain historical design
facts. The implemented registry now contains optional Danbooru, Reddit,
Karaoke, YouTube, Languages, and Manayomi modules, all with module-owned backend and
frontend surfaces. Their additions follow the same
dependency, database, API, lifecycle, and frontend rules rather than changing
them.

---

## 2. Core model (locked for V1.1.0)

1. **Fresh launch shows only the Files base**, listing every file the user has
   added, as plain files. No module is present until the user enables one.
2. **Danbooru becomes an enable-able module.** Enabling it makes a **Danbooru**
   entry appear in the Keivotos (suite-level) sidebar and lights up its views.
3. **The base is a lens, not a manager.** Files indexes and displays
   filesystem facts only. It authors no metadata and (in V1.1.0) does not
   rename/move/delete originals. "Files stay in place" (ARCHITECTURE §C) holds.
4. **Modules enrich; the base stays neutral.** Tags, ratings, favorites-of-a-
   post, reading position, etc. belong to modules, never to the base.
5. **Dependency direction is one-way: modules depend on the base; the base
   never depends on a module.** This is the invariant that keeps the base from
   rotting into "a thing that knows every module," and is what makes a future
   plugin system possible (§14).

---

## 3. Database model (locked)

There are exactly **three** SQLite databases in V1.1.0, and the count grows by
**one disposable index per module** thereafter — never more precious files.

| Database | Holds | Kind | Count rule |
|---|---|---|---|
| `files.sqlite` | index of every file: path, name, ext, size, mtime, (lazy) hash, thumb refs | **disposable** — rebuildable from disk | one, for the base |
| `danbooru.sqlite` | booru posts + tags (existing) | **disposable** — rebuildable from disk | one **per module** |
| `user.sqlite` | favorites, collections, folder roles, enabled modules, module-specific user state | **irreplaceable** — hand-made | **exactly one, forever** |

Pattern: **N disposable index DBs (one per module + one for the base) + 1
precious `user.sqlite`.** Today N = 2 (base + Danbooru) ⇒ three files.

### 3.1 `user.sqlite` promotion (the one delicate step)

- `user.sqlite` currently resolves under `modules/danbooru/`
  ([config.py](../../backend/config.py) `USER_DB_PATH = METADATA_DIR / "user.sqlite"`).
  Because the base must exist with zero modules, the shared precious DB **cannot
  live inside an optional module's folder.**
- **Promote it to the suite root** (`SUITE_HOME / "user.sqlite"`) using the
  existing **copy → verify → atomic install → preserve source, fail closed on
  conflict** pattern already used for the metadata-wrapper flatten and the
  Documents-home copy (ARCHITECTURE §H). Do **not** simply repoint the path and
  move the file.
- This is the highest-risk operation in V1.1.0. It is its own change, verified
  before anything else builds on it.

### 3.2 Table ownership: prefix convention

- Inside the single `user.sqlite`, tables are namespaced by a **prefix**
  (`danbooru_favorites`), **not** a dot (`danbooru.favorites` in SQLite means an
  *attached separate database file*, which we are not using).
- Prefixes: `suite_*`, `files_*`, `danbooru_*`, and `<module>_*` for future
  modules.
- Danbooru's existing bare tables are **renamed to `danbooru_*` during the
  §3.1 promotion migration** (one verified additive migration), so the rename
  never happens as a risky standalone step.
- All schema changes remain **additive** (`_ensure_column` /
  `CREATE TABLE IF NOT EXISTS`); user tables are never recreated (ARCHITECTURE §C.5).

### 3.3 Universal vs. module-only user data

The split that keeps twelve modules from each reinventing "favorites":

- **Universal user concepts** — *favorite, collection, user-tag* — make sense
  for **any** file and want to live at the **base, keyed by content hash**
  (`files_favorites`, `files_collections`, `files_user_tags`). One query answers
  "everything I favorited," across all modules.
- **Module-only user concepts** — things that only make sense inside one module
  (`manga_reading_state`, `anime_watch_progress`, `danbooru_artist_follows`,
  `danbooru_blacklist_tags`) — live in **module tables**.

**Staging (important):** Danbooru already has working `favorites` / `collections`
tables. **V1.1.0 keeps them as `danbooru_*` (grandfathered).** The universal
`files_favorites` unification is **deferred** to a later release, once a second
module makes the duplication real. Table names are chosen now so the door is
open; the migration is not done now.

Illustrative end-state map (not all built at once):

```
user.sqlite (one file)
  suite_enabled_modules, suite_settings            ← the suite
  files_sources, files_folder_roles                ← the base
  files_favorites, files_collections, files_user_tags   ← base, universal (future unification)
  danbooru_blacklist_tags, danbooru_artist_follows, danbooru_user_image_tags   ← booru-only
  danbooru_favorites, danbooru_collections          ← grandfathered now; fold into files_* later
  manga_reading_state, manga_bookmarks              ← future
  anime_watch_progress                              ← future
  music_playlists, music_play_counts                ← future
```

### 3.4 Concurrency

- Per-module index DBs are separate files → base scan and Danbooru sync never
  collide.
- All modules **share** `user.sqlite`; SQLite allows one writer at a time. Use
  **WAL mode** on `user.sqlite` and keep writes short. Confirm WAL as part of
  the §3.1 promotion.

---

## 4. Content identity & folder roles (locked)

### 4.1 Identity is by content hash (MD5)

- A file's durable identity is a **content hash**, not its path. This makes
  metadata and user data **survive moves and renames**. Danbooru already uses
  MD5 as its content key (ARCHITECTURE §E) and already stores per-file
  `local_md5` ([schema.py](../../backend/schema.py) `files.local_md5`, indexed).
- **Hashing is lazy and on-demand, never a per-file tax.** Browsing/listing
  needs only path + size + mtime. A hash is computed only when a feature needs
  it: a module claims/enriches the file, the file moves and needs re-identifying,
  or duplicate detection is requested.
- Dedup optimization: two files can be duplicates only if they share an exact
  byte-size, so only size-colliding candidates are ever hashed.

### 4.2 Folders carry a role

- Generalize the existing `registered_folders` concept: every registered folder
  is assigned exactly one canonical role: **Files** (`files`, browse only) or
  one enabled **module** (that module manages/enriches it). The legacy spelling
  `base` reads as `files` without a global rewrite.
- Example: `general/` (Files role) vs `danbooru/` + `danbooru_peak/` (Danbooru
  role). Moving a file between two Danbooru-role folders keeps it managed;
  moving it to `general/` makes it "just a file," with its hash-linked metadata
  preserved (archived) and re-attachable if moved back.
- Role answers *"who manages this location?"*; hash answers *"this content's
  metadata."* They are complementary. (This mirrors FileBrowser Quantum's
  "sources with rules.")

### 4.3 Missing ≠ deleted

- When a file disappears from its path, the base marks it **unavailable**, not
  deleted. If the same hash reappears elsewhere (a move), it **re-links**
  automatically. A truly deleted file shows as unavailable rather than silently
  dropping the user's favorite. Never destroy user data because a *file* moved.

---

## 5. Metadata ownership & "modules claim files" (locked)

- **The base authors and stores no metadata.** `files.sqlite` holds only
  disk-derived facts, which is what keeps it disposable. There is exactly **one
  metadata authority per file**, and for booru images that is Danbooru
  (sidecars remain the durable store, ARCHITECTURE §C.2).
- **The base never reads a module's database.** That would invert the
  dependency direction. Instead:
- **Modules claim files.** Each enabled module registers a capability with the
  suite shell: *"given a file identity (hash), do I own it? If so, here is a
  deep-link."* The base renders a read-only chip (e.g. "↗ open in Danbooru")
  from whatever the shell returns, without knowing what a tag is.
- **Chip ships after the base.** The claim interface is designed in V1.1.0; the
  visible chip can land in a follow-up step so the base can ship as
  browse/search/preview first.

---

## 6. Module lifecycle (locked)

- **Enable / disable only.** No "purge" or "wipe" verbs in V1.1.0.
  - *Enable*: create `modules/<name>/`, run the module's migrations, mark
    `suite_enabled_modules` on, show its sidebar entry and views.
  - *Disable*: hide the entry, stop the module's code, **keep its index DB and
    its `user.sqlite` tables intact.** Re-enabling restores everything.
- **Removing/disabling a module never drops `user.sqlite` data.** Only
  disposable per-module index data may ever be deleted, and only on an explicit
  future action, never as a side effect of disable.
- **"The app boots" ≠ "Danbooru boots."** Suite startup becomes small: open
  `user.sqlite`, read enabled modules, initialize each. All Danbooru-specific
  startup (its DBs, migrations, checkpoints, sidecar migration) becomes
  **conditional on the module being enabled.**

---

## 7. Error isolation (locked)

- One app, modules inside (a **modular monolith**, §9) → isolation is **not**
  free and must be built.
- **Every place a module's code runs (startup and background work) runs inside a
  catch boundary.** A module that throws is marked "failed to load," logs its
  full error to its own log stream, and the suite + base + other modules stay
  up. The base must never go dark because a module crashed.
- Per-module logs continue the existing dated, rolling, module-scoped scheme
  (ARCHITECTURE §G); a suite-level log records "module X failed to load."

---

## 8. API namespacing (locked)

- The frontend↔backend contract stays **REST over HTTP with FastAPI + the
  OpenAPI snapshot** — no change of API technology. This is the same three-tier
  shape FileBrowser Quantum uses (Go + Vue + REST + SQLite); Keivotos is already
  built this way.
- **Base endpoints:** `/api/files/*`, always available.
- **New module endpoints:** `/api/<module>/*` (e.g. `/api/manga/*`).
- **Danbooru's existing unprefixed routes are grandfathered** (`/api/images`,
  …). They are **not** renamed — the OpenAPI snapshot
  ([tests/snapshots/openapi.json](../../tests/snapshots/openapi.json)) freezes
  them and renaming buys nothing.
- **Routers stay always-mounted**; endpoints check enabled-state rather than
  appearing/disappearing, so the snapshot is stable regardless of which modules
  are on.

---

## 9. Frontend architecture (locked)

- **Modular monolith, not micro-frontends.** One SPA, one build. Each module
  owns its own views **and its own chrome** as components inside the one app.
  Micro-frontends solve a many-teams problem Keivotos (one developer) does not
  have, and would multiply the `core.py`-style coupling. (Confirmed by research;
  "monolith first, but modular.")
- **A module layer sits above `viewMode`.** Introduce an `activeModule` concept
  (base = Files, plus each enabled module). The Keivotos suite sidebar switches
  modules; each module keeps its own internal view set. The existing "no router,
  `viewMode` drives the view, ImageDetail is an overlay" contract (ARCHITECTURE
  §F) is preserved *within* a module.
- **Module chrome stays separate.** The Keivotos suite sidebar/drawer and the
  Danbooru library sidebar are distinct and are never merged behind one generic
  drawer (consistent with MODULAR_ARCHITECTURE_PLAN §11 motion ownership). The
  Danbooru sidebar's broken-motion restoration is still owed and unchanged by
  this contract.

### 9.1 Router / URL scheme (reserve now, ship later)

- A client-side **router** (remembering current module/view/search/filters via
  the URL) was planned for **V1.1.1**, deferred to **V1.1.2**, and is now
  scheduled for **V1.1.3** (V1.1.1 shipped the Files info panel and the
  `core.py` removal; V1.1.2 is the Files-browsability cycle). Its purpose is
  "remember what I searched and where I was." It is deferred deliberately: it
  rewires core navigation state, which is the highest-risk thing to fold into a
  feature cycle.
- **The URL scheme is reserved in V1.1.0** even though the router ships later,
  because the scheme is defined by the module shell and is expensive to retrofit.
  Reserved shape: `/<module-or-base>/<view>?<query/filters/folder>` — e.g.
  `/danbooru/browse?q=cat_ears&rating=g`, `/files/library/photos?q=vacation`.

---

## 10. The Files base — behavior (locked scope for V1.1.0)

- **Type-agnostic.** The unit is "file," not "image." `a.png`, `w.webp`,
  `1.gif`, `lll.docx`, `data.xlsx` all coexist. The base must not assume image.
- **Index cheaply up front** (name, path, size, mtime, ext). No opening files,
  no thumbnails during the initial scan — this survives very large trees.
- **Thumbnail on view, not on index**, cached, regenerated only on change.
  Reuse the WebP approach in [thumbnails.py](../../backend/thumbnails.py). Accept
  that the base and Danbooru will duplicate thumbnails in V1.1.0; a shared
  thumbnail service is a later base-extraction.
  **Status (verified 2026-07-25): there is nothing to extract.**
  `backend/thumbnails.py` already sits at backend top level, imports only
  `config` and PIL, and exposes `ensure_thumbnail(path, size, content_md5)` —
  a plain path API with no Danbooru concept in it. Because the cache key is the
  **content MD5**, the same bytes seen by two modules resolve to the *same*
  cache file, so the feared duplication does not occur either. V1.1.2's Files
  thumbnails call the existing function directly. The only real divergence is
  that `SUPPORTED_IMAGES`/`SUPPORTED_VIDEOS` are narrower than the Files inline
  allowlist (no `avif`, `bmp`, `m4v`); widening them changes Danbooru behavior
  too and therefore gets its own commit and test.
- **Incremental re-scan** via a size+mtime manifest (the pattern
  `danbooru.sqlite` already uses); unchanged files are skipped.
- **Duplicate detection is a base capability** (only the base sees across all
  folders/roles), computed from the base's own lazy hashes — **not** owned by
  Danbooru, even though Danbooru carries per-file `local_md5` for its own
  post-matching.
- **File serving is the one new security-sensitive surface.** A general browser
  serves arbitrary paths, so the serving endpoint must **canonicalize the path,
  confirm it resolves inside a registered source, block traversal/symlink
  escape, and deny the metadata/credential/backup/log dirs** — reusing the
  existing denylist logic in [folders.py](../../backend/routers/folders.py)
  (`_is_generated_folder`). Loopback-only + host validation (ARCHITECTURE §G)
  still apply.

### 10.1 Deferred to V1.1.x (not V1.1.0)

- Rich previews for non-visual types (docx/xlsx/pdf) — V1.1.0 shows a **type
  icon** for these; visual media gets a thumbnail.
- Per-type **click behavior** beyond: visual media previews in-app, everything
  else opens externally / reveals in folder.
- Cross-everything universal search (V1.1.0 search is filename + type within the
  current source/folder).
- In-app Danbooru downloading (paste URL/tag/post-id → fetch via existing
  gallery-dl engine). Feasible and cheap (extends existing acquisition), but it
  is a **Danbooru-module** feature, not base.

---

## 11. Settings — three tiers (locked)

```
Settings
  Keivotos (suite)   theme, port, which modules are enabled, backup
  Files (base)       registered folders + roles, thumbnail behavior, scan cadence
  Danbooru (module)  gallery-dl folder, Danbooru credentials, watcher interval
  Reddit (module)    capture defaults, archive/storage/provider status
  Karaoke (module)   library/provider/player/storage status
  YouTube (module)   acquisition defaults, safety/status/storage
```

- Suite settings apply to everything; base settings to the neutral file view;
  each module's settings appear only when it is enabled and affect only it.
- "Which modules are enabled" lives in `user.sqlite` (`suite_enabled_modules`) —
  it is a user choice, therefore precious. Other settings may live per-tier.

---

## 12. Product identity (locked direction)

- [product.py](../../backend/product.py) moves from a hardcoded
  `MODULE_NAME = "Danbooru"` to a **suite-first identity** with a dynamic active
  module (window title, user-agent, log names derive from suite + active
  module). Version target `1.1.0`. This is done late, after the base and shell
  exist.

---

## 13. Sequencing & relationship to the core.py plan (locked)

The order is chosen to protect the working Danbooru module.

1. **Establish the green baseline first** (§15). No build starts from an unknown
   state.
2. **Build the Files base fully isolated.** New `modules/files/` (or
   `routers/files.py` + `services/files_*`), own `files.sqlite`, own
   `/api/files/*`, own scan/thumbnails. **No `from core import *`; the base
   never imports Danbooru.** The base becomes the second real consumer and the
   first vertical built to the modular target.
3. **Add the suite/module shell** (enable/disable, suite sidebar, conditional
   startup) — additive, touching none of Danbooru's internals.
4. **The `core.py` extraction was DEFERRED at the time of this contract**, and
   that call was right: it was not a prerequisite for the Files base. The
   deferral was lifted once Files shipped and both consumers existed; the
   extraction ran 2026-07-24/25 and `core.py` is now deleted. Original reasons
   for deferring:
   extracting a "shared base" from one consumer means guessing its shape; and it
   is the single most regression-prone work in the repo. Extract the genuinely
   shared base (thumbnails, path-safety, delta-scan) **later**, once Files and
   Danbooru both exist to reveal what is actually shared, behind the tripwires.
5. Duplication in the meantime (e.g. Files making its own thumbnails) is
   **accepted**; it is far cheaper than a wrong abstraction or a premature
   `core.py` rewrite.

---

## 14. Plugin future (design intent, not V1.1.0 work)

- A user-authored plugin system is a possible **V3/V4** direction. It is **not**
  built now, but the boundaries in this contract are exactly its groundwork:
  labeled `/api/<module>/*` surfaces, module-owned tables/views, and the
  "claim a file" capability are natural extension points; HTTP is a natural
  plugin boundary.
- The one rule to keep true **forever** so "internal module" and "third-party
  plugin" stay the same shape: **the base/suite never reaches up into a specific
  module's internals.** Do not build the plugin door now; do not wall it up.

---

## 15. Baseline gate (do this before any code)

Prove the current app is healthy so any later breakage is attributable:

```powershell
uv run python -m unittest discover -s tests -v     # backend, incl. OpenAPI snapshot + /api/images golden
cd frontend
npm.cmd run check                                  # frontend types
npm.cmd run build                                  # frontend compiles
```

Record the green result. It is the regression tripwire referenced throughout.
The Files base additionally gets its own tests from day one (it is isolated and
easy to test). Additive-only discipline: nothing is deleted from Danbooru
because it "looks unused."

**Baseline recorded 2026-07-21 (green):**

- backend `unittest discover -s tests`: **102 tests, OK**;
- frontend `npm run check`: **114 files, 0 errors, 0 warnings**;
- frontend `npm run build`: **built OK, 154 modules**.

### Build progress (V1.1.0)

- **Slice 1 — Files index engine (backend, isolated): DONE, green.**
  `backend/files_base/` (`schema.py`, `index.py`): `files.sqlite` schema (WAL),
  `scan_source` (cheap stat facts, no hashing, type-agnostic, missing≠deleted),
  `list_directory`, `search_by_name`, `drop_source`. No `core`/Danbooru imports.
  `config.py` adds `BASE_HOME` / `FILES_DB_PATH` at `SUITE_HOME/base/`.
  Tests: `tests/test_files_base.py` (5).
- **Slice 2 — Sources + `/api/files/*` router (backend): DONE, green.**
  `files_base/sources.py` owns the `files_sources` table in `user.sqlite`
  (add-in-place; `user.sqlite` promotion still deferred). `routers/files.py`:
  list/register/scan/remove sources, browse, search — isolated, always mounted.
  Removal un-indexes only; never touches disk. OpenAPI snapshot regenerated
  (additive `/api/files/*`). Tests: `tests/test_files_api.py` (6).
  Full suite after Slice 2: **113 tests, OK.**
- **Slice 3 — Frontend module shell: FIRST ATTEMPT REVERTED.** The first attempt
  added a parallel `SuiteRail.svelte` and restructured `App.svelte`, which
  **duplicated the existing Keivotos module drawer** (`components/AppDrawer.svelte`,
  opened from the TopBar — it already lists the Danbooru module and a "Coming
  Soon" slot) and broke the established layout. This was a design regression and
  was fully reverted: `App.svelte` and `stores.ts` restored git-clean, `SuiteRail`
  deleted. `FilesView.svelte` and `lib/filesApi.ts` remain in the tree but are
  **inert (not imported)**, kept for the corrected integration.
- **Slice 3 (redone) — Files as the base surface via the existing drawer: DONE,
  verified in browser.** Correct model: **Files is the base top-level surface**
  (default), Danbooru is a module; the EXISTING `AppDrawer.svelte` is the
  switcher (no new rail). Changes: `stores.ts` re-adds `activeModule` (default
  `files`); `AppDrawer.svelte` gains a **Files** entry at the top (tagged "Base")
  above the Danbooru module, wired to `activeModule` with active highlighting;
  `FilesView.svelte` gets its own suite top bar (hamburger → same Keivotos
  drawer + "Files · Keivotos base" branding); `App.svelte` renders `FilesView`
  when `activeModule==='files'` else the **byte-identical** Danbooru chrome
  (its structure untouched — that is what the first attempt broke). Frontend
  `check`: **116 files, 0 errors**; `build` OK. Browser: Danbooru surface
  unchanged; drawer shows Files (base) + Danbooru (module) + Coming Soon;
  switching to Files shows the base with its own bar, sources, and browse grid.
- Backend (Slices 1–2) is unaffected by the revert: `files_base/` + `/api/files/*`
  remain isolated, tested, green (113 tests).
- **Slice 4 — Module enable/disable + first-launch gate: DONE, verified in
  browser.** Backend: `suite_modules.py` (isolated registry) owns
  `suite_enabled_modules` in `user.sqlite` (additive, in-place); `routers/suite.py`
  exposes `/api/suite/modules` (list) + enable/disable. **Nothing is enabled by
  default** → fresh launch shows only Files. Frontend: `lib/suiteApi.ts`,
  `enabledModules` store, `AppDrawer` gains an "Add a module" section with an
  **Enable** action (and ✕ to disable, keeping data), Profile gated on Danbooru
  enabled; `App.svelte` renders a module only when it is the active surface AND
  enabled, else Files. Verified: fresh = Files + "Add a module: Danbooru"; enable
  → Danbooru surface renders; disable → falls back to Files even with `danbooru`
  persisted as active. Backend **119 tests**; frontend **117 files, 0 errors**.
  NOTE: gates UI visibility only; Danbooru's backend still initializes at boot
  (the "app boots != Danbooru boots" startup decoupling remains deferred).
- **Slice 5 — user.sqlite promotion (§3.1): DONE, verified in browser.**
  `config.promote_user_database()` copies a legacy `modules/<module>/user.sqlite`
  up to `SUITE_HOME/user.sqlite` with WAL-checkpoint + size + `quick_check`
  verification, atomic install, and the legacy source preserved; idempotent and
  fail-closed. `USER_DB_PATH` now resolves to `SUITE_HOME/user.sqlite`; runs in
  the lifespan before `init_user_db`. Verified live: promotion logged, both files
  present and identical size, `files_sources` data survived (demo source
  browsable after promotion). Tests: `tests/test_user_db_promotion.py` (3).
- **Slice 6 — startup decoupling (partial, safe): DONE, verified in browser.**
  Lifespan now always runs suite-level startup (promotion, `init_user_db`,
  `init_data_db`, user-DB recovery checkpoint) but gates **Danbooru's background
  work — the sidecar-layout file-walk and the auto-ingest watcher — on the module
  being enabled** (`danbooru_module_enabled()`, fail-safe to enabled on read
  error). `run_startup_maintenance` split into `run_user_recovery_checkpoint`
  (always) + `run_sidecar_layout_migration` (gated); wrapper kept for compat.
  Verified live: with Danbooru disabled, log shows "Danbooru module not enabled;
  skipping its background startup" and the app boots on Files. SCOPE NOTE:
  `init_data_db` still runs (cheap schema only) so enabling Danbooru mid-session
  works without a restart; full artifact-level decoupling (no empty
  `danbooru.sqlite` when disabled) remains a later refinement.
- Full suite after Slices 5–6: **122 tests, OK**.
- **Slice 7 — Lazy hashing + duplicate detection (§4.1, §10): DONE, verified in
  browser.** `files_base/hashing.py`: MD5 computed on demand and **only for
  files whose byte-size collides with another file's** (unique sizes are never
  read); bounded batches (`compute_missing_hashes`, incremental + idempotent);
  `find_duplicates` groups identical content across ALL sources. API:
  `POST /api/files/hash`, `GET /api/files/duplicates` (snapshot regenerated).
  UI: a **Duplicates** toggle in the Files header that hashes in batches, then
  lists groups (count, md5, per-file source/path). Verified live: a planted
  copy was grouped "2× identical" with its original. Tests: +3 hashing tests
  in `test_files_base.py`. Backend **125 tests**; frontend **117 files, 0
  errors**.
- **Slice 8 — Folder-picker + Files UI polish: DONE, verified in browser.**
  Replaced the "paste an absolute path" input with a real folder picker:
  `files_base/filesystem.py` (read-only directory listing, drives on Windows) +
  `GET /api/files/fs`; `FolderPicker.svelte` modal (This PC → drives → folders →
  "Add this folder"). Sources panel widened (`w-72`, "Your folders" header),
  friendlier empty state ("No folders yet" + Add-a-folder call to action).
  Tests: +2 filesystem tests. Backend **127 tests**; frontend **118 files, 0
  errors**. Verified: picker browses `C:\` and lists directories.
- **Slice 8b — native Windows folder picker for Files: DONE.** Files' "Add
  folder" now opens the same native COM dialog Danbooru uses
  (`filesystem.native_pick_folder` → `scripts/windows_folder_picker.py`, via
  `POST /api/files/pick`); the in-app picker remains the non-Windows fallback.
  Backend **128 tests**; frontend **118 files, 0 errors**. Not browser-verified
  (the native dialog opens on the real desktop); backend test covers helper reuse.
- **Slice 9 — folder unification via projection (§4.2, "Option A"): DONE,
  verified in browser.** Decided: modules **publish** their folders into the
  shared browse-list rather than being rebuilt on top of it (keeps each module's
  storage core untouched, preserves module→base direction, scales to many
  modules — a single collapsed table would have to absorb every module's storage
  quirks). Danbooru keeps `registered_folders` as its source of truth and mirrors
  it into `files_sources` as role='danbooru' via: a register hook + a remove hook
  in `routers/folders.py`, and a startup `reconcile_danbooru_folders()` in the
  Danbooru-enabled lifespan branch (self-healing). Base helpers
  `upsert_module_source` / `remove_source_by_path` / `reconcile_module_sources`
  in `files_base/sources.py`; lazy scan-on-browse (`source_is_indexed`) so
  published folders show their files. Files UI shows a "Danbooru" badge on
  role='danbooru' folders and hides remove (managed by the module). Verified
  live: registering a folder in Danbooru made it appear in Files as
  role=danbooru, browsable (lazy-indexed img1/img2), badged, non-removable;
  base folders unchanged. Tests: +3 projection tests. Backend **131 tests**;
  frontend **118 files, 0 errors**.
- **Slice 10 — descriptor registry + suite/module identity split: DONE,
  automated and browser green.** `ModuleDescriptor` and the static registry define Files
  (required base) and Danbooru (optional) with owned paths, credentials,
  declared API/log prefixes, user agents, flags, and hooks. Keivotos owns the
  suite window/API title, suite-root `user.sqlite`, `backups/`, `logs/`, and
  `keivotos:` browser prefix. Verified copy/preserve migrations cover the
  legacy module user DB, module-scoped backup folder, and recognized browser
  keys. Danbooru route prefixing remains deliberately deferred.
- **Reddit fork extension — DONE 2026-07-27.** The same registry now includes
  Reddit as an optional descriptor at `<suite-home>/modules/reddit`. Its
  namespaced `/api/reddit/*` routes remain mounted while disabled and enforce
  enablement at the endpoint boundary; its module-owned frontend surface is
  resolved through the existing registry/surface switchboard.
- **Karaoke and YouTube extension — IMPLEMENTED LOCALLY 2026-07-28.** The
  registry now also includes optional Karaoke and YouTube descriptors with
  stable `/api/karaoke/*` and `/api/youtube/*` boundaries and create-only
  module-owned libraries published to Files. Karaoke owns its metadata-first
  local library, precious favorites/playlists/playback state, Kara.moe-first
  acquisition, lyrics, and shared local player. YouTube owns bounded yt-dlp
  search/format planning, confirmed local video/audio/caption acquisition, and
  a YouTube-inspired local-only surface. Their explicit handoff carries only
  query intent in the frontend and Files identity/local subtitle bytes on the
  return path; neither module reads the other's private database. The final
  isolated 2026-07-28 browser pass verified both published Files roots,
  local-only YouTube playback, Karaoke player/lyrics/queue behavior, saved
  settings, narrow layout, and the Files-identity return handoff; the full
  regression finished at 352 passing tests without a provider-media download.
- **Languages module — IMPLEMENTED LOCALLY 2026-07-28.** The registry
  includes an optional Languages descriptor at
  `<suite-home>/modules/language`. Its enabled publication hook initializes a
  rebuildable `language.sqlite`, contained versioned create-only media/staging,
  and additive precious `language_*` tables in the suite `user.sqlite`.
  Source-plus-source-key word identity survives note edits. Its Files role
  adopt/release hooks change only registry ownership and preserve study-folder
  bytes; publication keeps user-assigned study folders alongside the declared
  media root. The enabled-state-gated API, module-owned Svelte surface,
  searchable Settings category, manual/override/list/practice workflows, JSON
  export, and explicit read-only AnkiConnect preview/import jobs are complete.
  Page load performs no Anki request; the full ingest path is stub-tested and
  no live Anki operation was used for implementation verification.
- **Slice 11 — editable folder roles + filtered registry UI: DONE, automated
  and browser green.** `files_sources.visible` is an additive
  column. The Files wrench opens a staged Manage folders dialog for display-only
  rename, one role, show/hide, Add folder, counted ✕ forget, and bottom-right
  Save. `/api/suite/folders/apply` validates the full draft, then dispatches
  adopt/release through descriptor hooks. Release/forget retain all original
  files and sidecars; forget removes only registry/disposable index entries.
- **Slice 12 — registry-driven suite shell and Files chrome: DONE, automated
  and browser green.** `App.svelte` and `AppDrawer.svelte`
  resolve descriptors and module-owned UI actions with no Danbooru branch.
  Danbooru's former shell lives in its module surface. Files uses one compact
  breadcrumb/Search/Rescan/Duplicates bar, a visibility-filtered sidebar, and
  an open-folder icon + role + module header.
  The isolated 2026-07-23 browser pass verified fresh Files startup, automatic
  first-visible-folder opening, single-bar order, descriptor drawer/module
  activation, `Keivotos` versus `Keivotos - Danbooru` titles, staged rename and
  hide remaining unchanged before Save, persisted batch Save, staged role
  selection/Cancel, and an empty browser warning/error log.
- Still open (natural follow-ups): the "↗ open in Danbooru" click on a published
  file (§5 claim chip); relocate-hook parity (currently handled by the next
  startup reconcile).
- Still deferred: the module-claim chip (§5), previews/click-policy (§10.1),
  router (§9.1), full artifact-level Danbooru decoupling. Future/decision items:
  Docker mounted-storage auto-registration; multi-user/login/remote-download
  (reopens the local-first §G contract).

---

## 16. Deferred / out of scope for V1.1.0

- ~~`core.py` internal extraction~~ — done 2026-07-25; the file is deleted.
- Universal `files_favorites` unification (§3.3; after a second module).
- ~~Shared thumbnail service~~ (§10) — **dropped 2026-07-25: not needed.**
  `backend/thumbnails.py` is already a shared, path-based, content-keyed
  service; both consumers can call it as-is.
- ~~Shared range-serving helper~~ (§13) — **done 2026-07-25.** The duplicate in
  `files_base/serving.py` and `modules/danbooru/media_files.py` moved to
  `services/range_serving.py`; both re-export it, so every caller binds the same
  object and the OpenAPI snapshot did not move.
- The "↗ open in module" chip visible UI (§5; interface designed, chip later).
- Client-side router (§9.1; **now V1.1.3** — scheme reserved since V1.1.0).
- Rich non-visual previews, per-type click policy, universal search (§10.1).
- In-app Danbooru downloading (§10.1; a Danbooru-module feature).
- Any change to local-first / loopback-only / single-user posture
  (ARCHITECTURE §G) — unchanged.
- Renaming historical versions or archive folders.

---

## 17. Open items still to decide

- The exact shape of a future universal `files_favorites` table (deferred until
  a second metadata module needs it).
- Exact shape of the module "claim a file" capability interface.
- Failed-module presentation and recovery behavior once lifecycle error
  isolation is implemented.
- Base search: exact filter set (type/size) and result ordering for V1.1.0.
- Whether the base offers any universal favorite in V1.1.0 or defers all
  favoriting to modules (current lean: defer; base is browse/search/preview).

---

## 18. Decision summary (one-line each)

- Files is the **base**, always on; Danbooru, Reddit, Karaoke, YouTube, and
  Languages are optional **modules**.
- **Seven DBs now**: `files.sqlite` + `danbooru.sqlite` + `reddit.sqlite` +
  `karaoke.sqlite` + `youtube.sqlite` + `language.sqlite` (rebuildable indexes)
  + one precious `user.sqlite`; **+1 disposable index per future module**.
- **Promote `user.sqlite`** to the suite root via verified copy; rename
  Danbooru's tables to `danbooru_*` in that same migration; WAL on.
- **Identity = content hash**, computed lazily; **folders carry roles**;
  **missing ≠ deleted**.
- **Base authors no metadata**; **modules claim files**; dependency points
  **modules → base**, never back.
- **Enable/disable only**; suite boot ≠ Danbooru boot; **module crashes are
  caught** and never take down the base.
- **REST/OpenAPI kept**; base `/api/files/*`, modules `/api/<module>/*`,
  Danbooru routes grandfathered, routers always mounted.
- **One modular-monolith SPA**; module-owned chrome; **router in V1.1.3** with
  the URL **scheme reserved now**.
- **Base is type-agnostic**, indexes cheap, thumbnails/hashes lazy, **dedup is a
  base feature**, file-serving is security-gated.
- **Three-tier settings**; suite-first product identity.
- **Build Files isolated first; defer the `core.py` extraction** (later done);
  establish the
  green baseline before any code.
