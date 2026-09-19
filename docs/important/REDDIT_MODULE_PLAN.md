# Reddit Module Capture Guide

## Current implemented boundary

Reddit fork Slices 0 through 8 form a registered, optional, local-first
Keivotos module. Slice 0 established the durable local archive. Slice 1 added
streaming Arctic Shift `.zst` ingestion and bounded official Reddit API
discovery. Slice 2 added explicitly confirmed, bounded acquisition of
already-queued Reddit-hosted media. Slice 3 added offline community
about/rules/wiki and optional moderator-snapshot import. Slice 4 added a
read-only comment-tree integrity and JSON export layer. Slice 5 added bounded
direct post/community capture through Arctic Shift's structured JSON API.
Slice 6 added the read-only library. Slice 7 registered `/api/reddit/*`, and
Slice 8 added the infinite local Reddit-inspired surface. The approved in-app
follow-up added a serialized capture endpoint and animated Save link drawer.
The approved media follow-up adds truthful indexed receipts, outbound link
cards, explicitly confirmed Images/GIFs, Videos, and Linked-files acquisition,
and automatic publication of friendly downloaded files into the Files base.
The approved Settings follow-up adds a sixth Reddit category with persistent
Save-link defaults and read-only archive, runtime, storage, Files-publication,
provider-scope, and safety-limit information.

### 2026-07-28 shared yt-dlp boundary

The later Karaoke/YouTube work extracted only Reddit's generic yt-dlp process
mechanics into `backend/services/yt_dlp.py`: command resolution, invariant
ignore-config/no-playlist/no-overwrite/resume/retry/socket-timeout/FFmpeg
arguments, shell-free execution, bounded error output, progress/cancellation,
and redaction. `backend/modules/reddit/media.py` still owns every Reddit
provider rule, queue/selection rule, destination, byte/free-space limit,
receipt, and object-install decision. The command ordering that restores
`--continue` after yt-dlp's `--no-overwrites` implication remains covered.

This is not a new Reddit acquisition mode. Karaoke and YouTube have separate
descriptors, APIs, storage, and indexes; Reddit does not import either module
or gain a cross-module download path. No Reddit media URL was opened while
making or verifying the extraction.

Implemented:

- parse subreddit names and supported Reddit, redd.it, asset, and external
  URLs without opening them;
- accept a local `.json`, `.jsonl`, `.ndjson`, or gzip-compressed JSONL source;
- stream JSONL sources in bounded chunks;
- preserve every nonblank source record in atomic gzip-compressed raw chunks;
- verify every raw chunk by SHA-256;
- normalize matching posts and comments into a rebuildable SQLite index;
- retain timestamped post/comment observations and source provenance;
- preserve comment parent IDs and depth;
- apply a maximum number of distinct post IDs to post or comment-only sources;
- index post and comment text with SQLite FTS5;
- record the authenticated account's supplied `likes`/`saved` observations
  without treating them as public vote totals;
- queue selected image, preview, video-manifest, avatar, and allowlisted
  external URLs without downloading them;
- store requested wiki, rules, moderator-list, subreddit-asset, and media
  policies in the post/comment capture manifest;
- resume an interrupted job from the last committed source line;
- make repeated resume safe and duplicate-free.
- stream standard Arctic Shift `.zst` JSONL without loading the dump into
  memory;
- optionally verify the source's published SHA-256 before creating archive
  state;
- apply inclusive `--after` and exclusive `--before` UTC date boundaries;
- distinguish already-scoped dumps from global dumps, pre-filtering a global
  source before raw chunks are written;
- write deterministic source coverage beside every `.zst` job;
- discover a current subreddit, search, or user Listing through official OAuth,
  following `after` cursors for at most 1,000 unique items;
- honor Reddit rate-limit/reset and retry headers without proxying, concurrency,
  or limit evasion;
- store API credentials only in environment variables and save only a minimal
  create-only ID/URL discovery manifest;
- use that discovery manifest to select matching submissions and all comments
  linked to those submissions from local Arctic Shift dumps;
- plan a deterministic Reddit-hosted media run without opening a network URL or
  creating the destination;
- bind a download confirmation to both the exact selected count and the
  selection SHA-256;
- download supported `i.redd.it` and `preview.redd.it` images with gallery-dl,
  recognized Reddit CDN images with a bounded HTTP fallback, and already-stored
  `v.redd.it` DASH/HLS/file URLs with pinned yt-dlp plus the existing FFmpeg;
- enforce finite file-count, per-file, run-byte, timeout, retry, and reserved
  free-space limits;
- validate completed images, preserve failed/oversize outputs and resumable
  partials, and never silently discard a downloader result;
- install completed bytes create-only in a SHA-256 object store, deduplicate
  identical bytes, write create-only observation manifests, and append
  started/complete/failed events to the rebuildable Reddit index;
