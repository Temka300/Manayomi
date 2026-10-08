# Manayomi Updates

## Current experimental update

- Keep edited and cleared Library tag filters when switching sections or returning from Settings; apply each manga-detail tag click only once.
- Place the manga-information close button at the left of the title in both local/nHentai and MangaDex panels.

- Export local nHentai manga IDs as a six-digit text list, import named lists in Manayomi Settings, and include those lists in Browse's Hide downloaded filter with individual removal controls.

- Add a separate hotspot launcher for WSL forwarding with an explicit private host allowance and unchanged same-origin protections.

- Add a local Bash LAN launcher matching the Windows maintainer wrapper, with optional explicit `--lan` and argument forwarding.

- Support verified relocation of saved Windows manga-library paths to Linux while preserving manga identities and user state.
- Add a Bash source launcher for WSL2/Linux, fix portable configuration initialization on Linux, and reuse an existing Windows-copied Data directory without renaming or migrating it.

- Upgrade this manga-focused checkout to the Keivotos V1.1.2 runtime and current experimental module registry.
- Register Manayomi as an optional suite module while preserving its historical `modules/manga` databases and `/api/manga` contract.
- Add verified, index-only manga-root relocation so an externally moved library can be rebased without moving or deleting media.
- Put Library search, Filter, sort, and language controls together at the top; show JP, EN, and CN badges at the lower right of manga covers.
- Apply blacklist tags before paging and show matching blacklist reasons clearly when blacklisted cards are visible.
- Open the Keivotos drawer from Manayomi's header and distinguish the Library sidebar control with a split-panel icon.
- Put Filter at the left of both Library and Browse toolbars and share one compact, short-input popover anchored directly below it at desktop and phone widths.
- Enlarge manga detail, use stateful Read/heart/pin/category actions, open galleries on nHentai or in Files, and keep download progress visible until detail closes.
- Preserve the first local-added manga date in the module user database so filesystem timestamp changes and disposable index rebuilds cannot replace it.
- Keep blacked-out cards in Browse only; reveal a matching cover on first click with animation and open cover-visible detail on the second click.
- Return detail-tag searches to the Library or Browse surface that opened them, open its filter popover, and show the value in the matching structured field.
- Move Downloads to the right-side header, show active and latest downloads in an anchored dropdown, and open the preserved-date local download list through Show all.
- Add the provider-backed HeH Tags directory with Popular/A–Z downward-flowing columns and route selections into downloaded Library results only.
- Make HeH Tags counts exact downloaded-Library totals, omit zero-match tags, and sort Popular by local prevalence rather than provider-wide totals.
- Show every generic tag found in downloaded nHentai metadata instead of stopping at HeH's 120-tag public directory shortlist.
- Consolidate manga-detail Read, site, Files, favourite, and pin actions into one adjacent row of equal-size accessible icons.
- Make Manayomi genuinely usable at phone and iPad widths with snap navigation, compact Library/Browse controls, searchable multi-column downloaded tags, and a compact phone detail summary with expandable tags.
- Preserve private reader page progress in additive Manayomi user state, add Continue reading/complete History, and close manga information by clicking its dim backdrop.
- Add an nHentai/MangaDex provider selector beneath Browse while preserving the existing nHentai workflow and routes.
- Browse MangaDex titles with provider-native search, paging, sort, language, blacklist, cover, creator, status, tag, and saved-chapter information.
- Open MangaDex titles into complete metadata and volume-grouped chapter feeds that preserve translation and scanlation-group variants and identify publisher-hosted chapters.
- Read MangaDex-hosted chapters through the contained paged/vertical reader with compliant temporary MangaDex@Home delivery, refresh, proxying, attribution, and transfer reporting.
- Select and queue explicit MangaDex chapter downloads as original-quality atomic CBZ files with portable manifests and `mangadex.json` sidecars.
- Preserve MangaDex UUIDs through an additive stable local-identity map so rescans and index rebuilds retain Library, history, favorites, pins, categories, series, and Files behavior without colliding with nHentai IDs.
- Add MangaDex original/translated language, rating, demographic, status, sort, tag-mode, Content, Format, Genre, and Theme filters using MangaDex's current public tag catalog.
- Move remote Browse filters into the provider row, share a persisted Hide downloaded header action, and dock Manayomi section navigation at the bottom on phones so covers start higher.
- Open MangaDex detail on Chapters at phone widths, show information and chapters side by side on desktop, and distinguish chapter loading, empty, and retryable failure states.

