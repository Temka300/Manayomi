# Agent Instructions

This manga-focused repository contains Keivotos, Manayomi, and the current
experimental module registry. The runtime identity is **V1.1.2**; V1.1.3 work
is present locally but is not version-bumped. Names already used
for folders, builds, commits, tags, or GitHub releases are historical facts and
must not be renamed retroactively. V1.10 and post-V1.0 ideas are future plans,
not current work.

This file is self-contained. No cross-repository startup reading is required.

## How to Work Here

1. **Read what the task touches, not everything.** Before changing a feature,
   read its entry in `docs\important\FEATURES.md` and its row in
   `docs\important\FEATURE_CODE_MAP.md`. Pull in the other reference docs
   below only when their domain is involved.
2. **Questions get answers, not edits.** When the user is asking, discussing,
   or thinking out loud, inspect read-only and answer. Use technical terms
   with a short plain explanation next to them. No filler.
3. **Changes get a plan and one yes.** When the user requests a change,
   present a short plan: what will change, which files, and how it will be
   verified. One clear "yes" from the user approves the whole plan — edits,
   rebuilds, app restarts, and verification included. No magic phrases.
4. **Scope growth needs a new yes.** If implementation reveals the plan must
   expand (new files, new behavior, anything destructive), stop, say what
   changed, and get approval for the addition.
5. **Work in small bisectable slices.** One logical change at a time, verified
   before the next, so any regression can be found by bisecting instead of
   forensics.
6. **Finish in prose.** State what changed, what was verified, whether the app
   server was restarted, and which real-data or network operations were
   intentionally not run.

## Absolute Rules (never relaxed by a plan approval)

- **Never delete or rewrite user data**: media, metadata, sidecars,
  `user.sqlite`, gallery-dl files, backups, or archived version folders.
  `user.sqlite` is never dropped or rebuilt; schema changes are additive
  migrations. Sidecar refreshes archive what they replace. Destructive bulk
  actions warn with counts first and need their own explicit approval.
- **Git and releases belong to the user.** No staging, committing, pushing,
  branching, tagging, packaging, or publishing unless the user explicitly asks
  for that specific action. 
- **Archived versions are read-only evidence.** Never edit anything under
  `D:\Kivotos\Github_Wakaru\Keinomous-Updates\` or the
  `D:\Kivotos\Github_Wakaru\V1.0.0 - *` folders.
- **Local-first, single-user.** No accounts, login, cloud sync, telemetry, or
  remote-user assumptions unless explicitly requested. No surprise downloads
  or remote-image hotlinking.
- **Existing behavior is a contract.** Preserve every existing feature,
  animation, transition, interaction, persistence rule, path guard, and
  data-safety behavior unless the approved plan explicitly lists its change.
  Do not remove behavior to reduce line count. If a feature intentionally
  changes: update `FEATURES.md`, `FEATURE_CODE_MAP.md`, `CHANGELOG.md`, and
  regression coverage in the same logical change — never silently delete a
  documentation entry.
- **Long network-heavy Danbooru operations** run only when the user explicitly
  asks.

## Reference Docs (`docs\important\`)

| Doc | When to read it |
| --- | --- |
| `PLAYBOOK.md` | session process, environment, commands |
| `FEATURES.md` | behavior contract + regression checklists — before any feature change |
| `FEATURE_CODE_MAP.md` | feature-to-code index — before editing mapped files |
| `CURRENT_STATE_AUDIT.md` | the 2026-07-16 baseline: what works, what's broken, what's unverified |
| `MODULAR_ARCHITECTURE_PLAN.md` | agreed extraction order — before architectural work |
| `ARCHITECTURE.md` / `DESIGN-PHILOSOPHY.md` | locked decisions and rationale |
| `PIPELINE.md` / `gallery-dl.md` | acquisition and import work |
| `DISTRIBUTION.md` | running and packaging |
| `ROADMAP.md` / `FUTURE.md` | what's next vs. future-only ideas |
| `RECONSTRUCTION_LEDGER.md` | recovery history and evidence provenance |

Line references in the code map are temporary navigation aids; the owning file
and symbol are the stable identity. Update stale references when editing.

## Current Priorities

The compatibility-facade extraction and Files-based module registry are
complete. The order now:

1. Preserve and characterize Manayomi's manga behavior while it settles into
   the descriptor registry.
2. Keep root/path changes verification-first and non-destructive.
3. Centralize remaining path policy behind the authoritative boundary.

Do not combine restoration, extraction, cleanup, and unrelated feature work in
one change.

## Verification

Static source inspection proves code exists, not that a feature works. Match
verification to the behavior:

- unit/characterization tests for pure logic and API contracts;
- OpenAPI and golden-response snapshots for endpoint/schema compatibility;
- isolated filesystem/SQLite tests for paths, migrations, sidecars, backups;
- **real timed browser interaction** for animations, transitions, delayed
  reveals, rapid reversals, dragging, scrolling, focus, and state restoration
  — a static render or source-string test does not verify motion;
- console and runtime logs free of relevant errors.

Commands when the affected area requires them:

- WSL2/Linux: `.venv/bin/python -m compileall -q backend scripts app.py`,
  `.venv/bin/python -m unittest discover -s tests -v`, and `npm run check` /
  `npm run build` in `frontend/`. Set `KEIVOTOS_HOME` to a separate scratch
  directory when running tests so imports cannot select live data.
- Windows: `.venv\Scripts\python.exe -m compileall -q backend scripts app.py`,
  `.venv\Scripts\python.exe -m unittest discover -s tests -v`, and
  `npm.cmd run check` / `npm.cmd run build` in `frontend\`.
- browser checks at `http://localhost:53325/`

