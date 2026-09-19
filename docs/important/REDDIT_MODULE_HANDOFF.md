# Reddit Module Research, Decisions, and Continuation Handoff

## Purpose

This document preserves the complete working context for the proposed Keivotos
Reddit module so that the work can continue in a new Codex task without
reconstructing the previous conversation.

It records:

- the user's end goal and requested workflow;
- what was inspected and researched;
- corrections to the original attached architecture proposal;
- current Reddit acquisition options and limitations;
- the intended URL-driven capture behavior;
- the recommended storage and search architecture;
- the proposed slice sequence;
- the completed Slices 0-8 plans and boundaries;
- what has and has not been implemented;
- the approval state and instructions for the next task.

This is a handoff and planning document. The implementation and verification
evidence for Slices 0-8 is recorded below and in `REDDIT_MODULE_PLAN.md`.

## Current Status at Handoff

Originally researched and written: **2026-07-26**  
Updated through Reddit fork Slice 8 and the in-app capture follow-up:
**2026-07-28**

Repository:

```text
D:\Kivotos\Github_Wakaru\Keivotos-Modulo\Reddit
```

Original Keivotos repository:

```text
D:\Kivotos\Github_Wakaru\Keivotos
```

Historical repository state when this document was created:

```text
branch: main
commit: e5172ec553496ddd2f7c8abb11b005ee987fcd27
version: 1.1.2
worktree before this document: clean
```

The fork and original repository were previously confirmed to be at the same
commit. The working directory no longer contains `.git`; the user explicitly
said this is a separate thing and does not want commits. Codex did not remove
`.git` and performed no Git mutation. Slices 0-8 now provide a registered
optional Reddit module, but no package or release was created.

On 2026-07-28, the approved Karaoke/YouTube work extracted Reddit's generic
yt-dlp subprocess mechanics to `backend/services/yt_dlp.py`. Reddit still owns
its provider allowlists, media plan, limits, object store, receipts, and Files
publication. Focused Reddit media plus shared-service regression tests confirm
the extraction; it adds no Reddit behavior and opened no Reddit media URL.
Karaoke and YouTube are independent optional descriptors and do not read
Reddit's archive or storage.

### Work completed

- Read the project structure and the relevant architecture and feature
  documentation.
- Read the user's attached Reddit architecture proposal in full.
- Compared the proposal with the current Keivotos tree.
- Inspected the current module, router, lifecycle, Files attachment, storage,
  frontend, testing, and dependency boundaries.
- Researched current Reddit API access, listing behavior, rate limits, data
  deletion requirements, research access, user exports, scraping terms,
  Arctic Shift, and gallery-dl.
- Designed a source-neutral, URL-driven preservation approach that can grow
  from roughly 5,000 to 500,000 or more records.
- Proposed an end-state slice sequence and a bounded Slice 0.
- Created this handoff document after explicit user approval.
- Implemented the approved offline Slice 0 URL parser, local streaming importer,
  atomic raw capture chunks, durable job manifest, rebuildable SQLite/FTS5
  index, post/comment observations, asset-policy queue, resume ledger, CLI, and
  focused regression tests.
- Documented the exact current boundary and usage in
  `docs/important/REDDIT_MODULE_PLAN.md`, `FEATURES.md`,
  `FEATURE_CODE_MAP.md`, and `CHANGELOG.md`.
- Verified Slice 0 with 11 focused tests plus 3 subtests, Python compileall, and
  the full repository suite: 253 tests plus 15 subtests passed.
- Researched the current Arctic Shift dump format, download indexes, streaming
  requirements, API behavior, and dataset scale.
- Researched Reddit's current approved-app/OAuth requirement, Listing cursor
  protocol, 100-QPM free-access rule, rate-limit headers, and deleted-content
  retention requirements.
- Implemented Slice 1 streaming reads for standard Arctic Shift `.zst` JSONL.
  It supports optional SHA-256 verification before archive creation, inclusive
  `--after`, exclusive `--before`, scoped/global source modes, target
  pre-filtering before global raw preservation, resumability, and deterministic
  coverage reports.
- Added `zstandard==0.25.0`, updated `uv.lock`, and recorded its BSD-3-Clause
  notice.
