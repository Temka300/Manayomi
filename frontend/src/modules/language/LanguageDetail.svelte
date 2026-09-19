<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import {
    languageApi,
    type LanguageMediaRole,
    type LanguageWord,
  } from '../../lib/languageApi';
  import { languageAutoplay } from './stores';

  export let word: LanguageWord;

  const dispatch = createEventDispatcher<{
    close: void;
    edit: LanguageWord;
    changed: LanguageWord;
    previous: void;
    next: void;
  }>();

  let audio: HTMLAudioElement | null = null;
  let error = '';

  $: example = word.examples[0]?.sentence ?? '';
  $: target = example.includes(word.sentence_form)
    ? word.sentence_form
    : example.includes(word.headword)
      ? word.headword
      : '';
  $: targetIndex = target ? example.indexOf(target) : -1;
  $: grammar = word.notes_text.filter((note) => note.kind === 'grammar');

  function mediaUrl(role: LanguageMediaRole): string {
    return languageApi.mediaUrl(word.word_id, role);
  }

  async function playWord() {
    if (!word.media_by_role.word_audio) return;
    if (audio) audio.pause();
    audio = new Audio(mediaUrl('word_audio'));
    try {
      await audio.play();
    } catch {
      error = 'Audio playback needs a click in this browser.';
    }
  }

  async function toggleFavorite() {
    try {
      await languageApi.favorite(word.word_id, !word.favorite);
      word = { ...word, favorite: !word.favorite };
      dispatch('changed', word);
    } catch (cause) {
      error = (cause as Error).message;
    }
  }

  async function revert() {
    try {
      word = (await languageApi.revertOverrides(word.word_id)).word;
      dispatch('changed', word);
    } catch (cause) {
      error = (cause as Error).message;
    }
  }

  function keydown(event: KeyboardEvent) {
    const targetElement = event.target as HTMLElement | null;
    if (targetElement?.matches('input, textarea, select')) return;
    if (event.key === 'Escape') dispatch('close');
    if (event.key === 'ArrowLeft') dispatch('previous');
    if (event.key === 'ArrowRight') dispatch('next');
    if (event.code === 'Space') {
      event.preventDefault();
      void playWord();
    }
  }

  onMount(() => {
    if ($languageAutoplay) void playWord();
  });
</script>

<svelte:window on:keydown={keydown} />

