<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { focusTrap } from '../../lib/focusTrap';
  import {
    youtubeApi,
    type YouTubeInspection,
    type YouTubePlan,
  } from '../../lib/youtubeApi';
  import { youtubeDownloadDefaults } from './settings';

  export let item: YouTubeInspection;
  export let karaokeIntent = false;

  const dispatch = createEventDispatcher<{
    close: void;
    started: {
      planToken: string;
      selectionSha256: string;
      authorized: boolean;
    };
  }>();

  const preferredResolution = Number($youtubeDownloadDefaults.resolution);
  let resolution = $youtubeDownloadDefaults.resolution === 'highest'
    || item.available_resolutions.includes(preferredResolution)
    ? $youtubeDownloadDefaults.resolution
    : item.available_resolutions.includes(1080)
      ? '1080'
      : String(item.available_resolutions.at(-1) ?? 'highest');
  let compatibility = $youtubeDownloadDefaults.compatibility;
  let audioFormat = $youtubeDownloadDefaults.audioFormat;
  let audioQuality = $youtubeDownloadDefaults.audioQuality;
  let selectedLanguages: string[] = [];
  let automaticCaptions = $youtubeDownloadDefaults.automaticCaptions;
  const audioFormatOptions = ['none', 'best', 'm4a', 'opus', 'mp3'] as const;
  let plan: YouTubePlan | null = null;
  let planning = false;
  let authorized = false;
  let error = '';

  const LANGUAGE_PRIORITY = ['ja', 'en', 'ko'];
  function languageOrder(left: string, right: string): number {
    const leftBase = left.split('-')[0].toLowerCase();
    const rightBase = right.split('-')[0].toLowerCase();
    const leftRank = LANGUAGE_PRIORITY.indexOf(leftBase);
    const rightRank = LANGUAGE_PRIORITY.indexOf(rightBase);
    if (leftRank !== rightRank) {
      return (leftRank < 0 ? 99 : leftRank) - (rightRank < 0 ? 99 : rightRank);
    }
    return left.localeCompare(right);
  }
  $: manualLanguages = Object.keys(item.subtitles).sort(languageOrder);
  $: autoLanguages = Object.keys(item.automatic_captions).sort(languageOrder);
  $: resolutionOptions = [
    ...item.available_resolutions
      .filter((value) => [480, 720, 1080, 1440, 2160].includes(value))
      .map(String),
    'highest',
  ];

  function toggleLanguage(language: string) {
    selectedLanguages = selectedLanguages.includes(language)
      ? selectedLanguages.filter((value) => value !== language)
      : [...selectedLanguages, language].slice(0, 10);
  }

  async function createPlan() {
    planning = true;
    plan = null;
    authorized = false;
    error = '';
    try {
      plan = (await youtubeApi.plan({
        video_id: item.video_id,
        resolution,
        compatibility,
        audio_format: audioFormat,
        audio_quality: audioQuality,
        subtitle_languages: selectedLanguages,
        automatic_captions: automaticCaptions,
        karaoke_intent: karaokeIntent,
        browser_session: $youtubeDownloadDefaults.browserSession,
      })).plan;
    } catch (cause) {
      error = (cause as Error).message;
    } finally {
      planning = false;
    }
  }

  function confirm() {
    if (!plan || !authorized) return;
    dispatch('started', {
      planToken: plan.token,
      selectionSha256: plan.selection_sha256,
      authorized,
    });
  }

  function bytes(value: number | null): string {
    if (!value) return 'Unknown before transfer';
    const units = ['B', 'KiB', 'MiB', 'GiB'];
    let amount = value;
    let index = 0;
    while (amount >= 1024 && index < units.length - 1) {
      amount /= 1024;
      index += 1;
    }
    return `${amount.toFixed(index ? 1 : 0)} ${units[index]}`;
  }
</script>

