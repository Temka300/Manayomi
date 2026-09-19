<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { mangaApi, type MangaSettings } from './mangaApi';
  import AppDrawer from '../AppDrawer.svelte';
  import MangaLibrary from './MangaLibrary.svelte';
  import MangaBrowseProviders from './MangaBrowseProviders.svelte';
  import MangaDownloads from './MangaDownloads.svelte';
  import MangaDownloadsMenu from './MangaDownloadsMenu.svelte';
  import MangaHistory from './MangaHistory.svelte';
  import MangaSettingsPanel from './MangaSettings.svelte';
  import MangaTags from './MangaTags.svelte';
  import MangaDetailOverlay from './MangaDetailOverlay.svelte';
  import MangaDexDetailOverlay from './MangaDexDetailOverlay.svelte';

  type Tab = 'library' | 'browse' | 'tags' | 'history' | 'downloads' | 'settings';
  type DisplaySize = 'small' | 'current' | 'large';
  type MangaFilterKey = 'tags' | 'categories' | 'groups' | 'artists' | 'parodies' | 'characters';
  type MangaFilterSeed = { key: MangaFilterKey; value: string };

  const DISPLAY_SIZES: { value: DisplaySize; label: string }[] = [
    { value: 'small', label: 'Small' },
    { value: 'current', label: 'Current' },
    { value: 'large', label: 'Large' }
  ];

  function persistedDisplaySize(key: string): DisplaySize {
    if (typeof localStorage === 'undefined') return 'current';
    const value = localStorage.getItem(`manayomi:${key}`);
    return value === 'small' || value === 'large' ? value : 'current';
  }

  function persistedBool(key: string, fallback: boolean): boolean {
    if (typeof localStorage === 'undefined') return fallback;
    const value = localStorage.getItem(`manayomi:${key}`);
    return value === null ? fallback : value === 'true';
  }

  let tab: Tab = 'library';
  let blur = true;
  let settings: MangaSettings | null = null;
  $: coverProgress = settings?.cover_progress ?? 'bar';
  let coverSize = persistedDisplaySize('cover-size');
  let infoSize = persistedDisplaySize('info-size');
  let hideDownloaded = persistedBool('hide-downloaded', false);
  let displayOptionsOpen = false;
  let libraryKey = 0; // bump to remount the library after settings/scan changes
  let browseKey = 0;
  let libraryComponent: MangaLibrary | null = null;
  let showAppMenu = false;
  let downloadsOpen = false;
  let downloadsWidget: HTMLDivElement | null = null;
  let tabsElement: HTMLElement | null = null;
  let lastVisibleTab: Tab | null = null;
  let detailOrigin: 'library' | 'browse' = 'library';
  let forceDetailCoverVisible = false;
  let detailStartReading = false;

  let openMangaId: number | null = null;
  let openRemoteId: number | null = null;
  let openMangaDexTitleId: string | null = null;
  let openMangaDexChapterId: string | null = null;

  const TABS: [Tab, string][] = [
    ['library', 'Library'],
    ['browse', 'Browse'],
    ['tags', 'Tags'],
    ['history', 'History'],
    ['settings', 'Settings']
  ];

  function onSettingsChanged(event: CustomEvent<MangaSettings>) {
    settings = event.detail;
    blur = settings.blur_covers;
  }

  function switchTab(next: Tab) {
    if (tab === 'settings' && next === 'library') libraryKey += 1;
    displayOptionsOpen = false;
    downloadsOpen = false;
    tab = next;
  }

  function keepActiveTabVisible() {
    const activeTab = tabsElement?.querySelector<HTMLElement>('[aria-current="page"]');
    if (!activeTab) return;
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    activeTab.scrollIntoView({
      behavior: reducedMotion ? 'auto' : 'smooth',
      block: 'nearest',
      inline: 'nearest'
    });
  }

  function closeOverlay() {
    openMangaId = null;
    openRemoteId = null;
    openMangaDexTitleId = null;
    openMangaDexChapterId = null;
    forceDetailCoverVisible = false;
    detailStartReading = false;
  }

  function filterSeed(category: string, name: string): MangaFilterSeed {
    const fieldByCategory: Partial<Record<string, MangaFilterKey>> = {
      tag: 'tags',
      category: 'categories',
      group: 'groups',
      artist: 'artists',
      parody: 'parodies',
      character: 'characters'
    };
    return { key: fieldByCategory[category] ?? 'tags', value: name };
  }

  function onSearchTag(event: CustomEvent<{ category: string; name: string }>) {
    const seed = filterSeed(event.detail.category, event.detail.name);
    closeOverlay();
    if (detailOrigin === 'browse') {
      tab = 'browse';
      pendingBrowseFilter = seed;
      browseKey += 1;
    } else {
      tab = 'library';
      pendingLibraryFilter = seed;
      libraryKey += 1;
    }
  }

  let pendingLibraryFilter: MangaFilterSeed | null = null;
  let pendingBrowseFilter: MangaFilterSeed | null = null;

  function openLocal(mangaId: number, startReading = false) {
    detailOrigin = 'library';
    detailStartReading = startReading;
    openMangaId = mangaId;
  }

  function openRemote(galleryId: number, forceCoverVisible = false, startReading = false) {
    detailOrigin = 'browse';
    forceDetailCoverVisible = forceCoverVisible;
    detailStartReading = startReading;
    openRemoteId = galleryId;
  }

  function openMangaDex(titleId: string, forceCoverVisible = false) {
    detailOrigin = 'browse';
    forceDetailCoverVisible = forceCoverVisible;
    detailStartReading = false;
    openMangaDexTitleId = titleId;
    openMangaDexChapterId = null;
  }

  function openMangaDexChapter(chapterId: string, startReading = false) {
    detailOrigin = 'browse';
    detailStartReading = startReading;
    openMangaDexTitleId = null;
    openMangaDexChapterId = chapterId;
  }

  function openDownloadedTag(event: CustomEvent<{ name: string }>) {
    tab = 'library';
    pendingLibraryFilter = { key: 'tags', value: event.detail.name };
    libraryKey += 1;
  }

  function openHistoryItem(event: CustomEvent<{ source: string; externalId: string | null; galleryId: number; localMangaId: number | null; startReading: boolean }>) {
    const item = event.detail;
    if (item.localMangaId !== null) openLocal(item.localMangaId, item.startReading);
    else if (item.source === 'mangadex' && item.externalId) openMangaDexChapter(item.externalId, item.startReading);
    else openRemote(item.galleryId, false, item.startReading);
  }

  function openDownloadItem(event: CustomEvent<{ source: string; externalId: string | null; galleryId: number | null; localMangaId: number | null }>) {
    downloadsOpen = false;
    if (event.detail.localMangaId !== null) openLocal(event.detail.localMangaId);
    else if (event.detail.source === 'mangadex' && event.detail.externalId) openMangaDexChapter(event.detail.externalId);
    else if (event.detail.galleryId !== null) openRemote(event.detail.galleryId);
  }

  function onWindowClick(event: MouseEvent) {
    if (downloadsOpen && downloadsWidget && !downloadsWidget.contains(event.target as Node)) {
      downloadsOpen = false;
    }
  }

  function onWindowKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape' && downloadsOpen) downloadsOpen = false;
  }

  $: if (typeof localStorage !== 'undefined') localStorage.setItem('manayomi:cover-size', coverSize);
  $: if (typeof localStorage !== 'undefined') localStorage.setItem('manayomi:info-size', infoSize);
  $: if (typeof localStorage !== 'undefined') localStorage.setItem('manayomi:hide-downloaded', String(hideDownloaded));
  $: if (tabsElement && tab !== lastVisibleTab) {
    lastVisibleTab = tab;
    void tick().then(keepActiveTabVisible);
  }

  onMount(async () => {
    try {
      settings = await mangaApi.settings();
      blur = settings.blur_covers;
    } catch {
      /* defaults stand */
    }
  });
