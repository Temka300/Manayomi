<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import {
    languageApi,
    type LanguageWord,
  } from '../../lib/languageApi';

  export let words: LanguageWord[] = [];

  type Mode = 'ko_meaning' | 'meaning_ko' | 'audio_meaning' | 'cloze';
  const dispatch = createEventDispatcher<{ close: void }>();

  let mode: Mode = 'ko_meaning';
  let length = 20;
  let queue: LanguageWord[] = [];
  let index = 0;
  let revealed = false;
  let sessionId = '';
  let missed: LanguageWord[] = [];
  let complete = false;
  let starting = false;
  let error = '';
  let audio: HTMLAudioElement | null = null;

  $: current = queue[index] ?? null;
  $: eligible = mode === 'audio_meaning'
    ? words.filter((word) => word.media_by_role.word_audio)
    : mode === 'cloze'
      ? words.filter((word) => cloze(word) !== word.examples[0]?.sentence)
      : words;

  function shuffle(values: LanguageWord[]): LanguageWord[] {
    const result = [...values];
    for (let cursor = result.length - 1; cursor > 0; cursor -= 1) {
      const target = Math.floor(Math.random() * (cursor + 1));
      [result[cursor], result[target]] = [result[target], result[cursor]];
    }
    return result;
  }

  function meanings(word: LanguageWord): string {
    return word.senses.map((sense) => sense.text).join(' / ');
  }

  function cloze(word: LanguageWord): string {
    const sentence = word.examples[0]?.sentence ?? '';
    const target = sentence.includes(word.sentence_form)
      ? word.sentence_form
      : sentence.includes(word.headword)
        ? word.headword
        : '';
    return target ? sentence.replace(target, '＿＿＿') : sentence;
  }

  async function start(source = eligible) {
    if (!source.length) return;
    starting = true;
    error = '';
    try {
      queue = shuffle(source).slice(0, length);
      const response = await languageApi.practiceSession(
        mode,
        queue.map((word) => word.word_id),
        queue.length,
      );
      sessionId = response.session.session_id;
      index = 0;
      missed = [];
      revealed = false;
      complete = false;
      if (mode === 'audio_meaning') setTimeout(playAudio, 80);
    } catch (cause) {
      error = (cause as Error).message;
    } finally {
      starting = false;
    }
  }

  function playAudio() {
    if (!current?.media_by_role.word_audio) return;
    audio?.pause();
    audio = new Audio(languageApi.mediaUrl(current.word_id, 'word_audio'));
    void audio.play().catch(() => {
      error = 'Click replay to permit audio in this browser.';
    });
  }

  async function grade(correct: boolean) {
    if (!current || !revealed) return;
    const final = index === queue.length - 1;
    try {
      await languageApi.practiceAnswer(
        sessionId,
        current.word_id,
        correct,
        final,
      );
      if (!correct) missed = [...missed, current];
      if (final) {
        complete = true;
      } else {
        index += 1;
        revealed = false;
        if (mode === 'audio_meaning') setTimeout(playAudio, 80);
      }
    } catch (cause) {
      error = (cause as Error).message;
    }
  }

  function keydown(event: KeyboardEvent) {
    const element = event.target as HTMLElement | null;
    if (element?.matches('input, textarea, select')) return;
    if (event.key === 'Escape') dispatch('close');
    if (!sessionId || complete) return;
    if (event.code === 'Space') {
      event.preventDefault();
      if (revealed && mode === 'audio_meaning') playAudio();
      else revealed = true;
    }
    if (revealed && event.key === '1') void grade(true);
    if (revealed && event.key === '2') void grade(false);
  }
</script>

<svelte:window on:keydown={keydown} />

