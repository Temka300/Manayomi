# Keivotos / Waifu-Hoard Current-State Audit

Audit date: 2026-07-16  
Repository: `D:\Kivotos\Github_Wakaru\Keivotos-test`  
Git baseline: `main` at `66a9351`  
Current development identity: **V1.0.0 Pre-release 1**

Follow-up (2026-07-18): this document remains the read-only July 16 baseline.
The working tree has since advanced to **V1.0.0 Pre-release 5** and centralized
its release version workflow; release-identity drift described below is
historical audit evidence, not the current contract.

## Evidence Boundary

This is a read-only static audit of the current checkout and the archived
version folders named in `AGENTS.md`.

It records:

- code and files that exist;
- dependency and ownership relationships visible in source;
- tests and snapshots that exist;
- direct differences between archived files;
- user-reported broken behavior; and
- behavior that still needs runtime verification.

It does **not** claim that the application currently passes its test suite or
that interactive features work merely because their code exists. No build,
test, server restart, browser automation, database migration, real-data
operation, network operation, packaging action, or Git write was performed for
this audit.

Status terms used below:

- **Implemented in source**: the owning code and API/UI path exist.
- **Regression-protected in source**: a relevant automated test or snapshot
  exists, but it was not executed during this audit.
- **User-reported broken**: the user has directly reported that the behavior
  does not work in the running application.
- **Statically broken**: the source tree has a directly provable missing
  dependency or contradiction.
- **Unverified**: the code exists, but current runtime behavior has not been
  exercised.
- **Future**: planned material that must not be described as current behavior.

## Executive Findings

1. The current Waifu-Hoard source is not an unknown intermediate mixture. The
   97 sampled application, backend, frontend, script, configuration, and test
   files are byte-identical to:
   `D:\Kivotos\Github_Wakaru\V1.0.0 - (Release soon 1) - from zero`.
2. `backend\core.py` is still the main coupling point. It is 3,157 physical
   lines and exports almost its entire namespace. All nine domain router files
   use `from core import *`.
3. Backend routing has been split physically, but not yet separated by explicit
   dependencies. `backend\server.py` is a small composition root, while the
   routers still depend on the compatibility facade for database handles,
   models, helpers, constants, path operations, external API helpers, and tool
   state.
4. Path handling is partially centralized:
   `backend\config.py` owns configured locations and
   `backend\storage_layout.py` owns stable root identity and canonical sidecar
   paths. Path interpretation, containment, move/delete targets, helper
   locations, and pipeline defaults are still distributed across multiple
   files.
5. The Waifu-Hoard sidebar animation is **user-reported broken** even though
   its later CSS transition implementation and a source-string regression test
   exist.
6. The current sidebar file is byte-identical from V1.0.0 Beta4 through
   Release Candidate 5 and Release soon 1. V1.0.0 Beta3.1 used Svelte's
   `transition:slide`; Beta4 replaced it with one persistent panel animated by
   CSS width and transform transitions while adding delayed grip reveal.
7. Existing sidebar coverage verifies strings and DOM-shape assumptions only.
   It does not verify actual transition frames, reversal timing, rapid toggles,
   dragging, delayed reveal, hover return, saved position, or scrolling.
8. Documentation has state drift. Several important documents describe V1.10
   as current, several describe a completed V1.0.0 release, and several still
   use the old `127.0.0.1:8000` URL. The current product constant uses
   `localhost:52325`.
9. The roadmap lists OpenAPI and golden-response characterization tests as not
   started even though both snapshots and their tests exist.
10. `Waifu-Hoard-Hoarder` is statically incomplete: its
    `backend\server.py` imports `downloader`, and its README lists
    `backend\downloader.py`, but that file is absent.
11. No existing code has been classified as safely removable. The wildcard
    compatibility facade makes static "unused" conclusions unsafe because
    indirect consumers are difficult to prove.

## Repository State

### Git and private working documents

