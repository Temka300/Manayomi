# Keivotos Feature Register

**This file is required reading before implementing any feature change, and it is
the contract for what must not break.** Every feature listed here exists in the
current source or is an intended compatibility contract and must not be silently
lost. Presence in this register is not proof that the feature currently works
at runtime. If your change adds, modifies, restores, or intentionally removes a
feature, update this file in the same change — a feature that is not listed here
is a feature that will eventually be lost.

Rules:

1. Read this file before editing code for a feature request.
2. Before finishing, walk the [Regression Checklist](#regression-checklist) for
   every surface your change touched.
3. If behavior listed here changed intentionally, edit the entry here and record
   the decision in `CHANGELOG.md`. Never delete an entry silently.
4. If you find a feature in code that is missing here, add it.

## Release and verification state

- Release identity is not repeated here: the current cycle is named in
  [ROADMAP.md](./ROADMAP.md#current-cycle), and the shipped semantic version is
  `backend/product.py`, written only by `scripts/release/set_version.py`.
- V1.10 and post-V1.0 ideas are future-only. Historical version folders and
  changelog headings are preserved as historical evidence.
- Unless an entry is explicitly marked otherwise, its status is:
  **implemented in source; current runtime behavior unverified**.

Status terms used here:

- **working** — exercised successfully in the current runtime;
- **broken** — current failure is directly reported or reproduced;
- **partial** — some required implementation or dependency is missing;
- **unverified** — source exists, but the current runtime behavior has not been
  exercised;
- **future** — not part of the current release contract.

Current exceptions:

| Surface | Status | Evidence boundary |
| --- | --- | --- |
| Danbooru sidebar animation | **working** | manually confirmed 2026-07-25: slide-in, grip drag/persist, click toggle, saved position across reload. (Not automatable — the browser pane does not composite, so rAF/CSS transitions cannot be driven in-harness.) |
| Manayomi manga module | **working** | 2026-08-24 real-data 360×800 and 390×844 Browse pass: bottom section navigation, provider/filter + search-only control stack, first cover at y=156 (formerly y=244), shared persisted Hide downloaded, live grouped MangaDex filters, chapter-first phone detail with first chapter at y=256, and desktop side-by-side Info/Chapters; no horizontal overflow; clean browser/server logs |
| Current test/check/build baseline | **working** | 445/445 tests, compileall, frontend check (0 errors/warnings), OpenAPI snapshot, and production frontend build passed 2026-08-24 |
| Current source and portable startup | **partial** | isolated source server and profile persistence passed 2026-07-18; portable package was not built |

---

## Philosophy

- **Local-first, single user.** No accounts, login, logout, cloud sync, or
  remote-user assumptions. Profile is a local-library page.
- **Immediate UI updates.** User-triggered mutations mutate the initiating
  component's local arrays/maps/sets first; refresh tokens
  (`imageRefreshToken`, `collectionRefreshToken`, `tagRefreshToken`,
  `artistFollowRefreshToken` in `frontend/src/lib/stores.ts`) only reconcile
  *other* views in the background. The initiating view never waits for a
  reload, route change, or second click.
- **No hotlinking / no surprise downloads.** Remote Danbooru posts render as
  placeholders or `#id` chips. The app does not expose general Danbooru media
  downloading; profile-media archiving remains explicitly user-triggered.
  Notification polling records post IDs only.
- **Compact, practical UI.** Top bar stays compact; icon-only controls with
  tooltips/aria-labels; no duplicated controls in multiple places; no settings
  copied from reference apps that don't exist in this project.
- **Data safety.** Never delete media, metadata, sidecars, databases, or
  gallery-dl files without an explicit user request; destructive bulk actions
  warn with counts first; sidecar refreshes archive the old sidecars.

## Architecture

```
app.py                    source/frozen entry point → uvicorn → backend/server.py
backend/
  server.py               app/router/static composition
  app_factory.py          the FastAPI application object and HTTP middleware
  lifecycle.py            startup maintenance and the application lifespan
  modules/danbooru/       the Danbooru module's own backend behavior
  modules/reddit/         the Reddit archive, queries, and module descriptor
  modules/karaoke/        local karaoke catalog, lyrics, storage, and Kara.moe acquisition
  modules/youtube/        yt-dlp metadata, formats, local acquisition, and catalog
  modules/language/       Languages catalog, authored library, Anki mirror, jobs, storage
  modules/manayomi/       Manayomi descriptor and Files publication hook
  manga/                  manga index, scanner, reader, queries, settings, roots, downloads
  services/               cohesive shared services, guarded yt-dlp, generic DPAPI secret store
  routers/                API endpoint bodies split by product domain
  backup_bundle.py        manual verified .keivotosbk creation and restore
  local_recovery.py       verified rotating user.sqlite checkpoints
  schema.py               authoritative data-DB schema and indexes
  storage_layout.py       stable library-root identities and sidecar paths
  database.py             Danbooru DB + shared user DB access and additive migrations
  files_base/             isolated Files index, source registry, hashing, filesystem browser
  module_descriptor.py    typed suite/module identity and lifecycle integration boundary
  module_registry.py      static Files + six optional-module descriptors
  models.py               Pydantic response models (the API contract)
  config.py               local application-data layout plus runtime settings
  thumbnails.py           three-tier thumbnail generation/caching/cleanup
scripts/
  danbooru_gallery_dl.py  incremental sync plus the four-phase import pipeline
  benchmark_library.py    read-only representative large-library benchmark
  init_metadata_db.py     metadata DB bootstrap
  release/                deterministic brand, notices, and Windows build helpers
frontend/                 Vite + Svelte 5 + TS + Tailwind; state in lib/stores.ts, API client in lib/api.ts
assets/branding/          suite and module brand masters plus generated derivatives
packaging/windows/        PyInstaller one-folder spec and separately invoked CLI entry
```

### Current application and distribution shell (since V1.1.0)

- **Keivotos is the suite; Danbooru is the module.** The browser document,
  manifest, FastAPI application, console, executable, and suite-drawer header
  use the Keivotos identity. Danbooru keeps its original module SVG in its
  top bar and on its entry inside the Keivotos drawer. The angular avatar mark at
  `assets/branding/keivotos/source/keivotos-angular-logo.svg` is the canonical
  suite logo; the transparent raster master, icon sizes, favicon, Windows
  icon, banner, wordmark, and social preview are all derivatives of that mark.
  Source launcher windows use that Windows icon and the normal-hyphen
  `Keivotos - Danbooru` title while retaining visible console output.
  The Keivotos mark stays on suite-owned surfaces only. Danbooru's top-right
  user control, drawer Profile entry, and local-profile/default-avatar fallback
  use the original module profile mark at
  `assets/branding/danbooru/profile-avatar.svg`. The supplied
  checkerboard-background PNG is a
  visual reference only and is never shipped as an icon.
- **The shell consumes a static descriptor registry.** Files is the required,
  non-disableable base descriptor; Danbooru, Reddit, Karaoke, YouTube,
  Languages, and Manayomi are optional descriptors. Each
  descriptor owns its slug, name, home, database, credentials, declared API
  prefix, log prefix, user agent, lifecycle flags, and publication hook. The
  frontend shell resolves enabled descriptors and surface components without
  module-specific branches in `App.svelte` or `AppDrawer.svelte`. Danbooru's
  existing unprefixed routes remain grandfathered. Reddit, Karaoke, and YouTube
  own the always-mounted `/api/reddit`, `/api/karaoke`, and `/api/youtube`
  prefixes declared by their descriptors.
- **Source and portable launches share `app.py`.** Source launch can auto-build
  through `run.bat` on Windows or `bash run.sh` on WSL2/Linux. Both synchronize
  locked Python 3.11 dependencies, build the frontend only when missing, and
  forward application flags. The Bash launcher uses `.venv/bin/python`.
  Frozen launch imports the packaged ASGI composition root,
  runs uvicorn in-process, and dispatches the import pipeline and Windows folder
  picker back through packaged helper modes. A portable resource check imports
  that backend, verifies its root route, and reports the exact bundled frontend
  and writable locations without starting the server. Frozen checks also require
  the separately invoked `gallery-dl.exe` and `ffmpeg.exe` beside `Keivotos.exe`.
  Maintainer-only `run-lan.local.bat` (Windows) and `bash run-lan-local.sh --lan`
  (WSL2/Linux) set a local developer marker; the shell wrapper enables LAN by
  default and forwards additional flags. The application discovers
  one active private IPv4 address, binds only that adapter, keeps the PC browser
  on loopback, and displays the address for trusted devices. Normal source and
  frozen launchers do not expose the LAN flag.
- **Application files are replaceable; writable state is external.** Suite
  state lives under `%LOCALAPPDATA%/Keivotos/`: `user.sqlite`, `backups/`,
  `logs/`, runtime config, and the Files base index at `base/files.sqlite`.
  Danbooru owns `modules/danbooru/`: optional library root, its disposable
  database, credentials, sidecars, thumbnails, recovery, and gallery-dl work
  files. Reddit owns `modules/reddit/`: its rebuildable archive index, exact
  structured-source evidence, local media objects, and capture manifests.
  Karaoke owns `modules/karaoke/`: its rebuildable song/lyrics/job index,
  create-only local media library, staging, metadata, and receipts. YouTube owns
  `modules/youtube/`: its rebuildable download/job index, create-only local
  video library, resumable staging, and explicit-search thumbnail cache.
  Languages owns `modules/language/`: a rebuildable word/progress catalog,
  versioned create-only media library, and staging. Its authored words,
  overrides, notes, media associations, favorites, lists, field profiles,
  settings, and practice history stay in additive `language_*` tables in the
  suite `user.sqlite`. Its enabled-state-gated API and complete module-owned
  Svelte surface are implemented.
  Manayomi preserves its existing storage beneath `modules/manga`: the
  disposable `manga.sqlite` index, precious module `user.sqlite`, covers, and
  download work. Registered external manga roots are published into Files and
  remain the authoritative location of original CBZ media.
  There is no extra `metadata/` wrapper. Before a
  normal startup loads configuration, an existing `Documents/Keivotos` tree is
  copied through resumable staging, verified file-by-file, installed atomically,
  and preserved at its original location. A configured prior module tree is
  likewise copied and verified into `modules/danbooru`, its config paths are
  rebased only after success, and its source is preserved. Startup also safely
  flattens the former default metadata wrapper and refuses conflicting files. Backups use
  `%LOCALAPPDATA%/Keivotos/backups/`; runtime overrides live in
  `%LOCALAPPDATA%/Keivotos/config.json`. The checked-in root
  `config.json` is a read-only default template. `KEIVOTOS_HOME` redirects the
  complete default layout for CI and isolated testing. Linux defaults use
  `$XDG_DATA_HOME/Keivotos` or `~/.local/share/Keivotos`. An empty `portable.txt`
  selects adjacent `data/`, reusing existing `Data/` when lowercase `data/` is
  absent. Distinct existing `data/` and `Data/` require an explicit home; neither
  is merged or renamed. Windows drive paths in saved libraries are not
  automatically rewritten. Native Windows folder picking and encrypted
  credentials remain platform-specific; use the existing folder fallback and
  credential environment variables on Linux.
- **The local HTTP surface is default-loopback with explicit source LAN
  opt-in.** This manga-focused checkout defaults to `http://localhost:53325`, refuses arbitrary
  non-loopback `--host` values, and still allows an explicit loopback
  `--host`/`--port` override. Only a non-frozen source run with the local
  `KEIVOTOS_DEVELOPER_LAN=1` marker admits `--lan`; it binds the one detected
  private IPv4 adapter while portable and ordinary source launch stay
  loopback-only. Middleware rejects every other `Host`, cross-site Fetch
  Metadata, and browser `Origin` values that do not exactly match the active
  Keivotos scheme, host, and port; wildcard CORS is not enabled. LAN mode is
  unauthenticated and therefore only for trusted private networks.
  For Windows hotspot forwarding into WSL, `bash run-hotspot-local.sh` explicitly
  allows the private IPv4 Host set by `KEIVOTOS_HOTSPOT_HOST` (default
  `192.168.137.1` in that separate launcher), only while LAN mode is active.
  Same-origin checks remain enforced. Windows hotspot-only port forwarding and
  firewall rules must already be configured; this launcher does not change them.
  After WSL restarts, update the forwarding destination if its address changes.
  Phone connectivity and school-network isolation require device-side verification.
- **Runtime logs are persistent, dated, separated, and bounded.** Every launch
  creates `keivotos-runtime-YYYY-MM-DD_HH-MM-SS-pPID.log` for startup,
  background work, mutations, failed reads, warnings, and errors, plus a
  matching `keivotos-access-...log` for every local HTTP method, path, and
  status. Successful GET/HEAD/OPTIONS traffic stays out of the runtime file so
  useful events are not buried. Each file rolls over at 5 MB with five chunks,
  and the 30 most recent files per type are retained. Settings displays both
  exact dated paths and explains their contents. Malformed runtime JSON is
  reported without an import traceback and is written to the dated runtime log
  before normal logging starts; invalid numeric preferences fall back to
  bounded defaults instead of breaking their APIs. Port conflicts are logged
  with the conflicting host/port and an alternate-port action.
- **Portable builds are one-folder and reproducible.** Python and frontend
  dependencies are locked, local backend/frontend checks verify the source, and
  the release script bundles Uvicorn's dynamic runtime modules, starts the staged
  executable against an isolated `KEIVOTOS_HOME`, requires a successful HTTP
  response, then builds a ZIP plus SHA-256 without publishing a release.
  GitHub Actions automation is deferred to a future release.
  `gallery-dl.exe` and `ffmpeg.exe` remain separately invoked tools
  with collected license and source-availability material.
- **Release-label alignment is centralized.**
  `scripts/release/set_version.py` updates runtime, Python package/lock,
  frontend package/lock, Windows-resource, and OpenAPI facts together. The release-layout test derives
  from `backend/product.py`; the Windows build derives its artifact name from
  the same version and rejects explicit mismatches. Frontend suite/module
  display labels derive from `frontend/src/lib/product.ts`; the release-layout
  guard rejects duplicated product labels in their display components while
  retaining historical storage, protocol, and asset identifiers.

- **One precious database plus disposable indexes.** The Files base's `files.sqlite`
  (disposable, type-agnostic index of cheap disk facts and lazy hashes) and
  Danbooru's *data* DB `danbooru.sqlite` (rebuilt from sidecars — disposable,
  holds posts/files/tags plus `sync_manifest` mtime/size change detection and
  `ingest_state` resumable import phases), Reddit's `reddit.sqlite`, Karaoke's
  `karaoke.sqlite`, and YouTube's `youtube.sqlite` are regenerable indexes. The
  one *user* DB
  `user.sqlite`
  (**irreplaceable — never dropped or rebuilt**) holds: `favorites`,
  `collections`, `collection_items`, `favorite_tags`, `favorite_tag_combos`,
  `blacklist_tags`, `user_image_tags`, `image_views` (view + heart-spam
  counts), `tag_wiki_cache`, `artist_follows`, `artist_follow_posts`,
  `artist_profile_assets`, `registered_folders`, Karaoke favorites/playlists/
  playback state, `tag_removals` (the latest
  upstream tag removals recorded by a manual metadata refresh). Queries that need both attach
  `userdb` and match on file identity (`user_file_match`).
- **Schema changes are additive.** `schema.py` is authoritative for the data
  DB and its indexes; `database.py` owns additive user-DB migrations with
  `_ensure_column` / `CREATE TABLE IF NOT EXISTS`. New columns arrive with a
  migration or backfill, never by recreating user tables.
- **Media root comes from `config.json`** — never assume the repo root contains
  images. External originals stay exactly where registered. Generated metadata
  defaults to `%LOCALAPPDATA%/Keivotos/modules/danbooru`; sidecars use
  `sidecars/roots/<stable-root-id>/<relative-path>`. The former repo `data/`
  tree is a preserved migration source and remains git-ignored.
- **Frontend has no router.** `viewMode` store drives which view renders in
  `App.svelte`; `ImageDetail` is an overlay on top of any view, driven by
  `selectedImageId` / `selectedArtistProfileAsset`.

---

## Feature Inventory

### Views (`viewMode` in stores.ts — every value must stay reachable)

| View | What must keep working |
|---|---|
| `home` | Local library dashboard, rating-aware and without a sidebar. The default **Discovery** layout has a cinematic full-bleed daily spotlight using Danbooru's own title, explanation, and compact Explore / Challenge / Random / Tags actions. Its balanced daily pool draws from Characters, Copyright, Artists, and General Tags instead of one category dominating. Five tag thumbnails stay aligned at the lower right; the center thumbnail is larger and owns the hero image. A nine-second white progress line advances the window: the focused thumbnail shrinks and moves left while the next thumbnail moves into the center and grows. Clicking any thumbnail focuses it and restarts the timer; clicking the hero artwork opens that local image in ImageDetail. Home receives up to six presentation-only candidates per tag, preferring landscape images closest to 16:9 before score; a deterministic local-day seed rotates Spotlight, the actual image windows in **From your library**, and both covers/tag lists in **Tag neighborhoods** at midnight while keeping refreshes stable within the day. A page-wide unique-file allocator prevents artwork reuse across Spotlight and neighborhoods, and moving lanes omit those assigned files when alternatives exist. Portrait fallbacks use an upper focal point rather than a body-centered crop. Canonical tag covers remain unchanged. Three borderless moving lanes prioritize Characters, Artists, and Copyright (`/api/home/tags`, `/api/home/image-rails`) and use the same landscape-first/upper-portrait direction. Below them, the single **Tag neighborhoods** heading introduces Characters, Copyrights, Artists, and General simultaneously as four compact visual entry cards. Each image lane pauses independently while the pointer is over it or keyboard focus is inside it; moving the pointer/focus away resumes that lane while the others keep moving. Opening a lane image releases its focus pause before ImageDetail appears, so returning from ImageDetail does not leave the lane frozen. Reduced motion makes all lanes manually scrollable. The former full-size Home remains intact as the persisted **Classic** layout. |
| `gallery` (Browse) | Image grid with search, sort, folder + multi-select rating filters (any combination of General, Sensitive, Questionable, Explicit, and Unrated; no selection means all), blacklist applied, pagination (10/20/30/50/all), duplicate-review mode, mass selection. |
| `favorites` | Favorited images with pin support (`favorites_only`), same grid features. |
| `collections` / `collection-detail` | Collection list with media-aware covers (GIF/MP4/WebM previews), create/rename/edit description, pin collections, pin images inside a collection, bulk membership edit. |
| `tags` | Tags browser + in-section tag detail: selecting a tag/artist stays in Tags, preserves the list search/filter state, and provides an integrated banner breadcrumb back to Tags. Tag detail includes wiki/info above local posts, always-visible dashed remote "Not in library" example cards without an Expand/Hide wrapper, local examples as real images, artist following, and linked-tag navigation that remains in Tags. Remote post references such as Non-examples use the same dashed Not-in-library treatment. |
| `popularity` | Created-date popularity: Date/Month/Year modes, top-center period controls with prev/next navigation, images below. |
| `timelapse` | Simple mode is primary (random images moving slowly); advanced mode uses the same top-right icon position for entry/back. Includes start/stop, working native fullscreen with an in-app fallback, a compact numeric speed slider, All Images or one exact typed-tag scope, and Hide UI (only its hover target remains until restored). |
| `challenges` | Daily character-guess challenge: only the top-left image quadrant starts visible; failed guesses reveal top-right, bottom-left, then bottom-right. Compact asymmetric play surface keeps guessing, suggestions, optional choices, clue trail, and guess history visible without the old stacked-card scroll; deterministic per-day seed. |
| `profile` | Local profile page: an inline-editable display name that defaults to Keivotos and persists through the `user_settings` table in `user.sqlite`, banner/avatar artwork, library stats, favorites, collections, followed-artist watchlist (image-first tiles, name overlay, local/new badges; horizontal rail that can expand to a grid at 10+ artists; focused panel with Open Tag / Check / Mark Seen / Unfollow), bulk profile-media check. No sidebar, no login. |

Discovery's three moving Home lanes must remain visible for small libraries:
they omit spotlight/neighborhood artwork when alternatives exist and reuse the
assigned images only when filtering would otherwise empty a lane. Challenges,
Popularity, and Timelapse share the Tags-style chevron breadcrumb back to Home.

### ImageDetail overlay

- Opens from any grid and from archived profile assets (not a browser tab).
- Zoom/drag: clicking while zoomed must not exit; the outside black border must
  not fake zoom/exit behavior.
- Tag list with category colors; favorite/pin tags without visual clutter;
  user-added tag filter toggle next to Favorited (shows only user tags,
  click again to turn off).
- A distinct, non-clickable **Removed upstream** section appears only when the
  latest manual Update Danbooru Tags run removed tags from that image. This
  history is stored in `user.sqlite`, so it survives index rebuilds.
- Add/remove local user tags; favorite the image; add to collections.
- Heart Spam button (only when enabled in Settings), count shown below Seen.
- Open file location on disk for both the portable data root and registered
  external library roots; move image to another folder (sidecar payload
  moves with it); delete with confirmation.
- Clicking a tag closes ImageDetail and opens that search in Browse from Home
  and other non-Tag views. When ImageDetail was opened from Tags, the click
  stays in Tags and opens that tag's info page instead.
- Parent/sibling related posts shown when local metadata has relationships;
  relations refresh action.
- Seen/view counting via `image_views`.

### Top bar (layout is a decision — keep the order)

Keivotos app-menu burger · Home · **Search** (with suggest + sort control + per-page) ·
**Size** (icon-only) · **Filter** (icon-only; rating, duplicates
all/same-folder/different-folder) · **Random** (icon-only; context-aware:
random image / random tag in tags view / random collection image) ·
followed-artist **notifications** · **user/avatar** pinned far top-right.
Avatar dropdown: Profile, Favorites, Collections, Search Help, Settings — and
nothing account-shaped.

The burger opens a Keivotos-themed app drawer rather than toggling the library
sidebar. The drawer iterates enabled descriptors (Files is marked Base), lists
disabled optional descriptors under Add a module, and derives module-owned
footer actions such as Danbooru Profile from the frontend registry. Bottom
Settings and the existing top-right user menu remain separate. Its drawer and
backdrop use matching lightweight transform/opacity
animations in both directions for burger open and every close path. The library
sidebar is intended to appear only in Browse and Tags and use one
animated draggable grip outside its edge for both open and closed states. The
sidebar body remains height-constrained and vertically scrollable even when its
folders, blacklist, related tags, and collections exceed the viewport. The
grip stays at its saved vertical anchor and is normally hidden; hovering only
the small hotspot at that anchor reveals it, and leaving that hotspot reverses
the animation. Clicking toggles the sidebar, dragging relocates the grip and
its hover hotspot vertically, and the saved position survives restart. The grip
briefly reveals itself when Browse/Tags opens and after toggling, then returns
to its hidden-until-hover state. The panel remains one persistent DOM instance;
open/close reverses its CSS width/position animation, so repeated or rapid
toggles cannot overlap incoming and outgoing sidebar copies. **Never remove
this grip or replace it with a Settings-only sidebar toggle.**

### Files base surface

- Files is the always-enabled base and the fresh-launch surface. Its one compact
  top bar contains the Keivotos drawer button, selected role icon,
  current-folder breadcrumb, and a Danbooru-positioned Search followed
  immediately by Rescan and Duplicates. It does not repeat a static Files label
  or render a second open-folder identity/path bar.
- The left sidebar is a filtered view of the shared `files_sources` registry.
  Only rows whose additive `visible` column is true appear there; hiding a row
  does not unregister or un-index it.
- The sidebar plus opens the native Windows folder picker and immediately
  registers the selected top-level folder. The adjacent wrench opens
  **Manage folders**. Every existing row can stage a display-only rename,
  exactly one role (`files` or an enabled module), and a show/hide switch. Its
  Add folder action uses Keivotos' in-app browser, starts from the already
  registered top-level folders, cannot navigate above them, and can select only
  a descendant folder. Nothing in Manage folders mutates until Save submits
  the complete draft to `/api/suite/folders/apply`.
- Role reassignment is non-destructive. Assigning Danbooru adopts the existing
  source into that module and starts its ordinary scoped local import; assigning
  Files releases the module registration and disposable module index rows while
  retaining originals and all sidecars.
- The row ✕ is the only forget control. It first displays counted base/module
  index entries and preserved sidecars, then stages the forget operation. Save
  removes registry and disposable index entries only; originals and sidecars
  remain on disk.
- Nested registered sources have deterministic ownership. A parent scan keeps
  the child-root directory visible but does not descend into it; the child owns
  its descendants, parent-scoped search includes registered descendants, and
  forgetting a child lets the nearest remaining ancestor reclaim the derived
  index rows. The top-bar breadcrumb reflects parent/child source ancestry.
  Legacy role `base` is read as `files` without rewriting the user's database
  globally.

#### Files grid thumbnails (V1.1.2)

- Image and video tiles in the browse grid render the real thumbnail instead of
  a 🖼️/🎞️ glyph. Everything else — folders, archives, PDFs, subtitles, MIDI,
  3D models — keeps its type glyph unchanged.
- The client decides from `hasThumbnail()` in `filePreview.ts`, which mirrors
  `SUPPORTED_IMAGES | SUPPORTED_VIDEOS` in `thumbnails.py` rather than the wider
  inline-preview allowlist. A non-visual folder therefore issues **no** thumbnail
  requests at all, so the backend never consults the index for them.
- Tiles are `loading="lazy"`: a folder of thousands of images requests only what
  is scrolled into view, and never spawns thousands of ffmpeg calls at once.
- A failed thumbnail falls back to the glyph for the rest of the session, so a
  broken-image box never appears and the 404 is not retried per render.
- The thumbnail box is a fixed height, so a folder mixing images and glyphs has
  uniform tile heights instead of ragged rows.
- The `v` cache-buster is `mtime-size` from the browse row.
- **Folder tiles wear a cover** drawn from the first thumbnailable file anywhere
  in that folder's subtree — not just its direct children, because a manga
  series' immediate children are chapter folders. A file sitting directly in the
  folder still wins over one buried deeper.
- A folder with no image anywhere below it keeps the 📁 glyph. Folders always
  ask, because only the index knows whether a cover exists; the 404 is visible
  in devtools and is normal.
- **A cover never crosses a source boundary.** The lookup is scoped to one
  `source_id`, so a parent folder that contains a separately registered source
  does not borrow that child source's images — matching the V1.1.0 rule that a
  parent scan stops at a child root.
- Known limit: a folder's `v` token is its own mtime, which does not change when
  a file deep inside it is replaced. The server-side cache stays correct
  (it keys on the cover file), but a browser may hold a stale folder cover until
  the folder's own mtime changes.
- **An origin attachment outranks everything.** If the subject has an origin
  note with an attachment, that image is the tile — ahead of a folder cover and
  ahead of the file's own thumbnail. Attaching a screenshot is therefore the way
  to give a 3D model, archive or document a face, and the way to override an
  auto-thumbnail you dislike. Within a note, an attachment flagged as cover wins,
  then authoring order.
- The grid requests a thumbnail for any **annotated** entry even when its type
  has none, because that is where an attachment would be. Unannotated,
  unrenderable entries still issue no request at all.
- Annotated tiles carry an extra `-r<n>` in their `v` token, bumped whenever the
  annotation set is re-read. Attaching a screenshot changes which image the tile
  should show but touches neither the file's mtime nor its size, so without this
  the `immutable` response would keep the pre-attachment picture on screen and
  attaching would appear to do nothing. Any previously failed tile is also
  allowed to retry after an origin edit.

#### Read-only archive contents (V1.1.2)

- `GET /api/files/archive` lists what is inside a zip **without extracting it**.
  The info panel shows a Contents section for `zip`/`cbz`/`epub` with a
  **Show contents** button — it is fetched on demand, so clicking through a
  folder of archives does not fire a listing per click.
- Entries show name, size and directory marker; the header summarises entry
  count, unpacked size and stored size.
- **Only the central directory is parsed.** `zipfile.ZipFile.infolist()` reads
  stored metadata; `read`/`open`/`extract`/`extractall` are never called, which
  is what makes a zip bomb inert — there is nothing to expand. A regression test
  asserts those four methods are never invoked.
- **Entry names are display text only.** They are never joined to a path or used
  to open anything, so a member literally named `../../etc/passwd` renders as
  that string and does nothing.
- **The entry count is capped** at 2000; a longer archive reports `truncated`
  while its totals still describe the whole file.
- **Archive-ness is judged by content**, not extension: a `.txt` renamed to
  `.zip` is a clean 415 rather than a half-parse.

#### Copy origin info from another file (V1.1.2)

- `POST /api/files/info/copy` carries one subject's origin note onto another.
  The intended workflow is unzipping: extract an archive, then move the Booth
  link, description and screenshots you recorded against the `.zip` onto the
  folder that came out of it, without retyping them.
- **The Origin header gains "Copy from…"**, which lists every subject in the
  current source that has origin info (excluding the current one), with a
  filter box.
- **Additive, never destructive.** Links merge as a union keyed by url+kind and
  attachments by content hash, so repeating a copy is a no-op rather than a pile
  of duplicates. Nothing is ever removed from the target, and the source note is
  never modified.
- **A description is never silently replaced.** If the target already has text,
  the server answers **409** and the UI asks before retrying with
  `overwrite_description`. This is the one destructive edge in the feature and
  it is gated.
- **Attachment bytes are not copied.** The store is content-addressed, so the
  new attachment row points at the blob that already exists on disk.

#### Files info panel order and type scale (V1.1.2)

- **Panel order changed** from Preview → Facts → Actions → Origin to
  **Preview → Origin → Facts → Actions**. Origin is the reason the panel exists;
  underneath the facts it fell below the fold whenever a preview was tall, so a
  user had to scroll past the MD5 to reach the description and screenshots.
- Type scale raised throughout: facts, description, "No origin info yet" and the
  Open/Show buttons go from 12px to 14px; MD5 and Path from 10px to 12px; link
  kind chips from 9px to 10px.
- The absolute Path no longer uses `break-all`, which split it mid-word
  (`…blue archive o` / `riginal soundtrack…`). It now wraps on word boundaries
  and only breaks a token that cannot fit.

#### Files info panel readability (V1.1.2)

- The info panel is **resizable** by a grip on its left edge: drag, or focus it
  and use Arrow keys (Shift for a coarse step). Width persists in
  `keivotos:files-info-width`, clamped to 300–760px. The default is 416px, up
  from the original 352px, which was too narrow for a description and a
  screenshot.
- Width is dragged in a local variable and written to the store on release, so
  a drag costs one `localStorage` write rather than one per pointer move. It is
  measured from the panel's own right edge, not the viewport's, because the
  panel is no longer always flush with the screen.
- The browse row is **uncapped**; the panel docks to the right edge. A 1250px
  cluster cap was tried during V1.1.2 to pull the panel closer to the tiles, but
  on a wide display it stranded a large dead band to the right of the panel and
  cost the grid several columns. It was removed on user report. The resizable
  panel achieves the same proximity without the waste: dragging it wider moves
  its left edge toward the grid and leaves no gap.
- The grip is a focusable `role="separator"` with `aria-valuenow`/`min`/`max` —
  the WAI-ARIA window-splitter pattern.

#### Files info panel metadata sections (current cycle)

- Files with no inline preview use the compact type glyph already present in
  the header; they do not reserve a second, tall "No in-app preview" block.
  Previewable images, video, audio, PDF, and capped text keep their existing
  inline preview.
- Origin remains first because it is the panel's primary authored information.
  Its creation timestamp appears as **Annotated on**, with both the absolute
  date and a relative label.
- **Details** replaces Facts directly below Origin. It groups format,
  image/video dimensions read from the loaded preview, size, modified time,
  first-indexed **Added** time, MD5 state, and the click-to-copy absolute path.
  Modified and Added show absolute and relative time together.
- Origin, Details, and archive Contents are collapsible. Their open/closed state
  is remembered in `keivotos:files-info-sections`; opening an editor, picker, or
  archive listing reopens the section containing that action.
- `GET /api/files/info` returns an envelope containing the optional Origin
  annotation and `indexed_at` from the disposable Files index. The envelope is
  present even when no annotation exists, so Added is available for ordinary
  unannotated files. Rescans preserve the original `indexed_at`.

#### Files grid size control (V1.1.2)

- The Files header carries the same Small/Medium/Large/Huge/Gigantic/Absurd
  picker Danbooru has. The **scale is shared** — one definition in
  `imageSizeOptions`, so "Large" means the same thing on both surfaces — but the
  **chosen value is per-surface**: `keivotos:files-grid-size` for Files,
  `keivotos:image-size` for Danbooru. Changing one never moves the other.
- The two are different browsing jobs (a uniform image wall versus a mixed
  folder of models, archives and documents), so a single suite-wide value would
  be wrong for one of them. Danbooru's existing key is deliberately not renamed;
  renaming it would silently reset a saved preference.
- The chosen size drives the column width, the tile's picture box, and which
  thumbnail tier is requested. The endpoint only serves 300/600/1200 and refuses
  anything under 300, so `thumbnailTierFor()` maps a column width onto a legal
  tier rather than sending the raw column size.
- `GridSizeMenu.svelte` is the single implementation, used by both the Files
  header and Danbooru's TopBar. Its `open` state is **bindable**: TopBar runs
  three mutually-exclusive menus (size, filter, page size) and must be able to
  close this one. Because the component toggles itself and reports through
  `bind:open`, TopBar re-asserts the one-at-a-time rule with a reactive guard
  rather than inside a toggle function — deleting `toggleSizeMenu()` without
  that guard leaves Size and Filter open simultaneously.

#### Files base thumbnails (V1.1.2)

- `GET /api/files/thumbnail` returns a cached WebP for one browsed file at
  `size` 300/600/1200. It reuses the DATA-039 containment chain exactly:
  absolute and `..` paths are refused before disk is touched, containment is
  re-checked after symlinks and junctions resolve, Keivotos's own tree is
  denied, and a directory is a 404.
- **A type it cannot render is a 404, deliberately, not a placeholder image.**
  The placeholder is module-owned presentation; the base falls back to its own
  type glyph in the grid. PDF, epub and archives therefore have no thumbnail
  yet — that is V1.1.3, not a defect.
- The cache key prefers the file's indexed content hash, which dedupes the same
  bytes across folders and across Files/Danbooru. Unhashed files fall back to an
  identity/mtime/size key so that browsing never reads a multi-gigabyte file
  just to draw a tile; the key still changes when the file changes, and
  converges on the content hash after a hash pass.
- The response is `immutable`, so the client varies a `v` query token (from
  mtime/size) to defeat its own cache when a file is replaced in place. The
  server ignores `v`.

#### Files info panel (V1.1.1)

- Clicking a file selects it and opens a right-side info panel; navigating into
  a folder makes that folder the panel's subject. A header toggle hides/shows the
  panel and the choice persists in `keivotos:files-info-open`.
- **Preview** renders inline only for an allowlist that mirrors the backend
  serving allowlist: images (not SVG), `mp4`/`webm`, audio, PDF (native browser
  viewer), and capped text/subtitles. MIDI, archives, 3D models, office formats,
  and unknown types use the compact header glyph and Open without a separate
  empty preview block. There is no in-app 3D viewer;
  user-added screenshots are the intended way to preview a model.
- **Details** show format, image/video dimensions when the preview reports them,
  size, modified and first-indexed dates with relative labels, full absolute
  path (click to copy), and MD5 once the file has been hashed.
- **Origin** is user-authored and stored in `user.sqlite`: a description, any
  number of labeled/kinded links (`source`/`discussion`/`mirror`/`author`/
  `other`), and image/video attachments. The base authors none of this — the
  user does. Attachment **bytes** are stored content-addressed inside the first
  registered Files folder at `<root>/.keivotos/attachments/`, so a screenshot of
  a since-deleted store page rides with the archive it documents; that directory
  is excluded from the Files scan and never appears as a browsable file.
  Identical uploads are de-duplicated; the bytes are removed only when the last
  reference to them is deleted. The note's creation time is shown as
  **Annotated on**.
- A file's origin info is keyed by content hash, so it follows a rename or move
  and is shared by byte-identical copies; a folder's is keyed by path. The file
  is hashed once, on the save that first enriches it. **Known limitation:** a
  moved file's note is dormant until the file is re-hashed (Duplicates run or a
  re-save); it is never lost. A folder rename needs a manual re-attach.