- import user-supplied local Arctic Shift community about, rules, and wiki
  JSON/JSONL/`.zst` records without calling a data service;
- import an optional module-owned local moderator snapshot bundle with an
  explicit format instead of pretending Arctic Shift supplies moderators;
- preserve community raw records, source provenance, ordered rule snapshots,
  wiki revisions, about observations, and moderator snapshots as versioned
  observations;
- write deterministic coverage for every community job and resume interrupted
  imports without duplicating records;
- queue recognized subreddit icon and banner URLs for the separately confirmed
  Slice 2 media workflow without downloading them;
- inspect one already-imported post's comments through a read-only SQLite
  connection without changing the archive;
- project deterministic parent/child order while preserving every normalized
  comment exactly once, including malformed and detached components;
- report missing, invalid, ambiguous, self, and cross-post parents; cycles,
  duplicate identities/fullnames, stored-versus-derived depth, unknown posts,
  deleted/removed bodies, and declared-versus-observed comment counts;
- represent missing parents as explicit local placeholders;
- export deeply nested threads with an iterative JSON encoder, create-only
  verification, and finite comment/output-byte limits;
- reject WARC/WACZ/Wayback targets and every related capture or replay path;
- capture exactly one requested post plus a bounded comment tree, or one
  subreddit's about/rules/wiki/image context without enumerating its posts;
- preserve exact direct-source JSON responses, hashes, source URLs, timing,
  limits, and coverage before normalization;
- preserve Arctic Shift `kind: "more"` IDs in additive
  `comment_placeholders` rows and expose their unresolved count;
- list saved posts with stable keyset cursors and subreddit/author/flair
  filters, search posts/comments with bounded FTS5, and read post/thread,
  community/history, local-media, and capture-status projections;
- expose the read-only library through enabled-state-gated `/api/reddit/*`
  routes, including contained SHA-256 local media with range support;
- show the archive in a module-owned Reddit-inspired Svelte surface with an
  infinite local feed, search, thread, and community views;
- keep remote URLs as evidence only: the runtime renders local media endpoints
  and never hotlinks them;
- prove a post capture against the local index and report its actual archived
  comment count instead of trusting the source bundle's summary;
- show all valid outbound URLs as inert link cards without remote preview
  requests;
- plan and explicitly confirm owner-scoped image/GIF, video, and Linked-files
  downloads in the UI;
- resolve MediaFire single-file metadata through pinned `mfget`, and stream
  it plus ordinary HTTPS file URLs through Keivotos's finite byte, disk,
  timeout, retry, redirect, and public-DNS guards;
- reject HTML pages, private/non-public targets, and unsupported folder/page
  links as downloads while leaving them visible to open;
- materialize friendly filenames under `media/library` and publish that exact
  module-declared root as **Reddit downloads** in the Files base;
- prefill each Save-link drawer from local Images/GIFs, Videos, Linked-files,
  and retry-failed defaults managed by the sixth Settings category;
- expose archive totals, jobs, current capture/download activity, exact module
  storage paths, and the backend's finite limits through the read-only status
  view used by Settings.

Not implemented:

- permanent preservation of Reddit API response bodies;
- WARC, WACZ, browser-capture, replay, Wayback, and Common Crawl adapters
  (explicitly outside the approved product);
- resolution of `more` placeholders beyond the IDs supplied by the bounded
  direct response;
- a real/live media acquisition run;
- automatic downloading of arbitrary HTML pages, private/login-required links,
  or linked folders;
- live current moderator acquisition;
- subreddit flair, emoji, widget, and stylesheet acquisition;
- Reddit-specific `user.sqlite` tables beyond shared module enablement;
- live watcher;
- deletion/removal synchronization;
- real-data 500,000-record performance verification.

The unsupported items require their own researched and approved slices. Direct
capture uses finite Arctic Shift endpoints only after the user supplies
`--arctic-shift-api`; ordinary imports, reads, and the Keivotos runtime never
silently depend on that service's uptime.

## Source strategy

Reddit listings cannot be trusted to discover more than approximately 1,000
items, and current Reddit terms create unresolved retention constraints for
deleted API content. Starting with a source-neutral local importer makes the
archive format usable with 5,000 or 500,000 records without prematurely
choosing a live service or silently promising noncompliant retention.

Durable post/comment preservation can use user-supplied local files or the
explicit bounded Arctic Shift adapter. Direct response bodies are preserved as
exact create-only source evidence before they pass through the same normalizer.
Official Reddit API mode remains a separate discovery operation: it writes IDs
and canonical URLs, not response bodies, and a later local `.zst` import can
consume that selection. Input dumps remain unchanged. Media is a separate,
explicitly confirmed phase that consumes only URLs already queued by an import;
planning it does not create the media directory. Community context is versioned
separately because about metadata, rules, wiki pages, and moderator membership
change independently of posts.
Slice 4 and the runtime library consume normalized local rows and never edit
their parent/depth facts. Cycle breaks and detached roots exist only in the
exported projection. Slice 5's schema-version-2 migration only adds the
`comment_placeholders` evidence table and its index; it does not rebuild or
drop existing archive content.

