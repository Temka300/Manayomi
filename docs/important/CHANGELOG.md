# Manayomi Updates

## Current experimental update

- Keep edited and cleared Library tag filters when switching sections or returning from Settings; apply each manga-detail tag click only once.
- Place the manga-information close button at the left of the title in both local/nHentai and MangaDex panels.

- Export local nHentai manga IDs as a six-digit text list, import named lists in Manayomi Settings, and include those lists in Browse's Hide downloaded filter with individual removal controls.

- Manayomi is a first-class optional surface in the current Keivotos descriptor registry; it keeps the established `modules/manga` storage and `/api/manga` routes.
- Manga roots can be relocated only after a read-only preview proves every indexed CBZ exists under the new root. Applying the relocation atomically rebases the index and root record; it never moves or deletes media.
- The Library toolbar keeps the sidebar, Filter, search, sort, and language controls together above the grid. Local and Browse covers show normalized JP, EN, and CN badges at lower right.
- Blacklist matching is applied by the backend before totals and paging. When ignored works are explicitly shown, their cards are darkened and name the matching blacklist tags.

---

# Shared Keivotos Changelog

This file records the useful product history for Danbooru. Keep it concise and update it when a feature or UX direction is important for future work.

## Current Direction

- Danbooru is a local-first gallery app for a personal image library.
- The user prefers direct implementation for versioned requests, followed by frontend checks, build, server restart, and in-app browser verification.
- The app should show changes immediately after user actions where practical, without requiring refresh or leaving/re-entering ImageDetail.
- UI should stay practical and compact. Avoid adding controls just because a reference app has them.
- Regression tests and release documentation are compatibility contracts: read
  them before feature work, update them with intentional changes, and run the
  matching checks so existing behavior is not lost.

## Files info panel metadata (implemented locally; not yet released)

- Replaced the tall no-preview fallback with the type glyph already present in
  the panel header, keeping the full inline preview only for supported media.
- Kept Origin first, added its Annotated-on date, and replaced the old Facts
  block with a Details section containing format, preview-derived image/video
  dimensions, size, modified time, first-indexed Added time, MD5, and the
  click-to-copy path. Dates pair an absolute value with a relative label.
- Made Origin, Details, and archive Contents collapsible with remembered
  per-browser state. Opening an Origin workflow or archive listing reopens the
  relevant section.
- Changed `GET /api/files/info` to return `indexed_at` alongside the optional
  annotation, including for files with no Origin note. Rescans retain the first
  indexed time. No media, user metadata, or sidecars are rewritten.

## Local media and Reddit usability repairs (implemented locally; not yet released)

- Karaoke now normalizes preserved Kara.moe token arrays into browser-safe VTT,
  diagnoses provider files whose size proves they are incomplete, always starts
  at zero, and uses an explicitly authored queue.
- Karaoke and YouTube update actions publish a clean versioned copy and switch
  the catalog only after completion. Older bytes are preserved and exposed
  through Files for deliberate manual cleanup.
- The shared player now has large icon controls, centered −10/play/+10
  transport, standard repeat states with a repeat-one badge, pointer reveal,
  and background-click overlay toggling.
- Reddit confirmed media runs as a background progress job visible from the
  module header after the Save-link drawer closes. Deep comment indentation is
  bounded, and pointer action menus position after mounting at the requested
  coordinates.

## Languages module (implemented locally; not yet released)

- Added the complete optional Languages module: isolated rebuildable catalog,
  additive precious authored state, versioned create-only local media and
  receipts, Files publication and non-destructive study-folder role hooks.
- Added the enabled-state-gated `/api/language/*` surface for word
  search/detail/manual creation, mirrored overrides and revert, soft retirement,
  ranged media, decks/Today, favorites, retireable lists, selection/bulk,
  local practice, settings/profiles, and full JSON export.
- Added a strict loopback-only AnkiConnect read allowlist, KO1Kv2 field
  normalization with English/Mongolian script-aware splitting, dry-run preview,
  explicit profile/duplicate confirmation, and cancellable background mirror
  jobs. Imports read notes, cards, reviews, due state, suspended/missing state,
  and media without exposing any Anki write action.
- Fixed the live `KO1Kv2+` confirmation deadlock. Compatible KO1Kv2 variants
  now validate their actual Anki fields before receiving a proposed mapping;
  unsupported models explain what is missing instead of leaving disabled
  controls. The live read-only 1,000-note preview and mapping confirmation
  passed, and the import itself was intentionally not started.
- Added preservation-first manual-to-mirrored merge behavior. The manual source
  record retires with its merge target while authored fields, private notes,
  favorites, list membership, and user media survive; authored media wins over
  mirrored media on the effective word.
- Added the original Languages drawer icon and complete Svelte surface:
  English-first/Mongolian-second word wall, search/filter/sort, paging or
  infinite append, table mode, Today/Sentences/Grammar/Decks, detail overlay,
  right-side composer, favorites/lists/selection/bulk, and four local
  self-graded practice modes with missed-word replay.
- Expanded the Languages library with accessible three-dot actions, explicit
  Korean/English/Mongolian alphabetical sorts, a dense Anki-style Browser with
  sortable audit columns and inspector, and the original mastery-tinted Hangul
  Atlas grouped by initial consonant.
- Added an original Mirinae-like Analyzer experience powered locally by Kiwi:
  sentence splitting, morphemes, compound lemmas, POS labels, deterministic
  grammar explanations, Revised Romanization, a horizontally scrollable token
  rail, exact Anki/manual meaning and example matches, optional system speech,
  and provenance on every enrichment source.
- Added explicit soft-retired Analyzer history in precious `user.sqlite`,
  disposable analysis/dictionary caches, and an optional DPAPI-protected
  KRDICT key. Dictionary traffic occurs only from the selected-token lookup
  button, targets the official fixed host with timeout/size bounds, and never
  runs during page load or ordinary analysis.
- Added locked `kiwipiepy`/model, `koroman`, and their runtime dependencies,
  plus PyInstaller native/model collection and complete dependency-license
  collection. No package or release artifact was produced.
- Added the searchable Languages Settings category for explicit Anki connection
  and profile controls, DPAPI-protected optional key, local storage/Files
  status, export, grid/page size, and audio autoplay. Opening the module or
  Settings performs no Anki request.
- Integrated the Analyzer into Keivotos' dark visual language while retaining
  local Kiwi morphology, editable English/Mongolian sentence meanings, and
  explicit provenance for every enrichment source.
- Added a Korean target/English-Mongolian meaning-order profile, practice
  totals, accuracy, daily activity, current streak and per-word results; Today
  now starts local practice without changing Anki scheduling.
- Moved Sentences and Grammar filtering and paging to the backend, replaced
  native list naming with a focus-trapped dialog, and added saved filters,
  clear-all, readable mastery labels, touch-visible actions, context menus, and
  actionable empty states.
- Initial implementation verification used a stub Anki client. The isolated
  browser pass created
  a manual Korean word, copied/rendered local SVG media, exercised
  search/table/infinite/selection/cloze/favorite/settings/sync-boundary flows,
  and found no console/server errors. A later user-requested live read-only
  Anki probe/preview verified `KO1Kv2+`; no import, version bump, package,
  release, or Git operation was performed.

## Karaoke and YouTube modules (implemented locally; not yet released)

- Added optional Karaoke and YouTube descriptors with stable enabled-state-
  gated API prefixes, module-owned rebuildable indexes, create-only local
  libraries/staging/receipts, and declared Files publication roots.
- Added a shared guarded yt-dlp process service for source/frozen command
  resolution, invariant ignore-config/no-playlist/no-overwrite/resume/retry/
  timeout/FFmpeg arguments, shell-free finite execution, progress,
  cancellation, bounded errors, and redaction. Reddit video acquisition now
  consumes that service without changing its provider or storage policy.
