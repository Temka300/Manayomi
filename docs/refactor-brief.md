# Keivotos — Recovery and Refactor Brief

> **Note (2026-07-16):** this brief is preserved as the original recovery
> mandate. Its conversation protocol (the exact-phrase gates) was superseded
> by the lean plan-then-one-yes model now defined in `AGENTS.md`. Steps 1–5
> are complete; steps 6–8 remain.

## Context: where the project stands

Let's stop this nonsense. The project is almost at its lowest point — things are
conflicting and regressing. What was the project at its peak is becoming its
biggest downfall.

core.py is way too big. When code is written or changed in there, small things
get removed and that causes an avalanche into other functions — for example the
sidebar animations are broken even though the code is still there. (This still
has not been fixed.)

I have shipped the project in its current state, even with some things not
functioning and bugs still present. The reason I hadn't uploaded the code before
is my fault: I wanted to test how Keivotos-test would behave on GitHub on the
first try (CI, workflow, GitHub Actions), which I shouldn't have cared about
from the beginning. This release is NOT V1.0.0. It was named "V1.0.0 release
soon 1" and I am now calling it "V1.0.0 Pre-release 1". Do not rename anything
retroactively — I am fine with how the start was named. There is still a lot to
do before the V1.0.0 full release.

The overall goal: slowly change the folder structure and the code inside it so
the whole codebase is modular — changing one function shouldn't affect the
others (much). Path/folder-location handling must live in a single place in the
code. core.py's code must be spread out so core.py calls other files to
function.

## How we work from now on (conversation protocol)

- When I say something, you first check AGENTS.md, then the whole project, then
  think about what you must, then answer me.
- Speak in technical terms, with a short plain explanation next to each term.
  No extra filler words. Tell me what you must — nothing more. Then I can talk
  about it.
- Everything I say is a QUESTION, not an implementation request. Do not
  implement anything from discussion.
- After I have asked all my questions, you give me a NUMBERED LIST of every
  change you will make, with a reference under each item to where in the
  conversation we discussed it, so I can search the conversation easily.
- Only when I say the exact phrase "now implement it" do you start writing
  changes.
- At the end of implementation: no bullet points. Tell me in prose what you
  changed, and write the changelog and release notes.

## Version control discipline

- The pre-refactor state is committed on `main` (the tree was clean at
  `66a9351` before this brief was added). Nothing starts from an uncommitted
  or dirty tree.
- Every restoration or refactor step lands as its own small commit — one
  logical change per commit — so any new regression can be found by bisecting
  commits instead of forensically reconstructing what happened.
- Git and release actions belong to the user. Committing happens only when the
  user asks for it, but work should be sliced so that each askable commit is
  small.

## Step 1 — Fix AGENTS.md (and check all the .md files first)

AGENTS.md should have prevented things like the sidebar animations being
removed, and it didn't. Update it to reflect everything in this brief. It must
define:

- What must be read before touching code
- How discussion and implementation are separated (the "now implement it" gate)
- How existing features are protected
- How regressions are checked
- How architectural changes are proposed
- How feature-to-code relationships are recorded
- How changelogs and release notes are maintained
- How archived versions are used for comparison
- How paths, storage locations, and sidecars are handled

## Step 2 — Audit the current project

Before rewriting the documentation, inspect:

- The complete current folder structure
- core.py, server.py, startup code, storage code, database code, API code,
  frontend code, and pipeline code
- Current working features
- Broken or partially regressed features
- Existing animations and interface behavior
- Duplicate implementations
- Hard-coded paths and path-resolution functions
- Features that still have code but no longer work
- Code that appears unused but supports another feature indirectly
- Differences between Release Candidate versions

## Step 3 — Update the important docs first

ARCHITECTURE.md, DESIGN-PHILOSOPHY.md, DISTRIBUTION.md, FEATURES.md, FUTURE.md,
gallery-dl.md, PIPELINE.md, PLAYBOOK.md, RECONSTRUCTION_LEDGER.md, ROADMAP.md
(all in docs/important). All of them were created when the project first
started at V0.0.1 — which literally rose from ashes with lots of broken things.
They need to reflect the current project.