- **Open** and **Show in folder** run through the same containment guard as
  serving. File serving canonicalizes the path, requires it to resolve inside a
  registered source, rejects traversal/symlink escape, denies the suite data
  tree, and forces active types (`.html`/`.svg`/`.js`) to download with
  `nosniff`. Backed by `/api/files/file` and `/api/files/info|open|reveal`.

**Current status:** the V1.1.1 interaction set was browser-verified 2026-07-24:
PDF renders inline, subtitles show text, file details populate, and a traversal
request is refused (400). The origin editor (description
and labeled links), tile note-badges, and image/video attachments (upload,
thumbnail strip, dedup, refcount-safe delete, empty-note prune) are all verified.
The current-cycle compact fallback, Added/dimensions/date presentation, and
remembered collapse state were browser-verified 2026-07-31 on real read-only
library data: a 253 MB ZIP reserved no empty preview space, a PNG reported
750×887, Details survived a reload while collapsed, and the console stayed
clean. No Origin note was created merely to exercise Annotated on.
Attachment bytes are an opt-in `.keivotosbk` backup component: the bundle carries
them by content hash, and restore re-materializes any missing ones back into
their folder additively (create-only, never overwriting) after the atomic
metadata restore — so a screenshot survives even if the source folder is lost.

> The status paragraph below belongs to the **Danbooru library sidebar**, not
> the Files info panel above. (It predates the Files base and is kept here until
> the sidebar restoration is closed out.)