- Added Kara.moe-first discovery, metadata normalization, exact one-hour
  plan/selection-hash/authorization confirmation, resumable official hardsub
  acquisition, sanitized metadata, acquisition receipts, normalized timed
  cues, and clearly labeled generated VTT/LRC derivatives.
- Added the Karaoke local library, screenshot-inspired metadata-first detail,
  favorites, playlists, playback state, create-only ASS/SSA/SRT/VTT/LRC
  attachment, and a reference-only Files import that rechecks the primary
  file's SHA-256 before playback.
- Added a shared full-screen local player with exact empty-stage Mouse-1 overlay
  toggling, three-second idle hide, center ±10/play controls, seek/buffer/
  volume/speed/captions/settings/PiP/fullscreen/queue/shuffle/repeat controls,
  keyboard and Media Session handling, a top-left lyrics drawer, native WebVTT,
  and locally bundled JASSUB/libass ASS/SSA rendering.
- Neutralized that player into a module-agnostic transport with thin Karaoke
  and YouTube wrappers, pluggable subtitle panels, module-owned accents and
  queues, stable native-track identity, visible repeat/shuffle states, narrow
  volume, quality/audio selectors, and click/tap control reveal by default.
  Closing a player overlay now restarts the three-second playing-idle timer.
- Added read-time compatibility for preserved Kara.moe cues whose token arrays
  were stored as either JSON or Python representations. Existing databases are
  not rewritten; the player now receives readable timed lyric lines.
- Added bounded YouTube yt-dlp search and inspection, strict YouTube identity,
  locally cached same-provider thumbnails, actual resolution-first format
  selection, compatible MP4 preference, optional companion audio, separate
  manual/automatic captions, exact plan details, authorization, one resumable/
  cancellable job, progress/ETA, receipts, and local-only ranged playback.
- Added an original YouTube-inspired Explore/Local library/Downloads surface
  and module Settings. Saved defaults prefill quality, compatibility, companion
  audio, and automatic-caption choices but never bypass the inspected plan or
  confirmation.
- Added explicit Kara.moe → YouTube query/intent handoff and YouTube → Karaoke
  return through published Files identity plus local subtitle bytes. Neither
  module reads the other's private database or media tree.
- Added focused backend, frontend-source, shared-process, descriptor,
  enablement, and OpenAPI regression coverage. No real Kara.moe or YouTube
  media download was performed during automated verification.
- Completed the isolated generated-media browser pass: local playback, exact
  Mouse-1 reversal, three-second auto-hide, keyboard/Escape, scrub and cue
  seek, VTT plus local JASSUB canvas, queue selection, playback/default
  persistence, module Settings, desktop/narrow layouts, Files publication, and
  YouTube-to-Karaoke return all passed with clean final console/server logs.
- Fixed the two runtime issues found by that pass: pointer movement that raced
  a hidden-control click, and duplicate undefined transcript keys that blocked
  the lyrics drawer. The final compile/check/build and all 352 tests pass.
- Restarted the main app at `localhost:54325`; the live registry exposes all
  five descriptors and preserves the prior enabled modules. Karaoke and
  YouTube remain optional until enabled from the Keivotos drawer.

## Reddit module fork (implemented locally; not yet released)

- Expanded the local archive into Home, Popular, Communities, and Profiles
  destinations with consistent narrow navigation. Communities support
  per-device favorites, history counts, additive refresh, and accessible
  three-dot/context actions; saved posts and profiles use the same action-menu
  language.
- Added bounded public-profile capture using exact preserved Arctic Shift
  post/comment search responses. Profile capture and post/community/profile
  refresh add observations without replacing prior archive evidence.
- Replaced the flattened 200-comment presentation with recursive collapsible
  branches and added score, declared-comment-count, and upvote-ratio history
  charts to post detail.
- Prevented future repeated Reddit Files aliases by converging each owner's
  identical content hash onto one readable alias. Existing aliases are
  deliberately retained.
- Fixed a saved-feed HTTP 500 caused by post-detail comment-tree code running
  inside the feed projection with undefined thread-only names. The same code now
  runs in `get_post`, and focused library/runtime tests cover feed and thread
  loading together.
- Added Reddit as the sixth Settings category. It provides persistent Save-link
  defaults for Images/GIFs, Videos, Linked files, and retrying failures, plus
  read-only archive health, jobs/activity, exact storage and Files paths,
  backend-reported safety limits, and Arctic Shift scope documentation.
- Replaced capture success based on upstream bundle counts with an indexed
  receipt. Post capture now proves the requested post exists and reports the
  database's actual archived-comment count; the saved feed also distinguishes
  that count from Reddit's point-in-time declared count.
- Added generic outbound link cards plus Images and GIFs, Videos, and
  **Linked files** selections to the Save link drawer. Capture produces an
  offline exact plan; a second explicit action confirms its count and SHA-256
  selection before any bytes are opened.
- Added bounded linked-file acquisition. Ordinary public HTTPS file responses
  use DNS/redirect/size/timeout/free-space guards; MediaFire single-file pages
  use pinned `mfget==0.1.3` as a maintained metadata resolver before Keivotos
  performs the guarded stream. Web pages, unsupported folder/page targets, and
  private/non-public endpoints remain visible links and are not installed.
- Downloaded Reddit bytes remain in the SHA-256 object store and are also
  materialized with friendly names beneath `media/library`. The Reddit
  descriptor publishes that exact root as **Reddit downloads** in the Files
  base and immediately scans it, while Files continues rejecting every
  undeclared path beneath the suite's private data home.
- Changed the default Keivotos browser origin from `localhost:52325` to
  `localhost:54325`; current launcher, Vite proxy, security/release tests, and
  user/maintainer guides agree. The origin change starts fresh browser-only
  preferences but does not move or alter any database or media.
- Added an in-app **Save link** control immediately after Reddit Refresh. Its
  240 ms right-to-left drawer accepts one post or subreddit URL and shows
  progress, errors, and a target-specific saved summary before refreshing the
  local feed and counts.
- Added serialized `POST /api/reddit/capture` and a shared direct-capture
  service used by both HTTP and CLI entry points. It retains all existing URL,
  response-byte, comment, wiki-page, timeout, retry, create-only provenance,
  and no-automatic-media-download boundaries.
- Verified the drawer in an isolated real browser with focus, validation,
  target-specific mocked success/refresh, Escape close, and a clean console.
  Also completed three bounded post captures and one subreddit-only Arctic
  Shift capture in the disposable module home without downloading media bytes.
- Completed the no-web-archive product direction: no WARC, WACZ, Wayback,
  Common Crawl, browser-capture, or replay adapter. Direct structured capture
  routes a post URL to that post plus comments and a subreddit URL to
  about/rules/wiki/image context only.
- Added Slice 5 bounded Arctic Shift direct capture with finite response,
  comment, wiki-page, timeout, retry, and wait limits. Exact structured
  responses are preserved create-only before normalization. Subreddit capture
  never calls a post/comment listing, and unavailable moderator membership is
  reported instead of inferred.
- Added schema-version-2 `comment_placeholders` observations for supplied
  Arctic Shift `kind: "more"` nodes and unresolved IDs. Older archives retain
  unknown collapsed-placeholder coverage; new direct captures report their
  observed unresolved count without claiming completeness.
- Added Slice 6 SQLite read-only/query-only library projections and CLI:
  stable keyset-cursor feeds, subreddit/author/flair filters, bounded post and
  comment FTS, post/thread detail, community snapshots and history, local-media
  references, and capture status.
- Added Slice 7 as the optional Reddit descriptor at
  `<suite-home>/modules/reddit` and the always-mounted, enabled-state-gated
  `/api/reddit/*` feed/search/post/community/status/local-media router. Media is
  hash-addressed, range-capable, contained within the module store, and never a
  remote redirect.
- Added Slice 8's original Reddit-inspired Svelte surface with optional-module
  drawer enablement, an infinite local saved-post feed, local filters and FTS
  search, observations, nested comments, community about/rules/wiki/moderators,
  and local-media-only rendering.