### Approved source boundary (2026-07-27)

The user explicitly rejected WARC/WACZ and related web-capture or replay
technology for this module. The approved design therefore has no WARC, WACZ,
Wayback, Common Crawl, Browsertrix, browser-session capture, or replay adapter.
Those formats and services are not fallbacks.

The direct-link workflow uses explicit structured sources:

- a Reddit post URL selects exactly one post and its comments;
- a subreddit URL selects community about metadata, rules, wiki pages, and
  subreddit image references, never the subreddit's post listing;
- local JSON/JSONL/gzip/Arctic Shift `.zst` remains an import source;
- the approved network adapter is the bounded Arctic Shift JSON API;
- Reddit HTML is not scraped, and official Reddit API response bodies are not
  placed in the permanent archive.

Arctic Shift does not publish current moderator membership. Subreddit capture
must report that domain as unavailable unless a user supplies the existing
versioned local moderator snapshot bundle. It must never silently substitute an
old or inferred moderator list.

## Command

Use the repository's locked Python 3.11 environment:

### Capture a Reddit link directly

For one post and its bounded comment tree:

```text
.venv\Scripts\python.exe scripts\reddit_capture.py ^
  --url https://www.reddit.com/r/BlueArchive/comments/<post-id>/<slug>/ ^
  --arctic-shift-api
```

For subreddit context only:

```text
.venv\Scripts\python.exe scripts\reddit_capture.py ^
  --url https://www.reddit.com/r/BlueArchive/ ^
  --arctic-shift-api
```

The second command retrieves about metadata, rules, wiki paths/pages, and
subreddit image references only. It never calls a post or comment listing
endpoint. Direct captures preserve exact JSON responses and a verified manifest
under `<module-home>/archives/direct/<capture-id>/`; the default index is
`<suite-home>/modules/reddit/reddit.sqlite`. Use `--arctic-max-comments`,
`--arctic-max-wiki-pages`, `--arctic-max-response-bytes`, and
`--arctic-timeout` to reduce the finite defaults. Direct capture only queues
recognized media references; downloading them remains the separately confirmed
media command.

The same direct workflow is available inside the enabled Reddit module. Select
**Save link** immediately after Refresh, paste one post or subreddit URL, and
submit. The right-side drawer remains open while the bounded request runs and
shows the saved record counts or the exact failure. On success the local feed
and archive status refresh automatically. This is an explicit network action;
opening or browsing the Reddit surface never contacts Arctic Shift.

The sixth **Reddit** category in application Settings controls only the initial
Save-link media checkboxes and retry-failed choice. It also reads local status
to show archive counts, recent jobs, active capture/download state, database and
media/Files paths, and the exact fixed safety limits. Opening Settings does not
capture, download, rebuild, or delete anything.

### Import a local post/comment source

```text
.venv\Scripts\python.exe scripts\reddit_capture.py ^
  --url https://www.reddit.com/r/BlueArchive/ ^
  --source-file D:\archives\bluearchive-posts.jsonl.gz ^
  --posts 5000 ^
  --comments all ^
  --database D:\archives\bluearchive\reddit.sqlite
```

The equivalent subreddit-name form is:

```text
.venv\Scripts\python.exe scripts\reddit_capture.py ^
  --subreddit BlueArchive ^
  --source-file D:\archives\bluearchive-posts.jsonl ^
  --posts 500000 ^
  --comments all ^
  --database D:\archives\bluearchive\reddit.sqlite
```

`--posts all` removes the distinct-post limit. For 500,000-scale data, use
JSONL/NDJSON, gzip-compressed JSONL, or Arctic Shift `.zst`. A normal `.json`
array is supported for small exports but is loaded as one JSON value and is
therefore not the large-corpus format.

### Stream a local Arctic Shift dump

For an already subreddit-scoped dump:

```text
.venv\Scripts\python.exe scripts\reddit_capture.py ^
  --subreddit AIcrack ^
  --source-file D:\archives\AIcrack_submissions.zst ^
  --source-format arctic-zst ^
  --source-scope scoped ^
  --after 2024-01-01 ^
  --before 2026-01-01 ^
  --expected-sha256 <published-64-digit-sha256> ^
  --posts 500000 ^
  --database D:\archives\AIcrack\reddit.sqlite
```

Use `--source-scope global` for a multi-subreddit dump. In that mode only
records matching the requested target survive into raw archive chunks.
`--after` is inclusive at midnight UTC; `--before` is exclusive.