- Implemented a bounded official Reddit OAuth Listing client. Credentials come
  only from `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, and
  `REDDIT_USER_AGENT`; it requests at most 100 items per page, follows `after`,
  deduplicates fullnames, stops repeated cursors, honors rate-limit/reset and
  retry headers, and caps one discovery at 1,000 items.
- Kept API response bodies out of the permanent archive. API mode writes only
  a create-only ID/canonical-URL manifest. A local `.zst` import can consume
  that manifest to select the listed posts and comments whose `link_id`
  belongs to those posts.
- Added focused `.zst`, integrity, coverage, OAuth, pagination, retry,
  rate-limit, create-only, and discovery-to-dump tests. The focused Slice 0-1
  set passes 19 tests plus 3 subtests; Python compileall and the full repository
  suite pass 261 tests plus 15 subtests.
- Updated `REDDIT_MODULE_PLAN.md`, `FEATURES.md`, `FEATURE_CODE_MAP.md`, this
  handoff, and the important changelog for Slice 1.
- Researched the installed gallery-dl Reddit image behavior and partial-file
  controls, current yt-dlp Python/FFmpeg and licensing requirements, the
  existing shared FFmpeg resolver, and the downloader packaging boundary.
- Implemented Slice 2 as a separate `reddit_media.py` plan/download workflow.
  Planning is offline and destination-free. Download requires both the exact
  selected count and selection SHA-256 from a matching plan.
- Added finite file-count, per-file, run-byte, retry, timeout, and reserved
  free-space limits. Only already-queued, HTTPS Reddit-hosted roles are
  eligible; credential-bearing URLs, custom ports, unrecognized hosts, and
  generic external roles are rejected.
- Integrated gallery-dl for its direct `i.redd.it`/`preview.redd.it` extractor,
  a bounded DNS/redirect/MIME/stream-checking HTTP fallback for recognized
  Reddit CDNs, and pinned `yt-dlp==2026.7.4` plus the shared FFmpeg resolver for
  stored `v.redd.it` DASH/HLS/file URLs.
- Added create-only SHA-256 object storage, verified byte deduplication,
  create-only observation manifests, and started/complete/failed database
  events. Resumable partials stay in stable staging; invalid completed and
  oversized outputs move to preserved failure directories so retries cannot
  become permanently stuck on the same invalid final file.
- Added focused offline media tests. Slice 2 focused verification passes 12
  tests plus 4 subtests; Python compileall and the full repository suite pass
  273 tests plus 19 subtests.
- Updated the dependency lock, compatibility requirements, third-party notice,
  release license collector, capture guide, feature/code maps, changelog, and
  this handoff for Slice 2.
- Researched Arctic Shift's published about, rules, and wiki record schemas and
  separated those local corpus shapes from the unavailable moderator domain.
- Implemented Slice 3 as the offline-only `reddit_community.py` importer and
  CLI. It accepts explicit about/rules/wiki JSON, JSONL, gzip JSONL, and `.zst`
  sources plus a versioned module-owned local moderator snapshot bundle.
- Added create-only community manifests, atomic verified raw chunks, source
  provenance, a durable error ledger, deterministic coverage, integrity
  checking, interruption/resume, and duplicate-free repeated completion.
- Added additive rebuildable-index tables for versioned subreddit about
  observations, ordered and empty rule snapshots, wiki paths and revisions,
  moderator snapshots, and recognized icon/banner asset-queue observations.
- Added 11 focused Slice 3 tests. The focused Reddit Slices 0-3 set passes 42
  tests plus 7 subtests; Python compileall and the full repository suite pass
  284 tests plus 19 subtests.
- Updated `REDDIT_MODULE_PLAN.md`, `FEATURES.md`, `FEATURE_CODE_MAP.md`, this
  handoff, and the important changelog for Slice 3. No dependency changed.
- Implemented Slice 4 as the read-only `comment_trees.py` projection and
  `reddit_comments.py` inspect/export CLI over already-normalized comments.
- Added deterministic parent/child ordering; exact once-only comment
  projection; missing-parent placeholders; cycle breaking only in the exported
  view; and explicit coverage for malformed parents, cycles, duplicates,
  unknown posts, stored/derived depth, removed bodies, and
  declared-versus-observed counts.
- Added pre-load comment and streaming output-byte caps, create-only
  verification, and an iterative JSON encoder that exports deeply nested
  threads without using Python recursion.
- Added 10 focused Slice 4 tests. The complete Reddit Slices 0-4 set passes 52
  tests plus 10 subtests; Python compileall and the full repository suite pass
  294 tests plus 22 subtests.
- Updated `REDDIT_MODULE_PLAN.md`, `FEATURES.md`, `FEATURE_CODE_MAP.md`, this
  handoff, and the important changelog for Slice 4. No schema or dependency
  changed.
- Implemented Slice 5 bounded direct-link capture through Arctic Shift's
  structured JSON API. Post URLs route to one post plus a comment tree capped
  at 25,000; subreddit URLs route only to about/rules/wiki/image context.
  Exact responses and source manifests are create-only, and supplied
  `kind: "more"` IDs are preserved in an additive placeholder table.
- Implemented Slice 6 as the SQLite read-only/query-only `library.py` service
  and `reddit_library.py` CLI: stable keyset feed cursors, filters, bounded FTS,
  post/thread detail, community snapshots/history, local-media references, and
  capture status.
- Implemented Slice 7 as the optional Reddit descriptor at
  `<suite-home>/modules/reddit`, an always-mounted enabled-state-gated
  `/api/reddit/*` router, guarded SHA-256 media serving with ranges, API tests,
  and an additive OpenAPI snapshot.
- Implemented Slice 8 as a module-owned Reddit-inspired Svelte surface with an
  infinite saved-post feed, search/filtering, post observations, nested
  comments, community about/rules/wiki/moderators, and local-media-only
  rendering.
- Verified the integrated surface against a disposable synthetic module home:
  enabled Reddit through the drawer, loaded 25 posts then 5 more by real
  scrolling, found a comment through FTS, opened the correct thread, opened
  community context, and observed no browser console warning or error.
- Ran frontend static checking with zero errors/warnings and built the
  production frontend successfully. No runtime dependency was added.
- Final Python compileall, the additive OpenAPI snapshot, frontend static
  checking, and production build passed. The complete repository run after the
  in-app capture follow-up passed all 314 tests.
- Changed the suite default browser port to 54325 across runtime, Vite, current
  tests, and current documentation without editing historical release evidence.
- Extracted the direct import orchestration into `direct_capture.py`, reused it
  from the CLI, and added enabled-only serialized `POST /api/reddit/capture`.
- Added the Save link button beside Refresh and a right-to-left animated drawer
  with URL input, progress/error/success states, Escape/backdrop/close behavior,
  and automatic local feed/status refresh after capture.
- Capture success now requires indexed post evidence and reports the actual
  archived-comment count. The drawer offers Images/GIFs, Videos, and generic
  Linked files, then requires a second confirmation against the exact offline
  plan before downloading.
- Added inert outbound-link cards and bounded HTTPS linked-file acquisition.
  Pinned `mfget==0.1.3` resolves supported MediaFire single-file metadata;
  Keivotos retains authority over DNS, redirects, byte limits, free-space
  guards, timeouts, object installation, and failure preservation.
- Friendly downloaded files are materialized beneath `media/library` and that
  exact declared root is published and scanned as **Reddit downloads** in the
  always-on Files base. Other private suite paths remain unservable.
- Verified the drawer in the isolated browser: URL autofocus, validation,
  target-specific mocked success, refresh, Escape close, and a clean console.
  Three bounded post captures and one subreddit-only capture were also run
  against Arctic Shift in the disposable module home; no media bytes were
  downloaded.

### Work not completed

- No Reddit API credentials have been created or used.
- No live media URL has been opened and no real media or linked file has been
  downloaded. Media engines were exercised only with injected local fixtures.
- No real archive database or user data has been created or modified; tests
  used isolated temporary JSONL and SQLite files and removed them afterward.
- The normal application data and server were not started or modified. A
  separate isolated server was started for browser verification, stopped, and
  its synthetic and live-capture scratch data removed afterward.
- Nothing has been staged, committed, pushed, tagged, packaged, or published.
- No actual large dump was imported; tests used small generated `.zst` files.
- Moderator membership was not supplied by the Arctic Shift subreddit smoke;
  the result reports that limitation instead of inferring names.
- Automated direct-capture tests still use injected finite JSON fixtures. Live
  verification was limited to three bounded posts and one bounded subreddit;
  no listing crawl or media-byte download ran.
- The user confirmed this Arctic Shift endpoint was reachable in their own
  manual test:

```text
https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=AIcrack&sort=desc&limit=5
```

  Slice 1 records it as a candidate for a later explicit network-source
  adapter; the implemented preservation path does not depend on that community
  service.

## Approval State

The user first approved this handoff document, then approved the recorded
Slice 0 plan by saying:

```text
now start
```

Slice 0 was implemented and verified after `now start`. The user then approved
the researched Slice 1 plan, clarified that no commit is wanted, asked for the
official Reddit API approximately-1,000-item option, manually tested the Arctic
Shift URL above, and gave final Slice 1 approval by saying:

```text
ok i tried arctic shift it works so let's go with slice 1
```

Slice 1 was implemented. The user then approved the recommended
Reddit-hosted-image-and-video Slice 2 plan by saying:

```text
do it
```

Slice 2 was implemented and verified. The user approved the recommended
offline community-context Slice 3 plan by saying:

```text
go
```

Slice 3 was implemented and verified. The user approved the recommended
offline comment-tree integrity/export Slice 4 plan by saying:

```text
go
```

Slice 4 is implemented and verified. On 2026-07-27 the user approved the
complete no-web-archive continuation plan by saying:

```text
yes
```

The approved continuation intentionally excludes WARC, WACZ, Wayback, Common
Crawl, Browsertrix, browser-session capture, and replay. It proceeds through a
bounded Arctic Shift direct-link adapter, the offline library service, runtime
module/API registration, and an original Reddit-inspired infinite local feed.
At the end of every slice, update both this handoff and
`REDDIT_MODULE_PLAN.md`.

## Slice 2 Implementation and Verification

Research, implementation, and offline verification were completed on
2026-07-27. No live media URL was opened.

The installed `gallery-dl==1.32.6` Reddit extractor can handle Reddit-hosted
images, galleries, embedded media, preview fallbacks, and direct DASH handoff.
Its current implementation delegates DASH/HLS video download and merging to
yt-dlp/youtube-dl. It also supports partial files, retries, timeouts, HTTP
content validation, per-file size limits when the server supplies a length, and
an SQLite download archive.

The project already resolved and bundled FFmpeg for video thumbnails and the
Windows portable build. Slice 2 pins the current `yt-dlp==2026.7.4` Python
distribution, invokes it as a child process, and disables user configuration.
It performs no surprise binary download or self-update.

Three next-slice choices were identified:

1. **Still images only:** use the existing gallery-dl engine plus a tightly
   bounded HTTP fallback for explicitly recognized Reddit CDN hosts. No new
   dependency, but Reddit video remains queued.
2. **Reddit-hosted images and video (recommended):** the first option plus a
   pinned yt-dlp wheel using the existing FFmpeg path for stored
   `v.redd.it` DASH/HLS/fallback URLs. This matches the user's explicit image
   and video preservation goal without re-querying a Reddit post page.
3. **Images, video, and arbitrary external sites together:** not recommended
   as one slice. gallery-dl child extractors can expand into many site-specific
   behaviors, credentials, redirects, and licensing assumptions. External
   domains need a separate allowlisted adapter after the Reddit-hosted path is
   characterized.

The approved bounded Slice 2 implementation is:

- add `backend/modules/reddit/media.py` and `scripts/reddit_media.py`;
- add a no-network `plan` command that reports eligible queued assets by
  role/host, selected file cap, destination, known/unknown size, and disk
  budget before any download;
- require a separate explicit `download` command with a matching confirmation
  count and selection hash, finite retry/timeout limits, a maximum file count,
  maximum per-file bytes, maximum run bytes, and minimum free-space reserve;
- consume only already queued Reddit-hosted image/preview/gallery/embed/avatar
  assets and stored `v.redd.it` URLs; never re-enumerate Reddit or call its API;
- invoke gallery-dl for supported image URLs, a small bounded HTTP fallback
  only for recognized Reddit CDN hosts, and pinned yt-dlp plus the existing
  FFmpeg engine for DASH/HLS video;
- preserve completed bytes in a SHA-256 content-addressed object store, never
  overwrite them, append download observations, and let multiple asset URLs
  reference the same object;
- retain resumable engine partials after interruption and never delete an
  earlier media object or metadata observation;
- reject queued `external` roles in this slice even if an allowlist exists;
- test planning, confirmation mismatch, role/host rejection, byte/disk caps,
  interruption/resume, hash deduplication, create-only behavior, subprocess
  argument secrecy, and a tiny local video/HTTP fixture; run no live Reddit or
  third-party media request;
- pin yt-dlp 2026.7.4, update `uv.lock`, third-party notices,
  dependency-license collection where required, the feature/code maps,
  changelog, capture guide, and this handoff;
- do not register the runtime module, alter the frontend, start the app server,
  or perform Git operations.

Implemented files and seams:

```text
backend/modules/reddit/media.py
backend/modules/reddit/archive.py
backend/thumbnails.py
scripts/reddit_media.py
tests/test_reddit_media.py
pyproject.toml
uv.lock
backend/requirements.txt
THIRD_PARTY_NOTICES.md
scripts/release/collect_licenses.py
```

The exact command and storage layout are in `REDDIT_MODULE_PLAN.md`. Automated
tests use generated local images and mocked downloader processes only. The app
server was not started or restarted, and no runtime registration, frontend,
build output, user database, real archive, or Git state was touched.

## Slice 3 Implementation and Verification

Research, implementation, and offline verification were completed on
2026-07-27 after Slice 2. No Reddit or Arctic Shift community data endpoint was
called.

Current source findings:

- Reddit's documented OAuth API has separate read endpoints for subreddit
  about metadata, rules, public moderator Listings, wiki page lists/content,
  widgets, and flair/emoji data. The about response includes description,
  subscriber count, and header image.
- Reddit currently requires approved OAuth access and a descriptive
  User-Agent. Its deletion policy expressly covers user-identifying fields such
  as usernames and avatar URLs, so permanent live moderator/user observations
  still conflict with Keivotos's absolute no-delete archive rule.
- Arctic Shift published a January 2025 community corpus with about metadata
  for roughly 22 million subreddits, rules for roughly 345,000, and roughly
  323,000 wiki pages. It also publishes JSON schemas for these record types.
- Arctic Shift's community API has subreddit search, batched rules, wiki-page
  listing, and wiki retrieval endpoints, but the project explicitly gives no
  uptime or performance guarantee and says subreddit metadata is updated only
  infrequently. It does not provide the requested current moderator list.

Three bounded choices followed from that:

1. **Local community corpus/bundle import (recommended):** stream
   user-supplied Arctic Shift community JSON/JSONL/`.zst` using the published
   schemas, plus an optional module-owned local moderator snapshot bundle.
   Preserve raw provenance, normalize versioned about/rule/wiki/moderator
   observations, queue recognized icon/banner assets, and report coverage. No
   network or API-retention decision is needed.
2. **Live Arctic Shift community adapter:** add plan/confirmation and bounded
   requests to the community service the user already tested. This is
   convenient for about/rules/wiki but is unofficial, currentness is limited,
   and moderators remain unavailable.
3. **Official OAuth current community adapter:** fetch the freshest about,
   rules, public moderator list, wiki, widgets, flair, and emoji data. This
   best matches the complete end goal, but permanent storage cannot be
   implemented until the user chooses a deletion/privacy policy compatible
   with Reddit's current terms and the fork's no-delete rule.

The user approved option 1. The implemented Slice 3 boundary is:

- add a standalone community importer under
  `backend/modules/reddit/community.py` with
  `scripts/reddit_community.py`;
- accept explicit local about, rules, wiki, and optional module-owned
  moderator snapshot sources; support standard Arctic Shift JSON/JSONL/`.zst`
  records without downloading a corpus;
- require a subreddit target and source type, optional published SHA-256, and
  bounded chunk size; pre-filter global sources before raw preservation;
- preserve create-only raw chunks/manifests and add observation tables instead
  of overwriting the latest about/rule/wiki/moderator state;
- queue subreddit icon/banner URLs into the existing Slice 2 asset queue while
  leaving their bytes untouched until a separately planned/confirmed media
  run;
- write coverage including source kind, records scanned/matched/invalid,
  distinct wiki pages/rules/moderators, observed dates, and missing requested
  domains;
- characterize the published schemas, nested wiki paths, duplicate revisions,
  ordering, missing/private fields, asset queuing, interruption/resume, and
  create-only behavior with generated local fixtures;
- add no dependency, no network adapter, no runtime module, no frontend, and no
  `user.sqlite` or Git operation.

This gives the future custom UI real community context at both 5k and 500k
scale without silently deciding the live API retention conflict.

Implemented files and seams:

```text
backend/modules/reddit/community.py
backend/modules/reddit/archive.py
scripts/reddit_community.py
tests/test_reddit_community.py
```

The published Arctic Shift shapes characterized by the importer are: one about
object per observation; a rules object containing `subreddit`, `retrieved_on`,
and an ordered `rules` array; and wiki objects containing `content`, nested
`path`, retrieval time, and revision fields. Empty rules arrays are preserved
as meaningful snapshots. About observations retain a normalized metadata
subset and their raw source record. Recognized icon and banner fields are
queued with `subreddit-icon` and `subreddit-banner` roles.

The optional moderator format is deliberately not presented as Arctic Shift or
Reddit output. It is
`format: "keivotos-reddit-moderators-v1"` with an explicit subreddit,
retrieval time, optional source label, and moderator records containing a name
plus optional account ID, permissions, and added time. It is local
user-supplied evidence and may contain identifying data.

Focused Reddit verification passes 42 tests plus 7 subtests. Python compileall
passes, and the full repository suite passes 284 tests plus 19 subtests. Tests
cover published shapes, nested wiki paths and multiple revisions, rule ordering
and empty snapshots, moderator bundles, global-before-raw and
scoped-as-evidence filtering, asset queuing, `.zst`, expected SHA-256,
invalid-source failure before database creation, interruption/resume,
idempotency, create-only coverage, and CLI behavior. No real archive, large
corpus, media directory, user database, application runtime, or Git state was
touched.

## Slice 4 Implementation and Verification

Research, implementation, and offline verification were completed after Slice
3 on 2026-07-27. No Reddit or Arctic Shift data endpoint was called.

Current comment findings:

- The archive already retains normalized comments with `link_id`, `parent_id`,
  and depth, but does not yet provide a deterministic whole-thread read model
  or a per-post completeness report.
- Arctic Shift documents `/api/comments/tree` with a maximum `limit` of 25,000.
  Its tree schema can contain collapsed `kind: "more"` nodes with IDs, so even
  a successful response must report placeholders rather than claim a complete
  tree. The service has no uptime or performance guarantee.
- Reddit's official OAuth API exposes `/comments/{article}` and
  `/api/morechildren`. Thread results may be truncated, so correct expansion is
  a separate rate-limited acquisition workflow rather than one Listing call.
- Reddit's current Data API rules require deletion of deleted post/comment
  content and author-identifying data, recommended within 48 hours. That still
  conflicts with this fork's absolute no-delete preservation rule.

Three bounded choices followed:

1. **Offline comment-tree integrity and export (recommended):** build trees
   only from already-imported comments, with deterministic ordering, orphan and
   cycle guards, missing-parent/placeholders, declared `num_comments` versus
   observed counts, per-post coverage, and local JSON export. This improves both
   5k and 500k archives without choosing a live service or retention policy.
2. **Bounded Arctic Shift known-post trees:** add a separate plan/confirmation
   adapter for explicit post IDs, preserve `kind: "more"` coverage, and cap
   requests/comments. It is convenient and aligns with the endpoint the user
   tested, but it is an unofficial live dependency with no uptime guarantee.
3. **Official OAuth thread hydration:** call the thread endpoint and expand
   `/api/morechildren` under strict request/rate limits. This is the freshest
   official path, but permanent content storage must wait for an explicit
   deletion/privacy policy compatible with Reddit's current rules.

The user approved option 1. The implemented bounded Slice 4 is:

- add a cohesive offline comment-tree/read-model helper and CLI;
- consume only existing normalized rows; never rewrite raw records or
  observations;
- detect duplicate identities, missing links/parents, self-parenting, cycles,
  impossible depths, and comments attached to an unknown post;
- output deterministic nested JSON and per-post coverage with observed totals,
  root/orphan/cycle/placeholders, maximum depth, and the latest supplied
  `num_comments` comparison;
- make the export create-only and safe to rerun, with post selection and output
  limits suitable for both small and large archives;
- characterize deleted/removed bodies, unsorted input, deep chains, malformed
  graphs, and large synthetic trees without recursion overflow;
- add no dependency, network adapter, runtime module, frontend, `user.sqlite`
  table, live operation, or Git operation.

Implemented files and seams:

```text
backend/modules/reddit/comment_trees.py
scripts/reddit_comments.py
tests/test_reddit_comments.py
```

`inspect` opens an existing archive through SQLite `mode=ro` plus
`query_only`, checks the comment cap before loading rows, and prints bounded
coverage. `export` builds the same projection and writes only the explicit
output path through a temporary file, enforcing a byte cap before create-only
installation. An existing identical file is verified; an unlike file is
refused and preserved.

The projection keeps archived parent IDs and stored depths unchanged. It
normalizes parent references only for the read model, orders siblings by
creation time then ID, reports malformed components, and breaks each detected
cycle at its deterministic smallest ID only in memory. Every normalized comment
appears exactly once under either `root_comments` or `detached_comments`.
Missing parent references produce explicit placeholder records. Older Slice 0
imports retain `null` collapsed-placeholder coverage because those records were
not normalized. Slice 5 direct captures add `comment_placeholders` observations
for every supplied Arctic Shift `kind: "more"` node and unresolved child ID, so
new projections report the observed count without claiming completeness.

Focused Slice 4 verification passes 10 tests plus 3 subtests. The complete
Reddit Slices 0-4 set passes 52 tests plus 10 subtests. Python compileall and CLI
help pass, and the full repository suite passes 294 tests plus 22 subtests.
Coverage includes ordinary ordering, malformed and cyclic graphs, unknown
posts, deleted/removed bodies, duplicate fullnames, latest supplied
`num_comments`, pre-load/output limits, create-only mismatch refusal, missing
database refusal, and iterative export of a 1,500-level thread. No archive
schema, dependency, application runtime, frontend, build output, user database,
real data, or Git state was changed.

Exact commands and output semantics are in `REDDIT_MODULE_PLAN.md`.

## Completed Slices 5-8

The user approved the complete continuation on 2026-07-27. The implementation
landed as independently verified boundaries.

### Slice 5: bounded direct-link capture

- Added a finite-response Arctic Shift JSON client with one descriptive user
  agent, timeouts, retries, response-byte caps, and no concurrency or evasion.
- A Reddit post URL retrieves exactly that post ID and its bounded comment
  tree. It preserves unresolved `kind: "more"` IDs and reports incomplete
  coverage instead of claiming every comment was returned.
- A subreddit URL retrieves only about metadata, rules, wiki paths/pages, and
  subreddit image references. It never enumerates posts or comments.
- Stores create-only source responses and provenance, then normalizes through the
  existing post/comment and community import boundaries.
- Arctic Shift supplies no current moderator list. The capture reports that domain as
  unavailable unless the existing local moderator bundle is supplied.
- Do not scrape Reddit HTML, use official Reddit response bodies as permanent
  archive input, download media, or perform a live request in automated tests.

### Slice 6: offline library service

- Added a cohesive read-only query service and local CLI.
- Provides stable cursor-based post listings, bounded FTS search, post/thread
  detail, community reads, local-media references, and job/coverage summaries.
- Characterize equal-timestamp pagination, invalid cursors, query plans, empty
  domains, and large synthetic libraries.

### Slice 7: runtime module and API

- Added the Reddit descriptor at `<suite-home>/modules/reddit`.
- Always mounts `/api/reddit/*` and enforces enabled state without changing route
  presence.
- Freeze additive request/response behavior in the OpenAPI snapshot and API
  tests.

### Slice 8: custom local frontend

- Added a module-owned original Reddit-inspired surface.
- Infinite-scrolls locally archived posts with local search/filtering.
- Open one post with nested comments and explicit incomplete-capture warnings.
- Render only locally stored media; never hotlink remote thumbnails or assets.
- Verify loading, errors, scroll continuation, rapid navigation, and state
  restoration in a real timed browser.

## User's End Goal

The product is a local, offline, searchable Reddit library inside Keivotos. It
is not merely a media downloader and is not intended to remain a command-line
tool forever.

The user wants to:

1. Enter a Reddit name, URL, archive file, or related URL.
2. Choose how many posts to preserve, including scales such as 5,000 or
   500,000.
3. Preserve posts, post text, comments, available vote information, flair,
   scores, timestamps, pictures, galleries, video, previews, user avatars,
   subreddit assets, wiki pages, rules, moderator lists, and selected external
   assets.
4. Save the actual images and videos optionally rather than always hotlinking.
5. Search through locally saved posts and comments.
6. Build a custom Reddit-style interface over the preserved local data.
7. Keep the design capable of growing beyond Reddit's approximately
   1,000-result listing window.
8. Discuss and research each implementation slice before it is approved.

The user's preferred working loop is:

```text
Codex researches the next slice
-> Codex explains the options and proposed implementation
-> user says go, requests changes, or says they do not know
-> only then does Codex implement that slice
```

The module must stay local-first and single-user. It must not introduce
accounts, cloud sync, telemetry, remote-user assumptions, or surprise
downloads.

## How the URL Entry Point Should Behave

The URL is a capture seed and scope declaration, not merely a media link.

### Subreddit URL

Example:

```text
https://www.reddit.com/r/BlueArchive/
```

Intended behavior:

- identify the subreddit;
- acquire its historical posts from the selected historical source;
- optionally start or update a live watcher;
- capture subreddit metadata and selected community assets;
- respect the requested post limit or `all`;
- record coverage and source provenance.

Historical discovery must not depend exclusively on Reddit's listing API.

### Post URL

Example:

```text
https://www.reddit.com/r/BlueArchive/comments/<post-id>/<slug>/
```

Intended behavior:

- preserve the post;
- retrieve every obtainable comment and resolve comment placeholders;
- preserve the comment hierarchy;
- preserve post and comment metadata observations;
- optionally download images, galleries, previews, video, avatars, and
  external assets;
- capture enough subreddit and author context to render the post locally;
- record missing or unresolved comments instead of falsely reporting a
  complete capture.

### User URL

Example:

```text
https://www.reddit.com/user/<username>/
```

Intended behavior:

- preserve available posts and comments by that user from the selected source;
- keep author provenance and deletion state;
- apply stricter privacy and removal handling than a subreddit-only capture;
- never imply that another user's private saved, voted, or browsing history is
  accessible.

### Search or Listing URL

Intended behavior:

- preserve the original query, sort, and time filter;
- use the URL as a filter over an archive source or local index;
- record that search and listing results are not proof of complete subreddit
  coverage.

### Direct Image, Video, or External URL

Intended behavior:

- save the asset when the selected policy and the host's rules permit it;
- associate it with an originating post when that relationship is known;
- store source URL, response metadata, hashes, and capture time;
- avoid unbounded recursive crawling by default.

### Local Archive File

Intended behavior:

- import `.json`, `.jsonl`, `.ndjson`, `.jsonl.gz`, `.zst`, and Reddit account
  export formats through source-specific adapters;
- stream large files rather than loading them entirely into memory;
- resume after interruption;
- preserve raw source provenance;
- normalize records into the same local search model.

## What the Archive Should Preserve

### Posts

Preserve every source field that is useful and safe, including:

- Reddit ID and fullname;
- title;
- author name and author ID when supplied;
- creation and edit timestamps;
- score observations;
- upvote-ratio observations when supplied;
- comment-count observations;
- permalink and outbound URL;
- domain;
- self-post text and rendered text when supplied;
- post flair text, identifiers, colors, rich text, and emoji references;
- author flair;
- NSFW, spoiler, sticky, locked, archived, distinguished, removed, deleted,
  and moderation states;
- awards or gilding fields supplied by the source;
- poll data;
- suggested sort and contest state;
- crosspost parent and embedded parent data;
- thumbnail and preview variants;
- gallery metadata and gallery ordering;
- Reddit video manifests, fallback URLs, duration, size, and transcoding
  metadata;
- raw source payload and source-specific extra fields.

Gallery ordering must use the source's ordered gallery item list rather than
assuming that a metadata dictionary preserves the intended display order.

Crosspost parent data should be retained because the origin post or subreddit
may later become unavailable.

### Comments

Preserve:

- comment ID and fullname;
- post/link ID;
- parent comment or post ID;
- body and safe rendered form;
- author and author flair;
- creation and edit timestamps;
- score observations;
- score-hidden and controversiality fields when supplied;
- depth;
- OP, moderator, administrator, sticky, collapsed, removed, and deleted
  states;
- permalink;
- embedded links and media;
- the source and capture time for each observation.

Reddit comment responses may contain `more` placeholders rather than the
complete tree. A capture must either resolve them or record their unresolved
IDs and report that the tree is incomplete. It must never silently call a
partial tree complete.

### Subreddit and Community Context

Preserve when obtainable:

- name, ID, title, descriptions, creation date, subscriber observation, and
  community type;
- icon, banner, header, mobile banner, colors, and related visual assets;
- rules;
- public moderator list;
- wiki page list, page content, and revision metadata where authorized;
- link-flair and user-flair templates;
- emoji and rich-flair assets;
- legacy visual identity such as Old Reddit stylesheet references when capture
  is authorized;
- capture time and access status for every community artifact.

The attached proposal correctly emphasized that post/comment dumps generally
do not preserve the full community context. Community metadata is therefore a
separate acquisition domain.

### Media and External Assets

Media policy must be selectable:

```text
images: none | preview | original | both
videos: none | manifest | full
avatars: off | on
subreddit assets: off | on
external assets: off | linked-media | selected-domains
```

Every media record should include:

- original URL;
- final URL when redirects occur;
- source post/comment;
- media role;
- MIME type;
- byte size;
- content hash;
- capture time;
- success, missing, denied, or unsupported state;
- downloader identity and version where applicable.

Media should be content-addressed so reposted files and shared default avatars
deduplicate naturally.

External assets must be allowlisted and bounded. An external URL must not turn
into a surprise crawl of an entire site.

### User-Owned Local State

The custom Keivotos interface needs local user state that is separate from
Reddit's state:

- locally saved/bookmarked;
- favourite or precious;
- personal tags;
- notes;
- read/unread;
- hidden locally;
- keep-fresh preference;
- capture settings;
- watched subreddits;
- last viewed position.

A post may be saved in Keivotos even if the authenticated Reddit account never
saved it. Conversely, an imported Reddit `saved` flag is only an observation
of the authenticated account's state at capture time.

## Vote Information: What Is and Is Not Possible

The requested archive should preserve all vote information a source actually
provides, but the interface must not invent precision.

Commonly available fields include:

- post score;
- post upvote ratio;
- comment score;
- the authenticated user's own vote on an item: up, down, or none;
- the authenticated user's own saved state;
- historical raw fields supplied by third-party dumps;
- timestamped score observations from repeated captures.

What cannot be promised:

- exact public upvote count;
- exact public downvote count;
- identities of users who voted;
- exact vote history before capture;
- a faithful reproduction of Reddit's original `best` comment ordering.

Reddit has historically fuzzed or obscured vote totals. A derived estimate from
score and upvote ratio may be stored only as an explicitly labelled estimate.
The default interface should display the source score, ratio, and observation
time rather than fabricated exact counts.

For comments, the public data commonly provides only a score, not a reliable
upvote/downvote split.

The local search design should therefore use fields such as:

```text
score_observed
upvote_ratio_observed
my_vote
reddit_saved_observed
observation_time
source
raw_source_vote_fields
```

## The Approximately 1,000-Item Listing Problem

Reddit listings paginate with `after` and `before` cursors, but an upstream
listing normally exposes at most approximately 1,000 items and can sometimes
return fewer. The current live API documentation explains cursor pagination
but does not clearly promise access beyond that window.

Consequences:

- API pagination alone cannot discover an old 5,000-post or 500,000-post
  subreddit history.
- Scraping the same subreddit listing UI does not reveal a hidden unlimited
  history; the UI is backed by a similarly bounded listing.
- Combining `new`, `hot`, `top`, and time windows may add coverage, but it is
  not proof of completeness.
- The API can still be useful for known IDs and for collecting new posts before
  they fall out of the current listing window.

The correct separation is:

```text
historical discovery -> offline archive/dump or separately authorized bulk data
known-ID hydration   -> current approved source where permitted
future preservation -> continuous polling before records leave the window
```

## Acquisition Options Considered

| Source | Best use | Strengths | Main limitations |
| --- | --- | --- | --- |
| Approved Reddit Data API | Current data and continuous future capture | Current post/comment state, OAuth account observations, official endpoints | Listing depth, approval, rate limits, deletion obligations |
| Separate Reddit agreement | Official bulk access | Cleanest official route for large preservation | Requires negotiation and may cost money |
| Reddit for Researchers | Approved academic analysis | Five-year historical research dataset through BigQuery | Eligibility, six-month delay, research-only restrictions, end-of-project deletion |
| Reddit account export | Preserving one's own account | Own posts, comments, votes, preferences, and related account data | Not a subreddit export and not another user's data |
| Arctic Shift offline dumps | Historical bulk import | Suitable for hundreds of thousands or millions, local and reproducible | Unofficial, incomplete, privacy/provenance review, often not complete media |
| Arctic Shift limited API | Smaller filtered historical selection | Query by subreddit, time, IDs, or users without downloading a global dump | Unofficial, limited, no service guarantee, unsuitable as the sole 500k transport |
| Known-ID hydration | Refreshing records whose IDs are already known | Listing cap does not prevent requesting a known item | Does not discover unknown old IDs |
| gallery-dl | Images, galleries, previews, and supported embeds | Already bundled by Keivotos, mature media engine | Media-first; not the complete structural archive |
| yt-dlp integration | Reddit and external video | HLS/DASH handling and video/audio merging | Additional dependency and host-specific behavior |
| HTML or headless-browser scraping | Rendered public page extraction | Technically flexible | Brittle, slow, listing discovery still bounded, prohibited without Reddit consent |
| Moderator/author/community packages | High-integrity originals | Original media, wiki text, owned community assets | Requires cooperation; moderators cannot authorize Reddit scraping on Reddit's behalf |
| User URL/ID lists | Targeted preservation | Deterministic scope and easy resume | Only preserves URLs the user already knows |

## Recommended Source Strategy

No source provides complete post metadata, complete comment trees, historical
deleted states, current scores, Reddit-hosted media, external media, subreddit
assets, wikis, rules, and moderator information together.

The archive should therefore use source adapters that normalize into one local
model while keeping source-specific raw records.

### Around 5,000 Historical Posts

Recommended:

1. Use an Arctic Shift query or a filtered offline dump for historical
   discovery.
2. Optionally hydrate known post IDs from an approved current source.
3. Resolve or import comments.
4. Download selected media through gallery-dl and yt-dlp.
5. Capture community metadata separately.
6. Start a watcher for new posts.

The Reddit listing API alone is not acceptable for this target.

### Around 500,000 Historical Posts

Recommended:

1. Use an offline compressed dump or separately authorized bulk dataset.
2. Stream and filter it locally.
3. Store raw records in chunks and normalize incrementally.
4. Hydrate only selected, recent, or precious known IDs.
5. Queue media as a separate resumable phase.
6. Apply disk estimates and domain allowlists before media acquisition.

Do not send 500,000 records through a limited community archive API when a
bulk dump exists. Do not attempt to overcome the listing cap through browser
automation.

### Future Posts

Recommended:

1. Poll the approved current source on a configured interval.
2. Enumerate new IDs.
3. Store new records before they fall out of the listing window.
4. Revisit active posts on a decaying schedule to observe score and comment
   changes.
5. Record each refresh as an observation or revision.

Over time, the local archive can exceed 500,000 records even though any one
upstream listing is bounded.

## Proposed Capture Pipeline

The attached proposal identified a useful four-phase pattern. The revised
source-neutral form is:

1. **Enumerate**
   - Parse a URL, dump, account export, or ID list.
   - Produce canonical subreddit, post, comment, user, and asset IDs.
   - Record source coverage and missing ranges.

2. **Normalize and hydrate**
   - Preserve raw source records.
   - Map them into normalized posts, comments, users, communities, and
     observations.
   - Optionally refresh known IDs from an approved current source.

3. **Trees and community context**
   - Resolve or import comment relationships.
   - Record unresolved placeholders.
   - Capture rules, wiki, flair, moderators, and community metadata through a
     separately authorized source.

4. **Media**
   - Queue images, previews, video, avatars, flair emoji, subreddit assets, and
     selected external assets.
   - Download through maintained engines.
   - Hash, deduplicate, verify, and attach results.

Every phase must be:

- resumable;
- idempotent;
- safe to interrupt;
- progress-recorded;
- streaming rather than memory-bound;
- explicit about incomplete coverage;
- prevented from overwriting raw evidence silently.

## Provenance and Revisions

Different sources may disagree. The normalized database must not erase those
differences.

Every observation should record:

- source adapter;
- source URL or file;
- source record ID;
- capture timestamp;
- source record timestamp when present;
- raw-record hash;
- field confidence or availability;
- whether it came from Reddit, a third-party archive, a web archive, an account
  export, or a user-created package.

Post bodies, scores, comment counts, author state, moderation state, and media
availability change over time. Refreshing must not silently overwrite the only
copy of an earlier observation.

Suggested states for the future interface:

| State | Meaning |
| --- | --- |
| Not archived | No local record exists |
| Archived, incomplete | A record exists but known comments/assets/ranges are missing |
| Archived, stale | Current counters or edit state differ from the last capture |
| Archived, fresh | Last current-state check matches the stored observation |
| Historical only | Available from an archive but not current Reddit |
| Unavailable upstream | Known ID no longer resolves from the current source |

## Storage Direction

The Reddit module should follow Keivotos's durable-artifact and rebuildable
index philosophy.

Conceptual layout:

```text
<suite-home>/modules/reddit/
  archives/
    raw/
      <source>/<capture-id>/*.jsonl.gz
    communities/
      <subreddit>/
        about/
        rules/
        wiki/
        flair/
    posts/
      <prefix>/<post-id>/
        revisions/
        comments/
        manifest.json
  media/
    <hash-prefix>/<content-hash>.<ext>
  avatars/
    <hash-prefix>/<content-hash>.<ext>
  reddit.sqlite
```

The final exact layout must consume Keivotos's authoritative configured-path
and storage-layout boundaries. It must not hard-code the personal paths shown
in this handoff.

### Rebuildable Reddit Index

The proposed disposable `reddit.sqlite` should eventually contain normalized
and rebuildable tables such as:

- captures;
- capture_sources;
- capture_jobs;
- posts;
- post_observations;
- comments;
- comment_observations;
- comment_edges or materialized paths;
- authors;
- subreddits;
- wiki_pages and revisions;
- rules;
- moderator observations;
- flair definitions;
- assets;
- post/comment asset links;
- unresolved records;
- capture manifest;
- FTS5 search tables.

The archive must be rebuildable from durable raw records and manifests.

### Precious User State

User choices belong in additive `reddit_*` tables in the suite-owned precious
database, for example:

- `reddit_watched_subreddits`;
- `reddit_capture_settings`;
- `reddit_saved_posts`;
- `reddit_user_tags`;
- `reddit_notes`;
- `reddit_read_state`;
- `reddit_precious_posts`.

Exact schema work belongs in a later approved slice and must use additive
migrations. `user.sqlite` is never dropped or rebuilt.

### Attachment Boundary Correction

The current `backend/files_base/attachment_store.py` models user-authored Files
origin-note attachments. It is not automatically the correct storage engine
for Reddit post media.

Reddit media may later project into the Files base or claim Files records, but
the Reddit archive remains the source of truth for post/comment relationships.
Do not force Reddit media into the existing attachment store merely because
both concepts use the word "attachment."

## Local Search and Custom Reddit Interface

The end-state module should offer local full-text search across:

- post titles;
- post bodies;
- comment bodies;
- authors;
- subreddit names;
- post and author flair;
- domains;
- outbound URLs;
- wiki text;
- personal tags and notes.

Filters should include:

- subreddit;
- author;
- date range;
- score range;
- upvote-ratio range when available;
- post or comment;
- media type;
- flair;
- NSFW/spoiler;
- removed/deleted/current state;
- locally saved/favourite/precious;
- source and capture date;
- capture completeness.

Potential module-owned views:

- subreddit listing;
- nested thread;
- local search;
- wiki;
- user-within-archive;
- capture jobs;
- saved/precious;
- coverage and integrity status.

An Old Reddit-inspired dense layout is a strong initial design reference
because it naturally represents threaded discussion. It should be an original
local implementation, not a redistributed copy of Reddit's asset bundle or
branding.

Local sorting can reconstruct `new`, `old`, score-based `top`, and other
transparent sorts. Reddit's original `best` ranking cannot be reproduced
faithfully without the hidden vote data, so any approximation must be labelled
as local.

The frontend is deliberately not part of Slice 0.

## Current Reddit Policy and Preservation Conflict

This is the most important correction to the attached proposal.

### Data API deletion requirements

Reddit's Data API documentation says a client must remove posts and comments
that have been deleted from Reddit. When an account is deleted, identifying
account references, names, profile URLs, avatar URLs, flair, and similar
author-identifying information must also be removed. Reddit recommends
detecting and removing affected stored data within 48 hours and states that
retaining deleted content even after anonymization violates its terms.

That conflicts with:

- a permanent deleted-content restoration feature;
- the attached proposal's suggestion to merge live `[removed]` content with
  archived pre-removal text and keep it indefinitely;
- Keivotos's absolute rule never to delete or rewrite user archive data.

This conflict must be resolved explicitly before implementing a Reddit API
retention/synchronization slice. It cannot be hidden behind a technical design.

Possible categories to evaluate later include:

- terms-controlled API cache;
- user-imported offline archive;
- user-authored preservation package;
- separately licensed bulk data;
- a user-supplied structured archive observation.

These categories require legal and product-policy judgment, not merely a
database flag. This document does not make that judgment.

### Scraping

The Reddit User Agreement effective 2026-07-01 prohibits accessing, searching,
or collecting service data by automated or other means except as permitted by
the agreement or a separate Reddit agreement. It conditionally permits
robots.txt-compliant crawling but prohibits scraping without Reddit's prior
written consent.

Consequences:

- HTML scraping is not a clean workaround for denied API access.
- Headless-browser automation does not become permissible merely because it
  renders a normal browser.
- The design must not include proxy rotation, CAPTCHA bypass, identity
  disguise, rate-limit evasion, or private endpoint interception.
- Browser capture and replay are outside the approved product, not a Reddit
  acquisition fallback.

### Research access

The Reddit for Researchers program is limited primarily to sponsored,
non-commercial academic researchers affiliated with eligible institutions and
requires a research proposal and ethics review. It supplies a historical
dataset through BigQuery with a delay, but requires deletion of Reddit data and
derivatives when the project finishes except for narrow academic
record-keeping.

It is not a normal permanent personal-archive route.

## Keivotos Architecture Findings

### What fits

The attached proposal correctly identified several strong architectural fits:

- Keivotos is the suite; Reddit should be an optional module.
- Files remains the always-on base.
- Reddit needs its own rebuildable index and its own durable source records.
- The app should orchestrate maintained acquisition engines rather than invent
  a new scraping engine.
- User choices belong in the precious suite database.
- Disable/re-enable must preserve every byte.
- Media can eventually project into the Files base.
- FTS5 and a nested-thread viewer should first prove their shape inside the
  Reddit module rather than being prematurely extracted as supposedly shared
  frameworks.

### Registration correction

The attached proposal described registration as genuinely one line. In the
current tree, the descriptor factory entry may be one line, but a usable module
also needs:

- a module descriptor;
- router and API ownership;
- lifecycle/adoption/release behavior where applicable;
- frontend module surfaces;
- state and navigation integration;
- tests and additive OpenAPI coverage;
- documentation updates.

The module boundary is still the right architecture, but the complete
integration is not literally one line.

### Current backend correction

`backend/core.py` has been removed. Current composition is:

```text
app.py
-> backend/server.py
-> backend/app_factory.py
-> backend/lifecycle.py
```

New endpoints belong in routers. Reddit-specific behavior belongs under
`backend/modules/reddit/`. Shared helpers belong under `backend/services/`
only when they are genuinely shared.

No wildcard imports or new catch-all module may be introduced.

### Dependency findings

The current environment bundles `gallery-dl==1.32.6`.

The Reddit extractor can handle images, galleries, previews, embedded media,
comment expansion options, and video handoff. Video muxing requires
yt-dlp/youtube-dl integration.

PRAW remains absent. Slice 1 chose maintained `zstandard==0.25.0` for
bounded-memory standard `.zst` streaming. Slice 2 chose
`yt-dlp==2026.7.4` for stored Reddit DASH/HLS/file URLs and reused the existing
FFmpeg resolver. Both are pinned in `pyproject.toml` and `uv.lock`.

## Prior Art Mentioned in the Attached Proposal

The attached proposal referenced the following projects as design references:

- redarc;
- subreddit-archiver;
- BDFR;
- reddit-html-archiver;
- redd-archiver;
- reddit-user-to-sqlite.

The proposal suggested learning from:

- dump ingestion plus live polling;
- resumable SQLite import;
- static offline rendering;
- nested-thread presentation;
- author/date/score filtering;
- simple relational schemas.

These projects were not all revalidated during the 2026-07-26 web research.
Before adopting code, dependencies, or schema ideas from any of them, the next
task must confirm current maintenance state, license, data assumptions, and
compatibility with Reddit's current policies.

## Proposed End-to-End Slice Sequence

The sequence below reflects the revised end goal. Each slice must be researched,
proposed, approved, implemented, verified, and handed back before the next
slice begins.

### Slice 0: Offline capture foundation

- URL and target parser.
- Streaming import contract.
- Raw provenance records.
- Rebuildable local archive schema.
- FTS search foundation.
- Resume and idempotency.
- CLI guide.
- No live network operations.

### Slice 1: Historical discovery beyond 1,000

- **Implemented 2026-07-27.**
- Streaming Arctic Shift standard `.zst` dump adapter; no automated dump
  download and no `.zst_blocks` support.
- Subreddit/date/user/URL target filtering, with `scoped` and `global` source
  modes.
- Optional published SHA-256 verification before archive writes.
- Deterministic coverage reporting.
- Official Reddit OAuth Listing discovery for smaller/current jobs, bounded to
  1,000 IDs/URLs and never admitted as raw API bodies.
- Discovery-manifest filtering for local submission and comment dumps.
- Small generated real-codec fixtures plus pagination/retry/rate-limit mocks;
  no live or large-data verification.

### Slice 2: Media and external asset queue

- **Implemented 2026-07-27 for Reddit-hosted assets.**
- Offline deterministic planning plus exact count/selection-hash confirmation.
- gallery-dl direct Reddit images, bounded recognized-CDN HTTP fallback, and
  pinned yt-dlp plus existing FFmpeg for stored `v.redd.it` URLs.
- Finite file/run/disk/retry/timeout limits, resumable partials, preserved
  invalid/oversized output.
- Create-only SHA-256 objects and manifests, verified deduplication, and
  append-only acquisition events.
- Arbitrary external-domain acquisition deliberately deferred to its own
  allowlisted adapter.

### Slice 3: Community context

- **Implemented 2026-07-27.**
- Local Arctic Shift community corpus/bundle import for subreddit
  about metadata, rules, and wiki pages, plus an optional local moderator
  snapshot bundle.
- Versioned observations, raw provenance, coverage, and icon/banner asset
  queuing.
- Live Arctic Shift and official OAuth community acquisition remain separate
  later adapters.

### Slice 4: Comment trees and completeness

- **Implemented 2026-07-27.**
- Deterministic offline trees and create-only JSON export from
  existing normalized comments.
- Missing-parent, orphan, cycle, depth, placeholder, and
  declared-versus-observed completeness reporting.
- Bounded Arctic Shift known-post trees and official OAuth thread expansion
  remain separate network alternatives.
- Known-ID refresh, live tailing, and permanent API-backed observations remain
  blocked on an explicit retention policy.

### Slice 5: Bounded direct-link capture

- **Implemented 2026-07-27.**
- Arctic Shift post-ID and bounded comment-tree capture for a post URL.
- Arctic Shift about/rules/wiki capture for a subreddit URL, with no post
  enumeration.
- Create-only structured response provenance and explicit unresolved-comment
  coverage.
- No Reddit HTML scraping, web-archive/replay adapter, live automated test, or
  media download.

### Slice 6: Offline library query service

- **Implemented 2026-07-27.**
- Read-only cursor-paginated listing, FTS search, detail/thread, community,
  local-media, and job coverage queries plus a local CLI.
- Golden response shapes, query-plan checks, and large synthetic pagination.

### Slice 7: Reddit runtime backend

- **Implemented 2026-07-27.**
- Module descriptor, archive location, registry, enabled-state, and
  `/api/reddit/*` router integration.
- Additive OpenAPI snapshot and API response compatibility tests.

### Slice 8: Custom Reddit-style frontend

- **Implemented 2026-07-27.**
- App drawer entry and original local Reddit-inspired surface.
- Infinite saved-post feed, nested comment viewer, local search/filters,
  capture coverage, and local-media-only rendering.
- Real timed browser verification for scrolling, interaction, and state
  restoration.

### Later: User state, rebuild, recovery, and scale

- Additive `reddit_*` user tables.
- Rebuildable index command.
- Backup and recovery integration.
- Kill/resume verification.
- 500k-library query and rendering benchmarks.
- Removal/privacy controls based on the explicitly chosen policy.

This revised sequence replaces the attached proposal's emergency live-capture
first slice because the user first requested a guide and because current policy
research exposed unresolved API-retention conflicts.

## Completed Slice 0 Plan

This is the plan approved by the user and implemented after this handoff was
first created.

### Intended files

```text
scripts/reddit_capture.py
backend/modules/reddit/archive.py
backend/modules/reddit/url_targets.py
tests/test_reddit_capture.py
docs/important/REDDIT_MODULE_PLAN.md
docs/important/FEATURES.md
docs/important/FEATURE_CODE_MAP.md
docs/important/CHANGELOG.md
```

The implementation stayed within this file list. This handoff was updated
afterward to keep the continuation state accurate.

### Initial CLI contract

```text
--url URL
--subreddit NAME
--posts 5000|500000|all
--comments none|all
--source-file PATH
--save-images none|preview|original|both
--save-videos none|manifest|full
--save-avatars
--save-subreddit-assets
--save-wiki
--save-rules
--save-mod-list
--save-external-assets
--external-domain DOMAIN
--database PATH
--media-directory PATH
--resume
```

The preservation switches form a forward-compatible job manifest in Slice 0.
Network and media adapters may fulfil them in later slices.

### Slice 0 boundaries

Slice 0 should:

- parse supported target URLs;
- canonicalize subreddit, post, user, search, archive, and asset targets;
- create a source-neutral capture job;
- stream local source records;
- store raw provenance;
- normalize posts and comments;
- preserve comment relationships;
- create an FTS5 index;
- record desired media/community capture policies;
- resume without duplication;
- support large counts without holding the corpus in memory;
- produce a user guide.

Slice 0 should not:

- contact Reddit;
- contact Arctic Shift;
- contact a web-capture or replay service;
- download images or video;
- register a runtime Reddit module;
- modify the frontend;
- modify the live Keivotos database;
- start or restart the app;
- add PRAW or yt-dlp;
- perform a real 5k or 500k network operation.

### Completed verification

- URL-type characterization tests.
- Canonical-ID tests.
- Streaming JSONL import fixture.
- Comment parent/child reconstruction fixture.
- Duplicate and idempotent re-import tests.
- Interrupted-job resume test.
- Full-text search tests.
- Media-policy manifest tests.
- Isolated temporary filesystem and SQLite use only.
- Python compile verification for affected files.
- Targeted tests followed by the proportionate repository test set.
- Read-only diff inspection.

No real network capture was part of Slice 0 verification. The completed
evidence is:

```text
targeted: 11 passed, 3 subtests passed
full suite: 253 passed, 15 subtests passed
compileall: passed
```

## Suggested CLI Direction Beyond Slice 0

The final command names are not approved, but the source-neutral model should
be able to express:

```text
reddit_capture capture --url <url> --source auto
reddit_capture import --source arctic-dump --input <file.zst>
reddit_capture import --source reddit-export --input <export.zip>
reddit_capture hydrate --input <post-ids.txt>
reddit_capture watch --url <subreddit-url>
reddit_capture media --job <capture-id>
reddit_capture search <query>
reddit_capture rebuild
```

Possible source identifiers:

```text
auto
arctic-dump
arctic-api
reddit-live
reddit-ids
reddit-export
url-list
community-package
```

`auto` must never hide a surprise large download. It should produce a plan and
require an explicit acquisition action when the selected source is large or
network-heavy.

## Outstanding Decisions

Slice 1 resolved two earlier questions: standard `.zst` uses
`zstandard==0.25.0`, and the official API path is hard-capped at 1,000 Listing
items rather than being treated as a historical transport. Source choice is
always explicit; `auto` does not download anything.

These decisions remain open and should be discussed at the relevant slice:

1. Should `AIcrack`, used in the user's successful manual Arctic Shift query,
   be the first explicitly approved live/large-data validation target?
2. Should comments remain default-all or become an explicit required choice?
3. Should images default to none, previews, originals, or both?
4. Should video default to manifest-only because of disk cost?
5. Which external domains, if any, are allowed initially?
6. How should authenticated personal `saved` and `my_vote` observations be
   imported?
7. How will current Reddit deletion requirements be reconciled with
    Keivotos's never-delete archive contract?
8. Will removed/deleted historical material be supported at all, and under
    what source and policy category?
9. When should Reddit media project into the Files base?
10. Should the first frontend skin be Old Reddit-inspired or a new custom
    design?
11. When should client-side permalink routing be scheduled? It must not be
    silently folded into the module.

The variable 5k/500k scale is not a decision that must be fixed globally. The
architecture should support both through different source adapters and job
policies.

## Instructions for the Next Codex Task

Start in:

```text
D:\Kivotos\Github_Wakaru\Keivotos-Modulo\Reddit
```

Then:

1. Read the root `AGENTS.md`.
2. Read this document completely.
3. Before changing the planned feature, reread:
   - `docs/important/FEATURES.md`;
   - `docs/important/FEATURE_CODE_MAP.md`;
   - `docs/important/MODULAR_ARCHITECTURE_PLAN.md`;
   - `docs/important/SUITE_MODULE_CONTRACT.md`;
   - `docs/important/REDDIT_MODULE_PLAN.md`;
   - any additional reference routed by those documents.
4. The directory currently has no `.git`. Do not recreate it or require Git;
   preserve all user files and unrelated changes.
5. Treat Slices 0 through 8 as complete and do not redo them.
6. Start only a newly requested slice; the approved no-web-archive module plan
   is complete.
7. Do not perform live Reddit, Arctic Shift, web-capture, replay, or media
   operations unless separately and explicitly requested.
8. Do not stage, commit, branch, push, tag, package, or publish. The user
   explicitly does not want a commit handoff for this separate tree.
9. After a verified slice, update this handoff and
   `REDDIT_MODULE_PLAN.md`, then report:
    - what changed;
    - what was verified;
    - whether the app was restarted;
    - which real-data and network operations were intentionally not run.

Suggested opening prompt for a new task:

```text
Read AGENTS.md, docs/important/REDDIT_MODULE_HANDOFF.md, and
docs/important/REDDIT_MODULE_PLAN.md completely. Treat Reddit Slices 0 through
8 as implemented and verified. Do not invent a continuation slice or introduce
web-archive/replay tooling. Run live network operations only when the user asks
for them explicitly. Reddit's yt-dlp subprocess mechanics are shared through
backend/services/yt_dlp.py, but its provider/storage policy remains
module-owned. This tree intentionally has no Git handoff.
```

## Researched Primary and Project Sources

### Reddit

- Developer access and data interfaces:
  <https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data>
- Reddit Data API rules, deletion requirements, OAuth requirements, and rate
  limits:
  <https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki>
- Live Reddit API documentation:
  <https://www.reddit.com/dev/api/>
- Data API Terms:
  <https://redditinc.com/policies/data-api-terms>
- User Agreement:
  <https://redditinc.com/policies/user-agreement>
- Reddit for Researchers:
  <https://support.reddithelp.com/hc/en-us/articles/49381918834964-Reddit-for-Researchers-Program>
- Reddit account data request:
  <https://support.reddithelp.com/hc/en-us/articles/360043048352-How-do-I-request-a-copy-of-my-Reddit-data-and-information>
- Archived Reddit JSON field documentation:
  <https://github.com/reddit-archive/reddit/wiki/json>

### Acquisition and archives

- Arctic Shift project, dumps, limited API, and removal-request information:
  <https://github.com/ArthurHeitmann/arctic_shift>
- Arctic Shift record-format and retrieval metadata:
  <https://github.com/ArthurHeitmann/arctic_shift/blob/master/file_content_explanations.md>
- Arctic Shift current download index and published hashes:
  <https://github.com/ArthurHeitmann/arctic_shift/blob/master/download_links.md>
- Arctic Shift community record schemas:
  <https://github.com/ArthurHeitmann/arctic_shift/tree/master/schemas/subreddits>
- Arctic Shift community API endpoints and stated no-guarantee boundary:
  <https://github.com/ArthurHeitmann/arctic_shift/tree/master/api>
- January 2025 subreddit metadata/rules/wiki corpus description:
  <https://www.reddit.com/r/pushshift/comments/1ithjd3/subreddits_metadata_rules_and_wikis_202501/>
- `zstandard` 0.25.0 package:
  <https://pypi.org/project/zstandard/0.25.0/>
- Python-zstandard streaming decompression:
  <https://python-zstandard.readthedocs.io/en/latest/decompressor.html>
- yt-dlp package, dependency, and license information:
  <https://pypi.org/project/yt-dlp/>
- yt-dlp format merging and FFmpeg requirements:
  <https://github.com/yt-dlp/yt-dlp/blob/master/README.md>
- gallery-dl Reddit and media configuration:
  <https://github.com/mikf/gallery-dl/blob/master/docs/configuration.rst>
- PRAW submission fields:
  <https://praw.readthedocs.io/en/stable/code_overview/models/submission.html>
- PRAW comment-tree handling:
  <https://praw.readthedocs.io/en/stable/tutorials/comments.html>

### Local API and search

- FastAPI module-owned `APIRouter` composition:
  <https://fastapi.tiangolo.com/tutorial/bigger-applications/>
- FastAPI streamed and file responses:
  <https://fastapi.tiangolo.com/advanced/custom-response/>
- SQLite FTS5 ranking, snippets, and highlighting:
  <https://www.sqlite.org/fts5.html>

## Final Handoff Summary

The proposed Reddit module is an offline preservation and search system whose
primary input is a URL or archive source. It must support both small and very
large histories without relying on Reddit's bounded listings. Historical
discovery, current observations, comments, community context, and media are
separate acquisition domains joined through IDs and explicit provenance.

The recommended long-term combination is:

```text
past history   -> offline archive/dump
known records  -> permitted current-state hydration
future posts   -> continuous approved collection
media          -> confirmed bounded gallery-dl/yt-dlp object acquisition
community      -> local Arctic Shift community corpus/bundle import
local product  -> rebuildable SQLite index + FTS5 + precious user state
```

The most important unresolved issue is not technical: permanent preservation
of deleted Reddit content conflicts with current Reddit API deletion rules and
with Keivotos's never-delete contract. That policy must be decided explicitly
before an API-backed retention feature is implemented.

Slices 0 through 8 are complete: bounded Arctic Shift direct-link capture, the
offline library service, runtime registration/API, and the custom infinite
local feed now sit on the earlier preservation foundation. No operation may
silently run a live request, download media, ingest a large dump, or introduce
web-capture/replay tooling.
