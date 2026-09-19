# Languages Module Plan

Status: **implemented and verified locally 2026-07-28.** Every open question
in the first draft of this document was answered by the user and is recorded
in §11. All thirteen original slices and the combined Analyzer/library-view
extension in §12 are complete. The full regression, zero-warning frontend
check/build, and isolated real browser interactions passed; no version,
release, package, or Git operation was performed.

The shipped product version stays owned by `backend\product.py` and
`scripts\release\set_version.py`. This plan authorizes no version bump,
release, package, or Git operation. It is **not** tied to a release cycle —
V1.1.3's Karaoke/YouTube work is unrelated and this module does not join it.

Companion reading: [SUITE_MODULE_CONTRACT.md](./SUITE_MODULE_CONTRACT.md)
(§3 databases, §4 roles, §5 metadata ownership, §6 lifecycle, §8 API
namespacing, §9 frontend) and
[KARAOKE_YOUTUBE_MODULE_PLAN.md](./KARAOKE_YOUTUBE_MODULE_PLAN.md), whose
descriptor, storage, and publication shape this plan copies rather than
reinvents.

---

## 1. Outcome

Keivotos gains one optional module, **Languages** (slug `language`), without
changing the behavior of Files, Danbooru, Reddit, Karaoke, or YouTube.

Its stated goal, in the user's words: **show every word I have learned.**

- It **mirrors** vocabulary from Anki into a local, browsable surface — words,
  English and Mongolian senses, example sentences, word/sentence audio,
  images, grammar notes, tags, and how far along each word is.
- It **stands alone too**: words can be typed in by hand, and mirrored words
  can be edited, with no Anki running.
- It **practices** what you have learned, in Languages only.
- It **never writes to Anki**, and never schedules. Anki keeps scheduling.
- Its local library publishes to Files, so audio and images are ordinary
  browsable files with durable identity.

Dependency direction:

```text
Languages -----> Files services and durable file identity
Languages -----> AnkiConnect (READ-ONLY, loopback, user-initiated)
Languages -X-> Danbooru / Reddit / Karaoke / YouTube internals
Languages -X-> any write into an Anki collection, ever
Files     -X-> Languages internals
```

---

## 2. Storage: the Files role and `data\` both, for different jobs

§4.2 of the contract separates them: a *role* answers "who manages this
location"; `data\` is "where this module keeps its own things".