Every `.zst` job writes `coverage.json` beside its raw chunks. An optional
`--coverage-json PATH` creates an identical report at another create-only
location.

### Discover the current official Reddit Listing

Reddit currently requires an approved OAuth app and a truthful, descriptive
User-Agent. Keep secrets out of command history:

```text
set REDDIT_CLIENT_ID=your-client-id
set REDDIT_CLIENT_SECRET=your-client-secret
set REDDIT_USER_AGENT=windows:keivotos-reddit:v0.1 (by /u/yourname)

.venv\Scripts\python.exe scripts\reddit_capture.py ^
  --subreddit AIcrack ^
  --reddit-api ^
  --posts 1000 ^
  --reddit-api-output D:\archives\AIcrack\current-discovery.json
```

The client requests at most 100 items per page, follows the returned `after`
cursor, deduplicates fullnames, refuses repeated cursor loops, and caps the
whole traversal at 1,000. A Listing can end earlier, so the JSON summary reports
the exact page/item counts and stop reason.

The output contains no titles, bodies, authors, votes, media metadata, OAuth
tokens, or raw API responses. It can select durable content from local
submission and comment dumps:

```text
.venv\Scripts\python.exe scripts\reddit_capture.py ^
  --subreddit AIcrack ^
  --source-file D:\archives\AIcrack_submissions.zst ^
  --discovery-manifest D:\archives\AIcrack\current-discovery.json ^
  --posts all ^
  --database D:\archives\AIcrack\reddit.sqlite
```

Run the same selection against the matching comment dump to retain comments
whose `link_id` belongs to a discovered post.

### Plan and download queued Reddit-hosted media

First produce a no-network plan:

```text
.venv\Scripts\python.exe scripts\reddit_media.py plan ^
  --database D:\archives\AIcrack\reddit.sqlite ^
  --destination D:\archives\AIcrack\media ^
  --max-files 100 ^
  --max-file-bytes 2GiB ^
  --max-run-bytes 10GiB ^
  --min-free-bytes 5GiB
```

The JSON reports queue/rejection counts, selected engine/role/host breakdowns,
a query-free preview of up to 25 selected asset identities, disk availability,
the conservative bytes required to start, and this exact confirmation pair:

```text
"confirm_assets": <selected count>
"selection_sha256": "<64-digit selection hash>"
```

Nothing is downloaded until a separate command repeats the same selection
options and supplies both values:

```text
.venv\Scripts\python.exe scripts\reddit_media.py download ^
  --database D:\archives\AIcrack\reddit.sqlite ^
  --destination D:\archives\AIcrack\media ^
  --max-files 100 ^
  --max-file-bytes 2GiB ^
  --max-run-bytes 10GiB ^
  --min-free-bytes 5GiB ^
  --confirm-assets <selected-count> ^
  --confirm-selection <selection-sha256>
```

If the queue changes while keeping the same count, the hash check still fails.
Failed assets are excluded from later plans unless `--retry-failed` is passed.
`--role ROLE` is repeatable when only a specific queued role should run.

Slice 2 accepts recognized Reddit-hosted image roles on Reddit CDN hosts and
video roles on `v.redd.it`. It rejects the generic `external` role and every
unrecognized host, non-HTTPS URL, custom port, or credential-bearing URL.
gallery-dl and yt-dlp ignore user configuration, use finite retries and
timeouts, and receive only the already-stored media URL; they do not revisit
the Reddit post or Listing API. The HTTP fallback additionally rejects
redirects outside recognized Reddit image hosts and non-public DNS results.

### Import local subreddit community context

Import about metadata from a multi-subreddit Arctic Shift source:

```text
.venv\Scripts\python.exe scripts\reddit_community.py ^
  --subreddit AIcrack ^
  --source-type about ^
  --source-file D:\archives\community\subreddits.zst ^
  --source-scope global ^
  --expected-sha256 <published-64-digit-sha256> ^
  --database D:\archives\AIcrack\reddit.sqlite
```

Use a separate command for each rules or wiki source:

```text
.venv\Scripts\python.exe scripts\reddit_community.py ^
  --subreddit AIcrack ^
  --source-type rules ^
  --source-file D:\archives\community\rules.zst ^
  --source-scope global ^
  --database D:\archives\AIcrack\reddit.sqlite

.venv\Scripts\python.exe scripts\reddit_community.py ^
  --subreddit AIcrack ^
  --source-type wiki ^
  --source-file D:\archives\community\wikis.zst ^
  --source-scope global ^
  --database D:\archives\AIcrack\reddit.sqlite
```

