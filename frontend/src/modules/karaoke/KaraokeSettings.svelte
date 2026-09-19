<script lang="ts">
  import { onMount } from 'svelte';

  import { karaokeApi } from '../../lib/karaokeApi';

  let status: Record<string, unknown> | null = null;
  let error = '';
  let loading = true;

  $: storage = (status?.storage ?? {}) as Record<string, string>;
  $: providers = (status?.providers ?? {}) as Record<string, boolean>;
  $: limits = (status?.limits ?? {}) as Record<string, number>;
  $: jobs = Array.isArray(status?.jobs) ? status.jobs as Array<Record<string, unknown>> : [];
  $: activeJobs = jobs.filter((job) => ['queued', 'running', 'cancelling'].includes(String(job.status))).length;

  async function refresh() {
    loading = true;
    error = '';
    try {
      status = await karaokeApi.status();
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
  <section class="overflow-hidden rounded-2xl border border-cyan-300/15 bg-[radial-gradient(circle_at_85%_-30%,rgba(34,211,238,.16),transparent_54%),#10151a]">
    <div class="flex flex-wrap items-center justify-between gap-4 border-b border-white/7 px-5 py-4">
      <div>
        <p class="text-[10px] font-semibold uppercase tracking-[0.2em] text-cyan-300">Karaoke module</p>
        <h3 class="mt-1 text-lg font-bold text-white">Local singing library</h3>
      </div>
      <button type="button" class="rounded-xl border border-white/10 px-3 py-2 text-xs text-white/65 hover:bg-white/5" on:click={refresh}>Refresh</button>
    </div>
    <div class="grid gap-3 p-4 sm:grid-cols-3">
      <div class="rounded-xl border border-white/7 bg-black/20 p-4"><div class="text-[10px] uppercase tracking-wider text-white/35">Songs</div><div class="mt-1 text-2xl font-bold text-cyan-100">{loading ? '…' : Number(status?.items ?? 0).toLocaleString()}</div></div>
      <div class="rounded-xl border border-white/7 bg-black/20 p-4"><div class="text-[10px] uppercase tracking-wider text-white/35">Playlists</div><div class="mt-1 text-2xl font-bold text-cyan-100">{loading ? '…' : Number(status?.playlists ?? 0).toLocaleString()}</div></div>
      <div class="rounded-xl border border-white/7 bg-black/20 p-4"><div class="text-[10px] uppercase tracking-wider text-white/35">Active jobs</div><div class="mt-1 text-2xl font-bold text-cyan-100">{loading ? '…' : activeJobs}</div></div>
    </div>
  </section>

  {#if error}<p class="rounded-xl border border-red-400/15 bg-red-500/6 px-4 py-3 text-xs text-red-300">{error}</p>{/if}

  <section id="setting-karaoke-providers" class="rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)] p-4">
    <h4 class="text-sm font-semibold text-[var(--text-primary)]">Discovery and handoff</h4>
    <div class="mt-3 grid gap-2 sm:grid-cols-2">
      <div class="flex items-center justify-between rounded-xl bg-black/20 px-3 py-3 text-xs"><span class="text-[var(--text-secondary)]">Kara.moe catalog</span><span class={providers.kara_moe ? 'text-green-300' : 'text-gray-600'}>{providers.kara_moe ? 'Available' : 'Unavailable'}</span></div>
      <div class="flex items-center justify-between rounded-xl bg-black/20 px-3 py-3 text-xs"><span class="text-[var(--text-secondary)]">YouTube fallback</span><span class={providers.youtube_handoff ? 'text-green-300' : 'text-gray-600'}>{providers.youtube_handoff ? 'Connected' : 'Unavailable'}</span></div>
    </div>
    <p class="mt-3 text-xs leading-5 text-[var(--text-muted)]">Kara.moe is searched first. A missing song can be handed to YouTube with the query preserved, then added back to Karaoke through its Files reference after download.</p>
  </section>

  <section id="setting-karaoke-player" class="rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)] p-4">
    <h4 class="text-sm font-semibold text-[var(--text-primary)]">Player behavior</h4>
    <div class="mt-3 flex flex-wrap gap-2 text-[11px] text-cyan-100/75"><span class="rounded-full bg-cyan-500/8 px-3 py-1.5">Mouse 1 toggles controls</span><span class="rounded-full bg-cyan-500/8 px-3 py-1.5">3-second idle hide</span><span class="rounded-full bg-cyan-500/8 px-3 py-1.5">ASS, SRT, VTT, LRC</span><span class="rounded-full bg-cyan-500/8 px-3 py-1.5">Playback position saved</span></div>
    <p class="mt-3 text-xs leading-5 text-[var(--text-muted)]">ASS/SSA is rendered locally through JASSUB. The lyrics button opens the cue list without leaving the player.</p>
  </section>

  <section id="setting-karaoke-storage" class="rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)] p-4">
    <h4 class="text-sm font-semibold text-[var(--text-primary)]">Storage and Files</h4>
    <div class="mt-3 space-y-2 text-xs">
      {#each Object.entries(storage) as [label, path]}
        <div class="rounded-lg bg-black/20 px-3 py-2"><span class="mr-2 font-semibold capitalize text-[var(--text-secondary)]">{label}</span><span class="break-all text-gray-600">{path}</span></div>
      {/each}
    </div>
    <p class="mt-3 text-xs leading-5 text-green-200/65">Downloaded media is create-only, published to Files, and never silently deleted or replaced. Files imports remain references and are hash-checked before playback.</p>
    {#if limits.minimum_free_bytes}<p class="mt-2 text-xs text-gray-600">Transfers retain at least {Math.round(limits.minimum_free_bytes / 1024 / 1024)} MiB free and only one Karaoke job may run at a time.</p>{/if}
  </section>
</div>
