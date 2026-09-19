<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import {
    mangaApi,
    type MangaDexBrowseFilters,
    type MangaDexFilterCatalog,
    type MangaDexTitle
  } from './mangaApi';
  import MangaDexFilterSheet from './MangaDexFilterSheet.svelte';

  export let blur = true;
  export let coverSize: 'small' | 'current' | 'large' = 'current';
  export let ignoredTags: string[] = [];
  export let showIgnored = true;
  export let hideDownloaded = false;
  export let filterOpen = false;
  export let filterCount = 0;

  const dispatch = createEventDispatcher<{
    openTitle: { titleId: string; forceCoverVisible: boolean };
  }>();

  let items: MangaDexTitle[] = [];
  let page = 1;
  let numPages = 1;
  let total = 0;
  let perPage: 10 | 20 | 30 | 50 | 'all' = 20;
  let query = '';
  let filters: MangaDexBrowseFilters = {
    language: 'all',
    originalLanguages: [],
    contentRatings: [],
    publicationDemographics: [],
    statuses: [],
    sort: 'latest',
    tagsMode: 'AND',
    includedTags: []
  };
  let filterCatalog: MangaDexFilterCatalog | null = null;
  let filterLoading = false;
  let filterError = '';
  let filterRequested = false;
  let loading = false;
  let error = '';
  let scrollRegion: HTMLDivElement;
  let requestSerial = 0;
  let revealedIgnored = new Set<string>();

  $: visibleItems = items.filter(
    (item) => (!hideDownloaded || item.downloaded_chapters === 0) && (showIgnored || !isIgnored(item))
  );
  $: filterCount = (filters.language !== 'all' ? 1 : 0)
    + (filters.sort !== 'latest' ? 1 : 0)
    + (filters.originalLanguages.length ? 1 : 0)
    + (filters.contentRatings.length ? 1 : 0)
    + (filters.publicationDemographics.length ? 1 : 0)
    + (filters.statuses.length ? 1 : 0)
    + (filters.includedTags.length ? 1 : 0)
    + (filters.tagsMode !== 'AND' ? 1 : 0);
  $: if (filterOpen && !filterCatalog && !filterLoading && !filterRequested) {
    void loadFilterCatalog();
  }

  async function loadFilterCatalog() {
    filterRequested = true;
    filterLoading = true;
    filterError = '';
    try {
      filterCatalog = await mangaApi.mangaDexFilters();
    } catch (reason) {
      filterError = reason instanceof Error ? reason.message : String(reason);
    } finally {
      filterLoading = false;
    }
  }

  function retryFilters() {
    filterRequested = false;
  }

  function clearFilters() {
    filters = {
      language: 'all',
      originalLanguages: [],
      contentRatings: [],
      publicationDemographics: [],
      statuses: [],
      sort: 'latest',
      tagsMode: 'AND',
      includedTags: []
    };
    search();
  }

  function applyFilters() {
    filterOpen = false;
    search();
  }

  function ignoredMatches(item: MangaDexTitle): string[] {
    if (item.ignored_matches?.length) return item.ignored_matches;
    const ignored = new Set(ignoredTags.map((tag) => tag.trim().toLowerCase()).filter(Boolean));
    return item.tags.map((tag) => tag.name).filter((name) => ignored.has(name.toLowerCase()));
  }

  function isIgnored(item: MangaDexTitle): boolean {
    return ignoredMatches(item).length > 0;
  }

  async function load(append = false): Promise<boolean> {
    if (append && loading) return false;
    const serial = append ? requestSerial : ++requestSerial;
    loading = true;
    error = '';
    try {
      const result = await mangaApi.mangaDexBrowse({
        query: query.trim(),
        page,
        perPage: perPage === 'all' ? 100 : perPage,
        sort: filters.sort,
        language: filters.language,
        originalLanguages: filters.originalLanguages,
        contentRatings: filters.contentRatings,
        publicationDemographics: filters.publicationDemographics,
        statuses: filters.statuses,
        includedTags: filters.includedTags,
        tagsMode: filters.tagsMode
      });
      if (serial !== requestSerial) return false;
      if (append) {
        const known = new Set(items.map((item) => item.id));
        items = [...items, ...result.items.filter((item) => !known.has(item.id))];
      } else {
        items = result.items;
      }
      page = result.page;
      numPages = result.num_pages;
      total = result.total;
      return true;
    } catch (reason) {
      if (serial !== requestSerial) return false;
      error = reason instanceof Error ? reason.message : String(reason);
      return false;
    } finally {
      if (serial === requestSerial) loading = false;
    }
  }

  function search() {
    page = 1;
    items = [];
    void load(false);
  }

  function open(item: MangaDexTitle) {
    const ignored = isIgnored(item);
    if (ignored && !revealedIgnored.has(item.id)) {
      revealedIgnored = new Set(revealedIgnored).add(item.id);
      return;
    }
    dispatch('openTitle', { titleId: item.id, forceCoverVisible: ignored });
  }

  function setPage(next: number) {
    if (next < 1 || next > numPages) return;
    page = next;
    void load(false).then(() => scrollRegion?.scrollTo({ top: 0, behavior: 'smooth' }));
  }

  function setPerPage() {
    page = 1;
    items = [];
    void load(false);
  }

  async function loadMore() {
    if (perPage !== 'all' || loading || page >= numPages) return;
    const previous = page;
    page += 1;
    if (!(await load(true))) page = previous;
  }

  function observeInfinite(node: HTMLElement) {
    const observer = new IntersectionObserver(
      (entries) => entries.some((entry) => entry.isIntersecting) && void loadMore(),
      { root: scrollRegion, rootMargin: '600px 0px' }
    );
    observer.observe(node);
    return { destroy: () => observer.disconnect() };
  }

  function cover(item: MangaDexTitle): string {
    return item.cover_filename ? mangaApi.mangaDexCoverUrl(item.id, item.cover_filename) : '';
  }

  onMount(() => void load());
