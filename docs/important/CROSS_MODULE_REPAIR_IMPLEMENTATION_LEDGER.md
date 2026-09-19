# Cross-Module Repair Implementation Ledger

Status: **Implemented and verified — one external dependency limitation**

Approved scope: the shared Keivotos player and suite UX, Settings, Reddit,
Karaoke, YouTube, and Languages. This ledger is the durable record of the
work requested on 2026-07-29. It supplements the module plans; it does not
replace their architecture or safety contracts.

## Safety boundary

- Preserve every existing media file, metadata record, sidecar, backup, and
  `user.sqlite` database.
- Database changes are additive migrations only.
- Prevent future duplicate Reddit Files aliases without deleting old aliases
  or removing the database relationships that explain where media came from.
- Do not perform full YouTube/Kara.moe/Reddit downloads during verification.
  Network checks are bounded metadata or extractor probes.
- No Git staging, commits, branches, tags, packages, or releases are performed
  by the agent.

## Status legend

- `[ ]` planned
- `[-]` in progress
- `[x]` implemented and verified
- `[!]` implemented with a documented external limitation

## 1. Shared suite UX

- [x] Add a suite-wide toast system with dismiss, retry, progress, and undo
  support for reversible actions.
- [x] Add an accessible shared action menu used by right-click, three-dot
  buttons, keyboard, and touch across Files, Danbooru, Reddit, Karaoke,
  YouTube, and Languages.
- [x] Give narrow layouts one consistent module-navigation replacement rather
  than hiding different sidebars at unrelated breakpoints.
- [x] Make custom dialogs trap focus, close on Escape, and restore focus.

Acceptance:

- Context menus do not replace native browser behavior in editable fields.
- Every menu action is also keyboard reachable.
- Errors are dismissible and retryable where the operation is safe to repeat.

## 2. Settings

- [x] Reorganize Settings into Suite, Player, Files, and Modules groups with
  clear separators and one section per installed module.
- [x] Add Player controls visibility policy. The default is click/tap to reveal
  controls; an option restores pointer-movement reveal behavior.
- [x] Add YouTube JavaScript-runtime, retry, subtitle, and optional
  browser-session recovery settings.
- [x] Add Reddit provider/profile-capture settings while preserving local-first
  defaults.

Acceptance:

- Settings remain local and persist across restarts.
- Disabled or unavailable modules are identified instead of silently omitted.

## 3. Neutral shared media player

- [x] Move karaoke-specific lyric types to neutral `SubtitleTrack` and
  `SubtitleCue` media types. `cues` is optional so native-only subtitle files
  are represented honestly.
- [x] Keep one module-neutral transport engine and add thin Karaoke and YouTube
  policy wrappers.
- [x] Remove hardcoded Karaoke names, cyan accents, and karaoke-only ARIA labels
  from the shared engine.
- [x] Replace index-based native text-track matching and fix the dead
  `trackUrl()` branch.
- [x] Make video click toggle play/pause and reveal controls. Pointer movement
  only reveals controls when the Player setting enables legacy behavior.
- [x] Redesign transport placement and visible active states for repeat,
  repeat-one, shuffle, captions, mini-player, and settings.
- [x] Keep volume available on narrow layouts and keep popovers above the
  scrubber.
- [x] Merge duplicate CC/Lyrics controls into **Subtitles & lyrics**, with
  attach support for ASS, SSA, SRT, VTT, and LRC.
- [x] Expose quality and audio selectors only when actual alternatives exist.
- [x] Make the side panel pluggable so Karaoke can show timed lyrics and
  YouTube can show subtitles/transcript/description without fake karaoke data.

Acceptance:

- Karaoke and YouTube share transport behavior without sharing module policy.
- Existing keyboard, fullscreen, PiP, buffering, and Media Session behavior
  remains functional.

## 4. Karaoke

- [x] Decode Kara.moe token-array lyric payloads into readable text instead of
  displaying serialized JSON objects.
- [x] Add a persistent top-right download indicator and job drawer with active,
  queued, completed, failed, and cancelled history.
