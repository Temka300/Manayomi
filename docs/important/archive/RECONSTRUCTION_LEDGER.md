# Reconstruction ledger

This is a historical evidence ledger, not a description of the current release
architecture. Historical paths, counts, and filenames are preserved as they
were recorded. The current user-defined release identity is **V1.1.0**; V1.10
and post-V1.0 ideas are future-only.

This repository is a **mechanical, evidence-verified reconstruction** of the
Waifu-Hoard project (originally at `E:\Archive\Github_Temka\Waifu-Hoard`,
lost) from the raw Codex session archive at
`D:\Wakaru\A_DriveC\Temka\.codex\Waifu Hoard\conversations\raw`
(25 rollouts, 2026-05-23 through 2026-06-20).

No line in this repo was invented or paraphrased. Every line comes from one of:

1. **Applied patches** — `patch_apply_end` records: full content for added
   files, the exact unified diff applied to disk for updates (790 successful
   patch applications; 789 replayed here — one touched only an out-of-scope
   copy under `E:\Storage\Anime_Waifu`).
2. **File reads** — `Get-Content` full/windowed/`-Raw`/`-Tail` outputs from
   the sessions (869 applied), used to seed pre-existing files and verify.
3. **Grep evidence** — `rg -n` / `Select-String` outputs carrying
   `line-number:content` pairs (416 events).

## Verification result

Replaying chronologically, every overlapping evidence point was cross-checked:

- **141,752** line checks from file reads — **0 mismatches**
- **17,608** line checks from grep output — **0 mismatches**

Known artifacts were detected and neutralized rather than ingested: the
PowerShell `profile.ps1` stderr banner (438 occurrences), PS console
word-wrapping of `Select-String` output, Codex `…N tokens truncated…` long-line
markers, and PowerShell's appended newline on `-Raw` reads.

## Git history

819 commits. `patch:` commits are the real edit events with their original
timestamps and thread ids. `evidence:` commits mark where a session read
revealed content the patches alone could not (knowledge snapshots, not edits).
`restructure:` commits replay the 2026-05-24 move
(`app/frontend`→`frontend`, `app/backend`→`backend`, `app/scripts`→`scripts`,
`app/config.json`→`config.json`, `app/run.py`→`app.py`) reconstructed from the
session's shell commands.

## Fully recovered (51 files)

Includes the complete backend — `backend/server.py` (5,378 lines),
`database.py`, `models.py`, `config.py`, `thumbnails.py`, `app.py` — all of
which pass `python -m py_compile` — plus every Svelte component,
`frontend/src/lib/api.ts`, `stores.ts`, `App.svelte`, `main.ts`,
`app.css`, `vite.config.ts`, `package.json`, `AGENTS.md`, `CHANGELOG.md`,
`config.json`, `.gitignore`, and the Waifu-Hoard-Hoarder side project
(under `Waifu-Hoard-Hoarder/`, original at
`E:\Archive\Github_Temka\Waifu-Hoard-Hoarder`) except its `app.js`.

## Fill pass (2026-07-12, after the evidence replay)

Lower-confidence recoveries, each clearly separated from the verified history:

- **index.html** — completed: 5 lines were evidence-known, the rest is the
  invariant Vite skeleton (doctype/head/body/script). High confidence.
- **svelte.config.js, tsconfig.json, tsconfig.node.json, tsconfig.app.json,
  vite-env.d.ts, frontend/.gitignore, frontend/README.md** — stock
  `create-vite` svelte-ts template files, consistent with the recovered
  `package.json` (vite 8 / svelte 5 / @tsconfig/svelte 5). Evidence confirmed
  tsconfig.app.json line 2 and a README heading verbatim. Exact whitespace or
  minor version drift possible.
- **package-lock.json** — regenerated with `npm install` (not the original).
- **TagsBrowser.svelte** — complete. The apparent 9-line tail gap was a replay
  accounting artifact, not missing source: the archived command used
  `Select-Object -Skip 1120` and returned empty output, while later archived
  tail reads end at the component's closing `</div>`. The temporary
  reconstruction comment was removed; there was no lost `<style>` block.
- **scripts/danbooru_gallery_dl.py** (filled 2026-07-12, post-reconstruction)
  — the 86 unrecovered lines (the script's own CLI-search helpers:
  `parse_search_terms` tail, `add_numeric_filter`, `add_dimension_filter`,
  `add_tag_condition`, `run_search`) were **reimplemented, not recovered**.
  The fill is constrained by the evidence lines that survived around them and
  mirrors the recovered server-side equivalents in `backend/server.py`, but
  exact original wording is unknown. This only affects the standalone
  `search` subcommand; the app's own search never used this code path. The
  file now compiles, which the download/backfill/sqlite/clean-sidecars
  commands (fully recovered) require.