</script>

<div class="flex h-full min-h-0 flex-col">
  <div class="relative border-b border-[#26263a] p-2 sm:p-3">
    <form class="flex min-w-0 gap-2" on:submit|preventDefault={search}>
      <input
        class="min-w-0 flex-1 rounded-lg border border-[#2c2c40] bg-[#15151f] px-3 py-1.5 text-sm text-gray-200 placeholder-gray-600 focus:border-purple-500/60 focus:outline-none"
        placeholder="Search MangaDex titles"
        bind:value={query}
      />
      <button class="rounded-lg border border-purple-500/35 bg-purple-500/10 px-3 text-sm font-semibold text-purple-200 hover:bg-purple-500/20" type="submit">Search</button>
    </form>
    <MangaDexFilterSheet
      open={filterOpen}
      catalog={filterCatalog}
      values={filters}
      loading={filterLoading}
      error={filterError}
      hasActive={filterCount > 0}
      on:close={() => (filterOpen = false)}
      on:change={(event) => (filters = event.detail)}
      on:retry={retryFilters}
      on:clear={clearFilters}
      on:apply={applyFilters}
    />
  </div>

  <div class="min-h-0 flex-1 overflow-y-auto p-2 sm:p-3" bind:this={scrollRegion}>
    {#if error}
      <p class="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">{error}</p>
    {:else if loading && items.length === 0}
      <p class="p-6 text-center text-sm text-gray-500">Loading MangaDex…</p>
    {:else}
      <div class="mangadex-grid grid gap-3" class:cover-small={coverSize === 'small'} class:cover-large={coverSize === 'large'} class:opacity-60={loading}>
        {#each visibleItems as item (item.id)}
          <button class="group relative min-w-0 overflow-hidden rounded-xl border border-[#26263a] bg-[#14141c] text-left" type="button" on:click={() => open(item)}>
            <div class="relative aspect-[7/10] overflow-hidden bg-[#101018]">
              {#if cover(item)}
                <img
                  src={cover(item)}
                  alt=""
                  loading="lazy"
                  class="h-full w-full object-cover transition-[filter,opacity,transform] duration-300 group-hover:scale-[1.02]"
                  class:blur-xl={blur && !isIgnored(item)}
                  class:opacity-0={isIgnored(item) && !revealedIgnored.has(item.id)}
                  class:group-hover:blur-none={blur && !isIgnored(item)}
                />
              {/if}
              {#if isIgnored(item)}
                <span class="blacklist-cover-overlay absolute inset-0 z-10 grid place-content-center gap-1 bg-black px-2 text-center" class:is-revealed={revealedIgnored.has(item.id)}>
                  <span class="text-[10px] font-bold uppercase tracking-[0.18em] text-red-200">Blacklisted</span>
                  <span class="line-clamp-2 text-xs text-gray-200">{ignoredMatches(item).join(', ')}</span>
                </span>
              {/if}
              {#if item.downloaded_chapters > 0}<span class="absolute right-1.5 top-1.5 rounded bg-green-600/90 px-1.5 py-0.5 text-[10px] font-bold text-white">{item.downloaded_chapters} saved</span>{/if}
              <span class="absolute bottom-1.5 left-1.5 rounded bg-black/75 px-1.5 py-0.5 text-[10px] uppercase text-gray-200">{item.status || item.content_rating}</span>
              <span class="absolute bottom-1.5 right-1.5 rounded bg-black/75 px-1.5 py-0.5 text-[10px] font-semibold text-yellow-200">{item.available_languages.length} lang</span>
            </div>
            <div class="p-2">
              <strong class="line-clamp-2 text-xs text-gray-100" title={item.title}>{item.title}</strong>
              <p class="mt-1 truncate text-[10px] text-gray-500">{[...item.authors, ...item.artists].filter((name, index, all) => all.indexOf(name) === index).join(', ') || 'Unknown creator'}</p>
              <p class="mt-1 flex min-w-0 gap-1 overflow-hidden text-[10px] text-purple-300">
                {#each item.tags.slice(0, 3) as tag}<span class="shrink-0">{tag.name}</span>{/each}
              </p>
            </div>
          </button>
        {/each}
      </div>
      {#if perPage === 'all' && page < numPages}
        <div class="mt-4 grid min-h-12 place-items-center text-xs text-gray-500" use:observeInfinite>{loading ? 'Loading more…' : 'Scroll for more'}</div>
      {/if}
    {/if}
  </div>

  <div class="md-pager z-20 flex shrink-0 items-center justify-between gap-2 border-t border-[#3a3a52] bg-[#161620] px-2 py-2 text-sm sm:justify-center sm:px-3">
    {#if perPage === 'all'}
      <span class="min-w-0 flex-1 truncate text-center text-xs text-gray-200 sm:flex-none sm:text-sm">{items.length} / {total} loaded</span>
    {:else}
      <button class="rounded-lg border border-[#3a3a52] bg-[#1d1d29] px-3 py-1 text-gray-100 disabled:opacity-40" disabled={page <= 1} on:click={() => setPage(page - 1)}>Prev</button>
      <span class="min-w-0 truncate text-center text-xs text-gray-200 sm:text-sm">{page} / {numPages} — {total} titles</span>
      <button class="rounded-lg border border-[#3a3a52] bg-[#1d1d29] px-3 py-1 text-gray-100 disabled:opacity-40" disabled={page >= numPages} on:click={() => setPage(page + 1)}>Next</button>
    {/if}
    <select aria-label="MangaDex titles per page" class="min-w-[3.5rem] rounded-lg border border-[#3a3a52] bg-[#1d1d29] px-2 py-1 text-xs text-white sm:ml-2 sm:text-sm" bind:value={perPage} on:change={setPerPage}>
      <option value={10}>10</option><option value={20}>20</option><option value={30}>30</option><option value={50}>50</option><option value="all">All</option>
    </select>
  </div>
  <p class="shrink-0 bg-[#101018] px-3 py-1 text-center text-[10px] text-gray-600">Metadata and chapters provided by MangaDex. Scanlation groups are credited in chapter details.</p>
</div>

<style>
  .md-pager { padding-bottom:max(.5rem, env(safe-area-inset-bottom)); }
  .mangadex-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
  .mangadex-grid.cover-small { grid-template-columns:repeat(3,minmax(0,1fr)); }
  .mangadex-grid.cover-large { grid-template-columns:repeat(1,minmax(0,1fr)); }
  .blacklist-cover-overlay { opacity:1; transition:opacity 300ms ease, transform 300ms cubic-bezier(.22,1,.36,1); }
  .blacklist-cover-overlay.is-revealed { opacity:0; pointer-events:none; transform:translate3d(.75rem,0,0); }
  @media (min-width:640px) { .mangadex-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.mangadex-grid.cover-small{grid-template-columns:repeat(4,minmax(0,1fr))}.mangadex-grid.cover-large{grid-template-columns:repeat(2,minmax(0,1fr))} }
  @media (min-width:768px) { .mangadex-grid{grid-template-columns:repeat(4,minmax(0,1fr))}.mangadex-grid.cover-small{grid-template-columns:repeat(5,minmax(0,1fr))}.mangadex-grid.cover-large{grid-template-columns:repeat(3,minmax(0,1fr))} }
  @media (min-width:1280px) { .mangadex-grid{grid-template-columns:repeat(6,minmax(0,1fr))}.mangadex-grid.cover-small{grid-template-columns:repeat(8,minmax(0,1fr))}.mangadex-grid.cover-large{grid-template-columns:repeat(5,minmax(0,1fr))} }
  @media (prefers-reduced-motion:reduce) { .blacklist-cover-overlay{transition-duration:1ms} }
</style>
