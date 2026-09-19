# Commit Checklist

Command dump for the routine below.

```
.venv\Scripts\python.exe -m compileall -q .\backend .\scripts .\app.py
.venv\Scripts\python.exe -m pytest
cd frontend
npm run check
npm run build
cd ..
.venv\Scripts\python.exe scripts\openapi_snapshot.py
uv lock
uv lock --check
cd frontend
npm install
cd ..
.venv\Scripts\python.exe app.py --portable-check
git status --ignored --short
git status --short
git diff
git add <the files for this slice>
git status
git diff --cached --stat
git commit
git push
```

Release only:

```
.venv\Scripts\python.exe scripts\release\set_version.py <version>
.venv\Scripts\python.exe -m pytest
.\scripts\release\build_windows.ps1
git tag v<version>
git push --tags
```

The full pre-commit routine. Steps marked **(Required)** run for every commit;
conditional steps run only when their trigger matches. Skip nothing that
matches. The Quick Reference table at the bottom maps changes to steps.

## Never commit

- Personal media, `user.sqlite` or any database, sidecars, gallery-dl files
- Credentials of any kind
- `artifacts/` build output
- `run-lan.local.bat`
- The preserved `data/` migration source and `_gallery-dl/`
- Version-number edits outside a release — only `scripts\release\set_version.py`
  changes version identity, and only when the user declares a release

---

## 1. Compile check (Required)

```
.venv\Scripts\python.exe -m compileall -q .\backend .\scripts .\app.py
```

**Purpose:** Catches syntax errors in files no test imports.

## 2. Run tests (Required)

```
.venv\Scripts\python.exe -m pytest
```

**Purpose:** Catches regressions, API contract changes, release layout issues,
schema problems, and security-guard failures.
**Must:** End with all tests passing (100+ tests).
**Setup:** pytest is a `dev` dependency. If it is missing, run
`uv sync --group dev` to install the test environment into `.venv`.

## 3. Frontend changed? (`frontend/src/**` or anything under `frontend/` except `dist/`)

```
cd frontend
npm run check
npm run build
cd ..
```

**Purpose:** Zero check errors, then rebuild the production frontend.
**Commit the rebuilt `frontend/dist` together with the source changes.**

- New hashed files → add
- Old hashed files → delete

## 4. Runtime behavior changed? (backend or frontend — anything the app does at runtime)

Restart the app (`run.bat`) and exercise the changed flow in the browser at
`http://localhost:54325/`. If both backend and frontend changed, do this
**after** step 3 so you are testing the rebuilt `frontend/dist`.

- After nontrivial changes, run the FEATURES.md smoke pass: Home, Browse with
  a mixed search, ImageDetail, Favorites, a Collection, a tag page,
  Popularity, Timelapse, Daily Challenge, Profile, Settings — no console
  errors.
- For motion changes, exercise real elapsed behavior: open/close direction,
  rapid reversal, delayed reveal, drag, hover return, scrolling, saved
  position, restoration.

**Purpose:** Tests passing proves logic, not that the app works. Static
renders do not prove animation or delayed interaction.

## 5. API routes/models/responses changed?

```
.venv\Scripts\python.exe scripts\openapi_snapshot.py
```

**Purpose:** Updates the OpenAPI snapshot used by contract tests.
Commit:

```
tests/snapshots/openapi.json
```

If golden-response snapshots under `tests/snapshots/` changed, review that
diff deliberately — a changed golden response is a changed API contract.

## 6. New feature, changed behavior, or removed behavior?

Update **in the same commit** as the code:

- `docs/important/FEATURES.md` — the behavior contract entry
- `docs/important/FEATURE_CODE_MAP.md` — the feature-to-code row
- `CHANGELOG.md` — durable user-visible decisions only, no diaries
- A regression test in `tests/` covering the new/changed behavior
- `docs/user/*` if the change is user-facing (these ship inside the release)
- `README.md` / `docs/build/*` if setup or running changed

**Purpose:** Existing behavior is a contract; docs move with the behavior
they describe. Never silently delete a documentation entry.

## 7. Database schema changed? (`backend/schema.py`, `backend/database.py`)

- Additive migrations only. `user.sqlite` is never dropped or rebuilt;
  existing data is migrated or backfilled.
- Test the migration against an isolated environment: set `KEIVOTOS_HOME` to
  an empty temp directory — never the live metadata dir.

**Purpose:** User data survives every schema change.

## 8. Path or storage logic changed? (`backend/config.py`, `backend/storage_layout.py`)

- All path rules live behind this one boundary — no new resolution functions
  elsewhere, no hard-coded personal paths.
- Containment checks use resolved absolute paths; confirm
  `test_storage_layout` and `test_security` still pass (step 2 covers them).

**Purpose:** One authoritative path boundary; escapes here risk user data.

## 9. Dependencies changed?

If `pyproject.toml` changed:

```
uv lock
uv lock --check
```

If `frontend/package.json` changed:

```
cd frontend
npm install
cd ..
```

**Purpose:** `uv lock` regenerates `uv.lock` only; `npm install` is what
regenerates `package-lock.json`. Commit the updated lockfiles:

- `uv.lock`
- `frontend/package-lock.json`

If a new **runtime** dependency was added, also update
`THIRD_PARTY_NOTICES.md` — it is hand-maintained, no script writes it.

## 10. Packaging or launcher changed? (`packaging/`, `run.bat`, `scripts/release/*`, `app.py`, `backend/config.py`)

`test_release_layout` in the suite (step 2) covers the layout contract. For
release-critical changes, do a full `build_windows.ps1` run before trusting
it — the layout test proves structure, not a working build.

