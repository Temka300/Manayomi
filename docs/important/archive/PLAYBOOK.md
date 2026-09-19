# Keivotos — Working Playbook

The repeatable process for a development session on this repo.

Startup reading: the repository `AGENTS.md`, then this playbook. Read the
other docs by domain when the task touches them — always
[FEATURES.md](FEATURES.md) and [FEATURE_CODE_MAP.md](./FEATURE_CODE_MAP.md)
before changing a mapped feature, and
[CURRENT_STATE_AUDIT.md](./CURRENT_STATE_AUDIT.md) before refactoring.

Companion docs: [ARCHITECTURE.md](./ARCHITECTURE.md) (locked decisions) ·
[PIPELINE.md](./PIPELINE.md) (data flow) · [ROADMAP.md](./ROADMAP.md) (what's
next) · [DESIGN-PHILOSOPHY.md](./DESIGN-PHILOSOPHY.md) (the why) ·
[DISTRIBUTION.md](./DISTRIBUTION.md) (running/packaging) ·
[gallery-dl.md](./gallery-dl.md) (acquisition).

---

## What this project is

**Keivotos** — the personal hoarding suite. Main module: **Danbooru**, the
reconstructed original Python (FastAPI) + Svelte 5 booru. The user-defined
current identity is **V1.1.0**; runtime/package constants are aligned at
`1.1.0`. V1.10 and post-V1.0 ideas are future-only. The source was
resurrected from raw Codex session logs after the original source was lost
([RECONSTRUCTION_LEDGER.md](RECONSTRUCTION_LEDGER.md)). The
mechanical reconstruction phase is over, but recovery and regression work is
not: the sidebar animation remains user-reported broken and broad refactoring
remains gated. The V1.1.0 automated/browser evidence is recorded in
`FEATURES.md` and `FEATURE_CODE_MAP.md`.

## The per-change loop

1. Questions and discussion are read-only; answer, don't edit.
2. For a requested change, present a short plan: what will change, which
   files, and how it will be verified. One clear user "yes" approves the whole
   plan — edits, rebuilds, app restarts, and verification included.
3. If the scope must grow beyond the approved plan, stop, say what changed,
   and get a new yes for the addition.
4. Read `FEATURES.md` and `FEATURE_CODE_MAP.md` for every affected surface.
   Compare archived versions when behavior lineage matters.
5. Implement in small bisectable logical changes, preserving every related
   behavior, motion, persistence rule, path guard, compatibility export, and
   data-safety contract.
6. Verify the affected static, timed, interactive, API, persistence, and
   regression contracts. A source-string test or static render does not prove
   animation or delayed interaction.
7. Update documentation in the same logical change when behavior,
   architecture, or process changes.

## Environment & commands (Windows)

- **Launcher:** `run.bat` — uv synchronizes the locked Python 3.11 environment,
  builds `frontend/dist` only when missing, and starts `app.py`. Flags pass
  through: `--dev` (reload), `--port N`, and loopback `--host`. Maintainer LAN
  testing uses ignored `run-lan.local.bat`, which sets the local developer
  marker and binds one private adapter. Ordinary source and portable builds do
  not expose `--lan`.
- **App URL:** `http://localhost:52325/` (uvicorn serving `backend/server.py`,
  which serves `frontend/dist`).
- **Venv python:** `.venv\Scripts\python.exe` — use it for all script runs;
  gallery-dl is installed inside it.
- **Frontend:** `npm.cmd run check` / `npm.cmd run build` / `npm.cmd run dev`
  in `frontend/`. In dev mode run the backend with `--dev` and Vite separately.
- **Pipeline CLI:** `.venv\Scripts\python.exe scripts\danbooru_gallery_dl.py
  <download|backfill|index|sqlite|sync|clean-sidecars|search>` — see
  [gallery-dl.md](./gallery-dl.md).

## Verification workflow

1. `python -m compileall -q .\backend .\scripts .\app.py`
2. `.venv\Scripts\python.exe -m unittest discover -s tests -v`
3. `npm.cmd run check` in `frontend/` → 0 errors.
4. `npm.cmd run build` in `frontend/` → passes.
5. Restart the app server when runtime behavior changed; exercise the changed
   flow in the browser at `http://localhost:52325/`.
6. After nontrivial changes, run the FEATURES.md **smoke pass** (Home, Browse
   with a mixed search, ImageDetail, Favorites, a Collection, a tag page,
   Popularity, Timelapse, Daily Challenge, Profile, Settings — no console
   errors).
7. For motion changes, exercise real elapsed behavior: open/close direction,
   rapid reversal, delayed reveal, drag, hover return, scrolling, and persisted
   restoration as applicable.
8. Do **not** run long network-heavy Danbooru refreshes unless the user
   explicitly asks.

The current documentation audit did not run this baseline. Tests and snapshots
existing in the tree are not the same as a confirmed passing current baseline.
Follow-up verification on 2026-07-18 passed compileall, the then-current 100
unit tests, frontend check/build, uv lock consistency, and an isolated
source-server Profile name save/reload. On 2026-07-19, the Danbooru identity
transition passed compileall, all 102 unit tests, frontend check, and the
production build. The Windows portable package remains unbuilt and unverified.

## Data-safety rules (important)

- The user's real library stays in registered external roots; generated
  metadata lives under configured `metadata_dir` (Local AppData by default).
  **Never delete media, metadata,
  sidecars, databases, or gallery-dl files without an explicit user request.**
- **`user.sqlite` is never dropped or rebuilt.** Schema changes are additive
  migrations; existing data gets migrated or backfilled.
- Sidecar refreshes **archive** replaced sidecars, never destroy them.
- Removing a folder/root defaults to un-index only. The explicit counted
  delete-sidecars choice may remove current central sidecars below the
  configured metadata directory, but must never touch original media, adjacent
  preservation sidecars, or archived history. Before recursive moves/deletes,
  verify resolved absolute source and destination paths are inside the intended
  directories.
- Destructive bulk actions warn with counts first.
- To test UI needing data, prefer the real library read-only; if you must
  seed, use a separate metadata dir via a scratch `config.json` — never the
  live one. Clean up test artifacts afterwards.
- The preserved `data/` migration source and `_gallery-dl/` stay out of git.

## Git & release rules (learned the hard way — they carry over)

- **The USER owns commits, pushes, force-pushes, tags, packages, and
  releases.** Do not run Git/release writes or append command handoffs unless
  the user explicitly asks for that specific action or those commands.
- No trailing `# comments` on handed-over command lines — Windows `cmd` does
  not treat `#` as a comment.
- **Identity check before the first push:** this repo still has the
  reconstruction replay identity configured. Confirm with the user
  which name/email (GitHub noreply) new commits should use — the commit
  *email* decides attribution.
- **Release-notes style (user preference):** plain imperative bullets,
  `Release Vx.x.x` — no emoji, no intro paragraph, no `### Added` headers.
  README prose ≠ release notes.
- Do not label the current work V1.10 or a completed V1.0.0 release. Use
  **V1.0.0 Pre-release 5** until the user changes the release identity.

## Communication

- Short progress updates while working; surface load-bearing findings.
- Explain assumptions around filesystem metadata, DB rebuilds, sidecar
  refreshes, and network-heavy operations before acting on them.
- Final response states: what changed, what was verified, whether the app
  server was restarted.
