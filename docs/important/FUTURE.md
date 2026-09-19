# Keivotos — Future: the hoarder suite

Parking lot for everything **beyond the current booru module**. The current
user-defined release identity is the cycle named in
[ROADMAP.md](./ROADMAP.md#current-cycle), and it is not being
declared feature-complete here. V1.10, post-V1.0 expansion, and every idea in
this file are future thoughts only unless explicitly marked as graduated: none
of the remaining ideas is approved, scheduled, promised, or automatic scope.
The Reddit module graduated into an implemented, unreleased fork on 2026-07-27;
see [REDDIT_MODULE_PLAN.md](./REDDIT_MODULE_PLAN.md). Smaller parked booru ideas stay in
[ROADMAP.md](./ROADMAP.md).

Historical version labels and archive-folder names are preserved where they
help explain lineage. Their presence does not mean those versions are the
current release.

The original idea list (preserved verbatim as source material):

| Future |
| --- |
| 00 - Dockerize it |
| 01 - Twitter and Pixiv Hoarder | save ones without images and only words, numbers retweets, favorited |
| 02 - Manga Hoarder | with comments |
| 03 - Anime Hoarder | with comments |
| 04 - Ripper Store Hoarder | ripper store words fantia or jp store info and said downloaded 3d, 2d, live2d models |
| 05 - Youtube Hoarder | youtuber info, comments, like, dislike |
| 06 - Reddit Hoarder | save ones without images and only words, upvote, downvote |
| 07 - Telegram Hoarder | save chat history, save files, images |
| 08 - Kemono Hoarder | patreon and other stuff |
| 09 - Web Hoarder | save pages that others have made for historical purpose and be able to download archive pages too |
| 10 - Folder Structure | might show the path of the folders (prob not gonna add idk need to think of an idea for it) |
| 11 - Github | save projects with issues and others |
| 12 - Music Hoarder + karaoke | jp romaji, video, audio |
| 13 - Discoverability and memories |
| 14 - Blue Archive Hoarder | live2d, 2d images, textures |
| 15 - Meme - user-added tags |
| 16 - Discord | save chat history |
| 17 - Soundboard - blue archive, meccha, lethal, memes | novelty only |

---

## The big picture

The naming question the old docs left open is answered: **Keivotos is the
suite** ("All in one application for hoarding data"), and **Danbooru is its
booru module**. Almost every idea above is the same shape:

> **fetch content + metadata from source X → sidecars/files on disk →
> SQLite index → browse / tag / collect locally**

That is already the booru's architecture. So the suite is not 17 separate
apps — it's **one core engine + a module per source**:

- **Core stays shared:** the two-DB pattern (disposable per-source index +
  irreplaceable user data), sidecar-style metadata on disk, incremental
  `sync`, tags/favorites/collections, thumbnails, media serving, the compact
  local-first UI shell.
- **Each hoarder = a module:** its own tables, its own fetcher, its own browse
  view, plugged into the shared core.
- **Acquisition stays external CLI tools** where possible (gallery-dl —
  already bundled and wrapped; yt-dlp; official exports). We orchestrate,
  we don't absorb; keep Python dependencies minimal and boring.

### Head start: the first module and next incubator already exist

- **Danbooru** (`backend/`, `frontend/`) — the V1.1.0 booru module
  module and current source reference for local identity, storage, search,
  metadata, collections, recovery, and intended immediate UI behavior. Most
  runtime behavior remains unverified after the current static audit, and its
  sidebar animation is user-reported broken.
- **Manga-hoarder prototype** — nhentai hoarder:
  browse/search via the official API, downloads to `.cbz` + gallery-dl-format
  `.json` sidecars, queue with progress, local library scan, **built-in
  reader**, cover blur, tag blacklist. FastAPI + vanilla JS, port 8113. Its
  static frontend survives, but `backend/server.py` imports a missing
  `backend/downloader.py`, so it is currently incomplete and cannot be treated
  as a working shared component. This is item **02 (Manga Hoarder)** source
  material only until a separately authorized audit and repair.

### Shared building blocks (build once, reuse across modules)

| Block | Needed by | Status |
| --- | --- | --- |
| Reader (paged, RTL, double-page) | 02 Manga | partial source exists in the manga-hoarder prototype; runtime unverified |
| Video player + library view | 03 Anime, 05 YouTube | booru plays mp4/webm; needs series/episode grouping |
| Thread / chat viewer (nested comments, chat log) | 05, 06, 07, 16 | ☐ |
| Full-text search (SQLite **FTS5**, built in — no deps) | 06, 07, 09, 11, 16, better booru search | ☐ |
| Live2D / 3D model preview | 04, 14 | ☐ (start with screenshots as covers) |
| Audio player + synced lyrics | 12 Music/karaoke | ☐ |

---

## Speculative tiers (not an approved build order)

**Tier 1 — same engine, new sources** (reuses ~80% of the booru pipeline):

| # | Idea | How / notes |
| --- | --- | --- |
| 01 | Twitter/Pixiv Hoarder | gallery-dl can fetch both and the current app already uses it for explicit profile-media extraction. A real module would still need text-only posts, like/RT counts, creator views, storage decisions, and a tag-translation decision. |
| 08 | Kemono Hoarder | gallery-dl supports kemono; posts + attachments per creator; free ride on everything 01 builds. |
| 15 | Meme library (user tags) | A registered folder with no Danbooru enrichment can use current source support for user tags and minimal indexing. A future module may still need a formal library-type concept. |
| 14 | Blue Archive Hoarder | Asset rips: images/textures ride the normal pipeline; Live2D waits on the shared viewer. |
| 04 | Ripper Store Hoarder | Store files + store-page info; 3D/Live2D preview is a big lift — thumbnails first, viewer later. |

**Tier 2 — new viewers on the same core:**

| # | Idea | How / notes |
| --- | --- | --- |
| 02 | Manga Hoarder | **Seeded by the manga-hoarder prototype.** Decide: merge into the suite UI or keep as sibling app (open question below). Add CBZ folder scan (same idempotent sync idea), MangaDex metadata/comments; Danbooru pools/parent-sibling are a stepping stone. |
| 03 | Anime Hoarder | Video files in place + AniList/AniDB metadata; needs series/episode grouping over the existing player. |
| 05 | Youtube Hoarder | yt-dlp (external CLI — same blessed-tool policy) gets video + metadata + comments in one pass. Decide storage budget/quality caps — video eats disk. |
| 12 | Music Hoarder + karaoke | Audio library + player; karaoke = synced LRC lyrics. JP→romaji with minimal deps is an open problem. |

**Tier 3 — different data model (text / threads / chat):**

| # | Idea | How / notes |
| --- | --- | --- |
| 06 | Reddit Hoarder | **Graduated in the Reddit fork.** Slices 0-8 provide structured local/dump capture, bounded direct Arctic Shift capture, a read-only SQLite/FTS library, nested threads, community context, `/api/reddit/*`, and an infinite local feed. No web-archive/replay tooling. |
| 07 | Telegram | Telegram Desktop's built-in JSON export — parse that; no API/ToS risk. Chat viewer shared with 16. |
| 16 | Discord | Hardest legally: self-bots break ToS; DiscordChatExporter is the usual external tool (own risk), or archive only your own data-export. Decide stance before building. |
| 11 | Github | `git clone --mirror` + REST API for issues/releases into SQLite; browse UI can start metadata-only. |
| 09 | Web Hoarder | Fetch page + inline assets into one self-contained HTML (SingleFile-style, own implementation); plus Wayback snapshots. |

**Infra / UX (not source modules):**

| # | Idea | How / notes |
| --- | --- | --- |
| 00 | Dockerize it | Pure-Python stack — mostly packaging + docs (library paths are entered manually outside Windows, and open-location degrades gracefully). Do it when the suite stabilizes, not per-module. See [DISTRIBUTION.md](./DISTRIBUTION.md). |
| 10 | Folder Structure | Simplest useful form: browse-by-folder tree per registered folder (paths are already indexed). Small enough to reconsider any time. |
| 13 | Discoverability & memories | "On this day", resurfacing old favorites, random-rediscovery feed. Pure in-app, no fetching — pairs with the daily challenge and `image_views` data that already exist. **Great low-effort win.** |
| 17 | Soundboard | Novelty; park indefinitely. |

---

## Open questions (decide before module #1, not now)

1. **One data DB or per-module data DBs?** The booru's pattern (per-source
   disposable index + one shared irreplaceable user DB) suggests: per-module
   `*.sqlite` indexes, one `user.sqlite` with content-keyed user data.
   Confirm when module #1 lands.