- Verified the integrated frontend with synthetic isolated data: 25 initial
  posts plus 5 loaded by real scrolling, comment search to thread detail,
  community detail, and no console warnings/errors. Frontend check and
  production build passed. That Slice 8-only pass issued no live request; the
  later in-app capture follow-up has its separate live-smoke evidence above.
- Added Slice 4 read-only comment-tree integrity and local JSON export over
  comments already normalized by Slice 0. Parent/child order is deterministic,
  every comment appears once, and malformed parents, cycles, duplicate
  identities, depth differences, unknown posts, removed bodies, and latest
  declared-versus-observed counts are explicit coverage instead of silent
  completeness claims.
- Missing parents become local placeholders. At Slice 4, collapsed Reddit
  `more` coverage remained unknown because the original normalized schema did
  not represent those nodes. Cycle breaks and derived depths exist only in the
  read-only projection.
- Added bounded inspect/export commands with pre-load comment limits,
  streaming output-byte limits, create-only verification, and an iterative
  encoder verified against a 1,500-level thread. That slice touched no data
  API, runtime module, frontend, user database, dependency, or Git state.
- Added Slice 3 offline community-context import for user-supplied Arctic Shift
  about, rules, and wiki JSON/JSONL/`.zst` sources plus an explicit optional
  module-owned local moderator snapshot bundle. The importer makes no network
  request and does not claim moderator completeness.
- Community records retain create-only raw provenance and deterministic
  coverage while the rebuildable index stores versioned about observations,
  ordered and empty rule snapshots, wiki revisions, and moderator snapshots.
  Global sources filter before raw preservation; scoped sources keep nonblank
  malformed and wrong-target evidence with errors.
- Recognized subreddit icon/banner URLs join the existing media queue, but no
  bytes are downloaded until the separate Slice 2 plan/confirmation boundary.
  Slice 3 added no dependency, runtime registration, frontend, `user.sqlite`
  table, or live data operation.
- Added Slice 2 bounded acquisition for media URLs already queued by local
  imports. A no-network plan reports the exact count, selection hash, and
  conservative disk requirement; the separate download command must confirm
  both the count and hash and applies finite file, byte, disk, retry, and
  timeout limits.
- Supported Reddit-hosted images use gallery-dl or a host/redirect/DNS/MIME
  checking HTTP fallback. Stored `v.redd.it` DASH/HLS/file URLs use pinned
  `yt-dlp==2026.7.4` and the existing FFmpeg resolver without revisiting a
  Reddit post or Listing API. Arbitrary external-site roles remain blocked.
- Media bytes install create-only under their SHA-256, identical downloads
  deduplicate, and create-only manifests plus started/complete/failed database
  events retain acquisition provenance. Resumable partials, invalid completed
  files, and oversized files are preserved rather than discarded. No live
  media URL, real archive, app runtime, frontend, or user database was touched.
- Added Slice 1 local Arctic Shift `.zst` ingestion. Dumps stream through
  `zstandard` with optional published SHA-256 verification, UTC date
  boundaries, scoped/global handling, target filtering before raw preservation,
  and deterministic coverage reports.
- Added bounded official Reddit OAuth Listing discovery. It follows `after`
  cursors in pages of at most 100, stops at 1,000 unique items or the real
  Listing end, observes rate-limit/retry signals, and writes only a create-only
  ID/URL manifest. Local `.zst` imports can consume that manifest to select
  discovered posts and their linked comments.
- Kept API response bodies outside the permanent archive because Reddit's
  deleted-content requirements remain incompatible with the fork's absolute
  no-delete archive rule. No live capture, large dump, media download, runtime
  module registration, or frontend work was performed for Slice 1.
- Added the offline-only Slice 0 capture foundation. A Reddit/subreddit,
  post, user, search, asset, or external URL defines a local import
  scope; JSONL and gzip JSONL stream into atomic verified raw chunks and a
  rebuildable SQLite/FTS5 post/comment index.
- Capture jobs record source provenance, post limits, comment policy, desired
  image/video/community capture settings, and allowlisted external asset URLs.
  Interrupted imports resume after the last committed source line and repeated
  resume is idempotent.
- Slice 0 performed no network acquisition, media download, application
  registration, frontend work, dependency change, or `user.sqlite` mutation.

## V1.1.2 (released 2026-07-25)

- Cycle theme: **"Files, actually browsable."** V1.1.1 gave Files an origin
  panel but left the grid as emoji icons, so a folder of models, manga, and
  PDFs still read as a list rather than a browser. Ten slices shipped: a guarded
  thumbnail endpoint, real grid thumbnails, folder covers drawn from a subtree,
  origin attachments as the tile face, a per-module grid size control, a
  resizable info panel led by Origin rather than by file facts,
  copy-origin-from-another-file, a read-only archive listing, and the cleanups
  the `core.py` extraction surfaced. The client-side URL router moved to V1.1.3
  so that navigation-state rewiring gets its own focused cycle.
- **The cycle added no new runtime dependency**, deliberately. Everything that
  needs an engine — PDF, epub and cbz covers — was deferred to V1.1.3 so this
  release carried no packaging or licensing risk.
- Two things were tried and reversed inside the cycle, both recorded rather than
  quietly dropped: a 1250px cap on the browse row (it stranded a dead band to
  the right of the panel on a wide display, and the resizable panel solves the
  same problem without waste), and a planned shared thumbnail service (
  `backend/thumbnails.py` was already path-based and content-keyed, so there was
  nothing to extract).
- The "dead compatibility aliases" cleanup found almost nothing: a mechanical
  scan of every public function in `backend/` surfaced exactly one genuinely
  unreferenced name. The other 84 candidates were FastAPI route handlers and
  middleware, bound by decorator and only *appearing* unused.

## V1.1.1 (released 2026-07-25, version bump `75789b2`)

- Fixed moving an image to another folder. The code that carries a file's
  sidecars along with it referenced a suffix list that was never defined
  anywhere, so a single move failed outright and a bulk move silently reported
  every image as failed. The sidecar pair is now named once in the module that
  owns sidecar paths, where it had been duplicated as a default argument, and a
  regression test moves a real file with both sidecars against throwaway
  fixtures. Found by a mechanical inventory of what each router takes from the
  shared compatibility module.
- Began replacing the routers' wildcard `core` imports with explicit ones,
  smallest first. `stats.py` now names exactly what it uses and takes each name
  from its real owner where one already exists; the objects it binds are
  identical to what the wildcard gave it, so behavior is unchanged. Eight
  routers remain, and the full per-router inventory of the 233 remaining
  name-uses is recorded to drive them.
- Started giving Danbooru a real backend boundary rather than only shrinking a
  file. Its HTTP client, post-relation lookups, tag wiki, user-tag listing,
  artist profile archive and artist follows now live in `modules/danbooru/`;
  genuinely shared helpers went to `services/`. `core.py` fell from 3,231 to
  1,988 lines, and the tags, artists and stats domains are finished end to end —
  their code sits in the module and their routers no longer touch the facade.
  Every move was made programmatically and checked to be byte-identical, with
  each moved name confirmed to still be the same object the wildcard exported,
  so no behavior changed.
- Fixed a second latent crash found by that work: the bundled gallery-dl lookup
  located itself with a path relative to its own file, which quietly assumed the
  code sat one directory below the project root. Moving it broke the lookup; it
  now resolves against the authoritative code root instead, and its test pins
  that seam rather than the old mechanism.

- Began the Files info panel. Clicking a file opens a right-side panel with a
  type-aware preview (images, mp4/webm, audio, PDF via the browser's own viewer,
  and capped text/subtitles render inline; MIDI, archives, 3D models, and office
  formats show a type icon), file facts, and an Open / Show-in-folder pair. There
  is deliberately no in-app 3D viewer — user-added screenshots are the intended
  way to preview a model, and outlast a deleted store page.
