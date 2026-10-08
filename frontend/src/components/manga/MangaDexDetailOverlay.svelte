<script lang="ts">
  import { createEventDispatcher, onDestroy, onMount, tick } from 'svelte';
  import {
    mangaApi,
    type MangaDexChapter,
    type MangaDexTitle,
    type MangaDownloadItem,
    type MangaDownloadState
  } from './mangaApi';

  export let titleId: string | null = null;
  export let chapterId: string | null = null;
  export let blur = false;
  export let infoSize: 'small' | 'current' | 'large' = 'current';
  export let startReading = false;

  const dispatch = createEventDispatcher<{ close: void; openLocal: { mangaId: number } }>();

  type ReaderMode = 'paged' | 'scroll';
  type ReaderDir = 'ltr' | 'rtl';
  type ReaderFit = 'height' | 'width';
  type ReaderQuality = 'fast' | 'original';
  type DetailPanel = 'chapters' | 'info';

  function persisted(key: string, fallback: string): string {
    return typeof localStorage === 'undefined' ? fallback : localStorage.getItem(`manayomi:${key}`) ?? fallback;
  }

  function persist(key: string, value: string) {
    if (typeof localStorage !== 'undefined') localStorage.setItem(`manayomi:${key}`, value);
  }

  let title: MangaDexTitle | null = null;
  let chapters: MangaDexChapter[] = [];
  let chapterTotal = 0;
  let chapterOffset = 0;
  let language = 'all';
  let loading = true;
  let chapterLoading = false;
  let error = '';
  let chapterError = '';
  let toast = '';
  let detailPanel: DetailPanel = 'chapters';
  let revealCover = false;
  let selecting = false;
  let selected = new Set<string>();
  let queued = new Set<string>();
  let downloadState: MangaDownloadState | null = null;
  let downloadTimer: ReturnType<typeof setTimeout> | null = null;
  let destroyed = false;

  let reading = false;
  let currentChapter: MangaDexChapter | null = null;
  let pageCount = 0;
  let pageIndex = 0;
  let pageUrls: string[] = [];
  let localGalleryId: number | null = null;
  let localPageVersion = '';
  let readerMode = persisted('reader-mode', 'paged') as ReaderMode;
  let readerDir = persisted('reader-dir', 'ltr') as ReaderDir;
  let readerFit = persisted('reader-fit', 'height') as ReaderFit;
  let readerQuality = persisted('reader-quality', 'fast') as ReaderQuality;
  let showOptions = false;
  let scrollReader: HTMLDivElement | null = null;
  let touchStartX: number | null = null;
  let touchStartY: number | null = null;
  let suppressReaderClick = false;
  let progressTimer: ReturnType<typeof setTimeout> | null = null;
  let scrollFrame: number | null = null;

  $: persist('reader-mode', readerMode);
  $: persist('reader-dir', readerDir);
  $: persist('reader-fit', readerFit);
  $: persist('reader-quality', readerQuality);

  function coverUrl(size: 0 | 256 | 512 = 512): string {
    return title?.cover_filename ? mangaApi.mangaDexCoverUrl(title.id, title.cover_filename, size) : '';
  }

  function chapterLabel(chapter: MangaDexChapter): string {
    const parts: string[] = [];
    if (chapter.volume) parts.push(`Vol. ${chapter.volume}`);
    if (chapter.chapter) parts.push(`Ch. ${chapter.chapter}`);
    if (chapter.title) parts.push(chapter.title);
    return parts.join(' — ') || 'Unnumbered chapter';
  }

  function languageLabel(code: string): string {
    return new Intl.DisplayNames(['en'], { type: 'language' }).of(code) ?? code.toUpperCase();
  }

  function dateLabel(value: string | null): string {
    return value ? new Date(value).toLocaleDateString() : 'Unknown date';
  }

  async function loadChapters(reset = false) {
    if (!title) return;
    chapterLoading = true;
    chapterError = '';
    if (reset) {
      chapters = [];
      chapterOffset = 0;
      chapterTotal = 0;
    }
    try {
      const offset = reset ? 0 : chapterOffset;
      const result = await mangaApi.mangaDexChapters(title.id, language, 500, offset);
      chapters = reset ? result.items : [...chapters, ...result.items];
      chapterOffset = offset + result.items.length;
      chapterTotal = result.total;
      if (reset) selected = new Set();
    } catch (reason) {
      chapterError = reason instanceof Error ? reason.message : String(reason);
    } finally {
      chapterLoading = false;
    }
  }

  async function load() {
    loading = true;
    error = '';
    let requestedChapter: MangaDexChapter | null = null;
    try {
      if (chapterId) {
        const context = await mangaApi.mangaDexChapter(chapterId);
        title = context.title;
        requestedChapter = context.chapter;
      } else if (titleId) {
        title = await mangaApi.mangaDexTitle(titleId);
      }
      if (!title) throw new Error('MangaDex title not found.');
    } catch (reason) {
      error = reason instanceof Error ? reason.message : String(reason);
    } finally {
      loading = false;
    }
    if (!title) return;
    await loadChapters(true);
    if (requestedChapter && !chapters.some((chapter) => chapter.id === requestedChapter!.id)) {
      chapters = [requestedChapter, ...chapters];
    }
    if (requestedChapter && startReading) await openReader(requestedChapter);
  }

  function toggleSelected(chapter: MangaDexChapter) {
    const next = new Set(selected);
    if (next.has(chapter.id)) next.delete(chapter.id);
    else next.add(chapter.id);
    selected = next;
  }

  async function download(chapter: MangaDexChapter) {
    try {
      const result = await mangaApi.downloadMangaDexChapter(chapter.id);
      toast = result.queued ? `Queued ${chapterLabel(chapter)}` : result.reason ?? 'Not queued';
      if (result.queued || result.reason === 'Already queued' || result.reason === 'Already downloading') {
        queued = new Set(queued).add(chapter.id);
      }
    } catch (reason) {
      toast = reason instanceof Error ? reason.message : String(reason);
    }
    setTimeout(() => (toast = ''), 3500);
  }

  async function downloadSelected() {
    const targets = chapters.filter((chapter) => selected.has(chapter.id) && !chapter.downloaded && !chapter.external_url);
    for (const chapter of targets) await download(chapter);
    selecting = false;
    selected = new Set();
  }

  function downloadItem(chapter: MangaDexChapter): MangaDownloadItem | null {
    const all = [downloadState?.current, ...(downloadState?.queue ?? []), ...(downloadState?.recent ?? [])];
    return all.find((item) => item?.source === 'mangadex' && item.external_id === chapter.id) ?? null;
  }

  function progress(item: MangaDownloadItem | null): number {
    if (!item) return 0;
    if (item.status === 'done') return 100;
    return item.pages ? Math.min(100, Math.round((item.page / item.pages) * 100)) : 0;
  }

  async function pollDownloads() {
    if (destroyed) return;
    try {
      downloadState = await mangaApi.downloads();
      let changed = false;
      chapters = chapters.map((chapter) => {
        const item = downloadItem(chapter);
        if (item?.status === 'done' && !chapter.downloaded) {
          changed = true;
          return { ...chapter, downloaded: true };
        }
        return chapter;
      });
      if (changed && title) title.downloaded_chapters += 1;
    } catch {
      /* a transient poll failure does not replace title/chapter content */
    } finally {
      if (!destroyed) downloadTimer = setTimeout(() => void pollDownloads(), 750);
    }
  }

  function rebuildPageUrls() {
    if (!currentChapter) return;
    if (localGalleryId !== null) {
      const maxWidth = readerQuality === 'fast' ? 1600 : 0;
      pageUrls = Array.from({ length: pageCount }, (_, index) =>
        mangaApi.pageUrl(localGalleryId!, index, localPageVersion, maxWidth)
      );
    } else {
      const quality = readerQuality === 'fast' ? 'data-saver' : 'data';
      pageUrls = Array.from({ length: pageCount }, (_, index) =>
        mangaApi.mangaDexPageUrl(currentChapter!.id, index, quality)
      );
    }
  }

  async function openReader(chapter: MangaDexChapter) {
    if (chapter.external_url) {
      window.open(chapter.external_url, '_blank', 'noopener,noreferrer');
      return;
    }
    error = '';
    currentChapter = chapter;
    localGalleryId = null;
    localPageVersion = '';
    try {
      if (chapter.downloaded) {
        const context = await mangaApi.mangaDexChapter(chapter.id);
        if (context.local) {
          localGalleryId = context.local.gallery_id;
          const pages = await mangaApi.pageList(context.local.gallery_id);
          pageCount = pages.pages;
          localPageVersion = pages.version;
        }
      }
      if (localGalleryId === null) {
        const pages = await mangaApi.mangaDexPages(chapter.id);
        if (pages.external_url) {
          window.open(pages.external_url, '_blank', 'noopener,noreferrer');
          return;
        }
        pageCount = pages.pages;
      }
      if (pageCount <= 0) throw new Error('This chapter has no readable pages.');
      const saved = (await mangaApi.mangaDexProgress(chapter.id)).progress;
      pageIndex = saved ? Math.min(Math.max(0, saved.last_page), pageCount - 1) : 0;
      rebuildPageUrls();
      reading = true;
      scheduleProgressSave();
      await tick();
    } catch (reason) {
      error = reason instanceof Error ? reason.message : String(reason);
    }
  }

  function closeReader() {
    void saveProgress();
    reading = false;
    showOptions = false;
  }

  async function saveProgress() {
    if (!currentChapter || pageCount <= 0 || !title) return;
    try {
      await mangaApi.saveMangaDexProgress(currentChapter.id, {
        title: `${title.title} — ${chapterLabel(currentChapter)}`,
        cover_path: coverUrl(),
        page: pageIndex,
        page_count: pageCount
      });
    } catch {
      /* progress persistence must never interrupt reading */
    }
  }

  function scheduleProgressSave() {
    if (progressTimer) clearTimeout(progressTimer);
    progressTimer = setTimeout(() => {
      progressTimer = null;
      void saveProgress();
    }, 250);
  }

  function setPage(next: number) {
    pageIndex = Math.min(Math.max(0, next), Math.max(0, pageCount - 1));
    scheduleProgressSave();
  }

  function turn(forward: boolean) {
    const delta = readerDir === 'rtl' ? (forward ? -1 : 1) : (forward ? 1 : -1);
    setPage(pageIndex + delta);
  }

  function onReaderClick(event: MouseEvent) {
    if (suppressReaderClick) {
      suppressReaderClick = false;
      return;
    }
    const target = event.currentTarget as HTMLElement;
    const x = (event.clientX - target.getBoundingClientRect().left) / target.clientWidth;
    if (x < 0.35) turn(readerDir === 'rtl');
    else if (x > 0.65) turn(readerDir !== 'rtl');
  }

  function onWheel(event: WheelEvent) {
    if (Math.abs(event.deltaY) < 20) return;
    event.preventDefault();
    turn(event.deltaY > 0);
  }

  function onTouchStart(event: TouchEvent) {
    touchStartX = event.touches[0]?.clientX ?? null;
    touchStartY = event.touches[0]?.clientY ?? null;
  }

  function onTouchEnd(event: TouchEvent) {
    if (touchStartX === null || touchStartY === null) return;
    const touch = event.changedTouches[0];
    if (!touch) return;
    const deltaX = touch.clientX - touchStartX;
    const deltaY = touch.clientY - touchStartY;
    touchStartX = null;
    touchStartY = null;
    if (Math.abs(deltaX) > 45 && Math.abs(deltaX) > Math.abs(deltaY)) {
      suppressReaderClick = true;
      turn(deltaX < 0 ? readerDir !== 'rtl' : readerDir === 'rtl');
    }
  }

  function onScrollReader() {
    if (scrollFrame !== null) cancelAnimationFrame(scrollFrame);
    scrollFrame = requestAnimationFrame(() => {
      scrollFrame = null;
      const images = Array.from(scrollReader?.querySelectorAll('img') ?? []);
      const target = (scrollReader?.getBoundingClientRect().top ?? 0) + (scrollReader?.clientHeight ?? 0) * 0.3;
      let closest = pageIndex;
      let distance = Number.POSITIVE_INFINITY;
      images.forEach((image, index) => {
        const value = Math.abs(image.getBoundingClientRect().top - target);
        if (value < distance) { distance = value; closest = index; }
      });
      if (closest !== pageIndex) setPage(closest);
    });
  }

  function onKeydown(event: KeyboardEvent) {
    if (!reading) {
      if (event.key === 'Escape') dispatch('close');
      return;
    }
    if (event.key === 'Escape') closeReader();
    else if (readerMode === 'paged' && ['ArrowRight', 'PageDown', ' '].includes(event.key)) { event.preventDefault(); turn(true); }
    else if (readerMode === 'paged' && ['ArrowLeft', 'PageUp'].includes(event.key)) { event.preventDefault(); turn(false); }
    else if (event.key === 'Home') setPage(0);
    else if (event.key === 'End') setPage(pageCount - 1);
  }

  function setQuality(next: ReaderQuality) {
    readerQuality = next;
    rebuildPageUrls();
  }

  onMount(() => {
    void load();
    void pollDownloads();
  });

  onDestroy(() => {
    destroyed = true;
    if (downloadTimer) clearTimeout(downloadTimer);
    if (progressTimer) clearTimeout(progressTimer);
    if (scrollFrame !== null) cancelAnimationFrame(scrollFrame);
    if (reading) void saveProgress();
  });