**Sidebar — current status: repaired in source (2026-07-16), awaiting user
visual confirmation.** Live diagnosis found the toggle transition mechanically intact
(both CSS end states resolve, and toggling creates the 280ms width/transform
transitions), but the **view-entry animation was lost in the Beta4 rewrite**:
the persistent dock mounted with `is-open` already applied, so entering
Browse/Tags popped the sidebar in with no motion, whereas Beta3.1's conditional
`transition:slide` mount animated on every entry. `SidebarDock.svelte` now
renders one closed frame on mount and applies `is-open` on the next rendered
frame, so the existing 280ms slide plays on Browse/Tags entry while the panel
remains one persistent instance. `tests/test_sidebar_grip_contract.py` pins the
gated class and the rAF intro, but it remains source-string characterization:
timed browser coverage of reversal, rapid toggles, drag, delayed reveal, hover
return, saved position, and scrolling is still missing.

### Search syntax (a user-facing contract — `parse_search_terms` in `backend/modules/danbooru/search.py`)

- Plain tags, quoted phrases, `-` negation on any term.
- Category prefixes: `artist:` `character:` `copyright:` `general:` `meta:`
  `unknown:` and `user:` (local user tags).
- Post ID: bare `#8824525` or `id:`/`post:`/`post_id:`/`danbooru:`/
  `danbooru_id:`/`danbooru_post_id:`.