- Added user-authored origin info stored in `user.sqlite`: a description and any
  number of labeled links (source, discussion where it was found, mirror, author,
  other) per file or folder. A file's note is keyed by content hash, so it
  follows a rename or move and is shared by byte-identical copies; a folder's is
  keyed by path. The file is hashed once, on the save that first enriches it. A
  moved file's note is dormant until the file is re-hashed, never lost.
- Added guarded file serving as the base's one security-sensitive surface. The
  endpoint takes a source plus a relative path (never an absolute one),
  canonicalizes it, requires it to stay inside a registered source, rejects
  traversal and symlink escape, denies the suite's own data tree, and forces
  active types like html/svg to download with `nosniff` so a served file cannot
  script the local API. Range requests are supported so video and audio seek.
- Added image/video attachments to origin notes. Bytes are stored
  content-addressed inside the first registered Files folder
  (`<root>/.keivotos/attachments/`), so a screenshot outlives a deleted store
  page and rides the user's own disk backups; that directory is excluded from the
  Files scan. Uploads go through the raw request body (no multipart dependency),
  identical files are de-duplicated, and the bytes are removed only when the last
  reference is deleted. Deleting the last piece of a note prunes the now-empty
  note so tile badges stay truthful.
- Made attachment bytes an opt-in `.keivotosbk` backup component. The bundle
  carries them by content hash from wherever they live, and restore re-creates
  any missing ones back into their folder additively — create-only, after the
  atomic metadata restore, and entirely outside the fragile metadata-tree
  rollback path — so a screenshot survives even if the source folder is lost. It
  never overwrites a file already present.
- Removed `backend/core.py`. It was a 3,231-line module that every domain router
  imported wholesale with `from core import *`, which is how a missing name could
  sit in a shipped feature without anything noticing. Its behavior moved out one
  domain at a time — search, tag wiki, tools, artist profiles and follows, image
  activity and queries, path and media helpers, the tool runner — into the
  Danbooru module or a shared service, and the FastAPI app and startup moved to
  `app_factory.py` and `lifecycle.py`. Each router then named exactly what it
  uses. With nothing left importing it, the file was deleted.
  Throughout, every moved name was checked to still be the same object, the moved
  source checked byte-identical, and the OpenAPI snapshot never changed.

- Files info panel slices landed: the annotation store, guarded serving, the info
  API (with lazy hash-on-annotate and http/https-only links), the read-only
  panel, the origin editor with note badges, image/video attachments, and the
  attachment backup component.

## V1.1.0 (2026-07-23)

- Added the Files base, an always-on neutral file layer that indexes folders in
  place and authors no metadata of its own. It scans, browses and searches every
  file type into a disposable `files.sqlite`, marks missing files rather than
  deleting them, and finds duplicates by lazily hashing only size-colliding
  candidates in bounded batches. Registered folders live in the shared
  `user.sqlite`; originals on disk are never moved or touched.
- Replaced the single global module slug with a per-module descriptor and a
  static registry. Each module declares its own slug, name, home, database,
  credentials, API prefix, log prefix and user agent, plus the hooks the shell
  calls to publish, adopt and release folders. Files is a descriptor too: the
  always-on base, which cannot be disabled. Registering a module is one import,
  so removing one means deleting its package and a single line.
- Made a folder's role an editable assignment rather than a label. Assigning a
  folder to a module hands it over; assigning it back to the base releases it.
  Release is non-destructive, so Danbooru un-indexes the folder but keeps its
  sidecars and re-adopting is cheap. Only an explicit forget removes a folder
  from the registry, and nested registered folders keep their ownership across
  rescans and return their files to the parent when forgotten.
- Added Manage folders, where the whole registry is edited behind one Save:
  rename, show or hide in the sidebar, reassign a module, or forget. The draft
  is validated in full before any of it is applied, so a rejected change mutates
  nothing. Subfolders can only be chosen inside registered roots, never drives
  or This PC. Adding a folder from the sidebar now goes through that same
  validation, so a folder that is already registered is reported instead of
  being silently accepted.
- Rebuilt the app shell around the registry. Keivotos boots into Files and
  switches surfaces by module slug instead of branching on a module name. The
  drawer lists every registered module with its enabled state, toggles the
  optional ones, and renders the base identically to the rest. Files carries one
  compact top bar: drawer, folder icon, breadcrumb, then search sized and placed
  to match Danbooru's, with Rescan and Duplicates beside it.
- Moved suite identity off the Danbooru namespace. The window title and display
  name are Keivotos rather than Keivotos - Danbooru, and logs are written as
  `keivotos-runtime-*` and `keivotos-access-*` because they cover every route
  including the base. Browser storage moved from the `danbooru:` prefix to
  `keivotos:`, migrating the old prefix on load. Module-owned identity moved to
  the module: the display name and the scraper user agent now come from the
  Danbooru descriptor.
- Reworked where suite data lives. `user.sqlite` is promoted to the suite root
  because every module shares it, legacy module backups are copied and verified
  into the suite backup directory with the originals preserved, and portable
  mode became opt-in through a `portable.txt` marker beside the executable, with
  `%LOCALAPPDATA%\Keivotos` as the default home. The Documents to Local AppData
  migration was retired.
- Separated suite startup from module startup. Promoting and checkpointing the
  user database always run; Danbooru's sidecar migration and auto-ingest watcher
  run only when the module is enabled, so the app boots without them. Folder
  reconciliation iterates the registry and calls each descriptor's publish hook,
  and the suite now starts even when the Danbooru module is absent from the
  registry entirely.
- Added `/api/files` and `/api/suite`, covering sources, browse, search, scan,
  hash, duplicates, filesystem listing and the native folder picker, plus the
  module registry and the batched folder apply. Removed the superseded
  single-source removal route, which predated folder roles and would have
  dropped a module-owned folder without calling that module's release hook.
- Added a GitHub Actions workflow running the compile check, the test suite and
  the frontend checks on every push, on Windows because that is what Keivotos
  ships. Marked `frontend/dist` and `tests/snapshots` as generated so they stay
  out of language statistics and collapse in diffs.

## V1.0.0 Pre-release 5 (2026-07-18)

- Renamed the active module identity to Danbooru across writable-data defaults,
  backups, dated logs, backup manifests, browser-local settings, branding
  masters, launch configuration, tests, and current-facing documentation. New
  module data lives under `modules/danbooru`; startup copies and verifies a
  configured prior module tree before rebasing its paths, preserves the source,
  and copies known browser preferences into the `danbooru:` namespace without
  deleting their original values.
- Replaced the hardcoded local Profile name with `Keivotos` as the clean-install
  default and added one inline edit surface. Confirmed names are trimmed,
  limited to 40 characters, and stored in the additive `user_settings` table in
  `user.sqlite`, so they travel with metadata backups. Existing browser-local
  names migrate once through the settings API; blank names return to the
  Keivotos default. A focused bundle roundtrip now proves a changed profile
  name is restored from the backed-up user database.
- Aligned the current identity at V1.0.0 Pre-release 5 and added one strict
  version command for runtime, Python/frontend package metadata and lockfiles,
  Windows resources, and OpenAPI. Centralized frontend product names and visible
  component labels while freezing the existing `waifu-hoard:` preference
  namespace, made release tests derive from product constants and reject
  duplicated component labels, and made Windows builds derive and validate
  their artifact version while resolving uv by full path.
- Kept the Python lockfile in lockstep with the version command and fixed the
  packaging script to read the product version across CRLF line endings, so the
  portable build derives its artifact name from a single source. The
  V1.0.0 Pre-release 5 portable archive now builds and passes its packaged
  smoke test end to end (frontend, backend, folder picker, gallery-dl, and
  ffmpeg all verified against a throwaway data home).
- Branded the source launcher window with the Keivotos icon and the
  `Keivotos - Waifu-Hoard` title, and standardized the browser/launcher identity
  on a normal hyphen while retaining visible setup, runtime, LAN, and error
  output.
