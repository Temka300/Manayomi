# Karaoke and YouTube Module Plan

Status: **approved for implementation on 2026-07-28**. This document is the
implementation contract. A checked item is implemented and verified; an
unchecked item remains planned. It must never be read as a statement that all
items already exist.

The shipped product version remains owned by `backend\product.py` and
`scripts\release\set_version.py`. This plan does not authorize a version bump,
release, package, Git operation, or real third-party media download.

## 1. Outcome

Keivotos gains two optional modules without changing the behavior of Files,
Danbooru, or Reddit:

- **Karaoke** searches Kara.moe first, acquires an official hardsub video when
  available, preserves source metadata and timed lyrics, manages a local
  karaoke library, and plays local media through a purpose-built player.
- **YouTube** searches YouTube through the already-pinned `yt-dlp`, lets the
  user select an actual reported video/audio/subtitle format, downloads local
  media after an explicit plan and confirmation, and hands selected local
  assets to Karaoke through Files identity.
- **Files** remains the always-on base and type-agnostic browser. Both optional
  modules publish their local library roots to Files. Files never imports or
  understands either module.

The dependency direction is:

```text
Karaoke -----> Files services and durable file identity
YouTube -----> Files services and durable file identity
Reddit  -----> shared guarded yt-dlp process service
YouTube -----> shared guarded yt-dlp process service

Karaoke -X-> YouTube backend internals
YouTube -X-> Karaoke backend internals
Files   -X-> optional-module internals
```

The two optional modules coordinate in the frontend through a small,
descriptor-aware handoff payload. The Karaoke import API receives only a Files
source/path identity, not a YouTube module object or database row.

## 2. Research Contract

### 2.1 Kara.moe

The supplied screenshot is the live Kara.moe record for **Akogare no Zankyô**.
Its public result contains the title, Blue Archive series/franchise, Japanese
and English languages, DAZBEE singer, Mitsukiyo and Yoshimi Yûno songwriters,
Yostar Pictures creator, Nemesise karaoke author, platforms, origin, group,
collection, four-minute-twenty-second duration, and 38 normalized lyric cues.

The official API documents:

- `GET /karas/search` for bounded repository search;
- `GET /karas/{kid}` for complete metadata and normalized lyrics; and
- `GET /karas/{kid}/hardsub` for the official MP4 hardsub.

The current public record normally does **not** expose the original ASS file.
The module therefore:

- downloads the documented hardsub MP4;
- preserves an exact sanitized source receipt and normalized lyric JSON;
- derives clearly named `.generated.vtt` and `.generated.lrc` files;
- never labels a derived file as an original ASS file;
- preserves a real upstream or user-supplied `.ass`, `.ssa`, `.srt`, `.vtt`,
  or `.lrc` file byte-for-byte when one exists; and
- disables a separate lyric overlay by default for a hardsub video to avoid
  drawing the same lyrics twice.

Sources:

- <https://kara.moe/>
- <https://api.karaokes.moe/server/>
- <https://api.karaokes.moe/server/swagger.json>
- <https://gitlab.com/karaokemugen/code/karaokemugen-server>

### 2.2 yt-dlp and YouTube

The repository already pins `yt-dlp` and provides FFmpeg through its current
runtime. The implementation uses documented machine-readable interfaces:

- `ytsearchN:` and JSON output for bounded search;
- reported format IDs rather than guessed URLs;
- `--progress-template` for parseable progress;
- `--write-subs`, `--write-auto-subs`, `--sub-langs`, and subtitle conversion;
- `-S res:<height>` and explicit format selection;
- `--extract-audio`, selected audio codecs, and selected bitrates;
- `--ignore-config`, `--no-playlist`, timeouts, retries, and no shell; and
- a module-owned output template inside a validated staging directory.

The YouTube Data API is not used. It does not authorize this downloader
workflow and its policy expressly prohibits offline-download and
audio-separation features in API clients. Every download plan displays the
source, destination, formats, estimated size, and an acknowledgement that the
user is authorized to download the selected content.