---

# Shared Keivotos Changelog

## Release V1.1.2

* Cover symlink escape via junction fallback (11e8571)
* Add a guarded thumbnail endpoint for the base (a6289cf)
* Render real thumbnails in the browse grid (5cb8a98)
* Cover folder tiles from their subtree (dd9148e)
* Prefer an origin attachment as the tile image (e53f4f3)
* Add a per-module grid size control (1fa5fb5)
* Share one grid size menu between surfaces (76c4a09)
* Keep the info panel readable on wide displays (6bd2f9a)
* Lead the info panel with origin, not file facts (504e1fa)
* Copy origin info from another file (b9d6c98)
* List archive contents without extracting (8515f8e)
* Show archive contents in the info panel (2e67d04)
* Share the range-serving helper (6c6b2d4)
* Drop the unused md5_of_file wrapper (10fa28f)
* Dock the info panel to the edge again (6d0e661)

## Release V1.1.1

* Add the file and folder annotation store (1cad12b)
* Serve source files with containment and range guards (e2929e0)
* Add the origin-info annotation API (aec11c6)
* Add the file info panel with type-aware preview (f35ac2a)
* Add the origin editor and note badges (031b53d)
* Add image and video attachments to origin notes (c78f301)
* Back up file attachment bytes in the bundle (cadb2de)
* Restore sidecar moves with a named suffix list (5c4cd90)
* Replace the wildcard core import with explicit ones (82422f4)
* Extract collection, profile and tag-name services (beffd58)
* Extract shared primitives and the Danbooru client (b6e6131)
* Move the tag wiki and user tags into the module (a9ce6b5)
* Move artist profiles and follows into the module (ea99c65)
* Move the tool runner into the module (1d3a807)
* Move the search grammar into the module (8ddde97)
* Extract the lifespan and FastAPI app factory (c927ea6)
* Extract the lifespan, app factory and relations (fa2360e)
* Split path, media and duplicate helpers out (b6421bf)
* Extract image activity and convert every router (251ce1a)
* Delete the backend compatibility facade (badf7f2)
* Split the API types out of the client (2b2a5ec)

## Release V1.1.0

- Make Files the required, non-disableable base and keep Danbooru as an optional module.
- Drive the suite shell from static backend and frontend module registries instead of Danbooru-specific branches.
- Split Keivotos-owned product identity, `user.sqlite`, backups, logs, and browser storage from module-owned paths, credentials, API identity, and user agents.
- Copy, verify, and preserve legacy module user databases and module-scoped backups before using their suite-owned locations.
- Copy recognized legacy browser preferences into the `keivotos:` namespace without deleting their original keys.
- Add the `files_sources.visible` column and read the legacy `base` role as `files` without a global rewrite.
- Add the staged Manage folders dialog for display-name edits, one role per folder, sidebar visibility, adding folders, and counted forget operations.
- Keep adopt, release, and forget non-destructive to original files and sidecars; remove only registration and disposable index state.
- Put the role icon, ancestral Files breadcrumb, Danbooru-positioned Search, Rescan, and Duplicates in one compact top bar and remove the redundant open-folder identity/path strip.
- Use the native Windows picker from the sidebar plus, constrain Manage folders to descendant folders inside registered top-level roots, and align its controls by row.
- Keep nested Files sources under one stable owner by stopping parent scans at child-root boundaries and reclaiming disposable rows when a child is forgotten.
- Preserve Danbooru's existing API paths while declaring descriptor prefixes for the Files base and future route-prefix work.
