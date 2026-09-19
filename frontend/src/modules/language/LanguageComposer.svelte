<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import {
    fileToBase64,
    languageApi,
    type LanguageMediaRole,
    type LanguageWord,
    type ManualWordInput,
  } from '../../lib/languageApi';

  export let word: LanguageWord | null = null;
  export let draft: Partial<ManualWordInput> | null = null;

  const dispatch = createEventDispatcher<{
    close: void;
    saved: LanguageWord;
    retired: string;
  }>();

  let headword = word?.headword ?? draft?.headword ?? '';
  let sentenceForm = word?.sentence_form ?? draft?.sentence_form ?? '';
  let reading = word?.reading ?? draft?.reading ?? '';
  let deck = word?.deck ?? draft?.deck ?? 'Keivotos';
  let sortIndex = (word?.sort_index ?? draft?.sort_index) === null
    || (word?.sort_index ?? draft?.sort_index) === undefined
    ? ''
    : String(word?.sort_index ?? draft?.sort_index);
  let english = word?.senses.find((sense) => sense.lang === 'en')?.text
    ?? draft?.senses?.find((sense) => sense.lang === 'en')?.text
    ?? '';
  let mongolian = word?.senses.find((sense) => sense.lang === 'mn')?.text
    ?? draft?.senses?.find((sense) => sense.lang === 'mn')?.text
    ?? '';
  let example = word?.examples[0]?.sentence ?? draft?.examples?.[0]?.sentence ?? '';
  let exampleEnglish =
    word?.examples[0]?.translations.find((value) => value.lang === 'en')?.text
    ?? draft?.examples?.[0]?.translations.find((value) => value.lang === 'en')?.text
    ?? '';
  let exampleMongolian =
    word?.examples[0]?.translations.find((value) => value.lang === 'mn')?.text
    ?? draft?.examples?.[0]?.translations.find((value) => value.lang === 'mn')?.text
    ?? '';
  let grammar =
    word?.notes_text.find((value) => value.kind === 'grammar')?.body
    ?? draft?.notes_text?.find((value) => value.kind === 'grammar')?.body
    ?? '';
  let tags = word?.tags.join(', ') ?? draft?.tags?.join(', ') ?? '';
  let personalNote = word?.personal_note ?? draft?.personal_note ?? '';
  let mediaFiles: Partial<Record<LanguageMediaRole, File>> = {};
  let advanced = Boolean(grammar || reading || tags);
  let saving = false;
  let error = '';
  let draggingRole: LanguageMediaRole | null = null;

  function payload(): ManualWordInput {
    const senses = [
      ...(english.trim() ? [{ lang: 'en', text: english.trim() }] : []),
      ...(mongolian.trim() ? [{ lang: 'mn', text: mongolian.trim() }] : []),
    ];
    const translations = [
      ...(exampleEnglish.trim()
        ? [{ lang: 'en', text: exampleEnglish.trim() }]
        : []),
      ...(exampleMongolian.trim()
        ? [{ lang: 'mn', text: exampleMongolian.trim() }]
        : []),
    ];
    return {
      lang: 'ko',
      headword: headword.trim(),
      sentence_form: sentenceForm.trim(),
      reading: reading.trim(),
      deck: deck.trim() || 'Keivotos',
      sort_index: sortIndex.trim() ? Number(sortIndex) : null,
      senses,
      examples: example.trim()
        ? [{ sentence: example.trim(), translations }]
        : [],
      notes_text: grammar.trim()
        ? [{ kind: 'grammar', body: grammar.trim() }]
        : [],
      tags: tags.split(',').map((value) => value.trim()).filter(Boolean),
      personal_note: personalNote.trim(),
    };
  }

  async function save() {
    if (!headword.trim() || saving) return;
    saving = true;
    error = '';
    try {
      let saved = word
        ? (await languageApi.updateWord(word.word_id, payload())).word
        : (await languageApi.createWord(payload())).word;
      for (const [role, file] of Object.entries(mediaFiles)) {
        if (!file) continue;
        await languageApi.attachMedia(
          saved.word_id,
          role as LanguageMediaRole,
          file.name,
          await fileToBase64(file),
        );
      }
      if (Object.keys(mediaFiles).length) {
        saved = (await languageApi.word(saved.word_id)).word;
      }
      dispatch('saved', saved);
    } catch (cause) {
      error = (cause as Error).message;
    } finally {
      saving = false;
    }
  }

  async function retire() {
    if (!word || word.source !== 'manual' || saving) return;
    if (!window.confirm(`Retire “${word.headword}”? Its authored record and media bytes will be preserved.`)) return;
    saving = true;
    error = '';
    try {
      await languageApi.retireWord(word.word_id);
      dispatch('retired', word.word_id);
    } catch (cause) {
      error = (cause as Error).message;
      saving = false;
    }
  }

  function pick(role: LanguageMediaRole, files: FileList | null) {
    const file = files?.[0];
    if (file) mediaFiles = { ...mediaFiles, [role]: file };
    draggingRole = null;
  }

  function drop(event: DragEvent, role: LanguageMediaRole) {
    event.preventDefault();
    pick(role, event.dataTransfer?.files ?? null);
  }