The first implementation supports public, single-video acquisition only. It
does not accept browser cookies, account credentials, private or
age-restricted content, playlists, channels, DRM/security bypass, geo bypass,
or arbitrary non-YouTube extractor URLs.

Sources:

- <https://github.com/yt-dlp/yt-dlp/blob/master/README.md>
- <https://www.youtube.com/static?template=terms>
- <https://developers.google.com/youtube/terms/developer-policies-guide>

### 2.3 Subtitle renderer and accessible player

Real ASS/SSA tracks are rendered by JASSUB/libass, dynamically loaded only
when such a track is active. JASSUB's single-thread fallback avoids a global
COOP/COEP header change. Remote font lookup remains disabled; only embedded,
bundled, or local fonts may be used.

Native WebVTT is used where it preserves the source. SRT and LRC remain
preserved and are parsed or converted into derived browser tracks without
replacing the original.

Sources:

- <https://github.com/ThaUnknown/jassub>
- <https://github.com/libass/libass>
- <https://developer.mozilla.org/en-US/docs/Web/API/WebVTT_API>
- <https://www.w3.org/WAI/media/av/player/>
- <https://support.google.com/youtube/answer/7631406?hl=en>

## 3. Module and Storage Boundaries

### 3.1 Karaoke

Descriptor contract:

- slug: `karaoke`
- optional dependency: Files
- API prefix: `/api/karaoke`
- home: `<suite-home>\modules\karaoke`
- rebuildable index: `<home>\karaoke.sqlite`
- browsable root: `<home>\media\library`
- Files role: `karaoke`
- Files display name: `Karaoke library`

Durable layout:

```text
modules/karaoke/
  media/library/<provider-id> - <safe-title>/
    video.mp4
    thumbnail.jpg (when FFmpeg can derive one)
    source.metadata.json
    acquisition.receipt.json
    lyrics.normalized.json
    lyrics.generated.vtt
    lyrics.generated.lrc
    <preserved user or upstream subtitle files>
  staging/<job-id>/
  karaoke.sqlite
```

The rebuildable index records providers, tags, local assets, lyric tracks,
variants, hashes, download jobs, and receipt locations. Durable provider IDs
and SHA-256 file identity are used across rebuilds.

Additive precious user tables own:

- favorites;
- playlists and ordered playlist items;
- playback position and completion;
- last selected lyric track;
- per-track lyric offset;
- repeat/shuffle preference; and
- last-played time.

User tables are created additively and are never dropped or rebuilt.

### 3.2 YouTube

Descriptor contract:

- slug: `youtube`
- optional dependency: Files
- API prefix: `/api/youtube`
- home: `<suite-home>\modules\youtube`
- rebuildable index: `<home>\youtube.sqlite`
- browsable root: `<home>\media\library`
- Files role: `youtube`
- Files display name: `YouTube downloads`

Durable layout:

```text
modules/youtube/
  media/library/<video-id> - <safe-title>/
    media.<selected-video-ext>
    media.<selected-audio-ext> (when companion audio is requested)
    media.jpg
    <manual or automatic caption sidecars>
    source.metadata.json
    acquisition.receipt.json
  staging/<job-id>/
  cache/search-thumbnails/
  youtube.sqlite
```

Raw yt-dlp info JSON is not copied blindly. The module recursively removes
credential/header/cookie/proxy/token fields, format/request arrays, and
thumbnails before writing bounded sanitized metadata plus a smaller acquisition
receipt.

Search thumbnails are fetched only for an explicit search, through a bounded
same-provider cache. The browser never hotlinks a provider thumbnail.

## 4. Acquisition Safety

Both modules use a plan/confirm boundary:

1. Inspect metadata without media acquisition.
2. Produce a deterministic plan containing source identity, paths, formats,
   estimated bytes, limits, and a selection hash.
