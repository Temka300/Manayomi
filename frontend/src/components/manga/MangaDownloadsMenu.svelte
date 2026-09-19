<script lang="ts">
  import { createEventDispatcher, onDestroy, onMount } from 'svelte';
  import { mangaApi, type MangaCard, type MangaDownloadItem, type MangaDownloadState } from './mangaApi';

  export let blur = false;

  const dispatch = createEventDispatcher<{
    close: void;
    showAll: void;
    open: { source: string; externalId: string | null; galleryId: number | null; localMangaId: number | null };
  }>();

  let state: MangaDownloadState | null = null;
  let recent: MangaCard[] = [];
  let timer: ReturnType<typeof setTimeout> | null = null;
  let error = '';
  let destroyed = false;

  async function load() {
    try {
      const [nextState, nextRecent] = await Promise.all([
        mangaApi.downloads(),
        mangaApi.recentDownloads(5)
      ]);
      state = nextState;
      recent = nextRecent.manga;
      error = '';
    } catch (reason) {
      error = reason instanceof Error ? reason.message : String(reason);
    } finally {
      if (!destroyed) timer = setTimeout(() => void load(), 1000);
    }
  }

  function formatDate(value: number): string {
    return new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  }

  function openActive(item: MangaDownloadItem) {
    dispatch('open', {
      source: item.source,
      externalId: item.external_id,
      galleryId: item.gallery_id,
      localMangaId: item.local_manga_id ?? null
    });
  }

  onMount(() => void load());
  onDestroy(() => {
    destroyed = true;
    if (timer) clearTimeout(timer);
  });
</script>

<div class="downloads-menu absolute right-0 top-full z-[65] mt-2 overflow-hidden rounded-xl border border-[#303046] bg-[#12121c] shadow-2xl shadow-black/60" role="dialog" aria-label="Latest Manayomi downloads">
  <div class="border-b border-[#29293b] px-3 py-2.5">
    <p class="text-xs font-semibold uppercase tracking-[0.13em] text-purple-300/70">Downloads</p>
    {#if state?.current}
      <button class="mt-2 block w-full rounded-lg bg-purple-500/8 p-2 text-left" type="button" on:click={() => openActive(state!.current!)}>
        <span class="block truncate text-xs font-semibold text-purple-100">{state.current.title}</span>
        <span class="mt-1 block text-[11px] text-gray-500">{state.current.page} / {state.current.pages || '?'} pages</span>
        <span class="mt-1.5 block h-1 overflow-hidden rounded-full bg-[#29293b]">
          <span class="block h-full bg-purple-500 transition-[width]" style="width: {state.current.pages ? (state.current.page / state.current.pages) * 100 : 0}%"></span>
        </span>
      </button>
    {:else if state?.queue.length}
      <p class="mt-1 text-xs text-gray-500">{state.queue.length} queued</p>
    {:else}
      <p class="mt-1 text-xs text-gray-500">No active download</p>
    {/if}
  </div>

  <div class="p-2">
    <p class="px-1 pb-1.5 text-[11px] font-semibold uppercase tracking-wide text-gray-600">Latest downloaded</p>
    {#if error}
      <p class="px-2 py-4 text-center text-xs text-red-300">{error}</p>
    {:else if recent.length}
      {#each recent as item (item.id)}
        <button class="flex w-full min-w-0 items-center gap-2 rounded-lg p-1.5 text-left hover:bg-purple-500/10" type="button" on:click={() => dispatch('open', { source: item.source, externalId: item.external_id, galleryId: item.gallery_id, localMangaId: item.id })}>
          <img src={mangaApi.coverUrl(item.gallery_id)} alt="" class="h-12 w-9 shrink-0 rounded object-cover transition" class:blur-md={blur} />
          <span class="min-w-0 flex-1">
            <strong class="block truncate text-xs font-semibold text-gray-200">{item.title}</strong>
            <small class="mt-0.5 block text-[10px] text-gray-600">{formatDate(item.created_at)} · #{item.gallery_id}</small>
          </span>
        </button>
      {/each}
    {:else}
      <p class="px-2 py-4 text-center text-xs text-gray-600">Downloaded manga will appear here.</p>
    {/if}
  </div>

  <button class="block w-full border-t border-[#29293b] px-3 py-2.5 text-center text-xs font-semibold text-purple-300 hover:bg-purple-500/10 hover:text-purple-100" type="button" on:click={() => dispatch('showAll')}>Show all</button>
</div>

<style>
  .downloads-menu { width: min(21rem, calc(100vw - 1rem)); }
</style>