| Thing | Where | Kind |
| --- | --- | --- |
| Module index | `data\modules\language\language.sqlite` | disposable, rebuildable |
| Imported audio/images/receipts | `data\modules\language\media\library\ko\<word-key>\` | create-only, published to Files |
| Anything the user typed | `user.sqlite`, `language_*` tables | precious, additive |
| A user's own study folder (textbook PDFs, drama subs) | wherever it lives, registered with the **Languages** role | optional |

**The Files role costs no new UI work, but it does require safe backend
hooks.** `services\folder_roles.py` `_validate_role` builds the role list from
`MODULE_REGISTRY`, so registering a `language` descriptor makes "Languages"
appear as a selectable role in the Files *Manage folders* dialog and as a
folder badge. The descriptor's adopt/release hooks update only the Files source
registry; they never move, delete, or rewrite files on disk.

**Words are not files and do not live in a folder the user creates.** Mirrored
words live in `language.sqlite`; authored words live authoritatively in
`user.sqlite` and may have a disposable read projection in `language.sqlite`.
Only their *media* becomes files, under `data\modules\language\`, published to
Files by the descriptor's publish hook exactly as
`modules\youtube\__init__.py` does.

The governing rule everywhere: **anything the user typed goes to `user.sqlite`;
anything re-derivable from Anki or from disk goes to `language.sqlite`.**

---

## 3. Research contract

### 3.1 AnkiConnect is the only ingest path

The AnkiConnect add-on (`2055492159`) runs a loopback HTTP server on
`127.0.0.1:8765` while Anki is open, bound to localhost by default, with
`localhost` a trusted origin. Every call is `POST /` with
`{"action": ..., "version": 6, "params": {...}}`, returning
`{"result": ..., "error": null}`.

The user's setup is default: port 8765, no API key, one profile. Port and API
key are still exposed in Settings (key via the existing encrypted credential
store, as Danbooru's is), but multi-profile handling is **not** built.

Actions used, and **only** these — all read-only:

| Action | Use |
| --- | --- |
| `requestPermission` | first call; confirms trusted origin and whether a key is required |
| `version` | capability floor |
| `deckNames`, `modelNames`, `modelFieldNames` | deck picker and field mapping |
| `findNotes` | note IDs for the scoped deck query |
| `notesModTime` | cheap incremental check; only changed notes are refetched |
| `notesInfo` | fields, tags, `modelName`, `mod`, `cards` |
| `cardsInfo` | `interval`, `due`, `reps`, `lapses`, `queue`, `type`, `deckName` |
| `findCards` | current due-card query for a user-triggered sync/probe |
| `getReviewsOfCards` | last reviewed timestamp for mirrored cards |
| `getMediaDirPath`, `retrieveMediaFile` | locate and pull `[sound:...]` / `<img src>` payloads as base64 |

`notesModTime` detects note-content edits, not scheduling-only changes. A
confirmed sync therefore refreshes card progress separately. `cardsInfo.due`
is stored verbatim because its meaning varies by queue; the import also stores
the explicit due-now result from `findCards` rather than guessing from the raw
number. The Today view reads that cached snapshot and never contacts Anki on
page load.

**Never called, by any slice, ever:** `addNote`, `updateNoteFields`,
`deleteNotes`, `removeEmptyNotes`, `storeMediaFile`, `deleteMediaFile`, `sync`,
`guiDeckReview`, or any other mutating action. This is permanent and absolute,
not a first-build default. A test asserts the client module contains no
mutating action name.

Sources: <https://git.sr.ht/~foosoft/anki-connect> ·
<https://foosoft.net/projects/anki-connect/>

### 3.2 `.apkg` import — dropped

Researched and rejected. Anki 2.1.50+ writes a **modern** package
(`collection.anki21b`, zstd-compressed, schema v18, protobuf media map); only
the legacy export produces the parseable `collection.anki2` + JSON media map.
A file importer that fails on Anki's default export format is worse than none.
Although the repository already has zstandard support, the modern collection
schema and protobuf media map would duplicate Anki's own compatibility work.
AnkiConnect covers the real workflow and manual entry covers the rest.

Sources: <https://docs.ankiweb.net/exporting.html> ·
<https://eikowagenknecht.com/posts/understanding-the-anki-apkg-format/> ·
<https://github.com/ankitects/anki/releases/tag/2.1.54>

### 3.3 The real note type, and why the schema is not thirteen columns

Scope for the first build is **`한국어::2. Refold KO1K v2` only** (~1000 notes,
whose live note type is `KO1Kv2+`), with fields: `Index`, `Word`, `Word Audio`,
`Definition`, `Word in Sentence Form`, `Example Sentence`, `Sentence Audio`,
`Sentence Translation`, `Image`, `Grammar Notes`, `Example Sentences`,
`Pronunciation`, `Tags`.

Observed facts the schema must survive:

- `Definition` and `Sentence Translation` hold **stacked lines** — English on
  line 1, Mongolian on line 2 (`to congratulate` / `Баяр хүргэх`).
- `Word Audio` / `Sentence Audio` hold `[sound:KO1K_백수_word.mp3]` tokens.
- `Word in Sentence Form` differs from `Word` (`축하하다` → `축하해요`). This is
  the form that actually appears in the sentence and is what the highlighter
  matches on first.
- Fields are routinely empty (`Image`, `Pronunciation`, `Example Sentences`),
  and grammar notes such as `-이다` have no word audio, no image, and a long
  `Grammar Notes` body.
- `Index` (808, 345, 219) is the deck's intended learning order.
- The collection's other decks (`500 Words`, `Core10K` 1–6, `Evita 6500`,
  `KRDICT 10K`, `문법`, `채굴 덱`, `The Sounds of Korean`, `Korean Immersion`)
  are **different note types** and are out of scope for now but must not
  require a schema change to add later.

Hence: a word row plus a per-note-type **profile**, never hardcoded columns.

---

## 4. Data model

### 4.1 `language.sqlite` — disposable index

```text
language_words
  word_id TEXT PK            sha256(source | source_key), stable across edits
  lang TEXT                  'ko' today; the column exists from day one
  headword TEXT              축하하다
  sentence_form TEXT         축하해요           (falls back to headword)
  reading TEXT               from Pronunciation only; never generated
  source TEXT                'anki' | 'manual' (manual is a disposable projection)
  source_key TEXT            Anki noteId, or a generated id for manual
  note_type TEXT             'KO1Kv2+' (or another field-compatible KO1Kv2 variant)
  deck TEXT                  '한국어::2. Refold KO1K v2'
  sort_index INTEGER         the deck's Index field; the default sort
  fields_json TEXT           the complete original field map, verbatim
  media_json TEXT            resolved local media relative paths
  anki_mod INTEGER
  missing INTEGER DEFAULT 0  set when the note vanishes from Anki
  suspended INTEGER DEFAULT 0
  added_at, updated_at
  UNIQUE(source, source_key)