3. Require the exact plan token and selection hash at confirmation.
4. Recheck enablement, path containment, free space, and limits.
5. Write only into a unique staging directory.
6. Preserve resumable partials on cancellation or recoverable failure.
7. Verify completed artifacts and calculate SHA-256.
8. Publish through a no-overwrite rename/copy boundary.
9. Write the durable receipt last.
10. Reconcile Files publication and the initiating UI immediately.

Initial limits:

- one active acquisition per module;
- a 512 MiB free-space reserve, plus YouTube's estimated post-processing
  working space;
- bounded search results;
- bounded metadata and thumbnail responses;
- configurable maximum media bytes;
- socket/read/process timeouts;
- finite retries;
- no playlist expansion;
- no shell;
- no arbitrary output paths; and
- no delete, replace, or purge endpoint.

Opening Keivotos, enabling a module, entering a module, or restoring a previous
view does not perform provider network activity. Searches and acquisition are
always user-triggered.

## 5. Karaoke User Experience

### 5.1 Library

The library is local-first and uses locally generated video thumbnails:

- responsive cover grid;
- title, series, language, duration, and source;
- hardsub, ASS karaoke, captions, and video-only badges;
- library/favorites/playlists filters;
- local text and metadata search;
- stable selection when returning from detail; and
- empty states for disabled, empty, search-no-result, and provider failure.

### 5.2 Detail

The detail layout follows the supplied Kara.moe screenshot while retaining
Keivotos's visual identity:

- large title, song role and series, and year;
- Play, Favorite, and Add to playlist actions;
- duration and acquisition time;
- colored chip rows for series, languages, singers, songwriters, creators,
  karaoke authors, video content, origin, platforms, group, collection, and
  franchise;
- source/receipt status;
- local variants and lyric tracks;
- Attach lyrics;
- Open in Files; and
- a back action that restores the exact library state.

Favorites and playlist mutations update the initiating component immediately,
then reconcile other views.

### 5.3 Kara.moe fallback

If Kara.moe returns no result, the empty state exposes **Search YouTube
instead**. It sends a one-shot payload containing the query and Karaoke intent
to the YouTube surface. It performs no network request until the user submits
or confirms the search.

After a YouTube download made with Karaoke intent, **Add to Karaoke** sends the
published Files source/path identity to Karaoke. Karaoke indexes that stable
file identity and optional subtitle identities without importing YouTube
backend code.

An item without usable lyrics is honestly labeled **Video only**. The user may
attach `.ass`, `.ssa`, `.srt`, `.vtt`, or `.lrc` through a create-only,
size-limited upload. The original is preserved and becomes visible through
Files.

## 6. Player Contract

The new local player belongs only to Karaoke and YouTube. Existing native
players in Files, Danbooru, and Reddit do not change.

Pointer contract:

- Mouse1 or one tap on the non-control media stage toggles control chrome.
- The next stage click hides it.
- A click inside a control, menu, dialog, or lyric drawer never toggles chrome.
- Controls auto-hide after three seconds of inactivity while playing and return on pointer
  movement, focus, or keyboard use.
- Manual hiding remains possible while paused.

Controls:

- center: rewind 10 seconds, play/pause, forward 10 seconds;
- bottom: buffered/played timeline, scrubbing, current/total time, mute,
  volume, lyric/subtitle track, speed, local quality display, picture-in-
  picture when supported, and fullscreen;
- queue: previous, next, shuffle, repeat queue, and repeat one;
- top: Back, title, queue access, and source/quality state;
- top-left: Lyrics button;
- explicit loading, buffering, resume, ended, and error states; and
- browser Media Session metadata and media-key handlers.

Keyboard contract:

- `Space`/`K`: play or pause;
- `J`/`L`: rewind or advance 10 seconds;
- seek-bar arrows: five seconds;
- `M`: mute;
- `C`: captions/lyrics;
- `F`: fullscreen;
- `0`-`9`: percentage seek;
- `<`/`>`: playback speed;
- `Shift+P`/`Shift+N`: previous/next queue item; and
- `Escape`: close the topmost menu, drawer, or fullscreen state.

The Lyrics drawer provides:

