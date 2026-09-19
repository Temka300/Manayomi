# Keivotos — Roadmap

Where the project stands and what comes next. The per-feature behavior
contract is [FEATURES.md](FEATURES.md); durable product decisions are in
[../../CHANGELOG.md](../../CHANGELOG.md); speculative suite expansion lives in
[FUTURE.md](./FUTURE.md).

Legend: ☐ not started · ◐ in progress/discussion · ✔ statically present or
completed · ⚠ broken/blocked · ? unverified · ✂ dropped

---

## Current cycle: V1.1.3 (in progress)

> **This heading is the single place in the doc set that names the current
> cycle.** The shipped semantic version is `backend/product.py`, written only by
> `scripts/release/set_version.py`. Every other document points here or there
> instead of repeating a number — a version in prose goes stale the moment a
> cycle turns, which is exactly what happened to the whole doc set at V1.1.1.

The last **bumped** identity is **V1.1.2**, set by `set_version.py` after all ten
of its slices landed. **V1.1.3** implementation has started locally with the
Karaoke and YouTube modules; its version bump still happens only at the end,
not while the cycle is under verification.

V1.10 and post-V1.0 work are future ideas. Historical version folders and
changelog headings remain unchanged as lineage evidence; they do not define
the current release.

The current source has a broad implemented feature surface. V1.1.0's complete
automated baseline and isolated Files/module browser pass are recorded in the
feature register; older interactions without newer evidence remain unverified.

### Current facts

| Item | Status | Current evidence |
| --- | --- | --- |
| Reconstruction evidence | ✔ | mechanical ledger and archive lineage exist |
| Current source lineage | ✔ | 97 sampled files match `V1.0.0 - (Release soon 1) - from zero` byte-for-byte |
| Important-document current-state correction | ✔ | ten important documents reconciled against the current-state audit |
| OpenAPI snapshot | ✔ | `tests/test_openapi_snapshot.py` and `tests/snapshots/openapi.json` exist |
| `/api/images` golden master | ✔ | `tests/test_images_golden.py` and `tests/snapshots/images.json` exist |
| Current clean compile/test/check/build baseline | ✔ | Karaoke/YouTube completion: Python compile passed, all 352 tests passed with the regenerated OpenAPI snapshot, frontend check is 0 errors/warnings, and the production build emits the local JASSUB assets. |
| Runtime smoke baseline | ✔ | Isolated generated-media browser pass on `localhost:54327` verified local player timing/lyrics/queue/persistence, desktop and narrow layouts, Settings, Files roots, local-only YouTube playback, and YouTube→Karaoke handoff with clean final console/server logs; the test server was stopped, then the main `localhost:54325` app was restarted and returned all five descriptors without changing existing module enablement. |
| Danbooru sidebar animation | ✔ | manually confirmed working 2026-07-25 (slide, grip drag/persist, toggle, saved position); not automatable in the non-compositing browser pane |
| Reddit module fork | ✔ | Slices 0-8 plus in-app Save link, confirmed media/Linked-files workflow, and sixth Reddit Settings category implemented locally through 2026-07-28: truthful indexed receipts, outbound link cards, bounded image/GIF/video/file downloads, persisted capture defaults, archive/storage/limit status, and default Files publication; feed/thread HTTP 500 regression fixed under automated coverage; default app origin `localhost:54325`; user-owned live browser/media verification still pending; not version-bumped or released |
| Karaoke and YouTube modules | ✔ | Both optional descriptors, stable APIs, create-only local libraries, Files publication, Karaoke metadata/library/lyrics/player, Kara.moe-first plan-confirm acquisition, YouTube actual-format plan-confirm yt-dlp acquisition, local-only UI, Settings, and cross-module handoff are implemented and verified through the full automated and isolated browser gates. No real provider media was downloaded. |
| Manayomi module | ✔ | integrated as the sixth optional descriptor with preserved manga databases, Files publication, verified root relocation, improved Library controls/language/blacklist UI; 427-test/check/build and real 4,109-item desktop/narrow browser gate passed 2026-08-08 |
| Backend modularity | ✔ | `backend/core.py` deleted 2026-07-25 (was 3,231 lines); no wildcard imports remain; Danbooru behavior under `modules/danbooru/`, shared helpers under `services/`; 193 tests green and the OpenAPI snapshot unchanged throughout |
| Path centralization | ◐ | config and sidecar layout are centralized; policy remains distributed |