`--source-scope global` filters non-target subreddits before raw preservation.
`--source-scope scoped` treats the whole nonblank input as already selected and
preserves wrong-target or malformed records as evidence while recording errors.
Both modes accept `.json`, `.jsonl`, `.ndjson`, gzip JSONL, and `.zst`; plain
JSON is intended for small bundles because it is loaded as one JSON value.
Every community job writes coverage. `--coverage-json PATH` writes the same
report to another create-only location, `--expected-sha256` verifies the whole
source before archive writes, and `--resume` continues the exact same job.

Arctic Shift does not supply moderator membership. An optional local snapshot
must use this module-owned JSON shape:

```json
{
  "format": "keivotos-reddit-moderators-v1",
  "subreddit": "AIcrack",
  "retrieved_on": "2026-07-27T00:00:00Z",
  "source_label": "manual export",
  "moderators": [
    {
      "name": "example_mod",
      "id": "optional-account-id",
      "permissions": ["all"],
      "added_utc": 1753574400
    }
  ]
}
```

Import it with `--source-type moderators --source-scope scoped`. The bundle is
local evidence supplied by the user; Slice 3 neither obtains it from Reddit nor
claims it is current or complete. Moderator names and IDs are identifying data,
so the live OAuth retention conflict remains unresolved.

### Inspect or export one local comment tree

Print bounded integrity and count coverage without writing anything:

```text
.venv\Scripts\python.exe scripts\reddit_comments.py inspect ^
  --database D:\archives\AIcrack\reddit.sqlite ^
  --post-id abc123 ^
  --max-comments 250000
```

Create one deterministic nested JSON artifact:

```text
.venv\Scripts\python.exe scripts\reddit_comments.py export ^
  --database D:\archives\AIcrack\reddit.sqlite ^
  --post-id abc123 ^
  --output D:\archives\AIcrack\exports\abc123-comments.json ^
  --max-comments 250000 ^
  --max-output-bytes 1GiB
```

The database must already exist and is opened read-only. A bare ID or
`t3_<id>` is accepted. The comment cap is checked before rows are loaded, and
the output-byte cap is checked while an iterative encoder writes a temporary
artifact. An existing identical output is verified and reused; an existing
different output is never replaced. The exported projection contains:

- the archived post and latest supplied `num_comments` observation;
- deterministic root and child order by creation time then comment ID;
- every normalized comment exactly once, including detached components;
- missing-parent placeholders and detailed integrity coverage;
- stored and derived depths without changing the archived depth;
- exact `[deleted]` and `[removed]` bodies with an explicit body state.

Cycles are broken only in the projection at their deterministic smallest
comment ID and are fully reported. `declared_unobserved_count` is a count
difference, not proof that the source is complete. Older Slice 0 imports have
unknown collapsed-placeholder coverage. Slice 5 direct captures preserve every
supplied Arctic Shift `kind: "more"` node, its parent, count, and unresolved IDs
in `comment_placeholders`, so current projections report those exact observed
placeholders without claiming the service returned every comment.

## Supported URL targets

| Input | Capture meaning |
| --- | --- |
| `BlueArchive`, `r/BlueArchive` | Subreddit scope |
| `https://reddit.com/r/BlueArchive/` | Subreddit scope |
| `/r/<sub>/new`, `hot`, `top`, `controversial`, `rising` | Subreddit scope with the requested listing recorded |
| `/r/<sub>/search?q=...` | Offline text/subreddit filter with the original query recorded |
| `/r/<sub>/comments/<id>/...` | One post ID and its matching comments |
| `/user/<name>/...` | Records whose supplied author matches that user |
| `https://redd.it/<id>` | One post ID |
| Reddit/direct media URL | Asset scope for matching supplied records |
| External URL | External scope for matching supplied records |

URLs containing credentials, non-HTTP schemes, malformed names, and an
unbounded Reddit home-page URL are rejected. `web.archive.org` and `.warc`,
`.warc.gz`, or `.wacz` targets are rejected explicitly.

Parsing a URL does not prove that a source contains every matching record.
Slice 1 `.zst` jobs report records scanned, date-matched, selected, invalid,
missing timestamps, observed time range, kind counts, source size, and an
optional verified source digest.

## Source record shapes

The local importer recognizes:

- a flat Reddit/Arctic-style post object;
- a flat comment object with `link_id`;
- Reddit `{"kind":"t3","data":{...}}` post objects;
- Reddit `{"kind":"t1","data":{...}}` comment objects;
- `{"type":"post","data":{...}}`,
  `{"type":"submission","data":{...}}`, and
  `{"type":"comment","data":{...}}` envelopes.

Each JSONL line is one source record. Unknown and malformed records are still
preserved in raw chunks and recorded in the job ledger, but they are not added
to the post/comment search index.

The local importer does not expand a whole Reddit Listing embedded as one
JSONL line. Official API mode enumerates a live Listing separately and never
stores its raw response.

## Capture options