</script>

<svelte:window on:keydown={onKeydown} />

<div class="fixed inset-0 z-[80] overflow-y-auto bg-black/80 backdrop-blur-sm" role="dialog" aria-modal="true" tabindex="-1">
  {#if !reading}
    <button class="absolute inset-0 h-full w-full cursor-default" type="button" aria-label="Close MangaDex information background" on:click={() => dispatch('close')}></button>
    <article class="md-detail relative z-10 mx-auto my-2 rounded-2xl border border-[#2a2a3e] bg-[#101018] shadow-2xl sm:my-8" class:info-small={infoSize === 'small'} class:info-large={infoSize === 'large'}>
      <header class="mb-4 flex items-start justify-between gap-3">
        <button class="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-[#303040] text-gray-400 hover:text-purple-100" type="button" aria-label="Close MangaDex information" on:click={() => dispatch('close')}>✕</button>
        <div class="min-w-0 flex-1">
          <p class="text-[10px] font-semibold uppercase tracking-[0.18em] text-orange-300/70">MangaDex</p>
          <h2 class="mt-1 text-xl font-bold text-purple-100">{title?.title ?? 'MangaDex title'}</h2>
        </div>
      </header>

      {#if loading}
        <p class="p-8 text-center text-sm text-gray-500">Loading title and chapters…</p>
      {:else if error && !title}
        <p class="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">{error}</p>
      {:else if title}
        <div class="mobile-detail-tabs" role="tablist" aria-label="MangaDex title sections">
          <button type="button" role="tab" aria-selected={detailPanel === 'chapters'} class:active={detailPanel === 'chapters'} on:click={() => (detailPanel = 'chapters')}>Chapters <span>{chapterTotal || chapters.length}</span></button>
          <button type="button" role="tab" aria-selected={detailPanel === 'info'} class:active={detailPanel === 'info'} on:click={() => (detailPanel = 'info')}>Info</button>
        </div>

        <div class="md-detail-layout">
        <section class="md-info-panel" class:phone-panel-hidden={detailPanel !== 'info'} aria-label="Manga information">
        <div class="md-summary grid gap-4">
          <button class="relative aspect-[7/10] overflow-hidden rounded-xl bg-black" aria-label={blur && !revealCover ? 'Reveal MangaDex cover' : 'MangaDex cover'} on:click={() => (revealCover = !revealCover)}>
            {#if coverUrl()}<img src={coverUrl()} alt="" class="h-full w-full object-cover transition-[filter] duration-200" class:blur-xl={blur && !revealCover} />{/if}
          </button>
          <div class="min-w-0 space-y-4">
            <dl class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
              <dt class="text-gray-500">Author</dt><dd class="text-gray-300">{title.authors.join(', ') || '—'}</dd>
              <dt class="text-gray-500">Artist</dt><dd class="text-gray-300">{title.artists.join(', ') || '—'}</dd>
              <dt class="text-gray-500">Status</dt><dd class="capitalize text-gray-300">{title.status || '—'}</dd>
              <dt class="text-gray-500">Year</dt><dd class="text-gray-300">{title.year ?? '—'}</dd>
              <dt class="text-gray-500">Rating</dt><dd class="capitalize text-gray-300">{title.content_rating || '—'}</dd>
              <dt class="text-gray-500">Saved</dt><dd class="text-gray-300">{title.downloaded_chapters} chapters</dd>
            </dl>
            {#if title.description}<p class="whitespace-pre-line text-sm leading-6 text-gray-300">{title.description}</p>{/if}
            <div class="flex flex-wrap gap-1.5">
              {#each title.tags as tag (tag.id)}<span class="rounded-full border border-[#343447] px-2.5 py-1 text-xs text-purple-200">{tag.name}</span>{/each}
            </div>
            <div class="flex flex-wrap gap-2">
              <a class="rounded-lg border border-[#343447] px-3 py-2 text-sm font-semibold text-gray-200 hover:border-orange-400/50" href={`https://mangadex.org/title/${title.id}`} target="_blank" rel="noreferrer">Open on MangaDex</a>
            </div>
          </div>
        </div>
        </section>

        <section class="md-chapter-panel" class:phone-panel-hidden={detailPanel !== 'chapters'} aria-labelledby="mangadex-chapters-title">
          <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 id="mangadex-chapters-title" class="font-semibold text-purple-100">Chapters</h3>
              <p class="text-xs text-gray-600">{chapters.length} of {chapterTotal} · translations and groups stay separate</p>
            </div>
            <div class="flex flex-wrap items-center justify-end gap-1.5">
              <select class="rounded-lg border border-[#343447] bg-[#15151f] px-2 py-1.5 text-sm text-gray-200" bind:value={language} on:change={() => void loadChapters(true)}>
                <option value="all">All languages</option><option value="en">English</option><option value="ja">Japanese</option><option value="ko">Korean</option><option value="zh">Chinese</option><option value="es">Spanish</option><option value="fr">French</option><option value="pt-br">Portuguese (BR)</option>
              </select>
              <button class="rounded-lg border border-purple-500/40 bg-purple-500/10 px-2.5 py-1.5 text-xs font-semibold text-purple-200 hover:bg-purple-500/20" on:click={() => (selecting = !selecting)}>{selecting ? 'Cancel' : 'Select downloads'}</button>
              {#if selecting && selected.size > 0}<button class="rounded-lg bg-purple-600 px-2.5 py-1.5 text-xs font-semibold text-white hover:bg-purple-500" on:click={downloadSelected}>Queue {selected.size}</button>{/if}
            </div>
          </div>
          {#if chapterError}<div class="mb-3 flex items-center justify-between gap-2 rounded-lg border border-red-500/30 bg-red-500/5 p-2 text-xs text-red-300"><span>{chapterError}</span><button class="shrink-0 rounded border border-red-400/30 px-2 py-1" on:click={() => void loadChapters(true)}>Retry</button></div>{/if}
          {#if error}<p class="mb-3 rounded-lg border border-red-500/30 bg-red-500/5 p-2 text-xs text-red-300">{error}</p>{/if}
          {#if toast}<p class="mb-3 rounded-lg border border-purple-500/30 bg-purple-500/10 p-2 text-xs text-purple-200">{toast}</p>{/if}
          {#if chapterLoading && chapters.length === 0}
            <p class="chapter-state">Loading chapters…</p>
          {:else if !chapterLoading && chapters.length === 0}
            <div class="chapter-state"><strong>No public chapters found.</strong><span>Try another translation language or retry the MangaDex feed.</span><button on:click={() => void loadChapters(true)}>Retry</button></div>
          {:else}
          <div class="chapter-list space-y-2">
            {#each chapters as chapter, index (chapter.id)}
              {#if index === 0 || chapters[index - 1].volume !== chapter.volume}
                <h4 class="sticky top-0 z-[1] bg-[#101018]/95 py-1 text-xs font-bold uppercase tracking-wide text-gray-500">{chapter.volume ? `Volume ${chapter.volume}` : 'No volume'}</h4>
              {/if}
              {@const item = downloadItem(chapter)}
              <div class="chapter-row rounded-xl border border-[#29293b] bg-[#14141d] p-3">
                <div class="flex min-w-0 items-start gap-3">
                  {#if selecting}<input class="mt-1 accent-purple-500" type="checkbox" checked={selected.has(chapter.id)} disabled={chapter.downloaded || !!chapter.external_url} aria-label={`Select ${chapterLabel(chapter)}`} on:change={() => toggleSelected(chapter)} />{/if}
                  <div class="min-w-0 flex-1">
                    <strong class="block text-sm text-gray-100">{chapterLabel(chapter)}</strong>
                    <p class="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-gray-500">
                      <span>{languageLabel(chapter.translated_language)}</span>
                      <span>{chapter.scanlation_groups.join(', ') || 'No scanlation group'}</span>
                      <span>{chapter.pages || '—'} pages</span>
                      <span>{dateLabel(chapter.publish_at)}</span>
                    </p>
                    {#if item}
                      <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-[#29293c]" title={`${item.status}: ${item.page}/${item.pages}`}><div class="h-full rounded-full {item.status === 'error' ? 'bg-red-500' : item.status === 'done' ? 'bg-green-500' : 'bg-purple-500'}" style={`width:${progress(item)}%`}></div></div>
                      {#if item.error}<p class="mt-1 text-[11px] text-red-300">{item.error}</p>{/if}
                    {/if}
                  </div>
                  <div class="flex shrink-0 gap-1.5">
                    {#if chapter.external_url}
                      <a class="rounded-lg border border-orange-500/35 px-2.5 py-1.5 text-xs font-semibold text-orange-200" href={chapter.external_url} target="_blank" rel="noreferrer">Publisher</a>
                    {:else}
                      <button class="rounded-lg border border-[#3a3a4e] px-2.5 py-1.5 text-xs font-semibold text-gray-200 hover:border-purple-500/60" on:click={() => openReader(chapter)}>Read</button>
                      {#if !chapter.downloaded}
                        <button class="rounded-lg border border-purple-500/40 bg-purple-500/10 px-2.5 py-1.5 text-xs font-semibold text-purple-200 disabled:opacity-40" disabled={item?.status === 'queued' || item?.status === 'downloading'} on:click={() => download(chapter)}>Download</button>
                      {:else}<span class="rounded-lg bg-green-500/10 px-2.5 py-1.5 text-xs font-semibold text-green-300">Saved</span>{/if}
                    {/if}
                  </div>
                </div>
              </div>
            {/each}
          </div>
          {/if}
          {#if chapterOffset < chapterTotal}<button class="mx-auto mt-4 block rounded-lg border border-[#343447] px-4 py-2 text-sm text-gray-300 disabled:opacity-50" disabled={chapterLoading} on:click={() => void loadChapters(false)}>{chapterLoading ? 'Loading…' : 'Load more chapters'}</button>{/if}
        </section>
        </div>
        <p class="mt-5 text-center text-[10px] text-gray-600">Manga metadata and page delivery by MangaDex. Chapter credits remain attached to their scanlation groups.</p>
      {/if}
    </article>
  {:else}
    <div class="reader-shell fixed inset-0 z-[85] flex flex-col bg-black">
      <div class="reader-toolbar flex min-w-0 items-center gap-2 bg-black/80 px-2 py-2 text-sm text-gray-300 sm:px-3">
        <button class="shrink-0 rounded border border-[#2c2c40] px-2 py-1 text-xs" on:click={closeReader}>← Back</button>
        <span class="min-w-0 flex-1 truncate">{title?.title} — {currentChapter ? chapterLabel(currentChapter) : ''}</span>
        <span class="shrink-0 text-xs text-gray-500">{pageIndex + 1} / {pageCount}</span>
        <button class="grid h-7 w-7 shrink-0 place-items-center rounded border border-[#2c2c40] text-xs" aria-label="Reader options" aria-expanded={showOptions} on:click={() => (showOptions = !showOptions)}>⚙</button>
      </div>
      {#if showOptions}
        <div class="reader-options flex flex-wrap items-center gap-2 bg-[#101018] px-2 py-2 text-xs text-gray-300 sm:px-4">
          <div class="option-group"><span>Mode</span><button class:active={readerMode === 'paged'} on:click={() => (readerMode = 'paged')}>Paged</button><button class:active={readerMode === 'scroll'} on:click={() => (readerMode = 'scroll')}>Vertical</button></div>
          <div class="option-group"><span>Direction</span><button class:active={readerDir === 'ltr'} on:click={() => (readerDir = 'ltr')}>LTR</button><button class:active={readerDir === 'rtl'} on:click={() => (readerDir = 'rtl')}>RTL</button></div>
          <div class="option-group"><span>Fit</span><button class:active={readerFit === 'height'} on:click={() => (readerFit = 'height')}>Height</button><button class:active={readerFit === 'width'} on:click={() => (readerFit = 'width')}>Width</button></div>
          <div class="option-group"><span>Quality</span><button class:active={readerQuality === 'fast'} on:click={() => setQuality('fast')}>Fast</button><button class:active={readerQuality === 'original'} on:click={() => setQuality('original')}>Original</button></div>
        </div>
      {/if}
      {#if readerMode === 'paged'}
        <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
        <div class="paged-reader min-h-0 flex-1 select-none overflow-auto" on:click={onReaderClick} on:wheel={onWheel} on:touchstart={onTouchStart} on:touchend={onTouchEnd}>
          <div class="flex min-h-full items-center justify-center"><img src={pageUrls[pageIndex]} alt={`page ${pageIndex + 1}`} class="paged-image" class:fit-height={readerFit === 'height'} class:fit-width={readerFit === 'width'} draggable="false" /></div>
        </div>
        <div class="reader-slider flex items-center gap-3 bg-black/80 px-3 py-2"><input class="flex-1 accent-purple-500" style={readerDir === 'rtl' ? 'direction:rtl' : ''} type="range" min="0" max={Math.max(0, pageCount - 1)} value={pageIndex} on:input={(event) => setPage(Number(event.currentTarget.value))} /></div>
      {:else}
        <div class="min-h-0 flex-1 overflow-y-auto" bind:this={scrollReader} on:scroll={onScrollReader}><div class="mx-auto flex max-w-3xl flex-col">{#each pageUrls as url, index (index)}<img src={url} alt={`page ${index + 1}`} loading="lazy" class={readerFit === 'width' ? 'w-full' : 'mx-auto max-w-full'} />{/each}</div></div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .md-detail { display:flex; width:calc(100% - 1rem); max-width:76rem; max-height:calc(100dvh - 1rem); flex-direction:column; overflow:hidden; padding:1rem; }
  .md-detail.info-small { max-width:58rem; padding:.75rem; }
  .md-detail.info-large { max-width:80rem; padding:1.25rem; }
  .md-detail-layout { display:grid; min-height:0; flex:1; grid-template-columns:minmax(18rem,23rem) minmax(0,1fr); gap:1rem; }
  .md-detail.info-small .md-detail-layout { grid-template-columns:minmax(16rem,20rem) minmax(0,1fr); }
  .md-detail.info-large .md-detail-layout { grid-template-columns:minmax(20rem,26rem) minmax(0,1fr); }
  .md-info-panel, .md-chapter-panel { min-height:0; overflow-y:auto; padding-right:.2rem; }
  .md-info-panel { border-right:1px solid #29293b; padding-right:1rem; }
  .md-summary { grid-template-columns:minmax(0,1fr); }
  .md-summary > :global(button) { width:min(11rem,55%); margin-inline:auto; }
  .chapter-list { padding-right:.15rem; }
  .chapter-state { display:grid; min-height:10rem; place-content:center; gap:.4rem; border:1px dashed #303044; border-radius:.75rem; padding:1rem; text-align:center; color:#777788; font-size:.75rem; }
  .chapter-state strong { color:#d1d5db; font-size:.875rem; }
  .chapter-state button { justify-self:center; border:1px solid #3a3a4e; border-radius:.45rem; padding:.35rem .75rem; color:#e5e7eb; }
  .mobile-detail-tabs { display:none; }
  .reader-shell { height:100dvh; }
  .reader-toolbar { padding-top:calc(.5rem + env(safe-area-inset-top)); }
  .reader-slider { padding-bottom:calc(.5rem + env(safe-area-inset-bottom)); }
  .paged-reader { touch-action:pan-y pinch-zoom; }
  .paged-image.fit-height { width:auto; max-width:100%; max-height:calc(100dvh - 7rem); }
  .paged-image.fit-width { width:100%; height:auto; }
  .option-group { display:flex; align-items:center; gap:.25rem; border:1px solid #242434; border-radius:.5rem; padding:.25rem; }
  .option-group span { padding:0 .25rem; color:#6b7280; }
  .option-group button { border-radius:.3rem; padding:.25rem .5rem; }
  .option-group button.active { background:rgba(168,85,247,.2); color:#f3e8ff; }
  @media (max-width:639px) {
    .md-detail { height:calc(100dvh - 1rem); padding:.75rem; }
    .md-detail > :global(header) { margin-bottom:.5rem; }
    .md-detail-layout { display:block; min-height:0; overflow:hidden; }
    .md-info-panel, .md-chapter-panel { height:100%; overflow-y:auto; padding-right:.1rem; }
    .md-info-panel { border-right:0; }
    .phone-panel-hidden { display:none; }
    .mobile-detail-tabs { display:grid; flex:none; grid-template-columns:1fr 1fr; gap:.25rem; margin-bottom:.65rem; border:1px solid #29293b; border-radius:.65rem; padding:.2rem; }
    .mobile-detail-tabs button { border-radius:.45rem; padding:.5rem; color:#777788; font-size:.75rem; font-weight:700; }
    .mobile-detail-tabs button.active { background:rgba(168,85,247,.18); color:#f3e8ff; }
    .mobile-detail-tabs span { margin-left:.25rem; color:#a78bfa; font-size:.65rem; }
    .md-summary > :global(button) { width:min(9rem,45%); }
    .chapter-row { padding:.65rem; }
    .chapter-row > :global(div) { flex-wrap:wrap; }
    .chapter-row :global(.flex.shrink-0) { width:100%; justify-content:flex-end; }
    .chapter-state { min-height:calc(100dvh - 14rem); }
  }
  @media (min-width:640px) { .md-detail{width:calc(100% - 2rem);height:min(52rem,calc(100dvh - 4rem));padding:1.5rem}.md-detail.info-large{padding:2rem} }
</style>