## Required sequence before broad application refactoring

1. ✔ Repair the repository agent instructions.
2. ✔ Audit the current project and archived lineage.
3. ✔ Correct the important documentation so current, historical, broken, and
   future states are separated.
4. ☐ Build the feature-to-code map with symbols, temporary line references,
   APIs, persistence, tests, archive lineage, and status.
5. ☐ Agree on the modular target and extraction order.
6. ☐ Add browser characterization for the sidebar and other high-risk timed
   interactions.
7. ☐ Run a clean compile, unit-test, frontend-check, and frontend-build baseline
   when separately authorized.
8. ☐ Run source-startup and browser smoke verification at
   `http://localhost:53325/` when separately authorized.
9. ☐ Restore the sidebar behavior before refactoring its implementation.
10. ✔ Extract `backend/core.py` one protected domain at a time — completed
    2026-07-25; the facade was reduced to zero behavior and deleted.
11. ☐ Centralize or explicitly document each path-policy boundary without
    creating a new giant path module.

Each restoration, characterization, extraction, path change, and cleanup is a
separate permission-scoped change. No code is approved for deletion merely
because it appears unused.

## Engineering safety status

| Safety net | Status |
| --- | --- |
| OpenAPI schema snapshot | ✔ regenerated for the intentional Karaoke/YouTube APIs; focused snapshot test passes |
| `/api/images` golden response | ✔ exists; current passing state unverified |
| focused backend/unit tests | ✔ 23 `test_*.py` files with 85 static test methods found |
| sidebar source contract | ✔ exists, but does not verify real motion |
| browser E2E smoke automation | ☐ not present |
| feature-to-code implementation index | ☐ next required documentation artifact |

## Historical lineage

The following remain reference material only:

- archived V0.0.1, V0.0.2, Beta, Release Candidate, and Release soon folders;
- historical `CHANGELOG.md` headings including V1.1 through V1.10;
- the retired intermediate SvelteKit reconstruction;
- the old rebuild remap from V1.x notes to 0.x milestones.

Archive labels are never rewritten to match the current release identity.

## V1.1.1 — shipped (version bumped, `75789b2`)

What was built under it:

- The **Files info panel**: type-aware preview, file facts, origin notes
  (description + labeled/kinded links), tile note-badges, image/video
  attachments stored in the first Files folder, and an opt-in `.keivotosbk`
  backup component for those bytes.
- **`backend/core.py` removed** — the 3,231-line wildcard facade reduced to zero
  behavior and deleted; Danbooru behavior now lives under `modules/danbooru/`.
  Two latent crash bugs (`SIDECAR_SUFFIXES`, the `gallery_dl_command` path) were
  found and fixed along the way.

## V1.1.2 — shipped 2026-07-25 (theme: "Files, actually browsable")

V1.1.1 gave Files an origin panel but left the grid as emoji icons. V1.1.2
delivered what the user asked for: **see a file's origin — its description, its
links, and a screenshot — without leaving the grid.** Ten slices, each verified
before the next, and **no new runtime dependency** in the whole cycle.

1. ✔ **Guarded thumbnail endpoint** — `GET /api/files/thumbnail`, reusing the
   V1.1.1 containment chain. Cache key prefers the indexed content hash and
   falls back to identity/mtime/size so browsing never reads a multi-gigabyte
   file to draw a tile.
2. ✔ **Grid thumbnails** — real image/video tiles, lazy, glyph fallback on 404,
   client-gated to the backend's real thumbnail set so non-visual folders issue
   no requests at all.
3. ✔ **Folder covers** — the first thumbnailable file in a folder's *subtree*,
   two index-friendly queries, scoped to one source so a nested source is never
   borrowed from.
4. ✔ **Origin attachment as the tile face** — an explicit attachment outranks
   everything, which is how a 3D model or archive gets a picture at all.
5. ✔ **Per-module grid size control** — shared Small…Absurd scale, per-surface
   value; `GridSizeMenu.svelte` is now used by both Files and Danbooru's TopBar.
6. ✔ **Resizable info panel** — drag or keyboard, persisted, 300–760px.
7. ✔ **Panel led by Origin** — reordered above the file facts, type scale raised
   12→14px / 10→12px, and the Path no longer breaks mid-word.
8. ✔ **Copy origin info from another file** — the unzip workflow. Additive
   union merge; a 409 guards an existing description.