- Current branch: `main`
- Current commit: `66a9351`
- Remote tracking: `origin/main`
- `AGENTS.md`, `CHANGELOG.md`, `.agents\`, `.claude\`, `.codex\`,
  `.reconstruction\`, and `docs\important\` are locally excluded through
  `.git\info\exclude`.
- `docs\refactor-brief.md` is locally excluded and is a private instruction
  document, not a public GitHub document.
- The ignored local `artifacts\` tree, `download.png`, and root
  `gallery-dl.spec` exist. They are not authoritative source files and must not
  be deleted or repurposed during refactoring without separate permission.

### Current top-level structure

```text
Keivotos-test/
├── .agents/                    local agent state, excluded
├── .claude/                    local launch settings, excluded
├── .codex/                     local Codex state, excluded
├── .git/
├── .github/                    issue and pull-request templates
├── .reconstruction/            local reconstruction evidence, excluded
├── .venv/                      local Python environment
├── artifacts/                  local packaging outputs
├── assets/
│   └── branding/
│       ├── keivotos/
│       └── waifu-hoard/
├── backend/
│   ├── routers/
│   ├── services/
│   ├── automation.py
│   ├── backup_bundle.py
│   ├── config.py
│   ├── core.py
│   ├── credentials.py
│   ├── database.py
│   ├── local_recovery.py
│   ├── models.py
│   ├── product.py
│   ├── runtime_logging.py
│   ├── schema.py
│   ├── security.py
│   ├── server.py
│   ├── storage_layout.py
│   ├── tag_history.py
│   └── thumbnails.py
├── docs/
│   ├── assets/
│   ├── build/
│   ├── important/
│   ├── user/
│   ├── project-direction.md
│   └── refactor-brief.md
├── frontend/
│   ├── dist/
│   ├── public/
│   └── src/
│       ├── components/
│       ├── lib/
│       ├── App.svelte
│       ├── app.css
│       └── main.ts
├── packaging/
│   └── windows/
├── scripts/
│   └── release/
├── tests/
│   └── snapshots/
├── Waifu-Hoard-Hoarder/
│   ├── backend/
│   └── frontend/static/
├── AGENTS.md
├── app.py
├── CHANGELOG.md
├── config.json
├── pyproject.toml
├── README.md
├── run.bat
└── uv.lock
```

### Area sizes

These counts include direct files in the named directory, not recursive
dependency folders:

| Area | Direct files | Bytes |
| --- | ---: | ---: |
| `backend\` | 17 | 228,019 |
| `backend\routers\` | 10 | 123,514 |
| `backend\services\` | 4 | 16,975 |
| `frontend\src\components\` | 26 | 599,265 |
| `frontend\src\lib\` | 5 | 42,317 |
| `scripts\` | 5 | 108,810 |
| `tests\` | 24 | 105,278 |
| `docs\important\` before this audit | 10 | 111,983 |

## Largest and Highest-Risk Files

Physical line counts include blank lines.

| File | Physical lines | Current responsibility |
| --- | ---: | --- |
| `backend\core.py` | 3,157 | lifespan, app, compatibility exports, search, media identity, relations, wiki, artist/profile logic, shared collection/profile queries, tool execution |
| `scripts\danbooru_gallery_dl.py` | 2,504 | acquisition, sidecars, indexing, imports, cleanup, CLI search |
| `frontend\src\components\ImageDetail.svelte` | 1,549 | overlay, media interaction, tags, favorites, collections, relations, moves/deletes |
| `frontend\src\components\HomeView.svelte` | 1,233 | Classic and Discovery Home, spotlight, rails, neighborhoods, timing |
| `frontend\src\components\AppSettingsModal.svelte` | 1,232 | settings shell, sections, search, persistence controls, lazy loading |
| `frontend\src\components\TagBrowseHeader.svelte` | 1,196 | tag/wiki banner, examples, artist controls, journey/profile media |
| `frontend\src\components\TagsBrowser.svelte` | 1,195 | tag lists, filters, pagination, in-section detail |
| `frontend\src\lib\api.ts` | 994 | all frontend API types and requests |
| `frontend\src\components\ImageGrid.svelte` | 974 | grids, filters, pagination, selection, bulk actions |
| `frontend\src\components\ProfileView.svelte` | 968 | profile statistics, favorites, collections, artist watchlist |
| `backend\routers\images_media.py` | 768 | image queries, random, detail, relations, tags, moves/deletes, media serving |
| `backend\models.py` | 569 | shared API request/response contract |
| `backend\routers\folders.py` | 478 | root listing, registration, browse, relocate, removal |
| `frontend\src\components\Sidebar.svelte` | 478 | folder/rating filters, blacklist, related/top tags, collections |
| `backend\database.py` | 463 | data/user connections, initialization, additive migrations |
| `frontend\src\components\TopBar.svelte` | 456 | navigation, search controls, filters, notifications, user menu |
| `backend\config.py` | 338 | resource root, Documents layout, runtime config, resolved paths |
| `backend\storage_layout.py` | 222 | stable root IDs, canonical/legacy sidecar locations, migration |
| `frontend\src\components\SidebarDock.svelte` | 203 | sidebar panel motion and draggable grip |
| `frontend\src\components\AppDrawer.svelte` | 183 | Keivotos drawer and its open/close animation |
| `backend\server.py` | 40 | router inclusion and built frontend delivery |

File size alone is not proof of bad design. The risk rises when a large file
owns unrelated domains or when many consumers import its entire namespace.
`core.py` has both risk factors. Several large Svelte components also need
feature characterization before decomposition because they combine tightly
coordinated visual states.

## Current Backend Architecture

### Startup and composition

```text
app.py
  ├── resolves packaged/source resource root
  ├── imports backend configuration and product identity
  ├── configures logging and browser launch
  ├── dispatches packaged helper modes
  └── loads backend.server:app

