<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import { mangaApi, type MangaHistoryItem } from './mangaApi';

  export let blur = false;

  const dispatch = createEventDispatcher<{
    open: { source: string; externalId: string | null; galleryId: number; localMangaId: number | null; startReading: boolean };
  }>();

  let items: MangaHistoryItem[] = [];
  let total = 0;
  let loading = true;
  let error = '';
  let showAll = false;

  $: unfinished = items.filter((item) => item.page_count === 0 || item.last_page < item.page_count - 1);

  async function load() {
    loading = true;
    error = '';
    try {
      const result = await mangaApi.history(200);
      items = result.items;
      total = result.total;
    } catch (reason) {
      error = reason instanceof Error ? reason.message : String(reason);
    } finally {
      loading = false;
    }
  }

  function cover(item: MangaHistoryItem): string {
    if (item.downloaded) return mangaApi.coverUrl(item.gallery_id);
    if (item.source === 'mangadex') return item.cover_path ?? '';
    return item.cover_path ? mangaApi.remoteImageUrl(item.cover_path) : '';
  }

  function progressLabel(item: MangaHistoryItem): string {
    if (!item.page_count) return `Page ${item.last_page + 1}`;
    if (item.last_page >= item.page_count - 1) return 'Completed';
    return `Page ${item.last_page + 1} of ${item.page_count}`;
  }

  function open(item: MangaHistoryItem, startReading: boolean) {
    dispatch('open', {
      source: item.source,
      externalId: item.external_id,
      galleryId: item.gallery_id,
      localMangaId: item.local_manga_id,
      startReading
    });
  }

  onMount(() => void load());
</script>

<section class="h-full overflow-y-auto px-2 py-4 sm:px-4 sm:py-5" aria-labelledby="manga-history-title">
  <div class="mx-auto max-w-7xl">
    <div class="mb-4 flex items-end justify-between gap-3">
      <div>
        <p class="text-[10px] font-semibold uppercase tracking-[0.2em] text-purple-400/60">Private and local</p>
        <h2 id="manga-history-title" class="mt-1 text-xl font-bold text-purple-100">History</h2>
      </div>
      <span class="text-xs text-gray-600">{total} read</span>
    </div>

    {#if loading}
      <p class="rounded-xl border border-[#29293b] bg-[#12121a] p-8 text-center text-sm text-gray-500">Loading reading history…</p>
    {:else if error}
      <p class="rounded-xl border border-red-500/30 bg-red-500/5 p-5 text-center text-sm text-red-300">{error}</p>
    {:else if items.length === 0}
      <p class="rounded-xl border border-[#29293b] bg-[#12121a] p-8 text-center text-sm text-gray-500">Manga you read in Manayomi will appear here.</p>
    {:else}
      {#if !showAll}
        <div class="mb-3 flex items-center justify-between gap-3">
          <h3 class="text-sm font-semibold text-gray-200">Continue reading</h3>
          <span class="text-xs text-gray-600">Saved automatically</span>
        </div>
        {#if unfinished.length}
          <div class="history-grid">
            {#each unfinished.slice(0, 10) as item (`continue-${item.gallery_id}`)}
              <button class="history-card group text-left" type="button" on:click={() => open(item, true)}>
                <span class="relative block aspect-[7/10] overflow-hidden rounded-lg bg-black">
                  {#if cover(item)}<img src={cover(item)} alt="" class="h-full w-full object-cover transition duration-200 group-hover:scale-[1.03]" class:blur-lg={blur} />{/if}
                  <span class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black via-black/75 to-transparent px-2 pb-2 pt-8 text-[10px] font-semibold text-purple-200">{progressLabel(item)}</span>
                </span>
                <strong class="mt-1.5 block truncate text-xs text-gray-200">{item.title}</strong>
              </button>
            {/each}
          </div>
        {:else}
          <p class="rounded-xl border border-[#29293b] bg-[#12121a] p-5 text-sm text-gray-500">Everything in your history is completed.</p>
        {/if}

        <button class="mx-auto mt-5 block rounded-lg border border-purple-500/35 bg-purple-500/10 px-5 py-2 text-sm font-semibold text-purple-200 hover:bg-purple-500/20" type="button" on:click={() => (showAll = true)}>Show all history</button>
      {:else}
        <div class="mb-3 flex items-center justify-between gap-3">
          <h3 class="text-sm font-semibold text-gray-200">All manga read here</h3>
          <button class="text-xs font-semibold text-purple-300 hover:text-purple-100" type="button" on:click={() => (showAll = false)}>Continue reading</button>
        </div>
        <div class="history-grid">
          {#each items as item (item.gallery_id)}
            <button class="history-card group text-left" type="button" on:click={() => open(item, false)}>
              <span class="relative block aspect-[7/10] overflow-hidden rounded-lg bg-black">
                {#if cover(item)}<img src={cover(item)} alt="" class="h-full w-full object-cover transition duration-200 group-hover:scale-[1.03]" class:blur-lg={blur} />{/if}
                <span class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black via-black/75 to-transparent px-2 pb-2 pt-8 text-[10px] font-semibold text-gray-300">{progressLabel(item)}</span>
              </span>
              <strong class="mt-1.5 block truncate text-xs text-gray-200">{item.title}</strong>
              <small class="mt-0.5 block text-[10px] text-gray-600">{new Date(item.last_read_at).toLocaleDateString()}</small>
            </button>
          {/each}
        </div>
      {/if}
    {/if}
  </div>
</section>

<style>
  .history-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.75rem; }
  .history-card { min-width:0; border-radius:.65rem; padding:.35rem; transition:background 160ms ease; }
  .history-card:hover { background:rgba(168,85,247,.09); }
  @media (min-width:520px) { .history-grid { grid-template-columns:repeat(3,minmax(0,1fr)); } }
  @media (min-width:760px) { .history-grid { grid-template-columns:repeat(5,minmax(0,1fr)); } }
  @media (min-width:1120px) { .history-grid { grid-template-columns:repeat(7,minmax(0,1fr)); } }
</style>