</script>

<div class="fixed inset-0 z-[115] flex justify-end bg-black/65 backdrop-blur-sm" role="presentation" on:click|self={() => dispatch('close')}>
  <aside
    class="language-sheet h-full w-full max-w-xl overflow-y-auto border-l border-amber-300/15 bg-[#101015] shadow-2xl shadow-black/70"
    aria-label={word ? 'Edit Languages word' : 'Add Languages word'}
  >
    <header class="sticky top-0 z-10 flex items-center justify-between border-b border-white/8 bg-[#101015]/95 px-5 py-4 backdrop-blur">
      <div>
        <p class="text-[10px] font-semibold uppercase tracking-[0.22em] text-amber-300">{word ? 'Edit word' : 'New word'}</p>
        <h2 class="mt-1 text-xl font-bold text-white">{word?.headword ?? 'Add to your library'}</h2>
      </div>
      <button type="button" class="grid h-9 w-9 place-items-center rounded-full text-white/50 hover:bg-white/8 hover:text-white" on:click={() => dispatch('close')} aria-label="Close">✕</button>
    </header>

    <form class="space-y-6 p-5" on:submit|preventDefault={save}>
      {#if word?.source === 'anki'}
        <div class="rounded-xl border border-sky-300/15 bg-sky-400/7 px-4 py-3 text-xs leading-5 text-sky-100/75">
          This is an Anki mirror. Your edits are stored as local overrides and never sent to Anki.
        </div>
      {/if}

      <section class="space-y-3">
        <h3 class="text-xs font-semibold uppercase tracking-[0.18em] text-white/35">Word</h3>
        <div class="grid gap-3 sm:grid-cols-3">
          <label class="sm:col-span-1">
            <span class="mb-1 block text-xs text-white/45">Headword</span>
            <input class="language-input" bind:value={headword} required placeholder="축하하다" />
          </label>
          <label>
            <span class="mb-1 block text-xs text-white/45">Sentence form</span>
            <input class="language-input" bind:value={sentenceForm} placeholder="축하해요" />
          </label>
          <label>
            <span class="mb-1 block text-xs text-white/45">Reading</span>
            <input class="language-input" bind:value={reading} placeholder="Optional" />
          </label>
        </div>
      </section>

      <section class="space-y-3">
        <div class="flex items-center justify-between">
          <h3 class="text-xs font-semibold uppercase tracking-[0.18em] text-white/35">Senses</h3>
          <span class="text-[10px] text-white/25">English first · Mongolian second</span>
        </div>
        <label>
          <span class="mb-1 block text-xs font-semibold text-amber-100/65">EN</span>
          <textarea class="language-input min-h-20 resize-y" bind:value={english} placeholder="to congratulate"></textarea>
        </label>
        <label>
          <span class="mb-1 block text-xs font-semibold text-sky-100/65">MN</span>
          <textarea class="language-input min-h-20 resize-y" bind:value={mongolian} placeholder="Баяр хүргэх"></textarea>
        </label>
      </section>

      <section class="space-y-3">
        <h3 class="text-xs font-semibold uppercase tracking-[0.18em] text-white/35">Example</h3>
        <textarea class="language-input min-h-20 resize-y" bind:value={example} placeholder="생일 축하해요!"></textarea>
        {#if example && (sentenceForm || headword)}
          <p class="rounded-xl border border-amber-300/10 bg-amber-300/5 px-3 py-2 text-sm text-white/65">
            Preview:
            {#if example.includes(sentenceForm || headword)}
              {example.slice(0, example.indexOf(sentenceForm || headword))}<mark class="rounded bg-amber-300/20 px-1 text-amber-100">{sentenceForm || headword}</mark>{example.slice(example.indexOf(sentenceForm || headword) + (sentenceForm || headword).length)}
            {:else}
              {example}
            {/if}
          </p>
        {/if}
        <div class="grid gap-3 sm:grid-cols-2">
          <input class="language-input" bind:value={exampleEnglish} placeholder="English translation" />
          <input class="language-input" bind:value={exampleMongolian} placeholder="Mongolian translation" />
        </div>
      </section>

      <section class="space-y-3">
        <h3 class="text-xs font-semibold uppercase tracking-[0.18em] text-white/35">Media</h3>
        <div class="grid gap-3 sm:grid-cols-3">
          {#each [
            ['word_audio', 'Word audio', 'audio/*'],
            ['sentence_audio', 'Sentence audio', 'audio/*'],
            ['image', 'Image', 'image/*'],
          ] as slot}
            <label
              class="flex min-h-28 cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed p-3 text-center transition-colors {draggingRole === slot[0] ? 'border-amber-300 bg-amber-300/8' : 'border-white/12 bg-black/15 hover:border-amber-300/35'}"
              on:dragover|preventDefault={() => draggingRole = slot[0] as LanguageMediaRole}
              on:dragleave={() => draggingRole = null}
              on:drop={(event) => drop(event, slot[0] as LanguageMediaRole)}
            >
              <span class="text-xl text-amber-200/65">{slot[0] === 'image' ? '▧' : '♪'}</span>
              <span class="mt-1 text-xs font-semibold text-white/65">{slot[1]}</span>
              <span class="mt-1 max-w-full truncate text-[10px] text-white/30">
                {mediaFiles[slot[0] as LanguageMediaRole]?.name ?? word?.media_by_role[slot[0] as LanguageMediaRole]?.origin_filename ?? 'Drop or choose'}
              </span>
              <input class="sr-only" type="file" accept={slot[2]} on:change={(event) => pick(slot[0] as LanguageMediaRole, event.currentTarget.files)} />
            </label>
          {/each}
        </div>
      </section>

      <button type="button" class="flex w-full items-center justify-between rounded-xl border border-white/8 px-4 py-3 text-sm text-white/55 hover:bg-white/4" on:click={() => advanced = !advanced}>
        <span>Grammar, tags, deck and notes</span><span>{advanced ? '−' : '+'}</span>
      </button>

      {#if advanced}
        <section class="space-y-3">
          <textarea class="language-input min-h-28 resize-y" bind:value={grammar} placeholder="Grammar notes"></textarea>
          <input class="language-input" bind:value={tags} placeholder="Tags, comma separated" />
          <div class="grid gap-3 sm:grid-cols-[1fr_8rem]">
            <input class="language-input" bind:value={deck} placeholder="Deck" />
            <input class="language-input" bind:value={sortIndex} type="number" placeholder="Index" />
          </div>
          <textarea class="language-input min-h-24 resize-y" bind:value={personalNote} placeholder="Your private note"></textarea>
        </section>
      {/if}

      {#if error}<p class="rounded-xl border border-red-400/20 bg-red-400/8 px-4 py-3 text-sm text-red-200">{error}</p>{/if}

      <footer class="flex items-center gap-3 border-t border-white/8 pt-5">
        {#if word?.source === 'manual'}
          <button type="button" class="rounded-xl border border-red-400/20 px-4 py-2.5 text-sm text-red-200 hover:bg-red-400/8" on:click={retire} disabled={saving}>Retire</button>
        {/if}
        <span class="flex-1"></span>
        <button type="button" class="rounded-xl px-4 py-2.5 text-sm text-white/50 hover:bg-white/5" on:click={() => dispatch('close')}>Cancel</button>
        <button type="submit" class="rounded-xl bg-amber-300 px-5 py-2.5 text-sm font-bold text-[#251a05] hover:bg-amber-200 disabled:opacity-40" disabled={saving || !headword.trim()}>{saving ? 'Saving…' : 'Save word'}</button>
      </footer>
    </form>
  </aside>
</div>

<style>
  .language-sheet { animation: language-sheet-in 220ms cubic-bezier(.2,.8,.2,1); }
  .language-input {
    width: 100%;
    border: 1px solid rgba(255,255,255,.1);
    border-radius: .75rem;
    background: rgba(0,0,0,.22);
    padding: .65rem .8rem;
    color: white;
    font-size: .875rem;
    outline: none;
  }
  .language-input:focus { border-color: rgba(251,191,36,.55); }
  @keyframes language-sheet-in { from { transform: translateX(100%); } to { transform: translateX(0); } }
</style>
