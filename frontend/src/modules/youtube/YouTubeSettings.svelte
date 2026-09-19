<script lang="ts">
  import { onMount } from 'svelte';

  import { youtubeApi } from '../../lib/youtubeApi';
  import {
    resetYouTubeDownloadDefaults,
    youtubeDownloadDefaults,
  } from './settings';

  let status: Record<string, unknown> | null = null;
  let error = '';
  let loading = true;

  $: storage = (status?.storage ?? {}) as Record<string, string>;
  $: limits = (status?.limits ?? {}) as Record<string, number>;
  $: jobs = Array.isArray(status?.jobs) ? status.jobs as Array<Record<string, unknown>> : [];
  $: activeJobs = jobs.filter((job) => ['queued', 'running', 'cancelling'].includes(String(job.status))).length;

  async function refresh() {
    loading = true;
    error = '';
    try {
      status = await youtubeApi.status();
    } catch (cause) {
      error = (cause as Error).message;
      status = null;
    } finally {
      loading = false;
    }
  }

  onMount(refresh);
</script>

<div class="mx-auto max-w-3xl space-y-4">
  <section class="overflow-hidden rounded-2xl border border-red-400/15 bg-[radial-gradient(circle_at_85%_-30%,rgba(239,68,68,.17),transparent_54%),#151111]">
    <div class="flex flex-wrap items-center justify-between gap-4 border-b border-white/7 px-5 py-4">
      <div><p class="text-[10px] font-semibold uppercase tracking-[0.2em] text-red-400">YouTube module</p><h3 class="mt-1 text-lg font-bold text-white">Local video acquisition</h3></div>
      <button type="button" class="rounded-xl border border-white/10 px-3 py-2 text-xs text-white/65 hover:bg-white/5" on:click={refresh}>Refresh</button>
    </div>
    <div class="grid gap-3 p-4 sm:grid-cols-3">
      <div class="rounded-xl border border-white/7 bg-black/20 p-4"><div class="text-[10px] uppercase tracking-wider text-white/35">Local videos</div><div class="mt-1 text-2xl font-bold text-red-100">{loading ? '…' : Number(status?.items ?? 0).toLocaleString()}</div></div>
      <div class="rounded-xl border border-white/7 bg-black/20 p-4"><div class="text-[10px] uppercase tracking-wider text-white/35">Active jobs</div><div class="mt-1 text-2xl font-bold text-red-100">{loading ? '…' : activeJobs}</div></div>
      <div class="rounded-xl border border-white/7 bg-black/20 p-4"><div class="text-[10px] uppercase tracking-wider text-white/35">Concurrency</div><div class="mt-1 text-2xl font-bold text-red-100">{loading ? '…' : Number(limits.active_jobs ?? 1)}</div></div>
    </div>
  </section>

  {#if error}<p class="rounded-xl border border-red-400/15 bg-red-500/6 px-4 py-3 text-xs text-red-300">{error}</p>{/if}

  <section id="setting-youtube-defaults" class="rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)] p-4">
    <div class="flex items-center justify-between gap-4"><div><h4 class="text-sm font-semibold text-[var(--text-primary)]">Download defaults</h4><p class="mt-1 text-xs text-[var(--text-muted)]">Prefill the confirmation sheet. Each plan still shows its exact format IDs and estimated size.</p></div><button type="button" class="rounded-lg border border-[var(--border-default)] px-3 py-2 text-xs text-[var(--text-secondary)] hover:bg-white/5" on:click={resetYouTubeDownloadDefaults}>Reset</button></div>
    <div class="mt-4 grid gap-3 sm:grid-cols-2">
      <label class="text-xs font-semibold text-[var(--text-muted)]">Video quality<select class="mt-2 w-full rounded-xl border border-[var(--border-default)] bg-[var(--bg-base)] px-3 py-2.5 text-sm text-[var(--text-primary)]" bind:value={$youtubeDownloadDefaults.resolution}>{#each ['480', '720', '1080', '1440', '2160', 'highest'] as value}<option value={value}>{value === 'highest' ? 'Highest available' : `${value}p`}</option>{/each}</select></label>
      <label class="text-xs font-semibold text-[var(--text-muted)]">Companion audio<select class="mt-2 w-full rounded-xl border border-[var(--border-default)] bg-[var(--bg-base)] px-3 py-2.5 text-sm text-[var(--text-primary)]" bind:value={$youtubeDownloadDefaults.audioFormat}>{#each ['none', 'best', 'm4a', 'opus', 'mp3'] as value}<option value={value}>{value === 'none' ? 'None' : value.toUpperCase()}</option>{/each}</select></label>
      <label class="text-xs font-semibold text-[var(--text-muted)]">Converted audio quality<select class="mt-2 w-full rounded-xl border border-[var(--border-default)] bg-[var(--bg-base)] px-3 py-2.5 text-sm text-[var(--text-primary)]" bind:value={$youtubeDownloadDefaults.audioQuality}><option value="128K">128 kbps</option><option value="192K">192 kbps</option><option value="320K">320 kbps</option></select></label>
      <label class="flex items-start gap-3 rounded-xl bg-black/20 p-3 text-xs text-[var(--text-secondary)]"><input class="mt-0.5 accent-red-500" type="checkbox" bind:checked={$youtubeDownloadDefaults.compatibility} /><span><strong class="block text-[var(--text-primary)]">Prefer compatible MP4</strong>H.264/AAC when available.</span></label>
      <label class="flex items-start gap-3 rounded-xl bg-black/20 p-3 text-xs text-[var(--text-secondary)]"><input class="mt-0.5 accent-red-500" type="checkbox" bind:checked={$youtubeDownloadDefaults.automaticCaptions} /><span><strong class="block text-[var(--text-primary)]">Allow automatic captions</strong>Manual captions remain the safer default.</span></label>
      <label class="text-xs font-semibold text-[var(--text-muted)] sm:col-span-2">YouTube browser session (optional)<select class="mt-2 w-full rounded-xl border border-[var(--border-default)] bg-[var(--bg-base)] px-3 py-2.5 text-sm text-[var(--text-primary)]" bind:value={$youtubeDownloadDefaults.browserSession}><option value="none">None — anonymous requests</option><option value="chrome">Chrome</option><option value="edge">Edge</option><option value="firefox">Firefox</option></select><span class="mt-2 block font-normal leading-5 text-amber-200/55">Use only when YouTube rate-limits anonymous subtitle requests. yt-dlp reads the selected local profile for that plan; Keivotos never stores the cookie data.</span></label>
    </div>
  </section>

  <section id="setting-youtube-safety" class="rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)] p-4">
    <h4 class="text-sm font-semibold text-[var(--text-primary)]">Acquisition boundary</h4>
    <div class="mt-3 flex flex-wrap gap-2 text-[11px] text-red-100/75"><span class="rounded-full bg-red-500/8 px-3 py-1.5">Public single videos</span><span class="rounded-full bg-red-500/8 px-3 py-1.5">Optional local browser session</span><span class="rounded-full bg-red-500/8 px-3 py-1.5">No playlists</span><span class="rounded-full bg-red-500/8 px-3 py-1.5">Sequential queue</span><span class="rounded-full bg-red-500/8 px-3 py-1.5">Explicit confirmation</span>{#if limits.minimum_free_bytes}<span class="rounded-full bg-red-500/8 px-3 py-1.5">{Math.round(limits.minimum_free_bytes / 1024 / 1024)} MiB free reserve</span>{/if}</div>
    <p class="mt-3 text-xs leading-5 text-[var(--text-muted)]">Search thumbnails are copied into the local cache before display. The module never streams remote video into the player and rejects non-YouTube acquisition targets.</p>
  </section>

  <section id="setting-youtube-storage" class="rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)] p-4">
    <h4 class="text-sm font-semibold text-[var(--text-primary)]">Storage and Files</h4>
    <div class="mt-3 space-y-2 text-xs">{#each Object.entries(storage) as [label, path]}<div class="rounded-lg bg-black/20 px-3 py-2"><span class="mr-2 font-semibold capitalize text-[var(--text-secondary)]">{label.replace('_', ' ')}</span><span class="break-all text-gray-600">{path}</span></div>{/each}</div>
    <p class="mt-3 text-xs leading-5 text-green-200/65">Completed videos, subtitles, audio, metadata, receipts, and thumbnails are published to Files. Downloads are create-only and resumable; existing local assets are not overwritten.</p>
  </section>
</div>
