<script lang="ts">
  import { createEventDispatcher, tick } from 'svelte';
  import type { SubtitleCue, SubtitleTrack } from '../../lib/media';

  export let tracks: SubtitleTrack[] = [];
  export let selectedTrackId: string | null = null;
  export let currentTime = 0;
  export let offset = 0;
  export let title = 'Subtitles & lyrics';
  export let accent = '#67e8f9';
  export let performanceMode = false;
  export let showTranslations = true;
  export let loopCue: SubtitleCue | null = null;

  const dispatch = createEventDispatcher<{
    close: void;
    select: string;
    seek: number;
    offset: number;
    loop: SubtitleCue | null;
  }>();

  let transcript: HTMLDivElement;
  let lastActiveIndex = -1;
  let followEnabled = true;

  $: selectedTrack = selectedTrackId !== null
    ? (tracks.find((track) => track.track_id === selectedTrackId) ?? tracks[0] ?? null)
    : null;
  $: selectedCues = selectedTrack?.cues ?? [];
  $: adjustedTime = currentTime + offset;
  $: activeIndex = selectedCues.findIndex(
    (cue) => adjustedTime >= cue.start && adjustedTime < cue.end,
  );
  $: activeCue = activeIndex >= 0 ? selectedCues[activeIndex] : null;
  $: nextCue = activeIndex >= 0
    ? selectedCues[activeIndex + 1] ?? null
    : selectedCues[0] ?? null;
  $: if (activeIndex !== lastActiveIndex) {
    lastActiveIndex = activeIndex;
    void scrollActive();
  }

  async function scrollActive(): Promise<void> {
    if (!followEnabled) return;
    await tick();
    transcript
      ?.querySelector<HTMLElement>('[aria-current="true"]')
      ?.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }

  function setOffset(value: number): void {
    const next = Math.max(-30, Math.min(30, Math.round(value * 10) / 10));
    dispatch('offset', next);
  }
</script>

<aside
  class="subtitle-panel absolute inset-y-0 left-0 z-40 flex w-[min(480px,96vw)] flex-col border-r border-white/10 bg-[#07090d]/95 shadow-2xl backdrop-blur-xl"
  aria-label={title}
  data-player-control-stop
  style={`--panel-accent:${accent}`}