- Filenames: a pasted complete local filename ending in a supported media
  extension, or partial `filename:`/`file:`/`name:` matching; prefix with `-`
  to exclude a filename fragment.
- Shape presets: `shape:`/`aspect:`/`aspect_ratio:`/`preset:` with values like
  vertical/portrait, horizontal/landscape/wide, phone (+aliases), banner, logo
  — also usable bare (e.g. `phone`).
- Dimensions: bare `1920x1080` or `res:`/`resolution:`/`dim:`/`dims:`/
  `dimension:`/`dimensions:`/`size:`; numeric comparisons for `width:`/`w:`,
  `height:`/`h:`, `pixels:`, `mp:`, `ratio:`, `score:`.
- `rating:` (`g`/`s`/`q`/`e`/`u`, where `u` is Unrated); comma-separated
  combinations such as `rating:g,s,q` support the multi-select sidebar state.
  Also supports `ext:`, `folder:`, and `orientation:`.
- Dates: `created:`/`uploaded:` (+`_at`/`_date` variants) and `downloaded:`
  variants, with ranges.
- Heart spam: `heart:`/`hearts:`/`heart_spam:`/`heartspam:`.
- Blacklist tags are excluded from all searches **except** exact post-ID
  lookups.
- Search Help modal must list whatever this syntax supports — update both
  together.

### Sorting (`/api/images` sort=)

`date`, `downloaded`, `score`, `name`, `id`, `size`, `tags`, `views`,
`hearts`/`heart_spam`, `random` — asc/desc.

### Mass selection (grid)

Select mode with per-card checkboxes; floating menu supports favorites,
collections, folder migration, delete from disk (must warn with the number of
images); shows which selected images are already in favorites/collections.

### Duplicate review

Only true duplicates (same duplicate key), never parent/sibling posts; scope
all / same folder / different folder; preferred flow is merge metadata/tags,
keep the best copy, delete only after warning. Duplicate review itself remains
a grid/filter workflow and never runs a hidden automatic merge or disk deletion.

### Settings (AppSettingsModal — real project settings only)

The modal uses a fixed header, a persistent left-side section rail, and a
remaining-height content pane. On a narrow viewport the same section rail
becomes a horizontal, scrollable destination strip instead of disappearing.
The active section retains its animated accent and transition state. The
content pane scrolls independently. Settings are visibly grouped as
**Suite**, **Files**, and **Modules**. Suite owns **Browsing**, **Display**, and
the shared **Player**; Files owns **Files & Library**,
**Danbooru & Metadata**, and **Safety & Recovery**; Modules owns **Reddit**,
**Karaoke**, **YouTube**, and **Languages**.
Discovery is not a
standalone section: duplicate review belongs to Browsing and cleanup belongs to
Safety.

Each section starts with concise factual state instead of promotional or
repeated explanatory copy: Browsing and Display show their visible section name
inside the colored summary followed by the current saved values;
Library shows generated-file paths plus root/image health; Metadata shows the
local Media → Sidecars → SQLite flow; Safety shows checkpoint, backup, restore,
and derived-cache state. Display intentionally has no decorative "live preview";
the summary reports the real card width, fit, animation, motion, and scale values.
Ordinary preferences remain compact rows without nested category summaries,
while action, status, warning, and recovery treatments stay visually distinct.
Long option sets use selects; short mutually exclusive sets use segmented
controls; binary preferences use switches. Browse sort uses the same single
reversible arrow control as the top-bar sort.

The settings search indexes individual controls, actions, and aliases across
all ten sections. Direct control-name matches rank ahead of looser keyword
matches, and every result includes a concise description of what it controls.
A result opens the correct section and smoothly centers the matching control in
the content pane, using an immediate jump when reduced motion is selected. A
gentle highlight remains visible for about 1.4 seconds after the jump, including
when the same result is chosen repeatedly. Browsing and Display can be reset
independently without touching library data, automation, credentials, or
maintenance state.

Current preferences include startup destination (Home / Browse / last visited),
Home layout (Discovery / Classic), persisted Browse sort/order, default rating,
images per page, sidebar
visibility, Heart Spam, followed-artist notification polling, duplicate review
scope, gallery card size, image fit, tag banner height (280–720 step 20),
animated-media behavior (Never / On hover / Always), followed-artist check
interval (5/15/30/60 minutes), interface motion (System /
Full / Reduced), and interface scale (Default / Comfortable). The former
boolean media-autoplay value migrates in place to the equivalent three-state
behavior.

Library owns local roots (add by path or native Browse dialog, counts/paths,
per-folder Rescan, and a counted Remove chooser: Un-index only or Delete current
central sidecars + un-index), generated-metadata location, and routine incremental
Re-scan. Metadata owns Danbooru credentials, the four resumable import phases,
the local-only watcher interval, Phase 3 filename/result progress, and its
optional limit. The old standalone backfill and tag-refresh cards are replaced
by this single workflow. Safety owns rotating local-recovery checkpoints,
manual component-selectable backup/restore, thumbnail tiers/limit/cleanup,
Clean Orphan Sidecars, and Rebuild Database (Recovery). The original five
backend maintenance operations remain available for compatibility and recovery,
but only routine Re-scan and the two uncommon recovery tools are primary Settings
actions. Tools retain
streamed progress, cancellation, and the one-at-a-time safety lock. They do not
appear in the browsing sidebar.

Settings is performance-isolated without losing its translucent presentation:
the app remains visible through the full-screen blur, while continuous
background animations pause through one CSS presentation state set before the
modal mounts, and currently playing videos pause without enumerating every
browser animation. Both remain paused for the modal lifetime
and resume according to the saved media-playback preference. The modal is a
separate idle-preloaded frontend chunk, so it stays quick to open without being
part of the initial app JavaScript. Browsing and Display open without library API work; folders, credentials, maintenance
status, backup/cache state, and import state load only when their owning section
is opened. Import status does not poll while idle. During an active import it
polls a lightweight task delta and performs the full phase-count query only on
entry and when the task finishes.

**Persistence contract:** every setting that should survive restart is
persisted. Suite-owned localStorage keys use the `keivotos:` prefix, including
`active-module`, `active-rating`,
`sidebar-open`, `sidebar-handle-position`, `fit-mode`, `image-size`,
`image-page-size`, `media-autoplay`, `heart-spam-enabled`, `tag-banner-height`,
`startup-view`, `home-layout`, `last-view`, `browse-sort`, `browse-sort-order`,
`artist-notifications-enabled`, `artist-notification-interval`,
`motion-preference`, `interface-scale`, and the preserved legacy
`player-control-reveal` key. Player controls now use one fixed interaction:
pointer movement reveals the overlay and a non-control background click toggles
only overlay visibility. Startup copies recognized legacy
module-prefixed values into missing suite-prefixed keys and preserves the old
keys. The prefix is centralized in `frontend/src/lib/product.ts`.
YouTube's per-device confirmation-sheet defaults use the same namespace under
`keivotos:youtube-download-defaults`; they cover quality, compatible MP4
preference, optional companion-audio format/quality, and whether automatic
captions may be selected. Every download still requires a fresh inspected plan
and explicit confirmation.
Languages' per-device `language-grid-size`, `language-page-size`, and
`language-autoplay` values use the same suite namespace. Its Anki port/mode and
cached probe live in `user.sqlite`; the optional key is Windows
DPAPI-protected. Opening Settings reads only cached/local state and never
contacts Anki.
The local Profile display name uses `user_settings.profile_name` through
`GET/PUT /api/user-settings/profile_name`; blank values normalize to `Keivotos`,
and confirmed names are limited to 40 characters. An existing
`danbooru:profile-name` value is migrated once after the API becomes
available. The focused metadata-bundle roundtrip changes this value and proves
restore brings the backed-up name back with `user.sqlite`. New browser-local
settings follow `persistedWritable` with a normalizer.
Daily Challenge guesses/reveal state is separate browser-local progress keyed
by challenge ID (`danbooru:daily-challenge-v2:*`). Clearing site data,
changing browser, or changing the HTTP origin resets these browser-only values
without touching SQLite, sidecars, originals, credentials, or backups.

### Artist following & notifications

- Follow/unfollow from artist tag info and Profile; stored in `user.sqlite`.
- Manual Check records Danbooru post IDs only — no file downloads, no
  hotlinks. Missing posts render as `#id` chips, expandable to dashed
  "Not in library" placeholder cards; local posts show real thumbnails.
- One-time current-post baseline per artist before any notification, so
  history is never misreported as new; stale follows re-checked in the
  background at the persisted 5/15/30/60-minute interval while the app is
  open. The notification panel has an explicit **Check now** action plus a
  visible result summary. Configured Danbooru credentials are applied to these
  API requests. The persisted Settings
  master switch hides the bell and stops this background polling when disabled.
- Notification actions open the focused profile panel and update mark-seen
  immediately.
- Profile-media archiving is explicitly user-triggered: validated Twitter/X and
  Pixiv avatars/banners saved under `<metadata>/artist_profile_archive`,
  deduplicated by content hash with history kept, served locally, opened in
  ImageDetail. The Twitter profile extractor resolves the gallery-dl executable
  bundled beside the running venv Python as well as PATH. Absence of a Pixiv
  banner is reported explicitly. **No Twitter/X post fetching.**

### Tag features

Favorite tags + pinning, saved favorite tag combos, blacklist tags (names
loaded at app start), tag suggest, related tags (sidebar), random tag,
letter/category/count filtering in the tags browser, local user tags with
categories, tag wiki cache (fetched once, cached in `user.sqlite`). Home,
Profile artist links, random-tag actions, tag cards, and wiki-linked tags open
tag detail inside Tags; entering Browse through its top navigation clears the
tag-detail request and shows the normal image grid. A middle-click on an active
search chip removes exactly that one chip.

### Folders

- Sidebar folder list is a **pure filter** shown only in Browse and Tags:
  counts + All Folders only. Folder
  management (add/rescan/remove) lives in Settings → Library.
- Folders are **existing directories registered by absolute path**
  (`registered_folders` internal key + `.display_name` + `.path` + stable
  `.root_id`); they may live outside `data_root`. Identity is the stable
  `root_id`, not the leaf name, so roots such as `D:\Art\Images` and
  `E:\Backup\Images` can coexist.
  Adding one kicks off an incremental sync of just that folder. A native
  folder picker is available via `POST /api/folders/browse`. On Windows the
  backend launches the modern Explorer `IFileOpenDialog` in a dedicated helper
  process. Source and portable launches use this Windows API exclusively; there
  is no tkinter fallback.