- Removed the current GitHub Actions CI and Windows-package workflows after
  their initial validation setup proved premature. Source checks and portable
  packaging remain available locally; hosted automation is deferred to a future
  release.
- Restricted trusted-network access to an ignored maintainer launcher and a
  local developer marker. LAN runs bind only the detected private adapter;
  ordinary source startup and every portable executable reject `--lan` and
  remain loopback-only.
- Moved the default writable suite home from Documents to Windows Local AppData.
  Normal startup copies and verifies an existing `Documents\Keivotos` tree,
  rebases only its internal suite paths, installs the completed copy atomically,
  and preserves the entire Documents original.
- Fixed manual backups at `%LOCALAPPDATA%\Keivotos\backups\waifu-hoard`, removed
  the destination editor, and adopted `backup_<Unix timestamp>.keivotosbk`
  while retaining listing and restore compatibility for `.whbackup` files.
  Retired the ignored `backup_destination` runtime key instead of implying that
  backups can move away from the fixed suite location.
- Rejected filesystem roots and Keivotos-generated storage during library-root
  registration and relocation without blocking ordinary external image folders.
- Fixed the Windows release cleanup boundary so prefix-sharing sibling paths
  are rejected before any deletion. Bundled Uvicorn's dynamically imported
  runtime modules and made packaging start the staged executable with an
  isolated home and require a successful HTTP response before creating a ZIP.
- Restored the Waifu-Hoard sidebar entry animation lost in the Beta4
  persistent-panel rewrite: the dock now renders one closed frame on mount and
  opens on the next rendered frame, so the 280ms slide plays when entering
  Browse or Tags. The panel remains one persistent instance; toggle behavior,
  grip, and saved position are unchanged. Live diagnosis confirmed the toggle
  transition itself was intact — only the entry animation was missing.
- Replaced the reused `keivotos.log` with timestamped, module-specific runtime
  and HTTP access logs. Successful read traffic now stays in the access log,
  while the runtime log keeps startup, mutations, failed reads, background
  work, warnings, and errors visible; Settings shows both exact dated paths and
  states what each file contains.
- Restored Waifu-Hoard's Beta3 profile avatar to the top-right user control,
  drawer Profile entry, and local profile fallback while keeping the angular
  Keivotos mark exclusive to suite-owned branding. Restored Settings to a
  vertically scrollable left-side section rail with its active transitions,
  kept the concise Display name, removed repeated section/row copy and the
  decorative fake preview, replaced signature panels with factual current-value
  summaries, and changed Browse sort to the same single reversible arrow used
  by the top-bar filter. Settings search now ranks direct control matches first,
  explains each result, smoothly centers the selected control unless reduced
  motion is active, and applies the gentler short highlight from Pre-release 1.
  Browsing and Display now name themselves inside their colored summaries.
- Restored reliable motion to Home's **From your library** lanes by keeping
  their normal running state explicit and restoring independent pause for both
  pointer hover and keyboard focus. Opening a lane image releases its focus
  before ImageDetail appears, so returning cannot leave that lane frozen; the
  original speeds, directions, seamless loops, and reduced-motion fallback
  remain unchanged.
- Silenced Pillow's harmless corrupt-EXIF warning only during index dimension
  reads while preserving successful indexing and real per-file failures.
- Preserved multi-level Danbooru relation chains during refresh, rejected blank
  collection names and missing-collection membership edits cleanly, deduplicated
  legacy favorite matches, and made Timelapse sampling application-memory bounded.
- Made malformed runtime JSON fail with a clear persistent startup diagnostic,
  defaulted invalid numeric settings safely, logged port/tool failures, preferred
  bundled portable helpers, and removed personal scan-folder fallbacks.
- Serialized tool state and backup/restore/automation starts, made restore wait
  for in-flight database connections, bounded thumbnail generation locks, and
  reduced watcher/relocation filesystem-memory overhead.
- Removed unreachable duplicate auto-merge/disk-delete models and helpers while
  preserving grid duplicate review, excluded local absolute paths from metadata
  backups, and ignored root-level portable build outputs plus the local logo
  reference screenshot.

## V1.0.0 (2026-07-15)

- Replaced every shipped Keivotos suite mark with the new angular logo while
  preserving Waifu-Hoard's original module logo in its top bar and Keivotos
  drawer entry. Made the transparent SVG the canonical Keivotos source and
  regenerated the favicon, web icon, Windows icon, profile banner, wordmark,
  banner, and social preview.
- Changed the default browser origin to `http://localhost:52325`. Browser-only
  preferences and challenge progress begin fresh on the new origin; SQLite,
  sidecars, roots, favorites, collections, and original media are unaffected.
- Recorded `backend/core.py` as an incremental extraction boundary rather than
  a rewrite target, and kept a Windows installer explicitly deferred/unlikely;
  the one-folder portable executable remains the supported Windows package.
- Restricted the local HTTP API to loopback binding, loopback Host headers,
  and the exact active Keivotos browser origin; removed wildcard CORS.
- Resolved the writable suite home through the Windows Documents Known Folder
  API so redirected Documents locations work, and added rotating persistent
  logs under `Documents\Keivotos\logs` with the exact path shown in Settings.
- Made registered roots stable-ID based: equal leaf names on different paths or
  drives can coexist, filters/move targets distinguish their locations, and a
  native-picker **Relocate** action preserves `root_id` and canonical sidecars
  while rewriting index, manifest, ingest, and user-data paths.
- Kept `.whbackup` metadata-only and made credential exclusion explicit in its
  manifest: originals, thumbnails, and DPAPI credential files are never packed.
- Established Keivotos as the suite identity and Waifu-Hoard as its first
  module. Added an original suite logo and complete icon, favicon, Windows,
  banner, wordmark, and social-preview asset set; aligned the browser, API,
  console, manifest, and drawer titles.
- Moved every default writable path out of the source/application folder into
  the Windows-known `Documents/Keivotos` location, with databases, sidecars, thumbnails, recovery,
  library, and gallery-dl directly under the Waifu-Hoard module directory plus
  a suite-level backup location. The obsolete extra `metadata/` wrapper is
  flattened safely on startup without overwriting conflicts. Runtime overrides now live outside the checkout, and
  `KEIVOTOS_HOME` supports isolated CI and test runs.
- Replaced source-only subprocess launch assumptions with one entry point that
  also supports frozen uvicorn, import-pipeline, folder-picker, version, and
  portable-resource modes.
- Added locked Python packaging metadata, source bootstrap, a PyInstaller
  one-folder specification, separate gallery-dl/FFmpeg tools, dependency notice
  collection, checksums, and a local artifact-building workflow.
- Made the frozen launcher collect and import the backend composition root
  directly, resolve bundled frontend assets from the shared resource root, and
  fail the portable check when the packaged backend cannot serve its root route.
- Fixed the portable Library Browse button to resolve its packaged helper from
  the shared resource root and use the native Windows `IFileOpenDialog`
  exclusively, without an unavailable tkinter fallback. Portable checks now
  also verify that the folder-picker helper is present.
- Restored Home's three moving discovery rows for small libraries by reusing
  spotlight/card images only when no unassigned lane alternatives exist.
- Made manual backup completion visible inside the backup card with the exact
  created filename, size, and destination, preventing accidental repeat clicks.
- Added the Tags-style chevron breadcrumb back to Home in Challenges,
  Popularity, and Timelapse.
- Added a professional public documentation and contribution surface: source
  and portable installation/build guides, data-layout/troubleshooting docs,
  issue/PR templates, security/support/conduct policies, and FOSS notices.
- Removed the disposable repository-local V0.0.1 test store instead of
  migrating it. External registered media is outside that removal boundary.

## V1.0.0 Beta 6 (2026-07-15)

- Made normal launches skip unchanged Python dependency sync, kept schema setup
  authoritative in the app lifespan, and moved recovery/legacy-sidecar work
  behind server readiness. A successful legacy-sidecar pass is now recorded so
  later restarts do not rescan every indexed media path.