>
  <header class="flex items-center gap-3 border-b border-white/10 px-4 py-4">
    <div class="min-w-0 flex-1">
      <h2 class="text-lg font-semibold text-white">{title}</h2>
      <p class="truncate text-xs text-white/50">
        {selectedTrack?.label ?? 'No local subtitle attached'}
      </p>
    </div>
    <button
      type="button"
      class="rounded-full border px-3 py-2 text-xs font-semibold {followEnabled ? 'active-control' : 'border-white/10 text-white/45'}"
      aria-pressed={followEnabled}
      on:click={() => {
        followEnabled = !followEnabled;
        if (followEnabled) void scrollActive();
      }}
    >Follow</button>
    <button
      type="button"
      class="grid h-10 w-10 place-items-center rounded-full text-xl text-white/70 hover:bg-white/10 hover:text-white focus-visible:outline focus-visible:outline-2"
      aria-label={`Close ${title.toLowerCase()}`}
      title={`Close ${title.toLowerCase()}`}
      on:click={() => dispatch('close')}
    >×</button>
  </header>

  {#if tracks.length > 1}
    <label class="mx-4 mt-4 block text-xs font-semibold uppercase tracking-[0.16em] text-white/45">
      Track
      <select
        class="mt-2 w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm normal-case tracking-normal text-white outline-none"
        value={selectedTrack?.track_id ?? ''}
        on:change={(event) => dispatch('select', event.currentTarget.value)}
      >
        {#each tracks as track}
          <option value={track.track_id}>{track.label} · {track.format.toUpperCase()}</option>
        {/each}
      </select>
    </label>
  {/if}

  <section class="active-summary mx-4 mt-4 rounded-2xl border p-4 {performanceMode ? 'performance' : ''}">
    <p class="min-h-8 font-semibold leading-relaxed {performanceMode ? 'text-3xl' : 'text-lg'}">
      {activeCue?.text ?? 'Subtitles will follow playback'}
    </p>
    {#if activeCue?.romaji}
      <p class="mt-2 text-sm leading-relaxed text-fuchsia-100/70">{activeCue.romaji}</p>
    {/if}
    {#if showTranslations && activeCue?.translation}
      <p class="mt-2 text-sm leading-relaxed text-white/55">{activeCue.translation}</p>
    {/if}
    {#if nextCue}
      <p class="mt-3 line-clamp-2 leading-relaxed text-white/45 {performanceMode ? 'text-xl' : 'text-sm'}">
        <span class="mr-2 text-[10px] font-bold uppercase tracking-widest text-white/25">Next</span>{nextCue.text}
      </p>
    {/if}
  </section>

  <div class="mx-4 mt-3 flex items-center gap-2 rounded-xl bg-white/5 px-3 py-2 text-xs text-white/60">
    <span class="mr-auto">Timing {offset >= 0 ? '+' : ''}{offset.toFixed(1)}s</span>
    <button type="button" class="rounded-lg px-2 py-1 hover:bg-white/10" on:click={() => setOffset(offset - 0.1)} aria-label="Subtitles earlier">−0.1</button>
    <button type="button" class="rounded-lg px-2 py-1 hover:bg-white/10" on:click={() => setOffset(0)}>Reset</button>
    <button type="button" class="rounded-lg px-2 py-1 hover:bg-white/10" on:click={() => setOffset(offset + 0.1)} aria-label="Subtitles later">+0.1</button>
  </div>

  <div bind:this={transcript} class="mt-3 min-h-0 flex-1 overflow-y-auto px-3 pb-8">
    {#if selectedCues.length}
      <div class="space-y-1">
        {#each selectedCues as cue, index (`${cue.start}:${cue.end}:${index}`)}
          <div class="group relative">
            <button
              type="button"
              class="block w-full rounded-xl px-3 py-3 pr-11 text-left transition {index === activeIndex ? 'active-line' : 'text-white/55 hover:bg-white/5 hover:text-white'}"
              aria-current={index === activeIndex ? 'true' : undefined}
              on:click={() => dispatch('seek', Math.max(0, cue.start - offset))}
            >
              <span class="mr-3 inline-block w-11 align-top text-[11px] tabular-nums text-white/30">
                {Math.floor(cue.start / 60)}:{String(Math.floor(cue.start % 60)).padStart(2, '0')}
              </span>
              <span class="inline-block max-w-[calc(100%-4rem)] whitespace-pre-line text-sm leading-6">{cue.text}</span>
              {#if cue.romaji}<span class="ml-14 mt-1 block text-xs leading-5 text-fuchsia-100/55">{cue.romaji}</span>{/if}
              {#if showTranslations && cue.translation}<span class="ml-14 mt-1 block text-xs leading-5 text-white/35">{cue.translation}</span>{/if}
            </button>
            <button
              type="button"
              class="absolute right-2 top-2 grid h-8 w-8 place-items-center rounded-lg text-xs opacity-45 hover:bg-white/10 hover:opacity-100 focus:opacity-100 {loopCue === cue ? 'active-control' : ''}"
              aria-label={loopCue === cue ? 'Stop looping this line' : 'Loop this line'}
              aria-pressed={loopCue === cue}
              on:click={() => dispatch('loop', loopCue === cue ? null : cue)}
            >↻</button>
          </div>
        {/each}
      </div>
    {:else if selectedTrack}
      <div class="grid h-full place-items-center px-6 text-center">
        <div>
          <p class="text-base font-medium text-white/70">Native subtitle track</p>
          <p class="mt-2 text-sm leading-6 text-white/40">
            This local track is rendered over the video. A parsed cue list is not available for the interactive transcript.
          </p>
        </div>
      </div>
    {:else}
      <div class="grid h-full place-items-center px-6 text-center">
        <div>
          <p class="text-base font-medium text-white/70">No subtitle attached</p>
          <p class="mt-2 text-sm leading-6 text-white/40">Attach ASS, SSA, SRT, VTT, or LRC from the player menu.</p>
        </div>
      </div>
    {/if}
  </div>
</aside>

<style>
  .active-control {
    border-color: color-mix(in srgb, var(--panel-accent) 45%, transparent);
    background: color-mix(in srgb, var(--panel-accent) 14%, transparent);
    color: color-mix(in srgb, var(--panel-accent) 80%, white);
  }

  .active-summary {
    border-color: color-mix(in srgb, var(--panel-accent) 18%, transparent);
    background: color-mix(in srgb, var(--panel-accent) 6%, transparent);
    color: color-mix(in srgb, var(--panel-accent) 72%, white);
  }

  .active-summary.performance {
    min-height: 13rem;
    display: flex;
    flex-direction: column;
    justify-content: center;
  }

  .active-line {
    background: color-mix(in srgb, var(--panel-accent) 12%, transparent);
    color: color-mix(in srgb, var(--panel-accent) 75%, white);
  }
</style>