backend/server.py
  ├── imports app from core.py
  ├── includes nine domain routers
  ├── serves frontend/dist index
  └── mounts static frontend assets

backend/core.py
  ├── constructs FastAPI app and lifespan
  ├── provides middleware
  ├── provides shared helpers and compatibility exports
  └── imports selected service namespaces back into core
```

This is partial modularization:

- **Physical separation exists**: endpoint bodies live in domain router files.
- **Dependency separation does not yet exist**: every router imports the entire
  `core` namespace.
- `core.py` ends with:
  `__all__ = [name for name in globals() if not name.startswith("__")]`.
- Home and Daily Challenge were extracted into services, but `core.py`
  wildcard-imports those services to preserve the compatibility surface.

### Router inventory

Static source contains 95 `@router` route decorators:

| Router | Route decorators | Core dependency |
| --- | ---: | --- |
| `artists.py` | 13 | `from core import *` |
| `collections.py` | 8 | `from core import *` |
| `discovery.py` | 5 | `from core import *` |
| `folders.py` | 7 | `from core import *` plus direct config/model imports |
| `images_media.py` | 15 | `from core import *` |
| `stats.py` | 1 | `from core import *` |
| `tags.py` | 2 | `from core import *` |
| `tools.py` | 29 | `from core import *` plus focused backend modules |
| `user_library.py` | 15 | `from core import *` |

The route split reduces `server.py` size and gives endpoints domain locations,
but a change to `core.py` can still affect every router.

### `core.py` responsibility map

Current approximate regions:

| Region | Responsibility |
| --- | --- |
| lines 140-564 | duplicate keys, media placeholders/ranges, registered roots, managed paths, moves/sidecars, view and heart state |
| lines 565-952 | file identities, summaries, Danbooru relation parsing/fetching/refresh |
| lines 953-1,054 | startup maintenance, lifespan, FastAPI app, security and timing middleware |
| lines 1,103-1,445 | search parsing and SQL construction |
| lines 1,496-1,510 | Home and Challenge compatibility service imports |
| lines 1,512-2,061 | tag wiki parsing, cache, related data, artist URL normalization |
| lines 2,141-2,655 | artist profile archives, gallery-dl resolution, followed-artist state and polling helpers |
| lines 2,657-2,844 | tag-combo and collection/profile query helpers |
| lines 2,845-3,156 | global tool state, command construction, subprocess progress, cancellation |

These are separate domains with different change and regression risks.

### Existing focused backend modules

Already separated:

- `config.py`: suite/module paths and runtime settings.
- `storage_layout.py`: stable root identities and sidecar location rules.
- `database.py`: connections, initialization, and user-schema migrations.
- `schema.py`: data database schema and indexes.
- `models.py`: Pydantic API models.
- `thumbnails.py`: cache generation and cleanup.
- `credentials.py`: credential storage and effective environment.
- `automation.py`: local watcher.
- `backup_bundle.py`: backup and restore.
- `local_recovery.py`: user database checkpoints.
- `tag_history.py`: removed-upstream tag recording.
- `security.py`: local browser request validation.
- `runtime_logging.py`: persistent runtime/access logging.
- `services\home.py`: Home discovery logic.
- `services\challenges.py`: Daily Challenge logic.
- `services\query_helpers.py`: rating and user-file identity query helpers.

These modules prove gradual extraction works, but the remaining wildcard facade
prevents a clear dependency graph.

## Current Frontend Architecture

### Application shell

- `frontend\src\App.svelte` uses a `viewMode` store rather than a router.
- `SidebarDock` mounts only for `gallery` and `tags`.
- `ImageDetail` is an overlay driven by selected image/profile-asset stores.
- `TopBar` owns suite drawer entry, Home/navigation controls, search-adjacent
  controls, notifications, and user menu.
- Persistent browser settings are implemented through `persistedWritable` in
  `frontend\src\lib\stores.ts`.
- API types and calls are centralized in `frontend\src\lib\api.ts`.

### View inventory present in source

The following `viewMode` values exist:

```text
home
profile
gallery
favorites
collections
collection-detail
tags
popularity
timelapse
challenges
```

Their component or grid ownership exists in source. Reachability and behavior
still require runtime smoke verification.

### Frontend coupling risks

- `ImageDetail.svelte` owns many unrelated mutations and media interaction
  states.
- `AppSettingsModal.svelte` owns the settings navigation shell, many individual
  preferences, lazy section loading, search, reset behavior, and presentation
  isolation.
- `HomeView.svelte` contains two layouts plus timed spotlight and moving-lane
  behavior.
- `TagBrowseHeader.svelte` combines wiki rendering, examples, tag navigation,
  artist following, journey, and profile-media archive behavior.
- `TagsBrowser.svelte` combines list browsing and in-section detail state.
- `ImageGrid.svelte` combines fetch/cache behavior, filters, pagination,
  duplicate review, selection, and batch operations.

These files should not be split only to reduce line count. Their state
transitions and immediate-update behavior need characterization first.

## Storage and Path Audit

### Existing authoritative boundaries

`backend\config.py` currently owns:

- source/frozen resource root;
- Windows Documents Known Folder lookup;
- `KEIVOTOS_HOME`;
- suite and module homes;
- runtime configuration location;
- default library, metadata, gallery-dl, backup, and log locations;
- resolved `DATA_ROOT`, `METADATA_DIR`, `GALLERY_DL_DIR`;
- derived database, thumbnail, sidecar, profile-archive, and credential paths;
- safe flattening of the former `metadata\` wrapper;
- persisted runtime settings.

`backend\storage_layout.py` currently owns:

- new and deterministic stable root IDs;
- loading roots from `user.sqlite`;
- longest matching registered root;
- media root/relative identity;
- canonical sidecar paths;
- legacy hashed and mirrored sidecar paths;
- candidate lookup order;
- containment-checked root sidecar directories;
- current central sidecar enumeration; and
- copy-and-verify legacy migration.

### Distributed path responsibilities

Static search found path-related constants or resolution across many files:

| Pattern | Python files containing it |
| --- | ---: |
| `DATA_ROOT` | 11 |
| `METADATA_DIR` | 9 |
| `SIDECAR_DIR` | 8 |
| `USER_DB_PATH` | 17 |
| `DATA_DB_PATH` | 12 |
| `GALLERY_DL_DIR` | 5 |
| `Path(__file__)` | 31 |
| `.resolve(...)` | 39 |
| `.expanduser(...)` | 6 |
| sidecar-related logic | 19 |

Not every occurrence is duplication. Consumers legitimately need resolved
paths. The architectural problem is that policy is still implemented outside
the central boundary:

- `core.py` implements `ensure_managed_path`, `folder_target`, and sidecar
  wrappers.
- `routers\folders.py` performs generated-folder exclusion, registration,
  relocate, containment, path rewriting, and sidecar deletion traversal.
- `routers\images_media.py` resolves move/delete/open targets.
- `routers\tools.py` implements `_resolve_tool_folder`.
- `scripts\danbooru_gallery_dl.py` has its own project-root resolution, sidecar
  candidates, defaults, archive paths, and registered-root loading.
- `app.py` separately resolves source/frozen resources.
- release scripts separately resolve repository and artifact roots.

### Confirmed duplicated concepts

1. **Search parsing**

   - Application search: `backend\core.py::parse_search_terms`
   - Standalone CLI search:
     `scripts\danbooru_gallery_dl.py::parse_search_terms`

   These are similar but not one shared contract. The reconstruction ledger
   already states the CLI version was reimplemented and can differ.

2. **Sidecar candidate resolution**

   - `backend\storage_layout.py::sidecar_candidates`
   - `backend\core.py::sidecar_candidates` compatibility wrapper
   - `scripts\danbooru_gallery_dl.py::sidecar_candidates_for`

3. **Folder/path interpretation**

   - `backend\config.py::_resolve_path`
   - `backend\core.py::folder_target`
   - `backend\core.py::ensure_managed_path`
   - `backend\routers\tools.py::_resolve_tool_folder`
   - direct resolution in folder and image routers

4. **Tool command/root assembly**

   - `core.py` builds pipeline subprocess commands from runtime configuration.
   - the pipeline script also maintains direct CLI defaults under `data\`.

The standalone CLI may need different defaults, but that distinction must be
explicit and tested rather than accidental.

## Database and Data Ownership

Source implements the documented two-database split:

- `danbooru.sqlite`: rebuildable media/index state.
- `user.sqlite`: favorites, collections, tags, follows, views, registered
  roots, and other irreplaceable local state.

Positive boundaries visible in source:

- additive user migrations in `database.py`;
- data schema and indexes in `schema.py`;
- file-identity helpers separated into `services\query_helpers.py`;
- backup/restore in `backup_bundle.py`;
- automatic checkpoints in `local_recovery.py`;
- root identity in `storage_layout.py`;
- removed tag history in `tag_history.py`;
- thumbnail cache separated as derived state.

Risk:

- Database path constants and `ATTACH DATABASE` calls are imported directly
  into several routers.
- Query construction remains split between `core.py`, routers, and services.
- Tests patch module-level path constants in multiple modules, showing that
  configuration is captured at import boundaries rather than passed as one
  explicit runtime dependency.

No database or sidecar mutation was performed during this audit.

## Acquisition and Import Pipeline

`scripts\danbooru_gallery_dl.py` remains a second very large subsystem. It
contains:

- gallery-dl acquisition;
- metadata normalization;
- sidecar writing and archiving;
- backfill;
- orphan cleanup;
- full SQLite rebuild;
- incremental sync;
- four-phase import;
- root identity loading;
- standalone CLI search; and
- command-line parser definitions.

The backend tool runner in `core.py` constructs commands for this script,
tracks one active process, parses its progress protocol, keeps bounded output,
and triggers recovery/cache post-actions.

Separation exists at the process boundary, but command construction and
progress ownership remain in `core.py`. This is a candidate for a focused tool
execution service after its protocol is characterized.

## Feature Status

### Application shell and distribution

| Feature | Static status | Runtime status |
| --- | --- | --- |
| source/frozen shared entry | implemented in `app.py` | unverified |
| loopback-only host selection | implemented and test files exist | unverified |
| browser opening after readiness | implemented | unverified |
| frontend static delivery | implemented in `server.py` | unverified |
| portable resource check | implemented and test files exist | unverified |
| persistent runtime/access logs | implemented and test files exist | unverified |
| Windows packaging scripts | implemented | not run |
| V1.0.0 Pre-release 1 identity | **not aligned**; code says `1.0.0` | requires correction |

### Library and metadata

| Feature | Static status | Runtime/data status |
| --- | --- | --- |
| registered external roots | implemented; tests exist | unverified |
| duplicate leaf-name roots | implemented; tests exist | unverified |
| root relocation | implemented; tests exist | unverified |
| counted root removal | implemented; tests exist | unverified |
| canonical root-based sidecars | implemented; tests exist | unverified |
| copy-and-verify legacy sidecars | implemented; tests exist | unverified |
| incremental sync | implemented; tests exist | unverified |
| sidecar-less minimal indexing | implemented; golden snapshot exists | unverified |
| four-phase import | implemented; tests exist | unverified |
| local watcher | implemented; tests exist | unverified |
| manual backup/restore | implemented; tests exist | unverified |
| automatic user DB checkpoint | implemented; tests exist | unverified |
| thumbnail tiers/cleanup | implemented; tests exist | unverified |

### Browse, search, and image management

| Feature | Static status | Runtime status |
| --- | --- | --- |
| Browse grid | implemented | unverified |
| favorites grid | implemented through grid/store/API state | unverified |
| search syntax | implemented; focused and golden tests exist | unverified |
| category/negative/ID/filename/shape/dimension/date filters | implemented in parser/query code | unverified as a complete set |
| rating multi-select including Unrated | implemented; golden test exists | unverified |
| contextual random | implemented | unverified |
| pagination and sorting | implemented | unverified |
| duplicate review scopes | implemented | unverified |
| mass favorite/collection/move/delete APIs | implemented | unverified |
| ImageDetail overlay | implemented | unverified |
| zoom/drag | implemented in component | unverified timed interaction |
| user tags | implemented | unverified immediate update |
| favorite and Heart Spam | implemented | unverified immediate update |
| relations refresh | implemented; test exists | unverified |
| open location | implemented; test evidence exists | unverified |
| move/delete guards | implemented | not exercised |

### Discovery and specialized views

| Feature | Static status | Runtime status |
| --- | --- | --- |
| Classic Home | implemented | unverified |
| Discovery Home | implemented; tests exist for ranking/rotation | unverified |
| timed Spotlight | implemented; source tests cover data contract | unverified timing |
| three moving Home lanes | implemented | unverified motion/pause/resume |
| tag neighborhoods | implemented | unverified |
| Popularity | implemented | unverified |
| Timelapse simple/advanced | implemented | unverified |
| fullscreen/fallback/Hide UI | implemented | unverified interaction |
| Daily Challenge | implemented through service and component | unverified |
| Home breadcrumb on special views | source-string test exists | unverified navigation |

### Tags, profile, and artist features

| Feature | Static status | Runtime/network status |
| --- | --- | --- |
| Tags browser | implemented | unverified |
| in-section tag detail | implemented | unverified state restoration |
| tag wiki cache | implemented | unverified |
| local and missing example presentation | implemented | unverified |
| favorite/pinned tags | implemented | unverified immediate update |
| tag combinations and blacklist | implemented | unverified |
| Profile | implemented | unverified |
| followed-artist watchlist | implemented | unverified |
| top-bar notifications | implemented | unverified |
| one-time notification baseline | implemented in backend helpers | network behavior not exercised |
| explicit artist profile-media archive | implemented | network behavior not exercised |
| no Twitter/X post fetching | documented and source intent visible | not network-audited |

### Settings

The five-section Settings implementation and its persistence keys exist.
Static source includes:

- section rail and content pane;
- control search and jump/highlight behavior;
- Browsing and Display reset behavior;
- lazy section data loading;
- settings presentation isolation;
- media playback, motion, scale, Home, Browse, notification, sidebar, fit,
  image size, page size, rating, and tag-banner preferences;
- Library, Metadata, Safety/Recovery, backup, import, credential, automation,
  and thumbnail surfaces.

All are unverified as current interactive behavior. No automated browser test
currently exercises the complete Settings layout or its timed highlight,
scroll, pause/resume, and lazy-loading behavior.

## Animation and Motion Audit

### Animation-bearing source

Static animation/transition definitions are concentrated in:

- `HomeView.svelte`: Svelte fade, Spotlight progress, moving lanes, hover
  transitions.
- `AppSettingsModal.svelte`: modal and section/control transitions.
- `ProfileView.svelte`: focused artist panel and related transitions.
- `ImageDetail.svelte`: overlay/media interaction transitions.
- `AppDrawer.svelte`: explicit drawer/backdrop in and out keyframes.
- `SidebarDock.svelte`: sidebar width/transform and grip reveal transitions.
- global reduced-motion and Settings pause rules in `app.css`.

### Keivotos app drawer

`AppDrawer.svelte` has explicit open and close animations:

- `drawer-in`
- `drawer-out`
- `drawer-backdrop-in`
- `drawer-backdrop-out`

Closing is delayed by 180 ms before the component dispatches its final close.
Reduced-motion rules shorten the animation. This behavior exists in source but
was not exercised.

### Waifu-Hoard sidebar and grip

Current implementation:

- one persistent `<Sidebar />` instance;
- dock width transition over 280 ms;
- panel transform transition over 280 ms;
- open state controlled with `class:is-open`;
- draggable pointer-captured grip;
- keyboard grip repositioning;
- persisted vertical position;
- delayed reveal on mount and after toggle/drag;
- hidden visual with a live hover hotspot;
- vertical sidebar body scrolling in `Sidebar.svelte`.

User report:

- the sidebar animations are broken in the running application even though the
  code remains.

Existing test:

- `tests\test_sidebar_grip_contract.py` checks required source fragments,
  absence of `transition:slide`, one `<Sidebar />` instance, and mounting in
  Browse/Tags.

Coverage gap:

- it never renders the component;
- it never measures width or transform over time;
- it never toggles rapidly;
- it never verifies reversal;
- it never performs pointer dragging;
- it never checks saved position after remount;
- it never waits for delayed reveal/hide;
- it never checks hover return;
- it never checks sidebar vertical scroll;
- it never checks reduced motion.

### Sidebar archive lineage

| Version | Sidebar implementation |
| --- | --- |
| V0.0.2 Beta6 CSS slidefade | byte-identical to V1.0.0 Beta3.1 |
| V1.0.0 Beta3.1 | conditional mount with Svelte `transition:slide`, draggable grip |
| V1.0.0 Beta4 | persistent panel with CSS width/transform transitions, delayed grip reveal |
| V1.0.0 Beta5/Beta6 | same sidebar dock file as Beta4 |
| Release Candidate 1/2 | same sidebar dock file as Beta4 |
| Release Candidate 3/4/5 | same sidebar dock file as Beta4 |
| Release soon 1 | same sidebar dock file as Beta4 |
| current checkout | same sidebar dock file as Beta4 |

The restoration decision is therefore not "find the last file before RC5."
The current implementation has been unchanged since Beta4. The earlier
animation behavior to compare is Beta3.1, but directly restoring that file
would also restore conditional mounting and could reintroduce the later
overlap/state problems. The correct next step is a live behavior comparison and
a characterized hybrid or repair that retains the persistent panel and grip
features.

## Regression Net

Static inventory contains 85 test methods across 23 `test_*.py` files.

Existing categories:

- acquisition and credentials;
- automation;
- backup/restore;
- four-phase import;
- filename/rating search;
- Windows folder picker;
- root removal and relocation;
- frontend delivery;
- Home discovery data contracts;
- `/api/images` golden responses;
- local recovery;
- OpenAPI snapshot;
- regression fixes;
- release layout;
- schema;
- local HTTP security;
- sidebar source contract;
- sidecar storage layout;
- removed-tag history;
- thumbnails;
- tool progress;
- special-view navigation source contract.

### Strong existing backend contracts

- `tests\snapshots\openapi.json`
- `tests\snapshots\images.json`
- isolated temporary databases and media roots in many tests;
- backup/restore safety tests;
- path/root/sidecar safety tests;
- tool progress bounding tests;
- release-layout and `KEIVOTOS_HOME` checks.

### Current gaps

1. No real frontend E2E smoke pass exists.
2. Sidebar coverage is source-string characterization, not behavior.
3. Special-view breadcrumb coverage is source-string characterization.
4. No browser test covers TopBar ordering and menu interactions.
5. No browser test covers Settings scroll, search highlight, lazy loading,
   animation pausing, or video pause/resume.
6. No browser test covers immediate local-state updates across the full mutation
   inventory.
7. No browser test covers Home Spotlight timing and lane hover/focus behavior.
8. No browser test covers ImageDetail zoom/drag/exit boundaries.
9. Network-dependent Danbooru and artist-profile flows are not safely covered by
   a deterministic local contract.
10. The existence of snapshots is contradicted by ROADMAP status, showing the
    documentation is not currently a reliable test inventory.

## Documentation Audit

### Release identity drift

Current runtime/package metadata says `1.0.0`:

- `backend\product.py`
- `pyproject.toml`
- `frontend\package.json`
- `frontend\package-lock.json`
- `packaging\windows\version_info.txt`
- `scripts\release\build_windows.ps1`
- OpenAPI snapshot and release-layout assertions

Public docs describe V1.0.0 as completed. The user has clarified that the
current state is **V1.0.0 Pre-release 1**, and existing historical names must
not be retroactively renamed.

### Current-versus-future drift

The following describe V1.10 as current or shipped:

- `docs\important\ARCHITECTURE.md`
- `docs\important\PLAYBOOK.md`
- `docs\important\ROADMAP.md`
- `docs\important\PIPELINE.md`
- portions of `docs\important\FUTURE.md`
- historical `CHANGELOG.md` entries

V1.10 and post-V1.0 work are future planning, not current release state.
Historical changelog material needs careful preservation rather than blind
deletion; current-state documents need explicit future labels.

### URL drift

Current product constants and public source instructions use:

```text
http://localhost:52325
```

Several important documents still use:

```text
http://127.0.0.1:8000
```

Affected private important documents include `PLAYBOOK.md`, `PIPELINE.md`, and
`gallery-dl.md`. `docs\user\troubleshooting.md` correctly describes the origin
change.

### Test-roadmap contradiction

`docs\important\ROADMAP.md` marks these as not started:

- OpenAPI snapshot diff
- `/api/images` characterization/golden-master tests

The repository already contains:

- `tests\test_openapi_snapshot.py`
- `tests\snapshots\openapi.json`
- `tests\test_images_golden.py`
- `tests\snapshots\images.json`

### Architecture text drift

- `ARCHITECTURE.md` correctly recognizes `core.py` as over 3,000 physical
  lines, but the ownership map is incomplete because it does not show the
  wildcard dependency from every router.
- The docs describe the router split as stronger modularity than the imports
  currently provide.
- `RECONSTRUCTION_LEDGER.md` contains historically valid old line counts and
  recovery facts; those should be clearly separated from the current
  architecture rather than rewritten as if they never happened.
- `FEATURES.md` is a strong behavior register but is not yet a complete
  feature-to-code map with symbols, tests, archive lineage, and working/broken
  status.

## Archived Version Map

All named archive directories exist. An additional source snapshot also exists:

```text
D:\Kivotos\Github_Wakaru\V1.0.0 - (Release soon 1) - from zero
```

### High-level lineage visible in selected files

| Snapshot | Relevant structural state |
| --- | --- |
| V0.0.1 / early V0.0.2 | large original Sidebar and early application shell |
| V0.0.2 Beta4/Beta5 | first `SidebarDock` and `AppDrawer` iterations |
| V0.0.2 Beta6 CSS slidefade | Svelte slide sidebar lineage; expanded drawer motion |
| V1.0.0 Beta1-Beta3.1 | continued slide sidebar; Settings/storage/import changes accumulate |
| V1.0.0 Beta4 | persistent CSS sidebar dock begins; Home redesign |
| V1.0.0 Beta5/Beta6 | persistent sidebar retained; later product and performance changes |
| RC1/RC2 | packaging/release candidate state; same sidebar |
| RC3/RC4 | bug-patch copies; selected UI files mostly same |
| RC5 Worst Version | selected current backend/config/sidebar files already match current |
| Release soon 1 | sampled 97 current source/test files match byte-for-byte |

### Selected backend size lineage

| Snapshot | `core.py` physical lines / bytes | `config.py` physical lines / bytes |
| --- | ---: | ---: |
| V1.0.0 Beta3.1 | 3,692 / 133,724 | 113 / 3,761 |
| V1.0.0 Beta4 | 3,755 / 136,431 | 113 / 3,761 |
| RC2 | 3,363 / 122,737 | 164 / 5,654 |
| RC5 | 3,157 / 114,239 | 338 / 12,101 |
| Release soon 1 | 3,157 / 114,239 | 338 / 12,101 |
| current | 3,157 / 114,239 | 338 / 12,101 |

Byte size is included only as lineage evidence. It does not establish that a
smaller version preserved every feature.

## Broken, Partial, and Unverified Summary

### Confirmed or directly reported broken

1. **Waifu-Hoard sidebar animation**

   User-reported broken in the running application. Source and a static test
   remain, so the failure requires timed runtime diagnosis.

2. **Waifu-Hoard-Hoarder startup dependency**

   `Waifu-Hoard-Hoarder\backend\server.py` imports `downloader`.
   `Waifu-Hoard-Hoarder\README.md` lists
   `backend\downloader.py`. The file is absent from the current tree.

3. **Current release identity/documentation**

   Runtime/package/public docs describe full `1.0.0`; the user-defined current
   identity is V1.0.0 Pre-release 1.

### Partial architecture

1. Router files exist, but every router wildcard-imports `core`.
2. Home and Challenge services exist, but are wildcard-re-exported by `core`.
3. Configuration and sidecar layout are centralized, but path policy remains
   duplicated across core, routers, scripts, and launch/release helpers.
4. Backend snapshots exist, but frontend timed behavior has no E2E contract.
5. `FEATURES.md` records behavior but not complete symbol/test/archive
   ownership.

### Unverified high-value behavior

- all current browser animations and transitions;
- all immediate UI mutation paths;
- sidebar drag/reveal/reversal/scroll persistence;
- Home Spotlight and rail timing;
- Settings presentation isolation and search jump;
- Timelapse fullscreen/Hide UI;
- ImageDetail zoom/drag and exit boundaries;
- Profile focused panel transitions;
- followed-artist polling and profile archive network behavior;
- source and portable startup;
- current test/build health;
- real-data folder moves, removals, restore, sidecar cleanup, and imports.

## Code That Appears Unused

No code is approved for removal based on this audit.

Reasons:

- every router imports the entire `core` namespace;
- `core.__all__` exports almost every global;
- tests directly call internal helpers and patch module globals;
- background automation imports `core` dynamically and calls underscored tool
  helpers;
- packaged helper modes create callers outside normal direct imports;
- source and frozen launch paths differ;
- archived behavior may depend on code not obvious from one route;
- UI behavior can be driven by stores and reactive statements rather than
  direct call sites.

The correct process is:

1. replace wildcard imports with explicit dependencies for one domain;
2. add characterization for that domain;
3. search all source, tests, scripts, and packaged entry paths;
4. remove only a proven unreferenced compatibility export in a separate
   authorized change.

## Refactor Constraints Derived from the Audit

1. Do not refactor the sidebar before its current and archived motion are
   exercised live.
2. Do not restore Beta3.1 wholesale; retain the persistent single panel,
   draggable grip, saved position, delayed reveal, accessibility, and later
   scrolling fixes.
3. Do not call the existing router split complete modularization while
   wildcard imports remain.
4. Do not move all path code into one giant replacement module. Define smaller
   authoritative responsibilities:

   - configured application locations;
   - resource/executable locations;
   - library root identity;
   - sidecar identity and candidates;
   - containment and allowed mutations;
   - folder target resolution.

5. Do not share application search and CLI search until their intended syntax
   differences are documented and tested.
6. Do not split large Svelte components until their state and timed behavior
   have browser characterization.
7. Preserve `user.sqlite`, external originals, sidecars, sidecar history,
   credentials, backups, and archived release folders.
8. Keep every restoration and extraction as a separate small logical change.

## Required Next Artifacts Before Application Refactoring

1. Updated important documentation with current, historical, broken, and future
   states separated.
2. A feature-to-code map with:

   - stable symbol/component ownership;
   - temporary current line ranges;
   - API and persistence dependencies;
   - related tests;
   - archive lineage;
   - working/broken/partial/unverified status.

3. An agreed modular architecture and extraction order.
4. Browser characterization for the sidebar and other high-risk motion.
5. A current clean compile/test/check/build baseline when separately
   authorized.
6. A runtime smoke baseline at the active configured origin when separately
   authorized.

Only after those gates should restoration and gradual `core.py` extraction
begin.
