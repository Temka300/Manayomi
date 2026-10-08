<script lang="ts">
  import { createEventDispatcher, onMount, tick } from 'svelte';
  import {
    mangaApi,
    languageBadges,
    MANGA_TAG_COLORS,
    type CoverProgressMode,
    type LibraryResult,
    type MangaCard,
    type MangaCategory,
    type MangaTag
  } from './mangaApi';
  import MangaFilterSheet from './MangaFilterSheet.svelte';

  type LibraryFilterKey = 'tags' | 'categories' | 'groups' | 'artists' | 'parodies' | 'characters';

  export let blur = true;
  export let initialFilter: { key: LibraryFilterKey; value: string } | null = null;
  export let coverSize: 'small' | 'current' | 'large' = 'current';
  export let coverProgress: CoverProgressMode = 'bar';

  /** Read-progress for a card, or null when it has never been opened. */
  function progressInfo(card: MangaCard) {
    const count = card.read_page_count ?? 0;
    const last = card.read_last_page;
    if (count <= 0 || last == null) return null;
    const read = Math.min(count, Math.max(0, last) + 1);
    const percent = Math.max(0, Math.min(100, Math.round((read / count) * 100)));
    return { percent, read, count };
  }

  const dispatch = createEventDispatcher<{ open: { mangaId: number }; filterSeedConsumed: void }>();

  let result: LibraryResult | null = null;
  let categories: MangaCategory[] = [];
  let topTags: MangaTag[] = [];
  let error = '';
  let loading = false;

  let q = '';
  let page = 1;
  let sort = 'recent';
  let language = 'all';
  let favoritesOnly = false;
  let categoryId: number | null = null;
  let showSidebar = true;
  let filterOpen = false;
  let perPage: 10 | 20 | 30 | 50 | 'all' = 20;
  let scrollRegion: HTMLDivElement;

  // Which series are expanded into their inline chapter strip, and a cache of
  // each expanded series' chapters. Both reset whenever the library reloads.
  let expandedSeries = new Set<number>();
  let seriesChapters: Record<number, MangaCard[]> = {};

  async function toggleSeries(seriesId: number | null) {
    if (seriesId == null) return;
    const next = new Set(expandedSeries);
    if (next.has(seriesId)) {
      next.delete(seriesId);
      expandedSeries = next;
      return;
    }
    next.add(seriesId);
    expandedSeries = next;
    if (!seriesChapters[seriesId]) {
      try {
        const detail = await mangaApi.seriesDetail(seriesId);
        seriesChapters = { ...seriesChapters, [seriesId]: detail.chapters };
      } catch {
        /* leave in the loading state; collapsing and reopening retries */
      }
    }
  }

  const FILTERS: { key: LibraryFilterKey; label: string; prefix: string }[] = [
    { key: 'tags', label: 'Tags', prefix: 'tag' },
    { key: 'categories', label: 'Categories', prefix: 'category' },
    { key: 'groups', label: 'Groups', prefix: 'group' },
    { key: 'artists', label: 'Artists', prefix: 'artist' },
    { key: 'parodies', label: 'Parodies', prefix: 'parody' },
    { key: 'characters', label: 'Characters', prefix: 'character' }
  ];

  export let filters: Record<LibraryFilterKey, string> = {
    tags: '',
    categories: '',
    groups: '',
    artists: '',
    parodies: '',
    characters: ''
  };

  function filterTokens(value: string, prefix: string): string[] {
    return value
      .split(',')
      .map((part) => part.trim().replace(/^['\"]|['\"]$/g, '').replace(/\s+/g, ' '))
      .filter(Boolean)
      .map((part) => `${prefix}:\"${part}\"`);
  }

  function titleToken(value: string): string {
    const title = value.trim().replace(/^['\"]|['\"]$/g, '').replace(/\"/g, ' ').replace(/\s+/g, ' ');
    return title ? `title:\"${title}\"` : '';
  }

  function effectiveQuery(): string {
    return [
      titleToken(q),
      ...FILTERS.flatMap((filter) => filterTokens(filters[filter.key], filter.prefix))
    ].filter(Boolean).join(' ');
  }

  $: hasActiveFilters = FILTERS.some((filter) => filters[filter.key].trim());

  const BASE_SORTS: [string, string][] = [
    ['recent', 'Recently added'],
    ['uploaded', 'Recently uploaded'],
    ['gallery', 'Gallery ID'],
    ['title', 'Title'],
    ['pages', 'Pages'],
    ['favorites', 'nH favorites'],
    ['random', 'Random']
  ];
  // "Recently added to category" only applies inside a selected category.
  $: SORTS = categoryId
    ? [...BASE_SORTS, ['category_added', 'Recently added to category'] as [string, string]]
    : BASE_SORTS;
  // Leaving the category makes its sort meaningless; fall back to the default.
  $: if (!categoryId && sort === 'category_added') sort = 'recent';
  const LANGS: [string, string][] = [
    ['all', 'All languages'],
    ['english', 'English'],
    ['japanese', 'Japanese'],
    ['chinese', 'Chinese'],
    ['korean', 'Korean']
  ];

  async function load() {
    loading = true;
    error = '';
    expandedSeries = new Set();
    seriesChapters = {};
    try {
      result = await mangaApi.library({
        q: effectiveQuery(),
        page,
        perPage: perPage === 'all' ? 0 : perPage,
        sort,
        language,
        favorites: favoritesOnly,
        category: categoryId
      });
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  function search() {
    page = 1;
    void load();
  }

  function onSearchKeydown(event: KeyboardEvent) {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    q = (event.currentTarget as HTMLInputElement).value;
    submitTitleSearch();
  }

  function submitTitleSearch() {
    search();
  }

  function applyFilters() {
    filterOpen = false;
    search();
  }

  function updateFilter(event: CustomEvent<{ key: string; value: string }>) {
    const key = event.detail.key as LibraryFilterKey;
    if (!FILTERS.some((filter) => filter.key === key)) return;
    filters = { ...filters, [key]: event.detail.value };
  }

  function setPage(next: number) {
    if (!result || next < 1 || next > result.page_count) return;
    page = next;
    void load().then(() => scrollRegion?.scrollTo({ top: 0, behavior: 'smooth' }));
  }

  function setPerPage() {
    page = 1;
    void load().then(() => scrollRegion?.scrollTo({ top: 0 }));
  }

  // Opening a category defaults its sort to the membership order; leaving one
  // (All / Favourites) restores the library-wide "recently added" default.
  function chooseCategory(id: number | null) {
    categoryId = id;
    favoritesOnly = false;
    sort = id ? 'category_added' : 'recent';
    search();
  }

  function chooseFavorites() {
    favoritesOnly = !favoritesOnly;
    categoryId = null;
    if (sort === 'category_added') sort = 'recent';
    search();
  }

  function clearFilters() {
    filters = {
      tags: '',
      categories: '',
      groups: '',
      artists: '',
      parodies: '',
      characters: ''
    };
    search();
  }

  async function toggleFavorite(card: MangaCard) {
    const res = await mangaApi.toggleFavorite(card.gallery_id);
    card.favorite = res.favorite ? 1 : 0;
    result = result;
  }

  async function togglePin(card: MangaCard) {
    const res = await mangaApi.togglePin(card.gallery_id);
    card.pinned = res.pinned ? 1 : 0;
    result = result;
  }

  function addTagToSearch(tag: MangaTag) {
    const fieldByCategory: Partial<Record<string, LibraryFilterKey>> = {
      tag: 'tags',
      category: 'categories',
      group: 'groups',
      artist: 'artists',
      parody: 'parodies',
      character: 'characters'
    };
    const key = fieldByCategory[tag.category] ?? 'tags';
    filters = {
      ...filters,
      [key]: filters[key] ? `${filters[key]}, ${tag.name}` : tag.name
    };
    filterOpen = true;
    search();
  }

  onMount(async () => {
    if (window.matchMedia('(max-width: 1023px)').matches) showSidebar = false;
    if (initialFilter) {
      filters = { ...filters, [initialFilter.key]: initialFilter.value };
      filterOpen = true;
      dispatch('filterSeedConsumed');
    }
    await tick();
    void load();
    try {
      categories = (await mangaApi.categories()).categories;
      topTags = (await mangaApi.topTags(50)).tags;
    } catch {
      /* sidebar extras are non-fatal */
    }
  });
</script>

<div class="flex h-full min-h-0 min-w-0 flex-col">
  <div class="border-b border-[#26263a] p-2 sm:p-3">
    <div class="library-toolbar flex min-w-0 flex-wrap items-center gap-2">
      <div class="relative shrink-0">
        <button
          class="relative grid h-8 w-8 place-items-center rounded-lg border border-[#2c2c40] text-gray-400 hover:text-purple-200"
          class:border-purple-500={filterOpen || hasActiveFilters}
          class:text-purple-200={filterOpen || hasActiveFilters}
          title="Structured library filters"
          aria-label="Structured library filters"
          aria-expanded={filterOpen}
          on:click|stopPropagation={() => (filterOpen = !filterOpen)}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true" class="h-4 w-4 fill-none stroke-current" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4 5h16l-6.5 7.2V18l-3 1.5v-7.3L4 5Z" />
          </svg>
          {#if hasActiveFilters}<span class="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-purple-400"></span>{/if}
        </button>
        <MangaFilterSheet
          open={filterOpen}
          title="Library filters"
          values={filters}
          hasActive={hasActiveFilters}
          on:close={() => (filterOpen = false)}
          on:change={updateFilter}
          on:clear={clearFilters}
          on:apply={applyFilters}
        />
      </div>
      <button
        class="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-[#2c2c40] text-gray-400 hover:text-purple-200"
        title="Toggle Library categories and top tags"
        aria-label="Toggle Library categories and top tags"
        aria-expanded={showSidebar}
        on:click={() => (showSidebar = !showSidebar)}
      >
        <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
          <rect x="3.5" y="4" width="17" height="16" rx="2" stroke-width="1.8" />
          <path d="M9 4v16M5.5 8h1M5.5 12h1M5.5 16h1" stroke-linecap="round" stroke-width="1.8" />
        </svg>
      </button>
      <form class="library-search min-w-0 flex-[1_1_20rem]" on:submit|preventDefault={submitTitleSearch}>
        <input
          class="w-full rounded-lg border border-[#2c2c40] bg-[#15151f] px-3 py-1.5 text-sm text-gray-200 placeholder-gray-600 focus:border-purple-500/60 focus:outline-none"
          placeholder={'Search titles or gallery number'}
          bind:value={q}
          on:keydown={onSearchKeydown}
        />
      </form>
      <div class="library-selects">
        <select class="library-sort min-w-0 flex-1 rounded-lg border border-[#2c2c40] bg-[#15151f] px-2 py-1.5 text-sm text-gray-300 sm:flex-none" bind:value={sort} on:change={search} aria-label="Sort Library">
          {#each SORTS as [value, label]}<option {value}>{label}</option>{/each}
        </select>
        <select class="library-language min-w-0 flex-1 rounded-lg border border-[#2c2c40] bg-[#15151f] px-2 py-1.5 text-sm text-gray-300 sm:flex-none" bind:value={language} on:change={search} aria-label="Filter Library by language">
          {#each LANGS as [value, label]}<option {value}>{label}</option>{/each}
        </select>
      </div>
    </div>
  </div>

  <div class="manga-library-layout flex min-h-0 min-w-0 flex-1">
  {#if showSidebar}
    <aside class="manga-library-sidebar shrink-0 overflow-y-auto border-[#26263a] p-3">
      <h3 class="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Categories</h3>
      <button
        class="mb-1 block w-full rounded px-2 py-1 text-left text-sm {categoryId === null && !favoritesOnly ? 'bg-purple-500/15 text-purple-100' : 'text-gray-400 hover:text-gray-200'}"
        on:click={() => chooseCategory(null)}
      >All {#if result}<span class="float-right text-xs text-gray-600">{result.stats.manga_count}</span>{/if}</button>
      <button
        class="mb-1 block w-full rounded px-2 py-1 text-left text-sm {favoritesOnly ? 'bg-purple-500/15 text-purple-100' : 'text-gray-400 hover:text-gray-200'}"
        on:click={chooseFavorites}
      >Favourites {#if result}<span class="float-right text-xs text-gray-600">{result.stats.favorite_count}</span>{/if}</button>
      {#each categories as category (category.id)}
        <button
          class="mb-1 block w-full rounded px-2 py-1 text-left text-sm {categoryId === category.id ? 'bg-purple-500/15 text-purple-100' : 'text-gray-400 hover:text-gray-200'}"
          on:click={() => chooseCategory(categoryId === category.id ? null : category.id)}
        >{category.name} <span class="float-right text-xs text-gray-600">{category.manga_count}</span></button>
      {/each}

      <h3 class="mb-2 mt-4 text-xs font-semibold uppercase tracking-wide text-gray-500">Top tags</h3>
      <div class="flex flex-wrap gap-1">
        {#each topTags as tag (tag.category + ':' + tag.name)}
          <button
            class="rounded-full border border-[#2c2c40] px-2 py-0.5 text-[11px] text-gray-300 hover:border-purple-400/60"
            style="color: {MANGA_TAG_COLORS[tag.category] ?? MANGA_TAG_COLORS.tag}"
            title="{tag.category} — {tag.count} manga"
            on:click={() => addTagToSearch(tag)}
          >{tag.name}</button>
        {/each}
      </div>
    </aside>
  {/if}

    <div class="flex min-h-0 min-w-0 flex-1 flex-col">
    <div class="min-h-0 flex-1 overflow-y-auto p-2 sm:p-3" bind:this={scrollRegion}>
      {#if error}
        <p class="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">{error}</p>
      {:else if result && result.manga.length === 0}
        <p class="p-6 text-center text-sm text-gray-500">
          {result.stats.manga_count === 0
            ? 'Library is empty — run a scan from Settings to index your folders.'
            : 'No manga match this search.'}
        </p>
      {:else if result}
        <div
          class="manga-cover-grid grid gap-3"
          class:cover-small={coverSize === 'small'}
          class:cover-large={coverSize === 'large'}
          class:opacity-60={loading}
        >
          {#each result.manga as card (card.id)}
            {@const seriesId = card.series_id}
            {@const isSeries = seriesId != null && (card.series_chapter_count ?? 0) > 1}
            <div
              class="group relative overflow-hidden rounded-xl border border-[#26263a] bg-[#14141c]"
              class:series-expanded={isSeries && seriesId != null && expandedSeries.has(seriesId)}
            >
              {#if isSeries && seriesId != null && expandedSeries.has(seriesId)}
                <div class="p-2">
                  <div class="mb-2 flex items-center justify-between gap-2">
                    <p class="min-w-0 flex-1 truncate text-sm font-semibold text-purple-100" title={card.series_title}>{card.series_title}</p>
                    <button
                      class="shrink-0 rounded-lg border border-[#2c2c40] px-2 py-1 text-xs text-gray-300 hover:border-purple-400/60"
                      title="Collapse series"
                      on:click={() => toggleSeries(seriesId)}
                    >‹ Collapse</button>
                  </div>
                  {#if seriesChapters[seriesId]}
                    <div class="series-strip flex gap-2 overflow-x-auto pb-1">
                      {#each seriesChapters[seriesId] as chapter, index (chapter.id)}
                        <button class="shrink-0 text-left" on:click={() => dispatch('open', { mangaId: chapter.id })}>
                          <div class="relative aspect-[7/10] w-24 overflow-hidden rounded-lg bg-[#101018]">
                            <img
                              src={mangaApi.coverUrl(chapter.gallery_id)}
                              alt=""
                              loading="lazy"
                              class="h-full w-full object-cover"
                              class:blur-xl={blur}
                              class:group-hover:blur-none={blur}
                            />
                            <span class="absolute left-1 top-1 rounded bg-black/70 px-1 py-0.5 text-[10px] font-semibold text-purple-100">{index + 1}</span>
                            {#if coverProgress !== 'off'}
                              {@const prog = progressInfo(chapter)}
                              {#if prog}
                                <div class="absolute inset-x-0 bottom-0 z-10 h-[3px] bg-black/45">
                                  <div class="h-full bg-white/90" style="width: {prog.percent}%"></div>
                                </div>
                              {/if}
                            {/if}
                          </div>
                          <p class="mt-1 w-24 truncate text-[11px] text-gray-300" title={chapter.title}>{chapter.title}</p>
                        </button>
                      {/each}
                    </div>
                  {:else}
                    <p class="px-1 py-6 text-center text-xs text-gray-500">Loading chapters…</p>
                  {/if}
                </div>
              {:else}
                <button class="block w-full text-left" on:click={() => dispatch('open', { mangaId: card.id })}>
                  <div class="relative aspect-[7/10] overflow-hidden bg-[#101018]">
                    <img
                      src={mangaApi.coverUrl(card.gallery_id)}
                      alt=""
                      loading="lazy"
                      class="h-full w-full object-cover transition duration-200"
                      class:blur-xl={blur}
                      class:group-hover:blur-none={blur}
                    />
                    {#if card.pinned}
                      <span class="absolute left-1.5 top-1.5 rounded bg-purple-500/80 px-1.5 py-0.5 text-[10px] font-bold text-white">PIN</span>
                    {/if}
                    <span class="absolute bottom-1.5 right-1.5 z-20 flex gap-1" aria-label="Manga languages">
                      {#each languageBadges(card.languages) as code}
                        <span class="rounded bg-black/70 px-1 py-0.5 text-[10px] font-semibold text-yellow-200">{code}</span>
                      {/each}
                    </span>
                    {#if coverProgress !== 'off'}
                      {@const prog = progressInfo(card)}
                      {#if prog}
                        {#if coverProgress === 'percent' || coverProgress === 'pages'}
                          <span
                            class="absolute bottom-1.5 left-1.5 z-20 rounded bg-black/70 px-1 py-0.5 text-[10px] font-semibold text-white"
                            title="Read {prog.read} of {prog.count} pages"
                          >{coverProgress === 'percent' ? `${prog.percent}%` : `${prog.read}/${prog.count}`}</span>
                        {/if}
                        <div
                          class="absolute inset-x-0 bottom-0 z-10 h-[3px] bg-black/45"
                          aria-label="Reading progress {prog.percent}%"
                        >
                          <div class="h-full bg-white/90" style="width: {prog.percent}%"></div>
                        </div>
                      {/if}
                    {/if}
                  </div>
                  <div class="p-2">
                    {#if isSeries}
                      <p class="truncate text-xs font-semibold text-gray-200" title={card.series_title}>{card.series_title}</p>
                      <p class="mt-0.5 text-[11px] text-gray-500">{card.series_chapter_count} chapters</p>
                    {:else}
                      <p class="truncate text-xs font-semibold text-gray-200" title={card.title}>{card.title}</p>
                      <p class="mt-0.5 text-[11px] text-gray-500">#{card.gallery_id}{card.pages ? ` — ${card.pages}p` : ''}</p>
                    {/if}
                  </div>
                </button>
                {#if isSeries}
                  <button
                    class="absolute right-1.5 top-1.5 z-30 flex items-center gap-0.5 rounded-full bg-purple-600/80 px-2 py-0.5 text-[11px] font-bold text-white hover:bg-purple-500"
                    title="Show {card.series_chapter_count} chapters"
                    aria-label="Expand series, {card.series_chapter_count} chapters"
                    on:click|stopPropagation={() => toggleSeries(seriesId)}
                  >{card.series_chapter_count} ›</button>
                {:else}
                  <div class="card-actions absolute right-1.5 top-1.5 flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                    <button
                      class="grid h-7 w-7 place-items-center rounded-full bg-black/70 text-sm"
                      class:text-pink-400={card.favorite}
                      class:text-gray-400={!card.favorite}
                      title="Favourite"
                      on:click|stopPropagation={() => toggleFavorite(card)}
                    >{card.favorite ? '♥' : '♡'}</button>
                    <button
                      class="grid h-7 w-7 place-items-center rounded-full bg-black/70 text-sm"
                      class:text-purple-300={card.pinned}
                      class:text-gray-400={!card.pinned}
                      title="Pin to top"
                      on:click|stopPropagation={() => togglePin(card)}
                    >📌</button>
                  </div>
                {/if}
              {/if}
            </div>
          {/each}
        </div>
      {:else}
        <p class="p-6 text-center text-sm text-gray-500">Loading library…</p>
      {/if}
    </div>
    {#if result}
      <div class="library-pager z-20 flex shrink-0 items-center justify-between gap-2 border-t border-[#3a3a52] bg-[#161620] px-2 py-2 text-sm sm:justify-center sm:px-3">
        <button class="rounded-lg border border-[#3a3a52] bg-[#1d1d29] px-3 py-1 text-gray-100 disabled:opacity-40" disabled={result.page <= 1} on:click={() => setPage(result!.page - 1)}>Prev</button>
        <span class="min-w-0 truncate text-center text-xs text-gray-200 sm:text-sm">{result.page} / {Math.max(1, result.page_count)} — {result.total} manga</span>
        <button class="rounded-lg border border-[#3a3a52] bg-[#1d1d29] px-3 py-1 text-gray-100 disabled:opacity-40" disabled={result.page >= result.page_count} on:click={() => setPage(result!.page + 1)}>Next</button>
        <label class="sr-only" for="library-per-page">Manga per page</label>
        <select
          id="library-per-page"
          aria-label="Manga per page"
          class="min-w-[3.5rem] rounded-lg border border-[#3a3a52] bg-[#1d1d29] px-2 py-1 text-xs text-white sm:ml-2 sm:text-sm"
          bind:value={perPage}
          on:change={setPerPage}
        >
          <option value={10}>10</option>
          <option value={20}>20</option>
          <option value={30}>30</option>
          <option value={50}>50</option>
          <option value="all">All</option>
        </select>
      </div>
    {/if}
    </div>
  </div>
</div>

<style>
  .library-toolbar {
    display: grid;
    grid-template-columns: 2rem 2rem minmax(0, 1fr);
    gap: 0.375rem;
  }

  .library-search { grid-column: 3 / -1; }
  .library-selects {
    grid-column: 1 / -1;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.375rem;
  }

  .manga-library-layout {
    flex-direction: column;
  }

  .manga-library-sidebar {
    width: 100%;
    max-height: min(14rem, 36vh);
    border-bottom-width: 1px;
  }

  .library-pager {
    padding-bottom: max(0.5rem, env(safe-area-inset-bottom));
  }

  .manga-cover-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    grid-auto-flow: row dense;
  }

  /* An expanded series takes a full-width row; dense flow backfills the gap it
     leaves so the surrounding covers stay tidy. */
  .series-expanded {
    grid-column: 1 / -1;
  }

  .series-strip {
    scrollbar-width: thin;
  }

  .manga-cover-grid.cover-small {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .manga-cover-grid.cover-large {
    grid-template-columns: repeat(1, minmax(0, 1fr));
  }

  @media (hover: none), (pointer: coarse) {
    .card-actions {
      opacity: 1;
    }
  }

  @media (min-width: 640px) {
    .library-toolbar { display: flex; gap: 0.5rem; }
    .library-selects { display: contents; }
    .library-search,
    .library-sort,
    .library-language { grid-column: auto; }
    .library-search { min-width: 12rem; }
    .manga-cover-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .manga-cover-grid.cover-small { grid-template-columns: repeat(4, minmax(0, 1fr)); }
    .manga-cover-grid.cover-large { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  }

  @media (min-width: 768px) {
    .manga-cover-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
    .manga-cover-grid.cover-small { grid-template-columns: repeat(5, minmax(0, 1fr)); }
    .manga-cover-grid.cover-large { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  }

  @media (min-width: 1280px) {
    .manga-cover-grid { grid-template-columns: repeat(6, minmax(0, 1fr)); }
    .manga-cover-grid.cover-small { grid-template-columns: repeat(8, minmax(0, 1fr)); }
    .manga-cover-grid.cover-large { grid-template-columns: repeat(5, minmax(0, 1fr)); }
  }

  @media (min-width: 1024px) {
    .manga-library-layout {
      flex-direction: row;
    }

    .manga-library-sidebar {
      width: 14rem;
      max-height: none;
      border-right-width: 1px;
      border-bottom-width: 0;
    }
  }

  @media (min-width: 1536px) {
    .manga-cover-grid { grid-template-columns: repeat(7, minmax(0, 1fr)); }
    .manga-cover-grid.cover-small { grid-template-columns: repeat(10, minmax(0, 1fr)); }
    .manga-cover-grid.cover-large { grid-template-columns: repeat(6, minmax(0, 1fr)); }
  }
</style>
