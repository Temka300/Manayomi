# Keivotos Modular Architecture Plan

Current development identity: see [ROADMAP.md](./ROADMAP.md#current-cycle)  
Plan date: **2026-07-16**  
Repository: `D:\Kivotos\Github_Wakaru\Keivotos`

> **STATUS 2026-07-25 — the `core.py` extraction described here is COMPLETE.**
> `backend/core.py` (3,231 lines) was reduced to zero behavior and deleted. No
> module wildcard-imports anything; every router imports its real owners.
> Danbooru behavior lives in `backend/modules/danbooru/`, shared helpers in
> `backend/services/`, and composition in `server.py` + `app_factory.py` +
> `lifecycle.py`. Read section 11.5 for what was actually executed and the two
> deliberate deviations from the staging below. **Sections 5 and 12 are the
> original plan and are now historical** — they describe a target tree and a
> stage order that were superseded in practice; do not treat them as pending
> work. The frontend items in section 13 remain genuinely outstanding.

This document defines the target architecture and the order for reaching it.
It is a design and migration plan, not a claim that the proposed files already
exist.

The plan is based on:

- `docs/important/archive/CURRENT_STATE_AUDIT.md`;
- `docs/important/FEATURE_CODE_MAP.md`;
- the locked decisions in `docs/important/ARCHITECTURE.md`;
- the OpenAPI-frozen API, three-database V1.1.0 model, storage rules, pipeline, tests,
  packaging paths, background jobs, and frontend behavior contracts; and
- archived lineage through V1.0.0 Pre-release 1.

No application-code change is authorized by this plan. Each restoration,
characterization, extraction, path-policy change, compatibility cleanup, and
frontend split remains a separate permission-gated change.

## 1. Required Outcome

The codebase should reach a state where:

1. A change to one product domain has an explicit and small dependency surface.
2. Routers translate HTTP input/output but do not own product behavior.
3. Domain services own behavior and do not import routers or the compatibility
   facade.
4. Storage and path policy have named owners instead of scattered local
   interpretations.
5. `core.py` is reduced gradually, first to an explicit compatibility facade
   and eventually removed only when no caller needs it.
6. API routes, response shapes, database schemas, browser persistence keys,
   animations, immediate UI updates, startup behavior, packaging behavior, and
   data-safety rules remain unchanged unless separately authorized.
7. Large frontend components are split only after their state, timed behavior,
   and mutation contracts are characterized.
8. Every migration slice can be reviewed, tested, and reverted independently.

The objective is lower coupling and safer change, not the smallest possible
line count. Moving the same coupling into a different giant file does not
complete the refactor.

## 2. Locked Constraints

The following are architectural invariants.

### Product and API

- The current identity is the cycle named in
  [ROADMAP.md](./ROADMAP.md#current-cycle); it is never restated here.
- V1.10 and post-V1.0 material are future-only.
- Existing grandfathered `/api` routes remain stable during architectural extraction;
  additive Files/suite routes are frozen by the current OpenAPI snapshot.
- OpenAPI names, parameter meanings, response models, error status codes, and
  JSON shapes remain stable unless an API change is separately authorized.
- The frontend remains client-router-free: `activeModule` selects the suite
  surface; Danbooru's `viewMode` controls its internal view and ImageDetail
  remains an overlay.
- Keivotos remains local-first, single-user, and loopback-only.

### Data

- Original media remains in place except for an explicit user-requested move or
  disk deletion.
- `danbooru.sqlite` remains the rebuildable library index.
- `user.sqlite` remains authoritative and must never be rebuilt or dropped.
- Cross-database user-data matching remains based on durable file identity, not
  transient row IDs.
- Sidecars remain the durable metadata store.
- Replaced sidecars are archived.
- Legacy sidecar migration remains copy-and-verify with preserved source.
- Schema changes remain additive and are not bundled into code movement.
- Backups continue to exclude original media, thumbnails, and credentials.

### Interface behavior

- Immediate initiating-view updates remain mandatory.
- Refresh tokens continue to reconcile other views after the local state
  changes.
- Top-bar order and control placement remain unchanged.
- The Keivotos app drawer and Danbooru library sidebar remain separate.
- Motion, transitions, delayed reveals, drag behavior, scrolling, state
  restoration, and reduced-motion behavior are product contracts.
- The user-reported broken sidebar must be characterized and restored before
  its component is structurally refactored.

### Migration discipline

- No wholesale rewrite.
- No simultaneous import-style conversion, file move, behavior rewrite, and
  cleanup in one change.
- No wildcard import in newly created modules.
- No new module imports `core`.
- No compatibility export is removed until every source, test, background,
  helper, source-launch, and frozen-launch caller is proven migrated.
- No code is classified as unused solely because a direct call is not found.

## 3. Current Coupling to Remove

The current dependency spine is:

```text
app.py
  -> backend/server.py
       -> backend/core.py::app
       -> nine routers
            -> from core import *

backend/core.py
  -> lifecycle and middleware
  -> path and sidecar wrappers
  -> image identity/activity/relations
  -> search parser and SQL builder
  -> tag wiki and Danbooru helpers
  -> artist profile archives and follows
  -> collection/profile helpers
  -> tool commands, process state, progress, and cancellation
  -> wildcard re-exports from Home and Challenge services
```

This is physical separation without dependency separation. A router can
currently receive almost any name in `core.py`, including names that are not
part of that router's intended domain.

The frontend has a similar, smaller coupling pattern:

```text
App.svelte
  -> large view components
       -> one broad api.ts client
       -> one broad stores.ts module
```

That structure is functional, but the largest components mix API orchestration,
state transitions, timers, presentation, and mutation behavior.

## 4. Target Dependency Direction

Backend dependencies must point downward only:

```text
launcher and packaging
        |
        v
composition: server.py + app_factory.py
        |
        +------> routers/
        |           |
        |           v
        |       services/
        |           |
        |           +------> integrations/
        |           +------> database.py / schema.py
        |           +------> path_policy.py / storage_layout.py / config.py
        |           +------> focused infrastructure modules
        |
        +------> lifecycle.py
                    |
                    +------> database initialization
                    +------> local recovery
                    +------> sidecar migration
                    +------> automation
```

Allowed dependency direction:

| Layer | May depend on | Must not depend on |
|---|---|---|
| Launcher | composition, product, resource bootstrap, logging | routers, domain service internals |
| Composition | app factory, routers, frontend static path | domain implementation details |
| Routers | FastAPI, request/response models, explicit services | `core`, other routers, filesystem policy implementation |
| Services | models/value types, database access, path policy, integrations | routers, FastAPI request objects, frontend |
| Integrations | credentials/config, standard HTTP/process libraries | routers, user-interface state |
| Storage/path modules | config values, value types, standard filesystem/SQLite | routers, feature UI, `core` |
| Foundation | standard library and lower-level value definitions | services, routers, `core` |
| Compatibility facade | explicit imports from new owners | new behavior, wildcard exports |

Frontend dependencies must point in this direction:

```text
App.svelte and view components
        |
        +------> feature-local controllers/state/helpers
        +------> domain API clients
        +------> shared cross-view stores
        |
        v
typed request layer
```

Frontend shared modules must never import Svelte view components. Feature-local
state must not be promoted into global stores unless another mounted surface
actually consumes it.

## 5. Target Backend Structure

The target is intentionally incremental. Existing focused modules stay in
place unless a later extraction proves that a move is useful.

```text
backend/
  server.py
  app_factory.py
  lifecycle.py
  core.py                       temporary explicit compatibility facade

  product.py
  config.py
  resource_paths.py
  runtime_logging.py
  security.py

  database.py
  schema.py
  models.py
  storage_layout.py
  path_policy.py

  thumbnails.py
  credentials.py
  automation.py
  backup_bundle.py
  local_recovery.py
  tag_history.py

  integrations/
    danbooru.py
    artist_profiles.py
    tool_process.py

  services/
    query_helpers.py
    search.py
    duplicate_review.py
    image_queries.py
    image_activity.py
    image_relations.py
    image_files.py
    image_mutations.py
    home.py
    challenges.py
    tags.py
    tag_wiki.py
    artist_follows.py
    artist_profile_assets.py
    collections.py
    user_library.py
    profile.py
    statistics.py
    folders.py
    tool_definitions.py
    tool_commands.py
    tool_runner.py

  routers/
    images_media.py
    discovery.py
    tags.py
    artists.py
    folders.py
    user_library.py
    collections.py
    stats.py
    tools.py
```

This tree is a responsibility map, not a requirement to create every file at
once. A module is created only when its extraction slice has a clear owner,
callers, and regression boundary.

### Files that should remain focused instead of being split automatically

- `models.py`: keep as the single API model contract until domain splitting
  materially improves navigation. Splitting models while moving behavior would
  add import churn without reducing behavior risk.
- `database.py`: keep connection gates and initialization together. Query
  behavior belongs in services, but connection lifetime and exclusive access
  remain one database concern.
- `schema.py`: remains the authoritative rebuildable data-DB schema.
- `storage_layout.py`: remains the stable-root and sidecar-identity owner.
- `backup_bundle.py`, `local_recovery.py`, `thumbnails.py`, `credentials.py`,
  `automation.py`, `tag_history.py`, `security.py`, and
  `runtime_logging.py`: already have cohesive ownership.
- `scripts/danbooru_gallery_dl.py`: remains a separately invoked process during
  initial backend modularization. Its internal split is a later independent
  project after the subprocess protocol is characterized.

## 6. Backend Module Ownership

### Composition and lifecycle

| Target owner | Responsibility | Current source |
|---|---|---|
| `app_factory.py` | Construct FastAPI application and attach middleware | `core.py:1018-1054` |
| `lifecycle.py` | Initialize DBs; start/cancel maintenance and automation tasks | `core.py:950-1015` |
| `server.py` | Include routers and serve the built frontend | Current `server.py`; remains small |
| `core.py` | Temporary explicit re-exports only | Current entire facade |

`server.py` should eventually import `app` from `app_factory`, not `core`.
During migration, `core` may re-export `app` for compatibility, but it must not
remain the construction owner.

### Image and search services

| Target owner | Responsibility | Current source |
|---|---|---|
| `duplicate_review.py` | Duplicate filename/group expressions and scope filter | `core.py:140-150` |
| `image_files.py` | Media placeholders, range parsing, streaming iterators | `core.py:177-224` |
| `image_queries.py` | Durable file identity, summaries, favorite metadata | `core.py:565-648` and query portions of `images_media.py` |
| `image_activity.py` | User tags, views, timestamps, Heart Spam | `core.py:392-496` |
| `image_relations.py` | Relation parsing, cache refresh, local relation models | `core.py:649-947` |
| `search.py` | One application search grammar and SQL predicate builder | `core.py:1103-1446` |
| `image_mutations.py` | Single/batch move and delete orchestration | Mutation bodies in `images_media.py` plus current `core` helpers |

Application search and standalone CLI search must not be merged merely because
their function names are similar. Their intended syntax must first be compared
and locked with shared or separate tests.

### Tags and artists

| Target owner | Responsibility | Current source |
|---|---|---|
| `tags.py` | Tag listing, suggestions, related/random tag queries | Current tag/artist router query bodies |
| `tag_wiki.py` | Wiki parsing, cache freshness, aliases, implications, examples | `core.py:1512-2061` |
| `artist_follows.py` | Follow state, baseline, post ID polling, seen state | `core.py:2460-2582` and artist router mutations |
| `artist_profile_assets.py` | Archive listing, content identity, persistence orchestration | `core.py:2141-2187`, `:2346-2406` |
| `integrations/artist_profiles.py` | Twitter/X and Pixiv profile discovery and validated byte retrieval | `core.py:2214-2345` |
| `integrations/danbooru.py` | Credentialed/rate-limited Danbooru JSON requests | `core.py:754` and other Danbooru request sites |

The integrations layer returns data or typed failures. It does not write
SQLite, select UI behavior, or create API responses.

### User library and profile

| Target owner | Responsibility | Current source |
|---|---|---|
| `collections.py` | Collection queries, preview items, CRUD, pinning, membership | `core.py:2715-2757` and collection router bodies |
| `user_library.py` | Favorites, favorite tags, combos, blacklist, user-tag operations | `core.py:2657-2705` and user-library router bodies |
| `profile.py` | Local profile aggregate and avatar/banner selection | `core.py:2793-2844` and stats/profile queries |
| `statistics.py` | Library statistics aggregation | Stats router body |

Service methods that mutate state return enough information for the initiating
frontend component to update immediately. They must not force a full view
reload as part of architectural extraction.

### Folders and tools

| Target owner | Responsibility | Current source |
|---|---|---|
| `folders.py` | Registration, rescan, relocation, removal preview/removal orchestration | Current folder router helper and endpoint bodies |
| `tool_definitions.py` | Stable five maintenance tool definitions | `routers/tools.py:38-70` |
| `tool_commands.py` | Build commands from runtime paths and selected roots | `core.py:2868-2961`, tool route command selection |
| `tool_runner.py` | Exclusive state, subprocess lifecycle, progress protocol, cancellation, post-success hooks | `core.py:2845-3137` |
| `integrations/tool_process.py` | Minimal process spawning/termination and stream reading | Process-specific part of current tool runner |

The tool runner owns the task state. Routers request a run, status, or cancel
operation and translate the result into the existing API models.

## 7. Centralized Path Architecture

Centralizing paths means centralizing **policy and interpretation**, not placing
every `Path` operation into one giant module.

### 7.1 Configured locations: `config.py`

`config.py` remains the only owner of:

- Windows Local AppData Known Folder resolution and preserved legacy Documents migration;
- `KEIVOTOS_HOME`;
- suite/module home;
- runtime config file;
- configured library, metadata, gallery-dl, backup, log, credential, thumbnail,
  sidecar, profile-archive, recovery, and database locations;
- relative-versus-absolute runtime configuration interpretation; and
- persisted watcher, backup, and thumbnail settings.

Target addition:

- expose an immutable `RuntimePaths` value containing resolved locations;
- retain current constants as temporary compatibility aliases;
- allow services/tests to receive `RuntimePaths` explicitly where that reduces
  import-time path capture.

Changing from constants to `RuntimePaths` must be a separate migration. It must
not be combined with moving or deleting files.

### 7.2 Resource and executable locations: `resource_paths.py`

This owner resolves:

- source versus frozen resource root after launcher bootstrap;
- frontend distribution path;
- packaged helper scripts;
- bundled `gallery-dl` and `ffmpeg`;
- pipeline script invocation; and
- executable-adjacent resources.

`app.py::resource_root` remains the unavoidable minimal bootstrap because the
backend path must be found before backend modules can be imported. After that
bootstrap, resource lookup should use the shared owner.

Repository roots and release-output roots remain release-script concerns, not
runtime storage concerns.

### 7.3 Root and sidecar identity: `storage_layout.py`

`storage_layout.py` remains the only owner of:

- stable and deterministic root IDs;
- longest matching registered root;
- root-relative media identity;
- canonical sidecar paths;
- legacy sidecar candidates;
- root-sidecar directory containment;
- current sidecar enumeration; and
- copy-and-verify migration.

Compatibility wrappers in `core.py` disappear only after all callers use
`storage_layout.py` explicitly.

### 7.4 Mutation and containment policy: `path_policy.py`

`path_policy.py` becomes the only owner of decisions such as:

- whether a path belongs to a configured or registered managed root;
- whether an action may read, move, delete, reveal, or write metadata for it;
- safe source/destination resolution;
- protection against traversal and root escape;
- generated/internal directory exclusions;
- registered-root selector resolution; and
- counted mutation plans for destructive actions.

Proposed value types:

```text
ManagedMedia
  absolute_path
  root_id
  relative_path
  display_folder

FolderTarget
  absolute_directory
  root_id
  display_name

MutationPlan
  sources
  destination
  affected_media
  affected_sidecars
  preserved_history
```

Services perform operations only after receiving a validated value or plan.
Routers and frontend labels must not recreate containment decisions.

### 7.5 Path consumers

| Consumer | Required owner |
|---|---|
| Folder registration/relocation/removal | `config.py`, `storage_layout.py`, `path_policy.py`, `services/folders.py` |
| Image open/move/delete | `path_policy.py`, `services/image_mutations.py` |
| Sidecar read/write/delete/migration | `storage_layout.py` plus pipeline |
| Tool folder selection | `path_policy.py`, `tool_commands.py` |
| Backup destination and staging | `config.py`, `backup_bundle.py` |
| Thumbnail paths | `config.py`, `thumbnails.py` |
| Artist profile archive | `config.py`, `artist_profile_assets.py` |
| Launcher/package resources | `resource_paths.py` |
| Direct CLI defaults | pipeline-specific adapter using explicit runtime arguments |

## 8. Database and Transaction Boundaries

The refactor does not introduce a generic repository framework.

Rules:

1. `database.py` owns connection context managers, initialization, row factory,
   user DB attachment, and exclusive access.
2. `schema.py` owns the data DB schema.
3. A pure query helper accepts a connection when practical.
4. A service owns its transaction when multiple statements must succeed or
   fail together.
5. Routers do not contain reusable SQL after their domain extraction.
6. Services do not cache a connection globally.
7. Database file paths are obtained from the configured runtime boundary, not
   copied into new module constants without need.
8. Backup restore continues to use exclusive database access.
9. User-data mutation and media mutation remain ordered so a filesystem failure
   cannot silently commit a contradictory database state.
10. Each destructive service must define its rollback or failure behavior
    before extraction.

Query modules may return Pydantic response models where that is already the
stable contract. Internal operations may use small dataclasses/value objects
when a response model would incorrectly couple them to HTTP output.

## 9. Router Boundary

After its domain is migrated, a router endpoint should normally contain only:

1. FastAPI parameter/model declaration.
2. A call to one explicit service function.
3. Translation of a known domain error to the existing HTTP error.
4. Return of the existing response type.

Example target shape:

```python
@router.post("/api/favorites/{file_id}")
def toggle_favorite(file_id: int):
    try:
        return user_library.toggle_favorite(file_id)
    except ImageNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
```

The exact names are illustrative. The existing response and error behavior is
the contract.

Routers must not:

- wildcard-import;
- build filesystem paths;
- spawn subprocesses;
- own background task state;
- parse Danbooru payloads;
- construct cross-domain SQL used elsewhere; or
- import another router.

## 10. Compatibility Facade Strategy

`core.py` is reduced in three states.

### State A: current broad facade

- Owns behavior.
- Wildcard-imported by every router.
- Dynamically exports nearly every global.

### State B: explicit compatibility facade

- New behavior lives in focused modules.
- `core.py` imports and explicitly re-exports only names still required by
  unmigrated callers.
- `__all__` is a hand-written list.
- Every re-export has a current caller recorded in the extraction change.
- No router uses `from core import *`.

Illustrative form:

```python
from services.search import build_where, parse_search_terms
from services.image_relations import build_image_relations

__all__ = [
    "build_where",
    "parse_search_terms",
    "build_image_relations",
]
```

### State C: retired facade

`core.py` can be removed only when:

- `rg` finds no source/test/script import;
- background automation has no dynamic import;
- source launcher and frozen launcher pass;
- the PyInstaller spec includes the new composition modules;
- all 95 routes remain in the OpenAPI snapshot;
- API golden responses remain stable; and
- no compatibility-only helper is still referenced.

Removing `core.py` is its own final change. It is not bundled with the final
domain extraction.

## 11. Frontend Modular Target

Large Svelte files are not split by line count alone. The target separates
behavior only where the boundary is observable and testable.

Proposed gradual structure:

```text
frontend/src/
  lib/
    api/
      request.ts
      images.ts
      discovery.ts
      tags.ts
      artists.ts
      folders.ts
      userLibrary.ts
      collections.ts
      tools.ts
      index.ts                  compatibility `api` export
    state/
      navigation.ts
      preferences.ts
      refresh.ts
      selection.ts
      index.ts                  compatibility store exports

  features/
    home/
      discoveryState.ts
      spotlightClock.ts
      allocation.ts
    browse/
      queryState.ts
      selectionState.ts
      bulkActions.ts
    imageDetail/
      zoomState.ts
      mutationState.ts
    tags/
      browseState.ts
      coverCache.ts
    artists/
      notificationPoller.ts
      profileArchiveState.ts
    settings/
      sectionLoader.ts
      searchIndex.ts
    timelapse/
      playbackClock.ts
    challenge/
      progressStore.ts

  components/
    existing component paths retained until a separately justified move
```

### Frontend extraction rules

1. Preserve current component paths during the first logic extraction so a
   behavior change is not hidden inside file relocation.
2. Extract pure calculation first: allocation, query parameter construction,
   normalization, cache keys, and deterministic clocks.
3. Extract timer/controller logic only after fake-clock or browser
   characterization exists.
4. Keep animation CSS/keyframes with their visual owner unless multiple
   components demonstrably share the same product animation.
5. Keep local component state local.
6. Keep only true cross-view state in shared stores.
7. Split `api.ts` by domain behind a compatibility `api` export so components
   can migrate incrementally.
8. Split `stores.ts` behind compatibility exports and preserve every
   `danbooru:*` storage key and normalizer.
9. Do not combine Svelte component splitting with sidebar restoration.
10. Every mutation extraction verifies local-array/map/set update before refresh
    token dispatch.

### Motion ownership

The Keivotos drawer and Danbooru sidebar must never be placed behind one
generic drawer abstraction.

| Contract | Owner during refactor |
|---|---|
| Keivotos drawer/backdrop in/out | `AppDrawer.svelte` |
| Danbooru sidebar width/transform and grip | `SidebarDock.svelte` |
| Sidebar content scrolling | `Sidebar.svelte` |
| Home Spotlight and lanes | `HomeView.svelte` plus characterized pure clock/allocation helpers |
| ImageDetail entry/exit/zoom/heart | `ImageDetail.svelte` plus characterized zoom/mutation helpers |
| Profile focused artist panel | `ProfileView.svelte` |
| Timelapse playback | `TimelapseBrowser.svelte` plus a characterized clock helper |
| Settings presentation isolation | `AppSettingsModal.svelte`, `settingsPresentation.ts`, `app.css` |

## 11.5 Executed sequence and two deliberate deviations (2026-07-24/25)

The extraction is underway. It departs from §12's staging in two ways, both
decided with the user and both recorded here so the staging below is read as
history rather than instruction.

**Deviation 1 — extraction runs before/alongside conversion, not after.**
§12 puts Stage 2 (replace every wildcard import) entirely ahead of Stage 3
(extract services). The reason Stage 2 came first was the blocking rule in
`FEATURE_CODE_MAP.md` — do not touch `core` exports until every caller is
mapped. That requirement is satisfied by a **mechanical AST inventory** of every
wildcard-supplied name per router, so the safety property was already owned. And
because `core.__all__` is built from `globals()`, a name imported back after
extraction stays available to unconverted routers. Doing all nine conversions
first would therefore have cost eight slices before a line left `core.py`, for
no safety gain.

**Deviation 2 — Danbooru domains extract into `backend/modules/danbooru/`, not
a flat `services/` or `integrations/`.** §5's target tree predates the module
contract. Extracting Danbooru-specific behavior into the module directory makes
the same work advance `SUITE_MODULE_CONTRACT.md` §13's removability goal instead
of only reducing a line count. Genuinely shared, non-module helpers still go to
`backend/services/`.

**Working order:** domain-at-a-time — extract a domain and convert its router in
the same slice, so each slice finishes something.

**Per-slice verification actually used** (in addition to the risk-matched gates):

1. every moved name is still in `core.__all__` **and is the identical object**;
2. the moved source is **byte-identical** to what left `core.py` (checked against
   the previous commit, because the moves are performed programmatically rather
   than retyped);
3. the router inventory re-run, confirming the converted router resolves nothing
   from `core`;
4. OpenAPI snapshot unchanged; full suite green.

**Completed:** leaf services (`collections`, `profile`, `user_library`), shared
primitives (`value_helpers`, `tag_names`), the Danbooru HTTP client and post
relations, tag wiki + user tags, artist profiles + follows. Routers converted:
`stats`, `tags`, `artists`. `core.py` 3,231 → 1,988; router→core name-uses
233 → 189.

**Two latent bugs surfaced by the work**, each fixed in its own commit with a
regression test rather than folded into a refactor slice:

- `SIDECAR_SUFFIXES` was referenced in `images_media.py` and defined nowhere, so
  single image move raised `NameError` and bulk move silently reported every
  image as failed. Found by the inventory's unresolved-name check.
- `gallery_dl_command()` located the bundled executable with
  `Path(__file__).parent.parent`, which silently assumed the code sat one
  directory below the code root; moving it deeper broke it. Now resolved against
  `CODE_ROOT`. Caught by an existing test that had been characterizing the old
  `__file__` mechanism.

The second is the general lesson: a verbatim move is not automatically safe when
the moved code reasons about its own location.

## 12. Migration Stages (historical — backend stages 2-12 are done)

> Stages 2 through 12 below were executed 2026-07-24/25, in a different order and
> with different destinations than written here; section 11.5 records what
> actually happened and why. Stage 13 (frontend logic extraction) is still open.


Each numbered stage is a sequence of small permission-gated changes, not one
large change.

### Stage 0 - Approve the target and establish a current baseline

Purpose:

- agree on this architecture;
- run the existing backend tests, frontend checks/build, source startup,
  portable check, and browser smoke under separate authorization;
- record current failures without folding fixes into baseline collection.

Required evidence:

- current OpenAPI snapshot result;
- current `/api/images` golden result;
- current backend suite result;
- current frontend check/build result;
- source and packaged-resource smoke;
- current browser behavior for every smoke-pass view.

Exit gate:

- failures are classified as pre-existing or introduced;
- no extraction begins from an unknown baseline.

### Stage 1 - Characterize and restore lost sidebar behavior

Purpose:

- reproduce the current sidebar failure;
- compare current/Beta4 and Beta3.1 motion;
- add timed characterization for open, close, rapid reversal, drag, saved
  position, delayed reveal/hide, hover return, scrolling, and reduced motion;
- restore the intended hybrid while retaining one persistent panel and all
  later grip/accessibility/scroll behavior.

This restoration is a separate frontend change. It is not a component split.

Exit gate:

- sidebar contract is Working with dated browser evidence;
- Keivotos drawer remains unchanged and separately verified.

### Stage 2 - Replace wildcard router imports without moving behavior

Order:

1. `stats.py`
2. `discovery.py`
3. `collections.py`
4. `user_library.py`
5. `tags.py`
6. `artists.py`
7. `folders.py`
8. `images_media.py`
9. `tools.py`

For each router:

- inventory the exact imported names;
- replace `from core import *` with explicit imports;
- change no function owner yet;
- run that router's focused tests, OpenAPI snapshot, and import/startup smoke.

Why this precedes extraction:

- it reveals the real dependency surface;
- it makes accidental global reliance visible;
- it allows each later service move to update known callers.

Exit gate:

- no router wildcard-imports `core`;
- current behavior remains owned by `core` where not yet extracted.

### Stage 3 - Extract low-risk read-only services

Proposed slices:

1. duplicate review expressions;
2. media range/placeholder helpers;
3. profile/statistics read queries;
4. collection preview/query helpers;
5. tag suggestions/related/random query helpers.

Regression gates:

- OpenAPI;
- `/api/images` golden where image results are affected;
- existing focused tests;
- read-only API smoke;
- no schema or filesystem change.

### Stage 4 - Extract application search and image query construction

Move:

- search normalization/parser;
- user-DB requirement detection;
- numeric/date/filename/dimension/shape predicates;
- `build_where`;
- durable image identity and summary construction.

Do not merge the CLI parser in this stage.

Regression gates:

- filename/rating tests;
- images golden snapshot;
- OpenAPI snapshot;
- mixed-search browser smoke from `FEATURES.md`;
- representative query benchmark/plans;
- exact post-ID blacklist exception.

### Stage 5 - Extract user-library and collection mutations

Move:

- favorites and pins;
- favorite tags and combos;
- blacklist;
- user image tags;
- collection CRUD, membership, and pinning;
- image activity/view/Heart Spam state.

Regression gates:

- collection validation and missing-collection behavior;
- durable identity across modern/legacy favorite rows;
- immediate frontend updates for each mutation;
- cross-view refresh token behavior;
- user DB checkpoint/backup safety remains unchanged.

### Stage 6 - Extract relations, wiki, and artist domains

Move in separate slices:

1. image relation parsing/query/refresh;
2. wiki parsing/cache;
3. Danbooru integration boundary;
4. artist follow state and polling;
5. artist profile discovery/archive.

Regression gates:

- relation-chain test;
- tag wiki cache behavior;
- notification one-time baseline;
- no remote image hotlink/download during notification checks;
- explicit-only profile archive download;
- credentials never returned;
- deterministic network fakes before live-network smoke.

### Stage 7 - Centralize path policy before moving filesystem mutations

Move:

- managed-root validation;
- folder selector/target resolution;
- generated directory exclusion;
- validated media identity;
- mutation-plan construction;
- resource/helper lookup.

Retain:

- configured location ownership in `config.py`;
- root/sidecar identity in `storage_layout.py`;
- minimal launcher bootstrap in `app.py`.

Regression gates:

- release-layout tests;
- storage-layout tests;
- folder root and relocation tests;
- folder removal preview/modes;
- external-root open-location test;
- unavailable-root safety;
- source/frozen helper lookup;
- resolved source and destination containment.

Exit gate:

- routers no longer make path-policy decisions;
- pipeline differences are explicit rather than accidentally duplicated.

### Stage 8 - Extract image and folder filesystem mutations

Move separately:

1. single image move;
2. batch image move;
3. single image delete;
4. batch image delete;
5. folder registration/rescan;
6. folder relocation;
7. folder removal.

Required fixture behavior:

- use disposable media, sidecars, history, thumbnails, and databases;
- verify exact counts and rollback/failure state;
- verify registered external roots;
- verify no operation escapes managed roots;
- verify unindex-only never deletes originals or sidecars;
- verify sidecar-delete mode deletes only current central sidecars;
- verify history remains preserved.

### Stage 9 - Extract tool definitions, commands, runner, and progress

Move in this order:

1. stable tool definitions;
2. command construction;
3. task snapshot/state;
4. exclusive operation gate;
5. subprocess runner and progress parser;
6. cancellation;
7. post-success recovery/cache/tag-history hooks.

Regression gates:

- original five tools remain;
- task-state isolation;
- incremental result indexing;
- structured file progress;
- bounded recent history;
- cancel behavior;
- serialized backup/restore/tool window;
- source and frozen command resolution;
- successful sync still checkpoints `user.sqlite`.

The pipeline script itself is unchanged in this stage.

### Stage 10 - Extract lifecycle and app factory

Move:

- startup maintenance;
- lifespan;
- middleware;
- FastAPI construction.

Change:

- `server.py` imports `app` from `app_factory.py`;
- `core.py` temporarily re-exports `app` if a caller remains.

Regression gates:

- security tests;
- local recovery;
- automation startup/cancel;
- sidecar migration key behavior;
- frontend root delivery;
- source launch;
- portable check;
- PyInstaller composition-root collection.

### Stage 11 - Convert `core.py` into an explicit compatibility facade

Actions:

- delete dynamic `__all__`;
- import only still-required names from their owners;
- write an explicit `__all__`;
- document each remaining caller;
- prohibit new facade imports.

Exit gate:

- `core.py` contains no product behavior;
- line count reflects explicit compatibility only;
- every export has a current caller.

### Stage 12 - Retire compatibility exports and optionally remove `core.py`

For each remaining export:

- migrate the last caller;
- run its focused regression set;
- remove that one export in the same small change.

Final removal gate:

- zero imports or dynamic references;
- all current entry paths pass;
- all route and response contracts pass;
- no package spec references it;
- no test patches it;
- no archived comparison work still depends on its location.

### Stage 13 - Frontend logic extraction

After lost behavior is restored and browser characterization exists, split one
feature at a time:

1. typed API request layer and domain clients;
2. navigation/preferences/refresh/selection stores;
3. Home pure allocation and clock;
4. Browse query and bulk-action controllers;
5. ImageDetail zoom and mutation controllers;
6. Tags cache/browse helpers;
7. artist notification poller;
8. Settings section loader/search index;
9. Timelapse clock;
10. Challenge progress store.

Large visual components may remain large when splitting would obscure rather
than protect their behavior.

## 13. Risk Tiers

| Tier | Examples | Minimum verification |
|---|---|---|
| 1 - structural/read-only | Explicit imports, pure formatting, read-only query helper move | Compile/import, focused tests, OpenAPI where applicable |
| 2 - query/API | Search, image queries, tags, stats, collection reads | Tier 1 plus golden responses, query plans, API smoke |
| 3 - user state | Favorites, collections, user tags, follows, views | Tier 2 plus fixture DB mutation, immediate UI update, backup/checkpoint boundary |
| 4 - timed UI/background | Sidebar, Home clocks, notifications, Timelapse, automation | Fake-clock or timed browser/background characterization, cleanup/restart |
| 5 - filesystem/destructive | Move, delete, folder removal, restore, sidecar cleanup | Disposable full fixture, containment, counts, rollback/failure, preserved originals/history |
| 6 - startup/package | Lifespan, app factory, resources, helpers, PyInstaller | Source launch, server smoke, portable check, package/build verification |

Higher-tier work cannot use a lower-tier verification set merely because the
code movement appears mechanical.

## 14. Regression Gate Matrix

| Surface changed | Mandatory checks before completion |
|---|---|
| Any backend import/extraction | Python compile; focused tests; backend import/startup |
| Router/API | OpenAPI snapshot; route count; response/error characterization |
| Image search/query | Filename/rating tests; images golden; mixed search; random and timelapse where shared |
| User DB mutation | Fixture mutation; durable identity; immediate UI; checkpoint/backup boundary |
| Path/storage | Release-layout, storage-layout, roots, removal, external-root, unavailable-root checks |
| Filesystem mutation | Disposable originals/sidecars/history/thumbnails/DB fixture and exact rollback state |
| Tools/import | Tool progress, beta import, automation, cancellation, checkpoint hook |
| Credentials/network | Encryption/non-return; transient config; deterministic HTTP fixture; rate/credential behavior |
| Lifecycle/security | Security, local recovery, automation, migration, frontend delivery, source launch |
| Frontend state | `npm run check`, build, affected browser interaction, persistence reload |
| Animation/timer | Real elapsed or fake-clock behavior, reversal, cleanup, reduced motion, state restoration |
| Packaging/resource | Portable check, spec collection, helper discovery, built frontend delivery |

The full `FEATURES.md` smoke pass remains mandatory after any nontrivial
application change:

- Home;
- Browse with the documented mixed search;
- ImageDetail;
- Favorites;
- a Collection;
- a tag page with wiki and banner;
- Popularity;
- Timelapse;
- Daily Challenge;
- Profile focused artist panel; and
- Settings.

## 15. Per-Change Procedure

Before each extraction:

1. Select one feature/domain slice.
2. Read its IDs in `FEATURE_CODE_MAP.md`.
3. List exact files and exact actions for permission.
4. Record current callers, imports, routes, tables, paths, jobs, tests, and
   archived lineage.
5. Add missing characterization before moving high-risk behavior.

During each extraction:

1. Move behavior without changing the public contract.
2. Keep compatibility exports for unmigrated callers.
3. Use explicit imports.
4. Keep transactions and path validation in their authoritative owner.
5. Avoid unrelated formatting or cleanup.

After each extraction:

1. Run the risk-matched regression gate.
2. Compare OpenAPI/golden outputs where applicable.
3. Exercise real timed behavior where applicable.
4. Update `FEATURE_CODE_MAP.md` owners and line anchors.
5. Update `FEATURES.md` only if the feature contract changed.
6. Update `CHANGELOG.md` with the restoration/refactor result.
7. Report whether the server was restarted and which real-data/network
   operations were intentionally not run.

## 16. Rollback and Bisectability

Each change should be independently reversible.

A valid extraction slice:

- has one responsibility;
- does not mix restoration and reorganization;
- does not mix schema changes with code moves;
- does not rename API routes;
- leaves a compatibility path when another caller remains;
- includes its own tests/characterization;
- can be reverted without reverting later unrelated features.

If a regression appears:

1. Stop further extraction in that domain.
2. Reproduce against the last verified slice.
3. Use the feature map to enumerate affected contracts.
4. Revert or repair the smallest slice.
5. Do not compensate by adding a second compatibility layer elsewhere.

Git actions remain user-owned. This plan describes logical change boundaries;
it does not authorize commits, branches, tags, pushes, or releases.

## 17. Architecture Definition of Done

The modular architecture is complete only when all of the following are true:

- no router wildcard-imports `core`;
- no new module imports `core`;
- routers contain transport translation rather than reusable product logic;
- services have explicit dependencies and no router imports;
- configured paths, resource paths, root/sidecar identity, and mutation policy
  have the named authoritative owners;
- filesystem mutations use validated plans and pass destructive fixture tests;
- tool process state/progress is outside `core`;
- lifecycle/FastAPI construction is outside `core`;
- `core.py` is an explicit facade or is removed after the final zero-caller
  gate;
- every OpenAPI route and snapshot remains accounted for;
- user DB, sidecars, sidecar history, originals, credentials, backups, and
  registered-root identity remain protected;
- browser persistence changes are copy-forward migrations that preserve legacy keys;
- immediate UI mutation behavior remains intact;
- broken sidebar behavior is restored and timed-characterized;
- large frontend components are split only where the new boundary reduces
  coupling and has regression coverage;
- source and packaged launch paths pass;
- `FEATURE_CODE_MAP.md`, `FEATURES.md`, `ARCHITECTURE.md`, and `CHANGELOG.md`
  match the resulting implementation.

## 18. Deliberately Deferred Work

The following are not prerequisites for safe modularization:

- converting all backend imports into a new Python package style;
- replacing FastAPI;
- replacing SQLite;
- replacing Svelte;
- introducing accounts, authentication, cloud sync, or remote users;
- merging application and CLI search without a contract decision;
- rewriting the acquisition pipeline in-process;
- splitting every API model into a domain package;
- renaming historical versions or archive folders;
- implementing V1.10 or post-V1.0 ideas;
- completing the separate manga-hoarder prototype; or
- reducing code solely to reach an arbitrary line-count target.

These may be proposed later as independent product or architecture changes.

## 19. First Implementation Boundary After Approval

The first application-code work should not be a broad `core.py` move.

The safe sequence is:

1. establish the current test/build/runtime baseline;
2. characterize and restore the Danbooru sidebar without splitting it;
3. replace router wildcard imports one router at a time;
4. begin low-risk read-only `core.py` extraction;
5. proceed through the staged plan only while each previous regression gate
   remains green.

### V1.1.0 suite/module identity boundary

The V1.1.0 Files/module work is an additive boundary, not permission for a
big-bang `core.py` rewrite:

1. **Descriptor and registry — implemented.** `ModuleDescriptor` replaces the
   former global module slug concept and a static registry contains exactly one
   required base (Files) plus optional modules (currently Danbooru and Reddit).
2. **Suite versus module identity — implemented.** Keivotos owns the product
   title, suite-root user DB/backups/logs, and browser prefix; descriptors own
   module homes, index DBs, credentials, declared API/log prefixes, and user
   agents. Legacy data is copied/verified/preserved.
3. **Registry-driven shell — implemented at the frontend shell boundary.**
   `App.svelte` and `AppDrawer.svelte` iterate descriptor/API state and module
   UI registrations; Danbooru and Reddit internal views remain in their module
   surfaces.
4. **Route prefixing — new modules implemented, Danbooru deferred.**
   `/api/files/*` and `/api/reddit/*` use namespaced routes. Existing Danbooru
   routes stay grandfathered and frozen by the OpenAPI snapshot.

Danbooru's legacy backend implementation is not yet physically contained in
`backend/modules/danbooru/`. Directory-only removal becomes a valid claim only
after the ordinary incremental extraction plan has moved every router, service,
background job, package helper, and compatibility export behind that boundary.

This order restores known lost behavior before structural work can hide it and
turns the current unknown dependency surface into explicit, reviewable
boundaries.