- **Relocate** selects the folder's new absolute location with the same Windows
  picker, preserves `root_id`, rewrites index/manifest/resumable-ingest and
  user-data path references, and starts a scoped incremental sync. It never
  moves originals or the stable `sidecars/roots/<root-id>/` tree. Relocation
  tolerates pre-incremental databases where manifest/ingest tables are absent
  and checks path conflicts without loading every library path into memory.
- Registering never creates directories. Removal previews exact indexed-image,
  current-sidecar, and byte counts, then offers **Un-index only** (registration,
  index rows, sync manifest, and resumable ingest state) or **Delete current central
  sidecars + un-index**. Neither choice touches external images or adjacent
  preservation sidecars, and archived sidecar history is always retained.
- Per-image folder moves keep metadata consistent and work for registered
  external folders too (`folder_target` maps root selectors to their paths);
  move/delete guards allow the data root plus registered folders. Folder
  filtering and duplicate same/different-root scope use `root_id`, so equal
  display names do not collapse two drives into one root.
- Images without sidecars are indexed minimally (dimensions, file dates,
  content MD5, no tags) and are rating **Unrated**. A `g` filter never includes
  them; `rating:u` selects them explicitly. Pillow's known corrupt-EXIF warning
  is suppressed only while reading dimensions; the image remains indexable and
  real inspection failures still remain per-file errors.

### Library maintenance tools (`/api/tools`, Settings -> Library)

The library watcher is opt-in and persisted in `config.json` with a selectable
5/15/30/60-minute interval. It stat-walks configured roots and compares
mtime/size with `sync_manifest`; it always launches the ordinary local
incremental `sync`. **It never contacts Danbooru.** `GET/PUT
/api/automation` expose the toggle, interval, last-check time, and candidate
count. Its directory-entry walk avoids a resolve/stat pair for every media file,
and its complete check-to-launch window is serialized with backup/restore and
manual maintenance starts.

There is one explicit bulk-import workflow with four resumable phases:
(1) stat-only Discover, (2) bounded-worker Hash & Inspect, (3) explicitly
confirmed rate-limited Danbooru Metadata using the stored MD5 rather than
rehashing, and (4) incremental Finalize. Phase 3 pins the current filename above
its progress bar and keeps recent Matched / No match / Failed results plus exact
counts. Per-file results also live in `ingest_state`; one damaged file does not
stop healthy files from finalizing. Folder add/rescan and the watcher stay on
the single ordinary incremental-sync path.

`backfill` accepts an existing media folder (or all configured library folders)
and optional limit. It uses a filename MD5 when available, otherwise hashes the
image, looks up the Danbooru post by MD5, and writes only missing canonical JSON
and tag sidecars. Media and local user tags are not modified.

`sync` (**the default indexing path**: incremental delta import driven by a
`sync_manifest` mtime/size table — new/changed sidecars imported, sidecar-less
media indexed minimally, rows for deleted files pruned; unchanged files are
never opened), `backfill` (fetch missing sidecars, rate-limited), `sqlite`
(full DB rebuild from sidecars — **recovery only**, chained with a sync so the
manifest is rebuilt), `clean-sidecars` (orphan cleanup), `refresh-tags`
(overwrite + **archive replaced sidecars** + sync). Folder add/rescan reuse
the `sync` tool id, so its progress is visible wherever tools status shows.
Tools keep writing sidecars to the configured metadata directory under the
stable root-based layout. The explicitly approved migration is copy-and-verify:
legacy sidecars are preserved and canonical copies are created. **Never wire a full rebuild into a
routine flow — sidecars stay the durable store, SQLite stays the incremental
index.** With no explicit `scan_folders`, the neutral library root is scanned;
the application ships no developer-specific folder-name fallback.

`refresh-tags` has a post-step that compares each archived sidecar to its new
replacement and saves `old tags - new tags` in `user.sqlite.tag_removals`.
Only this manual refresh records removed-tag history. `clean-sidecars` first
checks that the media root is reachable; an unplugged or unavailable root is
skipped rather than mistaken for a library full of orphans.

Only one tool may run at a time to prevent concurrent sidecar/SQLite writes;
each job exposes stage, progress,
recent output, and cancellation. Danbooru username/API key can be entered in Settings;
the username and a Windows-DPAPI-encrypted key are stored in git-ignored
`<metadata>/danbooru_credentials.json`. Environment variables override saved values.
Keys never appear in API responses, command lines, or tool output, and
connection checking is explicitly user-triggered.

### Reddit local preservation module (Reddit fork Slices 0-8)

Reddit is a registered, optional Keivotos module. Its durable content lives at
`<suite-home>/modules/reddit`: a rebuildable `reddit.sqlite`, verified raw
structured responses and imports, capture manifests, and content-addressed
local media. The shared `user.sqlite` stores only the normal optional-module
enablement slug; Reddit content and observations never enter it.

A subreddit name or supported Reddit/post/user/search/asset URL defines
the capture scope. A user-supplied local JSON, JSONL/NDJSON, or
gzip-compressed JSONL file supplies records. JSONL sources stream in bounded
chunks; each source record is first preserved in an atomic, verified
gzip-compressed raw chunk, then normalized into a rebuildable Reddit SQLite
index with post/comment observations and FTS5 search. Interrupted jobs resume
after the last committed source line, and rerunning a completed job with
`--resume` is duplicate-free.

Post limits apply to distinct post IDs even for comment-only inputs. Comments
may be normalized with their parent hierarchy or kept as raw-only evidence.
Image, preview, video, avatar, subreddit-asset, wiki, rule, moderator, and
allowlisted-external options are capture policies and asset queue entries only:
local import never opens a remote URL, creates the future media directory, or
downloads bytes.

Slice 1 streams standard Arctic Shift `.zst` JSONL with optional published
SHA-256 verification, inclusive/exclusive UTC boundaries, scoped/global source
handling, and a deterministic coverage report. Global sources are filtered to
the target before raw chunks are written. Slice 1 added
`zstandard==0.25.0`; Slice 2 adds `yt-dlp==2026.7.4`.

An explicit official Reddit OAuth mode discovers up to 1,000 current unique
Listing items with 100-item pages, `after` cursors, rate-limit waits, bounded
retries, and repeated-cursor protection. It creates only a minimal ID/URL
manifest; it never stores API response bodies, OAuth secrets, or bearer tokens
in the durable archive. A later local `.zst` import can use that manifest to
select the discovered posts and comments linked to them.

Slice 2 separately plans already-queued Reddit-hosted media without network
access, then requires a matching count and selection SHA-256 before download.
gallery-dl handles supported direct Reddit images, a bounded redirect/DNS/MIME
checking fallback handles recognized Reddit CDN images, and pinned
`yt-dlp==2026.7.4` plus the existing FFmpeg path handles already-stored
`v.redd.it` manifests/files. File-count, per-file, run-byte, retry, timeout,
and reserved free-space limits are finite. Completed bytes are installed
create-only by SHA-256, identical bytes deduplicate, manifests and database
events remain observations, partials are resumable, and failed/oversized
outputs are preserved. Generic external-site roles remain blocked.

Slice 3 adds a second offline importer at `scripts/reddit_community.py` for
user-supplied Arctic Shift about/rules/wiki JSON, JSONL, gzip JSONL, or `.zst`
sources and an explicit optional local moderator-snapshot bundle. It preserves
create-only raw chunks and provenance, stores versioned about observations,
ordered rule snapshots, wiki revisions, and moderator snapshots, and writes
deterministic coverage for every job. Global sources are filtered before raw
preservation; already-scoped sources keep malformed or wrong-target nonblank
records as evidence. Recognized subreddit icons and banners are queued for the
separately confirmed media phase without downloading bytes.

Slice 4 adds `scripts/reddit_comments.py` and a module-owned read-only comment
tree projection. It opens only an existing archive, checks a finite comment cap
before loading, deterministically orders parents and children, preserves every
normalized comment exactly once, and reports missing/invalid/cross-post/self
parents, cycles, duplicates, unknown posts, stored/derived depth differences,
body removal state, and latest declared-versus-observed counts. Missing parents
become explicit export placeholders.

Inspect mode writes nothing. Export mode uses an iterative encoder so deeply
nested threads do not overflow Python recursion, applies a finite byte cap, and
installs one explicit JSON path create-only. Existing identical output is
verified; unlike output is never replaced. Cycle breaks and derived depths
exist only in the projection—SQLite comment rows are not changed.

Slice 5 adds bounded direct-link capture through Arctic Shift's structured JSON
API. A post URL retrieves that exact post ID and a comment tree capped at
25,000 records. A subreddit URL retrieves only about metadata, rules, wiki
paths/pages, and subreddit image references; it never enumerates subreddit
posts or comments. Exact JSON responses are installed create-only with hashes,
source URLs, timing, and coverage before normalization. Arctic Shift
`kind: "more"` nodes become additive `comment_placeholders` rows with unresolved
IDs, so the thread view reports the observed unresolved count rather than a
false complete tree. Arctic Shift supplies no current moderator membership, so
that domain is explicitly unavailable unless a local moderator snapshot bundle
was imported.

Slice 6 adds a cohesive SQLite read-only/query-only library and
`scripts/reddit_library.py`: keyset-cursor post feeds, filters, FTS5 post/comment
search, post observations plus bounded comment trees, latest community
about/rules/wiki/moderator snapshots and history, local media references, and
capture/job status.

Slice 7 registers the descriptor at `<suite-home>/modules/reddit`, always mounts
the enabled-state-gated `/api/reddit/*` router, and serves only contained,
hash-addressed local media with byte ranges and safe response headers. Route
presence remains stable when the module is disabled; content endpoints then
return the module-disabled response.

Slice 8 adds a module-owned Reddit-inspired Svelte surface: an infinite local
saved-post feed, subreddit/author/flair filters, FTS search, post observations,
nested comment detail with incomplete-capture warnings, and a community view
for about/rules/wiki/moderators. It renders only verified local media endpoints
and never hotlinks archived remote URLs.

The 2026-07-29 archive-workbench expansion adds Home, Popular, Communities,
and Profiles destinations with the same desktop rail/mobile bottom-navigation
answer used by the other optional modules. Popular is a local score ordering,
not a remote feed. Communities aggregates every locally known subreddit,
persists per-device favorites, exposes snapshot counts and refresh, and gives
the same keyboard-accessible three-dot/context actions as saved posts and
profiles. A bounded public user URL capture preserves the exact Arctic Shift
post/comment search responses, then indexes at most 100 matching records of
each kind. Post, community, and profile refreshes add observations; they never
rewrite an earlier observation.

Post detail renders the recursive comment tree directly with per-branch
collapse/expand controls instead of flattening and truncating it. Indentation
is one bounded increment per recursive branch and tightens after six levels, so
deep threads retain readable content width. When at least
two post observations exist, score, declared comment count, and upvote ratio
are charted separately. New Reddit Files aliases retain a readable source name
but are keyed by owner plus content hash, so preview/original roles that resolve
to identical bytes converge on one future alias. Existing duplicate aliases
remain untouched as archive evidence.

The in-app capture follow-up adds a **Save link** control immediately after
Refresh. It opens a right-to-left 240 ms drawer with one Reddit URL field,
progress, error, and success states. `POST /api/reddit/capture` accepts only a
post, subreddit, or public user target, requires the module to be enabled,
serializes capture jobs, and runs the same bounded direct-capture service as
the CLI. A successful
post receipt is derived from the indexed post and its actual archived-comment
count, so a source-response count cannot masquerade as an indexed success. A
successful post capture refreshes the feed and archive counts; a successful subreddit
capture refreshes the community/status index. Closing is available through the
backdrop, close button, or Escape while idle.

The drawer also offers Images and GIFs, Videos, and **Linked files** as generic
download selections. Capture and download remain separate: after indexing, an
offline plan reports the exact bounded selection and the user must confirm it.
Confirmed transfers run as transient background jobs. The drawer shows a
file-count progress bar and may be closed after the job starts; a Reddit-header
activity control continues to show active count, aggregate progress, recent
jobs, failures, and completion. **Update downloaded media** reopens the same
bounded capture/plan flow for one saved post.
All valid outbound URLs appear as inert link cards without fetching previews.
Reddit images use gallery-dl or the guarded HTTP image path, Reddit video uses
yt-dlp plus FFmpeg, ordinary HTTPS file responses use a guarded streaming path,
and MediaFire single-file pages use pinned `mfget` only to resolve metadata
before the same Keivotos byte/DNS/redirect limits apply. HTML pages, private or
login-required targets, custom ports, non-public addresses, and unsupported
folder/page links are never installed as files. Completed bytes remain
content-addressed and also receive a friendly hardlink/copy under the module's
`media/library` tree. That exact declared root is published and scanned as
**Reddit downloads** in the Files base by default; every other path under the
private suite home remains forbidden to Files serving.

