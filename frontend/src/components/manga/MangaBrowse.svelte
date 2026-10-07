<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import { languageBadges, mangaApi, MANGA_TAG_COLORS } from './mangaApi';
  import MangaFilterSheet from './MangaFilterSheet.svelte';

  type BrowseFilter = 'tags' | 'categories' | 'groups' | 'artists' | 'parodies' | 'characters';

  export let blur = true;
  export let enabled = false;
  export let coverSize: 'small' | 'current' | 'large' = 'current';
  export let ignoredTags: string[] = [];
  export let showIgnored = true;
  export let initialFilter: { key: BrowseFilter; value: string } | null = null;
  export let hideDownloaded = false;
  export let filterOpen = false;
  export let filterCount = 0;

  interface BrowseItem {
    id: number;
    media_id: string;
    english_title: string;
    japanese_title: string | null;
    thumbnail: string;
    num_pages: number;
    num_favorites: number;
    downloaded: boolean;
    downloaded_elsewhere: boolean;
    known_tags: { name: string; category: string }[];
    ignored_matches: string[];
  }

  const dispatch = createEventDispatcher<{ openRemote: { galleryId: number; forceCoverVisible: boolean } }>();

  let items: BrowseItem[] = [];
  let numPages = 1;
  let total = 0;
  let page = 1;
  let perPage: 10 | 20 | 30 | 50 | 'all' = 20;
  let query = '';
  let sort = 'recent';
  let language = 'all';
  let loading = false;
  let error = '';
  let toast = '';
  let scrollRegion: HTMLDivElement;
  let requestSerial = 0;
  let revealedIgnored = new Set<number>();

  const FILTERS: { key: BrowseFilter; label: string; prefix: string }[] = [
    { key: 'tags', label: 'Tags', prefix: 'tag' },
    { key: 'categories', label: 'Categories', prefix: 'category' },
    { key: 'groups', label: 'Groups', prefix: 'group' },
    { key: 'artists', label: 'Artists', prefix: 'artist' },
    { key: 'parodies', label: 'Parodies', prefix: 'parody' },
    { key: 'characters', label: 'Characters', prefix: 'character' }
  ];

  let filters: Record<BrowseFilter, string> = {
    tags: '',
    categories: '',
    groups: '',
    artists: '',
    parodies: '',
    characters: ''
  };

  $: filterCount = FILTERS.filter(({ key }) => filters[key].trim().length > 0).length
    + (sort !== 'recent' ? 1 : 0)
    + (language !== 'all' ? 1 : 0);
  $: hasActiveFilters = filterCount > 0;
  $: visibleItems = items.filter(
    (item) => (!hideDownloaded || (!item.downloaded && !item.downloaded_elsewhere)) && (showIgnored || !isIgnored(item))
  );

  function browseLanguageBadges(item: BrowseItem): string[] {
    return languageBadges(
      item.known_tags
        .filter((tag) => tag.category === 'language')
        .map((tag) => tag.name)
        .join(',')
    );
  }

  function filterTokens(value: string, prefix: string): string[] {
    return value
      .split(',')
      .map((entry) => entry.trim().replace(/^"|"$/g, '').replace(/"/g, '').replace(/\s+/g, ' '))
      .filter(Boolean)
      .map((entry) => `${prefix}:${entry.includes(' ') ? `"${entry}"` : entry}`);
  }

  function effectiveQuery(): string {
    const structured = FILTERS.flatMap(({ key, prefix }) => filterTokens(filters[key], prefix));
    return [query.trim(), ...structured].filter(Boolean).join(' ');
  }

  async function load(append = false): Promise<boolean> {
    if (!enabled) return false;
    if (append && loading) return false;
    const serial = append ? requestSerial : ++requestSerial;
    loading = true;
    error = '';
    try {
      const qs = new URLSearchParams({
        query: effectiveQuery(),
        page: String(page),
        per_page: String(perPage === 'all' ? 25 : perPage),
        sort,
        language
      });
      const response = await fetch(`/api/manga/browse?${qs}`);
      if (!response.ok) throw new Error((await response.json()).detail ?? `${response.status}`);
      const data = await response.json();
      if (serial !== requestSerial) return false;
      if (append) {
        const known = new Set(items.map((item) => item.id));
        items = [...items, ...data.items.filter((item: BrowseItem) => !known.has(item.id))];
      } else {
        items = data.items;
      }
      numPages = data.num_pages;
      total = data.total;
      page = data.page;
      return true;
    } catch (e) {
      if (serial !== requestSerial) return false;
      error = e instanceof Error ? e.message : String(e);
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

  function submitSearch() {
    const value = query.trim();
    if (/^\d{1,6}$/.test(value)) {
      dispatch('openRemote', { galleryId: Number(value), forceCoverVisible: false });
      return;
    }
    search();
  }

  function onSearchKeydown(event: KeyboardEvent) {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    query = (event.currentTarget as HTMLInputElement).value;
    submitSearch();
  }

  function clearFilters() {
    sort = 'recent';
    language = 'all';
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

  function updateFilter(event: CustomEvent<{ key: string; value: string }>) {
    const key = event.detail.key as BrowseFilter;
    if (!FILTERS.some((filter) => filter.key === key)) return;
    filters = { ...filters, [key]: event.detail.value };
  }

  function applyFilters() {
    filterOpen = false;
    search();
  }

  function ignoredMatches(item: BrowseItem): string[] {
    if (item.ignored_matches?.length) return item.ignored_matches;
    const ignored = new Set(ignoredTags.map((tag) => tag.trim().toLowerCase()).filter(Boolean));
    return item.known_tags
      .map((tag) => tag.name)
      .filter((name) => ignored.has(name.toLowerCase()));
  }

  function isIgnored(item: BrowseItem): boolean {
    return ignoredMatches(item).length > 0;
  }

  function openBrowseItem(item: BrowseItem) {
    const ignored = isIgnored(item);
    if (ignored && !revealedIgnored.has(item.id)) {
      revealedIgnored = new Set(revealedIgnored).add(item.id);
      return;
    }
    dispatch('openRemote', { galleryId: item.id, forceCoverVisible: ignored });
  }

  function setPage(next: number) {
    if (next < 1 || next > numPages) return;
    page = next;
    void load(false).then(() => scrollRegion?.scrollTo({ top: 0, behavior: 'smooth' }));
  }

  function setPerPage() {
    page = 1;
    items = [];
    void load(false).then(() => scrollRegion?.scrollTo({ top: 0 }));
  }

  async function loadMore() {
    if (perPage !== 'all' || loading || page >= numPages) return;
    const previous = page;
    page += 1;
    if (!(await load(true))) page = previous;
  }

  function observeInfinite(node: HTMLElement) {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) void loadMore();
      },
      { root: scrollRegion, rootMargin: '600px 0px' }
    );
    observer.observe(node);
    return { destroy: () => observer.disconnect() };
  }

  async function download(item: BrowseItem) {
    try {
      const response = await fetch(`/api/manga/download/${item.id}`, { method: 'POST' });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? `${response.status}`);
      toast = data.queued ? `Queued "${item.english_title || item.id}"` : data.reason;
      if (data.queued) item.downloaded = false;
      setTimeout(() => (toast = ''), 2500);
    } catch (e) {
      toast = e instanceof Error ? e.message : String(e);
      setTimeout(() => (toast = ''), 4000);
    }
  }

  function bestTitle(item: BrowseItem): string {
    return item.english_title || item.japanese_title || `#${item.id}`;
  }

  onMount(() => {
    if (initialFilter) {
      filters = { ...filters, [initialFilter.key]: initialFilter.value };
      filterOpen = true;
    }
    void load();
  });
</script>

{#if !enabled}
  <div class="grid h-full place-items-center p-6 text-center">
    <p class="max-w-md text-sm text-gray-500">
      Online nHentai access is disabled. Turn it on in <b>Settings → nHentai access</b> to browse.
    </p>
  </div>
{:else}
  <div class="flex h-full min-h-0 min-w-0 flex-col">
    <div class="relative border-b border-[#26263a] p-2 sm:p-3">
      <div class="browse-search-row flex min-w-0 items-center gap-2">
        <form class="min-w-0 flex-1" on:submit|preventDefault={submitSearch}>
          <input
            class="w-full rounded-lg border border-[#2c2c40] bg-[#15151f] px-3 py-1.5 text-sm text-gray-200 placeholder-gray-600 focus:border-purple-500/60 focus:outline-none"
            placeholder={'Search by title or gallery number'}
            bind:value={query}
            on:keydown={onSearchKeydown}
          />
        </form>
      </div>
      <MangaFilterSheet
        open={filterOpen}
        title="nHentai filters"
        values={filters}
        {sort}
        {language}
        hasActive={hasActiveFilters}
        on:close={() => (filterOpen = false)}
        on:change={updateFilter}
        on:sortChange={(event) => (sort = event.detail)}
        on:languageChange={(event) => (language = event.detail)}
        on:clear={clearFilters}
        on:apply={applyFilters}
      />
    </div>

    {#if toast}
      <p class="border-b border-purple-500/30 bg-purple-500/10 px-4 py-2 text-sm text-purple-200">{toast}</p>
    {/if}

    <div class="manga-browse-grid min-h-0 flex-1 overflow-y-auto p-2 sm:p-3" bind:this={scrollRegion}>
      {#if error}
        <p class="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">{error}</p>
      {:else if loading && items.length === 0}
        <p class="p-6 text-center text-sm text-gray-500">Loading nHentai…</p>
      {:else}
        <div
          class="manga-cover-grid grid gap-3"
          class:cover-small={coverSize === 'small'}
          class:cover-large={coverSize === 'large'}
          class:opacity-60={loading}
        >
          {#each visibleItems as item (item.id)}
            <div class="group relative overflow-hidden rounded-xl border border-[#26263a] bg-[#14141c]">
              <button
                class="block w-full text-left"
                aria-label={isIgnored(item)
                  ? revealedIgnored.has(item.id)
                    ? `${bestTitle(item)} — cover revealed, click to open manga information`
                    : `Blacklisted ${ignoredMatches(item).join(', ')} — click to reveal cover`
                  : undefined}
                on:click={() => openBrowseItem(item)}
              >
                <div class="relative aspect-[7/10] overflow-hidden bg-[#101018]">
                  <img
                    src={`/api/manga/nh-image?path=${encodeURIComponent(item.thumbnail)}&kind=thumb`}
                    alt=""
                    loading="lazy"
                    class="h-full w-full object-cover opacity-100 transition-[filter,opacity] duration-300"
                    class:blur-xl={blur && !isIgnored(item)}
                    class:opacity-0={isIgnored(item) && !revealedIgnored.has(item.id)}
                    class:group-hover:blur-none={blur && !isIgnored(item)}
                  />
                  {#if isIgnored(item)}
                    <span
                      class="blacklist-cover-overlay absolute inset-0 z-10 grid place-content-center gap-1 bg-black px-2 text-center"
                      class:is-revealed={revealedIgnored.has(item.id)}
                      aria-hidden={revealedIgnored.has(item.id)}
                    >
                      <span class="text-[10px] font-bold uppercase tracking-[0.18em] text-red-200">Blacklisted</span>
                      <span class="line-clamp-2 text-xs text-gray-200">{ignoredMatches(item).join(', ')}</span>
                    </span>
                  {/if}
                  {#if item.downloaded}
                    <span class="absolute right-1.5 top-1.5 rounded bg-green-600/90 px-1.5 py-0.5 text-[10px] font-bold text-white">✓</span>
                  {/if}
                  <span class="absolute bottom-1.5 left-1.5 rounded bg-black/75 px-1 py-0.5 text-[10px] text-gray-200">{item.num_pages}p</span>
                  <span class="absolute bottom-1.5 right-1.5 flex gap-1" aria-label="Manga languages">
                    {#each browseLanguageBadges(item) as code}
                      <span class="rounded bg-black/75 px-1 py-0.5 text-[10px] font-semibold text-yellow-200">{code}</span>
                    {/each}
                  </span>
                </div>
                <div class="p-2">
                  <p class="truncate text-xs font-semibold text-gray-200" title={bestTitle(item)}>{bestTitle(item)}</p>
                  <p class="mt-0.5 flex flex-wrap gap-1 text-[10px]">
                    {#each item.known_tags.slice(0, 3) as tag}
                      <span style="color: {MANGA_TAG_COLORS[tag.category] ?? MANGA_TAG_COLORS.tag}">{tag.name}</span>
                    {/each}
                  </p>
                </div>
              </button>
              {#if !item.downloaded}
                <button
                  class="download-action absolute left-1.5 top-1.5 grid h-8 w-8 place-items-center rounded-full bg-black/70 text-purple-200 opacity-0 transition-opacity hover:bg-purple-600/80 hover:text-white group-hover:opacity-100"
                  title="Download to library"
                  on:click|stopPropagation={() => download(item)}
                >⬇</button>
              {/if}
            </div>
          {/each}
        </div>
        {#if perPage === 'all' && page < numPages}
          <div class="mt-4 grid min-h-12 place-items-center text-xs text-gray-500" use:observeInfinite>
            {loading ? 'Loading more…' : 'Scroll for more'}
          </div>
        {/if}
      {/if}
    </div>
    <div class="browse-pager z-20 flex shrink-0 items-center justify-between gap-2 border-t border-[#3a3a52] bg-[#161620] px-2 py-2 text-sm sm:justify-center sm:px-3">
      {#if perPage === 'all'}
        <span class="min-w-0 flex-1 truncate text-center text-xs text-gray-200 sm:flex-none sm:text-sm">{items.length} / {total} loaded</span>
      {:else}
        <button class="rounded-lg border border-[#3a3a52] bg-[#1d1d29] px-3 py-1 text-gray-100 disabled:opacity-40" disabled={page <= 1} on:click={() => setPage(page - 1)}>Prev</button>
        <span class="min-w-0 truncate text-center text-xs text-gray-200 sm:text-sm">{page} / {numPages} — {total} manga</span>
        <button class="rounded-lg border border-[#3a3a52] bg-[#1d1d29] px-3 py-1 text-gray-100 disabled:opacity-40" disabled={page >= numPages} on:click={() => setPage(page + 1)}>Next</button>
      {/if}
      <label class="sr-only" for="browse-per-page">Manga per page</label>
      <select
        id="browse-per-page"
        aria-label="Browse manga per page"
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
  </div>
{/if}

<style>
  .blacklist-cover-overlay {
    opacity: 1;
    transform: translate3d(0, 0, 0);
    transition: opacity 300ms ease, transform 300ms cubic-bezier(0.22, 1, 0.36, 1);
  }

  .blacklist-cover-overlay.is-revealed {
    opacity: 0;
    pointer-events: none;
    transform: translate3d(0.75rem, 0, 0);
  }

  .browse-pager {
    padding-bottom: max(0.5rem, env(safe-area-inset-bottom));
  }

  .manga-cover-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .manga-cover-grid.cover-small {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .manga-cover-grid.cover-large {
    grid-template-columns: repeat(1, minmax(0, 1fr));
  }

  @media (hover: none), (pointer: coarse) {
    .download-action {
      opacity: 1;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .blacklist-cover-overlay {
      transition-duration: 1ms;
    }
  }

  @media (max-width: 639px) {
    .browse-search-row { gap: 0.375rem; }
  }

  @media (min-width: 640px) {
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

  @media (min-width: 1536px) {
    .manga-cover-grid { grid-template-columns: repeat(7, minmax(0, 1fr)); }
    .manga-cover-grid.cover-small { grid-template-columns: repeat(10, minmax(0, 1fr)); }
    .manga-cover-grid.cover-large { grid-template-columns: repeat(6, minmax(0, 1fr)); }
  }
</style>