- Extended deterministic daily Home discovery to Spotlight, the actual image
  windows in **From your library**, and Tag-neighborhood covers/tag lists. The
  next local-midnight change happens without requiring a page reload.
- Added stale-while-revalidate Browse/Tags page memory, cancellation of replaced
  requests, lazy bulk-menu data, batch favorites/membership/move/delete APIs,
  page-scoped favorite metadata, one-query collection previews, and one-pass
  normal tag count/pagination.
- Preserved the existing Settings blur while pausing background animation before
  mount through one CSS presentation state; videos no longer require a scan of
  every browser animation. Section-owned Settings data remains lazy, and the
  modal now loads as an idle-preloaded code split instead of inflating the
  initial app bundle (about 20% less initial JavaScript in the Beta 6 build).
- Serialized same-key thumbnail generation, moved periodic cache pruning off the
  response path, and made versioned thumbnail responses immutable in the browser.
- Reduced `backend/core.py` by moving Home discovery/cache, Daily Challenge, and
  shared rating/user-file identity logic into `backend/services/`, retaining
  `core.py` as the router compatibility facade. Added `Server-Timing` response
  headers for repeatable API performance checks.
- Made backup/restore staging deterministic and crash-recoverable under the
  existing process lock, and made tag-history tests use the active configured
  user database instead of an import-time path. The full backend suite is now
  clean at 46/46.

## V1.0.0 Beta 5 (2026-07-15)

- Balanced Daily Spotlight across Characters, Copyright, Artists, and General
  Tags with deterministic daily picks. Removed the local-path count, made the
  hero artwork open ImageDetail, renamed the Copyright moving lane, and reduced
  the lower discovery section to the single **Tag neighborhoods** heading.
- Made sidebar ratings multi-select across all five values; any combination is
  sent consistently through Browse, contextual Random, Home, Popularity,
  Timelapse, and Daily Challenge. Clearing every button continues to mean all
  ratings. Restored vertical sidebar scrolling for long library panels.
- Made ImageDetail tag clicks open the Browse search from non-Tag views while
  preserving in-section tag-info navigation when the overlay was opened from
  Tags. Open Image Location now accepts registered external library roots as
  well as the portable data root.
- Removed the tag-info Examples Expand/Hide wrapper. Missing examples are
  always-visible dashed Not-in-library cards, and remote wiki references such
  as Non-examples use the same visual treatment.
- Repaired Twitter/X profile-media archiving by resolving the gallery-dl
  executable bundled in the active venv and parsing its profile-info payload.
  Archived profile media once again opens in ImageDetail.
- Repaired followed-artist polling by applying saved Danbooru credentials,
  added persisted 5/15/30/60-minute intervals, and made **Check now** plus its
  result visible inside the notifications panel.

## V1.0.0 Beta4 (2026-07-15)

- Replaced the split-panel Spotlight with a cinematic full-bleed hero using
  Waifu-Hoard's own copy and actions. Five tag covers stay at the lower right;
  the larger center cover owns the background, a nine-second white progress
  line advances it, and the old center shrinks/moves left while the next cover
  slides into the middle and grows.
- Added Home-only cover candidate sets without changing canonical tag covers.
  Discovery ranks landscape and near-landscape images before score, rotates
  candidates daily, avoids reusing one file across Spotlight, tag
  neighborhoods, and the moving lanes when alternatives exist, and focuses
  portrait fallbacks near the upper face region instead of the body midpoint.
- Turned moving-image discovery into three borderless, independently paced
  Characters, Artists, and Series rows with larger artwork. Hover/focus pauses
  only that row while the others keep moving; reduced motion remains manually
  scrollable and the global Pause/Resume control is intentionally absent.
- Replaced the lower single-category feature with four purposeful tag
  neighborhoods below the rails. Characters, Copyrights, Artists, and General
  are visible together as compact visual leads with their strongest local tags.
- Preserved the previous Home intact as **Classic** under Settings -> Browsing
  -> Home layout. The persisted default is the new **Discovery** layout.
- Restored the draggable sidebar grip's delayed reveal on Browse/Tags entry and
  after toggling while preserving its hidden-until-hover idle state, animated
  sidebar movement, and saved vertical position. Added a regression contract so
  it cannot be replaced by the Settings fallback. The sidebar now keeps one
  persistent panel and reverses its CSS animation, eliminating the intermittent
  overlapping duplicate produced by repeated bidirectional slide mounts.
- Added local filename search: pasted complete `.jpg`/`.png`/`.webp`/`.gif`/
  `.jfif`/`.mp4`/`.webm` names work directly, while `filename:`/`file:`/`name:`
  support partial and negative matching across Browse and contextual Random.

## V1.0.0 Beta3 (2026-07-14)

- Moved generated metadata to `~/Documents/Waifu-Hoard` while leaving every
  external image at its existing path. Registered roots now have stable IDs;
  canonical sidecars use `sidecars/roots/<root-id>/<relative-path>`. Startup
  migration copies and verifies legacy sidecars and never deletes the source.
- Added manual `.whbackup` bundles with a user-selected destination, component
  switches, preflight size calculation, CRC/SQLite verification, restore-time
  staging, and a local rollback folder. Original images and thumbnails are
  always excluded. Restored automatic verified `user.sqlite` recovery
  checkpoints on startup and after successful syncs, with identical-state
  deduplication, five-slot rotation, visible status/path, and a manual
  **Checkpoint now** action.
- Removed the temporary Legacy/Beta selector and made the four-phase workflow
  the single explicit bulk import: stat-only Discover, bounded Hash & Inspect,
  confirmed Danbooru Metadata that reuses indexed MD5, and incremental Finalize.
  Folder add/rescan and the watcher now share the ordinary incremental sync.
- Moved Import pipeline and Watch for new or changed files from Library to
  Metadata, replacing the standalone Fill missing metadata and Check tag
  updates cards. **Run all four phases** now occupies the former selector
  position. Phase 3 pins the current filename and separates recent Matched,
  No match, and Failed items with exact counters; results persist in
  `ingest_state` through Finalize.
- Replaced network-capable automatic tagging with a selectable-interval,
  local-only file watcher that never invokes Danbooru. Consolidated the data
  schema and sidecar-path logic and added high-value SQLite indexes.
- Consolidated derived thumbnails to 300/600/1200 WebP tiers with a persisted
  size limit, stale cleanup, oldest-first pruning, and a Settings status panel.
  Added `scripts/benchmark_library.py` for read-only before/after query timing.
- Fixed the Library panel's import phase counter mapping so the phase controls
  remain functional, and made the frontend entry document
  non-cacheable so a rebuilt release cannot keep booting a stale JS bundle.
- Added a counted two-choice Library-root removal flow: **Un-index only** keeps
  sidecars, while **Delete sidecars & un-index** removes current central
  sidecars too. Both choices preserve external images and sidecar history, and
  removal now clears the root's resumable ingest state as well.
- Optimized the Beta3 Settings and large-import path without removing its
  blurred background or any controls: section-owned data now loads lazily,
  background motion/video pauses behind the blur, idle import polling is gone,
  active polling transfers only new file results, phase counts use one aggregate
  query, tool output/results stay bounded, and repeated backup estimates reuse
  recent component scans.

## V1.0.0 Beta2 (2026-07-14)

- Rebuilt Settings around five task-based sections: Browsing, Media & Display,
  Library, Metadata, and Safety & Recovery. Discovery was removed as a weak
  category; duplicate review and cleanup now live where their actual tasks do.
- Added a distinct functional surface per section: browsing-default summary,
  live gallery preview, library-health status, local metadata pipeline, and a
  safety-first verified-backup panel. Routine preferences, actions, status,
  warnings, and recovery tools no longer share one uniform row treatment.
- Upgraded Settings search from category filtering to individual setting
  results with section breadcrumbs, jump-to-control behavior, and a temporary
  highlight. Browsing and Media & Display also have safe per-section resets.