language_senses        word_id, lang ('en'|'mn'), position, text
language_examples      word_id, position, sentence, translation_json, audio_rel
language_notes_text    word_id, kind ('grammar'|'pronunciation'|'usage'), body
language_tags          word_id, name
language_media         media_id, word_id, role, position, relative_path,
                       sha256, bytes, origin_filename, active, imported_at
language_progress      word_id, card_id, interval, due, reps, lapses,
                       queue, type, stage, card_mod, due_now,
                       last_reviewed_at, synced_at
language_sync_runs     run_id, scope_json, counts, started_at, finished_at, error
```

Built-in profile defaults live in code; confirmed or edited profiles are
precious rows in `user.sqlite`. That is what lets five different decks land in
one UI later without making a user's confirmed mapping disposable. A profile
maps note-type field names onto canonical roles:

```json
{
  "note_type": "KO1Kv2+",
  "map": {
    "Word": "headword",
    "Word in Sentence Form": "sentence_form",
    "Definition": "sense_block",
    "Example Sentence": "example",
    "Sentence Translation": "example_translation_block",
    "Word Audio": "word_audio",
    "Sentence Audio": "sentence_audio",
    "Image": "image",
    "Grammar Notes": "grammar",
    "Pronunciation": "reading",
    "Index": "sort_index"
  },
  "sense_languages": ["en", "mn"]
}
```

A `*_block` role means "split on line breaks; line *n* is
`sense_languages[n]`", guarded by a script check (Hangul → `ko`, Cyrillic →
`mn`, Latin → `en`) so a reordered or single-line field is never mislabelled. A
one-line definition produces one sense, not an empty Mongolian row. Profiles
are proposed by name matching and **shown for confirmation before the first
import of a note type** — never silently guessed.

**Progress aggregation:** one row in the wall is one *note*. When a note has
several Anki cards, `language_progress` keeps every card, and the displayed
stage is the **weakest** one (lowest interval), so a word only reads as mature
when every direction is.

**Manual and mirrored words can collide**, and must not silently duplicate. A
hand-added word and a later Anki import matching on `(lang, headword)` are
offered as a **merge**: the mirrored row becomes the base, everything the user
typed is converted to overrides and notes, and the manual row is retired with
its media re-pointed. The merge is proposed at import preview time and needs
one confirmation — it is never automatic, and declining it keeps both rows with
a "possible duplicate" marker. Nothing the user typed is discarded either way.

### 4.2 `user.sqlite` — precious, additive

```text
language_user_words        word_id PK, payload_json   -- fully hand-authored
language_user_overrides    word_id, field, value      -- your edit shadows the mirror
language_user_notes        word_id, body, retired_at, merged_into_word_id, updated_at
language_user_media        media_id, word_id, role, position, relative_path,
                           sha256, bytes, origin_filename, active, created_at
language_favorites         word_id, added_at
language_word_lists        list_id, name, description, retired_at
language_word_list_items   list_id, word_id, position, retired_at
language_sync_scope        deck_pattern, enabled
language_profiles          note_type PK, mapping_json, updated_at
language_anki_settings     singleton, port, sync_mode, updated_at
language_practice_sessions session_id, mode, set_json, status,
                           started_at, finished_at
language_practice_results  session_id, word_id, mode, correct, answered_at
```

An override never rewrites the mirrored row; it shadows it at read time, so a
re-sync can never clobber something the user typed. An edited word shows a
quiet "edited" marker with one-click revert. A note deleted in Anki is marked
`missing` and keeps its row, its media, its overrides, and its notes — the
same missing≠deleted rule the Files base uses (contract §4.3). Suspended cards
stay fully visible with a small marker; they are still words you learned.
Manual words, lists, list membership, and manual media associations are
soft-retired with tombstones instead of hard-deleted. Rebuilding
`language.sqlite` reprojects all active authored rows from `user.sqlite`.

### 4.3 Media on disk

```text
data\modules\language\
  language.sqlite
  media\library\ko\<word-key>\
      word.<content-prefix>.mp3
      sentence.<content-prefix>.mp3
      image.<content-prefix>.jpg
      note.<sync-id>.metadata.json      original note + import receipt
  staging\