Settings has a sixth, module-owned **Reddit** category. It keeps local
Save-link defaults for Images/GIFs, Videos, Linked files, and failed-file retry
under the suite-owned `keivotos:` browser-storage namespace; the drawer reads
those defaults when it opens but still requires the per-run confirmation.
The category reads `/api/reddit/status` for archive counts, queue/job activity,
database/archive/media/Files paths, active capture/download state, and the
backend's exact finite file/run/free-space/thread limits. It also explains the
post-versus-subreddit Arctic Shift scope and the default Files publication
boundary. These controls do not capture, download, delete, or rebuild data.

The 2026-07-28 feed regression was a misplaced post-detail comment-tree block:
`list_posts` referenced thread-only `normalized` and `max_comments` names and
returned HTTP 500 even though capture had correctly indexed the post. The block
now runs only in `get_post`; direct feed and post route contracts cover both
paths so archive counts can no longer coexist with a falsely empty 500 feed.

WARC, WACZ, Wayback, Common Crawl, browser-capture, and replay adapters are
explicitly outside the Reddit product. The 2026-07-27 isolated browser pass
confirmed the right-to-left drawer, focused URL input, backend validation,
target-specific success, refresh, Escape close, and a clean console. Three
bounded post captures and one subreddit-only capture were also exercised
against Arctic Shift in a disposable module home; no media URL was opened and
the scratch archive was removed after verification. Exact commands, the
moderator-source limitation, storage layout, coverage semantics, and the API
retention boundary are in `REDDIT_MODULE_PLAN.md`.

### Karaoke and YouTube local-media modules

Karaoke and YouTube are separate optional descriptors with always-mounted,
enabled-state-gated APIs. Both own create-only libraries beneath their
descriptor homes and publish only their declared `media/library` roots to the
Files base. Disabling either module hides its surface but preserves its index,
media, receipts, jobs, and precious user state.

**Karaoke** searches Kara.moe first through its structured API. Search and
detail results normalize the title, year, duration, series, languages, singers,
songwriters/composers, video content, origin, platforms, creators, karaoke
authors, group, collection, and franchise fields used by the supplied
metadata-first reference. Selecting a result creates a deterministic,
one-hour plan for Kara.moe's official hardsub video, estimated size, local
destination, and selection SHA-256. The transfer starts only after the user
confirms authorization. Provider hosts, DNS, redirects, response type, response
bytes, timeout, cancellation, and resume partials are bounded.

A completed Kara.moe item preserves sanitized source metadata and an
acquisition receipt. Timed provider cues become normalized cue rows plus
clearly labeled generated VTT and LRC derivatives; Keivotos does not pretend
those derivatives are an original ASS file. Local ASS/SSA, SRT, VTT, or LRC
files may also be attached create-only. Karaoke can add an existing registered
Files audio/video asset without copying the primary media: it stores the Files
source/relative path and SHA-256, and refuses playback if the referenced bytes
later change.

The Karaoke surface is a local cover library with Library, Favorites,
Playlists, and Kara.moe discovery. Selecting a song opens the metadata-first
detail view before playback. The shared full-screen local player provides:

- Mouse 1 on non-control player space toggles the overlay immediately; motion
  reveals it and active playback hides it after three idle seconds;
- center rewind 10 seconds, play/pause, and forward 10 seconds controls;
- seek/buffer timeline, volume/mute, speed, previous/next, shuffle, repeat
  off/all/one, captions, settings, Picture-in-Picture, and fullscreen;
- Space/K play-pause, J/L ±10, arrows ±5, M mute, C lyrics, F fullscreen,
  0–9 percentage seek, Shift+N/P queue navigation, and Escape close order;
- a top-left Lyrics drawer with track choice, current/next cue, seekable
  transcript, and ±30-second timing offset;
- local ASS/SSA rendering through the bundled JASSUB/libass WebAssembly worker,
  native WebVTT captions, LRC/VTT transcript cues, and no remote font fetch;
- Media Session handlers plus durable lyric track, lyric offset, repeat,
  shuffle, play count, and last-played state in `user.sqlite`. Karaoke always
  opens at 0:00 and writes no resumable position.

Native WebVTT tracks are served through a normalized cue endpoint, so preserved
Kara.moe token arrays—including Python-representation arrays from older
imports—reach the browser as plain `WEBVTT` text rather than dictionary
objects. Karaoke and YouTube queues are manual, per-surface selections managed
from each item's context menu; opening a local library never queues every item.
Truncated or malformed MP4 box structure marks Karaoke media incomplete without
trusting Kara.moe's unrelated metadata-size estimate. **Replace broken copy**
for incomplete media, and **Update local copy** otherwise, download into a
clean versioned directory and switch the catalog only after the expected bytes
arrive. The prior file is recorded and remains available in Files for manual
deletion.

**YouTube** is a local acquisition module, not an embedded streaming client.
An explicit search runs bounded `ytsearchN` metadata through the pinned yt-dlp
installation. Result thumbnails are copied through an HTTPS YouTube-CDN,
public-DNS, redirect, MIME, timeout, and 2 MiB guard into the local cache before
the browser displays them. The UI never hotlinks a result thumbnail and never
feeds a remote YouTube video URL into the player.

Selecting a result inspects actual reported formats. The confirmation sheet
offers 480p, 720p, 1080p, 1440p, 2160p, or Highest where applicable; compatible
MP4/H.264/AAC preference; optional best/M4A/Opus/MP3 companion audio at
128/192/320 kbps; manual subtitles; and separately labeled automatic captions.
The quality cap chooses the best resolution first and uses compatibility to
break format choices at that resolution. The plan shows the actual video/audio
format IDs, codecs/containers, estimated bytes, destination, files to be
created, and selection SHA-256 before an authorization checkbox can start it.

The shared yt-dlp process service uses no shell, ignores user yt-dlp config,
rejects playlists and arbitrary sites at the YouTube provider boundary, applies
finite retries/socket/process/file limits, preserves resumable partials, and
supports cooperative cancellation. One job runs at a time. A completed item
keeps the video, requested companion audio, thumbnail, manual/automatic caption
sidecars, sanitized metadata, and an acquisition receipt; then it is indexed,
published, and immediately scanned into Files. The YouTube-inspired surface has
Explore, Local library, and Downloads views and plays only completed local
bytes through the shared player. **Update local copy** performs the same fresh
inspection and authorization flow, publishes to a clean versioned destination,
and retains the former file path as obsolete evidence for manual cleanup.

The cross-module fallback is explicit. When Kara.moe returns no song, **Search
YouTube instead** transfers the current query and karaoke intent through
in-memory module handoff state. After a YouTube download completes, **Add to
Karaoke** imports the video by its published Files source identity and copies
only selected local subtitle bytes into Karaoke's create-only lyrics area.
Neither module reaches into the other's private database or storage.

Settings adds module-owned Karaoke and YouTube categories. Karaoke reports live
song/playlist/job counts, provider handoff state, player behavior, and exact
storage/Files paths. YouTube reports local-video/job/concurrency state, persisted
confirmation-sheet defaults, the public-single-video/no-cookie/no-playlist
boundary, and exact storage/Files paths. These status reads do not download,
delete, rebuild, or contact a provider.

Automated verification covers descriptors and enablement, additive Karaoke user
tables, lyric normalization, create-only and contained storage, Kara.moe plan/
confirm acquisition, Files-reference hash checks, actual YouTube format
selection, manual-versus-automatic captions, shared yt-dlp argument ordering and
cancellation, local-only frontend contracts, cross-module handoff, and the
OpenAPI snapshot. The final 2026-07-28 regression passed 352 tests, Python
compile, a zero-warning frontend check, and the production build. An isolated
timed browser pass with generated MP4/VTT/ASS fixtures verified the core
player, lyrics, queue, persistence, responsive layouts, settings, local-only
YouTube playback, Files publication, and YouTube-to-Karaoke handoff with a
clean current-bundle console and clean server log. Real provider search and
media download were intentionally excluded.

### Languages learned-word module

Languages is the fifth optional module descriptor. It owns isolated
`modules/language` storage, a rebuildable `language.sqlite`, a credential
path, the enabled-state-gated `/api/language/*` namespace, an original local
drawer icon, and a Files-published `media/library` root. Disable, release, and
study-folder role changes remove no catalog, media, authored row, source byte,
or sidecar.

The disposable catalog derives stable word identity from source plus immutable
source key, never editable text. It separates senses, examples, grammar/usage
notes, tags, versioned media, every Anki card's progress, and sync runs. The
weakest card determines the displayed mastery stage. Missing and suspended
states are mirrored, not interpreted as deletion.

Anything the user authors is authoritative in additive `language_*` tables in
the suite `user.sqlite`: complete manual words, mirrored-field overrides,
private notes, manual media associations, favorites, retireable lists,
confirmed field profiles, connection settings, and local practice results.
Manual removal is a soft retirement. Reverting an Anki override reveals the
mirror again. A confirmed manual-to-mirrored merge retires the original record
while preserving authored fields, the private note, favorite, list membership,
and user media; authored media takes presentation precedence over mirrored
media.

AnkiConnect is loopback-only and read-only. Its strict allowlist covers
permission/version/deck/model discovery, note/card/review reads, and media
retrieval; no mutating action is callable. Page load and Settings never probe
Anki. Probe, dry-run preview, field-profile confirmation, duplicate selection,
and background import are explicit user steps. Imports are cancellable, pull
media into versioned create-only paths, write per-run receipts, and never
schedule a card. `.apkg` import is not supported.
The built-in KO1Kv2 profile also recognizes field-compatible note-type
variants such as `KO1Kv2+`; compatibility is checked against the model's
actual field names before the confirmation action is enabled. Unsupported
models show a specific mapping explanation instead of a disabled dead end.

The module surface provides a configurable Korean study profile with English
and Mongolian meaning order, search, stage/source/missing/suspended filters,
named browser-local filter presets with clear-all, shared grid sizing,
30/60/120 server paging or bounded infinite append, and
Korean/English/Mongolian alphabetical ordering. Today starts local practice
directly; Sentences and Grammar are filtered and paged by the server instead
of fetching 5,000 rows for client filtering; Sentences, Grammar, and Decks
have actionable empty states. Practice history now exposes totals, accuracy,
daily activity, current streak, and per-word results without changing Anki
scheduling. Every card and dense view has touch-visible accessible three-dot
and context-menu actions for local edit, detail, favorite, and list
membership. List and filter naming use a focus-trapped custom dialog rather
than a native prompt. The mastery bar has a readable stage label and legend.
The dedicated Browser presents number, Anki/manual source, Korean,
sentence form, English, Mongolian, note type, deck, mastery, due state, media,
and flags as sortable columns with row selection and a right-side inspector.
The original Hangul Atlas groups words by initial consonant in an irregular
mastery-tinted constellation layout with keyboard focus and reduced-motion
support. Detail supports local image wash, exact sentence-form/headword
highlighting, local audio/autoplay, mastery, keyboard navigation, notes, edit,
favorite, and override revert. The right-side composer supports manual or
override editing plus local word/sentence audio and image attachments.

The Analyzer is an original dark Keivotos surface inspired by the same
sentence-to-structure workflow as dedicated Korean study tools. Kiwi runs
locally for sentence splitting, morphemes, lemmas, and part-of-speech tags;
Keivotos adds friendly labels, deterministic grammar cards, color-coded
horizontal token inspection, compound dictionary forms, Revised Romanization,
and exact matches to effective local Anki/manual meanings. It never presents
generated prose as dictionary fact: each result labels Kiwi, Keivotos rule,
local Anki/manual, or KRDICT provenance. Existing exact example translations
and sentence audio are reused; otherwise English and Mongolian translations
remain user-editable.

Pasted Analyzer text is not retained automatically. Save is explicit and
stores the text, authored translations, and analysis in additive
`language_analyzer_saved` rows; retirement is a tombstone. Derived morphology
and dictionary responses live only in disposable `language.sqlite` caches.
The optional KRDICT key is DPAPI-protected alongside the independent
AnkiConnect key. KRDICT is never contacted by page load or analysis; only the
visible lookup button for the selected lemma can make the fixed-host,
size/timeout-bounded request. Browser speech uses an installed Korean system
voice when available and downloads nothing.