<div class="fixed inset-0 z-[110] overflow-y-auto bg-[#09090d]/95 backdrop-blur-lg">
  <header class="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-white/8 bg-[#0c0c12]/92 px-4 backdrop-blur">
    <button type="button" class="detail-button" on:click={() => dispatch('close')} aria-label="Close detail">←</button>
    <div class="min-w-0 flex-1">
      <p class="truncate text-[10px] font-semibold uppercase tracking-[0.2em] text-amber-300/70">{word.deck || 'Keivotos'}</p>
      <h1 class="truncate text-lg font-bold text-white">{word.headword}</h1>
    </div>
    <button type="button" class="detail-button {word.favorite ? 'text-amber-300' : ''}" on:click={toggleFavorite} aria-label="Favorite">{word.favorite ? '★' : '☆'}</button>
    <button type="button" class="rounded-xl border border-amber-300/20 px-4 py-2 text-sm font-semibold text-amber-100 hover:bg-amber-300/8" on:click={() => dispatch('edit', word)}>Edit</button>
  </header>

  <main class="mx-auto grid min-h-[calc(100vh-4rem)] max-w-7xl gap-8 p-5 lg:grid-cols-[minmax(0,1.05fr)_minmax(22rem,.95fr)] lg:p-10">
    <section class="space-y-6">
      <div class="relative min-h-80 overflow-hidden rounded-3xl border border-white/8 bg-[radial-gradient(circle_at_20%_10%,rgba(245,158,11,.15),transparent_48%),#111118]">
        {#if word.media_by_role.image}
          <img class="absolute inset-0 h-full w-full object-cover opacity-25 blur-[1px]" src={mediaUrl('image')} alt="" />
          <div class="absolute inset-0 bg-gradient-to-t from-[#111118] via-[#111118]/35 to-transparent"></div>
        {/if}
        <div class="relative flex min-h-80 flex-col justify-end p-7 sm:p-10">
          <div class="mb-auto flex gap-2">
            {#if word.missing}<span class="detail-chip text-red-200">Missing in Anki</span>{/if}
            {#if word.suspended}<span class="detail-chip text-[var(--text-primary)]">Suspended</span>{/if}
            {#if word.edited}<button type="button" class="detail-chip text-sky-200 hover:bg-sky-300/10" on:click={revert}>Edited · revert</button>{/if}
            {#if word.possible_duplicate}<span class="detail-chip text-amber-200">Possible duplicate</span>{/if}
          </div>
          <p class="text-5xl font-black tracking-tight text-white sm:text-7xl">{word.headword}</p>
          {#if word.sentence_form !== word.headword}<p class="mt-2 text-xl text-amber-100/65">{word.sentence_form}</p>{/if}
          {#if word.reading}<p class="mt-1 text-sm text-white/35">{word.reading}</p>{/if}
          <div class="mt-7 flex flex-wrap gap-3">
            {#if word.media_by_role.word_audio}
              <button type="button" class="rounded-full bg-amber-300 px-5 py-2.5 text-sm font-bold text-[#251a05] hover:bg-amber-200" on:click={playWord}>▶ Word audio</button>
            {/if}
            {#if word.media_by_role.sentence_audio}
              <audio class="h-10 max-w-full" src={mediaUrl('sentence_audio')} controls></audio>
            {/if}
          </div>
        </div>
      </div>

      {#if example}
        <section class="rounded-3xl border border-white/8 bg-[var(--bg-elevated)] p-6 sm:p-8">
          <p class="text-[10px] font-semibold uppercase tracking-[0.22em] text-amber-300/60">In a sentence</p>
          <p class="mt-4 text-2xl font-medium leading-relaxed text-white">
            {#if targetIndex >= 0}
              {example.slice(0, targetIndex)}<mark class="rounded-lg bg-amber-300/18 px-1.5 py-1 text-amber-100">{target}</mark>{example.slice(targetIndex + target.length)}
            {:else}
              {example}
            {/if}
          </p>
          {#each word.examples[0].translations as translation}
            <p class="mt-3 border-l-2 border-white/8 pl-3 text-sm text-white/45"><span class="mr-2 text-[10px] font-bold uppercase text-white/25">{translation.lang}</span>{translation.text}</p>
          {/each}
        </section>
      {/if}
    </section>

    <section class="space-y-5">
      <section class="rounded-3xl border border-white/8 bg-[var(--bg-elevated)] p-6">
        <p class="text-[10px] font-semibold uppercase tracking-[0.22em] text-white/30">Meanings</p>
        <div class="mt-4 space-y-4">
          {#each word.senses as sense}
            <div class="grid grid-cols-[2.5rem_1fr] gap-3">
              <span class="pt-1 text-[10px] font-bold uppercase text-white/25">{sense.lang}</span>
              <p class="text-lg leading-relaxed {sense.lang === 'en' ? 'text-amber-50' : 'text-sky-100/70'}">{sense.text}</p>
            </div>
          {:else}
            <p class="text-sm text-white/30">No mapped meaning yet.</p>
          {/each}
        </div>
      </section>

      {#if grammar.length}
        <section class="rounded-3xl border border-amber-300/15 bg-amber-300/5 p-6">
          <p class="text-[10px] font-semibold uppercase tracking-[0.22em] text-amber-300/65">Grammar notes</p>
          {#each grammar as note}<p class="mt-4 whitespace-pre-wrap text-sm leading-7 text-amber-50/75">{note.body}</p>{/each}
        </section>
      {/if}

      <section class="rounded-3xl border border-white/8 bg-[var(--bg-elevated)] p-6">
        <p class="text-[10px] font-semibold uppercase tracking-[0.22em] text-white/30">Progress</p>
        <div class="mt-4 grid grid-cols-2 gap-3 text-sm">
          <div class="stat-box"><span>Stage</span><strong class="capitalize">{word.stage}</strong></div>
          <div class="stat-box"><span>Weakest interval</span><strong>{word.weakest_interval}d</strong></div>
          <div class="stat-box"><span>Cards</span><strong>{word.progress.length}</strong></div>
          <div class="stat-box"><span>Last reviewed</span><strong>{word.last_reviewed_at ? new Date(word.last_reviewed_at).toLocaleDateString() : '—'}</strong></div>
        </div>
        <div class="mt-5 h-1.5 overflow-hidden rounded-full bg-white/8">
          <div class="h-full rounded-full transition-all {word.stage === 'mature' ? 'bg-emerald-400' : word.stage === 'young' ? 'bg-sky-400' : word.stage === 'learning' ? 'bg-amber-400' : 'bg-slate-500'}" style={`width:${Math.min(100, word.weakest_interval / 21 * 100)}%`}></div>
        </div>
        <p class="mt-4 text-xs text-white/35">Local practice: {word.practice.answers ? `${Math.round((word.practice.accuracy ?? 0) * 100)}% across ${word.practice.answers} answers` : 'No answers yet'}</p>
      </section>

      {#if word.personal_note}
        <section class="rounded-3xl border border-sky-300/12 bg-sky-300/5 p-6">
          <p class="text-[10px] font-semibold uppercase tracking-[0.22em] text-sky-200/55">Your note</p>
          <p class="mt-3 whitespace-pre-wrap text-sm leading-6 text-sky-50/70">{word.personal_note}</p>
        </section>
      {/if}

      {#if word.tags.length}
        <div class="flex flex-wrap gap-2">{#each word.tags as tag}<span class="rounded-full border border-white/8 bg-white/4 px-3 py-1 text-xs text-white/40">{tag}</span>{/each}</div>
      {/if}

      {#if error}<p class="text-xs text-red-300">{error}</p>{/if}
      <p class="pb-8 text-[11px] leading-5 text-white/20">← / → move · Space replays word audio · Esc closes · Anki remains the only scheduler</p>
    </section>
  </main>
</div>

<style>
  .detail-button { display:grid; height:2.5rem; width:2.5rem; place-items:center; border-radius:999px; color:rgba(255,255,255,.55); }
  .detail-button:hover { background:rgba(255,255,255,.07); color:white; }
  .detail-chip { border:1px solid rgba(255,255,255,.1); border-radius:999px; background:rgba(0,0,0,.25); padding:.35rem .65rem; font-size:.65rem; font-weight:600; }
  .stat-box { display:flex; flex-direction:column; gap:.25rem; border-radius:.8rem; background:rgba(0,0,0,.2); padding:.8rem; }
  .stat-box span { color:rgba(255,255,255,.3); font-size:.65rem; text-transform:uppercase; letter-spacing:.08em; }
  .stat-box strong { color:rgba(255,255,255,.75); font-weight:600; }
</style>