<div class="fixed inset-0 z-[112] flex flex-col bg-[#09090d] text-white">
  <header class="flex h-16 shrink-0 items-center gap-3 border-b border-white/8 px-4 sm:px-6">
    <button type="button" class="grid h-10 w-10 place-items-center rounded-full text-white/55 hover:bg-white/7" on:click={() => dispatch('close')} aria-label="Leave practice">←</button>
    <div class="flex-1">
      <p class="text-[10px] font-bold uppercase tracking-[0.2em] text-amber-300/65">Languages practice</p>
      <p class="text-sm text-white/45">{sessionId && !complete ? `${index + 1} / ${queue.length}` : 'Local self-grading'}</p>
    </div>
    {#if sessionId && !complete}<div class="h-1.5 w-28 overflow-hidden rounded-full bg-white/8 sm:w-48"><div class="h-full bg-amber-300 transition-all" style={`width:${((index + 1) / queue.length) * 100}%`}></div></div>{/if}
  </header>

  {#if !sessionId}
    <main class="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center p-6">
      <p class="text-xs font-semibold uppercase tracking-[0.22em] text-amber-300/60">Build from the wall</p>
      <h1 class="mt-2 text-4xl font-black">Practice {words.length} visible word{words.length === 1 ? '' : 's'}</h1>
      <p class="mt-3 max-w-xl text-sm leading-6 text-white/40">These results stay in Languages. They never alter Anki scheduling or the mastery meter.</p>
      <div class="mt-8 grid gap-3 sm:grid-cols-2">
        {#each [
          ['ko_meaning', 'Korean → meaning', 'See Hangul, recall English and Mongolian.'],
          ['meaning_ko', 'Meaning → Korean', 'See meanings, recall the Hangul.'],
          ['audio_meaning', 'Audio → meaning', 'Listen with the word hidden.'],
          ['cloze', 'Sentence cloze', 'Recall the missing sentence form.'],
        ] as value}
          <button type="button" class="rounded-2xl border p-4 text-left transition-colors {mode === value[0] ? 'border-amber-300/45 bg-amber-300/8' : 'border-white/8 bg-white/3 hover:border-white/15'}" on:click={() => mode = value[0] as Mode}>
            <strong class="block text-sm text-white/85">{value[1]}</strong>
            <span class="mt-1 block text-xs leading-5 text-white/35">{value[2]}</span>
          </button>
        {/each}
      </div>
      <div class="mt-6 flex flex-wrap items-center gap-3">
        <span class="text-xs text-white/35">Length</span>
        {#each [10, 20, 50] as value}<button type="button" class="rounded-full px-3 py-1.5 text-xs {length === value ? 'bg-amber-300 text-[#251a05]' : 'bg-white/6 text-white/45'}" on:click={() => length = value}>{value}</button>{/each}
        <button type="button" class="rounded-full px-3 py-1.5 text-xs {length === eligible.length ? 'bg-amber-300 text-[#251a05]' : 'bg-white/6 text-white/45'}" on:click={() => length = eligible.length}>All</button>
        <span class="ml-auto text-xs text-white/25">{eligible.length} eligible</span>
      </div>
      {#if error}<p class="mt-4 text-sm text-red-300">{error}</p>{/if}
      <button type="button" class="mt-8 rounded-2xl bg-amber-300 px-6 py-4 text-sm font-black text-[#251a05] hover:bg-amber-200 disabled:opacity-35" disabled={starting || !eligible.length} on:click={() => start()}>{starting ? 'Starting…' : 'Begin session'}</button>
    </main>
  {:else if complete}
    <main class="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center p-6">
      <p class="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-300/65">Session saved</p>
      <h1 class="mt-2 text-5xl font-black">{queue.length - missed.length} / {queue.length}</h1>
      <p class="mt-3 text-sm text-white/40">{missed.length ? 'Review the words that did not land this time.' : 'Clean run. Nicely remembered.'}</p>
      {#if missed.length}
        <div class="mt-8 grid gap-2 sm:grid-cols-2">
          {#each missed as word}<div class="rounded-xl border border-white/8 bg-white/3 px-4 py-3"><strong>{word.headword}</strong><span class="ml-3 text-xs text-white/35">{meanings(word)}</span></div>{/each}
        </div>
        <button type="button" class="mt-6 rounded-2xl bg-amber-300 px-6 py-3 text-sm font-bold text-[#251a05]" on:click={() => start(missed)}>Practice just these again</button>
      {/if}
      <button type="button" class="mt-3 rounded-2xl border border-white/10 px-6 py-3 text-sm text-white/60 hover:bg-white/5" on:click={() => dispatch('close')}>Return to words</button>
    </main>
  {:else if current}
    <main class="mx-auto flex w-full max-w-4xl flex-1 flex-col items-center justify-center p-6 text-center">
      <div class="w-full rounded-[2rem] border border-white/8 bg-[radial-gradient(circle_at_50%_0%,rgba(245,158,11,.11),transparent_45%),#111118] px-6 py-14 sm:px-14">
        {#if mode === 'ko_meaning'}
          <p class="text-5xl font-black sm:text-7xl">{current.headword}</p>
          {#if current.sentence_form !== current.headword}<p class="mt-3 text-lg text-amber-100/45">{current.sentence_form}</p>{/if}
        {:else if mode === 'meaning_ko'}
          <p class="text-2xl font-semibold leading-relaxed sm:text-4xl">{meanings(current)}</p>
        {:else if mode === 'audio_meaning'}
          <button type="button" class="mx-auto grid h-24 w-24 place-items-center rounded-full bg-amber-300 text-3xl text-[#251a05] hover:scale-105" on:click={playAudio} aria-label="Replay audio">▶</button>
          <p class="mt-5 text-sm text-white/30">Listen, then recall the meaning</p>
        {:else}
          <p class="text-2xl font-semibold leading-relaxed sm:text-4xl">{cloze(current)}</p>
        {/if}

        {#if revealed}
          <div class="mt-10 border-t border-white/8 pt-8">
            <p class="text-4xl font-black text-amber-100">{current.headword}</p>
            <p class="mt-3 text-lg text-white/55">{meanings(current)}</p>
            {#if current.examples[0]}<p class="mt-5 text-sm text-white/35">{current.examples[0].sentence}</p>{/if}
          </div>
        {:else}
          <button type="button" class="mt-12 rounded-full border border-white/12 px-6 py-3 text-sm text-white/60 hover:bg-white/5" on:click={() => revealed = true}>Reveal · Space</button>
        {/if}
      </div>
      {#if revealed}
        <div class="mt-6 grid w-full max-w-lg grid-cols-2 gap-3">
          <button type="button" class="rounded-2xl bg-emerald-400/15 px-5 py-4 font-semibold text-emerald-200 hover:bg-emerald-400/22" on:click={() => grade(true)}>1 · Knew it</button>
          <button type="button" class="rounded-2xl bg-red-400/12 px-5 py-4 font-semibold text-red-200 hover:bg-red-400/20" on:click={() => grade(false)}>2 · Didn’t</button>
        </div>
      {/if}
      {#if error}<p class="mt-4 text-sm text-red-300">{error}</p>{/if}
    </main>
  {/if}
</div>