- Added persisted startup destination, Browse sort/order, followed-artist
  notification switch, interface motion, and interface scale preferences.
  Replaced boolean media autoplay with Never / On hover / Always while
  migrating the existing localStorage value in place.
- Moved routine Re-scan and folder roots to Library; Danbooru access, backfill,
  and tag refresh to Metadata; and manual backup/restore, cache cleanup, orphan
  cleanup, and recovery rebuild to Safety without removing the five maintenance
  tools or their data-safety confirmations.

## V1.0.0 Beta1 (2026-07-14)

- Added opt-in Library Automation. Enabling it records a timestamp baseline;
  startup and 45-second checks backfill only newer sidecar-less media, then run
  the existing incremental sync. Old library backlogs remain manual, and
  failed metadata fetches retry naturally on a later check.
- Reorganized Settings -> Library around the normal workflow: automatic
  tagging, Fill missing metadata now, and Re-scan now. Tag refresh, orphan
  cleanup, and recovery rebuild remain available in collapsed Maintenance
  without renaming the five backend tool definitions.
- Manual Update Danbooru Tags now compares archived and replacement sidecars,
  saves removed upstream tags in rebuild-proof `user.sqlite`, and displays them
  as non-searchable history at the bottom of ImageDetail.
- Protected sidecars on unavailable media roots: cleanup skips an unplugged or
  missing root and only treats a sidecar as orphaned when the root is reachable
  but its specific media file is gone.
- Added focused regression coverage for the automation baseline, removed-tag
  history, and offline-root cleanup behavior.

## V0.0.1 beta4 (2026-07-13)

- Kept tag and artist detail inside Tags. Tag cards, Home tags, Profile artist
  links, random tags, and linked wiki tags now open the in-section detail state;
  Back returns to the preserved tag-list search and Browse remains a normal grid.
- Simplified missing remote examples to one Expand/Hide control around the
  dashed Not in library example cards, without removing the visual placeholder.
- Removed the redundant title/summary strip at the top of all four Settings
  categories.
- Rebuilt Daily Challenge around quadrant reveals: top-left first, then
  top-right, bottom-left, and bottom-right after failed guesses. Guessing,
  choices, clue progression, and history now share one compact asymmetric panel.
- Unified Timelapse mode switching at the top-right with icon-only advanced/back
  controls, replaced fixed speed choices with a compact numeric slider, repaired
  fullscreen with native and in-app fallback paths, added All Images/exact-tag
  scope, and added a hover-restorable Hide UI mode.
- Limited the library sidebar to Browse and Tags. Its open-state chevron now
  lives naturally in the image/tag summary instead of covering the scrollbar;
  the closed handle retains its delayed idle fade.
- Integrated the return-to-Tags action into the tag banner as a breadcrumb,
  compacted the app drawer into consistent Waifu Hoard / Coming Soon / Profile
  rows without descriptions or the extra footer outline, and renamed the suite
  to Keivotos.
- Fixed active search chips so one middle-click removes exactly one tag instead
  of firing both `mousedown` and `auxclick` removal paths.
- Moved the closed-sidebar handle from the tag-banner corner to a subtle
  mid-edge panel grip, preventing it from covering the Tags breadcrumb while
  preserving its delayed fade and hover return.
- Unified Hide/Show Sidebar into one draggable grip with animated sidebar
  width, chevron rotation, and a persisted vertical position. Compacted the
  drawer's Profile/Settings footer to the same row density as Waifu Hoard.
- Moved that grip fully outside the library sidebar. Its small hover hotspot
  stays at the user-saved position instead of following the pointer; dragging
  relocates both. Replaced the choppy state-driven reveal with a GPU-friendly
  CSS animation and repaired the malformed pointer-events class that prevented
  clicks from toggling the sidebar.
- Matched the Keivotos app drawer to that motion language: the drawer and dark
  backdrop now animate smoothly both in and out for the X, outside click,
  Escape, Waifu Hoard, and Profile close paths instead of disappearing on exit.

## V0.0.1 beta3 Post-reconstruction hardening (2026-07-12)

- Moved local metadata from `_danbooru_metadata/` to the git-ignored `data/`
  directory: both SQLite databases, sidecars, thumbnails, artist assets, and backups.
- Added verified `VACUUM INTO` snapshots of `data/user.sqlite` on startup,
  after successful syncs, and from Settings. Identical snapshots are skipped
  and only the five newest are retained.
- Added a distinct `u` / Unrated state for sidecar-less media. General filters
  now match only explicit `g` metadata, and `rating:u` is supported.
- Added `/api/images` golden-master tests and a committed OpenAPI snapshot.
- Split API endpoint bodies into nine domain routers, with shared helpers in
  `backend/core.py` and a small `backend/server.py` composition root.
- Key thumbnails by content MD5 and extract MP4/WebM frames locally.
- Track the runnable `frontend/dist`; `run.bat` builds it when missing and npm exists.
- Replaced the primary tkinter folder chooser with Windows Explorer's modern
  `IFileOpenDialog`, isolated in a helper process. The temporary compatibility
  fallback from this iteration was removed for V1.0.0 portable builds.

## V0.0.1 beta2 In-app Library tools (2026-07-13)

- Moved the original five maintenance tools out of the browsing sidebar and
  into Settings -> Library without replacing or hiding them: Sync Database,
  Backfill Metadata, Rebuild Database (Recovery), Clean Orphan Sidecars, and
  Update Danbooru Tags.
- Improved Backfill Metadata with optional folder/Browse and limit controls.
  It obtains the image MD5 from its filename or hashes the file, finds the
  matching Danbooru post, and writes missing canonical JSON/tag sidecars. Its
  default remains every configured library folder.
- Added stage-aware streamed progress, a single global tool lock, and
  cancellation for maintenance runs.
- Added local Danbooru credential management and a user-triggered connection
  check. API keys are encrypted with Windows DPAPI under git-ignored `data/`,
  never returned to the frontend, and passed to tools through environment
  variables instead of command lines. Environment credentials override saved
  values.
- Backfill and refresh now scan every configured library folder, including
  registered external paths. External central sidecars no longer look orphaned
  merely because their media lives outside `data_root`.
- Update Danbooru Tags continues to archive replaced sidecars and then sync the
  refreshed metadata into SQLite; local user tags remain untouched.

## V0.0.1 beta1 Settings density pass (2026-07-13)

- Pinned the modal to an explicit header row and remaining-height content row,
  preventing short tabs from floating vertically in the middle.
- Converted App Behavior into the compact settings reference: a single grouped
  surface with hairline row dividers, right-aligned controls, and single-line
  segmented choices without purple glow or truncated descriptions.
- Extended the same grouped-row layout to Appearance and Discovery. Converted
  their card grids into compact segmented controls with descriptions in helper
  text and tooltips.
- Consolidated Library into one accordion surface. All five maintenance tools
  and Folders start expanded; credentials and backup details can be opened when
  needed without turning the page into a long stack of cards.

## V0.10

- Folder management moved from the sidebar to Settings → Library.
  - The sidebar folder list is now a pure filter (counts + All Folders); the
    + icon, name input, and per-folder remove button were removed.
  - "Add folder" now means registering an **existing** directory (anywhere on
    disk, by typed path or a native Browse dialog served by the backend);
    the app never creates folders anymore.
  - `registered_folders` gained a `path` column (additive migration; old
    name-only rows are backfilled as `data_root/name`).
  - Removing a folder un-indexes it (including subfolder labels and sync
    manifest rows) and never deletes files.
- Decision: **no full sidecar→SQLite rebuilds in routine flows.** New `sync`
  command in `danbooru_gallery_dl.py` does incremental delta imports driven
  by a `sync_manifest` (mtime/size) table: unchanged files are skipped
  without being opened, deleted files' rows are pruned, and folder
  add/rescan syncs only that folder. The full rebuild remains as a
  "Rebuild Database (Recovery)" tool; `refresh-tags` now ends with a sync
  instead of a rebuild. Sidecars stay the durable metadata store.