9. ✔ **Read-only archive listing** — central directory only, never decompressed,
   names inert, 2000-entry cap, content-sniffed rather than extension-trusted.
10. ✔ **Cleanups surfaced by the extraction**
    - The duplicated range-serving helper moved to `services/range_serving.py`;
      both surfaces re-export it, identity verified, OpenAPI unchanged.
    - **"Dead compatibility aliases" turned out to be almost nothing.** A
      mechanical scan of every public function in `backend/` found exactly one
      genuinely unreferenced name (`files_base/hashing.py:md5_of_file`). The
      other 84 hits were FastAPI route handlers and middleware, bound by
      decorator and only *looking* unreferenced — deleting any would have
      deleted an endpoint.
    - A shared thumbnail service was **not** needed: `backend/thumbnails.py` is
      already path-based and content-MD5-keyed.

### Tried and reversed inside the cycle

- A **1250px cap** on the browse row, added to pull the panel away from the
  screen edge. On a wide display it stranded a ~450px dead band to the right of
  the panel and cost the grid two columns; removed on user report. The resizable
  panel achieves the same proximity with no waste.

## V1.1.3 — current work and remaining candidate pool

- **Karaoke + YouTube local media modules — implemented locally.** The approved
  `KARAOKE_YOUTUBE_MODULE_PLAN.md` is complete through backend, frontend,
  Settings, Files publication, cross-module handoff, full regression, and
  isolated timed-browser verification. Provider search/download was
  deliberately not run as part of automated verification. This is not yet a
  version bump, package, commit, or release.

The following candidates remain unstarted and are not part of the current
Karaoke/YouTube change:

- **The engine tier for thumbnails**, deliberately held out of V1.1.2 so that
  cycle stayed dependency-free:
  - **PDF** first page — `pypdfium2` (BSD/Apache) preferred over PyMuPDF (AGPL)
    for a distributed app. Ships a native binary, so `build_windows.ps1` must be
    verified, not assumed.
  - **cbz and epub covers** — stdlib `zipfile` plus OPF manifest parsing; could
    land dependency-free.
  - **cbr** — needs `rarfile` *and* an external unrar binary. Only worth it if
    the library actually contains `.cbr` files; unconfirmed.
  - **Embedded cover art for audio** — a FLAC/MP3 album folder currently renders
    as a wall of identical 🎵 glyphs, and those files usually carry cover art.
    Needs `mutagen`. Noticed while reviewing the real `OST` folder.
- **Module-claim chip** (§5) — the "↗ open in Danbooru" affordance.
- **`ImageSize` → `GridSize` rename** — a pure rename across five components,
  now that the scale is genuinely shared rather than Danbooru-owned.
- **Frontend `VERSION` is dead code** — `frontend/src/lib/product.ts` exports it,
  nothing imports it, and Vite tree-shakes it, so the built bundle contains no
  version string at all. A release bump therefore produces no `dist` change.
  `set_version.py` calls it "frontend runtime identity", which overstates it.
  Either surface it in the UI or drop the claim; a test already keeps it in sync
  with `product.py`, so nothing is broken today.
- Bigger or gated: a 3D/Live2D model viewer; universal `files_favorites` (needs
  a second metadata module first); frontend logic extraction (gated on sidebar
  restoration); remaining path-policy centralization.

## V2.0.0 — candidate pool (not started, nothing committed)
- **Client-side URL router** (SUITE_MODULE_CONTRACT §9.1) — the headline
  candidate. Rewires core navigation state (`viewMode`, `activeModule`, search,
  filters), which is higher-risk and harder to prove intact in this harness.
  After the sidebar lesson, risky navigation work gets its own cycle.

- **Auto categorizer** - When a user adds their file to one folder user will give info about it like
  3d or live2d or danbooru. then add infos like url, desc, extra url, extra desc.
  which then the tool will auto organize to the related folder

## Unscheduled future ideas

No feature update beyond the stabilization/refactor sequence above has been
selected. V1.10, post-V1.0 suite modules, themes, reverse image search, missing
tags, feeds, tag graphs, relationships, tier lists, translation, OCR, Docker,
Linux packaging, and other ideas remain discussion material in
[FUTURE.md](./FUTURE.md).

Multi-user accounts remain contrary to the current local-first product
contract unless the user explicitly reopens that decision.