- current and next line;
- full scrollable interactive transcript;
- automatic follow and a Follow toggle;
- language track selection plus translation/romaji cue display when supplied;
- active-line highlighting, with ASS karaoke syllable timing rendered over the
  video by JASSUB/libass when the source provides it;
- click-to-seek;
- subtitle timing offset and reset; and
- persistent selection/offset per library item.

All controls have visible focus, names, tooltips, sufficient contrast, reduced-
motion behavior, touch targets, and screen-reader state. The player is
responsive from narrow portrait layouts to full-screen desktop.

## 7. YouTube User Experience

The module is YouTube-inspired, not a clone and not an official client:

- original Keivotos icon and red accent;
- charcoal surface;
- compact left rail;
- top search field;
- bounded filter chips;
- responsive 16:9 result grid;
- locally cached result thumbnails;
- title, channel, duration, date, and views when reported;
- Download and Local Library sections; and
- no remote playback or official YouTube logo.

The format sheet uses only formats reported for the selected video:

- video: 480p, 720p, 1080p, 1440p, 2160p, and Highest when available;
- compatibility preference: MP4/H.264/AAC when available;
- highest-source preference: best reported source streams with the actual
  codec/container displayed;
- companion audio: best original, M4A, Opus, or MP3 at 128/192/320 kbps;
- manual subtitles and automatic captions listed separately; and
- actual format IDs, codec/container, estimated bytes, and destination before
  confirmation.

Video is mandatory for Karaoke-intent acquisition. A standalone YouTube
download also defaults to video; a companion extracted audio file is optional.
Lossless conversion from a lossy source is not presented as improved quality.

Jobs expose phase, progress, bytes, speed, ETA, post-processing, completion,
failure, and cancellation. A cancelled `.part` remains resumable and is never
silently deleted.

## 8. Planned Source Surface

Expected new source:

- `backend\modules\karaoke\`
- `backend\modules\youtube\`
- `backend\routers\karaoke.py`
- `backend\routers\youtube.py`
- `backend\services\yt_dlp.py`
- `frontend\src\modules\karaoke\`
- `frontend\src\modules\youtube\`
- `frontend\src\components\media\`
- focused Karaoke/YouTube API clients and handoff state
- focused backend, frontend-contract, and browser regression tests

Expected existing source touched:

- `backend\module_registry.py`
- `backend\server.py`
- `backend\database.py`
- `backend\modules\reddit\media.py`
- `frontend\src\modules\registry.ts`
- `frontend\src\modules\surfaces.ts`
- `frontend\src\components\AppSettingsModal.svelte`
- `frontend\package.json`
- `frontend\package-lock.json`
- `tests\snapshots\openapi.json`
- `frontend\dist\`

Expected current-state documentation updated:

- `FEATURES.md`
- `FEATURE_CODE_MAP.md`
- `ARCHITECTURE.md`
- `SUITE_MODULE_CONTRACT.md`
- `ROADMAP.md`
- `CHANGELOG.md`
- `REDDIT_MODULE_PLAN.md`
- `REDDIT_MODULE_HANDOFF.md`

Any behavior or file outside this boundary requires a new approval.

## 9. Implementation Slices

- [x] Slice 0 — baseline and this approved design contract.
- [x] Slice 1 — shared guarded yt-dlp process service; Reddit unchanged.
- [x] Slice 2 — Karaoke descriptor, storage, index, user schema, Files
  publication, router skeleton, and OpenAPI coverage.
- [x] Slice 3 — Kara.moe search/detail, plan/confirm acquisition, hardsub
  download, receipts, lyric derivation, and local indexing.
- [x] Slice 4 — Karaoke library/detail, favorites, playlists, subtitle
  attachment, and local artifact APIs.
- [x] Slice 5 — shared local player, JASSUB/WebVTT/LRC, lyrics drawer, queue,
  keyboard, pointer, persistence, and timed browser coverage.
- [x] Slice 6 — YouTube descriptor, storage, index, yt-dlp search/formats,
  plan/confirm jobs, progress/cancel, receipts, and Files publication.
- [x] Slice 7 — YouTube-inspired search/download/library interface.
- [x] Slice 8 — Kara.moe-to-YouTube query handoff and Files-identity
  Add-to-Karaoke workflow.
- [x] Slice 9 — complete docs, generated frontend, full regression, isolated
  app restart, and final handoff.

## 10. Verification Contract

Baseline on 2026-07-28:

- Python compile: passed.
- Pytest: **324 passed**.
- `npm.cmd run check`: passed with zero warnings/errors.
- `npm.cmd run build`: passed.

Completion evidence on 2026-07-28:

- Python compile passed.
- Full pytest passed: **352 tests**.
- The regenerated OpenAPI snapshot passed with the intentional Karaoke and
  YouTube API surface.
- `npm.cmd run check` passed with zero errors and zero warnings.
- `npm.cmd run build` passed and emitted the local JASSUB worker, fallback
  worker, fonts, and WebAssembly assets.
- An isolated app at `localhost:54327` used a generated 12-second MP4, VTT,
  and ASS fixture. Timed interaction verified exact empty-stage Mouse-1
  hide/show (including rapid reversal), three-second playing auto-hide,
  keyboard play and Escape, timeline scrubbing, cue seeking, native VTT,
  a live local JASSUB canvas, lyrics track switching/Follow/romaji/
  translation, queue selection, saved playback, persisted YouTube quality
  defaults, settings/status, and desktop plus 390×844 layouts.
- The same isolated pass proved that the YouTube player source and poster were
  localhost media endpoints, then completed **Add to Karaoke** through
  published Files identity and attached the local caption. The Karaoke
  library immediately reconciled from two to three items.
- The browser console was clean for the final bundle and the isolated server
  recorded no 4xx, 5xx, traceback, or error. The test server was stopped and
  the normal viewport restored.
- The main app was then restarted on `localhost:54325`; its module registry
  returned Files, Danbooru, Reddit, Karaoke, and YouTube while preserving the
  user's existing enabled state (Files and Reddit enabled; the two new optional
  modules remain disabled until the user enables them).
- The timed pass caught and fixed two runtime-only regressions before
  completion: pointer-move/click event ordering during a hidden-control
  reversal, and duplicate undefined cue keys in the lyrics transcript.
- No Kara.moe or YouTube provider media was searched or downloaded.

Required completion gates:

- Python compile and full pytest;
- deterministic Kara.moe and yt-dlp fixtures;
- additive user migration and restart tests;
- module enable/disable and Files publication tests;
- path traversal, symlink, byte range, MIME, and no-overwrite tests;
- plan-token/selection-hash mismatch tests;
- size, free-space, timeout, cancellation, partial, retry, and receipt tests;
- OpenAPI snapshot;
- frontend check and production build;
- real timed browser interaction with synthetic local audio/video for pointer
  toggling, auto-hide, seeking, dragging, keyboard, lyrics, queue, rapid
  reversals, persistence, progress/cancel, responsive layout, reduced motion,
  and clean console; and
- the existing full Files/Danbooru/Reddit/suite smoke pass.

Provider API reads may be used to validate metadata contracts. No real
Kara.moe or YouTube media is downloaded for verification unless the user
separately supplies an authorized test item.

## 11. Non-goals

The approved first implementation does not include:

- cloud sync, accounts, telemetry, or remote-user behavior;
- YouTube Data API keys, login, cookies, subscriptions, comments, likes, or
  remote playlists;
- arbitrary-site yt-dlp use;
- DRM, access-control, age, private-content, or geo circumvention;
- playlist/channel bulk download;
- voice removal, stem separation, pitch scoring, microphone scoring, or AI
  lyric synchronization;
- a subtitle authoring/timing editor;
- destructive cleanup, purge, replace, or user-data deletion;
- a client-side URL router;
- a shipped-version change, release notes, packaging, or Git operation; or
- changes to existing Files, Danbooru, or Reddit player behavior.