**Build status after fills:** backend passes `py_compile`;
frontend `vite build` succeeds.

## Current-tree reconciliation (2026-07-16)

The statements above describe the reconstruction and fill events at the time
they occurred. The current tree has continued to change:

- `backend/server.py` is now a 40-line composition root and
  `backend/core.py` is a 3,157-line compatibility facade. Nine domain routers
  exist, but every router still wildcard-imports `core`, so modular separation
  is incomplete.
- A 97-file current source/test/configuration sample is byte-identical to
  `D:\Kivotos\Github_Wakaru\V1.0.0 - (Release soon 1) - from zero`.
- Files once missing or scaffolded during reconstruction now exist in the
  current tree, including `LICENSE`, the Svelte/TypeScript configuration files,
  `frontend/src/vite-env.d.ts`, `frontend/public/icons.svg`, and the stock
  Svelte/Vite SVG assets. `frontend/src/assets/hero.png` remains absent and is
  not referenced by current source.
- `Waifu-Hoard-Hoarder/frontend/static/app.js` exists, but
  `Waifu-Hoard-Hoarder/backend/downloader.py` is absent even though its server
  imports it. The side project is therefore incomplete.
- The build statement above is historical. The current compile, unit-test,
  frontend-check, frontend-build, source-startup, and portable-startup baseline
  was not rerun during the documentation audit.

Notably, none of `hero.png`, `public/icons.svg`, `src/assets/svelte.svg`,
`src/assets/vite.svg` are referenced anywhere in the recovered sources —
they were unused leftovers, so their loss does not affect the app.

## Original-content gaps

In the mechanical replay, `#<<UNRECOVERED-LINE>>` marked a line that existed
but was never shown in any session output, and `#<<UNRECOVERED-TAIL: ...>>`
marked an unobserved file tail. The fill pass above replaces some of those
markers with working code or stock scaffold content. The counts below measure
unknown **original wording/content**, not necessarily broken current files.

| File | Lines | Unknown | Where |
|---|---|---|---|
| scripts/danbooru_gallery_dl.py | 1553 | 86 | scattered through lines ~1198–1553 (`add_dimension_filter` region); the mechanical replay did not compile, and the documented fill above restores it |
| Waifu-Hoard-Hoarder/frontend/static/app.js | 1402 | 1204 | only patched regions known |
| frontend/package-lock.json | 1584 | 1475 | generated file; regenerate with `npm install` |
| frontend/index.html | 9+ | 4 + tail | |
| frontend/public/icons.svg | 22+ | 18 + tail | |
| frontend/README.md | 24 | 23 + tail | stock Vite template README |
| frontend/tsconfig.app.json | 2+ | 1 + tail | stock Vite template config |
| frontend/src/assets/svelte.svg / vite.svg | 1 | tail only | stock Vite/Svelte template assets |

## Missing at mechanical-reconstruction time

- `LICENSE`
- `frontend/svelte.config.js`, `frontend/tsconfig.json`,
  `frontend/tsconfig.node.json` — likely stock `create-vite` svelte-ts
  template files
- `frontend/src/assets/hero.png` — binary, unrecoverable from text logs
- possibly `frontend/src/vite-env.d.ts` and other files hidden by truncated
  session file listings

This list is historical. See the current-tree reconciliation above for which
items now exist.

Also not part of this reconstruction: the data folders now stored under `data/`
and `_gallery-dl` (moved into the original repo on 2026-05-24; they are
data, not code) and `frontend/node_modules` / `frontend/dist` build outputs.

## Patches not applied

Five `apply_patch` calls were **rejected by the approval layer** ("usage
limit") and never touched disk; the sessions retried them successfully, so
their content is present via the retries. One patch targeted the stray copy
at `E:\Storage\Anime_Waifu\app\...` and is out of scope. Full details in
`.reconstruction/ledger.json`.

## Relation to the `github/` folder in the archive

The archive's `github/` folder is an earlier AI *behavioral* reconstruction
(code re-written to match observed behavior). This repository was built
independently of it, from raw evidence only. Where this repo has markers, the
`github/` version may contain a plausible but unverified guess.