```text
--url URL
--subreddit NAME
--source-file PATH | --arctic-shift-api | --reddit-api
--arctic-output-root PATH
--arctic-timeout SECONDS
--arctic-max-response-bytes BYTES
--arctic-max-comments 1..25000
--arctic-max-wiki-pages 0..10000
--posts 5000|500000|all
--comments none|all
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
--source-format auto|arctic-zst
--source-scope scoped|global
--after YYYY-MM-DD
--before YYYY-MM-DD
--expected-sha256 HEX
--coverage-json PATH
--discovery-manifest PATH
--reddit-max-items 1..1000
--reddit-api-output PATH
--reddit-timeout SECONDS
```

`--url` and `--subreddit` are mutually exclusive. Exactly one of
`--source-file`, `--arctic-shift-api`, and `--reddit-api` is required. A direct
Arctic Shift capture requires a post or subreddit target and rejects user,
search, listing, media, and arbitrary external scopes. Source/date/hash/coverage
and discovery flags apply only to local `.zst`; Reddit limit/output/timeout
flags apply only to official API discovery; Arctic limits apply only to direct
capture.

External assets require both `--save-external-assets` and at least one
repeatable `--external-domain`. A domain matches itself and its subdomains.
There is no unrestricted external crawl mode.

Media flags create queue records only during a local import. API discovery
rejects those flags so an ID-only operation cannot look like a media capture.

## Resume behavior

A job ID is derived from:

- source absolute path;
- source size and modification time;
- canonical target;
- capture options;
- `.zst` scope, UTC boundaries, expected digest, and discovery-manifest
  identity when present;
- archive schema version.

Running the same job again without `--resume` fails closed rather than
silently doing work. Running it with `--resume`:

- returns immediately if it already completed;
- continues after the last committed source line if it failed or was stopped;
- reuses a matching verified raw chunk left by a crash;
- does not duplicate normalized records or observations.

If the source file changes, its size or modification time produces a new job
identity. The old capture remains preserved.

Community job identity also includes its source type, source scope, target
subreddit, chunk size, expected digest, source signature, and community schema
version. Its `--resume` behavior is likewise create-only and duplicate-free.

## Output layout

Given:

```text
--database D:\archives\bluearchive\reddit.sqlite
```

Local imports write:

```text
D:\archives\bluearchive\
  reddit.sqlite
  archives\
    raw\
      <job-id>\
        manifest.json
        coverage.json
        <first-line>-<last-line>-<hash>.jsonl.gz
```

`coverage.json` exists for Slice 1 `.zst` capture jobs only. Every Slice 3
community job writes its own coverage file, regardless of source compression.

Community imports add:

```text
D:\archives\bluearchive\
  archives\
    community\
      <job-id>\
        manifest.json
        coverage.json
        <first-line>-<last-line>-<hash>.jsonl.gz
```

Direct Arctic Shift capture adds:

```text
D:\archives\bluearchive\
  archives\
    direct\
      <capture-id>\
        manifest.json
        coverage.json
        responses\
          <ordered-name>-<sha256>.json
        generated\
          posts.jsonl
          comments.jsonl
          about.jsonl
          rules.jsonl
          wiki.jsonl
```

Only files relevant to the target exist: post captures contain post/comment
sources, while subreddit captures contain community sources and never a post
listing. Exact responses and the manifest are create-only and verified by hash
when encountered again.

Slice 4 writes only the explicit `--output` path selected by the user. It adds
no cache, implicit export directory, or `user.sqlite` state.

Given:

```text
--destination D:\archives\bluearchive\media
```

confirmed Slice 2 runs add:

```text
D:\archives\bluearchive\media\
  objects\
    sha256\
      <first-two-hash-digits>\
        <sha256>.<safe-extension>
  manifests\
    <asset-id>\
      <attempt-id>.json
  .staging\
    <asset-id>\
      <resumable engine partials>
  failed\
    <asset-id>\<attempt-id>\<preserved invalid output>
  oversize\
    <asset-id>\<attempt-id>\<preserved oversized output>
```

Object paths and observation manifests are create-only. An identical file
queues a second observation but points at the already verified object instead
of storing duplicate bytes. Failed completed output is moved out of the stable
staging directory so `--retry-failed` can make a new attempt; genuine partial
files stay in staging for the engines to resume.

Raw chunks are written to a unique temporary file, flushed, atomically
installed, and verified before their database ledger entry commits. An
interrupted retry never overwrites a verified chunk.

The create-only manifest records the source signature, canonical target,
capture policies, and archive schema version so the SQLite index can be rebuilt
without guessing how the raw records were selected.

The SQLite file is a rebuildable index. It contains:

- capture jobs and policies;
- raw-chunk and source-record provenance;
- selected post IDs;
- normalized posts and observations;
- normalized comments and observations;
- direct-source unresolved comment placeholder observations;
- queued asset URLs;
- media-object hashes and append-only acquisition events;
- community import jobs, chunks, source-record provenance, and errors;
- versioned subreddit about observations;
- ordered rule snapshots and observations;
- wiki page/revision observations;
- optional moderator snapshots and observations;
- capture errors;
- post/comment FTS5 indexes.

Media bytes live under the separately selected media destination, not inside
SQLite. Reddit's only `user.sqlite` state is the shared optional-module
enablement slug.

## Vote truth

The local archive stores the raw vote fields a source supplies, including score,
upvote ratio, `ups`, `downs`, `likes`, and `saved`. The normalized interface
uses:

- post score;
- post upvote ratio;
- comment score;
- the authenticated account's own vote state when supplied;
- the authenticated account's own Reddit saved state when supplied;
- observation time and source provenance.

It does not claim that `ups` and `downs` are exact public totals or expose
voter identities. Reddit has historically fuzzed or withheld that information.

## Local library and runtime

`backend/modules/reddit/library.py` opens the archive with SQLite `mode=ro` and
`query_only`. `scripts/reddit_library.py` exposes the same projections used by
the HTTP API:

```text
.venv\Scripts\python.exe scripts\reddit_library.py feed
.venv\Scripts\python.exe scripts\reddit_library.py search "archive query"
.venv\Scripts\python.exe scripts\reddit_library.py post <post-id>
.venv\Scripts\python.exe scripts\reddit_library.py community <subreddit>
.venv\Scripts\python.exe scripts\reddit_library.py status
```

The feed uses a stable opaque keyset cursor over creation time and post ID, with
a maximum page size of 100. Search uses the existing post/comment FTS5 indexes
and can filter by:

- subreddit;
- author;
- record type (`post`, `comment`, or `all`);
- result limit.

The same projections are always mounted at `/api/reddit/feed`, `/search`,
`/posts/{post_id}`, `/community/{subreddit}`, `/status`, and
`/media/{sha256}`. `POST /api/reddit/capture` exposes the same bounded
direct-capture service as the CLI and serializes requests so only one capture
runs at a time. All routes require the optional Reddit descriptor to be
enabled. Media lookup accepts only a known 64-digit object hash whose resolved
path remains inside the module media root; it supports byte ranges and never
redirects to a stored remote URL.

## Safety boundary

- No input source file is rewritten or deleted.
- No raw chunk is overwritten.
- Slice 0-1 capture, Slice 2 planning, and Slice 3 community import create no
  media directory.
- Slice 4 opens only an existing archive in SQLite read-only/query-only mode;
  cycle breaks, derived depths, and detached roots exist only in memory/export.
- Slice 4 checks the comment cap before loading a thread and the byte cap before
  installing output. It never replaces a different existing JSON artifact.
- Direct Arctic Shift capture has finite timeout, retry, per-response byte,
  comment, wiki-page, and wait limits and preserves exact response evidence
  create-only before normalization.
- In-app capture accepts only a parsed Reddit post or subreddit URL, calls only
  the fixed Arctic Shift JSON origin, and runs one capture at a time. The UI
  disables dismissal during the request so its completion state is not hidden.
- Slice 2 download requires an exact count and selection-hash confirmation.
- Reddit-hosted media is bounded by file, byte, retry, timeout, and reserved
  free-space limits; external roles remain blocked.
- Completed, failed, oversized, and partial downloader output is preserved.
- Post/comment and community file imports and all library/runtime reads make no
  network request. Only explicit `--arctic-shift-api`, `--reddit-api`, or a
  separately confirmed Slice 2 media download contacts a remote service.
- OAuth secrets and bearer tokens are never written to manifests or stdout.
- Official Reddit API response bodies are not admitted to the permanent raw
  archive. Explicit direct Arctic Shift responses are preserved as identified,
  hashed source evidence.
- Commands default to the descriptor-owned
  `<suite-home>/modules/reddit/reddit.sqlite`; an explicit `--database` can
  select another archive.
- Runtime feed, search, thread, community, and status queries are read-only.
- The frontend requests only local Keivotos media endpoints.
- No external asset is accepted without a domain allowlist.

The Reddit API deletion-policy conflict recorded in
`REDDIT_MODULE_HANDOFF.md` remains unresolved and blocks an API-backed
permanent-retention design.

## Verification

The Reddit tests include `test_reddit_capture.py`,
`test_reddit_arctic_shift.py`, `test_reddit_api.py`, `test_reddit_media.py`,
`test_reddit_community.py`, `test_reddit_comments.py`,
`test_reddit_link_capture.py`, `test_reddit_library.py`,
`test_reddit_runtime_api.py`, `test_reddit_frontend_contract.py`, and the
shared `test_yt_dlp_service.py`. They
characterize:

- URL canonicalization and rejection;
- post, comment, user, search, and asset targets;
- streamed JSONL and gzip imports;
- atomic verified raw chunks;
- normalized posts/comments and nested parent IDs;
- score, ratio, own-vote, and saved observations;
- FTS post/comment search and filters;
- image/video asset queues;
- subreddit filtering;
- post limits on post and comment-only inputs;
- raw-only comment policy;
- explicit resume and duplicate prevention;
- simulated interruption and continuation;
- streaming `.zst` reads and invalid-source failure before database creation;
- global pre-filtering before raw preservation and scoped raw preservation;
- inclusive/exclusive UTC boundaries, SHA-256 verification, and coverage;
- API discovery selection of posts and their linked comments;
- OAuth headers, 100-item pages, `after` traversal, deduplication, repeated
  cursor stops, rate-limit waits, and 429 retry;
- missing credentials, unsupported targets, the 1,000 cap, and create-only
  discovery output;
- CLI summary output and no media-directory creation.
- offline media planning and exact count/hash confirmation;
- accepted/rejected roles, hosts, ports, and credential-bearing URLs;
- finite disk and byte caps, interruption partials, failed/oversize
  preservation, and explicit retry selection;
- image validation, SHA-256 object installation, byte deduplication,
  create-only manifests, and append-only event records;
- gallery-dl and yt-dlp subprocess boundaries, including the yt-dlp option
  order required to preserve resume behavior and the shared service's
  no-shell, timeout, cancellation, and redaction contracts;
- global-before-raw and scoped-as-evidence community filtering;
- published about/rules/wiki shapes, nested wiki paths, multiple revisions,
  ordered and empty rule snapshots, and the explicit moderator-bundle format;
- subreddit icon/banner queuing without media-directory creation;
- community SHA verification, invalid-source failure before database creation,
  create-only coverage, interruption/resume, and duplicate prevention;
- deterministic root/child ordering and exact comment preservation;
- missing, invalid, ambiguous, self, and cross-post parent handling;
- cycle detection/projection, unknown posts, duplicate fullnames, and
  stored-versus-derived depth reporting;
- latest supplied `num_comments` comparison and explicit deleted/removed body
  states;
- pre-load comment limits, streaming output-byte limits, create-only export
  verification, and missing-database refusal;
- iterative export of a 1,500-level synthetic thread without recursion failure.
- exact direct-response bundles, post-only and community-only endpoint routing,
  response-byte/comment/wiki caps, retries, and invalid preflight refusal;
- additive `kind: "more"` placeholder storage and thread coverage;
- read-only equal-timestamp cursor pagination, invalid cursor handling, filters,
  FTS results, post/community/status projections, and local media identity;
- disabled-module gating, API response shapes, path containment, safe headers,
  ranges, and outside-root refusal;
- frontend registry, infinite-feed trigger, local-only media, search,
  thread-detail, community-detail, and explicit incomplete-source states.

No live Reddit or Arctic Shift request and no large dump is used by the
automated suite. No live media URL was opened. An isolated browser used
synthetic local records to verify optional enablement, the initial 25-post page
plus a 5-post scroll continuation, FTS comment search, post/thread and community
overlays, and a clean console. The in-app follow-up then verified the live
drawer motion, focus, validation, mocked success/refresh, and Escape close.
Three bounded post captures and one subreddit-only capture were exercised
against Arctic Shift in that disposable home; the scratch archive was removed
afterward. The production frontend check and build passed. The final repository
run after the in-app capture follow-up passed all 314 tests. Python compileall,
the additive OpenAPI snapshot, frontend static check with zero errors/warnings,
and the production build also passed.

## Completed continuation sequence

The user approved the complete no-web-archive continuation plan on
2026-07-27. Each slice was implemented and independently verified:

1. **Slice 5 — bounded direct-link capture.** The Arctic Shift JSON adapter
   captures one selected post plus its bounded comments, or community-only
   about/rules/wiki/image context, with exact-source evidence and unresolved
   placeholders.
2. **Slice 6 — offline Reddit library service.** Stable cursor-paginated post
   listings, bounded FTS search, post/thread detail, community history,
   local-media references, capture status, and a local CLI use read-only SQLite.
3. **Slice 7 — runtime module/API.** The Reddit descriptor owns
   `<suite-home>/modules/reddit`; `/api/reddit/*` is always mounted and enforces
   enabled state, with additive OpenAPI and response tests.
4. **Slice 8 — custom local frontend.** The original Reddit-inspired surface
   provides infinite saved-post browsing, local search/filtering, nested thread
   and community detail, local-media-only rendering, and timed browser evidence.

No live Reddit or Arctic Shift request, real archive import, or media download
is part of the automated suite. The disposable live link-capture smoke described
above is complete; downloading referenced media remains a separate explicit
user action.