- [x] Allow multiple acquisitions to queue while one worker processes them.
- [x] Add playlist rename, delete, item removal, and reorder; show every
  playlist rather than the first eight.
- [x] Make Previous/Next use the active filtered view or playlist.
- [x] Make **Open in Files** navigate to the exact acquired media item.
- [x] Surface play counts, recently played, last played, and completion state.
- [!] Add key/pitch shift using the maintained
  `@soundtouchjs/audio-worklet` engine, with a safe unsupported-browser
  fallback.
- [x] Add performance mode, translation visibility, a large next-line preview,
  and per-line looping.
- [x] Correct dialog behavior, tag contrast, detail typography, and persistent
  failed/cancelled job history.

Acceptance:

- Existing songs and playlists are migrated additively.
- A Kara.moe song with tokenized lyrics renders human-readable timed lines.
- Pitch/key shift is the one external limitation: adding
  `@soundtouchjs/audio-worklet` was blocked by the environment's dependency
  safety review. No unreviewed audio engine was vendored as a workaround.

## 5. YouTube

- [x] Add a top-right **Acquisition** button that opens a persistent drawer
  containing a pasted-URL field and inspected video details.
- [x] Add a neighboring **Downloads** indicator with aggregate progress and a
  persistent job/history drawer.
- [x] Show selected/loading/queued state immediately so slow inspection cannot
  look like a dead click.
- [x] Queue more than one acquisition and restore jobs after reload.
- [x] Mark already-downloaded search results and add three-dot actions.
- [x] Make category chips filter real metadata.
- [x] Prioritize Japanese, English, then Korean subtitle choices.
- [x] Prefer the locked project yt-dlp over an older PATH executable, install
  its EJS support, and pass the installed Node runtime explicitly.
- [x] Split media and subtitle acquisition so an optional subtitle failure does
  not discard a successfully downloaded video.
- [x] Add bounded retry/backoff and subtitle request spacing. Report HTTP 429
  honestly and allow subtitle-only retry.
- [x] Add disabled-by-default browser-session recovery for a user who has
  explicitly enabled it; never copy browser credentials silently.
- [x] Add a server-side YouTube-to-Karaoke handoff.
- [x] Wire Previous/Next, local playback persistence, and real locally
  available quality/audio variants.

Acceptance:

- The supplied URL can be inspected with the configured JavaScript runtime.
- A subtitle 429 becomes a recoverable warning/job state rather than erasing
  the media result.

## 6. Reddit

- [x] Add Home, Popular, Communities, and Profiles destinations.
- [x] Build Popular from the newest locally captured observations.
- [x] List every captured subreddit with favorite, history, refresh, and
  three-dot actions.
- [x] Add user-profile capture through the existing credentialed adapter:
  profile snapshot, bounded submitted posts/comments, and observation history.
- [x] Refresh posts, communities, and profiles additively to capture score,
  comment, and upvote-ratio changes.
- [x] Chart observation history for score, comment count, and upvote ratio.
- [x] Render comments as recursive collapsible threads with expand/collapse
  controls instead of a flattened capped list.
- [x] Add context/three-dot actions to captured Reddit entities.
- [x] Publish one readable Files alias per owner/content hash while retaining
  all archive-asset relationships.

Acceptance:

- Existing duplicate aliases are counted and reported but not removed.
- Refresh never rewrites an older observation.

## 7. Languages

- [x] Keep the module named Languages, add a configurable study/meaning
  profile, and label Korean-only tools honestly.
- [x] Restyle Sentence Analyzer as a dark Keivotos surface while retaining the
  Kiwi morphology engine.
- [x] Show editable English and Mongolian sentence meanings. Fill exact learned
  word meanings from local EN/MN data; do not fabricate automatic sentence
  translations.
- [x] Surface practice totals, accuracy, daily activity, streak, and per-word
  performance.
- [x] Make Today actionable through local practice, audio, and word detail
  without writing Anki scheduling state.
