# Keivotos Feature-to-Code Map

Current development identity: see [ROADMAP.md](./ROADMAP.md#current-cycle)  
Map last updated: **2026-07-27**  
Repository: `D:\Kivotos\Github_Wakaru\Keivotos-Modulo\Reddit`

This is the correlation register required by Step 4 of
`docs/important/archive/refactor-brief.md`. It maps the current product contracts to their
frontend owners, backend owners, API routes, persistence, tests, and archived
lineage before modular refactoring begins.

Line numbers in this file are temporary navigation aids. The symbol,
component, route, table, and feature IDs are the durable references. Update the
line numbers whenever an owning file changes.

## Status Key and Evidence Boundary

| Status | Meaning |
|---|---|
| **Working** | Exercised successfully in the current checkout and current runtime. |
| **Broken** | Directly reported or proven not to work. |
| **Partial** | Some required code or dependency exists, but the contract is incomplete or internally inconsistent. |
| **Unverified** | Owning code exists, but the current runtime behavior was not exercised during the static audit. |
| **Historical** | Evidence from an archived version or changelog; not a claim about the current runtime. |
| **Future** | V1.10 or post-V1.0 planning; not a current feature. |

No current application feature is promoted to **Working** by this register
alone. The current audit did not run the application, build, tests, animations,
network integrations, migrations, or real-data operations. Existing tests are
recorded as regression source, not as current passing evidence.

Later verification on 2026-07-23 passed compileall, all 145 unit tests,
frontend check (0 errors/warnings), and the production frontend build. This evidence applies only
to those automated contracts and the isolated migrations exercised by them.

Known exceptions:

- **Broken:** the Danbooru sidebar grip interaction behavior remains
  unverified. The sidebar view-entry animation was repaired in source on
  2026-07-16 (see SHELL-006/MOTION-002) and awaits user visual confirmation.
- **Partial:** remaining cross-suite path centralization outside the verified
  Manayomi root boundary.
- **Unverified:** all other current runtime behavior unless a later dated
  verification result is appended to this register.

V1.10 and post-V1.0 headings in `CHANGELOG.md` are historical/future planning
only. They must not be used as the current release identity.

## Shared Architecture and Dependency Spine

| ID | Responsibility | Current owners and temporary anchors | Dependents | Status |
|---|---|---|---|---|
| ARC-001 | Desktop/source launcher (`run.bat`, `run.sh`; local LAN wrappers `run-lan.local.bat`, `run-lan-local.sh`; locked setup and argument forwarding) | `app.py:resource_root`, `_load_configuration`, `_load_asgi_app`, `_set_console_branding`, `_run_helper`, `_open_browser_when_ready`, `_portable_check`, `_port_available`, `_is_lan_ipv4`, `_discover_lan_ipv4`, `main` | FastAPI composition root, legacy-home bootstrap, pipeline helper, Windows picker, branded source console, browser, developer-gated LAN access, packaging | Developer LAN binds one adapter; packaged artifact requires a real HTTP smoke |
| ARC-002 | FastAPI composition and frontend delivery | `backend/server.py` router composition plus frontend dist/root route | All current `/api` routes and the built Svelte application | Automated OpenAPI/frontend-delivery contracts working |
| ARC-003 | FastAPI lifecycle and middleware | `backend/lifecycle.py` (startup maintenance, module-gated background work, `lifespan`); `backend/app_factory.py` (`app`, `restrict_local_browser_access`, `add_server_timing_header`) | DB initialization, recovery, sidecar migration, automation, every request | Verified 2026-07-25: source launch, portable check, and host/origin rejection exercised |
| ARC-004 | Backend compatibility facade | **Removed 2026-07-25.** `backend/core.py` is deleted; nothing imports it. Composition is `server.py` -> `app_factory.py`, startup in `lifecycle.py` | (none) | Retired: zero wildcard imports, zero importers, OpenAPI snapshot unchanged across the whole extraction |
| ARC-005 | Frontend descriptor switchboard | `frontend/src/App.svelte`; `modules/surfaces.ts`; module-owned Danbooru, Reddit, Karaoke, YouTube, Languages, and Manayomi surfaces | Resolves enabled active descriptor, dynamic module display title, and all seven current surfaces | 432 tests plus check/build and real Manayomi desktop/390×844 browser pass verified 2026-08-08 |
| ARC-006 | Frontend shared state | `frontend/src/lib/stores.ts:56 persistedWritable`, `stores.ts:189-245 exported stores` | Nearly every component | Unverified |
| ARC-007 | Frontend API contract | `frontend/src/lib/api.ts:4-417 types`, `api.ts:419-480 request helpers`, `api.ts:484 thumbnailUrl`, `api.ts:494 imageFileUrl`, `api.ts:499-800 api methods` | All API-consuming components | Unverified |
| ARC-008 | Immediate local mutation and cross-view reconciliation | `stores.ts:219 imageRefreshToken`, `:220 collectionRefreshToken`, `:221 tagRefreshToken`, `:222 artistFollowRefreshToken`, `:224 deletedImageId` | ImageDetail, ImageGrid, Collections, Tags, Profile, notifications | Unverified |
| ARC-009 | Library database access gate | `backend/database.py:15 database access state`, `:72 exclusive_database_access`, `:84 get_data_db`, `:97 get_user_db`, `:136 init_data_db`, `:319 init_user_db` | All routes that query or mutate SQLite; backup/restore quiescence | Unverified |
| ARC-010 | Focused backend services | `backend/services/`: query/home/challenge/value/tag/collection/profile/user-library services plus guarded `yt_dlp.py` process execution and generic `secret_store.py` Windows DPAPI | Routers and optional modules import these directly; no facade remains | Complete: `core.py` deleted 2026-07-25; shared yt-dlp and secret-store consumers verified 2026-07-28 |
| ARC-013 | Danbooru module backend boundary | `backend/modules/danbooru/`: `client.py` (credentialed HTTP), `relations.py`, `tag_wiki.py`, `tags.py`, `artist_profiles.py`, `artist_follows.py`, `search.py`, `tools.py`, `folder_registry.py` | Tag/artist/tools routers, tag-wiki cache, follow polling, profile archive, search grammar, pipeline runner | Extracted 2026-07-24/25, each move byte-identical and re-exported through `core`; image behavior, path helpers and lifecycle not yet behind the boundary |
| ARC-011 | Static module descriptors and registry | `backend/module_descriptor.py:ModuleDescriptor`; `backend/module_registry.py:ModuleRegistry/build_registry`; `backend/modules/{files,danbooru,reddit,karaoke,youtube,language,manayomi}`; frontend `modules/registry.ts`, `modules/surfaces.ts` | Suite shell, paths, API module list, publication/adopt/release hooks, module-owned UI actions | Unit/runtime verified for one required base plus six optional modules; existing-module enablement migration is one-time and idempotent |
| ARC-012 | Files base isolation | `backend/files_base/`; `backend/routers/files.py`; `frontend/src/components/FilesView.svelte`; `frontend/src/lib/filesApi.ts` | Neutral source/index browsing, search, hashing, duplicates, native root picker, constrained subfolder picker | Unit/build, nested-source ownership, and constrained-picker browser passes verified 2026-07-23 |

## Application Shell, Navigation, and Motion

| ID | Feature or contract | Frontend owner | Backend/API and persistence | Regression source | Status and lineage |
|---|---|---|---|---|---|
| SHELL-001 | Route-free view navigation | `App.svelte:41-56`; `stores.ts:4 ViewMode`, `:193 initialViewMode`, `:204 viewMode` | Browser local storage: `startup-view`, `last-view` | `tests/test_view_navigation.py:12` covers special-view breadcrumb source | Unverified |
| SHELL-002 | Top-bar order and compact controls | `TopBar.svelte:22-128 state/actions`, `:212 SearchBar`, `:448 ArtistNotifications`, `:450 UserMenu`, `:455 AppDrawer` | Calls image, random-tag, collection, search, and notification APIs | Feature checklist in `FEATURES.md:227-254` | Unverified |
| SHELL-003 | Keivotos app drawer | `AppDrawer.svelte` iterates suite descriptors and module-owned UI actions; registry details in `modules/registry.ts`; drawer/backdrop keyframes remain local | `/api/suite/modules`; opens base/enabled modules; enable/disable; module Profile action; Settings | Existing motion contract retained; timed browser pass pending |
| SHELL-004 | User/avatar menu | `UserMenu.svelte:13-61 menu, lazy Settings, Search Help, Profile, Favorites, Collections`, `:172 SearchHelpModal` | View stores only; Settings loads APIs after opening sections | No focused runtime test | Unverified |
| SHELL-005 | Danbooru sidebar mounting | `App.svelte:36-38` mounts only for `gallery` and `tags`; `SidebarDock.svelte:112 Sidebar` | Browser local storage for open state and handle position | `tests/test_sidebar_grip_contract.py:37` | Mounting verified live 2026-07-16; entry animation repaired (SHELL-006) |
| SHELL-006 | Danbooru sidebar open/close animation | `SidebarDock.svelte:91 toggle`, `:108 gated is-open`, `:157 width 280ms`, `:168 transform 280ms`; rAF intro gate in `onMount`; one persistent `Sidebar` instance | `danbooru:sidebar-open` | `tests/test_sidebar_grip_contract.py:11` is static source/DOM characterization only | **Repaired in source 2026-07-16**: entry animation (lost in Beta4 rewrite; Beta3.1 `transition:slide` animated every mount) restored via one-frame closed mount; toggle transitions verified created live. **Working** — manually confirmed 2026-07-25 in a real browser: slide-in on Browse entry, grip drag reposition-and-persist, click open/close, saved position across reload. |
| SHELL-007 | Draggable, auto-hiding sidebar grip | `SidebarDock.svelte:18 mount`, `:38 clamp`, `:42 reveal`, `:51/60/71 drag lifecycle`, `:85 cancel`, `:97 keyboard reposition`, `:126-127 grip data`, `:180 grip transition` | `danbooru:sidebar-handle-position` | `tests/test_sidebar_grip_contract.py:11` | **Unverified interaction**; no timed drag/reversal test |
| SHELL-008 | Scrollable sidebar body and filter controls | `Sidebar.svelte:59 lists`, `:79 load`, `:128 tag`, `:135 folder`, `:141-151 special views`, `:156-161 rating`, `:169 favorite tags`, `:198-220 blacklist`, `:231 collections`; CSS in same file | Folders, favorite tags, blacklist, related tags, collections APIs; user DB tables below | No browser overflow test | Unverified |
| SHELL-009 | Search help overlay | `SearchHelpModal.svelte:1-136 help content`, `:137 close`, `:141 keyboard` | Documents `parse_search_terms`; no persistence | No focused test | Unverified |
| SHELL-010 | Settings modal presentation state | `settingsPresentation.ts:4 prepareSettingsPresentation`, `:14 restoreSettingsPresentation`; `app.css:25-31` pauses background animation and owns settings layer | Browser DOM presentation only | Source contract in `FEATURES.md:367-375` | Unverified |
| SHELL-011 | Reduced-motion and motion preference | `app.css:14-20 prefers-reduced-motion`; `stores.ts:235 motionPreference`; motion-aware components listed below | Local storage only | No browser animation test | Unverified |
| SHELL-012 | Interface scale | `stores.ts:236 interfaceScale`; `App.svelte:18-20 interface dataset`; Settings display controls | Local storage only | No focused test | Unverified |
| SHELL-013 | Home/Tags breadcrumb navigation | `HomeBreadcrumbBack.svelte:1-22`; used by Popularity, Timelapse, Daily Challenge and tag detail | `viewMode` store | `tests/test_view_navigation.py:12` | Source-protected; runtime unverified |
| SHELL-014 | Stale frontend bundle prevention | `backend/server.py:19-32 serve_index` sends no-cache headers while hashed assets remain static | Root `/`; no DB | `tests/test_frontend_delivery.py:15` | Unverified in current server |
| SHELL-015 | Files compact top bar and managed-folder sidebar | `FilesView.svelte`; `ManageFoldersDialog.svelte`; `FolderPicker.svelte` | `/api/files/*`, `/api/suite/folders/*`; `files_sources` display/role/visible | Browser verified icon + ancestral breadcrumb, removed middle path strip, Danbooru-matched search sizing/placement with adjacent actions, contained Manage picker, staged Cancel, and clean console 2026-07-23; native desktop dialog remains helper-test-only |

## View Inventory

| ID | View and current contract | Main frontend owner and temporary anchors | Backend/API, persistence, and dependencies | Regression source | Status |
|---|---|---|---|---|---|
| VIEW-001 | Home: Discovery and persisted Classic layouts | `HomeView.svelte:87 mount`, `:155 daily reset`, `:260 spotlight schedule`, `:268/273 selection/movement`, `:298 unique allocation`, `:350-391 local cache`, `:401 load`, `:431 rails`, `releaseLaneFocusPause`, lane motion CSS | `GET /api/home/tags`, `GET /api/home/image-rails`, random image; data DB `files/posts/tags/post_tags`; local cache `danbooru:home:*`; `homeLayout` | `tests/test_home_discovery.py` | Source contract covers focus pause/release; timed motion/cache behavior unverified |
| VIEW-002 | Browse/gallery image grid | `ImageGrid.svelte:144 bulk state`, `:449 loadImages`, `:533 reload`, `:604 loadMore`, `:649 pagination`, `:669 select`, `:682 pin` | `GET /api/images`, favorites, collections, folders, thumbnail; both DBs | Golden, filename-search, thumbnails tests | Unverified |
| VIEW-003 | Favorites | `App.svelte:56 ImageGrid fallback` with `viewMode=favorites`; `ImageGrid.svelte` favorite query/mutations | Favorites endpoints; user DB `favorites` | `tests/test_images_golden.py:114` guards legacy/modern favorite join duplication | Unverified |
| VIEW-004 | Collections list | `CollectionsView.svelte:19 mount`, `:23 create`, `:33 sort`, `:42 pin`, `:59-92 edit`, `:102 delete`, `:124 open`; `CollectionPreviewGrid.svelte` | Collections endpoints; `collections`, `collection_items` | `tests/test_regression_fixes.py:75,80` | Unverified |
| VIEW-005 | Collection detail | `App.svelte` + `activeCollectionId` at `stores.ts:225`; `ImageGrid.svelte` collection mode | `GET /api/images?collection_id=`, collection image/membership endpoints | OpenAPI/golden source | Unverified |
| VIEW-006 | Tags browser and in-section detail | `TagsBrowser.svelte:98 mount`, `:244 fetch`, `:294 search debounce`, `:302-377 filters/sort/page`, `:412 wiki`, `:438 images`, `:470 detail`, `:490 linked tags`, `:535 example`, `:552/574 favorite/pin`, `:592 follow`, `:631-650 combos` | Tags, wiki, related, favorite-tag, follow, and images APIs; both DBs | OpenAPI snapshot; sidebar mount test | Unverified |
| VIEW-007 | Popularity periods | `PopularityBrowser.svelte:41-126 period navigation`, `:155 mode`, `:164 home` | `GET /api/popularity/periods`; data DB | No focused behavior test | Unverified |
| VIEW-008 | Timelapse simple/advanced playback | `TimelapseBrowser.svelte:33/62 timers`, `:92-114 seek/play`, `:130 fullscreen`, `:171-182 scope`, `:191 speed`, `:202/208 modes`, `:215 simple load`, `:267 advance`, `:300 advanced load`, `:397/409 lifecycle`, `:434/461 intervals` | `GET /api/timelapse/frames`, `GET /api/images`; data DB | `tests/test_images_golden.py:143` guards SQL sampling | Unverified timed playback |
| VIEW-009 | Daily Challenge | `DailyChallengeView.svelte:51 mount`, `:68-97 browser state`, `:100 load`, `:121/127 suggestions`, `:153/178 resolve/submit`, `:197 reveal`, `:204 choices`, `:209-219 navigation` | Challenge and character-suggest APIs; data DB; browser-local `danbooru:daily-challenge-v2:<id>` | No focused challenge test | Unverified |
| VIEW-010 | Local Profile | `ProfileView.svelte` name edit/load/open actions and artist rail/focus | Stats, favorites, collections, artist follows/assets; `GET/PUT /api/user-settings/profile_name`; `user_settings`; one-time legacy `danbooru:profile-name` migration | `test_schema.py` DB/API contract; `test_release_layout.py` source contract; `test_backup_bundle.py` restore roundtrip; isolated browser save/reload 2026-07-18 | API-backed and backup-restored Profile name verified; broader Profile interactions remain unverified |
| VIEW-011 | ImageDetail overlay | `ImageDetail.svelte:121 mount`, `:167 load`, `:199 favorite`, `:230-267 heart/search`, `:273-315 tag/favorite-tag/collection`, `:360-384 relations`, `:398-534 user tags`, `:570-677 keyboard/zoom/drag`, `:688-726 collection mutation`, `:743 move`, `:767 open location`, `:781 delete`, `:835/966 fly transitions`, `:1532 heart keyframes` | Image detail, relations, favorites, user tags, collections, folder move, open location, delete, media endpoints; both DBs and filesystem | Golden, acquisition open-location, relation regression tests | Unverified interactive behavior |
| VIEW-012 | Profile asset ImageDetail path | `App.svelte:61-67`; `selectedArtistProfileAsset` at `stores.ts:217`; asset actions in `ProfileView.svelte` and `TagBrowseHeader.svelte` | Artist profile asset file API; `artist_profile_assets` and local archive files | Acquisition profile extraction test | Unverified |

## Browse, Search, and Image Management Contracts

| ID | Feature | Owning code | API and persistence | Tests | Status |
|---|---|---|---|---|---|
| BROWSE-001 | Search parsing: positive/negative tags, category prefixes, ID, filename, date, numeric, dimension, rating, extension, folder, orientation | UI: `SearchBar.svelte:24-34 normalization`, `:74 debounce`, `:97 commit`; backend: `modules/danbooru/search.py` (`parse_search_terms`, `build_where`) | `GET /api/images`, random, timelapse, CLI search; data DB query | `test_filename_search.py:15,29,42`; images golden | Unverified |
| BROWSE-002 | Search suggestions and keyboard selection | `SearchBar.svelte:38-59 suggestion parsing`, `:74 debounce`, `:113 select`, `:127/162 keyboard`, `:176 blur` | `GET /api/tags/suggest` | No timed UI test | Unverified |
| BROWSE-003 | Visible filter chips remove exactly one term | `FilterChips.svelte:11/15 remove`, `:43 classify`, `:57 style`, `:63 rating label` | Shared `activeTags` and derived `searchString` at `stores.ts:241-247` | No focused test | Unverified |
| BROWSE-004 | Multi-rating filter | `Sidebar.svelte:156-161`; `stores.ts:143/149/158 rating normalization`, `:213 activeRating` | `GET /api/images?rating=`; data DB `posts.rating` | `test_filename_search.py:42` | Unverified |
| BROWSE-005 | Sort and order | `TopBar.svelte:47/51`; `stores.ts:214-215`; `ImageGrid.svelte` request construction | `GET /api/images?sort=&order=` | Golden/OpenAPI | Unverified |
| BROWSE-006 | Page size and incremental loading | `stores.ts:230`; `ImageGrid.svelte:604 loadMore`, `:649 pagination` | `GET /api/images?offset=&limit=` | Golden/OpenAPI | Unverified |
| BROWSE-007 | Folder filter | `Sidebar.svelte:135`; `stores.ts:211-212` | `GET /api/folders`, `GET /api/images?folder=`; `files.root_id/relative_path/folder` | Folder roots/removal tests | Unverified |
| BROWSE-008 | Blacklist applied except exact post ID | `App.svelte:23-29 startup load`; `Sidebar.svelte:198-220`; `stores.ts:242` | Blacklist CRUD/names; `blacklist_tags`; `modules/danbooru/search.py build_where` | OpenAPI and search source | Unverified |
| BROWSE-009 | Context-aware Random | `TopBar.svelte:128`; `HomeView.svelte:492`; tag/collection branches in TopBar | `GET /api/images/random`, `GET /api/tags/random`, collection-scoped image query | OpenAPI | Unverified |
| BROWSE-010 | Duplicate review and scope | `stores.ts:238 duplicatesOnly`, `:239 duplicateScope`; `TopBar.svelte:58`; `ImageGrid.svelte` query | `GET /api/images?duplicates_only=&duplicate_scope=`; data DB MD5/post identity | Golden/OpenAPI source | Unverified |
| BROWSE-011 | Card selection, long press, and pin | `ImageCard.svelte:72-89 long press`, `:93 click`, `:101 pin`; `ImageGrid.svelte:228-251 selection`, `:682 pin` | Favorite/collection pin APIs depending context | No touch/timed test | Unverified |
| BROWSE-012 | Bulk favorites | `ImageGrid.svelte:286` | `PUT /api/favorites/batch`; `favorites` | OpenAPI | Unverified |
| BROWSE-013 | Bulk add/remove collection membership | `ImageGrid.svelte:318`, `:356`; collections membership/client methods | `POST /api/collections/memberships`, `PUT /api/collections/{id}/images`; `collection_items` | `test_regression_fixes.py:80` | Unverified |
| BROWSE-014 | Bulk move | `ImageGrid.svelte:381` | `PUT /api/images/batch/folder`; filesystem, sidecars, data DB path fields | Folder/acquisition tests cover parts; per-image path covered by `tests/test_image_move.py` | **Repaired 2026-07-24** — it calls the single move inside `except Exception`, so the same undefined name silently reported every image as failed. Bulk-level live regression still owed |
| BROWSE-015 | Bulk delete | `ImageGrid.svelte:412` | `DELETE /api/images/batch`; filesystem, thumbnails, both DBs | No live deletion test | Unverified; destructive |
| BROWSE-016 | Favorite and favorite pin | `ImageDetail.svelte:199`; `ImageCard.svelte:101`; grid/profile uses | Favorite toggle/pin/IDs/batch APIs; `favorites` | Golden legacy join test | Unverified |
| BROWSE-017 | Heart Spam counter and animation | `ImageDetail.svelte:230/245`, `:1532 keyframe`; `stores.ts:232` | `POST /api/images/{post_id}/heart-spam`; `image_views.heart_spam_count` | Schema/golden source | Unverified |
| BROWSE-018 | View counts and first/last viewed | `ImageDetail.svelte:167` requests `record_view`; Profile stats | `GET /api/images/{post_id}?record_view=`; `image_views` | Golden source | Unverified |
| BROWSE-019 | User image tags | `ImageDetail.svelte:398-534` | Add/delete user-tag routes; `user_image_tags`; removed upstream tags from `tag_removals` | `test_images_golden.py:100`; tag-history test | Unverified |
| BROWSE-020 | Parent, sibling, and child relations | `ImageDetail.svelte:360-384` | Image detail and refresh-relations routes; `posts.parent_id/has_children/child_ids_json`; `modules/danbooru/relations.py` | `test_regression_fixes.py:43` | Unverified |
| BROWSE-021 | Zoom, pan, fit, and overlay keyboard navigation | `ImageDetail.svelte:570-677`; `stores.ts:228 fitMode`; visible IDs at `:218` | Media/thumbnail endpoints; no DB mutation except view | No browser interaction test | Unverified |
| BROWSE-022 | Animated media behavior | `stores.ts:231 mediaPlayback`; `ImageCard`, `ImageDetail`, collection previews | `/api/image-file`, `/api/thumbnail`; filesystem | Thumbnail video frame test covers preview generation only | Unverified |
| BROWSE-023 | Open file location | `ImageDetail.svelte:767` | `POST /api/images/{post_id}/open-location`; managed-root containment | `test_acquisition.py:228` | Unverified current OS integration |
| BROWSE-024 | Single-image folder move | `ImageDetail.svelte:743` | `PUT /api/images/{post_id}/folder`; filesystem, canonical sidecar, DB identities | `tests/test_image_move.py`; folder roots/storage tests cover supporting contracts | **Repaired 2026-07-24** — the sidecar loop referenced an undefined `SIDECAR_SUFFIXES`, so every move raised NameError. Now named in `storage_layout.py` and regression-tested against disposable fixtures |
| BROWSE-025 | Single-image delete | `ImageDetail.svelte:781` | `DELETE /api/images/{post_id}`; filesystem, thumbnails, both DBs | No live deletion test | Unverified; destructive |
| BROWSE-026 | Original media delivery with byte ranges | `api.ts:494 imageFileUrl`; `modules/danbooru/media_files.py` range helpers; `images_media.py:705` | `GET /api/image-file/{file_id}`; filesystem | OpenAPI/golden source | Unverified |
| BROWSE-027 | Tiered thumbnail delivery | `api.ts:484 thumbnailUrl`; `ThumbnailCacheSettings.svelte`; `thumbnails.py:36-271`; `images_media.py:749` | `GET /api/thumbnail/{file_id}`; derived cache files | `test_thumbnails.py:34,46,68,88,114` | Unverified current runtime |

## Tags, Wiki, Artists, Profile, and Collections

| ID | Feature | Owning code | API and persistence | Tests | Status |
|---|---|---|---|---|---|
| META-001 | Tag browse, categories, letter/source filters, count/sort/page | `TagsBrowser.svelte:244-377` | `GET /api/tags`; `tags`, `post_tags`, user tag/favorite tables | OpenAPI | Unverified |
| META-002 | Danbooru tag wiki/info cache | `TagsBrowser.svelte:412`; `TagBrowseHeader.svelte:262` | `GET /api/tags/{tag}/wiki`; `tag_wiki_cache`; `modules/danbooru/tag_wiki.py` | Acquisition credentials/source tests; OpenAPI | Unverified network/cache behavior |
| META-003 | Wiki examples and remote “Not in library” placeholders | `TagsBrowser.svelte:438/535`; wiki types `api.ts:40-93` | Wiki route returns local/remote references; no remote hotlinking | Golden/OpenAPI source | Unverified |
| META-004 | Linked tags, aliases, implications, parent/sibling-style navigation | `TagsBrowser.svelte:490`; `TagBrowseHeader.svelte:288` | Wiki and related-tag APIs | No focused browser test | Unverified |
| META-005 | Tag banner and local cover override | `TagBrowseHeader.svelte:111-188 storage/override`, `:218 load covers`; `stores.ts:237 tagBannerHeight` | Local storage `danbooru:tag-cover:*`; images API | No focused test | Unverified |
| META-006 | Favorite tags and pinning | `TagsBrowser.svelte:552/574`; `Sidebar.svelte:169` | Favorite-tag toggle/pin/list/names; `favorite_tags` | OpenAPI | Unverified |
| META-007 | Favorite tag combinations | `TagsBrowser.svelte:151`, `:631/645/650` | Combo list/create/delete; `favorite_tag_combos` | OpenAPI | Unverified |
| META-008 | Related tags in sidebar | `Sidebar.svelte` related-tag load/display | `GET /api/tags/related` | OpenAPI | Unverified |
| META-009 | Artist follow/unfollow | `TagBrowseHeader.svelte:472 favorite state`, `:485/505 follow`; `TagsBrowser.svelte:592`; `ProfileView.svelte` | Artist-follow CRUD; `artist_follows` | OpenAPI | Unverified |
| META-010 | One-time notification baseline and post polling | `ArtistNotifications.svelte:34 mount`, `:84-90 schedule`, `:104 load`, `:116 check`, `:177 seen`, `:194 all`; `stores.ts:233-234` | Follow check/seen/list APIs; `artist_follows.notification_initialized_at`, `artist_follow_posts` | No network/polling test | Unverified |
| META-011 | Top-bar followed-artist notifications | `ArtistNotifications.svelte:154/158 menu`, `:162 open artist`, `TopBar.svelte:448` | Artist follow/check/seen APIs | No browser test | Unverified |
| META-012 | Profile followed-artist watchlist and focus panel | `ProfileView.svelte:249-367`, `:979-1009 animations`; `artistFocusRequest` at `stores.ts:223` | Follow, check, seen, assets; user DB | No focused test | Unverified |
| META-013 | Artist profile-media archive | `TagBrowseHeader.svelte:324-391`; `ProfileView.svelte:293`; backend `modules/danbooru/artist_profiles.py` | Asset list/refresh/bulk/file routes; `artist_profile_assets`; `<metadata>/artist_profile_archive` | `test_acquisition.py:156` covers profile URL extraction | Unverified network/archive behavior |
| META-014 | Artist history through retained profile assets | Same asset UI/backend as META-013; content-hash identity in backend | `artist_profile_assets` keeps changed versions | Acquisition source test only | Unverified |
| META-015 | Removed upstream tag history | ImageDetail removed tags; `tag_history.py:15-154`; refresh-tags success callback | `tag_removals`; archived replaced sidecars | `test_tag_history.py:54` | Unverified current migration/tool run |
| META-016 | Collection media-aware covers | `CollectionsView.svelte`; `CollectionPreviewGrid.svelte` | Collections list and thumbnail/media URLs; `collection_items` pin/order | Collection regression tests cover validation, not playback | Unverified |
| META-017 | Collection create/rename/description/delete/pin | `CollectionsView.svelte:23-124` | Collection CRUD/pin; `collections` | `test_regression_fixes.py:75,80` | Unverified |
| META-018 | Pin image inside collection | `ImageCard`/grid collection context | `POST /api/collections/{id}/images/{file_id}/pin`; `collection_items.pinned_at` | OpenAPI | Unverified |
| META-019 | Local profile identity, stats, and artwork | `ProfileView.svelte` name edit/load; `stores.ts` profile store/migration; `product.ts` default | `GET /api/stats`; `GET/PUT /api/user-settings/profile_name`; favorites, collections, views, tags, follows; selected local avatar/banner file IDs; `user_settings` display name | `test_schema.py`; `test_release_layout.py`; `test_backup_bundle.py`; isolated browser save/reload verified 2026-07-18 | Profile identity persistence and backup restore verified; stats/artwork remain without a focused live test |

## Settings and Browser Persistence Register

SET-001 through SET-023, SET-025/026, SET-028, and SET-029 are browser-local. SET-024
and SET-027 are user data in SQLite.
Resetting interface preferences must not touch SQLite, sidecars, originals,
credentials, backups, or metadata archives.

| ID | Stored key or state | Owner and temporary anchor | Consumers | Status |
|---|---|---|---|---|
| SET-001 | `danbooru:startup-view` | `stores.ts:189` | App initial view, Settings Browsing | Unverified |
| SET-002 | `danbooru:last-view` | `stores.ts:193-209` | Startup “last visited” | Unverified |
| SET-003 | `danbooru:home-layout` | `stores.ts:190` | Home Discovery/Classic | Unverified |
| SET-004 | `danbooru:active-rating` | `stores.ts:213` | Home, Browse, Tags, discovery views | Unverified |
| SET-005 | `danbooru:browse-sort` | `stores.ts:214` | Browse query and top bar | Unverified |
| SET-006 | `danbooru:browse-sort-order` | `stores.ts:215` | Browse query and top bar | Unverified |
| SET-007 | `danbooru:sidebar-open` | `stores.ts:226` | SidebarDock | Unverified interaction |
| SET-008 | `danbooru:sidebar-handle-position` | `stores.ts:227` | SidebarDock grip | Unverified interaction |
| SET-009 | `danbooru:fit-mode` | `stores.ts:228` | ImageGrid/ImageDetail media presentation | Unverified |
| SET-010 | `danbooru:image-size` | `stores.ts:229` | Grid card width | Unverified |
| SET-011 | `danbooru:image-page-size` | `stores.ts:230` | Grid paging | Unverified |
| SET-012 | `danbooru:media-autoplay` | `stores.ts:231` | Animated image/video cards and detail | Unverified |
| SET-013 | `danbooru:heart-spam-enabled` | `stores.ts:232` | ImageDetail | Unverified |
| SET-014 | `danbooru:artist-notifications-enabled` | `stores.ts:233` | ArtistNotifications | Unverified |
| SET-015 | `danbooru:artist-notification-interval` | `stores.ts:234` | ArtistNotifications polling timer | Unverified |
| SET-016 | `danbooru:motion-preference` | `stores.ts:235` | App dataset/CSS and animated components | Unverified |
| SET-017 | `danbooru:interface-scale` | `stores.ts:236` | App dataset/CSS | Unverified |
| SET-018 | `danbooru:tag-banner-height` | `stores.ts:237` | TagBrowseHeader | Unverified |
| SET-019 | `danbooru:daily-challenge-v2:<challenge_id>` | `DailyChallengeView.svelte:68-97` | Guess/reveal progress per challenge | Unverified |
| SET-020 | `danbooru:home:<version>:<kind>:<rating>` | `HomeView.svelte:350-391` | Home tags and rail presentation cache | Unverified |
| SET-021 | `danbooru:tag-cover:<version>:<tag>` | `TagBrowseHeader.svelte:111-188` | Local tag cover override | Unverified |
| SET-022 | Non-persisted duplicate mode/scope | `stores.ts:238-239` | TopBar, ImageGrid | Unverified |
| SET-023 | Non-persisted active tags/folder/collection/selection | `stores.ts:211-225`, `:241-247` | Browse, tags, collections, overlays | Unverified |
| SET-024 | `user_settings.profile_name`; legacy migration key `danbooru:profile-name` | `database.py:init_user_db`; `stats.py:get_user_setting/put_user_setting`; `stores.ts` API-backed profile store; `ProfileView.svelte` edit flow | Local Profile display name; default `Keivotos`; 40-character confirmed-value limit; included with `user.sqlite` backups | `test_schema.py`; `test_release_layout.py`; `test_backup_bundle.py` restore roundtrip; isolated browser save/reload verified 2026-07-18 | Verified; legacy-value migration branch characterized in source/unit contract |
| SET-025 | `keivotos:reddit-capture-defaults` | `modules/reddit/settings.ts`, `RedditSettings.svelte` | Prefills explicit Reddit Save-link capture options | Frontend source contract verified |
| SET-026 | `keivotos:youtube-download-defaults` | `modules/youtube/settings.ts`, `YouTubeSettings.svelte`, `YouTubeDownloadSheet.svelte` | Prefills quality, compatibility, companion audio, and auto-caption choice; does not authorize a download | Frontend check/source contract verified 2026-07-28 |
| SET-027 | Karaoke favorites/playlists/playback state | `modules/karaoke/catalog.py:ensure_user_schema`; `routers/karaoke.py`; `KaraokeDetail.svelte`; `LocalMediaPlayer.svelte` | Precious stable item/file identity, lyric offset/track, repeat, shuffle, and last played; Karaoke position is deliberately reset to zero | `test_karaoke_module.py`; player source contract verified |
| SET-028 | `keivotos:language-grid-size`, `keivotos:language-page-size`, `keivotos:language-autoplay` | `modules/language/stores.ts`; `LanguageSurface.svelte`; `LanguageDetail.svelte`; `LanguageSettings.svelte` | Languages card density, 30/60/120/all paging, local word-audio autoplay | Frontend check/source contract and isolated browser persistence surface verified 2026-07-28 |
| SET-029 | Preserved legacy `keivotos:player-control-reveal` key | `lib/stores.ts`; `components/AppSettingsModal.svelte`; `components/media/LocalMediaPlayer.svelte` | Compatibility-only persisted key; current shared player always reveals on pointer motion and toggles overlay visibility on background click | Settings/check source contract |

Settings UI ownership:

| ID | Settings surface | Owner | APIs/config changed | Status |
|---|---|---|---|---|
| SETTINGS-001 | Searchable section index and motion-aware jump/highlight | `AppSettingsModal.svelte:46 sections`, search index/ranking, `openSearchResult`, marker/highlight animation | Browser DOM only | `tests/test_settings_motion_contract.py`; timed browser behavior pending |
| SETTINGS-002 | Browsing/display preferences | `AppSettingsModal.svelte` and stores SET-001 through SET-018 | Browser local storage | Unverified |
| SETTINGS-003 | Folder registration, rescan, relocate, removal | `AppSettingsModal.svelte:153 load`, `:355-474 actions` | Folder APIs; config/user DB/filesystem | Unverified |
| SETTINGS-004 | Danbooru credentials | `AppSettingsModal.svelte:229 load`, `:269/286/301 save/check/clear` | Credential APIs; DPAPI-bound credential JSON | Unverified |
| SETTINGS-005 | Maintenance tool cards and polling | `AppSettingsModal.svelte:211 load`, `:319-345 run/cancel`, `:167-203 polling` | Tool APIs and task state | Unverified |
| SETTINGS-006 | Guided import | `LibraryImportSettings.svelte:30-83 polling`, `:106 run`, `:125 cancel`, `:137 automation`, `:153/157 lifecycle` | Import and automation APIs; ingest state/config | Unverified |
| SETTINGS-007 | Backup and restore | `BackupRestoreSettings.svelte:applyConfiguration`, `load`, `createCheckpoint`, `refreshEstimate`, `saveConfiguration`, `createBackup`, `inspectSelected`, `restoreSelected` | Fixed Keivotos backup directory, component preferences, backup/recovery APIs; retired `backup_destination` ignored/scrubbed | Focused backend/source and legacy-key retirement contract verified 2026-07-18 |
| SETTINGS-008 | Thumbnail cache | `ThumbnailCacheSettings.svelte:13 load`, `:18 cleanup/clear`, `:33 limit`, `:47 mount` | Thumbnail cache APIs and config | Unverified |
| SETTINGS-009 | Lazy settings sections | `settingsLoader.ts:3-7`; `AppSettingsModal.svelte:248 lazy section` | Defers folder/credential/maintenance/backup/cache/import requests | No bundle/runtime test | Unverified |
| SETTINGS-010 | Interface-only reset | `AppSettingsModal.svelte:632` plus persisted stores | Local storage only | Unverified safety boundary |
| SETTINGS-011 | Reddit archive/defaults/status category | `modules/reddit/RedditSettings.svelte`, `modules/reddit/settings.ts` | Status reads plus SET-025; no acquisition mutation | Source/API verified 2026-07-28 |
| SETTINGS-012 | Karaoke status/player/storage category | `modules/karaoke/KaraokeSettings.svelte` | `/api/karaoke/status`; no provider or data mutation | Check/build and source contract verified 2026-07-28 |
| SETTINGS-013 | YouTube defaults/status/safety/storage category | `modules/youtube/YouTubeSettings.svelte`, `settings.ts` | `/api/youtube/status` plus SET-026; no provider request | Check/build and source contract verified 2026-07-28 |
| SETTINGS-014 | Languages connection/profiles/dictionary/storage/display category | `modules/language/LanguageSettings.svelte`; `components/AppSettingsModal.svelte` | Cached `/api/language/status`, settings/profiles, independent DPAPI-protected AnkiConnect and optional KRDICT keys, explicit probe/preview/import, export plus SET-028; opening makes no Anki or KRDICT request | API/frontend contracts and isolated browser pass verified 2026-07-28 |
| SETTINGS-015 | Grouped Suite/Files/Modules navigation and shared Player category | `components/AppSettingsModal.svelte`; `lib/stores.ts`; `lib/focusTrap.ts` | Browser-local SET-029; no backend mutation | Frontend check/source contract verified 2026-07-29; narrow timed pass pending |
| SETTINGS-016 | Global transient feedback and action-menu primitives | `components/ui/{ToastViewport,ActionMenu}.svelte`; `lib/ui.ts`; mounted by `App.svelte` | In-memory notifications/actions only | Frontend check/source contract verified 2026-07-29; surface adoption tracked by owning features |

## Storage, Databases, Import, Recovery, and Maintenance

| ID | Contract | Owning code and temporary anchors | Data affected | Regression source | Status |
|---|---|---|---|---|---|
| DATA-001 | Windows Local AppData / Linux XDG defaults, portable Data case preservation, and preserved suite/module migrations | `config.py:_Guid`, `_windows_known_folder`, `local_app_data_directory`, `_portable_suite_home`, layout/migration helpers, `promote_user_database`, `promote_legacy_module_backups`, `_load`, `save_config` | Suite config/user DB/backups/logs/Files index; Danbooru module data; preserved prior layouts | `test_release_layout.py`, `test_user_db_promotion.py` | Copy/verify/preserve contracts passed 2026-07-23 |
| DATA-002 | Legacy default metadata flattening | `config.py:_files_match`, `_merge_legacy_entry`, `migrate_legacy_default_metadata`; called from backend lifespan | Metadata files; conflict-preserving copy/move logic | `test_release_layout.py` flatten and conflict-preservation tests | Isolated migration contracts passed 2026-07-19 |
| DATA-003 | Stable registered-root identity | `storage_layout.py:15 LibraryRoot`, `:21/25 IDs`, `:30 load`, `:60 match`, `:75 identity` | `registered_folders`; `files.root_id/relative_path` | `test_folder_roots.py:101,116,167`; `test_storage_layout.py:34` | Unverified |
| DATA-004 | Canonical sidecar layout and legacy candidates | `storage_layout.py:88 canonical_sidecar_path`, `:99/105 legacy paths`, `:113 candidates`, `:139 root directory` | `<metadata>/sidecars/roots/<root-id>/<relative-path>` | Acquisition/storage layout tests | Unverified |
| DATA-005 | Copy-and-verify sidecar migration, preserved source | `storage_layout.py:148 current files`, `:188 migrate_existing_sidecars`; startup `lifecycle.py:run_sidecar_layout_migration` | Sidecar copies and data DB migration key | `test_storage_layout.py:34,51` | Unverified migration |
| DATA-006 | Path containment and managed roots | `modules/danbooru/paths.py` root/path helpers; `storage_layout.py:139`; route-specific guards | Move/delete/open-location/sidecar targets | Acquisition open-location, release-layout guard, storage-layout escape test | Partial centralization; behavior unverified |
| DATA-007 | Data DB schema and additive upgrade | `schema.py:10-82 tables`, `:86-104 indexes`, `:115-133 ensure columns`; `database.py:136 init_data_db` | `danbooru.sqlite` | `test_schema.py:25` | Unverified current migration |
| DATA-008 | Shared user DB schema and additive upgrade | `database.py` user tables; `files_base/sources.py:ensure_sources_schema`; `suite_modules.py:ensure_schema` | Suite-root `user.sqlite`, including additive `files_sources.visible` and canonical role reads | Schema/files/suite/folder-role tests | Additive contracts passed 2026-07-23 |
| DATA-009 | Exclusive database gate for restore and active users | `database.py:15`, `:72`, `:84`, `:97`; `backup_bundle.py:320` | Both SQLite files | `test_backup_bundle.py:127` | Unverified current concurrency |
| DATA-010 | Pipeline download | `danbooru_gallery_dl.py:104 gallery-dl command`, `:116 config`, `:202 run_download`, `:263 normalize sidecars` | Media, transient gallery-dl config, canonical sidecars | Acquisition tests | Unverified network operation |
| DATA-011 | Metadata backfill by MD5/post ID | `danbooru_gallery_dl.py:390 request_json`, `:436 find_post_by_md5`, `:873 run_backfill` | Canonical sidecars; optional archive of replaced sidecars | Acquisition backfill test | Unverified network operation |
| DATA-012 | Sidecar index and cleanup | `danbooru_gallery_dl.py:508-753 path/sidecar helpers`, `:996 run_index`, `:1037 run_clean_sidecars` | JSON index and orphan sidecars | Acquisition external/offline-root tests | Unverified; cleanup is destructive |
| DATA-013 | Full SQLite rebuild | `danbooru_gallery_dl.py:1071-1339`, especially `:1151 import_payload_to_sqlite`, `:1339 run_sqlite` | Replaces/rebuilds data DB from sidecars | Schema/acquisition source | Unverified; recovery operation |
| DATA-014 | Incremental sync | `danbooru_gallery_dl.py:1425-1771`, especially `:1485 import_minimal_media`, `:1581 discover`, `:1676 enrich`, `:1740 finalize`, `:1771 sync` | Data DB and ingest state | Automation and beta-import tests | Unverified |
| DATA-015 | Guided four-phase import | `tools.py:103-163`; `LibraryImportSettings.svelte` | `ingest_state`, files/posts/tags; sidecars during metadata phase | `test_beta_import.py:75,106,134`; `test_tool_progress.py` | Unverified |
| DATA-016 | Automatic changed-media watcher | `automation.py:22 candidates`, `:62 status`, `:74 config`, `:89 tick`, `:128 loop`; started `lifecycle.py` | Runtime config; incremental sync | `test_automation.py:27,45,48` | Unverified background task |
| DATA-017 | Startup local recovery checkpoint | `local_recovery.py:21-75`; `lifecycle.py:run_user_recovery_checkpoint` | Verified rotated snapshots of `user.sqlite` | `test_local_recovery.py:47` | Unverified startup task |
| DATA-018 | Manual metadata backup | `backup_bundle.py:BACKUP_FORMAT`, `COMPONENTS`, `backup_estimate`, `backup_configuration`, `list_backups`, `_sqlite_snapshot`, `create_backup_bundle` | Fixed suite backup destination; selected DBs, sidecars/history, artist profile archive; never original media/thumbnails/credentials | `test_backup_bundle.py`; backup-path migration coverage in `test_release_layout.py` | Focused tests passed 2026-07-23 |
| DATA-019 | Backup inspection and rollback-safe restore | `backup_bundle.py:BACKUP_SUFFIX`, `list_backups`, `create_backup_bundle`, `inspect_backup_bundle`, `_safe_members`, `_quiesce_sqlite`, `restore_backup_bundle` | Fixed suite backup directory; `.keivotosbk` plus compatibility `.whbackup`; selected metadata with rollback directory | `test_backup_bundle.py` | Focused create/inspect/restore/compatibility/Profile-name roundtrip passed 2026-07-19 |
| DATA-020 | Thumbnail cache tiers, deduplication, cleanup, pruning | `thumbnails.py:36 normalize tier`, `:51 token`, `:58 key`, `:67 path`, `:98 remove`, `:112 video frame`, `:141 lock`, `:145 async prune`, `:163 ensure`, `:218-271 management` | Derived WebP cache only | `test_thumbnails.py:34,46,68,88,114` | Unverified |
| DATA-021 | DPAPI-bound Danbooru credentials | `credentials.py:24 protect`, `:44 unprotect`, `:62 saved payload`, `:72 saved`, `:84 effective`, `:94 status`, `:107 save`, `:131 clear`, `:136 environment` | Credential file bound to current Windows user; never returned in API | `test_acquisition.py:108,133` | Unverified current Windows account |
| DATA-022 | Default-loopback and developer-gated source-LAN browser/API security, with explicit private hotspot Host via `run-hotspot-local.sh` / `KEIVOTOS_HOTSPOT_HOST` | `security.py:LOOPBACK_HOSTS`, `_host_and_port`, `validate_local_browser_request`; middleware `app_factory.py:restrict_local_browser_access`; `app.py:LAN_DEVELOPER_ENV`, `main`; ignored `run-lan.local.bat` | Every HTTP request | `test_security.py`; launcher coverage in `test_regression_fixes.py` | Source LAN binds only detected adapter; ordinary source/frozen reject flag, focused tests verified 2026-07-17 |
| DATA-023 | Runtime/access log separation and retention | `runtime_logging.py`; suite log paths in `config.py`; launcher configuration | Dated `keivotos-runtime-*` and `keivotos-access-*` files | `test_regression_fixes.py` | Filename/rotation setup verified 2026-07-23 |
| DATA-024 | Tool task isolation, progress stream, cancellation, bounded recent results | `modules/danbooru/tools.py`; `routers/tools.py`; Settings/LibraryImport polling | In-memory task registry; subprocesses; checkpoint after sync | `test_tool_progress.py:18,32,50,84` | Unverified |
| DATA-025 | Native Windows folder picker | `app.py:145 helper`; `scripts/windows_folder_picker.py`; folder route `folders.py:258` | Returns a selected path only | `test_folder_picker.py:16,23,34,46` | Unverified current OS |
| DATA-026 | Folder add and targeted rescan | `folders.py:_is_generated_folder`, `_unsafe_library_root_reason`, `register_folder`, `rescan_folder`; Settings actions | Rejects filesystem roots and Keivotos-generated storage; ordinary registered roots and data DB incremental sync | Release-layout and folder-root tests | Focused unsafe-root test verified 2026-07-17 |
| DATA-027 | Folder relocation preserving identity | `folders.py:307`; `storage_layout.py`; Settings | Registered path plus data/user DB references | `test_folder_roots.py:116,167` | Unverified |
| DATA-028 | Counted folder removal modes | `folders.py:437 preview`, `:456 remove`; Settings | Unindex-only or current central sidecar deletion; originals/history preserved by contract | `test_folder_removal.py:131,158` | Unverified; destructive option |
| DATA-029 | Maintenance tool: Sync Database | `tools.py:38-44`, run dispatch `:381-425`; pipeline `run_sync` | Data DB, local recovery checkpoint after success | Automation/tool-progress tests | Unverified |
| DATA-030 | Maintenance tool: Backfill Metadata | `tools.py:46-51`, targeted route `:271`; pipeline `run_backfill` | Network, canonical sidecars | `test_acquisition.py:244` | Unverified |
| DATA-031 | Maintenance tool: Rebuild Database (Recovery) | `tools.py:53-57`, dispatch `:393-401`; pipeline `run_sqlite` then sync | Data DB replacement/rebuild | Schema/source tests | Unverified |
| DATA-032 | Maintenance tool: Clean Orphan Sidecars | `tools.py:59-63`, dispatch `:402`; pipeline `run_clean_sidecars` | Deletes confirmed orphan current sidecars | Acquisition offline-root test | Unverified; destructive |
| DATA-033 | Maintenance tool: Update Danbooru Tags | `tools.py:65-69`, dispatch `:403-425`; `tag_history.py` callback | Network, archived sidecars, canonical sidecars, data DB, tag removals | `test_tag_history.py:54`; acquisition tests | Unverified |
| DATA-034 | Files source registry, ancestry, and visibility | `files_base/sources.py`; `routers/files.py` | `files_sources` in shared `user.sqlite`; display name, one role, visible flag, resolved parent/child relationships | `test_files_api.py`, `test_folder_roles.py` | Focused unit/API verified 2026-07-23 |
| DATA-035 | Files disposable index, nested-root ownership, and lazy duplicate hashes | `files_base/schema.py`, `index.py`, `hashing.py` | `base/files.sqlite`; one absolute-path row owned by its deepest registered source; disk-derived facts and on-demand MD5 only | `test_files_base.py`, `test_files_api.py`, `test_folder_roles.py` | Focused nested scan/rescan/remove coverage verified 2026-07-23 |
| DATA-036 | Folder role adopt/release orchestration | `services/folder_roles.py`; descriptor hooks in `modules/danbooru`; compatibility operations in `routers/folders.py` | Shared registry, disposable Files/Danbooru index rows, Danbooru registration; originals/sidecars preserved | `test_folder_roles.py`, `test_folder_removal.py` | Unit verified 2026-07-23 |
| DATA-037 | Counted shared-folder forget | `folder_roles.forget_preview/apply_changes`; suite folder endpoints; `ManageFoldersDialog.svelte` | Removes shared registry + disposable index entries only after staged Save | Folder role/removal tests; runtime confirmation pending | Automated safety contract working |
| DATA-038 | Suite-owned browser storage migration | `frontend/src/lib/product.ts:migratePersistedStorage`; `stores.ts:persistedWritable` | `keivotos:*`; copies recognized legacy module-prefixed values without deleting them | Release-layout source contract; frontend check/build | Static/build verified 2026-07-23 |
| DATA-039 | Guarded Files byte serving | `files_base/serving.py`; `routers/files.py:serve_file` | Streams a source file; containment + inline allowlist + ranges; refuses traversal/symlink/suite-tree; forces active types to download | `test_files_serving.py` | Unit + browser verified 2026-07-24 |
| DATA-040 | Files base thumbnails | `routers/files.py:serve_file_thumbnail`, `:_thumbnail_cache_key`; `thumbnails.py:ensure_thumbnail` | Cached WebP for one browsed file; same containment chain as DATA-039; unrenderable types are 404 so the grid falls back to its glyph; key prefers the indexed content hash and falls back to identity/mtime/size so large media is never read just to draw a tile | `test_files_thumbnails.py` | Unit + browser verified 2026-07-25 against the real library (14 MB JPEG → 10 KB WebP, cold 449 ms / warm 3 ms; MP4 frame 302 ms; 840 MB zip refused in 21 ms) |
| DATA-040 | Files origin annotations, editor, badges | `files_base/annotations.py`; `routers/files.py` info/annotated/open/reveal; `FileInfoPanel.svelte` editor, `lib/filePreview.ts`, `FilesView.svelte` badges | `files_annotation*` in `user.sqlite`; lazy hash-on-annotate; local-state-first save then `changed` re-badges; moved-file note dormant until re-hash | `test_files_annotations.py`, `test_files_info.py` | Unit + browser verified 2026-07-24 (save/persist/badge/delete) |
| DATA-041 | Files attachment byte store | `files_base/attachment_store.py`; `routers/files.py` attachment endpoints; `FileInfoPanel.svelte` strip | Bytes content-addressed under first Files folder `<root>/.keivotos/attachments/` (`stored_root` per row); `.keivotos` excluded from scan; dedup; refcount-safe delete; empty-note prune | `test_files_attachments.py` | Unit + browser verified 2026-07-24 |
| DATA-042 | Attachment bytes as a backup component | `backup_bundle.py` (`file_attachments` component, `_attachment_records`, `_restore_attachments`); `config.py` default; `BackupRestoreSettings.svelte` toggle | Opt-in `.keivotosbk` component; bundled by content hash; restore re-materializes missing bytes create-only after the atomic restore, outside the metadata-tree rollback path | `test_backup_bundle.py` (roundtrip + create-only) | Unit verified 2026-07-24; live estimate exposure checked |
| DATA-045 | Reddit local preservation module (fork Slices 0-8 + archive workbench) | Capture: `scripts/reddit_capture.py`, `reddit_media.py`, `reddit_community.py`, `reddit_comments.py`; query: `scripts/reddit_library.py`; backend `modules/reddit/{url_targets,archive,arctic_shift,arctic_shift_api,direct_capture,reddit_api,media,download_jobs,community,comment_trees,library}.py`; descriptor `modules/reddit/__init__.py`; runtime `routers/reddit.py`, `server.py`; frontend `lib/redditApi.ts`, `components/AppSettingsModal.svelte`, `modules/reddit/{RedditSurface,RedditCaptureDrawer,RedditDownloadActivity,RedditPostCard,RedditThreadView,RedditCommentBranch,RedditCommunityView,RedditProfileView,RedditSettings}.svelte`, `modules/reddit/settings.ts`, `modules/{registry,surfaces}.ts` | Local JSON/JSONL/gzip/Arctic `.zst` and bounded Arctic Shift direct post/community/user JSON -> verified raw evidence + rebuildable `modules/reddit/reddit.sqlite`; direct user capture preserves and indexes at most 100 author-matching posts and comments each; additive post/community/profile refresh; local Popular/community/profile indexes; bounded-indent recursive threads and score/comment/upvote observation charts; confirmed media runs in one transient progress job and remains create-only SHA-256 objects; readable Files aliases converge by owner/content hash; only local contained media is rendered; shared `user.sqlite` stores optional-module enablement only; no web-archive/replay adapter | `test_reddit_capture.py`, `test_reddit_arctic_shift.py`, `test_reddit_api.py`, `test_reddit_media.py`, `test_reddit_community.py`, `test_reddit_comments.py`, `test_reddit_link_capture.py`, `test_reddit_library.py`, `test_reddit_runtime_api.py`, `test_reddit_frontend_contract.py`, `test_settings_motion_contract.py`, `test_suite_modules.py`, OpenAPI snapshot | Focused backend/frontend contracts and zero-warning frontend check verified 2026-07-31; timed browser verification pending |
| DATA-046 | Shared guarded yt-dlp process boundary | `backend/services/yt_dlp.py`; consumers `modules/reddit/media.py`, `modules/youtube/{provider,acquisition}.py` | Resolves frozen/source command, invariant ignore-config/no-playlist/no-overwrite/resume/retry/timeout/FFmpeg args, shell-free finite execution, bounded logs, progress, cancel, and credential redaction; provider modules still own URL and output policy | `test_yt_dlp_service.py`, `test_reddit_media.py`, `test_youtube_module.py` | Focused and full automated regression verified 2026-07-28; Reddit command behavior retained |
| DATA-047 | Karaoke local library and Kara.moe acquisition | Backend `modules/karaoke/{__init__,storage,catalog,lyrics,kara_moe,acquisition}.py`, `routers/karaoke.py`; frontend `lib/karaokeApi.ts`, `modules/karaoke/{KaraokeSurface,KaraokeDetail,KaraokeSettings}.svelte`; shared player `components/media/{LocalMediaPlayer,LyricsPanel}.svelte` | Rebuildable `modules/karaoke/karaoke.sqlite`; create-only versioned media plus stage/receipts/metadata/lyrics; precious `karaoke_*` favorites/playlists/playback except resumable position; exact Kara.moe plan/authorization and structural MP4 completeness health; clean replacement publication with obsolete path retained; Files-reference import with SHA-256 recheck; normalized cue-generated VTT endpoint; manual queue and ranged local media | `test_karaoke_module.py`, `test_karaoke_acquisition.py`, `test_karaoke_youtube_frontend_contract.py`, `test_suite_modules.py`, OpenAPI | Focused automated verification passed 2026-07-31; real provider replacement intentionally not run |
| DATA-048 | YouTube local acquisition and Karaoke handoff | Backend `modules/youtube/{__init__,storage,catalog,provider,acquisition}.py`, `routers/youtube.py`; frontend `lib/youtubeApi.ts`, `modules/youtube/{YouTubeSurface,YouTubeDownloadSheet,YouTubeSettings}.svelte`, `modules/youtube/settings.ts`; handoff `modules/handoff.ts` | Explicit yt-dlp metadata search/inspect, local same-provider thumbnail cache, actual format IDs, quality/compatibility/audio/manual-vs-auto captions, exact plan/authorization, one resumable/cancellable job, manual queue, create-only versioned update destinations with prior path retained, receipts, Files publication; YouTube→Karaoke references Files identity then attaches local subtitle bytes | `test_youtube_module.py`, `test_yt_dlp_service.py`, `test_karaoke_youtube_frontend_contract.py`, `test_module_registry.py`, `test_suite_modules.py`, OpenAPI | Focused automated verification passed 2026-07-31; real YouTube search/media transfer intentionally not run |
| DATA-049 | Languages learned-word library and read-only Anki mirror | Backend `modules/language/{__init__,storage,catalog,user_state,library,anki,imports}.py`, `routers/language.py`, shared `services/secret_store.py`; frontend `lib/languageApi.ts`, `modules/language/{LanguageSurface,LanguageDetail,LanguageComposer,LanguagePractice,LanguageSettings,LanguageSyncDialog,LanguageNameDialog,stores}.svelte`, `modules/{registry,surfaces}.ts`, `components/AppSettingsModal.svelte` | Stable source-keyed IDs; rebuildable word/sense/example/note/tag/media/per-card-progress/sync catalog; additive precious authored/override/note/media/favorite/list/profile/settings/practice rows; soft retirement and preservation-first manual merge; strict loopback read allowlist; preview-token-confirmed cancellable imports; versioned create-only media/receipts; ranged local serving; Files publication; JSON export; configurable Korean/EN/MN display profile; named filter presets and custom naming dialog; actionable Today practice; server-side Sentences/Grammar filtering and paging; practice totals/accuracy/daily activity/streak/per-word results; readable mastery and empty states | `test_language_module.py`, `test_language_library.py`, `test_language_anki.py`, `test_language_api.py`, `test_language_frontend_contract.py`, registry/folder/suite tests, OpenAPI snapshot | Focused 32-test backend/frontend contract pass and clean frontend check completed 2026-07-29; stub Anki only, no live Anki operation |
| DATA-050 | Languages Analyzer and expanded library presentation | Backend `modules/language/{analyzer,dictionary,library,catalog,user_state}.py`, `routers/language.py`, shared `services/secret_store.py`; frontend `lib/languageApi.ts`, `modules/language/{LanguageAnalyzer,LanguageBrowser,LanguageHangulAtlas,LanguageWordMenu,LanguageSurface,LanguageComposer,LanguageSettings}.svelte`; packaging `pyproject.toml`, `uv.lock`, `Keivotos.spec`, license collector/notices | Local Kiwi sentence/morpheme/POS/lemma analysis, deterministic provenance-labelled grammar and compound lemmas, koroman Revised Romanization, effective Anki/manual meaning matches, exact local example translation/audio reuse, explicit saved analyses with soft retirement, disposable morphology/KRDICT cache, fixed-host explicit-only KRDICT EN/MN lookup, system voice only, independent DPAPI secret keys; dark Keivotos Analyzer identity; touch-visible three-dot/context actions, Korean/English/Mongolian sorts, dense sortable Browser/inspector and reduced-motion Hangul Atlas | `test_language_analyzer.py`, `test_language_library.py`, `test_language_api.py`, `test_language_frontend_contract.py`, release-layout/license checks, OpenAPI snapshot | Focused automated verification completed 2026-07-29; renewed timed browser pass pending; no live Anki or KRDICT operation |

## Animation and Timed-Interaction Contracts

These contracts must be tested over elapsed time. Static screenshots or
source-string checks are insufficient.

| ID | Animation/interaction | Owner and timing anchors | Required regression observations | Status/lineage |
|---|---|---|---|---|
| MOTION-001 | **Keivotos app drawer** open/close | `AppDrawer.svelte:8 EXIT_MS=180`, `:14-44 all close paths`, `:138-170 drawer/backdrop transform and opacity keyframes` | Burger open; backdrop, close button, keyboard, Settings, Danbooru, Profile close paths; matching in/out direction; no stale backdrop | Unverified; independent contract |
| MOTION-014 | **Neutral local media player control overlay and subtitle panel** | `components/media/LocalMediaPlayer.svelte`; `LyricsPanel.svelte`; `lib/media.ts`; `modules/{karaoke/KaraokePlayer,youtube/YouTubePlayer}.svelte` | Pointer motion reveals; background click toggles the overlay; large centered −10/play/+10 controls; three-second playing idle hide resumes after overlays close; icon-only controls and repeat-one badge; pluggable subtitle panel, keyboard/PiP/fullscreen, stable native track IDs, and wrapper-owned module policy | Source/check contract verified 2026-07-31; renewed timed browser pass pending |
| MOTION-015 | **Languages detail/composer/practice overlays** | `modules/language/{LanguageDetail,LanguageComposer,LanguagePractice,LanguageSyncDialog}.svelte` | Composer enters from the right and closes from backdrop/button; detail Escape/arrow/Space shortcuts; practice Space/1/2/Escape; sync remains a blocking explicit-confirmation dialog | **Working** — isolated timed browser verification 2026-07-28 covered composer entry, detail Escape, practice Space/2 and saved missed replay, plus the explicit sync boundary; source contracts cover remaining keyboard paths |
| MOTION-016 | **Languages menu, Browser inspector, Hangul Atlas and Analyzer** | `modules/language/{LanguageWordMenu,LanguageBrowser,LanguageHangulAtlas,LanguageAnalyzer}.svelte` | Three-dot outside/Escape closure and keyboard actions; sortable table and responsive inspector; Atlas focus/hover meaning reveal and reduced motion; long Analyzer rail horizontal scroll, token selection, history sheet, responsive stack | **Working** — timed isolated browser verification 2026-07-28 covered Escape/outside closure, edit/list actions, table sorting and inspector independence, Atlas keyboard-focus reveal, real Kiwi selection, saved history, local detail, and composer prefill; source contracts cover responsive/reduced-motion branches |
| MOTION-002 | **Danbooru sidebar** expand/hide | `SidebarDock.svelte:91`, `:108`, `:157 width 280ms`, `:168 transform 280ms`; rAF intro gate | Entry slide on Browse/Tags mount, open, close, rapid reversal, repeated toggles, one persistent sidebar, no overlapping copy | **Working** — manually confirmed 2026-07-25 in a real browser: slide-in on Browse entry, grip drag reposition-and-persist, click open/close, saved position across reload. |
| MOTION-003 | Sidebar draggable/auto-hide grip | `SidebarDock.svelte:29`, `:38-84`, `:113-114`, `:171` | Click toggle, drag without toggle, top/bottom clamp, saved position, hover reveal/return, keyboard movement, pointer cancellation | **Working** — manually confirmed 2026-07-25 in a real browser: slide-in on Browse entry, grip drag reposition-and-persist, click open/close, saved position across reload. |
| MOTION-004 | Sidebar overflow scrolling | `Sidebar.svelte` body CSS and long content groups | Wheel/keyboard scroll when folders, blacklist, related tags, and collections exceed viewport | Unverified |
| MOTION-005 | Home nine-second spotlight | `HomeView.svelte:155/260-273`, progress/motion CSS `:1027-1210` | Five thumbnails, center growth, previous shrink/left move, hero change, timer reset on click, midnight reset, reduced-motion behavior | Unverified |
| MOTION-006 | Home independent moving lanes | `HomeView.svelte:431`, `releaseLaneFocusPause`, lane CSS/keyframes | Independent hover and keyboard-focus pause/resume, other lanes keep moving, ImageDetail return does not freeze, reduced-motion manual scroll | Source contract restored 2026-07-16; timed browser verification required |
| MOTION-007 | ImageDetail entry/exit and heart burst | `ImageDetail.svelte:835/966 fly`, `:1532 heart keyframe` | Both transition directions, overlay close paths, no lost state, repeated heart behavior | Unverified |
| MOTION-008 | ImageDetail zoom/pan | `ImageDetail.svelte:596-677` | Wheel, click, drag, reset, fit mode, keyboard, boundary behavior | Unverified |
| MOTION-009 | Profile focused-artist panel | `ProfileView.svelte:979-1009` | Focus/open/close direction, rapid artist changes, state restoration | Unverified |
| MOTION-010 | Settings marker/highlight and background pause | `AppSettingsModal.svelte:598-626`, `:1187-1207`; `app.css:25-31` | Search jump highlight, modal lifetime pause, restoration on every close path | Unverified |
| MOTION-011 | Timelapse playback | `TimelapseBrowser.svelte:33/62`, `:92-114`, `:267`, `:434/461` | Simple/advanced timers, speed changes, seek, play/pause, fullscreen, reload, destroy cleanup | Unverified |
| MOTION-012 | Daily Challenge reveal | `DailyChallengeView.svelte:153-204` | Guess, suggestion, submit, reveal, persisted reload state, next-day challenge key | Unverified |
| MOTION-013 | Card long press | `ImageCard.svelte:72-93` | Touch/mouse threshold, cancel, click suppression, selection result | Unverified |

## Background Jobs and Lifecycle Work

| ID | Job | Owner | Trigger and state | Safety boundary | Status |
|---|---|---|---|---|---|
| JOB-001 | Startup DB initialization | `lifecycle.py:lifespan`, `database.py`, `schema.py` | Every FastAPI lifespan start | Additive migrations; failure must be explicit | Unverified |
| JOB-002 | Startup local recovery checkpoint | `lifecycle.py:run_user_recovery_checkpoint`, `local_recovery.py` | Background thread after server starts | Failure logged, does not block startup | Unverified |
| JOB-003 | Startup canonical-sidecar migration | `lifecycle.py:run_sidecar_layout_migration`, `storage_layout.py:188` | Once per data DB migration key | Copy/verify only; preserved source; failure leaves key unset | Unverified |
| JOB-004 | Legacy metadata flattening | `lifecycle.py:lifespan`, `config.py:239` | Before DB initialization | Preserve conflicts and do not overwrite | Unverified |
| JOB-005 | Automatic changed-media ingestion | `lifecycle.py:lifespan`, `automation.py:128` | While app is open and enabled | Ignores unavailable roots; incremental sync only | Unverified |
| JOB-006 | Artist notification polling | `ArtistNotifications.svelte:84-90` | While mounted and enabled | Post IDs only; no remote image download/hotlink; baseline before notifications | Unverified |
| JOB-007 | Settings tool polling | `AppSettingsModal.svelte:167-203` | While maintenance section/modal needs task state | Bounded polling and cleanup required | Unverified |
| JOB-008 | Guided import polling | `LibraryImportSettings.svelte:30-83` | During import task | Incremental result index, bounded recent state, cancel support | Unverified |
| JOB-009 | Timelapse timers | `TimelapseBrowser.svelte:33/62`, lifecycle `:397/409` | During playback | Clear timers on mode change/destroy | Unverified |
| JOB-010 | Home daily/timed presentation | `HomeView.svelte:155/260`, lifecycle `:87/93` | Mounted Home | Stable within local day; reset at midnight; timer cleanup | Unverified |
| JOB-011 | Thumbnail pruning | `thumbnails.py:145 _schedule_thumbnail_prune` | After thumbnail activity | Runs outside response path; bounded key locks | Unverified |
| JOB-012 | Browser-open readiness probe | `app.py:85-99` | Launcher without `--no-browser` | Daemon thread, 120-second limit, loopback URL | Unverified |

## Persistence Ownership

### `danbooru.sqlite` — rebuildable library index

Schema owner: `backend/schema.py:10-104`; runtime initialization:
`backend/database.py:136-153`; pipeline writes:
`scripts/danbooru_gallery_dl.py:1071-1771`.

| Table | Purpose and feature owners | Main writers/readers |
|---|---|---|
| `files` | Path, root identity, relative path, extension, MD5, size, timestamps; Browse/media/folders/import | Pipeline, folder routes, images/media routes |
| `posts` | Danbooru post metadata, rating, score, dimensions, dates, relations | Pipeline/backfill; image, discovery, stats, tag routes |
| `tags` | Canonical tag names/categories/counts | Pipeline; search, tags, discovery, suggestions |
| `post_tags` | Post-to-tag relation | Pipeline; search, tags, wiki examples, discovery |
| `metadata` | Schema/migration markers including `sidecar_layout_v2_complete` | Startup maintenance, schema/pipeline |
| `sync_manifest` | Incremental sync identity and file state | Pipeline sync/discover/finalize |
| `ingest_state` | Guided import phase/status/progress | Pipeline and import APIs |

### Optional-module rebuildable indexes

| Database | Rebuildable contents | Precious state excluded |
|---|---|---|
| `modules/reddit/reddit.sqlite` | Normalized posts/comments/community observations, provenance, FTS, media events, capture jobs | Optional enablement only is in `user.sqlite`; raw evidence and media remain on disk |
| `modules/karaoke/karaoke.sqlite` | Song metadata/tags/lyrics, acquisition plans/jobs, local artifact paths | Favorites, playlists, playlist membership, and playback state are in `user.sqlite` |
| `modules/youtube/youtube.sqlite` | Downloaded-video catalog, artifact paths, acquisition plans/jobs | The browser-only confirmation-sheet defaults are localStorage; media/receipts remain on disk |
| `modules/language/language.sqlite` | Mirrored/manual projection, senses/examples/notes/tags, media projection, every Anki card's progress, sync runs | Authored values, overrides, personal media associations, lists, profiles, settings, and practice stay in `user.sqlite`; media/receipts remain on disk |
| `modules/manga/manga.sqlite` | Manayomi CBZ identity, root-relative indexed paths, metadata, tags, and derived cover references | `modules/manga/user.sqlite` preserves roots, favorites, pins, categories, settings, first-added timestamps, and reading progress/history; original CBZ media remain in registered external roots |

### `user.sqlite` — authoritative user data

Schema owner: `backend/database.py:319-469`; additive upgrades and indexes:
`backend/database.py:168-318`.

| Table | Purpose and feature owners | Main routes/helpers |
|---|---|---|
| `favorites` | Favorite membership, durable path/MD5 identity, pin time | Favorite routes; image/grid/profile queries |
| `collections` | Name, description, created and pinned time | Collection CRUD/pin routes |
| `collection_items` | Collection membership, durable identity, image pin | Collection image/membership routes |
| `favorite_tags` | Favorite tag category and pin | Favorite-tag routes; Sidebar/Tags |
| `favorite_tag_combos` | Named multi-tag shortcuts | Combo routes; TagsBrowser |
| `blacklist_tags` | User blacklist | Blacklist routes; search exclusion |
| `user_image_tags` | User-owned tags with durable identity/category | Image user-tag routes; ImageDetail/search |
| `image_views` | Counts, first/last view, Heart Spam count | Image detail and stats |
| `tag_wiki_cache` | Cached Danbooru wiki/artist data | Tag wiki route |
| `artist_follows` | Follow state, notification baseline/check/seen fields | Artist follow routes |
| `artist_follow_posts` | Discovered Danbooru post IDs and seen state | Artist check/seen/notification UI |
| `artist_profile_assets` | Content-addressed archived avatar/banner versions | Artist profile asset routes |
| `tag_removals` | Tags removed by upstream refresh, durable file identity | Tag history and ImageDetail |
| `registered_folders` | Absolute external roots, stable root ID, display name | Folder/storage/path resolution |
| `user_settings` | Backed-up local user preferences, currently `profile_name` | User-settings GET/PUT routes; Profile |
| `files_sources` | Shared folder registry: stable source ID/path, display-only name, exactly one canonical role, sidebar visibility | Files API; suite Manage folders batch; module publication hooks |
| `suite_enabled_modules` | Enabled optional descriptor slugs; the required Files base is never persisted here | Suite module API and shell |
| `files_annotations` | User-authored origin note per file (keyed by content hash) or folder (keyed by path): description + last-known-location hint | `files_base/annotations.py`; `/api/files/info` |
| `files_annotation_links` | Labeled, kinded origin links (source/discussion/mirror/author/other) for an annotation | `files_base/annotations.py`; `/api/files/info` |
| `files_annotation_attachments` | User screenshots/clips attached to an annotation; bytes stored on disk, keyed by content hash (byte store is a later slice) | `files_base/annotations.py`; `/api/files/info` |
| `karaoke_favorites` | Favorite song identity plus optional file SHA-256 | Karaoke library/detail API |
| `karaoke_playlists` | User-authored playlist names/descriptions/timestamps | Karaoke playlist API |
| `karaoke_playlist_items` | Ordered playlist membership keyed by stable item/file identity | Karaoke playlist API/player queue |
| `karaoke_playback_state` | Position, duration, completion, lyric track/offset, repeat, shuffle, last played | Karaoke playback GET/PUT and local player |
| `language_user_words`, `language_user_overrides`, `language_user_notes`, `language_user_media` | Authored words, mirrored-field edits, personal notes, and manual media associations; retire/merge markers instead of hard-delete | Languages word/detail/media API and import merge |
| `language_favorites`, `language_word_lists`, `language_word_list_items` | Precious word organization with list/list-item retirement columns | Languages favorites/lists/bulk API and surface |
| `language_sync_scope`, `language_profiles`, `language_anki_settings` | Confirmed deck scope, field mapping, port/mode, and cached probe state; optional key remains in the descriptor credential file through DPAPI | Languages settings and explicit Anki preview/import |
| `language_practice_sessions`, `language_practice_results` | Local-only self-graded sessions and answers; never Anki scheduling state | Languages practice API/surface/stats |
| `language_analyzer_saved` | Explicitly saved source text, authored English/Mongolian translations, and the inspected analysis; retirement is a tombstone | Languages Analyzer history; exported with the rest of precious language state |

### Filesystem/config persistence

| Store | Owner | Contents and exclusions |
|---|---|---|
| Runtime config JSON | `config.py:265 save_config`, `:278 snapshot` | Paths, watcher, backup, cache preferences; no browser-only UI preferences |
| Browser local storage | `product.ts:STORAGE_PREFIX/migratePersistedStorage`; `stores.ts:persistedWritable`; component-owned browser state including Reddit/YouTube settings | Per-device UI preferences and presentation caches only; current suite keys use `keivotos:` including `youtube-download-defaults`; recognized legacy module-prefixed settings copy forward without deleting their source; profile name and Karaoke user state live in SQLite |
| Canonical sidecars | `storage_layout.py`, pipeline | Durable per-media Danbooru metadata under stable root identity |
| Sidecar history | Pipeline archive helpers | Replaced sidecars used for history/tag removals; preserved by backup/removal contracts |
| Local recovery | `local_recovery.py` | Automatic/manual verified `user.sqlite` checkpoints |
| `.keivotosbk` / legacy `.whbackup` | `backup_bundle.py` | Selected metadata components only; never originals, thumbnails, or credentials |
| Thumbnail cache | `thumbnails.py` | Derived 300/600/1200 WebP files; safe to clear |
| Artist profile archive | `modules/danbooru/artist_profiles.py` | User-triggered Twitter/X and Pixiv avatar/banner versions |
| Credentials | `credentials.py` | DPAPI-bound Danbooru username/API key; excluded from backups/API responses |
| Logs | `runtime_logging.py` | Separated runtime and access logs with retention |

## Complete API Register

`tests/snapshots/openapi.json` is the authoritative current inventory. V1.1.0
added always-mounted `/api/files/*` endpoints and `/api/suite/*` descriptor and
folder-management endpoints while preserving every grandfathered Danbooru path;
V1.1.1 added the file-serving and origin-annotation endpoints under
`/api/files/*`. The Reddit fork adds always-mounted, enabled-state-gated
`/api/reddit/*` feed, search, post, community, status, and local-media paths.
Karaoke and YouTube add stable enabled-state-gated `/api/karaoke/*` and
`/api/youtube/*` boundaries.
`backend/server.py` also serves the non-API frontend root when
`frontend/dist` exists.

Frontend method anchors are in `frontend/src/lib/api.ts:499-800`.

### Folders — `backend/routers/folders.py`

| Route anchor | Method and path | Feature IDs | Persistence/effect | Status |
|---|---|---|---|---|
| `folders.py:169` | `GET /api/folders` | BROWSE-007, DATA-003 | Reads data/user DB and configured roots | Unverified |
| `folders.py:208` | `POST /api/folders` | DATA-026 | Registers root and starts targeted sync | Unverified |
| `folders.py:258` | `POST /api/folders/browse` | DATA-025 | Native picker helper; no DB by itself | Unverified |
| `folders.py:292` | `POST /api/folders/{folder_identifier}/rescan` | DATA-026 | Targeted incremental sync | Unverified |
| `folders.py:307` | `PUT /api/folders/{root_id}/path` | DATA-027 | Rewrites registered path and references | Unverified |
| `folders.py:437` | `GET /api/folders/{folder_identifier}/removal-preview` | DATA-028 | Count-only DB/filesystem inspection | Unverified |
| `folders.py:456` | `DELETE /api/folders/{folder_identifier}` | DATA-028 | Unindex or central-sidecar deletion mode | Unverified/destructive |

### Files base and suite — `backend/routers/files.py`, `suite.py`

| Route group | Feature IDs | Persistence/effect | Status |
|---|---|---|---|
| `/api/files/sources`, `/browse`, `/search`, source scan/remove | ARC-012, DATA-034/035 | Shared registry plus disposable Files index; legacy remove remains unindex-only | API/unit verified |
| `/api/files/hash`, `/duplicates` | DATA-035 | Bounded on-demand hashing of size-colliding files only | Unit verified |
| `/api/files/fs`, `/pick` | DATA-025, DATA-034 | Read-only contained subfolder listing or native top-level helper selection | Unit verified; native desktop not rerun |
| `/api/files/file` | DATA-039 | Guarded byte serving with containment, inline allowlist, `nosniff`, ranges | Unit + browser verified 2026-07-24 |
| `/api/files/thumbnail` | DATA-040 | Cached WebP thumbnail for a browsed file; `size` 300/600/1200, `v` is a client cache-buster the server ignores | Unit + browser verified 2026-07-25 |
| VIEW-040 | Files grid thumbnails | `FilesView.svelte` tile block, `:thumbFailed/:thumbVersion/:entryKey`; `filePreview.ts:hasThumbnail`; `filesApi.ts:thumbnailUrl` | `GET /api/files/thumbnail`; derived WebP cache only | Client-gated to the backend's real thumbnail set, lazy, glyph fallback on error | Browser verified 2026-07-25: 217 image tiles decode, non-visual folders issue zero requests |
| DATA-044 | Read-only archive listing | `files_base/archives.py:list_archive/:is_archive`; `routers/files.py:list_archive`; `FileInfoPanel.svelte:loadArchive`; `filePreview.ts:isListableArchive` | `GET /api/files/archive`; reads only the zip central directory, writes nothing | Never decompresses (asserted by test); names are inert display text; 2000-entry cap; content-sniffed not extension-trusted | `test_files_archives.py` (12 tests) | Browser verified 2026-07-25 on the real library: 840 MB zip listed in **53 ms** reporting 1861 MB unpacked; 253 MB model zip 38 entries; Japanese member names intact; plain `.txt` 415, directory 404, traversal 400 |
| DATA-043 | Copy origin info between subjects | `routers/files.py:copy_info`, `CopyInfoRequest`; `FileInfoPanel.svelte:openPicker/:copyFrom`; `filesApi.ts:copyInfo`, `ApiError` | `POST /api/files/info/copy`; `files_annotations`/`_links`/`_attachments` in `user.sqlite`; no bytes written | Additive union merge; 409 guards an existing description; attachment rows re-point at the existing content-addressed blob | `test_files_copy_info.py` (10 tests; description guard and link union both mutation-verified) | Browser verified 2026-07-25 on an isolated `KEIVOTOS_HOME`: copy carried description+link+attachment, source untouched, repeat idempotent, 409 preserved target text, overwrite honoured, picker excludes self |
| VIEW-043 | Files info panel order + type scale | `FileInfoPanel.svelte` Origin block (now above `<dl>`), facts/path/link classes | No API change; presentation only | Origin moved above the facts; 12px→14px body, 10px→12px mono, `break-all`→`break-words` on Path | Browser verified 2026-07-25: Origin heading y=206 vs facts y=299; computed 14px/12px; Path `overflow-wrap: break-word`, `word-break: normal`; Origin visible with no scrolling on an image subject |
| VIEW-044 | Files info panel metadata sections | `FileInfoPanel.svelte:sections/:readImageDimensions/:readVideoDimensions/:formatRelativeDate`; `filesApi.ts:FileInfo`; `routers/files.py:FileInfoModel/:get_info/:_indexed_facts` | `GET /api/files/info`; `files_index.indexed_at`; `keivotos:files-info-sections` | No empty fallback preview; Origin remains first; collapsible remembered Origin/Details/Contents; Format, preview-derived dimensions, Added, relative dates, Annotated on, existing path/MD5/actions | `test_files_info.py`; OpenAPI snapshot; frontend check/build | Verified 2026-07-31: 405 tests, compile/check/build; real ZIP compact fallback + Added dates; PNG 750×887; collapsed Details survived reload; clean console |
| VIEW-042 | Files info panel resize | `FileInfoPanel.svelte:startResize/:onResize/:endResize/:nudgeWidth`; `stores.ts:filesInfoWidth`, `FILES_INFO_MIN/MAX_WIDTH` | `keivotos:files-info-width`; no API change | Pointer drag with keyboard fallback; panel docks to the right edge (the cluster cap was removed — see below) | Browser verified 2026-07-25 at 1990px: **dead space 0** at both 416px and 760px, panel flush right, grid 1254px/6 columns at default and 910px when dragged wide, clamps at 300/760, arrows step 16/48, survives reload. **Drag exercised with synthetic PointerEvents (capture stubbed); real drag feel unverified — non-compositing pane** |
| VIEW-041 | Files grid size control | `GridSizeMenu.svelte`; `stores.ts:filesGridSize`, `:thumbnailTierFor`; `FilesView.svelte:gridSize/:thumbTier/:thumbBoxPx` | Shared scale (`imageSizeOptions`), per-surface value; `keivotos:files-grid-size` vs `keivotos:image-size` | No API change; drives columns, picture box, and requested tier | Browser verified 2026-07-25: Small 144px/tier 300, Large 296px, Absurd 600px/tier 600, persisted across reload, `keivotos:image-size` unchanged throughout |
| DATA-042 | Origin attachment as tile face | `routers/files.py:_attachment_cover`; `FilesView.svelte:thumbVersion/:wantsThumbnail/:annotationRevision` | Attachment outranks folder cover and the file's own image; resolved hash-first like `get_info` so no fresh read; annotated tiles carry `-r<n>` so an attach visibly refreshes an `immutable` response | `test_files_thumbnails.py:AttachmentCoverTests` (precedence mutation-verified) | Verified 2026-07-25 on an isolated `KEIVOTOS_HOME`: zip 404→90x30, folder 404→70x50, photo 60x45→24x18 |
| DATA-041 | Files folder covers | `routers/files.py:_folder_cover` | Two index-friendly queries (direct children, then a `parent` range) both using `idx_files_index_source_parent`; scoped to one `source_id` so a nested source is never borrowed from; the `rel + '/'` lower bound stops `rel-vol2` matching | `test_files_thumbnails.py:FolderCoverTests` | Browser verified 2026-07-25: `OST` covered from `Cover.jpg` three levels deep (265 ms cold / 3 ms warm); nested `Danbooru` source correctly refused a cover |
| `/api/files/info` (GET/PUT/DELETE), `/open`, `/reveal` | DATA-040, VIEW-044 | GET returns first-indexed time plus optional Origin annotation; writes remain hash-on-annotate; open/reveal remain guarded | Unit + browser verified 2026-07-31 |
| `/api/files/annotated` | DATA-040 | Relative paths in a source that carry a note, for tile badges; file notes resolved via content hash | Unit + browser verified 2026-07-24 |
| `/api/files/attachment` (POST), `/attachment/{id}` (GET/DELETE) | DATA-041 | Upload (raw body), serve (ranges), refcount-safe delete of image/video attachments | Unit + browser verified 2026-07-24 |
| `/api/suite/modules*` | ARC-011, SHELL-003 | Static descriptor projection and optional enablement state | API/unit verified |
| `/api/suite/folders/apply`, `/folders/{source_id}/forget-preview` | SHELL-015, DATA-036/037 | Validated staged registry edits, role dispatch, counted forget | Service/OpenAPI verified; rename/visibility batch verified in isolated browser |
| `/api/reddit/feed`, `/search`, `/posts/{post_id}`, `/community/{subreddit}`, `/communities`, `/profiles*`, `/status` | DATA-045 | Read-only cursor or local-Popular feed, FTS, recursive detail, community directory, profile activity, and status views; status also reports exact archive/media/Files paths, runtime busy state, and finite limits | API/unit reverified 2026-07-29; feed 500 regression covered |
| `POST /api/reddit/capture`, `/posts/{post_id}/refresh`, `/community/{subreddit}/refresh` | DATA-045 | Explicit bounded Arctic Shift post/community/user capture and additive refresh; enabled-only, one at a time, exact responses before indexing, no media-byte download | API/unit verified 2026-07-29; prior isolated post/community capture and timed browser verification retained |
| `POST /api/reddit/media/plan`, `/media/download` | DATA-045 | Offline owner-scoped image/video/Linked-files selection, exact confirmation hash/count, bounded acquisition, content-addressed install, friendly Files publication | API/unit verified; real network download intentionally not run |
| `/api/reddit/media/{sha256}` | DATA-045 | Contained local SHA-256 media only, safe disposition, nosniff, immutable cache and ranges | API/unit verified 2026-07-27 |
| `/api/karaoke/status`, `/kara-moe/search`, `/kara-moe/{id}`, `/kara-moe/plan`, `/kara-moe/download`, `/jobs*` | DATA-047 | Enabled-only provider metadata and exact plan/confirm/resume/cancel jobs; status reads local counts/paths only | API/unit verified; live provider transfer intentionally not run |
| `/api/karaoke/library*`, `/library/import-files`, `/library/{id}/lyrics`, `/favorite`, `/playlists*`, `/playback`, `/media/*` | DATA-047 | Local catalog, Files reference, create-only subtitles, precious user state, and range-capable local bytes | API/unit verified 2026-07-28 |
| `/api/youtube/status`, `/search`, `/videos/{id}`, `/plan`, `/download`, `/jobs*` | DATA-048 | Explicit bounded metadata/cache and exact actual-format plan/confirm/resume/cancel jobs | API/unit verified; live provider search/transfer intentionally not run |
| `/api/youtube/library*`, `/search-thumbnails/{id}`, `/media/*` | DATA-048 | Local catalog, guarded cached image, range-capable completed local media, and Files handoff identity | API/unit verified 2026-07-28 |

### Tags and stats

| Route anchor | Method and path | Feature IDs | Persistence/effect | Status |
|---|---|---|---|---|
| `tags.py:9` | `GET /api/tags` | META-001 | Reads tag/index/user state | Unverified |
| `tags.py:86` | `GET /api/tags/{tag_name}/wiki` | META-002–META-004 | Reads/writes `tag_wiki_cache`; may call Danbooru | Unverified |
| `stats.py:get_user_setting` | `GET /api/user-settings/{key}` | META-019, SET-024 | Reads supported `user_settings` values | Isolated route-function contract verified 2026-07-18 |
| `stats.py:put_user_setting` | `PUT /api/user-settings/{key}` | META-019, SET-024 | Normalizes and upserts supported `user_settings` values | Isolated route-function contract verified 2026-07-18 |
| `stats.py:9` | `GET /api/stats` | META-019 | Aggregates both DBs | Unverified |

### Collections — `backend/routers/collections.py`

| Route anchor | Method and path | Feature IDs | Persistence/effect | Status |
|---|---|---|---|---|
| `collections.py:9` | `POST /api/collections/memberships` | BROWSE-013 | Reads membership for file IDs | Unverified |
| `collections.py:34` | `GET /api/collections` | VIEW-004, META-016 | Reads collections and previews | Unverified |
| `collections.py:92` | `POST /api/collections` | META-017 | Inserts collection | Unverified |
| `collections.py:108` | `PUT /api/collections/{collection_id}` | META-017 | Updates name/description | Unverified |
| `collections.py:133` | `POST /api/collections/{collection_id}/pin` | META-017 | Toggles collection pin | Unverified |
| `collections.py:152` | `DELETE /api/collections/{collection_id}` | META-017 | Deletes collection/memberships | Unverified |
| `collections.py:160` | `POST /api/collections/{collection_id}/images/{file_id}/pin` | META-018 | Toggles item pin | Unverified |
| `collections.py:193` | `PUT /api/collections/{collection_id}/images` | BROWSE-013 | Bulk add/remove memberships | Unverified |

### User library — `backend/routers/user_library.py`

| Route anchor | Method and path | Feature IDs | Persistence/effect | Status |
|---|---|---|---|---|
| `user_library.py:9` | `PUT /api/favorites/batch` | BROWSE-012 | Bulk favorite add/remove | Unverified |
| `user_library.py:54` | `POST /api/favorites/{file_id}` | BROWSE-016 | Toggle favorite | Unverified |
| `user_library.py:80` | `GET /api/favorites/ids` | BROWSE-016 | Reads favorite IDs | Unverified |
| `user_library.py:94` | `POST /api/favorites/{file_id}/pin` | BROWSE-016 | Toggle favorite pin | Unverified |
| `user_library.py:123` | `POST /api/favorite-tags/{tag_name}` | META-006 | Toggle favorite tag | Unverified |
| `user_library.py:147` | `POST /api/favorite-tags/{tag_name}/pin` | META-006 | Toggle favorite-tag pin | Unverified |
| `user_library.py:175` | `GET /api/favorite-tags` | META-006 | List favorite tag details | Unverified |
| `user_library.py:218` | `GET /api/favorite-tags/names` | META-006 | List favorite tag names | Unverified |
| `user_library.py:234` | `GET /api/favorite-tag-combos` | META-007 | List combos | Unverified |
| `user_library.py:243` | `POST /api/favorite-tag-combos` | META-007 | Create combo | Unverified |
| `user_library.py:268` | `DELETE /api/favorite-tag-combos/{combo_id}` | META-007 | Delete combo | Unverified |
| `user_library.py:276` | `POST /api/blacklist-tags/{tag_name}` | BROWSE-008 | Add blacklist tag | Unverified |
| `user_library.py:290` | `DELETE /api/blacklist-tags/{tag_name}` | BROWSE-008 | Remove blacklist tag | Unverified |
| `user_library.py:299` | `GET /api/blacklist-tags` | BROWSE-008 | List blacklist details | Unverified |
| `user_library.py:331` | `GET /api/blacklist-tags/names` | BROWSE-008 | List blacklist names | Unverified |

### Images and media — `backend/routers/images_media.py`

| Route anchor | Method and path | Feature IDs | Persistence/effect | Status |
|---|---|---|---|---|
| `images_media.py:10` | `GET /api/images` | VIEW-002–005, BROWSE-001–010 | Reads/searches both DBs | Unverified |
| `images_media.py:124` | `GET /api/timelapse/frames` | VIEW-008 | SQL-sampled data DB read | Unverified |
| `images_media.py:236` | `GET /api/images/random` | BROWSE-009 | Context-filtered DB read | Unverified |
| `images_media.py:312` | `PUT /api/images/batch/folder` | BROWSE-014 | Filesystem and metadata move | Unverified/destructive |
| `images_media.py:325` | `DELETE /api/images/batch` | BROWSE-015 | Filesystem and DB delete | Unverified/destructive |
| `images_media.py:345` | `GET /api/images/{post_id}` | VIEW-011, BROWSE-018–021 | Detail read; optionally records view | Unverified |
| `images_media.py:420` | `POST /api/images/{post_id}/heart-spam` | BROWSE-017 | Increments user view counter | Unverified |
| `images_media.py:428` | `POST /api/images/{post_id}/relations/refresh` | BROWSE-020 | May call Danbooru and update relation metadata | Unverified |
| `images_media.py:445` | `POST /api/images/{post_id}/user-tags` | BROWSE-019 | Adds user tag | Unverified |
| `images_media.py:464` | `DELETE /api/images/{post_id}/user-tags/{tag_name:path}` | BROWSE-019 | Removes user tag | Unverified |
| `images_media.py:486` | `POST /api/images/{post_id}/open-location` | BROWSE-023 | Opens managed filesystem location | Unverified |
| `images_media.py:511` | `PUT /api/images/{post_id}/folder` | BROWSE-024 | Moves media/sidecars and rewrites DB identity | Unverified/destructive |
| `images_media.py:627` | `DELETE /api/images/{post_id}` | BROWSE-025 | Deletes media/derived/user references | Unverified/destructive |
| `images_media.py:705` | `GET /api/image-file/{file_id}` | BROWSE-026 | Streams original local media | Unverified |
| `images_media.py:749` | `GET /api/thumbnail/{file_id}` | BROWSE-027 | Creates/streams derived thumbnail | Unverified |

### Tools, Settings, Backup, and Cache — `backend/routers/tools.py`

| Route anchor | Method and path | Feature IDs | Persistence/effect | Status |
|---|---|---|---|---|
| `tools.py:83` | `GET /api/tools` | DATA-029–033 | Reads tool definitions/task state | Unverified |
| `tools.py:88` | `GET /api/automation` | DATA-016 | Reads watcher config/status | Unverified |
| `tools.py:93` | `PUT /api/automation` | DATA-016 | Writes watcher config | Unverified |
| `tools.py:98` | `GET /api/storage` | DATA-001 | Returns public path/config snapshot | Unverified |
| `tools.py:121` | `GET /api/import-pipeline` | DATA-015 | Reads ingest phase counts/state | Unverified |
| `tools.py:127` | `GET /api/import-pipeline/task` | DATA-015, DATA-024 | Reads incremental task results | Unverified |
| `tools.py:142` | `POST /api/import-pipeline/run` | DATA-015 | Starts discover/enrich/metadata/finalize/all | Unverified |
| `tools.py:172` | `POST /api/import-pipeline/cancel` | DATA-015 | Cancels import task | Unverified |
| `tools.py:177` | `GET /api/danbooru/credentials` | DATA-021 | Returns status only | Unverified |
| `tools.py:182` | `PUT /api/danbooru/credentials` | DATA-021 | Saves DPAPI-protected credential | Unverified |
| `tools.py:190` | `DELETE /api/danbooru/credentials` | DATA-021 | Clears saved credential | Unverified |
| `tools.py:195` | `POST /api/danbooru/credentials/check` | DATA-021 | Validates effective credentials against Danbooru | Unverified |
| `tools.py:252` | `GET /api/tools/folders` | DATA-026, DATA-030 | Lists configured tool targets | Unverified |
| `tools.py:271` | `POST /api/tools/backfill/run` | DATA-030 | Starts targeted/all-folder backfill | Unverified |
| `tools.py:288` | `GET /api/backups` | DATA-018 | Gets backup config/list | Unverified |
| `tools.py:293` | `GET /api/local-recovery` | DATA-017 | Gets checkpoint status | Unverified |
| `tools.py:298` | `POST /api/local-recovery/checkpoint` | DATA-017 | Creates manual checkpoint | Unverified |
| `tools.py:306` | `PUT /api/backups` | DATA-018 | Saves destination/components | Unverified |
| `tools.py:314` | `POST /api/backups/estimate` | DATA-018 | Read-only component scan/estimate | Unverified |
| `tools.py:319` | `POST /api/backups/create` | DATA-018 | Creates verified bundle | Unverified |
| `tools.py:330` | `GET /api/backups/{backup_name}/inspect` | DATA-019 | CRC/manifest inspection | Unverified |
| `tools.py:339` | `POST /api/backups/restore` | DATA-019 | Quiesced rollback-safe restore | Unverified/destructive |
| `tools.py:359` | `GET /api/thumbnails/cache` | DATA-020 | Reads derived-cache status | Unverified |
| `tools.py:364` | `POST /api/thumbnails/cache/cleanup` | DATA-020 | Removes stale/legacy derived thumbnails | Unverified |
| `tools.py:369` | `POST /api/thumbnails/cache/clear` | DATA-020 | Clears derived thumbnails | Unverified |
| `tools.py:375` | `PUT /api/thumbnails/cache/limit` | DATA-020 | Saves limit and prunes | Unverified |
| `tools.py:381` | `POST /api/tools/{tool_id}/run` | DATA-024, DATA-029–033 | Starts selected maintenance workflow | Unverified |
| `tools.py:429` | `POST /api/tools/{tool_id}/cancel` | DATA-024 | Cancels selected workflow | Unverified |
| `tools.py:436` | `GET /api/tools/{tool_id}/status` | DATA-024 | Reads selected workflow status | Unverified |

### Languages — `backend/routers/language.py`

| Route group | Method and path | Feature IDs | Persistence/effect | Status |
|---|---|---|---|---|
| Cached status and catalog reads | `GET /api/language/status`, `/words`, `/words/{word_id}`, `/decks`, `/today` | DATA-049 | Local catalog/user reads only; `/words` supports server-side `content=all|sentences|grammar`; status and Today never contact Anki | API/unit verified; renewed browser pass pending |
| Authored and override workflow | `POST /words`; `PATCH/DELETE /words/{word_id}`; `DELETE /words/{word_id}/override` | DATA-049 | Precious manual rows or field overrides; manual delete is retirement; mirrored delete refused | API/SQLite/browser verified |
| Local media | `POST /words/{word_id}/media`; `GET /media/{word_id}/{role}` | DATA-049 | Versioned create-only bytes plus precious association; contained hash/size recheck and ranged serving | Filesystem/API/browser verified |
| Organization | `GET/PUT/DELETE /favorites*`; `GET/POST/PATCH/DELETE /lists*`; `PUT /lists/{list_id}/items`; `POST /bulk` | DATA-049 | Precious favorites and retireable list membership; batch favorite/unfavorite/add-to-list | API/frontend verified |
| Local practice | `POST /practice/session`, `/practice/answer`; `GET /practice/stats` | DATA-049 | Precious self-graded results only; totals, accuracy, daily activity, current streak, and per-word results; no Anki schedule mutation | API/frontend verified; renewed browser pass pending |
| Export and settings | `GET /export`; `GET/PUT /settings`; `GET /profiles`; `GET/PUT /profiles/{note_type}` | DATA-049, SETTINGS-014 | Full JSON export; precious settings/profiles; optional DPAPI key; local reads by default | API/browser verified |
| Explicit Anki mirror | `GET /anki/probe`; `POST /anki/preview`, `/anki/import`; `GET/DELETE /anki/jobs/{job_id}` | DATA-049 | Loopback strict-read allowlist; preview token and selection hash; field-compatible KO1Kv2 variant detection; cancellable background import with versioned media/receipts | Stub/API verified; live KO1Kv2+ probe/preview verified read-only 2026-07-28 |

### Manayomi — `backend/routers/manga.py`

| Route group | Method and path | Feature IDs | Persistence/effect | Status |
|---|---|---|---|---|
| Module status and settings | `GET /api/manga/status`, `/settings`; `PUT /settings` | MANGA-001, MANGA-006 | Reads local status; writes additive module settings only; all routes are enabled-state gated | Focused unit/source contract verified |
| Downloaded-ID list transfer | `MangaSettings.svelte`, `MangaView.svelte`, `MangaBrowse.svelte`, `mangaApi.ts`; `manga/database.py` (`downloaded_id_lists`, `downloaded_id_list_items`); `manga/queries.py` (`export_downloaded_ids`, `import_downloaded_ids`, `list_downloaded_id_lists`, `remove_downloaded_id_list`, `imported_downloaded_gallery_ids`); `GET /api/manga/downloaded-ids/export`; `GET/POST /downloaded-ids`; `DELETE /downloaded-ids/{list_id}` | MANGA-006, MANGA-007 | Export local nHentai IDs only as six-digit lines; atomically validate/import named lists with counts; additive user-state tables survive index rebuilds. Individual removal preserves overlapping lists and all media/user organization. Browse adds `downloaded_elsewhere` alongside unchanged local `downloaded`; Hide downloaded combines both. Settings mutations update their list immediately and increment the Browse refresh token. Reader/local lookup and MangaDex stay source-specific | Isolated HTTP/SQLite integration in `test_manga_module.py` covers roundtrip, BOM/CRLF, older IDs, duplicate/invalid input, overlap/removal, cache reconciliation, restart/index-rebuild preservation, and disabled-module gating; browser verification recorded after execution |
| Roots and scanning | `GET/POST /roots`; `DELETE /roots/{root_id}`; `POST /scan`, `/scan/stop`; `GET /scan/progress` | MANGA-002 | Registers/unindexes roots and rebuildable manga rows; original files are never deleted by root operations | Isolated scan verified |
| Verified root relocation | `POST /roots/{root_id}/relocate-preview`, `/relocate` | MANGA-003 | Preview verifies every resolved destination, including Windows-to-Linux moves via `storage_layout.py:relative_path_for_relocation`; confirmed apply atomically rebases index/root paths only | Isolated moved-root test and real 4,109-file relocation verified |
| Library and reading | `MangaView.svelte`, `MangaFilterSheet.svelte`, `MangaLibrary.svelte`, `MangaHistory.svelte`, `MangaDetailOverlay.svelte`; `GET /library`, `/detail/{id}`, `/cover/{gallery_id}`, `/pages/{gallery_id}`, `/page/{gallery_id}/{page_index}`, `/history*` | MANGA-004, MANGA-005, MANGA-006 | Local index/user reads; derived covers/pages; hidden-mode Library blacklist applied before paging; `library_additions` preserves first local-added time; additive `reading_history` preserves paged/vertical resume state; narrow navigation is a snap strip and Library controls use a fixed compact grid; detail projects a contained Files handoff identity, presents play/site/Files/favourite/pin as one equal-size icon row, and uses a phone summary grid plus expandable tag wall; detail header places close before title; `MangaView.libraryFilters` binds the current six Library fields through section/settings remounts, while `MangaLibrary` consumes each pending tag seed once and opens the matching anchored filter | Isolated search/blacklist/reader/date-rebuild, filter-handoff, history migration/resume and responsive source-contract tests; opt-in `MangaBrowserRegressionTests` exercises edited/cleared filters through remounts and both detail headers at desktop/phone widths; real-library 360×800, 390×844, 768×1024, and 1024×768 detail/navigation browser checks verified 2026-08-09 |
| User organization | category, favorite, pin, first-added, and reading-history routes beneath `/api/manga/*`; icon-only detail controls | MANGA-004 | Precious module favorites, pins, categories, membership, `library_additions`, and `reading_history`, all keyed by source/gallery identity | Favorite, added-date, and reading-progress preservation across isolated index rebuild verified |
| Explicit remote browse/download and local HeH tag directory | `MangaBrowseProviders.svelte`, `MangaBrowse.svelte`, `MangaFilterSheet.svelte`, `MangaDexBrowse.svelte`, `MangaDexFilterSheet.svelte`, `MangaDexDetailOverlay.svelte`, `MangaView.svelte`, `MangaTags.svelte`, `MangaDownloadsMenu.svelte`, `MangaDownloads.svelte`, `MangaDetailOverlay.svelte`; `manga/mangadex.py`; `/remote/mangadex/*` including `/filters`, `/browse`, `/heh/tags`, `/download*`, `/jobs*`, `/nh-image` | MANGA-007 | Provider access occurs only from explicit Browse, remote detail/reader, filter-catalog, or download actions. nHentai retains its gallery contract in a provider-specific sheet. MangaDex preserves title/chapter UUID hierarchy; validates original/translated language, rating, demographic, status, sort/direction, tag mode, and live Content/Format/Genre/Theme tags; preserves duplicate translation/group chapters, external publisher entries, scanlation credits, backend-proxied at-home pages/reporting, counted chapter selection, and per-chapter atomic CBZ/manifest/`mangadex.json` downloads. Phone navigation is bottom-docked; Hide downloaded is shared/persisted; MangaDex detail is chapter-first on phones and side-by-side on desktop with separate chapter states. Additive `remote_identities` gives UUID chapters stable negative local keys across index rebuilds. HeH Tags remains local/offline and exact to downloaded relations; ignored tags use each provider's native exclusions where available; shown matches retain first-click reveal and second-click detail; the unified download dropdown/list reads local preserved dates | `test_mangadex.py` covers API normalization, full structured-filter mapping/validation/live grouped tag catalog, current numeric feed flags, at-home delivery, UUID paths, additive identity, sidecar scan, Library/history joins; `test_manga_module.py` pins compact phone navigation/provider filters. Live real-data verification passed 2026-08-24 at 360×800, 390×844, and 1024×768: first cover y=156, first chapter y=256, live Status + Sort filter, chapter/Info tab switch, both desktop columns, no horizontal overflow, clean console/runtime log. Reader page delivery and chapter download remained intentionally outside non-mutating verification |

Downloaded-ID verification on 2026-10-08 passed all 455 tests, compileall,
frontend type checks, and the production build. Real Edge interaction at
1280×900 and 390×844 verified export/import, invalid-file feedback, counts,
Hide downloaded/show, reload persistence, individual removal, and clean
console/HTTP logs against disposable local fixtures. No live-library mutations
or manga provider transfers were run.

### Artists — `backend/routers/artists.py`

| Route anchor | Method and path | Feature IDs | Persistence/effect | Status |
|---|---|---|---|---|
| `artists.py:9` | `POST /api/artist-profile-assets/refresh-followed` | META-013, META-014 | User-triggered bulk archive refresh | Unverified |
| `artists.py:30` | `GET /api/artist-profile-assets/{tag_name}` | META-013, META-014 | Lists archived versions | Unverified |
| `artists.py:39` | `POST /api/artist-profile-assets/{tag_name}/refresh` | META-013, META-014 | Downloads/validates/archive profile media | Unverified |
| `artists.py:47` | `GET /api/artist-profile-asset-files/{asset_id}` | VIEW-012 | Streams archived local asset | Unverified |
| `artists.py:64` | `GET /api/artist-follows` | META-009–012 | Lists follows/post state | Unverified |
| `artists.py:78` | `GET /api/artist-follows/names` | META-009 | Lists followed names | Unverified |
| `artists.py:92` | `POST /api/artist-follows/{tag_name}` | META-009 | Creates follow | Unverified |
| `artists.py:113` | `DELETE /api/artist-follows/{tag_name}` | META-009 | Removes follow/post state | Unverified |
| `artists.py:124` | `POST /api/artist-follows/{tag_name}/check` | META-010–012 | Polls Danbooru post IDs and initializes baseline | Unverified |
| `artists.py:176` | `POST /api/artist-follows/{tag_name}/seen` | META-010–012 | Marks discovered posts seen | Unverified |
| `artists.py:202` | `GET /api/tags/random` | BROWSE-009 | Random tag query | Unverified |
| `artists.py:232` | `GET /api/tags/suggest` | BROWSE-002 | Tag suggestions | Unverified |
| `artists.py:266` | `GET /api/tags/related` | META-008 | Related tag groups | Unverified |

### Discovery — `backend/routers/discovery.py`

| Route anchor | Method and path | Feature IDs | Persistence/effect | Status |
|---|---|---|---|---|
| `discovery.py:9` | `GET /api/popularity/periods` | VIEW-007 | Aggregated data DB read | Unverified |
| `discovery.py:71` | `GET /api/home/tags` | VIEW-001 | Home tag candidates/covers | Unverified |
| `discovery.py:137` | `GET /api/home/image-rails` | VIEW-001 | Home moving-lane items | Unverified |
| `discovery.py:208` | `GET /api/challenges/daily` | VIEW-009 | Deterministic daily challenge | Unverified |
| `discovery.py:242` | `GET /api/challenges/characters/suggest` | VIEW-009 | Character suggestions | Unverified |

## Regression Source Matrix

The current full suite passed 378 tests on 2026-07-28. The symlink-escape
coverage falls back to an unprivileged directory junction on Windows when a
file symlink is unavailable. `test_tool_progress.py`'s bounded-tail test is
timing-sensitive and can be rerun in isolation if a heavily loaded full pass
ever exposes that unrelated flake.

| Test file | Main protected contracts |
|---|---|
| `tests/test_acquisition.py` | Canonical/external sidecars, offline roots, credentials, artist profile extraction, gallery-dl discovery, EXIF tolerance, open location, targeted backfill, five tool definitions |
| `tests/test_automation.py` | Changed-media candidate selection, unavailable roots, incremental sync path |
| `tests/test_backup_bundle.py` | Estimate cache, visible creation feedback, verified restore without images, Profile-name backup roundtrip, DB access quiescence |
| `tests/test_import_phases.py` | Resumable discover/enrich/finalize phases, metadata progress, no-match retention |
| `tests/test_filename_search.py` | Pasted filename search, positive/negative filename filter, multiple ratings |
| `tests/test_files_api.py` | Files source API, additive visibility, canonical legacy role, module publication projection |
| `tests/test_files_annotations.py` | Origin-note store: hash-keyed files (follows rename/move), path-keyed folders, shared-copy dedup, link replace, attachment refcount, explicit-only delete |
| `tests/test_files_attachments.py` | Attachment upload/store-in-first-folder, on-disk dedup, serve, refcount-safe delete, empty-note prune, `.keivotos` scan exclusion, non-media rejection |
| `tests/test_files_base.py` | Type-agnostic index, unavailable state, search, bounded lazy hashing/duplicates, picker filesystem |
| `tests/test_files_info.py` | Info API roundtrip, lazy hash-on-annotate written to index, http-only link validation, empty-note auto-remove, guarded open/reveal |
| `tests/test_files_serving.py` | Containment chain, traversal/absolute/symlink/suite-tree refusal, exact module-declared browse-root exception, inline allowlist vs forced-download, non-ASCII disposition, range 206. The escape test falls back from a privileged file symlink to an unprivileged directory junction, so the containment branch is covered on an ordinary Windows host instead of skipping |
| `tests/test_folder_roles.py` | Staged batch semantics, display/visibility edits, descriptor adopt/release dispatch, counted safe forget |
| `tests/test_folder_picker.py` | Modern Windows picker and frozen helper routing, no Tk fallback |
| `tests/test_folder_removal.py` | Counted preview, unindex preservation, current-sidecar-only deletion |
| `tests/test_folder_roots.py` | Same display names, relocation identity/reference rewrite, legacy schema tolerance |
| `tests/test_frontend_delivery.py` | Root document no-cache behavior |
| `tests/test_home_discovery.py` | Landscape-first candidates and five-item spotlight source contract |
| `tests/test_settings_motion_contract.py` | Settings summary names, motion-aware smooth search jump, short repeatable highlight |
| `tests/test_image_move.py` | Single-image folder move carries media **and every sidecar**; pins `SIDECAR_SUFFIXES` resolving in the router (regression: it was undefined) |
| `tests/test_images_golden.py` | `/api/images` golden response, removed tags, favorite join identity, SQL timelapse sampling |
| `tests/test_local_recovery.py` | Verified/deduplicated/rotated checkpoints |
| `tests/test_module_registry.py` | One required non-disableable base, seven descriptor identities including Manayomi, unique slugs, and module publication boundaries |
| `tests/test_manga_module.py` | Manayomi surface/mobile/drawer/anchored-filter/detail/tag-handoff/language/Browse-reveal/Downloads/HeH-Tags/History contracts, nHentai tag parser, search parser, isolated CBZ scan, favorite and durable added-date/reading-progress preservation, server-side blacklist paging, verified root relocation, and isolated downloaded-ID HTTP roundtrip/validation/overlap-removal/persistence/disabled-gating coverage; opt-in `MangaBrowserRegressionTests` runs real timed desktop/phone checks for filter edits/clears across remounts, repeated handoffs, both information-header positions, and close-button/Escape/backdrop behavior using browser-only manga fixtures |
| `tests/test_mangadex.py` | MangaDex title/chapter normalization, complete structured-filter mapping and validation, live grouped tag-catalog projection, official query/expansion/exclusion and current numeric chapter-feed parameters, chapter-first UI contract, at-home quality/report path, UUID-safe layout and additive identity, local sidecar rescan, Library search, and private history joins without live media transfer |
| `tests/test_manga_browse_paging.py` | Remote Browse logical-page aggregation, exact totals, visible blacklist matches, and hidden-mode negative provider queries |
| `tests/test_manga_reader_pages.py` | Natural CBZ page ordering, archive identity cache, and bounded phone-sized WebP reader cache |
| `tests/test_language_module.py` | Languages descriptor paths/hooks, stable word identity, catalog schema, additive precious schema, disable preservation, contained versioned create-only storage |
| `tests/test_language_library.py` | Manual create/edit/retire, effective override/revert, authored-media precedence, lists/favorites, weakest-card filtering, Korean/English/Mongolian ordering, practice, and full JSON export |
| `tests/test_language_anki.py` | KO1Kv2/script/media normalization, compatible note-type variants, strict read-action allowlist, stubbed preview/import/progress/cancel, and confirmed duplicate-merge preservation |
| `tests/test_language_analyzer.py` | Real Kiwi Korean golden output/cache, compound lemmas and grammar, romanization, local meaning/example matches, precious saved-history tombstones, KRDICT explicit cache boundary, and independent secret preservation |
| `tests/test_language_api.py` | Disabled gating, cached status without client creation, manual API lifecycle, lists, Analyzer/history/dictionary boundary, and export |
| `tests/test_language_frontend_contract.py` | Registry/icon/surface wiring, local-only media, word wall/detail/composer/practice interactions, three-dot/Browser/Atlas/Analyzer workflows, explicit network boundaries, and searchable Settings category |
| `tests/test_openapi_snapshot.py` | Complete API schema snapshot |
| `tests/test_regression_fixes.py` | Relation chain, collection validation/404, helper exit, port probe, malformed config, log separation, safe numeric defaults |
| `tests/test_source_startup.py` | Portable GUID layout/import, existing Data preservation, ambiguous-case refusal and explicit override; Bash cwd/argument forwarding and setup-failure propagation |
| `tests/test_release_layout.py` | Local AppData defaults, preserved Documents and prior-module migrations, ignored outputs, neutral scan config, generated/root guards, isolated config, identity/portable check, spec/runtime smoke/frontend/brand |
| `tests/test_schema.py` | Additive schema migration with dictionary rows |
| `tests/test_security.py` | Loopback/LAN same-origin allow and cross-origin/inactive-host rejection |
| `tests/test_sidebar_grip_contract.py` | Static sidebar grip strings/DOM shape and Browse/Tags mounting; **not animation behavior** |
| `tests/test_storage_layout.py` | Root identity/legacy copy preservation and sidecar-directory containment |
| `tests/test_reddit_frontend_contract.py` | Reddit surface registration, local-media-only rendering, outbound link cards, confirmed download controls, sixth Settings category/defaults, archive health, infinite-feed trigger, thread/community/search contracts |
| `tests/test_reddit_library.py` | Read-only keyset feed, filters, FTS search, actual archived-comment counts, outbound links, detail/community/status projections, cursors, local media |
| `tests/test_reddit_link_capture.py` | Direct post/community Arctic Shift bundles, exact-response provenance, URL rejection, `more` placeholders, no post enumeration for subreddit targets |
| `tests/test_reddit_runtime_api.py` | Disabled gating, truthful indexed capture receipts, feed/thread direct-call regression, archive/storage/limit/runtime status, scoped media plans, Files publication, local media containment, ranges, missing/outside-path refusal |
| `tests/test_karaoke_module.py` | Karaoke descriptor/storage containment, additive precious user schema, Files-reference identity/hash check, JSON/Python-representation lyric-token normalization, and ranged local serving |
| `tests/test_karaoke_acquisition.py` | Kara.moe normalization, exact plan/authorization, hardsub staging, generated lyrics/receipt, Files publication, and no overwrite |
| `tests/test_youtube_module.py` | Strict YouTube metadata/search, actual resolution-first format selection, manual/automatic captions, exact plan authorization, completed local catalog and Files publication |
| `tests/test_yt_dlp_service.py` | Shared no-shell process resolution, bounded invariant arguments, cancellation, timeout/error behavior, and redaction |
| `tests/test_karaoke_youtube_frontend_contract.py` | Karaoke/YouTube surfaces, local-only playback, Mouse-1/player/lyrics controls, YouTube defaults, query handoff, and Files-identity Add to Karaoke |
| `tests/test_suite_modules.py` | Files plus Danbooru/Reddit/Karaoke/YouTube/Language/Manayomi descriptor API, optional persistence, and one-time existing-install enablement |
| `tests/test_tag_history.py` | Removed-tag history by durable identity |
| `tests/test_thumbnails.py` | Move-stable content key, three tiers, cleanup, video frame, endpoint MD5, bounded locks |
| `tests/test_tool_progress.py` | Task-state isolation, incremental results, structured status, bounded recent history |
| `tests/test_user_db_promotion.py` | Verified suite-root user DB promotion with legacy source preservation |
| `tests/test_view_navigation.py` | Shared Home breadcrumb for special views |

Committed response contracts:

- `tests/snapshots/openapi.json`
- `tests/snapshots/api_images.json`

Major missing regression coverage:

- real browser/timed sidebar animation, reversal, drag, grip auto-hide, saved
  position, and overflow scrolling;
- Keivotos drawer open/close timing across every exit path;
- Home timed spotlight and independent lane pause/resume;
- Profile focus animation, ImageDetail transitions/zoom, Timelapse timers, and
  Daily Challenge reveal/persistence;
- full frontend typecheck/build and current server smoke;
- destructive move/delete/restore behavior against disposable fixture media;
- current Danbooru network behavior and artist notification baselining.

## Archived Lineage

Historical source is evidence for recovery, not an instruction to copy entire
old folder structures.

| Historical point | Feature/code significance |
|---|---|
| V0.0.1 and early V0.0.2 | Large original Sidebar and early application shell |
| V0.0.2 Beta4/Beta5 | First `SidebarDock` and `AppDrawer` iterations |
| V0.0.2 Beta6 | Sidebar file byte-identical to the later V1.0.0 Beta3.1 slide implementation |
| V1.0.0 Beta1-Beta3.1 | Conditional sidebar mount with Svelte `transition:slide`; Settings/storage/import features accumulate |
| V1.0.0 Beta4 | Current persistent one-instance CSS sidebar begins; Home redesign begins |
| V1.0.0 Beta5/Beta6 | Same sidebar dock retained; later consistency and service/performance work |
| Release Candidate 1/2 | Packaging/distribution work; same sidebar dock |
| Release Candidate 3/4/5 | Bug-fix lineage; same sidebar dock |
| Release soon 1 | 97 sampled current source/test files match byte-for-byte |
| Current checkout | the cycle named in ROADMAP.md; Files/module descriptor work is additive and sidebar restoration remains present |

Relevant historical changelog feature groupings:

- `CHANGELOG.md:476` V1.6: ImageDetail, Popularity, Timelapse, relations, mass
  selection, advanced search, duplicate review.
- `CHANGELOG.md:456` V1.7: Home, wiki/tag information, artist journey, Daily
  Challenge, favorite tags.
- `CHANGELOG.md:434` V1.8: immediate refresh, Profile, Search Help, Settings,
  collection media covers, Heart Spam.
- `CHANGELOG.md:407` V1.9: artist follows, post IDs, profile-media archive,
  notifications, immediate update.
- `CHANGELOG.md:373` V1.10: future/historical planning only.
- `CHANGELOG.md:259-278` current reconstruction Beta1 foundation.
- `CHANGELOG.md:238` Beta2 Settings.
- `CHANGELOG.md:195` Beta3 roots, sidecars, backup, import, thumbnails.
- `CHANGELOG.md:164` Beta4 Home/sidebar/search.
- `CHANGELOG.md:140` Beta5 ratings/tags/fixes.
- `CHANGELOG.md:111` Beta6 service/performance work.
- Earlier package/security history remains historical; the user-defined current
  identity is the cycle named in [ROADMAP.md](./ROADMAP.md#current-cycle).

## Partial and Broken Boundaries That Must Block Refactoring

1. ~~Do not remove or simplify `core.py` exports until every importing router and
   test is mapped to explicit replacements.~~ **Satisfied and closed 2026-07-25.**
   A mechanical AST inventory mapped all 233 wildcard-supplied names to their
   real owners; every router and test was converted, and `core.py` was deleted.
   The rule that replaces it: **no module may reintroduce a wildcard import or a
   catch-all module.** New behavior goes in the owning module or service.
2. Do not refactor `SidebarDock.svelte` from static source assumptions. First
   reproduce the user-reported failure, compare Beta3.1 and Beta4/current
   behavior in a browser, select the intended motion, and add timed
   characterization.
3. Do not merge the Keivotos app drawer and Danbooru library sidebar. They
   are separate controls, separate state, separate mounting rules, and separate
   animation contracts.
4. Do not centralize paths by deleting route- or pipeline-level guards until
   every move, delete, picker, helper, backup, sidecar, and registered-root
   consumer has been redirected and regression-tested.
5. Do not infer that a test currently passes because it exists. Record the
   dated command/result before changing a status to Working.
6. Manayomi is now part of the suite runtime. Preserve its historical
   `modules/manga` storage boundary, precious module `user.sqlite`, explicit
   network actions, and verify-before-apply root relocation contract.

## How to Maintain This Register During Refactoring

For every proposed application-code change:

1. Find the affected feature IDs in this file.
2. List every owning file, API route, table, background job, animation, and test
   referenced by those IDs before requesting permission.
3. Compare the relevant archived implementation when lineage is listed.
4. Add characterization for unprotected behavior before moving or reducing
   code.
5. Preserve immediate initiating-view updates and then trigger the appropriate
   cross-view refresh token.
6. Update temporary line anchors after the code change.
7. Append dated verification evidence and change **Unverified** to **Working**
   only for the exact exercised contract.
8. If a contract is intentionally changed or removed, update this file and
   `FEATURES.md` in the same authorized change.