```

Folders are named with the Hangul headword rather than a hash, because this
root is browsable in Files and `media\library\ko\축하하다\` is legible where a
hash is not. Collisions get a numeric suffix.

`note.metadata.json` archives the complete original note: every field
verbatim, tags, note type, deck, card ids, and **the rendered question/answer
HTML plus the note type's CSS from `cardsInfo`**. The rendered form is stored
as insurance so nothing is lost on import, and is **never displayed** —
Keivotos draws its own design from the mapped fields, and importing Anki's
styling would mean two visual truths for the same word.

Copies are **create-only** (staged, then installed only when the destination
does not exist), mirroring `modules\youtube\storage.py`. Names are versioned by
content or sync identity, so a later Anki edit never overwrites the previous
bytes or receipt. Anki's `collection.media` is read and never written.

Copying rather than referencing is deliberate: Anki's Check Media can move or
delete files out from under a reference, a profile switch changes the path, and
only a copy gets a content hash and a Files identity. Cost is a few hundred KB
per word.

---

## 5. Backend surface

`/api/language/*`, router always mounted, every endpoint gated by
`_require_enabled()` exactly as `routers\youtube.py` does.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/language/status` | enabled, counts, storage paths, cached probe state, last sync; no network |
| GET | `/api/language/words` | list/search/filter/sort, `offset`+`limit` paging |
| GET | `/api/language/words/{word_id}` | one word, overrides applied |
| POST | `/api/language/words` | manual create |
| PATCH | `/api/language/words/{word_id}` | edit — writes an override for mirrored words |
| DELETE | `/api/language/words/{word_id}/override` | revert to the mirrored value |
| DELETE | `/api/language/words/{word_id}` | soft-retire manual words only; refuses on mirrored rows |
| POST | `/api/language/words/{word_id}/media` | attach a local file (create-only copy) |
| GET | `/api/language/media/{word_id}/{role}` | range-served playback via `services\range_serving.py` |
| GET | `/api/language/decks` | mirrored deck tree + counts |
| GET | `/api/language/today` | cards due today, from mirrored progress |
| GET/POST/DELETE | `/api/language/favorites` | precious |
| GET/POST/PATCH/DELETE | `/api/language/lists` | word lists |
| POST | `/api/language/practice/session` | build a session from a set + mode + length |
| POST | `/api/language/practice/answer` | record a result; writes nothing to Anki |
| GET | `/api/language/practice/stats` | per-word and per-set accuracy |
| POST | `/api/language/bulk` | favorite / add-to-list / unfavorite over a word-id set |
| GET | `/api/language/export` | full JSON export of the library and all user data |
| GET/PUT | `/api/language/settings` | local port/mode/probe cache plus DPAPI-protected optional API key |
| GET | `/api/language/anki/probe` | `requestPermission` + `version` + `deckNames`; imports nothing |
| POST | `/api/language/anki/preview` | dry run: what a scope **would** import; writes nothing |
| POST | `/api/language/anki/import` | start a confirmed background import from a previewed token |
| GET/DELETE | `/api/language/anki/jobs/{job_id}` | progress/result, or cooperative cancel |
| GET; GET/PUT | `/api/language/profiles`; `/api/language/profiles/{note_type}` | confirmed field mappings |

Preview-then-confirm is the same plan/authorize shape Karaoke and YouTube use.
**No AnkiConnect call happens on page load** — every one is user-triggered.

---

## 6. User experience

Plain Svelte 5 + Tailwind 4, the app's existing accent-tint idiom
(`bg-amber-500/10 text-amber-300`), the reusable `GridSizeMenu`, and the
overlay-not-page contract from ARCHITECTURE §F. The existing `SearchBar` and
`FilterChips` are Danbooru-store-specific, so Languages owns small equivalents
instead of coupling itself to Danbooru state. System font throughout — no
bundled webfont, so Hangul renders in Malgun Gothic on Windows and the design
carries the weight instead.

### 6.1 Word wall — the default view

A responsive CSS grid of **word cards**, sorted by the deck's `Index` so the
wall reads as the intended progression through KO1K.

Card face at the default size:

- the Hangul headword large and heavy, with `sentence_form` small beneath when
  it differs;
- **English on the prominent line, Mongolian beneath it** smaller and cooler —
  the two-language stack is this module's visual signature;
- a thin **mastery meter** across the foot, fed by the mirrored Anki interval
  only, tinted by stage: new (slate) → learning (amber) → young, under 21d
  (sky) → mature, 21d+ (emerald). Local practice results never touch this bar;
- the note image as a low-opacity background wash behind the text — the
  treatment the Files origin-attachment tile face already uses — never a hard
  photo block fighting the Hangul;
- a speaker button fading in on hover, playing word audio in place;
- grammar-body notes such as `-이다` render with a distinct grammar treatment
  instead of an image wash; they stay in the wall because they are words you
  learned;
- `missing` and `suspended` carry quiet corner markers.

**Paging follows Danbooru exactly** ([ImageGrid.svelte:589](../../frontend/src/components/ImageGrid.svelte:589)):
one page-size control where a number gives numbered pagination with a page bar,
and `'all'` switches to infinite scroll that appends a batch when the container
is within 900px of the bottom. Same control, same two behaviors, no second
pattern invented. Sizes are 30 / 60 / 120 / all, defaulting to **60** — word
cards are far smaller than image thumbnails, so Danbooru's default of 10 would
read as a nearly empty wall.

**Selection mode.** A select toggle in the header turns cards into checkboxes
and raises an action bar: Favorite, Add to list, Practise these. Building a
word list out of a thousand mirrored notes one card at a time is the kind of
friction that makes a feature go unused, and lists are in scope from the start,
so the two ship together.

**First-run empty state**, before anything is mirrored: two buttons, *Connect
to Anki* and *Add a word*, and nothing else. The module is off by default like
every other optional module, per the suite contract.

Motion: small lift and border-brighten on hover, meter width transition on
sync, staggered first paint. All of it inherits the existing
`html[data-motion='reduced']` guard in `app.css`.

### 6.2 Detail overlay

Opened over the wall, not routed to:

- left — image, the two audio players, and the **example sentence with the
  target form highlighted inline**. The matcher tries `sentence_form` first,
  then `headword`; if neither matches it highlights nothing rather than
  guessing. No stem fallback, no tokenizer;
- **word audio autoplays on open**; the longer sentence clip stays on click so
  it never talks over you;
- right — senses stacked per language in labelled rows, then Grammar Notes in a
  visually distinct panel (grammar is prose, not a field, and must not look
  like one), then pronunciation when the note has one, then tags as chips;
- footer — deck path, note type, interval/reps/lapses, last reviewed, **your
  local practice accuracy shown separately from the Anki meter**, an "edited"
  marker with revert when an override exists, and a "your note" box;
- keyboard: `←`/`→` between words, `Space` replays word audio, `Esc` closes.

### 6.3 The other views

- **Today** — a rail of what is due in Anki right now. Read-only; it shows the
  day's shape and grades nothing.
- **Sentences** — every example sentence in one reading column with target
  words highlighted.
- **Grammar** — only notes carrying a grammar body, as readable articles.
- **Decks** — the mirrored deck tree with counts and sync scope.
- **Table** — a dense sortable layout toggle on the Words view, for auditing
  what is missing across a thousand notes (no audio, no image, no Mongolian).
- **Practice** — §6.5.

### 6.4 Adding and editing words

A composer sheet sliding from the right, the shape `RedditCaptureDrawer` and
`YouTubeDownloadSheet` established. Two entry points in the header:
**+ Add word** and, on any open word, **Edit**.

- one row for the word: headword · sentence-form · reading;
- a **senses stack** — English and Mongolian rows by default, `+` for another;
- an **example block** — sentence, translations, and a live highlight preview;
- **media slots** — three drop targets (word audio, sentence audio, image),
  each accepting drag-and-drop or a native file pick, copying create-only on
  save;
- collapsed-by-default grammar / pronunciation / tags;
- deck optional, defaulting to a `Keivotos` pseudo-deck so hand-made words
  never pretend to be Anki notes.

Editing a mirrored word writes an **override**, never a change to the mirror,
and never anything to Anki. Manual words are marked `source='manual'` and are
the only ones `DELETE` removes.

### 6.5 Practice — Languages only, never pushed to Anki

Sessions, not scheduling. **Nothing claims a due date, nothing is written to
Anki, and nothing feeds the mastery meter.**

**The wall is the set builder.** A *Practise* button in the header runs against
whatever is on screen — the current search, deck, tag, list, favorites, stage
filter, or an explicit selection — and opens full-bleed over the wall, the same
way the detail overlay does. There is no separate builder view, because
building one would duplicate the filtering the wall already does. Length is
10 / 20 / 50 / all, defaulting to **20**.

All four modes ship:

| Mode | Prompt → answer |
| --- | --- |
| Korean → meaning | `축하하다` → "to congratulate / Баяр хүргэх" |
| Meaning → Korean | the senses → recall the Hangul |
| Audio → meaning | play the clip with text hidden; only offered on notes that have audio |
| Sentence cloze | `생일 ___!` with the target form blanked using `sentence_form` |

**Self-graded, never typed.** Every mode reveals the answer and asks *knew it*
/ *didn't*. Typing Hangul mid-session is friction that measures your IME, not
your memory, and one interaction model across four modes is one thing to learn
and one thing to verify. Keyboard: `Space` reveals, `1` / `2` grade, `Esc`
leaves — the session is saved as abandoned, not discarded.

The summary lists what you missed with a **Practise just these again** button,
which is the only reason a session-based tool beats a shuffled list. Results
land in `language_practice_results`; per-word accuracy surfaces on the detail
overlay, kept visibly separate from Anki's meter.

### 6.6 Settings

A new **Languages** category in `AppSettingsModal.svelte`; the existing
`settingsPresentation.ts` stays limited to its current shared presentation
helpers:

- `language-anki` — connection status, probe button, port and optional API key,
  deck scope, incremental vs full, and a plain statement that Keivotos never
  writes to Anki;
- `language-profiles` — note-type field maps;
- `language-storage` — library path, DB path, Files publication, media counts,
  and the JSON export button;
- `language-display` — default grid size, page size, sort, autoplay toggle.

### 6.7 Drawer icon

A small monochrome SVG in `frontend\public`, matching the drawer's existing
style, so Languages has an icon like Danbooru rather than falling back to text
like Karaoke and YouTube. A few hundred bytes, no licensing.

---

## 7. Non-goals

Confirmed out:

- **Any write to Anki — permanently.** Not notes, not media, not sync. §3.1.
- **Scheduling of any kind.** Anki + FSRS is the sole authority. Practice
  sessions record accuracy and nothing else.
- **`.apkg` / `.colpkg` import.** Dropped, §3.2.
- **KRDICT lookup.** The National Institute of Korean Language open API does
  publish Korean→Mongolian and Korean→English entries and is an unusually good
  match for this user's two languages, so it is a strong later candidate — but
  it needs a registered key and a network call, so it is out until the module
  works. <https://krdict.korean.go.kr/eng/openApi/openApiInfo>
- **Text-to-speech.** Out; the KO1K deck already carries real recordings.
- **Romanization generation.** The `Pronunciation` field shows when a note has
  one; nothing is ever generated.
- **New runtime dependencies.** Everything newly written here is stdlib:
  `json` over loopback HTTP, `sqlite3`, `hashlib`, `base64`. Same no-new-
  dependency discipline as V1.1.2. A Korean morphological tokenizer and any
  TTS engine are excluded by this rule; the repository's existing zstandard
  dependency does not change the `.apkg` decision in §3.2.
- **Multi-language UI.** Korean only; the `lang` column and per-language sense
  rows exist from day one so a second language is data entry, not a migration.
- **CSV export shaped for re-import into Anki.** JSON export ships (§7.1), but a
  round-trip format invites exactly the two-way sync this module refuses to be.
- **Typed answers in practice**, and any input method work.
- **Multiple Anki profiles**, handwriting, OCR, reader integration.

### 7.1 Export is in scope, and here is why

A single `GET /api/language/export` producing one JSON file: mirrored words,
hand-made words, overrides, personal notes, favorites, lists, and practice
history.

Most of that is reconstructible — the mirror can be rebuilt from Anki at any
time. But hand-made words, edits, notes, lists, and practice history **exist
nowhere else**, and a module whose whole posture is "never lose user data"
should not be the only copy of something with no way to get it out. One
endpoint and one Settings button is a cheap answer to that.

---

## 8. Implementation slices

One logical change at a time, verified before the next, committed on its own.

| # | Slice | Verified by |
| --- | --- | --- |
| 1 ✓ | Descriptor + registry entry + disposable catalog schema + additive precious schema + storage layout + publish/adopt/release hooks | 360-test regression; Files publication and role transitions preserve disk and user rows |
| 2 ✓ | `/api/language/*` read endpoints, enablement-gated | tests + regenerated OpenAPI snapshot |
| 3 ✓ | Manual create/edit/soft-retire, override shadowing, media attach | isolated filesystem/SQLite tests; overrides and retired rows survive a simulated re-sync |
| 4 ✓ | AnkiConnect client: probe, preview, field-compatible KO1Kv2 profiles, sense splitting | stub tests plus a user-requested live read-only `KO1Kv2+` probe/preview; a test asserts no mutating action name appears in the client |
| 5 ✓ | Background confirmed import incl. versioned media pull, note + card incrementals, missing/suspended handling, manual↔mirrored merge | stubbed import with progress/cancel; the live 1,000-note import was intentionally not started during verification |
| 6 ✓ | Frontend surface, drawer/registry/surface wiring, icon, word wall, search, Danbooru-style paging + infinite scroll, empty state | zero-warning `npm run check`, production build, isolated browser pass |
| 7 ✓ | Detail overlay: audio autoplay, sentence highlighting, mastery meter, edit sheet | timed isolated browser interaction and frontend contract tests |
| 8 ✓ | Today, Sentences, Grammar, Decks, table toggle | isolated browser pass and frontend contract tests |
| 9 ✓ | Add-word composer sheet + media drop targets | isolated browser pass with a real create-only local SVG copy |
| 10 ✓ | Favorites, word lists, **selection mode and bulk actions** | API/frontend contracts plus isolated favorite and selection browser pass |
| 11 ✓ | Practice sessions, all four modes, self-grading, missed-words replay | cloze browser pass plus backend/frontend contracts; no Anki write path |
| 12 ✓ | Settings category + JSON export | browser pass; export round-trips through `json.loads` in tests |
| 13 ✓ | `FEATURES.md`, `FEATURE_CODE_MAP.md`, changelog | implementation-aligned doc review |

The slices were still implemented and verified at their internal boundaries,
but the user asked for one uninterrupted completion rather than thirteen
separate handoffs. The final result therefore covers the complete surface and
data path together.

---

## 9. Verification contract

Static inspection proves existence, not behavior:

- `.venv\Scripts\python.exe -m compileall -q .\backend .\scripts .\app.py`
- `.venv\Scripts\python.exe -m pytest` — new isolated tests for schema, profile
  mapping, sense splitting including the Cyrillic/Latin guard and the
  single-line case, weakest-card aggregation, media create-only refusal,
  override shadowing, missing≠deleted, and the no-mutating-action assertion;
- AnkiConnect covered primarily by a **stub server**; the user-requested
  follow-up also verified the live read-only probe/preview and compatible
  `KO1Kv2+` mapping without starting the import;
- `npm.cmd run check` / `npm.cmd run build`;
- real timed browser interaction against an isolated loopback home for hover lift,
  overlay open/close, audio autoplay, meter transitions, infinite-scroll
  append, and the composer sheet — a rendered snapshot does not verify motion;
- console and server logs clean.

Data-safety checks are explicit in the slice that introduces them: the client
has a strict read-action allowlist, stubbed imports prove the full workflow
without opening a live collection, `user.sqlite` migrations are additive only,
manual merge preservation is regression-tested, and module disable loses
nothing. A live Anki collection byte-comparison was intentionally not run.

---

## 10. What this plan does not touch

Files' base behavior, Danbooru, Reddit, Karaoke, YouTube, the shared
`user.sqlite` promotion, the deferred client-side router, path-policy
centralization, or the local-first/loopback-only posture — all unchanged.

---

## 11. Decision log (locked 2026-07-28)

Items 1–30 were decided by the user. Items 31–42 were delegated —
"take creative liberty" — and are recorded with their reasoning so any of them
can be overruled without re-deriving the argument.

| # | Decision | Chosen |
| --- | --- | --- |
| 1 | Naming | slug `language`, display **Languages** |
| 2 | Release cycle | unrelated to V1.1.3/V1.1.4; not cycle-bound |
| 3 | Language scope | Korean only, `lang` column reserved |
| 4 | Quiz | yes — Languages-only, never pushed to Anki |
| 5 | Deck scope | `한국어::2. Refold KO1K v2` only, to start |
| 6 | Sync trigger | manual button only, plus edit and add-word buttons |
| 7 | Wall granularity | one row per note, weakest card feeds the meter |
| 8 | Second language | Mongolian; **English first** on the card face |
| 9 | Romanization | none generated; `Pronunciation` shown when present |
| 10 | Media | copied create-only into the module library |
| 11 | Edits | override shadows the mirror forever, with revert |
| 12 | Default view | word wall |
| 13 | Views | Words + detail, Sentences, Table toggle, Today, Decks, Grammar |
| 14 | Font | system font, no bundled webfont |
| 15 | Deleted / suspended in Anki | deleted stays as `missing`; suspended stays visible |
| 16 | Grammar notes | in the wall **and** a Grammar view |
| 17 | Mastery meter | Anki interval only; practice accuracy shown separately |
| 18 | Audio | word autoplays on open; sentence on click |
| 19 | Favorites and lists | both, from the start |
| 20 | Practice modes | all four: ko→meaning, meaning→ko, audio→meaning, cloze |
| 21 | Sentence highlighting | `sentence_form` then `headword`; no stem fallback |
| 22 | Drawer icon | a simple SVG, written for this module |
| 23 | AnkiConnect setup | defaults (8765, no key, one profile); port/key configurable |
| 24 | `.apkg` import | dropped entirely |
| 25 | Scale | Danbooru's control: numbered pages, `'all'` → infinite scroll |
| 26 | Card face | headword, English, Mongolian, mastery meter |
| 27 | KRDICT | out for now, revisit after the module works |
| 28 | TTS | out for now |
| 29 | Dependencies | stay dependency-free |
| 30 | Default sort | deck order, by the `Index` field |

| # | Delegated decision | Chosen, and why |
| --- | --- | --- |
| 31 | Practice placement | A *Practise* button on the wall, running against whatever is on screen, full-bleed over the wall. No builder view — the wall's own filtering already is one, and duplicating it would be two things to maintain that disagree. |
| 32 | Session length | 10 / 20 / 50 / all, default 20. Long enough to be worth starting, short enough to finish. |
| 33 | Practice grading | Self-graded *knew it* / *didn't*, never typed. Typing Hangul measures your IME, not your memory, and one interaction model across four modes is one thing to verify. |
| 34 | Missed words | Session summary lists them with *Practise just these again* — the one thing a session beats a shuffled list at. |
| 35 | Anki's rendered card HTML/CSS | Archived in `note.metadata.json`, never displayed. Insurance against a wrong field mapping losing something, without importing a second visual truth for the same word. |
| 36 | Bulk selection | In, shipping with lists in slice 10. Building a list out of a thousand notes one card at a time is the kind of friction that makes a feature go unused. |
| 37 | Export | JSON export in (§7.1); CSV-for-Anki out. Hand-made words, edits, notes, lists and practice history exist nowhere else, and this module should not be their only copy. A round-trip format, by contrast, invites the two-way sync the module refuses to be. |
| 38 | Media folder names | The Hangul headword (`media\library\ko\축하하다\`), not a hash — that root is browsable in Files, where a hash is unreadable. Numeric suffix on collision. |
| 39 | Enabled by default | No. Off like every other optional module, per the suite contract. |
| 40 | Manual ↔ mirrored collisions | Offered as a confirmed merge at import preview, never automatic; declining keeps both with a duplicate marker. Nothing typed is ever discarded. |
| 41 | Page sizes | 30 / 60 / 120 / all, default 60. Danbooru's default of 10 suits image thumbnails, not word cards. |
| 42 | First-run empty state | Two buttons — *Connect to Anki*, *Add a word* — and nothing else. |

---

## 12. Approved Analyzer and library-view extension (2026-07-28)

The user approved this extension as one combined implementation rather than
one feature at a time. It supersedes original decisions 9, 13, 27, 28, and 29
only for the behavior listed here; the original table remains the historical
record of the dependency-free first implementation.

- Every word presentation receives an accessible three-dot menu for local
  edit/override, detail, favorite, and list membership. It intentionally
  contains no destructive quick action.
- Sorting expands to Korean, English, and Mongolian alphabetical order.
  Missing translated senses remain last in either direction.
- The small table toggle becomes a dedicated Anki-style **Browser** section:
  number/index, Anki/manual source, Korean, sentence form, English, Mongolian,
  note type, deck, stage/interval/due state, media, flags, sortable headers,
  row selection, and a right-side inspector.
- A second original presentation, **Hangul Atlas**, groups by Korean initial
  consonant and uses irregular constellation cards, mastery tint/glow, local
  image washes, hover/focus meaning reveal, responsive layout, and reduced
  motion. It copies no CodePen source or external asset.
- A new **Analyzer** follows the useful sentence → morphology → explanation
  workflow seen in Korean study products while keeping Keivotos's own visual
  identity, components, text, and rules. No Mirinae code, assets, branding,
  lesson copy, or proprietary output is copied.

The Analyzer is deliberately a hybrid instead of a hand-written morphology
engine:

- locked `kiwipiepy`/Kiwi handles sentence splitting, spans, morphemes, lemmas,
  and POS tags locally; Keivotos combines predicate groups into useful
  dictionary forms and renders friendly labels;
- deterministic Keivotos rules explain common particles, tense/honorific
  markers, connectors, adnominal/nominal endings, and derivational suffixes;
  raw Kiwi tags and source provenance remain visible instead of overstating
  certainty;
- locked `koroman` supplies Revised Romanization;
- effective local Anki/manual words are matched in one pass for English and
  Mongolian meanings, existing exact sentence translation, and local audio;
- the browser's installed Korean system voice is optional and creates no
  download;
- the National Institute of Korean Language's KRDICT API is optional. Its
  independent DPAPI-protected key enables only an explicit selected-lemma
  button. Requests use the fixed official HTTPS host, eight-second timeout,
  two-MiB response limit, English/Mongolian translated entries, and a
  disposable cache. Analysis and page load never contact it;
- pasted text is not retained automatically. Explicit saves land in additive
  `language_analyzer_saved` rows with editable EN/MN translation and
  soft-retirement; morphology and dictionary caches stay rebuildable in
  `language.sqlite`;
- selected lemmas can open an existing learned word or prefill the normal
  add-word composer. Nothing writes to Anki.

Packaging and licensing are part of the same approved scope:
`pyproject.toml`/`uv.lock`, Kiwi's PyInstaller binary/model/data collection,
the release license collector, third-party notices, and distribution guidance
all include the new runtime. No package, release, version bump, or Git
operation is authorized.

Verification adds Korean golden analyses, cache and provenance checks, exact
library/example matching, alphabetical missing-last ordering, precious-history
and secret-key preservation, explicit-network boundaries, API/OpenAPI and
frontend contracts, zero-warning check/build, the full Python regression, and
timed browser interaction for menu closure, sortable Browser/inspector,
Atlas focus/reduced motion, Analyzer token selection/long horizontal scroll,
history, composer prefill, and responsive layouts.