Run the portable resource check to verify packaged resources resolve and to
print every writable data path:

```
.venv\Scripts\python.exe app.py --portable-check
```

**Purpose:** Confirms frontend, backend, and folder picker are present and
prints the resolved home, runtime config, library, metadata, and gallery-dl
paths. Exit 0 = all resources present. In a frozen build it also checks that
`gallery-dl.exe` and `ffmpeg.exe` sit beside `Keivotos.exe`. Run it after any
change to path or launcher logic to confirm the paths still point where you
expect.

## 11. Check ignored files (Recommended)

PowerShell:

```
git status --ignored --short
```

Git Bash:

```
git status --ignored --short | grep -iE "artifacts|credentials|\.sqlite|run-lan"
```

**Purpose:** Ensure secrets and large files stay ignored.

## 12. Review changes (Required)

```
git status --short
git diff
```

**Purpose:** Verify exactly what changed before staging.
Check for:

- Unexpected files
- Accidental deletions
- Accidental edits
- Doc entries removed without an approved behavior change

## 13. Stage this slice (Required)

Stage the files belonging to **one** logical change:

```
git add <the files for this slice>
```

`git add -A` is not the default. Staging everything is what turns a week of
work into one unreviewable commit, and it silently contradicts step 15. Use
`-A` only when it is scoped to a path whose adds and deletes must move
together:

```
git add -A frontend/dist
```

**Purpose:** One commit, one idea. If a change does not belong to the slice
you are describing in step 15, it belongs to a different commit.

### What may not ride along

- **Generated fixtures that tests assert against** — `tests/snapshots/openapi.json`
  — commit **with** the API change that caused them. Held back, the tree is
  red at that commit.
- **Generated build artifacts** — `frontend/dist` — commit **alone**, in their
  own `chore:` commit. Nothing asserts on their contents, and mixing them in
  buries the authored diff.
- **Unrelated fixes** noticed in passing. Write them down and commit them
  separately.

## 14. Verify staged changes (Required)

```
git status
git diff --cached --stat
```

**Purpose:** Final review before committing.
Confirm:

- Expected files only
- No ignored or never-commit files
- `frontend/dist` additions **and** deletions are present (if frontend changed)
- Docs + tests + snapshots ride in the same commit as the behavior they cover

## 15. Commit (Required)

```
git commit
```

**Purpose:** Save the staged snapshot. One logical change per commit — keep
changes bisectable; don't mix restoration, refactoring, and features.

### Message convention

```
type(scope): imperative summary, lower case, no trailing period
```

`type` is one of `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`.
`scope` is the area: `files`, `suite`, `folders`, `config`, `core`, `product`,
`api`, `drawer`, `release`. Omit the scope only when a change is genuinely
repository-wide.

```
feat(files): add MD5 hashing and duplicate detection
fix(config): survive a missing Danbooru module
chore: regenerate the OpenAPI snapshot and frontend bundle
```

**One line. No body.** The subject is the whole message, so keep it under 72
characters and make it stand on its own. Explanation, rationale and any
deliberate behavior change belong in the release notes shown on the Releases
page, not in `git log`.

If a change needs a paragraph to justify it, that is a sign it is really two
commits.

## 16. Push (Required)

```
git push
```

**Purpose:** Upload the commit to the remote repository.

---

## Release only (not normal commits)

1. Write release notes in `CHANGELOG.md` under `Release Vx.x.x` — plain
   imperative bullets, no emoji, no intro paragraph, no `### Added` headers.
2. Set the version everywhere:

   ```
   .venv\Scripts\python.exe scripts\release\set_version.py <version>
   ```

3. Run the tests again:

   ```
   .venv\Scripts\python.exe -m pytest
   ```

4. Build:

   ```
   .\scripts\release\build_windows.ps1
   ```

   The build script itself runs `npm ci`/`check`/`build`, brand-asset
   generation, and license collection — no separate steps needed.
5. Confirm `artifacts/` stayed ignored (step 11 again).
6. Commit and push the release commit, then tag:

   ```
   git tag v<version>
   git push --tags
   ```

---

## Quick Reference

| If you changed...                     | Do this                                                             |
| ------------------------------------- | ------------------------------------------------------------------- |
| Anything                              | `compileall` → `pytest` → review → stage → commit                   |
| `frontend/src/**`                     | `npm run check` → `npm run build` → commit `frontend/dist` adds+deletes |
| Backend + frontend together           | Tests → frontend build → restart app → exercise the flow            |
| Runtime behavior                      | Restart `run.bat` → exercise flow at `localhost:54325` → smoke pass |
| API routes/models/responses           | Regenerate `tests/snapshots/openapi.json`                           |
| Any feature (new/changed/removed)     | `FEATURES.md` + `FEATURE_CODE_MAP.md` + `CHANGELOG.md` + regression test, same commit |
| `backend/schema.py` / `database.py`   | Additive migration only; test with isolated `KEIVOTOS_HOME`         |
| `backend/config.py` / `storage_layout.py` | Keep the single path boundary; containment tests must pass      |
| `pyproject.toml`                      | `uv lock` + `uv lock --check` → commit `uv.lock`                    |
| `frontend/package.json`               | `npm install` → commit `frontend/package-lock.json`                 |
| New runtime dependency                | Update `THIRD_PARTY_NOTICES.md` by hand                             |
| `packaging/` / `run.bat` / `app.py` / release scripts | Layout test in suite; `app.py --portable-check`; full build for release-critical changes |
| `backend/config.py` path/launcher logic | `app.py --portable-check` — confirm resolved data paths          |
| Release version                       | CHANGELOG notes → `set_version.py` → tests → `build_windows.ps1` → tag |