To test UI needing data, prefer the real library read-only. If seeding is
needed, use a separate metadata dir via a scratch `config.json` — never the
live one — and clean up afterwards.

## Architecture Rules

`backend\core.py` has been removed. Routers use explicit owning modules and
services; do not reintroduce wildcard imports or a catch-all compatibility
facade. Keep public API behavior and response models stable, and change one
cohesive characterized domain at a time.

Path policy has one authoritative boundary: `backend\config.py` (configured
locations) and `backend\storage_layout.py` (root identity, canonical
sidecars). New code consumes that boundary; do not invent new path rules,
hard-code personal paths, or duplicate resolution functions. Containment
checks use resolved absolute paths. Sidecars live under
`sidecars\roots\<stable-root-id>\<relative-path>`; legacy migration is
copy-and-verify and never deletes preserved source sidecars.

## Product and UI Contracts

- Keivotos is the suite; Manayomi is the manga module in this checkout. The
  Keivotos drawer and every module-owned library/sidebar control remain separate.
- User-triggered mutations update the initiating component immediately, then
  reconcile other views via refresh tokens.
- Top bar stays compact: Size, Filter, and Random icon-only beside Search;
  followed-artist notifications before the far-right user/avatar control.
- Profile remains a local-library view.
- The library sidebar's animations, vertical scrolling, draggable grip,
  delayed reveal, hover return, saved position, and rapid-toggle behavior are
  protected features (currently user-reported broken — restoration target).
- Avoid duplicated controls unless the user explicitly requests the workflow.

## Project Layout

- Application entry point: `app.py`
- Backend composition: `backend\server.py`; routers: `backend\routers\`;
  services: `backend\services\`; module descriptors: `backend\modules\`
- Configuration/paths: `backend\config.py`; root identity/sidecars:
  `backend\storage_layout.py`; database: `backend\database.py` +
  `backend\schema.py`; API models: `backend\models.py`
- Frontend: `frontend\` — shared state `frontend\src\lib\stores.ts`, API
  client `frontend\src\lib\api.ts`
- Helper scripts: `scripts\` (release helpers in `scripts\release\`)
- Tests: `tests\` (snapshots in `tests\snapshots\`)
- Launchers: `bash run.sh` on WSL2/Linux; `run.bat` on Windows (uv-synced
  Python 3.11; flags `--dev`, `--port N`, and `--no-browser` pass through);
  app URL `http://localhost:53325/`
- Venv Python for script runs: `.venv/bin/python` on WSL2/Linux;
  `.venv\Scripts\python.exe` on Windows.
- An empty `portable.txt` reuses an existing adjacent `Data/` when `data/` is
  absent. Never rename data to address filename case, or rewrite saved Windows
  library paths without verifying their intended Linux destinations.

Work with the current tree as-is. Existing uncommitted changes belong to the
user; do not revert, overwrite, or reformat unrelated work.

## Documentation, Changelog, and Release Notes

Documentation must keep four states distinct: current implemented behavior,
broken/unverified behavior, historical release lineage, and future ideas.
Update docs in the same logical change as the behavior they describe; the
important docs must agree with the actual code.

`CHANGELOG.md` records durable user-visible decisions and release history —
no conversation transcripts or implementation diaries. Release notes are plain
imperative bullets under `Release Vx.x.x` — no emoji, no intro paragraph, no
`### Added` headers.