Practice builds from the visible or selected set and supports Korean→meaning,
meaning→Korean, audio→meaning, and sentence cloze. Space reveals/replays, 1/2
self-grade, Escape exits, results stay local, and missed words can be replayed.
The searchable Languages Settings category owns the explicit Korean target and
English/Mongolian meaning-order profile, Anki connection/profile controls,
optional explicit KRDICT enrichment, storage/Files paths, full JSON export,
grid/page defaults, and autoplay.

Automated coverage uses a stub Anki client only. The isolated browser pass
created a manual Korean word, copied and rendered a local SVG, verified
favorite/search/table/selection/cloze/self-grading/settings/sync-boundary
behavior, and remained free of console/server errors. The follow-up pass
verified three-dot Escape/outside closure, edit and list actions,
Korean/English alphabetical ordering, Browser headers/rows/inspector,
Hangul Atlas keyboard-focus reveal, real Kiwi token and grammar output,
exact local translations, saved Analyzer history, and word-detail/composer
handoffs. No live Anki or KRDICT operation was run.

### Manayomi local manga module

Manayomi is the sixth optional module descriptor and the manga-focused surface
for this checkout. The suite registry owns its public `manayomi` identity while
its existing data remains under `modules/manga`; no database rebuild or
destructive storage migration is required. The module keeps the established
`/api/manga/*` API and publishes every available registered manga root into the
neutral Files base. Existing installations are enabled once during the
registry migration when their module database already exists; later explicit
disable choices are preserved.

The Library indexes existing CBZ files in place. It supports roots, scans,
server paging, search grammar, structured tag/title filters, sort, language,
favorites, pins, categories, cover generation, detail, and local archive
reading. Manayomi's header has a dedicated Keivotos burger beside its module
mark, opening the suite drawer for other modules and Settings. The Library's
separate category/sidebar control uses a split-panel icon so it cannot be
mistaken for that suite drawer. Library keeps Filter at the left of its
toolbar. Remote Browse owns one Filter button in the provider strip, so
nHentai and MangaDex each open their own provider-specific compact sheet
without rendering a permanent sort/language row over the grid. Both local
Library and remote Browse cards normalize known language tags into JP, EN, CN,
or KR badges at the lower-right corner.
At phone widths, Manayomi's five section destinations move into a compact fixed
bottom bar while the header retains the suite drawer, module identity, display,
cover visibility, Browse-only Hide downloaded, and Downloads actions. Browse
therefore has only the provider/filter row and search row above its covers.
Desktop keeps the section destinations in the header. Library retains its
deliberate compact controls rather than browser-dependent wrapping.

Remote Browse has a persistent provider selector directly beneath the Browse
section: **nHentai** preserves the established gallery workflow, while
**MangaDex** searches the public MangaDex title catalog. MangaDex cards show
cover, creator, status, available-language count, tags, and locally saved
chapter count. Its filter sheet exposes translated and original language,
content rating, publication demographic, status, every supported sort and
direction, AND/OR tag matching, and the live MangaDex Content, Format, Genre,
and Theme catalogs. Fixed enum values are validated locally; tag words and UUIDs
come from MangaDex's public tag endpoint and are cached for thirty minutes.
nHentai's existing sort, language, and six structured query fields live in its
own sheet, so MangaDex filtering does not reinterpret nHentai's query grammar.
Hide downloaded is one persisted Browse header action shared by both providers.
Clicking a MangaDex title opens localized title information, description,
authors/artists, publication state, tags, explicit MangaDex attribution, and a
language-filterable chapter feed grouped by volume. Desktop shows information
and chapters side by side; phones open directly on a prominent Chapters tab
with Info beside it, preventing the cover and description from pushing the feed
below the initial viewport. Chapter loading, empty, and failure/retry states are
distinct. Translations and scanlation groups with the same chapter number remain
separate. Publisher-hosted chapters link to their external publisher and expose
no false Read or Download action.

MangaDex hosted chapters read through Manayomi's contained backend proxy in the
same paged/vertical, LTR/RTL, fit-height/fit-width, fast/original reader. The
backend obtains temporary MangaDex@Home locations, never exposes authorization
headers to image nodes, refreshes failed/expired locations, and reports
community-node transfers as required by MangaDex. Remote reading writes only
private additive progress state. A title-level Download action first enters
chapter selection and displays the selected count; every actual transfer remains
an explicit per-chapter queue action. Scanlation-group credits remain attached
to chapter rows and MangaDex is credited in both Browse and detail.

Downloads is a right-edge header action rather than a center navigation tab.
Its anchored dropdown keeps the active job and newest locally downloaded manga
visible, while **Show all** opens the full queue/job summary and every local
manga ordered strictly by the preserved Downloaded date. The HeH Tags section
lists every generic tag present in downloaded nHentai metadata rather than the
provider site's 120-tag public shortlist. Its counts are calculated from the
actual downloaded manga/tag relations used by the Library Tags filter rather
than HeH totals or a cached tag summary. Popular sorts by that exact local
count and A–Z sorts the complete downloaded tag set alphabetically. Its
responsive columns fill downward before continuing to the next column. The
directory remains local and available without provider access. A sticky local
search filters the complete directory in memory; phones show two downward-flowing
columns (one only below 340px), while iPad-width surfaces show four. Selecting a
tag returns to the local Library filter, so the result contains downloaded
manga only rather than remote Browse results.

Blacklist settings are module-owned. When ignored works are hidden, Library
excludes matching tag rows before totals, page counts, and offsets are
calculated, while Browse adds the same negative tags to its explicit provider
query. When ignored works are shown, Library uses normal cards; only Browse
uses a solid black cover with a `Blacklisted` label and the exact matching tag
names. The first click animates that black cover away and reveals the unblurred
manga cover. The second click opens manga information, where the cover remains
visible.

Manga detail uses a medium-large responsive panel and cover, larger tag chips,
equal-height category controls, and one adjacent row of equal-size icon actions:
play/Read, external nHentai page, Files folder, heart, and pin. Read is black for
a remote work and purple for a downloaded local work; favourite and pin retain
their state colours. On phones the cover and metadata share the summary row,
the action row and categories precede the tag wall, and the first eight tag
chips expand through an explicit Show all/Show fewer control. iPad and desktop
retain the roomier side-by-side information layout. Every gallery can open its nHentai page explicitly;
downloaded CBZs can also hand off to their exact published location in Files. A download started or already
active while detail is open shows its real queued/page/completed state. The
completed bar remains for that dialog lifetime and is discarded when detail
closes. Tag clicks return to the originating Library or Browse surface, open
its filter popover, populate the matching Tags/Categories/Groups/Artists/
Parodies/Characters field, and immediately apply that filter.
Clicking the dim backdrop closes manga information without affecting clicks
inside the panel.

Reading History is durable private Manayomi user state. Starting the reader and
changing pages upserts the current page, page count, title, cover identity, and
timestamps in the additive `user.sqlite.reading_history` table. Paged and
vertical readers both update it. History first presents unfinished manga as
**Continue reading**, opening directly at the saved page, and **Show all
history** exposes every manga read in Manayomi. This state survives index
rebuilds and does not modify CBZ media or provider metadata.

The displayed Downloaded date is the first local-added time. Existing
`manga.created_at` values are copied once into the additive
`user.sqlite.library_additions` table, keyed by source and gallery identity.
Future scans/downloads use insert-if-absent semantics, so rescans, metadata
refreshes, root relocation, filesystem timestamp changes, and disposable index
rebuilds never replace the preserved date.

MangaDex title and chapter UUIDs are preserved verbatim in `mangadex.json`
sidecars and additive index columns. `user.sqlite.remote_identities` maps each
opaque chapter UUID to a stable negative local gallery key, keeping all existing
numeric Library, cover, reading-history, favorite, pin, category, series, and
Files contracts intact without colliding with positive nHentai gallery IDs. The
mapping survives disposable index rebuilds. Downloads create one original-quality
atomic `chapter.cbz` beneath `<title>--m<title-uuid>/<language/volume/chapter>--c<chapter-uuid>/`,
then write the manifest and sidecar and index the result; existing archives are
never overwritten. Scans recognize this sidecar locally without contacting
MangaDex.

A registered root may be rebased after its folder is moved externally. Preview
resolves the destination, rejects conflicts/escapes, and verifies every indexed
file at its relative destination without changing either database. Apply
requires explicit confirmation and atomically updates the disposable index and
precious root record only after that same verification. It moves, deletes, or
rewrites no CBZ media; favorites, pins, and categories remain keyed to source
and gallery identity.

The Svelte surface uses a dynamic-height, min-height-zero container so mobile
browser chrome does not crop tabs, toolbars, grids, or the touch reader. A
pre-registry browser that last used the former `manga` view migrates its active
surface to `manayomi` without deleting the legacy storage key.

### API surface (grouped; domain routers included by `backend/server.py`)

images & media (`/api/images*`, `/api/image-file`, `/api/thumbnail`,
random, heart-spam, user-tags, open-location, folder move/delete (single and batch), relations
refresh) · timelapse frames · popularity periods · home (tags, image-rails) ·
daily challenge (+character suggest) · tags (list, wiki, random, suggest,
related) · artist follows (+names, check, seen) · artist profile assets
(+bulk refresh, asset files) · folders (+browse, rescan, relocate, removal preview/modes) · favorites (+ids, pin, batch update) · favorite
tags (+names, pin) · favorite tag combos · blacklist tags (+names) ·
collections (+pin, image pin, bulk edit and membership lookup) · stats · tools (+run,
status) · Files base (`/api/files/*`: sources, browse/search, scan, lazy hashes,
duplicates, filesystem/native picker) · suite (`/api/suite/*`: descriptor
enablement plus folder batch/forget preview) · Reddit (`/api/reddit/*`: bounded
link capture, cursor feed, FTS search, post/thread detail, community context,
status, offline media plan, confirmed bounded media download, and guarded local
media) · Karaoke (`/api/karaoke/*`: status, Kara.moe
search/detail/plan/download/jobs, library, Files import, lyrics, favorites,
playlists, playback, ranged local media) · YouTube (`/api/youtube/*`: status,
search/inspect/plan/download/jobs, local library, cached thumbnails, ranged
local media) · Languages (`/api/language/*`: cached status,
word/query/detail/manual/override/media operations, decks/today,
favorites/lists/bulk, practice, export/settings/profiles, and explicit
read-only Anki probe/preview/import/jobs, plus local Analyzer
status/analysis/saved-history and explicit KRDICT lookup) · Manayomi
(`/api/manga/*`: status/settings, roots/verified relocation, scan, Library,
detail/covers/pages, categories/favorites/pins, and explicit nhentai browse or
download jobs). Removing or renaming any of these,
or dropping fields from the
models in `backend/models.py`, is a breaking change — check
`frontend/src/lib/api.ts` for the consumers.

The tools domain also includes Danbooru credential status/save/remove/check,
configured folder suggestions, targeted backfill runs, job cancellation,
storage/import status, incremental import-task status, and four-phase actions,
automation status/toggle,
local-recovery status/manual checkpoint, manual backup estimate/create/inspect/restore, and thumbnail-cache status,
limit, cleanup, and clear actions.

### Automatic local recovery

- `user.sqlite` is snapshot automatically after database initialization on app
  startup and after every successful `sync`. `VACUUM INTO` + `quick_check` verify
  each checkpoint, byte-identical states are skipped, and only the newest five
  are retained under `<module-home>/local_recovery/user_database/` by default.
- Settings shows the exact directory, latest time, and retained count and offers
  **Checkpoint now**. This same-device safety net is separate from portable,
  user-triggered `.keivotosbk` bundles.

### Manual metadata backups and restore

- Backups happen **only when the user presses Create backup**. The destination
  is fixed at `%LOCALAPPDATA%/Keivotos/backups`; legacy files under the former
  `backups/danbooru` location are copied, verified, and preserved. Persisted component
  toggles cover `user.sqlite`,
  `danbooru.sqlite`, current sidecars, sidecar history, archived artist
  profile media, and Files attachment bytes (bundled by content hash and, on
  restore, re-created into their folder additively — create-only, after the
  atomic restore, never touching originals or the metadata-tree rollback path).
  Estimated raw and compressed sizes are shown first, and the
  created filename, size, and destination are confirmed inline in the same card.
  The user database component includes `user_settings`, including the Profile
  display name.
  The retired `backup_destination` key is ignored and scrubbed when runtime
  configuration is next saved; external library locations never relocate this
  fixed suite backup directory.