## Step 4 — Write down every single feature and where it lives in code

Document every feature, animation, etc. — for example: animations for both the
Keivotos sidebar and the Waifu-Hoard sidebar; the Waifu-Hoard sidebar
expand/hide button that is draggable; search functions; challenges; timelapse;
popularity; user profile; artist new-Danbooru-upload notifications (both the
top-bar one and the one in profile for favorite artists); tags using Danbooru's
tag info; follow artist; artist history; and many more not listed here.

For each feature, record which code file and which lines it associates with.
When we make changes, we check this register to see what the change correlates
to, so we do not lose what the code does — the line is saved to the md
temporarily so code is not lost and we can check side by side. When we optimize
or improve, optimizing means making the code smaller if possible; if not, that
is fine. The most important part is: NO regressions.

## Step 5 — Design the modular architecture

## Step 6 — Gradually reduce core.py

## Step 7 — Centralize path handling (or confirm the project already does)

## Step 8 — Begin application-code refactoring, starting with bringing lost features back

Compare against the archived versions and bring back the best version of the
sidebar animations, and everything else that was lost, before refactoring:

```
D:\Kivotos\Github_Wakaru\Keinomous-Updates\V0.0.1 - Risen from death
D:\Kivotos\Github_Wakaru\Keinomous-Updates\V0.0.2
D:\Kivotos\Github_Wakaru\Keinomous-Updates\V0.0.2 - (beta2)
D:\Kivotos\Github_Wakaru\Keinomous-Updates\V0.0.2 - (beta3) changed settings design
D:\Kivotos\Github_Wakaru\Keinomous-Updates\V0.0.2 - (beta4)
D:\Kivotos\Github_Wakaru\Keinomous-Updates\V0.0.2 - (beta5)
D:\Kivotos\Github_Wakaru\Keinomous-Updates\V0.0.2 - (beta6) css slidefade animation
D:\Kivotos\Github_Wakaru\Keinomous-Updates\V0.0.2 - changed server.py, backups, fixed bugs, thumbnail fix
D:\Kivotos\Github_Wakaru\Keinomous-Updates\V1.0.0 - (beta1) Changed the tools
D:\Kivotos\Github_Wakaru\Keinomous-Updates\V1.0.0 - (beta2)
D:\Kivotos\Github_Wakaru\Keinomous-Updates\V1.0.0 - (beta3) backups, sidecars, sqlite
D:\Kivotos\Github_Wakaru\Keinomous-Updates\V1.0.0 - (beta3.1) - little optimization
D:\Kivotos\Github_Wakaru\Keinomous-Updates\V1.0.0 - (beta4) - home redesign
D:\Kivotos\Github_Wakaru\Keinomous-Updates\V1.0.0 - (beta5) - general consistancy, minor fixes
D:\Kivotos\Github_Wakaru\Keinomous-Updates\V1.0.0 - (beta6) - ultimate optimization for everything
D:\Kivotos\Github_Wakaru\Keinomous-Updates\V1.0.0 - (Release Candidate 1) Release both github and build
D:\Kivotos\Github_Wakaru\Keinomous-Updates\V1.0.0 - (Release Candidate 2) Release both github and build
D:\Kivotos\Github_Wakaru\V1.0.0 - (Release Candidate 3) Bug patches
D:\Kivotos\Github_Wakaru\V1.0.0 - (Release Candidate 4) Bug Patches
D:\Kivotos\Github_Wakaru\V1.0.0 - (Release Candidate 5) Worst Version
```

## Gate — implementation does not start until ALL of these are true

1. Current features are documented.
2. Broken features are identified.
3. Archived working versions are mapped.
4. The new architecture is agreed upon.
5. Regression checks exist.
6. I explicitly say "now implement it."
