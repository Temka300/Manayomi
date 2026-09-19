<script lang="ts">
  import { createEventDispatcher, onDestroy, onMount } from 'svelte';
  import {
    mangaApi,
    type MangaCard,
    type MangaDownloadState
  } from './mangaApi';

  export let blur = false;
  export let coverSize: 'small' | 'current' | 'large' = 'current';

  const dispatch = createEventDispatcher<{ open: { mangaId: number } }>();

  let state: MangaDownloadState | null = null;
  let downloaded: MangaCard[] = [];
  let total = 0;
  let loading = true;
  let error = '';
  let timer: ReturnType<typeof setTimeout> | null = null;
  let destroyed = false;
  const batchSize = 60;

  async function pollQueue() {
    try {
      state = await mangaApi.downloads();
    } catch {
      /* transient queue status errors do not hide the local download list */
    } finally {
      if (!destroyed) timer = setTimeout(() => void pollQueue(), 1000);
    }
  }

  async function loadDownloads(append = false) {
    loading = true;
    error = '';
    try {
      const offset = append ? downloaded.length : 0;
      const result = await mangaApi.recentDownloads(batchSize, offset);
      downloaded = append ? [...downloaded, ...result.manga] : result.manga;
      total = result.total;
    } catch (reason) {
      error = reason instanceof Error ? reason.message : String(reason);
    } finally {
      loading = false;
    }
  }

  function dateLabel(value: number): string {
    return new Date(value).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  }

  const STATUS_COLORS: Record<string, string> = {
    queued: 'text-gray-400',
    downloading: 'text-purple-200',
    done: 'text-green-300',
    error: 'text-red-300'
  };

  onMount(() => {
    void pollQueue();
    void loadDownloads();
  });
  onDestroy(() => {
    destroyed = true;
    if (timer) clearTimeout(timer);
  });
</script>

<section class="h-full overflow-y-auto p-3 sm:p-4" aria-labelledby="downloads-title">
  <div class="mx-auto max-w-7xl space-y-5">
    <div class="flex min-w-0 flex-wrap items-end justify-between gap-2">
      <div>
        <p class="text-[10px] font-semibold uppercase tracking-[0.2em] text-purple-400/60">Local Manayomi library</p>
        <h2 id="downloads-title" class="mt-1 text-xl font-bold text-purple-100">Downloads</h2>
      </div>
      <span class="text-xs text-gray-600">{total} downloaded</span>
    </div>

    {#if state?.current || state?.queue.length || state?.recent.length}
      <div class="grid gap-3 lg:grid-cols-[1.2fr_.8fr]">
        <div>
          {#if state?.current}
            <div class="rounded-xl border border-purple-500/30 bg-[#14141c] p-4">
              <p class="truncate text-sm font-semibold text-purple-100">{state.current.title}</p>
              <p class="mt-1 text-xs text-gray-500">#{state.current.gallery_id} — page {state.current.page}/{state.current.pages || '?'}</p>
              <div class="mt-2 h-1.5 overflow-hidden rounded bg-[#26263a]">
                <div class="h-full bg-purple-500 transition-all" style="width: {state.current.pages ? (state.current.page / state.current.pages) * 100 : 0}%"></div>
              </div>
            </div>
          {:else}
            <p class="rounded-xl border border-[#26263a] bg-[#14141c] p-4 text-sm text-gray-500">Nothing downloading.</p>
          {/if}

          {#if state && state.queue.length > 0}
            <div class="mt-3 rounded-xl border border-[#26263a] bg-[#14141c] p-4">
              <h3 class="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Queued ({state.queue.length})</h3>
              {#each state.queue as item (item.gallery_id)}
                <p class="truncate py-0.5 text-sm text-gray-400">#{item.gallery_id} {item.title}</p>
              {/each}
            </div>
          {/if}
        </div>

        {#if state && state.recent.length > 0}
          <div class="rounded-xl border border-[#26263a] bg-[#14141c] p-4">
            <h3 class="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Recent jobs</h3>
            {#each state.recent as item, index (index)}
              <div class="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-0.5 py-1 text-sm">
                <span class="w-16 shrink-0 text-xs {STATUS_COLORS[item.status]}">{item.status}</span>
                <span class="min-w-0 flex-1 basis-40 truncate text-gray-300">{item.title}</span>
                {#if item.error}<span class="w-full break-words text-xs text-red-400" title={item.error}>{item.error}</span>{/if}
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {/if}

    <div>
      <h3 class="mb-3 text-sm font-semibold text-gray-200">All downloaded manga</h3>
      {#if error}
        <p class="rounded-xl border border-red-500/30 bg-red-500/5 p-5 text-center text-sm text-red-300">{error}</p>
      {:else if downloaded.length === 0 && !loading}
        <p class="rounded-xl border border-[#29293b] bg-[#12121a] p-8 text-center text-sm text-gray-500">Downloaded manga will appear here.</p>
      {:else}
        <div class="download-grid" class:cover-small={coverSize === 'small'} class:cover-large={coverSize === 'large'}>
          {#each downloaded as item (item.id)}
            <button class="group min-w-0 rounded-lg p-1.5 text-left hover:bg-purple-500/10" type="button" on:click={() => dispatch('open', { mangaId: item.id })}>
              <span class="relative block aspect-[7/10] overflow-hidden rounded-lg bg-black">
                <img src={mangaApi.coverUrl(item.gallery_id)} alt="" loading="lazy" class="h-full w-full object-cover transition duration-200 group-hover:scale-[1.03]" class:blur-lg={blur} />
                <span class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black via-black/75 to-transparent px-2 pb-2 pt-8 text-[10px] text-purple-200">{dateLabel(item.created_at)}</span>
              </span>
              <strong class="mt-1.5 block truncate text-xs text-gray-200">{item.title}</strong>
              <small class="mt-0.5 block text-[10px] text-gray-600">#{item.gallery_id}</small>
            </button>
          {/each}
        </div>
        {#if downloaded.length < total}
          <button class="mx-auto mt-5 block rounded-lg border border-purple-500/35 bg-purple-500/10 px-5 py-2 text-sm font-semibold text-purple-200 hover:bg-purple-500/20 disabled:opacity-50" type="button" disabled={loading} on:click={() => void loadDownloads(true)}>{loading ? 'Loading…' : 'Load more'}</button>
        {/if}
      {/if}
    </div>
  </div>
</section>

<style>
  .download-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.55rem; }
  @media (min-width:520px) { .download-grid { grid-template-columns:repeat(3,minmax(0,1fr)); } }
  @media (min-width:760px) { .download-grid { grid-template-columns:repeat(5,minmax(0,1fr)); } }
  @media (min-width:1120px) { .download-grid { grid-template-columns:repeat(7,minmax(0,1fr)); } }
  @media (min-width:1120px) { .download-grid.cover-small { grid-template-columns:repeat(9,minmax(0,1fr)); } }
  @media (min-width:1120px) { .download-grid.cover-large { grid-template-columns:repeat(6,minmax(0,1fr)); } }
</style>