<div class="fixed inset-0 z-[95] flex justify-end bg-black/70 backdrop-blur-sm" role="presentation" on:click={(event) => { if (event.target === event.currentTarget) dispatch('close'); }}>
  <aside class="h-full w-full max-w-xl overflow-y-auto border-l border-white/10 bg-[#121212] text-white shadow-2xl" aria-label="YouTube download options" tabindex="-1" use:focusTrap={{ close: () => dispatch('close') }}>
    <header class="sticky top-0 z-10 flex items-center gap-3 border-b border-white/10 bg-[#121212]/95 px-5 py-4 backdrop-blur">
      <button type="button" class="grid h-10 w-10 place-items-center rounded-full hover:bg-white/10" on:click={() => dispatch('close')} aria-label="Close download options">×</button>
      <div class="min-w-0 flex-1">
        <p class="text-xs font-semibold uppercase tracking-[0.18em] text-red-400">Local acquisition</p>
        <h2 class="truncate font-semibold">{item.title}</h2>
      </div>
    </header>

    <div class="space-y-6 p-5">
      {#if karaokeIntent}
        <div class="rounded-2xl border border-cyan-300/20 bg-cyan-300/7 p-4 text-sm leading-6 text-cyan-100">
          Karaoke fallback is active. Video is mandatory, and the completed Files asset can be added to Karaoke.
        </div>
      {/if}

      <section>
        <h3 class="text-sm font-semibold">Video quality</h3>
        <div class="mt-3 grid grid-cols-3 gap-2">
          {#each resolutionOptions as value}
            <button type="button" class="rounded-xl border px-3 py-3 text-sm font-semibold {resolution === value ? 'border-red-500 bg-red-500 text-white' : 'border-white/10 bg-white/4 text-white/65 hover:bg-white/8'}" on:click={() => { resolution = value; plan = null; }}>
              {value === 'highest' ? 'Highest' : `${value}p`}
            </button>
          {/each}
        </div>
        <label class="mt-3 flex items-start gap-3 rounded-xl bg-white/4 p-3 text-sm">
          <input class="mt-1 accent-red-500" type="checkbox" bind:checked={compatibility} on:change={() => plan = null} />
          <span><strong>Prefer compatible MP4</strong><span class="mt-1 block text-xs leading-5 text-white/40">Choose H.264/AAC when reported. Turn off to prefer the highest source codec/container.</span></span>
        </label>
      </section>

      <section>
        <h3 class="text-sm font-semibold">Optional companion audio</h3>
        <div class="mt-3 grid grid-cols-3 gap-2">
          {#each audioFormatOptions as value}
            <button type="button" class="rounded-xl border px-3 py-3 text-sm uppercase {audioFormat === value ? 'border-red-500 bg-red-500/15 text-red-100' : 'border-white/10 text-white/55 hover:bg-white/5'}" on:click={() => { audioFormat = value; plan = null; }}>{value}</button>
          {/each}
        </div>
        {#if audioFormat !== 'none'}
          <label class="mt-3 block text-xs font-semibold uppercase tracking-wider text-white/40">
            Conversion quality
            <select class="mt-2 w-full rounded-xl border border-white/10 bg-white/5 px-3 py-3 text-sm normal-case tracking-normal text-white" bind:value={audioQuality} on:change={() => plan = null}>
              <option value="128K">128 kbps</option>
              <option value="192K">192 kbps</option>
              <option value="320K">320 kbps</option>
            </select>
          </label>
        {/if}
      </section>

      <section>
        <h3 class="text-sm font-semibold">Subtitles and captions</h3>
        {#if $youtubeDownloadDefaults.browserSession !== 'none'}
          <p class="mt-3 rounded-xl border border-amber-300/15 bg-amber-300/6 px-3 py-2 text-xs leading-5 text-amber-100/75">This plan may read the local {$youtubeDownloadDefaults.browserSession} YouTube session to reduce anonymous rate limits. Keivotos does not store the cookies.</p>
        {/if}
        {#if manualLanguages.length}
          <p class="mt-3 text-xs font-semibold uppercase tracking-wider text-white/35">Manual subtitles</p>
          <div class="mt-2 flex flex-wrap gap-2">
            {#each manualLanguages as language}
              <button type="button" class="rounded-full border px-3 py-2 text-xs {selectedLanguages.includes(language) ? 'border-cyan-300 bg-cyan-300 text-black' : 'border-white/10 text-white/55'}" on:click={() => { toggleLanguage(language); plan = null; }}>{language}</button>
            {/each}
          </div>
        {/if}
        {#if autoLanguages.length}
          <label class="mt-4 flex items-start gap-3 rounded-xl bg-amber-300/6 p-3 text-sm">
            <input class="mt-1 accent-amber-400" type="checkbox" bind:checked={automaticCaptions} on:change={() => plan = null} />
            <span><strong>Include automatic captions</strong><span class="mt-1 block text-xs leading-5 text-white/40">Automatic captions are not guaranteed to be accurate or syllable-timed karaoke lyrics.</span></span>
          </label>
          {#if automaticCaptions}
            <div class="mt-2 flex max-h-36 flex-wrap gap-2 overflow-y-auto">
              {#each autoLanguages as language}
                <button type="button" class="rounded-full border px-3 py-2 text-xs {selectedLanguages.includes(language) ? 'border-amber-300 bg-amber-300 text-black' : 'border-white/10 text-white/55'}" on:click={() => { toggleLanguage(language); plan = null; }}>{language}</button>
              {/each}
            </div>
          {/if}
        {/if}
        {#if !manualLanguages.length && !autoLanguages.length}<p class="mt-3 text-sm text-white/40">No subtitle tracks were reported.</p>{/if}
      </section>

      {#if error}<div class="rounded-xl border border-red-400/20 bg-red-400/10 p-3 text-sm text-red-100">{error}</div>{/if}

      {#if !plan}
        <button type="button" class="w-full rounded-full bg-red-600 py-3.5 text-sm font-bold hover:bg-red-500 disabled:opacity-40" on:click={createPlan} disabled={planning}>{planning ? 'Inspecting selected formats…' : 'Review download plan'}</button>
      {:else}
        <section class="rounded-2xl border border-white/10 bg-white/4 p-4">
          <div class="flex items-center justify-between gap-3">
            <h3 class="font-semibold">{plan.display_quality}</h3>
            <span class="text-sm text-white/45">{bytes(plan.estimated_bytes)}</span>
          </div>
          <div class="mt-3 space-y-2 text-xs text-white/55">
            {#each plan.selected_formats as format}
              <div class="rounded-lg bg-black/20 p-2 font-mono">format {format.format_id} · {format.ext} · {format.vcodec} / {format.acodec}</div>
            {/each}
          </div>
          <p class="mt-3 break-all text-xs leading-5 text-white/35">Destination: {plan.destination}</p>
          {#if plan.replacement}
            <p class="mt-2 rounded-lg border border-cyan-300/20 bg-cyan-300/8 p-2 text-xs leading-5 text-cyan-100/80">
              This clean replacement becomes the playable copy. The older file stays available in Files for manual deletion.
            </p>
          {/if}
          <label class="mt-4 flex cursor-pointer items-start gap-3 rounded-xl border border-amber-300/20 bg-amber-300/6 p-3 text-sm leading-5">
            <input class="mt-1 accent-red-500" type="checkbox" bind:checked={authorized} />
            <span>I confirm that the Service or relevant rights holders authorize me to download this content.</span>
          </label>
          <div class="mt-4 flex gap-3">
            <button type="button" class="flex-1 rounded-full border border-white/15 py-3 text-sm font-semibold hover:bg-white/5" on:click={() => plan = null}>Change options</button>
            <button type="button" class="flex-1 rounded-full bg-red-600 py-3 text-sm font-bold disabled:opacity-40" disabled={!authorized} on:click={confirm}>Download locally</button>
          </div>
        </section>
      {/if}
    </div>
  </aside>
</div>