- Images without sidecars are now indexed (minimal record: dimensions via
  Pillow, dates from the filesystem, no tags) so plain image folders are
  browsable. This historical General fallback was replaced by the distinct
  Unrated state in the 2026-07-12 hardening work above.
- The reconstruction gap in `danbooru_gallery_dl.py` (86 unrecovered lines in
  the CLI search helpers) was filled with working reimplementations so the
  script compiles and the tools runner works again (see
  `archive/RECONSTRUCTION_LEDGER.md`). Bare numeric CLI filters default to `>=`,
  matching the surviving backend implementation from which these helpers
  were adapted.
- Reconstruction audit proved that `TagsBrowser.svelte` did not have a
  missing 9-line tail: the archived read after line 1120 was empty and later
  tail reads end at the component's closing `</div>`. The temporary gap
  marker was removed; no styles or feature code were absent there.

## V0.9

- Added local artist following as a profile watchlist.
  - Artist follows are stored locally in `user.sqlite`.
  - Artist follow UI lives on artist tag info and the local Profile page.
  - Twitter/X post fetching is intentionally out of scope; explicit profile-logo/banner archiving is supported separately.
- Added Danbooru post ID tracking for followed artists.
  - Manual checks record Danbooru post IDs only; they do not download files or hotlink images into the library.
  - Previously missing posts render as compact `#id` chips until expanded.
  - Expanded missing posts use dashed "Not in library" placeholder cards, while downloaded/local posts show actual local thumbnails.
- Followed artist cards now use a local profile thumbnail when available and update Check/Expand/Mark Seen state immediately in the profile view.
- Added an app-wide immediate-update pass.
  - Tag favorites/pins, artist follows, saved tag combos, blacklist tags, folders, image favorites, folder moves, grid refreshes, profile unfollows, and timelapse refreshes now update the visible UI directly or reconcile in the background.
  - Future mutations should keep using the local-state-first pattern instead of relying on a later reload to reveal the result.
- Followed artist profile cards are image-first tiles with only the artist name overlay and numeric local/new badges.
  - The focused panel darkens the profile page, animates the artist profile to the left, and reveals undownloaded Danbooru post placeholders plus Open Tag, Check, Mark Seen, and Unfollow actions.
  - The profile watchlist defaults to a horizontally scrollable rail. At ten or more artists it can expand into a complete responsive grid, and profile artwork uses consistent filled crops instead of letterboxed full-image framing.
- Added local artist profile-media archives.
  - Artist tag info can explicitly save current Twitter/X and Pixiv logos and banners under `data/artist_profile_archive` without hotlinking them in the UI.
  - Changed profile images create deduplicated historical versions; the archive is horizontally scrollable and expands when it grows.
  - Archived profile media opens in ImageDetail instead of a browser tab, and profiles without a published Pixiv banner report that absence explicitly.
  - Profile includes a bulk action to check every followed artist for changed profile media.
- Added followed-artist Danbooru notifications in the top bar.
  - Each artist establishes a one-time current-post baseline, then stale follows are checked in the background every 15 minutes while the app is open; historical posts are not misreported as new and no remote images are downloaded.
  - Notification actions open the artist's focused profile panel and update mark-seen state immediately.
  - Size, Filter, and Random now sit beside Search; notifications and the local profile remain pinned to the right.

## V0.8

- Added immediate-refresh direction for mutations such as favorites, collections, tags, and other image/detail changes.
- Added collection organization direction: collections should support editing names/descriptions and useful management actions.
- Added a top-right local user/avatar menu.
  - Current decision: avatar remains pinned to the far top-right.
  - Current decision: avatar dropdown has Profile, Favorites, Collections, Search Help, and Settings.
  - Current decision: Favorites and Collections live in the avatar dropdown rather than the main top nav.
  - Current decision: Profile is a full local-library page with banner/avatar artwork, library stats, favorites, and collections.
  - Current decision: no logout for local-only usage.
- Added Search Help modal from the avatar menu for supported query syntax: tags, negative tags, category prefixes, IDs, dimensions, height/width filters, shapes, score/rating/folder/ext filters, and date ranges.
- Collection cover previews now use media-aware preview data, so GIF and MP4/WebM items can preview from the real media file instead of only showing static thumbnails/placeholders.
- Added Settings modal for real Waifu-Hoard settings only.
  - Includes existing settings such as autoplay, card size, image fit, page size, rating filter, sidebar visibility, tag banner height, and duplicate review mode.
- Added Heart Spam as an optional ImageDetail interaction.
  - Settings controls whether the heart button is shown.
  - Heart spam is stored per local image, displayed below Seen, and searchable with `hearts:` / `heart_spam:`.
- Top bar UI decision:
  - Size, Filter, and Random are icon-only controls.
  - Size lives in the top bar, not inside the avatar menu.
  - Filter and Random should not show text labels in the top bar.

## V0.7

- Home shifted from a basic booru landing page toward a local library dashboard.
- Featured tags and more tags were redesigned to be cleaner and less cluttered.
- Added moving/rotating image discovery between Featured Tags and More Tags.
- Added local Danbooru tag wiki/info support.
  - Tag pages should show tag info above the local posts for that tag.
  - Remote example posts can show placeholders when the image is not local.
  - Local examples should show actual local images when available.
- Moved tag info into Browse-style tag pages with a banner header.
  - Banner should use a relevant local image where possible.
  - Banner height is configurable in Settings.
- Added artist journey/timeline concept inside artist tag info.
  - Timeline thumbnails should be large enough to inspect.
- Added daily challenge concept for guessing characters.
  - Direction: use blurred images and make answering by character name/tag less annoying.
- Added favorite/pinned tag directions.
  - Favorite tags can be pinned/used for prioritization.
  - Favoriting tags from ImageDetail should be available without visual clutter.

## V0.6

- Added or refined ImageDetail zoom/drag behavior.
  - Clicking while zoomed should not unexpectedly leave ImageDetail.
  - Outside black border should not expose misleading zoom/exit behavior.
- Added user-added tag filter behavior.
  - User-added filter is near Favorited.
  - Clicking it shows only user-added tags; clicking again turns it off.
- Added ability to open an image's folder/location from ImageDetail.
- Increased generated/displayed image quality enough to reduce blur without excessive storage growth.
- Added created-date popularity browsing.
  - Date, Month, and Year modes sort by popularity over the selected period.
  - UI direction: top-center period controls, previous/next period navigation, images below.
- Added Timelapse.
  - Simple timelapse is the primary user-facing mode: random images moving slowly.
  - Advanced timelapse exists but should be hidden behind an advanced entry and have a way back to simple mode.
  - Timelapse supports fullscreen and start/stop.
  - Avoid overcrowding the timelapse toolbar.
- Added parent/sibling local awareness direction based on Danbooru posts.
  - Related posts should be shown in ImageDetail when local metadata indicates parent/sibling relationships.
- Added mass-selection direction.
  - Select/check images from grid.
  - Floating menu should support favorites, collections, folder migration, and delete from disk.
  - Disk delete must warn with the number of images being deleted.
- Added search-by-ID such as `#8824525`.
- Added shape/size search options such as phone, banner, horizontal, vertical, logo.
- Added duplicate review direction.
  - Only true duplicates should be shown.
  - Parent/sibling relationships must not be treated as duplicates.
  - Preferred action is merge metadata/tags, keep the best copy, and delete the duplicate only after warning.
- Added mass action visibility for images already in favorites/collections.

## Metadata And Sidecars

- Sidecars moved conceptually to the central sidecar directory, now `data\sidecars`, separated by source folder.
- Future sidecar-writing/backfill behavior should write there directly.
- Do not add a normal user feature that migrates sidecars to that location unless explicitly requested.

## Notes For Future Updates

- Keep this changelog as a concise memory of durable decisions.
- Do not paste long conversation transcripts here.
- If a feature is scrapped, record the final decision, not every intermediate attempt.