</script>

<svelte:window on:click={onWindowClick} on:keydown={onWindowKeydown} />

<div class="manga-shell flex h-full min-w-0 flex-col overflow-hidden">
  <div class="manga-header relative border-b border-[#26263a] px-2 py-2 sm:px-3">
    <div class="manga-brand flex min-w-0 items-center gap-2">
      <button
        type="button"
        class="grid h-9 w-9 shrink-0 place-items-center rounded-full text-gray-300 transition-colors hover:bg-purple-500/15 hover:text-purple-100"
        aria-label="Open Keivotos menu"
        title="Keivotos modules and settings"
        on:click={() => (showAppMenu = true)}
      >
        <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>
      <span class="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-purple-500/15 text-base">漫</span>
      <span class="truncate text-sm font-bold text-purple-100">Manayomi</span>
    </div>

    <nav class="manga-tabs flex min-w-0 gap-1 overflow-x-auto py-0.5" aria-label="Manayomi sections" bind:this={tabsElement}>
      {#each TABS as [value, label]}
        <button
          class="manga-tab shrink-0 whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-semibold transition-colors {tab === value ? 'bg-purple-500/15 text-purple-100' : 'text-gray-400 hover:text-gray-200'}"
          aria-current={tab === value ? 'page' : undefined}
          on:click={() => switchTab(value)}
        >{label}</button>
      {/each}
    </nav>

    <div class="manga-actions flex items-center justify-end gap-1">
      <button
        class="grid h-8 w-8 place-items-center rounded-lg border border-[#2c2c40] text-gray-400 transition-colors hover:text-purple-200"
        type="button"
        title="Manayomi display sizes"
        aria-label="Open Manayomi display size options"
        aria-expanded={displayOptionsOpen}
        on:click={() => (displayOptionsOpen = !displayOptionsOpen)}
      >
        <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
          <rect x="3.5" y="4" width="7" height="7" rx="1" stroke-width="1.7" />
          <rect x="13.5" y="4" width="7" height="7" rx="1" stroke-width="1.7" />
          <rect x="3.5" y="14" width="7" height="6" rx="1" stroke-width="1.7" />
          <path d="M14 16h6M14 19h4" stroke-linecap="round" stroke-width="1.7" />
        </svg>
      </button>
      <button
        class="grid h-8 w-8 place-items-center rounded-lg border border-[#2c2c40] text-sm transition-colors {blur ? 'text-gray-400' : 'text-purple-200'}"
        title={blur ? 'Covers blurred — click to reveal' : 'Covers visible — click to blur'}
        aria-label={blur ? 'Reveal manga covers' : 'Blur manga covers'}
        on:click={() => (blur = !blur)}
      >{blur ? '🙈' : '👁'}</button>
      {#if tab === 'browse'}
        <button
          class="grid h-8 w-8 place-items-center rounded-lg border transition-colors {hideDownloaded ? 'border-purple-500/50 bg-purple-500/15 text-purple-100' : 'border-[#2c2c40] text-gray-400 hover:text-purple-200'}"
          type="button"
          title={hideDownloaded ? 'Show downloaded manga' : 'Hide downloaded manga'}
          aria-label={hideDownloaded ? 'Show downloaded manga' : 'Hide downloaded manga'}
          aria-pressed={hideDownloaded}
          on:click={() => (hideDownloaded = !hideDownloaded)}
        >
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
            <path d="M12 3v10m0 0 3-3m-3 3-3-3M5 17h14" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" />
            <path d="M4 4l16 16" stroke-width="1.7" stroke-linecap="round" />
          </svg>
        </button>
      {/if}
      <div class="relative" bind:this={downloadsWidget}>
        <button
          class="flex h-8 items-center gap-1.5 rounded-lg border px-2 text-xs font-semibold transition-colors {downloadsOpen || tab === 'downloads' ? 'border-purple-500/50 bg-purple-500/15 text-purple-100' : 'border-[#2c2c40] text-gray-400 hover:text-purple-200'}"
          type="button"
          title="Latest downloads"
          aria-label="Open latest downloads"
          aria-expanded={downloadsOpen}
          on:click={() => {
            displayOptionsOpen = false;
            downloadsOpen = !downloadsOpen;
          }}
        >
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
            <path d="M12 3v11m0 0 4-4m-4 4-4-4M5 18h14" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <span class="hidden sm:inline">Downloads</span>
        </button>
        {#if downloadsOpen}
          <MangaDownloadsMenu
            {blur}
            on:close={() => (downloadsOpen = false)}
            on:showAll={() => {
              downloadsOpen = false;
              tab = 'downloads';
            }}
            on:open={openDownloadItem}
          />
        {/if}
      </div>
    </div>

    {#if displayOptionsOpen}
      <div class="display-options absolute right-2 top-full z-50 mt-2 rounded-xl border border-[#303046] bg-[#12121c] p-3 shadow-2xl shadow-black/50 sm:right-3">
        <p class="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">Display size</p>
        <div class="mb-3 flex items-center justify-between gap-3">
          <span class="text-sm text-gray-300">Cover cards</span>
          <div class="flex rounded-lg border border-[#2c2c40] p-0.5">
            {#each DISPLAY_SIZES as option (option.value)}
              <button
                class="rounded-md px-2 py-1 text-xs {coverSize === option.value ? 'bg-purple-500/20 text-purple-100' : 'text-gray-500 hover:text-gray-300'}"
                type="button"
                on:click={() => (coverSize = option.value)}
              >{option.label}</button>
            {/each}
          </div>
        </div>
        <div class="flex items-center justify-between gap-3">
          <span class="text-sm text-gray-300">Manga information</span>
          <div class="flex rounded-lg border border-[#2c2c40] p-0.5">
            {#each DISPLAY_SIZES as option (option.value)}
              <button
                class="rounded-md px-2 py-1 text-xs {infoSize === option.value ? 'bg-purple-500/20 text-purple-100' : 'text-gray-500 hover:text-gray-300'}"
                type="button"
                on:click={() => (infoSize = option.value)}
              >{option.label}</button>
            {/each}
          </div>
        </div>
      </div>
    {/if}
  </div>

  <div class="min-h-0 flex-1">
    {#if tab === 'library'}
      {#key libraryKey}
        <MangaLibrary
          bind:this={libraryComponent}
          {blur}
          {coverSize}
          {coverProgress}
          initialFilter={pendingLibraryFilter}
          on:open={(e) => openLocal(e.detail.mangaId)}
        />
      {/key}
    {:else if tab === 'browse'}
      {#key browseKey}
        <MangaBrowseProviders
          {blur}
          {coverSize}
          initialFilter={pendingBrowseFilter}
          ignoredTags={settings?.ignored_tags ?? []}
          showIgnored={settings?.show_ignored ?? true}
          enabled={settings?.nhentai_enabled ?? false}
          {hideDownloaded}
          on:openRemote={(e) => openRemote(e.detail.galleryId, e.detail.forceCoverVisible)}
          on:openMangaDex={(e) => openMangaDex(e.detail.titleId, e.detail.forceCoverVisible)}
        />
      {/key}
    {:else if tab === 'tags'}
      <MangaTags on:selectTag={openDownloadedTag} />
    {:else if tab === 'history'}
      <MangaHistory {blur} on:open={openHistoryItem} />
    {:else if tab === 'downloads'}
      <MangaDownloads {blur} {coverSize} on:open={(event) => openLocal(event.detail.mangaId)} />
    {:else}
      <div class="h-full overflow-y-auto">
        <MangaSettingsPanel on:settingsChanged={onSettingsChanged} />
      </div>
    {/if}
  </div>
</div>

{#if openMangaId !== null || openRemoteId !== null}
  <MangaDetailOverlay
    mangaId={openMangaId}
    remoteGalleryId={openRemoteId}
    blur={forceDetailCoverVisible ? false : blur}
    {infoSize}
    startReading={detailStartReading}
    on:close={closeOverlay}
    on:searchTag={onSearchTag}
  />
{/if}

{#if openMangaDexTitleId !== null || openMangaDexChapterId !== null}
  <MangaDexDetailOverlay
    titleId={openMangaDexTitleId}
    chapterId={openMangaDexChapterId}
    blur={forceDetailCoverVisible ? false : blur}
    {infoSize}
    startReading={detailStartReading}
    on:close={closeOverlay}
    on:openLocal={(event) => { closeOverlay(); openLocal(event.detail.mangaId); }}
  />
{/if}

{#if showAppMenu}
  <AppDrawer on:close={() => (showAppMenu = false)} />
{/if}

<style>
  .manga-header {
    display: grid;
    grid-template-areas:
      "brand actions"
      "tabs tabs";
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 0.5rem;
  }

  .manga-brand { grid-area: brand; }
  .manga-tabs {
    grid-area: tabs;
    scrollbar-width: none;
    scroll-padding-inline: 0.25rem;
    scroll-snap-type: x proximity;
    overscroll-behavior-inline: contain;
  }
  .manga-tabs::-webkit-scrollbar { display: none; }
  .manga-tab { scroll-snap-align: nearest; }
  .manga-actions { grid-area: actions; }

  .display-options {
    width: min(18rem, calc(100vw - 1rem));
  }

  @media (min-width: 768px) {
    .manga-header {
      grid-template-areas: "brand tabs actions";
      grid-template-columns: auto minmax(0, 1fr) auto;
      align-items: center;
    }
  }

  @media (max-width: 639px) {
    .manga-shell {
      padding-bottom: calc(3.35rem + env(safe-area-inset-bottom));
    }

    .manga-header {
      grid-template-areas: "brand actions";
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 0.25rem;
    }

    .manga-tabs {
      position: fixed;
      z-index: 60;
      right: 0;
      bottom: 0;
      left: 0;
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 0;
      min-height: calc(3.35rem + env(safe-area-inset-bottom));
      overflow: visible;
      border-top: 1px solid #303044;
      background: rgba(16, 16, 24, 0.97);
      padding: 0.35rem 0.25rem calc(0.35rem + env(safe-area-inset-bottom));
      box-shadow: 0 -0.5rem 1.5rem rgba(0, 0, 0, 0.32);
      backdrop-filter: blur(14px);
    }

    .manga-tab {
      min-width: 0;
      padding: 0.6rem 0.15rem;
      font-size: 0.7rem;
    }

    .manga-actions { gap: 0.2rem; }
  }
</style>