- [x] Move Sentences and Grammar filtering/pagination to the server.
- [x] Replace `window.prompt` list naming with an accessible custom dialog.
- [x] Add clear-all and saved filter sets.
- [x] Add a readable mastery legend and touch-visible card actions.
- [x] Add useful empty states to Sentences, Grammar, and Decks.
- [x] Preserve and retest word three-dot editing, Korean/English/Mongolian
  alphabetical sorting, Browser table view, and Hangul Atlas.

Acceptance:

- No analyzer view imports Mirinae's light visual identity.
- Local Anki mirroring remains read-only.

## 8. Documentation and regression verification

- [x] Update `FEATURES.md` and `FEATURE_CODE_MAP.md` in each behavior slice.
- [x] Update `docs/important/CHANGELOG.md` with the implemented behavior and
  important limitations.
- [x] Update the OpenAPI snapshot with additive endpoint/schema changes.
- [x] Add backend, frontend-contract, migration, filesystem, and regression
  coverage for every changed behavior.
- [x] Run Python compileall and the full pytest suite.
- [x] Run frontend `check` and production `build`.
- [x] Verify interaction timing, focus, narrow layouts, playback controls, and
  restored job state in the live browser.
- [x] Run only bounded metadata/runtime probes for the supplied YouTube URL.
- [x] Restart the application and verify relevant console/runtime logs.

## Implementation record

This section is updated as slices finish.

| Date | Slice | Result | Verification |
| --- | --- | --- | --- |
| 2026-07-29 | Scope ledger | Approved work recorded before code changes | Plan cross-checked against the user request and repository contracts |
| 2026-07-29 | Shared UX and Settings | Global toast/action-menu/focus foundations, consistent mobile module navigation, grouped settings and shared Player policy | Frontend check and focused source contracts |
| 2026-07-29 | Neutral media player | Module-neutral transport, stable subtitle IDs, click-to-play/reveal policy, explicit state controls, wrappers and pluggable subtitle panel | Player/source contracts and frontend check |
| 2026-07-29 | Karaoke | Readable Kara.moe lyrics, persistent sequential jobs, playlist management, exact Files navigation, playback history and performance tools | Focused Karaoke tests; pitch dependency limitation recorded |
| 2026-07-29 | YouTube | URL acquisition, persistent queue/progress, local playback state, server handoff, subtitle-safe acquisition and explicit JS runtime | Focused YouTube tests; no media download run |
| 2026-07-29 | Reddit | Local Popular/communities/profiles, bounded user capture, additive refresh/graphs, recursive comments and future alias convergence | Focused 42-test Reddit pass; no existing alias removed |
| 2026-07-29 | Languages | Dark Kiwi Analyzer, EN/MN profile, actionable Today/practice statistics, server filtering, saved filters and accessible states | Focused 32-test Language pass and clean frontend check |
| 2026-07-29 | Cross-surface actions | Files, Danbooru, Reddit, Karaoke, YouTube and Languages expose shared context/three-dot actions | Clean frontend check, focused contract pass, live Reddit and Files menu checks |
| 2026-07-29 | Preserved lyric compatibility | Existing Kara.moe JSON/Python token-array cues normalize to readable timed text at read time without rewriting the catalog | Focused 19-test Karaoke/player pass and live “The Line” lyric inspection |
| 2026-07-29 | Final verification | Final source, production assets, API contracts, and local runtime verified together | Python compileall; 399 pytest tests; Svelte check 0 errors/0 warnings; production build; timed player/Reddit/Files/YouTube/Language browser checks; fresh console and runtime logs clean |

## Intentional limitations and non-operations

- Pitch/key shift remains unavailable until the maintained
  `@soundtouchjs/audio-worklet` dependency is explicitly approved for
  installation. No substitute DSP implementation was vendored.
- The supplied YouTube URL was inspected through the configured Node runtime,
  but no YouTube, Kara.moe, or Reddit media download was started.
- Existing duplicate Reddit aliases remain preserved. Only future publication
  converges identical owner/content hashes.
- The app is running at `http://localhost:54325/` from the locked virtual
  environment. `run.bat` remains blocked before application startup by the
  pre-existing uv cache-path conflict; that external cache was not changed.
- No Git, version, packaging, release, account, telemetry, or cloud operation
  was performed.