2. **One app with a module switcher, or sibling apps?** The manga-hoarder prototype
   currently runs as a sibling (port 8113, own UI). The shared chrome, tags
   and collections argue for one app; the sibling proves modules can incubate
   separately first.
3. **External-tool policy:** gallery-dl is blessed and bundled; formally
   extend the same status to yt-dlp etc. (external CLI = fine; heavyweight
   scraping dependencies = no).
4. **Disk budget** for video-heavy modules (03, 05) — caps and quality tiers.
5. ~~Naming~~ — answered: Keivotos is the suite, Danbooru the booru module.

## Possible investigations after the current release is stabilized

No investigation below has been selected. The current refactor, regression
baseline, and broken behavior take priority until the user chooses otherwise.

1. **02 Manga prototype audit** — inspect its actual storage,
   reader, acquisition, and UI boundaries; decide what becomes shared Keivotos
   infrastructure and what remains module-owned before moving code. Restore or
   replace its missing downloader before treating it as runnable.
2. **Module contract** — decide index ownership, shared `user.sqlite` identity,
   navigation, startup, ports/processes, and external-tool rules using the two
   real codebases rather than an abstract framework.
3. **Promote the smallest reusable reader/library slice** — integrate one
   vertical path only after the contract is written and regression-protected.
4. **Then choose by payoff:** Discoverability & memories for a no-fetcher UX
   win; Twitter/Pixiv then Kemono for acquisition reuse; anime/video,
   music/karaoke, 2D/3D/Live2D, and thread/chat archives as later viewers and
   data models.

Update feeds, automatic deployment, Docker, signing, plugin APIs, and
private/public dual-repository development remain deliberate later decisions.
A Windows installer is specifically low-priority and unlikely: the one-folder
portable executable remains the distribution contract unless real user friction
justifies installer/uninstaller maintenance. The current
source provides a candidate build/data foundation without committing the
project to those maintenance-heavy systems. This document does not assign any
future version number.
