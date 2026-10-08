<script lang="ts">
  import { createEventDispatcher, onDestroy, onMount, tick } from 'svelte';
  import { activeModule, filesNavigationRequest } from '../../lib/stores';
  import {
    mangaApi,
    MANGA_TAG_COLORS,
    type MangaCategory,
    type MangaDetail,
    type MangaDownloadItem,
    type MangaDownloadState,
    type MangaSeries,
    type MangaTag
  } from './mangaApi';

  /** Local mode: mangaId set. Remote mode: remoteGalleryId set (browse item). */
  export let mangaId: number | null = null;
  export let remoteGalleryId: number | null = null;
  export let blur = false;
  export let infoSize: 'small' | 'current' | 'large' = 'current';
  export let startReading = false;

  const dispatch = createEventDispatcher<{ close: void; searchTag: { category: string; name: string } }>();

  type ReaderMode = 'paged' | 'scroll';
  type ReaderDir = 'ltr' | 'rtl';
  type ReaderFit = 'height' | 'width';
  type ReaderQuality = 'fast' | 'original';

  function persisted(key: string, initial: string): string {
    if (typeof localStorage === 'undefined') return initial;
    return localStorage.getItem(`manayomi:${key}`) ?? initial;
  }
  function persist(key: string, value: string) {
    localStorage.setItem(`manayomi:${key}`, value);
  }
  function defaultReaderQuality(): ReaderQuality {
    if (typeof window === 'undefined') return 'original';
    return window.matchMedia('(max-width: 767px), (pointer: coarse)').matches ? 'fast' : 'original';
  }

  let detail: MangaDetail | null = null;
  let remote: any = null;
  let categories: MangaCategory[] = [];
  let categoryIds: number[] = [];
  let seriesList: MangaSeries[] = [];
  let newSeriesName = '';
  let error = '';
  let toast = '';
  let downloadState: MangaDownloadState | null = null;
  let downloadItem: MangaDownloadItem | null = null;
  let downloadTimer: ReturnType<typeof setTimeout> | null = null;
  let trackedDownload = false;
  let completionLoaded = false;
  let destroyed = false;

  let reading = false;
  let pageCount = 0;
  let pageIndex = 0;
  let pageUrls: string[] = [];
  let localReaderGalleryId: number | null = null;
  let localPageVersion = '';
  let prefetchedUrls: string[] = [];
  let readerMode: ReaderMode = persisted('reader-mode', 'paged') as ReaderMode;
  let readerDir: ReaderDir = persisted('reader-dir', 'ltr') as ReaderDir;
  let readerFit: ReaderFit = persisted('reader-fit', 'height') as ReaderFit;
  let readerQuality: ReaderQuality = persisted('reader-quality', defaultReaderQuality()) as ReaderQuality;
  let showOptions = false;
  let revealCover = false;
  let showAllTags = false;
  let touchStartX: number | null = null;
  let touchStartY: number | null = null;
  let suppressReaderClick = false;
  let progressTimer: ReturnType<typeof setTimeout> | null = null;
  let scrollFrame: number | null = null;
  let scrollReader: HTMLDivElement | null = null;

  $: persist('reader-mode', readerMode);
  $: persist('reader-dir', readerDir);
  $: persist('reader-fit', readerFit);
  $: persist('reader-quality', readerQuality);

  $: if (localReaderGalleryId !== null && localPageVersion) {
    const maxWidth = readerQuality === 'fast' ? 1600 : 0;
    pageUrls = Array.from({ length: pageCount }, (_, index) =>
      mangaApi.pageUrl(localReaderGalleryId!, index, localPageVersion, maxWidth)
    );
  }

  $: galleryId = detail?.gallery_id ?? remote?.id ?? null;
  $: title = detail?.title ?? (remote ? remote.title?.pretty || remote.title?.english || `#${remote.id}` : '');
  $: tags = (detail?.tags ?? (remote?.tags ?? []).map((t: any) => ({ name: t.name, category: t.type }))) as MangaTag[];
  $: coverUrl =
    detail !== null
      ? mangaApi.coverUrl(detail.gallery_id)
      : remote
        ? `/api/manga/nh-image?path=${encodeURIComponent(remote.cover.path)}&kind=thumb`
        : '';
  $: downloaded = detail !== null || remote?.downloaded === true;
  $: downloadProgress = downloadItem?.status === 'done'
    ? 100
    : downloadItem?.pages
      ? Math.min(100, Math.round((downloadItem.page / downloadItem.pages) * 100))
      : 0;

  async function loadLocal(localMangaId: number) {
    detail = await mangaApi.detail(localMangaId);
    categoryIds = detail.category_ids;
    const pages = await mangaApi.pageList(detail.gallery_id);
    pageCount = pages.pages;
    localReaderGalleryId = detail.gallery_id;
    localPageVersion = pages.version;
  }

  async function load() {
    try {
      if (mangaId !== null) {
        await loadLocal(mangaId);
      } else if (remoteGalleryId !== null) {
        const response = await fetch(`/api/manga/gallery/${remoteGalleryId}`);
        if (!response.ok) throw new Error((await response.json()).detail ?? `${response.status}`);
        const gallery = await response.json();
        if (gallery.local_manga_id) {
          await loadLocal(Number(gallery.local_manga_id));
          remote = gallery;
        } else {
          remote = gallery;
          localReaderGalleryId = null;
          localPageVersion = '';
          pageCount = remote.pages?.length ?? 0;
          pageUrls = (remote.pages ?? []).map(
            (page: any) => `/api/manga/nh-image?path=${encodeURIComponent(page.path)}&kind=image`
          );
        }
      }
      const loadedGalleryId = detail?.gallery_id ?? remote?.id ?? null;
      if (loadedGalleryId !== null) {
        const saved = (await mangaApi.readingProgress(loadedGalleryId)).progress;
        if (saved) pageIndex = Math.min(Math.max(0, saved.last_page), Math.max(0, pageCount - 1));
      }
      categories = (await mangaApi.categories()).categories;
      if (detail) seriesList = (await mangaApi.series()).series;
      if (startReading && pageCount > 0) {
        await enterReader();
      }
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }

  async function toggleFavorite() {
    if (!galleryId) return;
    const result = await mangaApi.toggleFavorite(galleryId);
    if (detail) detail.favorite = result.favorite ? 1 : 0;
    detail = detail;
  }

  async function togglePin() {
    if (!galleryId) return;
    const result = await mangaApi.togglePin(galleryId);
    if (detail) detail.pinned = result.pinned ? 1 : 0;
    detail = detail;
  }

  async function toggleCategory(category: MangaCategory) {
    if (!galleryId) return;
    const result = await mangaApi.toggleCategory(category.id, galleryId);
    categoryIds = result.member
      ? [...categoryIds, category.id]
      : categoryIds.filter((id) => id !== category.id);
  }

  // Series membership is keyed by gallery, so refetching the card is enough to
  // reflect a change; no need to re-read the pages.
  async function refreshSeriesState() {
    if (!detail) return;
    detail = await mangaApi.detail(detail.id);
    seriesList = (await mangaApi.series()).series;
  }

  async function addToExistingSeries(seriesId: number) {
    if (!detail || !seriesId) return;
    await mangaApi.addToSeries(seriesId, detail.gallery_id);
    await refreshSeriesState();
    toast = 'Added to series';
  }

  async function createSeriesFromThis() {
    if (!detail || !newSeriesName.trim()) return;
    await mangaApi.createSeries(newSeriesName.trim(), [detail.gallery_id]);
    newSeriesName = '';
    await refreshSeriesState();
    toast = 'Series created';
  }

  async function removeFromSeries() {
    if (!detail) return;
    await mangaApi.removeFromSeries(detail.gallery_id);
    await refreshSeriesState();
    toast = 'Removed from series';
  }

  async function setSeriesFirst() {
    if (!detail) return;
    await mangaApi.setSeriesFirst(detail.gallery_id);
    await refreshSeriesState();
    toast = 'Set as first chapter';
  }

  async function downloadRemote() {
    if (!remote) return;
    const response = await fetch(`/api/manga/download/${remote.id}`, { method: 'POST' });
    const data = await response.json();
    toast = response.ok ? (data.queued ? 'Queued for download' : data.reason) : (data.detail ?? 'Failed');
    if (response.ok && (data.queued || data.reason === 'Already queued' || data.reason === 'Already downloading')) {
      trackedDownload = true;
      await pollDownloads(false);
    }
    setTimeout(() => (toast = ''), 2500);
  }

  function activeDownload(state: MangaDownloadState): MangaDownloadItem | null {
    if (!galleryId) return null;
    if (state.current?.gallery_id === galleryId) return state.current;
    return state.queue.find((item) => item.gallery_id === galleryId) ?? null;
  }

  async function loadCompletedDownload() {
    if (completionLoaded || remoteGalleryId === null) return;
    completionLoaded = true;
    try {
      const response = await fetch(`/api/manga/gallery/${remoteGalleryId}`);
      if (!response.ok) return;
      const gallery = await response.json();
      if (!gallery.local_manga_id) return;
      remote = gallery;
      await loadLocal(Number(gallery.local_manga_id));
    } catch {
      /* The completed bar stays visible; a later Library refresh will reconcile. */
    }
  }

  async function pollDownloads(adoptActive: boolean) {
    if (remoteGalleryId === null || destroyed) return;
    if (downloadTimer) {
      clearTimeout(downloadTimer);
      downloadTimer = null;
    }
    try {
      downloadState = await mangaApi.downloads();
      const active = activeDownload(downloadState);
      if (adoptActive && active) trackedDownload = true;
      if (trackedDownload) {
        downloadItem = active
          ?? downloadState.recent.find((item) => item.gallery_id === galleryId)
          ?? downloadItem;
        if (downloadItem?.status === 'done') await loadCompletedDownload();
      }
    } catch {
      /* transient polling errors do not replace the detail content */
    } finally {
      if (!destroyed) downloadTimer = setTimeout(() => void pollDownloads(false), 750);
    }
  }

  function openInFiles() {
    if (!detail?.files_source_id || !detail.files_relative_path) return;
    filesNavigationRequest.set({
      sourceId: detail.files_source_id,
      relativePath: detail.files_relative_path,
      reveal: true
    });
    activeModule.set('files');
    dispatch('close');
  }

  async function enterReader() {
    if (pageCount === 0) return;
    reading = true;
    scheduleProgressSave();
    await tick();
    if (readerMode === 'scroll' && scrollReader) {
      const image = scrollReader.querySelectorAll('img')[pageIndex] as HTMLImageElement | undefined;
      if (image) scrollReader.scrollTop = Math.max(0, image.offsetTop);
    }
  }

  function openReader() {
    void enterReader();
  }

  function closeReader() {
    void saveProgress();
    reading = false;
  }

  function historyTitle(): string {
    return detail?.title ?? remote?.title?.pretty ?? remote?.title?.english ?? `#${galleryId}`;
  }

  function historyCoverPath(): string | null {
    return remote?.cover?.path ?? null;
  }

  async function saveProgress() {
    if (progressTimer) {
      clearTimeout(progressTimer);
      progressTimer = null;
    }
    if (!galleryId || pageCount <= 0) return;
    try {
      await mangaApi.saveReadingProgress(galleryId, {
        title: historyTitle(),
        cover_path: historyCoverPath(),
        page: pageIndex,
        page_count: pageCount
      });
    } catch {
      /* Reading remains uninterrupted; the next page change retries persistence. */
    }
  }

  function scheduleProgressSave() {
    if (progressTimer) clearTimeout(progressTimer);
    progressTimer = setTimeout(() => void saveProgress(), 180);
  }

  function prefetchAdjacent(urls: string[]) {
    if (typeof Image === 'undefined') return;
    for (const url of urls) {
      if (!url || prefetchedUrls.includes(url)) continue;
      const image = new Image();
      image.decoding = 'async';
      image.src = url;
      prefetchedUrls = [...prefetchedUrls.slice(-11), url];
    }
  }

  $: if (reading && pageUrls.length > 0) {
    prefetchAdjacent([
      pageUrls[pageIndex - 1],
      pageUrls[pageIndex + 1],
      pageUrls[pageIndex + 2]
    ].filter(Boolean));
  }

  function setPage(next: number) {
    const resolved = Math.min(Math.max(0, next), pageCount - 1);
    if (resolved === pageIndex) return;
    pageIndex = resolved;
    if (reading) scheduleProgressSave();
  }

  function onScrollReader() {
    if (!scrollReader || readerMode !== 'scroll' || scrollFrame !== null) return;
    scrollFrame = requestAnimationFrame(() => {
      scrollFrame = null;
      if (!scrollReader) return;
      const targetY = scrollReader.getBoundingClientRect().top + scrollReader.clientHeight * 0.3;
      const images = Array.from(scrollReader.querySelectorAll('img'));
      let visibleIndex = 0;
      for (let index = 0; index < images.length; index += 1) {
        if (images[index].getBoundingClientRect().top <= targetY) visibleIndex = index;
        else break;
      }
      setPage(visibleIndex);
    });
  }

  function turn(forward: boolean) {
    setPage(pageIndex + (forward ? 1 : -1));
  }

  function turnFromHorizontal(goRight: boolean) {
    // In RTL the "next page" is to the left.
    turn(readerDir === 'rtl' ? !goRight : goRight);
  }

  function onReaderClick(event: MouseEvent) {
    if (readerMode !== 'paged') return;
    if (suppressReaderClick) {
      suppressReaderClick = false;
      return;
    }
    const target = event.currentTarget as HTMLElement;
    const x = (event.clientX - target.getBoundingClientRect().left) / target.clientWidth;
    if (x < 0.33) turnFromHorizontal(false);
    else if (x > 0.67) turnFromHorizontal(true);
    else showOptions = !showOptions;
  }

  function onPagedWheel(event: WheelEvent) {
    if (readerMode !== 'paged') return;
    event.preventDefault();
    turn(event.deltaY > 0);
  }

  function onReaderTouchStart(event: TouchEvent) {
    if (readerMode !== 'paged' || event.touches.length !== 1) return;
    touchStartX = event.touches[0].clientX;
    touchStartY = event.touches[0].clientY;
  }

  function onReaderTouchEnd(event: TouchEvent) {
    if (touchStartX === null || touchStartY === null || event.changedTouches.length === 0) return;
    const touch = event.changedTouches[0];
    const deltaX = touch.clientX - touchStartX;
    const deltaY = touch.clientY - touchStartY;
    touchStartX = null;
    touchStartY = null;
    if (Math.abs(deltaX) < 48 || Math.abs(deltaX) <= Math.abs(deltaY) * 1.2) return;
    suppressReaderClick = true;
    turnFromHorizontal(deltaX < 0);
    setTimeout(() => (suppressReaderClick = false), 350);
  }

  function onKeydown(event: KeyboardEvent) {
    if (!reading) {
      if (event.key === 'Escape') dispatch('close');
      return;
    }
    if (event.key === 'Escape') closeReader();
    else if (event.key === 'ArrowRight') turnFromHorizontal(true);
    else if (event.key === 'ArrowLeft') turnFromHorizontal(false);
    else if (event.key === ' ' || event.key === 'ArrowDown') {
      if (readerMode === 'paged') {
        event.preventDefault();
        turn(true);
      }
    } else if (event.key === 'ArrowUp' && readerMode === 'paged') turn(false);
  }

  function formatDate(ms: number | null | undefined): string {
    return ms ? new Date(ms).toLocaleDateString() : '—';
  }
  function formatSize(bytes: number | null | undefined): string {
    if (!bytes) return '—';
    return bytes > 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.round(bytes / 1024)} KB`;
  }

  onMount(() => {
    void (async () => {
      await load();
      await pollDownloads(true);
    })();
  });
  onDestroy(() => {
    destroyed = true;
    if (downloadTimer) clearTimeout(downloadTimer);
    if (progressTimer) {
      clearTimeout(progressTimer);
      void saveProgress();
    }
    if (scrollFrame !== null) cancelAnimationFrame(scrollFrame);
  });

</script>

<svelte:window on:keydown={onKeydown} />

<div class="fixed inset-0 z-[80] overflow-y-auto bg-black/80 backdrop-blur-sm" role="dialog" aria-modal="true" tabindex="-1">
  {#if !reading}
    <button class="absolute inset-0 h-full w-full cursor-default" type="button" aria-label="Close manga information background" on:click={() => dispatch('close')}></button>
    <div
      class="manga-info-panel relative z-10 mx-auto my-2 rounded-2xl border border-[#2a2a3e] bg-[#101018] shadow-2xl sm:my-8"
      class:info-small={infoSize === 'small'}
      class:info-large={infoSize === 'large'}
    >
      <div class="mb-4 flex items-start justify-between gap-3">
        <button class="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-[#303040] text-gray-400 hover:text-purple-100" type="button" aria-label="Close manga information" on:click={() => dispatch('close')}>✕</button>
        <h2 class="min-w-0 flex-1 text-lg font-bold text-purple-100">{title}</h2>
      </div>

      {#if error}
        <p class="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">{error}</p>
      {:else}
        <div class="manga-info-layout flex flex-col gap-5 sm:flex-row sm:gap-6">
          <button class="manga-info-cover relative shrink-0 self-center overflow-hidden rounded-xl bg-black sm:self-start" aria-label={blur && !revealCover ? 'Reveal manga cover' : 'Manga cover'} on:click={() => (revealCover = !revealCover)}>
            {#if coverUrl}<img src={coverUrl} alt="" class="w-full transition duration-200" class:blur-xl={blur && !revealCover} />{/if}
          </button>
          <div class="manga-info-body min-w-0 flex-1">
            <dl class="manga-info-metadata grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
              <dt class="text-gray-500">Gallery</dt><dd class="text-gray-300">#{galleryId}</dd>
              <dt class="text-gray-500">Pages</dt><dd class="text-gray-300">{pageCount || detail?.pages || '—'}</dd>
              {#if detail}
                <dt class="text-gray-500">Uploaded</dt><dd class="text-gray-300">{formatDate(detail.upload_date)}</dd>
                <dt class="text-gray-500">Downloaded</dt><dd class="text-gray-300">{formatDate(detail.created_at)}</dd>
                <dt class="text-gray-500">File size</dt><dd class="text-gray-300">{formatSize(detail.file_size)}</dd>
              {:else if remote}
                <dt class="text-gray-500">nH favourites</dt><dd class="text-gray-300">{remote.num_favorites}</dd>
              {/if}
            </dl>

            <div class="manga-info-tags-shell">
              <div id="manga-info-tag-list" class="manga-info-tags flex flex-wrap gap-1" class:tags-expanded={showAllTags}>
                {#each tags as tag (tag.category + ':' + tag.name)}
                  <button
                    class="manga-tag-chip rounded-full border border-[#2c2c40] px-3 py-1 text-sm hover:border-purple-400/60"
                    style="color: {MANGA_TAG_COLORS[tag.category] ?? MANGA_TAG_COLORS.tag}"
                    title="Search this {tag.category} from the current Manayomi section"
                    on:click|stopPropagation={() => dispatch('searchTag', { category: tag.category, name: tag.name })}
                  >{tag.name}</button>
                {/each}
              </div>
              {#if tags.length > 8}
                <button
                  class="manga-info-tags-toggle mt-2 rounded-lg border border-[#343447] px-3 py-1.5 text-xs font-semibold text-purple-200 hover:border-purple-500/60"
                  type="button"
                  aria-controls="manga-info-tag-list"
                  aria-expanded={showAllTags}
                  on:click={() => (showAllTags = !showAllTags)}
                >{showAllTags ? 'Show fewer tags' : `Show all ${tags.length} tags`}</button>
              {/if}
            </div>

            <div class="manga-info-actions flex flex-wrap items-center gap-2 pt-1">
              <button
                class="icon-action grid h-10 w-10 shrink-0 place-items-center rounded-lg border text-white disabled:opacity-40 {downloaded ? 'border-purple-500 bg-purple-600 hover:bg-purple-500' : 'border-[#343447] bg-black hover:border-purple-500/60'}"
                disabled={pageCount === 0}
                title="Read manga"
                aria-label="Read manga"
                on:click={openReader}
              >
                <svg class="h-5 w-5 fill-current" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4.8v14.4c0 .8.9 1.3 1.6.9l11-7.2a1.05 1.05 0 0 0 0-1.8l-11-7.2c-.7-.4-1.6.1-1.6.9Z" /></svg>
              </button>
              {#if galleryId}
                <a
                  class="icon-action grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-[#343447] bg-[#171720] text-gray-200 hover:border-purple-500/60 hover:text-purple-100"
                  href={`https://nhentai.net/g/${galleryId}/`}
                  target="_blank"
                  rel="noreferrer"
                  title="Open on nHentai"
                  aria-label="Open on nHentai"
                >
                  <svg class="h-5 w-5 fill-none stroke-current" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5h5v5m0-5-9 9M19 13v5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5" /></svg>
                </a>
              {/if}
              {#if downloaded && detail}
                {#if detail.files_source_id && detail.files_relative_path}
                  <button class="icon-action grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-[#343447] bg-[#171720] text-gray-200 hover:border-purple-500/60 hover:text-purple-100" title="Open in Files" aria-label="Open in Files" on:click={openInFiles}>
                    <svg class="h-5 w-5 fill-none stroke-current" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.5 7.5h6l2 2h9v8.5a1.5 1.5 0 0 1-1.5 1.5H5A1.5 1.5 0 0 1 3.5 18V7.5Zm0 0V6A1.5 1.5 0 0 1 5 4.5h4l2 2h8A1.5 1.5 0 0 1 20.5 8" /></svg>
                  </button>
                {/if}
                <button
                  class="icon-action grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-[#343447] bg-white/15"
                  class:text-pink-400={detail.favorite}
                  class:text-black={!detail.favorite}
                  title={detail.favorite ? 'Remove from favourites' : 'Add to favourites'}
                  aria-label={detail.favorite ? 'Remove from favourites' : 'Add to favourites'}
                  on:click={toggleFavorite}
                >
                  <svg class="h-5 w-5 fill-current" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s-7.2-4.35-9.45-8.58C.62 8.8 2.35 4.5 6.52 4.08 8.9 3.84 10.6 5.1 12 6.8c1.4-1.7 3.1-2.96 5.48-2.72 4.17.42 5.9 4.72 3.97 8.34C19.2 16.65 12 21 12 21Z" /></svg>
                </button>
                <button
                  class="icon-action grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-[#343447] bg-white/15"
                  class:text-purple-300={detail.pinned}
                  class:text-black={!detail.pinned}
                  title={detail.pinned ? 'Unpin manga' : 'Pin manga'}
                  aria-label={detail.pinned ? 'Unpin manga' : 'Pin manga'}
                  on:click={togglePin}
                >
                  <svg class="h-5 w-5 fill-current" viewBox="0 0 24 24" aria-hidden="true"><path d="m14.8 3.2 6 6-2 2-1.2-1.2-3.1 3.1.7 3.7-1.4 1.4-3.6-3.6-4.4 4.4-1.4-1.4 4.4-4.4-3.6-3.6 1.4-1.4 3.7.7 3.1-3.1L12.8 5l2-1.8Z" /></svg>
                </button>
              {:else if remote && !remote.downloaded}
                <button class="download-action h-10 rounded-lg border border-purple-500/40 bg-purple-500/10 px-4 text-sm font-semibold text-purple-200 hover:bg-purple-500/20 disabled:opacity-50" disabled={trackedDownload && downloadItem?.status !== 'error'} on:click={downloadRemote}>Download</button>
              {/if}
            </div>

            {#if (trackedDownload && downloadItem) || toast || detail}
              <div class="manga-info-followup">
              {#if trackedDownload && downloadItem}
              <div class="rounded-xl border border-purple-500/25 bg-purple-500/5 p-3" aria-live="polite">
                <div class="mb-2 flex items-center justify-between gap-3 text-xs">
                  <span class="font-semibold capitalize {downloadItem.status === 'error' ? 'text-red-300' : downloadItem.status === 'done' ? 'text-green-300' : 'text-purple-200'}">{downloadItem.status}</span>
                  <span class="text-gray-400">{downloadItem.status === 'done' ? 'Complete' : downloadItem.pages ? `${downloadItem.page} / ${downloadItem.pages} pages` : 'Waiting'}</span>
                </div>
                <div class="h-2 overflow-hidden rounded-full bg-[#29293c]">
                  <div class="h-full rounded-full transition-[width] duration-300 {downloadItem.status === 'error' ? 'bg-red-500' : downloadItem.status === 'done' ? 'bg-green-500' : 'bg-purple-500'}" style="width: {downloadProgress}%"></div>
                </div>
                {#if downloadItem.error}<p class="mt-2 text-xs text-red-300">{downloadItem.error}</p>{/if}
              </div>
              {/if}
              {#if toast}<p class="text-xs text-purple-300">{toast}</p>{/if}

            {#if detail && categories.length > 0}
              <div class="flex flex-wrap items-center gap-2 pt-1">
                <span class="mr-1 text-sm text-gray-500">Categories:</span>
                {#each categories as category (category.id)}
                  <button
                    class="h-10 rounded-lg border px-4 text-sm font-semibold {categoryIds.includes(category.id) ? 'border-purple-400/70 bg-purple-500/15 text-purple-100' : 'border-[#343447] text-gray-400 hover:text-gray-200'}"
                    on:click={() => toggleCategory(category)}
                  >{category.name}</button>
                {/each}
              </div>
              {/if}

            {#if detail}
              <div class="flex flex-wrap items-center gap-2 pt-1">
                <span class="mr-1 text-sm text-gray-500">Series:</span>
                {#if detail.series_id != null}
                  <span class="rounded-lg border border-purple-400/50 bg-purple-500/10 px-3 py-1.5 text-sm text-purple-100" title="This chapter is part of a series">{detail.series_title} · {detail.series_chapter_count} ch</span>
                  <button class="h-10 rounded-lg border border-[#343447] px-3 text-sm text-gray-300 hover:text-gray-100" title="Show this chapter's cover as the series cover" on:click={setSeriesFirst}>Set as first</button>
                  <button class="h-10 rounded-lg border border-red-500/30 px-3 text-sm text-red-300 hover:bg-red-500/10" on:click={removeFromSeries}>Remove</button>
                {:else}
                  {#if seriesList.length > 0}
                    <select
                      class="h-10 rounded-lg border border-[#343447] bg-[#15151f] px-2 text-sm text-gray-200"
                      aria-label="Add this chapter to an existing series"
                      on:change={(e) => { const id = Number(e.currentTarget.value); e.currentTarget.value = ''; if (id) addToExistingSeries(id); }}
                    >
                      <option value="">Add to series…</option>
                      {#each seriesList as series (series.id)}<option value={series.id}>{series.title} ({series.chapter_count})</option>{/each}
                    </select>
                  {/if}
                  <input
                    class="h-10 w-40 rounded-lg border border-[#343447] bg-[#15151f] px-2 text-sm text-gray-200 placeholder-gray-600"
                    placeholder="New series name"
                    bind:value={newSeriesName}
                    on:keydown={(e) => e.key === 'Enter' && createSeriesFromThis()}
                  />
                  <button class="h-10 rounded-lg border border-purple-500/40 bg-purple-500/10 px-3 text-sm text-purple-200 hover:bg-purple-500/20" on:click={createSeriesFromThis}>Create</button>
                {/if}
              </div>
              {/if}
              </div>
            {/if}
          </div>
        </div>
      {/if}
    </div>
  {:else}
    <!-- Reader -->
    <div class="reader-shell fixed inset-0 z-[85] flex flex-col bg-black">
      <div class="reader-toolbar flex min-w-0 items-center gap-2 bg-black/80 px-2 py-2 text-sm text-gray-300 sm:px-3">
        <button class="shrink-0 rounded border border-[#2c2c40] px-2 py-1 text-xs" on:click={closeReader}>← Back</button>
        <span class="min-w-0 flex-1 truncate">{title}</span>
        <span class="shrink-0 whitespace-nowrap text-xs text-gray-500">{pageIndex + 1} / {pageCount}</span>
        <button class="grid h-7 w-7 shrink-0 place-items-center rounded border border-[#2c2c40] text-xs" aria-label="Reader options" aria-expanded={showOptions} on:click={() => (showOptions = !showOptions)}>⚙</button>
      </div>

      {#if showOptions}
        <div class="reader-options flex flex-wrap items-center gap-2 bg-[#101018] px-2 py-2 text-xs text-gray-300 sm:px-4">
          <div class="reader-option-group flex flex-none items-center gap-1 rounded-lg border border-[#242434] p-1">
            <span class="px-1 text-gray-500">Mode</span>
            <button class="flex-1 rounded px-2 py-1 sm:flex-none {readerMode === 'paged' ? 'bg-purple-500/20 text-purple-100' : ''}" on:click={() => (readerMode = 'paged')}>Paged</button>
            <button class="flex-1 whitespace-nowrap rounded px-2 py-1 sm:flex-none {readerMode === 'scroll' ? 'bg-purple-500/20 text-purple-100' : ''}" on:click={() => (readerMode = 'scroll')}>Vertical</button>
          </div>
          <div class="reader-option-group flex items-center gap-1 rounded-lg border border-[#242434] p-1">
            <span class="px-1 text-gray-500">Direction</span>
            <button class="rounded px-2 py-1 {readerDir === 'ltr' ? 'bg-purple-500/20 text-purple-100' : ''}" on:click={() => (readerDir = 'ltr')}>LTR</button>
            <button class="rounded px-2 py-1 {readerDir === 'rtl' ? 'bg-purple-500/20 text-purple-100' : ''}" on:click={() => (readerDir = 'rtl')}>RTL</button>
          </div>
          <div class="reader-option-group flex items-center gap-1 rounded-lg border border-[#242434] p-1">
            <span class="px-1 text-gray-500">Fit</span>
            <button class="rounded px-2 py-1 {readerFit === 'height' ? 'bg-purple-500/20 text-purple-100' : ''}" on:click={() => (readerFit = 'height')}>Height</button>
            <button class="rounded px-2 py-1 {readerFit === 'width' ? 'bg-purple-500/20 text-purple-100' : ''}" on:click={() => (readerFit = 'width')}>Width</button>
          </div>
          {#if localReaderGalleryId !== null}
            <div class="reader-option-group flex items-center gap-1 rounded-lg border border-[#242434] p-1">
              <span class="px-1 text-gray-500">Quality</span>
              <button class="rounded px-2 py-1 {readerQuality === 'fast' ? 'bg-purple-500/20 text-purple-100' : ''}" title="Phone-sized WebP for faster LAN reading" on:click={() => (readerQuality = 'fast')}>Fast</button>
              <button class="rounded px-2 py-1 {readerQuality === 'original' ? 'bg-purple-500/20 text-purple-100' : ''}" title="Original CBZ image" on:click={() => (readerQuality = 'original')}>Original</button>
            </div>
          {/if}
        </div>
      {/if}

      {#if readerMode === 'paged'}
        <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
        <div class="paged-reader min-h-0 flex-1 select-none overflow-auto" on:click={onReaderClick} on:wheel={onPagedWheel} on:touchstart={onReaderTouchStart} on:touchend={onReaderTouchEnd}>
          <div class="flex min-h-full items-center justify-center">
            <img
              src={pageUrls[pageIndex]}
              alt="page {pageIndex + 1}"
              class="paged-reader-image"
              class:fit-height={readerFit === 'height'}
              class:fit-width={readerFit === 'width'}
              draggable="false"
            />
          </div>
        </div>
        <div class="reader-slider flex items-center gap-3 bg-black/80 px-3 py-2 sm:px-4">
          <input
            type="range"
            min="0"
            max={Math.max(0, pageCount - 1)}
            value={pageIndex}
            class="flex-1 accent-purple-500"
            style={readerDir === 'rtl' ? 'direction: rtl' : ''}
            on:input={(e) => setPage(Number(e.currentTarget.value))}
          />
        </div>
      {:else}
        <div class="min-h-0 flex-1 overflow-y-auto" bind:this={scrollReader} on:scroll={onScrollReader}>
          <div class="mx-auto flex max-w-3xl flex-col">
            {#each pageUrls as url, index (index)}
              <img src={url} alt="page {index + 1}" loading="lazy" class={readerFit === 'width' ? 'w-full' : 'mx-auto max-w-full'} />
            {/each}
          </div>
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .manga-info-panel {
    width: calc(100% - 1rem);
    max-width: 64rem;
    padding: 1rem;
    --mobile-cover-width: 8rem;
  }

  .manga-info-panel.info-small {
    max-width: 52rem;
    padding: 0.75rem;
    --mobile-cover-width: 7rem;
  }

  .manga-info-panel.info-large {
    max-width: 76rem;
    padding: 1.25rem;
    --mobile-cover-width: 9rem;
  }

  .manga-info-body,
  .manga-info-followup {
    display: flex;
    min-width: 0;
    flex-direction: column;
    gap: 1rem;
  }

  .manga-info-tags-toggle { display: none; }

  .manga-info-cover {
    width: 16rem;
    aspect-ratio: 7 / 10;
  }

  .info-small .manga-info-cover {
    width: 12rem;
  }

  .info-large .manga-info-cover {
    width: 19rem;
  }

  .manga-info-cover :global(img) {
    height: 100%;
    object-fit: cover;
  }

  .manga-info-panel.info-small :global(.text-lg) {
    font-size: 1rem;
    line-height: 1.5rem;
  }

  .manga-info-panel.info-small :global(.text-sm) {
    font-size: 0.75rem;
    line-height: 1.1rem;
  }

  .manga-info-panel.info-large :global(.text-lg) {
    font-size: 1.5rem;
    line-height: 2rem;
  }

  .manga-info-panel.info-large :global(.text-sm) {
    font-size: 1rem;
    line-height: 1.5rem;
  }

  .manga-info-panel.info-large :global(.text-xs) {
    font-size: 0.875rem;
    line-height: 1.25rem;
  }

  .reader-shell {
    height: 100dvh;
  }

  .reader-toolbar {
    padding-top: calc(0.5rem + env(safe-area-inset-top));
  }

  .reader-slider {
    padding-bottom: calc(0.5rem + env(safe-area-inset-bottom));
  }

  .paged-reader {
    touch-action: pan-y pinch-zoom;
  }

  .paged-reader-image.fit-height {
    width: auto;
    max-width: 100%;
    max-height: calc(100dvh - 7rem);
  }

  .paged-reader-image.fit-width {
    width: 100%;
    height: auto;
  }

  @media (max-width: 639px) {
    .manga-info-layout {
      display: grid;
      grid-template-columns: var(--mobile-cover-width) minmax(0, 1fr);
      gap: 0.75rem;
      align-items: start;
    }

    .manga-info-body { display: contents; }

    .manga-info-cover,
    .info-small .manga-info-cover,
    .info-large .manga-info-cover {
      grid-column: 1;
      grid-row: 1;
      width: 100%;
      align-self: start;
    }

    .manga-info-metadata {
      grid-column: 2;
      grid-row: 1;
      column-gap: 0.625rem;
      font-size: 0.75rem;
      line-height: 1.1rem;
    }

    .manga-info-actions {
      grid-column: 1 / -1;
      grid-row: 2;
      justify-content: center;
      padding-top: 0;
    }

    .manga-info-followup {
      grid-column: 1 / -1;
      grid-row: 3;
      gap: 0.75rem;
    }

    .manga-info-tags-shell {
      grid-column: 1 / -1;
      grid-row: 4;
    }

    .manga-info-tags:not(.tags-expanded) .manga-tag-chip:nth-child(n + 9) {
      display: none;
    }

    .manga-info-tags-toggle { display: inline-flex; }

    .manga-tag-chip {
      padding: 0.25rem 0.625rem;
      font-size: 0.8125rem;
    }

    .manga-info-actions :global(button:not(.icon-action)) {
      min-width: min(8rem, 100%);
      flex: 1;
    }

    .manga-info-actions :global(.icon-action) {
      flex: none;
      min-width: 2.5rem;
    }
  }

  @media (min-width: 640px) {
    .manga-info-panel {
      width: calc(100% - 2rem);
      padding: 1.5rem;
    }

    .manga-info-panel.info-small {
      padding: 1rem;
    }

    .manga-info-panel.info-large {
      padding: 2rem;
    }
  }
</style>
