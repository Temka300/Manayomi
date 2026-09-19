# Keivotos — Design Philosophy

Why the architecture is what it is. Nearly every choice maps to a well-worn
principle in general software design; this doc records the reasoning and the
broader developer consensus behind it.

## Current-state note

The current release identity is named in [ROADMAP.md](./ROADMAP.md#current-cycle);
the shipped version is `backend/product.py`. This document explains
the principles behind the implementation present in source; it does not claim
that every behavior has been freshly exercised. V1.10 and post-V1.0 material
belong to future planning. Historical archive names and earlier design labels
remain unchanged as evidence.

A note on lineage: an earlier version of this document (written for the
retired intermediate SvelteKit rebuild)
argued for the *opposite* storage model — one SQLite file as the single source
of truth, sidecars killed as a "pile of files" anti-pattern. Keivotos is the
original app resurrected, and it keeps the original's sidecar model — but
refined. Section 2 explains why that isn't a regression.

---

## 1. The database references files on disk; it never stores them

Images stay in their folders; SQLite holds metadata plus a path pointer. We
never stuff image bytes into a database. This is the textbook answer: metadata
wants ACID and querying; bytes want the filesystem. Databases choke loading
BLOBs on queries that don't need them; filesystems are built for serving bytes
(and FastAPI serves ranges for video straight off disk).

> Refs: [Brent Ozar — Store Files in a File System, Not a Relational Database](https://www.brentozar.com/archive/2021/07/store-files-in-a-file-system-not-a-relational-database/),
> [DZone — File System vs. Database](https://dzone.com/articles/which-is-better-saving-files-in-database-or-in-fil)

## 2. Sidecars are the durable store; SQLite is a disposable index

**The choice:** per-file `.danbooru.json` / `.tags.txt` sidecars under the
configured metadata directory are the durable metadata record;
`danbooru.sqlite` is a rebuildable index over them, kept fresh by an
incremental `sync`.

**Why the rebuild argued the other way, and why we still choose sidecars:**
the single-DB argument (SQLite's own ["pile of files"](https://sqlite.org/appfileformat.html)
essay) is real — atomic writes, one-file backup, queryability. But its sting
was always operational: *"the sidecar model made rebuilding the DB a routine
chore."* That pain is gone. The `sync_manifest` (mtime/size) delta import means
the index is maintained incrementally — unchanged files are never even opened —
and the full rebuild is demoted to a recovery tool. What remains are the
sidecar model's genuine strengths for an archive:

- **One durable record per image without touching source folders.** A stable
  registered-root ID plus relative path replaces the old one-hash-directory-
  per-external-file layout. External libraries remain preservation-owned and
  read-only from the importer's perspective; metadata can be copied as one
  coherent tree or `.keivotosbk` bundle.
- **Blast-radius isolation.** A corrupted index costs a rebuild, not your
  metadata. A bad import is re-runnable. The old single-DB design had to make
  backups a first-class feature *because* one file held everything.
- **Write-once, archive-on-change.** Sidecars are effectively immutable;
  refreshes archive the replaced files. The "half-written JSON on crash"
  concern applies to hot mutable state, which sidecars are not.
- **Greppable, future-proof, tool-friendly.** Plain JSON on disk outlives any
  schema. gallery-dl produces the same format — the acquisition tool and the
  archive speak the same language natively.

**The refinement over the original:** hot, mutable, *irreplaceable* state does
not belong in scattered files — so it lives in exactly one place,
`user.sqlite`, which gets the full single-DB treatment (atomic writes, additive
migrations, never rebuilt). Each kind of data gets the storage its write
pattern deserves.

## 3. Be honest about what's "truth" vs. "cache"

One source of truth per datum; everything derived is disposable and
regenerable (the [materialized-view pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/materialized-view)).
The line-drawing:

| Data | Role | Recoverable if lost? |
| --- | --- | --- |
| Image bytes (media folders) | primary — your archive | no → back up the folders |
| Sidecars (Danbooru metadata) | durable, upstream-derived | yes, `backfill` re-fetches (slow) |
| `user.sqlite` (favorites, collections, user tags, follows, views…) | **authoritative, exists nowhere else** | **no → automatic local checkpoint + include it in a manual backup** |
| `danbooru.sqlite` (index + sync manifest) | materialized view over sidecars | yes — rebuild + sync |
| Thumbnails | derived cache | yes — regenerated on demand |

Danbooru is an *upstream enrichment source* we pull from once — not the source
of truth for your library. The things only you produced are concentrated in
one small file. Verified five-slot checkpoints protect it automatically on the
same device; the manual backup surface can package it with either database,
sidecars, sidecar history, and artist profile media without duplicating the
image archive or derived thumbnails.

## 4. Content-addressing by MD5 → dedupe, idempotency, and durable user data

Every file is keyed by its MD5 — read from the gallery-dl filename
(`{id}_{md5}.{extension}`) when present, computed once otherwise. Three things
fall out of this content-addressable-storage move:

- **Deduplication:** the duplicate-review feature is just CAS applied to the
  UI (same key = true duplicate; parent/sibling posts are explicitly *not*
  duplicates).
- **Idempotent ingestion:** the same content always produces the same key, so
  re-running backfill or sync is safe and repeatable.
- **Rebuild-proof user data:** `user_file_match` ties favorites, collections
  and the rest to *file identity*, not to rebuildable row ids — a full index
  rebuild cannot orphan a favorite.

> Refs: [Content Addressable Storage — DevX](https://www.devx.com/terms/content-addressable-storage/)

## 5. Sync is an idempotent reconciliation loop, not a one-shot import

The `sync` tool compares the world (files + sidecars, by mtime/size) against
the index and acts only on the delta: new/changed sidecars imported,
sidecar-less media indexed minimally, rows for deleted files pruned. Same idea
as Kubernetes reconciliation and warehouse incremental loads: persistent state
between runs (`sync_manifest`), upsert-style idempotent operations,
replay-safe under repeated runs. A crashed sync just gets re-run.

> Refs: [Idempotent Data Reconciliation — DEV](https://dev.to/137foundry/idempotent-data-reconciliation-production-patterns-that-dont-create-noise-4lpm),
> [Kubernetes reconciliation loop](https://dev.to/naveens16/beyond-yaml-building-kubernetes-operators-with-crds-and-the-reconciliation-loop-524d)

## 6. gallery-dl does one thing well; we orchestrate, we don't absorb

The app itself never scrapes. gallery-dl remains the acquisition engine —
bundled for convenience, driven by `scripts/danbooru_gallery_dl.py`, but still
a separate program composed through the filesystem: it writes files (with the
MD5 in the name) and sidecar-compatible metadata; the pipeline picks them up.
Unix philosophy — the power is in the relationship between the tools, and
either side can change independently. The same policy extends to future
modules: prefer blessed external CLI tools (yt-dlp, exporters) over bundling
scraping libraries.

> Refs: [Unix philosophy — Wikipedia](https://en.wikipedia.org/wiki/Unix_philosophy)

## 7. Local-first & personal — own your data, optimize for you

Single-user, self-hosted, offline. No accounts, no cloud, no lock-in, no
telemetry. Files + JSON + SQLite is about the most openable-in-100-years
combination there is (the [local-first](https://www.inkandswitch.com/essay/local-first/)
argument). Corollaries the app enforces:

- **No hotlinking, no surprise downloads.** Remote content renders as
  placeholders until *you* choose to fetch it.
- **The chrome recedes; the artwork is the interface.** Compact, practical UI;
  icon-only controls; no controls added just because a reference app has them.
- **YAGNI applies hard** — software for an audience of one doesn't get
  speculative multi-user, cloud, or theming complexity.

## 8. Preserve behavior before reducing code

Animation, motion, immediate visible updates, path containment, compatibility
exports, migrations, and recovery behavior are product contracts even when
their implementation looks larger or indirect. Optimization is successful only
when it preserves those contracts.

This matters especially during the current refactor:

- a static source assertion is not proof that a timed interaction works;
- code is not removable merely because a direct caller is hard to find;
- wildcard imports and packaged/background entry paths make "unused" analysis
  unsafe until dependencies are explicit;
- restoration and architectural extraction are separate changes;
- smaller code is desirable only after equivalent behavior is characterized.

The user-reported broken Danbooru sidebar animation is the immediate example:
its grip, persistence, scroll behavior, delayed reveal, rapid-toggle behavior,
and open/close motion must be observed together before any implementation is
replaced.

## 9. The phoenix lesson — durability comes from plural, boring artifacts

This project *died* once: the original source was lost, and the versioned
backups turned out to be empty skeletons. It came back only because durable,
plain-text artifacts existed outside the primary store — session logs from
which 141k+ lines were re-verified ([RECONSTRUCTION_LEDGER.md](archive/RECONSTRUCTION_LEDGER.md)).
That is the same bet the storage model makes: keep the irreplaceable core
small and known (`user.sqlite`), keep the bulk in boring open formats that
survive tooling loss (files + JSON), and make everything else cheap to
regenerate. And the operational caveat stands: **create metadata backups and
back up the external media folders separately** — the code can be resurrected;
your hoard and your curation cannot.