- A `backup_<Unix timestamp>.keivotosbk` file is a CRC-verified ZIP64 bundle
  with a manifest and SQLite
  `quick_check` results. Original images and derived thumbnails are always
  excluded. DPAPI credential files are also always excluded: credentials stay
  bound to the current Windows user and are never transferred by backup or
  restore. Legacy `.whbackup` files inside the fixed directory remain listed
  and restorable. Backup staging lives as one deterministic child of the fixed
  destination, is guarded by the existing process lock, and safely replaces a
  stale staging directory left by an interrupted prior attempt. Bundle config
  and manifest data omit absolute library, metadata, work, and backup paths.
- Restore only accepts a bundle inside the fixed suite destination, rejects
  unsafe ZIP paths, validates staged databases before replacement, checkpoints
  live SQLite files, preserves the previous metadata under
  `local_recovery/restore_*`, and requires an app restart. External originals
  are never touched. Restore staging uses the same deterministic, lock-guarded
  cleanup rule inside the configured metadata directory. Its replacement window
  waits for in-flight application database connections, blocks new ones, and
  cannot race an automation/manual tool launch.

### Thumbnail cache

- Thumbnails are generated on demand in exactly 300, 600, and 1200 pixel WebP
  tiers keyed by content MD5 (path hash fallback). They are derived, never
  included in backup, and safe to clear. Same-key concurrent requests share one
  of a fixed set of generation locks, versioned responses are immutable in the
  browser cache, and automatic pruning runs outside the thumbnail response path.
  A missing portable `ffmpeg.exe` produces an actionable log entry rather than
  silently degrading video previews.
- Settings shows per-tier counts, stale-file count, and total bytes; users can
  set a 2/5/10/20/50 GB limit, remove legacy/unindexed entries, or clear all.
  Automatic oldest-first pruning enforces the configured limit periodically.

### Automated regression net

The following files exist in the current tree. This section records coverage
intent, not a claim that the suite currently passes; a clean baseline requires
separate authorization and execution.

- `tests/snapshots/images.json` is the golden master for `/api/images` over an
  isolated fixed library, including General versus Unrated behavior.
- `tests/snapshots/openapi.json` is generated from `app.openapi()` and catches
  accidental endpoint or response-schema removal.
- `tests/test_acquisition.py` protects download-sidecar normalization,
  external-folder orphan resolution, offline-root cleanup safety, and
  credential redaction/encryption.
- `tests/test_automation.py` protects stat-signature change detection,
  unavailable-root safety, and the single incremental watcher path;
  `tests/test_tag_history.py` protects rebuild-proof
  removed-tag recording.
- `tests/test_storage_layout.py`, `tests/test_beta_import.py`,
  `tests/test_folder_roots.py`, `tests/test_folder_removal.py`,
  `tests/test_backup_bundle.py`, `tests/test_security.py`, and
  `tests/test_local_recovery.py` protect non-destructive sidecar migration,
  duplicate-name registration and stable-ID relocation, resumable local phases
  and Phase 3 results, counted root removal, verified restore/rollback,
  same-origin loopback access, rotating user checkpoints, and external-image safety.
- `tests/test_tool_progress.py` protects the structured filename/result protocol
  consumed by the Phase 3 Settings progress card, incremental result delivery,
  and the bounded 250-result/100-line in-memory tails used by long imports.
- `tests/test_thumbnails.py` protects all three cache tiers and stale cleanup.
- `tests/test_home_discovery.py` protects landscape-first Home candidate
  ranking, daily rotation across all three Home discovery surfaces, and the
  five-thumbnail timed-progress Spotlight contract. It also protects
  keyboard-focus lane pausing and focus release before ImageDetail.
- `tests/test_settings_motion_contract.py` protects the visible Browsing and
  Display summary names plus the motion-aware smooth search jump, short
  highlight, and repeat-highlight cleanup.
- `tests/test_karaoke_module.py` and `tests/test_karaoke_acquisition.py`
  protect descriptor/storage containment, additive precious tables, lyrics,
  plan confirmation, resumable acquisition, Files references, and ranged
  playback.
- `tests/test_youtube_module.py` and `tests/test_yt_dlp_service.py` protect
  strict provider identity, resolution-first actual format selection, manual/
  automatic caption labels, no-shell bounded process execution, cancellation,
  receipts, and Files publication.
- `tests/test_karaoke_youtube_frontend_contract.py` protects both surface
  registrations, Mouse-1/player/lyrics controls, local-only playback, saved
  YouTube defaults, Kara.moe fallback handoff, and Files-identity Add to
  Karaoke.
- `tests/test_manga_module.py`, `tests/test_manga_browse_paging.py`, and
  `tests/test_manga_reader_pages.py` protect the Manayomi surface/toolbar,
  language badges, blacklist paging, search, scan, favorite preservation,
  verified moved-root rebasing, browse paging, CBZ ordering, and reader cache.
- `tests/test_regression_fixes.py` protects relation-chain refresh, collection
  validation, safe config startup/defaulting, helper exit codes, and port-conflict
  detection; adjacent suites cover EXIF-noise suppression, bounded locks,
  legacy-favorite deduplication, restore quiescence, and old-schema relocation.
---

## Regression Checklist

Run the items that match what you touched. This is the "did I lose a feature"
gate, distilled from past breakages.

**Any feature change**

- [ ] All layers updated: backend models → queries/filters → migrations or
      backfills → helper scripts → `frontend/src/lib/api.ts` types → Svelte
      stores/components/menus/chips.
- [ ] The initiating view updates immediately (local state first); other views
      reconcile via the right refresh token.
- [ ] `python -m compileall -q .\backend .\scripts .\app.py`
- [ ] `.venv\Scripts\python.exe -m unittest discover -s tests -v`
- [ ] `npm.cmd run check` and `npm.cmd run build` in `frontend/`.
- [ ] App restarted and the changed flow exercised in the browser at
      `http://localhost:53325/`.

**Application shell / distribution changes**

- [ ] `python app.py --version` and `python app.py --portable-check` report the
      current version (see `backend/product.py`), bundled frontend and
      folder-picker availability, and external writable paths.
- [ ] Normal source launch remains loopback-only; `run-lan.local.bat` prints and
      serves only the detected private IPv4 adapter; ordinary source and frozen
      launchers reject `--lan`; foreign Host and Origin values remain rejected.
- [ ] Browser title, favicon, web manifest, suite drawer logo, API title/version,
      branded source-console title/icon, and executable identity agree on
      `Keivotos - Danbooru`.
- [ ] An isolated `KEIVOTOS_HOME` keeps databases, work files, runtime config,
      and backups out of the source or packaged application directory.
- [ ] Windows packaging keeps gallery-dl and FFmpeg separate and includes
      project/dependency notices, user docs, a ZIP, and a SHA-256 checksum.

**Search/filter changes**

- [ ] New filter wired through: search parsing → API params → visible filter
      chips → random-image behavior (if relevant) → sorting (if requested).
- [ ] Existing prefixes in the inventory above still parse.
- [ ] Search Help modal updated to match.

**Settings changes**

- [ ] Persisted via `persistedWritable` with a normalizer if it should survive
      restart; listed in the Settings modal; added to the persistence contract
      above.

**Schema / metadata changes**

- [ ] Additive migration in `database.py`; existing data migrated or backfilled
      when practical; `user.sqlite` tables never recreated.
- [ ] Sidecar-writing changes archive old sidecars instead of destroying them.

**UI changes**

- [ ] Top bar order and icon-only convention preserved; avatar stays far
      top-right; no duplicated controls introduced.
- [ ] Burger opens the app drawer; the dedicated library-sidebar chevron only
      appears on Browse/Tags and still restores the persisted sidebar state.
- [ ] Sidebar motion is exercised over time: open, close, rapid reversal,
      drag, delayed reveal, hover return, saved position, and overflow scroll.
- [ ] Every `viewMode` still reachable; ImageDetail still opens from the
      surfaces listed above.

**Karaoke / YouTube changes**

- [x] Search or inspection creates no media bytes; the exact plan and
      authorization confirmation precede every transfer.
- [x] The neutral player uses a large center play/pause button; non-control
      background click toggles overlay visibility and pointer movement reveals
      controls. Idle hide waits three seconds,
      controls remain clickable, closing a queue/settings/panel overlay resumes
      the idle timer, the pluggable Subtitles & lyrics panel opens
      independently, and keyboard, fullscreen, PiP, native track identity,
      offset, visibly labelled repeat/shuffle state, quality variants, and
      saved-position events remain available.
- [x] Karaoke cue reads normalize Kara.moe's JSON token arrays and preserved
      Python-representation token arrays into plain timed text without
      rewriting the existing library database; the native VTT URL is generated
      from those normalized cues.
- [x] Karaoke starts at zero, both module queues are manual, and update/replace
      downloads publish clean versioned copies without deleting older media.
- [x] Provider media and thumbnails are never hotlinked into the player;
      completed local endpoints support ranges and reject traversal.
- [x] Kara.moe → YouTube carries the query/intent, and YouTube → Karaoke uses
      published Files identity rather than cross-reading private storage.

**Languages changes**

- [x] Page load and Settings use cached/local state only; Anki probe, preview,
      and import remain explicit user actions behind the read-action allowlist.
- [x] Manual words, overrides, notes, favorites, lists, profiles, media
      associations, and practice remain in additive precious tables; removal
      retires records instead of deleting authored history.
- [x] A confirmed duplicate merge preserves authored fields, notes, favorite,
      list membership, and media, with authored media taking precedence.
- [x] Local media is create-only and range-served; the frontend renders no
      remote Anki media URL.
- [x] Word wall, Browser/inspector, Hangul Atlas, filters, paging/infinite
      mode, detail/composer, Today, Sentences, Grammar, Decks, selection/bulk,
      and all four local practice modes remain reachable.
- [x] Analyzer morphology and romanization stay local; pasted text is retained
      only by explicit save, saved retirement is non-destructive, and KRDICT
      remains an explicit fixed-host lookup with independent protected key.

**Manayomi changes**

- [x] Root relocation first verifies every indexed file under the resolved
      destination and requires confirmation; it changes index/root paths only
      and never moves or deletes CBZ media. On Linux, explicit relocation can
      interpret a saved absolute Windows root; it rejects outside-root and
      parent-traversal paths before verifying the Linux destination.
- [x] Favorites, pins, categories, module settings, and registered roots remain
      in the existing module user database; migrations are additive.
- [x] Library blacklist filtering occurs before total/page calculation and never
      produces blacked-out cards; only Browse's shown-blacklisted cards name
      the matching tags and use the reveal-then-open interaction.
- [x] Library and Browse language badges remain lower-right and normalize
      Japanese, English, and Chinese to JP, EN, and CN.
- [x] Exercise top toolbar layout, Filter expansion, blacklist reveal, and
      language filters/badges at desktop and narrow browser widths.
- [x] Preserve the first local-added timestamp outside the disposable index;
      shared filter-sheet, provider/Files actions, progress lifetime, and
      Library/Browse blacklist contracts have focused regression coverage.
- [x] Keep Downloads at the right edge with a latest-download dropdown; source
      the complete HeH Tags directory from downloaded metadata with exact local
      counts, and preserve reader resume/history in additive user state.
- [x] Exercise the live touch reader at a narrow browser width; its source,
      CBZ ordering, and cached-page contracts are covered automatically.
- [x] Keep phone section navigation and Library/Browse controls compact; expose
      all downloaded tags through sticky search and downward columns; keep the
      detail summary/actions in the first viewport with an expandable tag wall.

**Smoke pass (after any nontrivial change)** — open each: Home, Browse with a
mixed search (`character:x -y rating:g phone score:>10`), an image's
ImageDetail (zoom, favorite, user tag), Favorites, a Collection, a tag page
with wiki + banner, Popularity, Timelapse (simple), Daily Challenge, Profile
(focused artist panel), Settings. Each should render and respond without
console errors.

---

## Ideas Not Yet Adopted (evaluated, deliberately optional)

Recorded so future sessions don't re-research them; adopt when the pain
justifies it.

- **A small E2E smoke script** driving the browser through the smoke pass
  above; for agent-driven development, top-heavy E2E catches cross-file
  regressions that unit checks miss.

## Maintaining This File

Keep entries as behavior contracts, not implementation notes. When a feature is
scrapped, record the final decision (here and in `CHANGELOG.md`), don't just
delete the row. If an agent repeatedly breaks something that isn't listed here,
that's the signal to add it.
