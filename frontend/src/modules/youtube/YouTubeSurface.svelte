<script lang="ts">
  import { get } from 'svelte/store';
  import { onDestroy, onMount } from 'svelte';
  import AppDrawer from '../../components/AppDrawer.svelte';
  import ActionMenu from '../../components/ui/ActionMenu.svelte';
  import { focusTrap } from '../../lib/focusTrap';
  import { karaokeApi } from '../../lib/karaokeApi';
  import {
    activeModule,
    enabledModules,
    filesNavigationRequest,
    miniPlayerExpandRequest,
  } from '../../lib/stores';
  import { showToast, type ActionMenuItem } from '../../lib/ui';
  import {
    youtubeApi,
    type YouTubeInspection,
    type YouTubeJob,
    type YouTubeLibraryItem,
    type YouTubeSearchItem,
  } from '../../lib/youtubeApi';
  import { moduleHandoff } from '../handoff';
  import YouTubeDownloadSheet from './YouTubeDownloadSheet.svelte';
  import YouTubePlayer from './YouTubePlayer.svelte';

  type Tab = 'search' | 'library';

  let tab: Tab = 'library';
  let showAppMenu = false;
  let searchInput = '';
  let activeSearch = '';
  let results: YouTubeSearchItem[] = [];
  let library: YouTubeLibraryItem[] = [];
  let selectedInspection: YouTubeInspection | null = null;
  let selectedLocal: YouTubeLibraryItem | null = null;
  let karaokeIntent = false;
  let searching = false;
  let loadingLibrary = true;
  let error = '';
  let job: YouTubeJob | null = null;
  let jobs: YouTubeJob[] = [];
  let jobTimer: ReturnType<typeof setTimeout> | null = null;
  let downloadDrawerOpen = false;
  let activeCategory = 'All';
  let menuOpen = false;
  let menuX = 0;
  let menuY = 0;
  let menuActions: ActionMenuItem[] = [];
  let queueIds: string[] = [];
  let destroyed = false;
  let inspectingVideoId = '';

  onMount(() => {
    void loadLibrary();
    void refreshJobs(true);
    const handoff = get(moduleHandoff);
    if (handoff?.target === 'youtube') {
      searchInput = handoff.query;
      karaokeIntent = handoff.intent === 'karaoke';
      moduleHandoff.set(null);
      if (searchInput.trim()) void submitSearch();
    }
  });

  $: if ($miniPlayerExpandRequest?.module === 'youtube') {
    const expandItem = library.find((item) => item.item_id === $miniPlayerExpandRequest?.itemId);
    if (expandItem) {
      expandItem.playback = {
        ...(expandItem.playback ?? { completed: false }),
        position_seconds: $miniPlayerExpandRequest.position,
      } as typeof expandItem.playback;
      selectedLocal = expandItem;
    }
    miniPlayerExpandRequest.set(null);
  }

  $: activeJobs = jobs.filter((entry) => ['queued', 'running'].includes(entry.status));
  $: aggregateProgress = activeJobs.length
    ? activeJobs.reduce((sum, entry) => sum + entry.progress, 0) / activeJobs.length
    : 0;
  $: downloadedVideoIds = new Set(library.map((entry) => entry.video_id));
  $: visibleResults = results.filter((entry) => matchesCategory(entry, activeCategory));
  $: manualQueue = queueIds
    .map((itemId) => library.find((item) => item.item_id === itemId))
    .filter((item): item is YouTubeLibraryItem => Boolean(item));
  $: playerQueue = selectedLocal
    ? manualQueue.some((item) => item.item_id === selectedLocal?.item_id)
      ? manualQueue
      : [selectedLocal, ...manualQueue]
    : manualQueue;

  onDestroy(() => {
    destroyed = true;
    if (jobTimer) clearTimeout(jobTimer);
  });

  async function loadLibrary() {
    loadingLibrary = true;
    try {
      const result = await youtubeApi.library();
      if (!destroyed) library = result.items;
    } catch (cause) {
      if (!destroyed) error = (cause as Error).message;
    } finally {
      if (!destroyed) loadingLibrary = false;
    }
  }

  async function refreshJobs(schedule = false) {
    try {
      jobs = (await youtubeApi.jobs()).jobs;
      job = jobs[0] ?? null;
      if (jobs.some((entry) => entry.status === 'completed' && !library.some((item) => item.item_id === entry.item_id))) {
        await loadLibrary();
      }
    } catch (cause) {
      if (!destroyed) error = (cause as Error).message;
    }
    if (!destroyed && (schedule || jobs.some((entry) => ['queued', 'running'].includes(entry.status)))) {
      if (jobTimer) clearTimeout(jobTimer);
      jobTimer = setTimeout(() => refreshJobs(false), 850);
    }
  }

  async function submitSearch() {
    const query = searchInput.trim();
    if (!query) return;

    const urlPattern = /(?:(?:m\.)?youtube\.com\/(?:watch\?v=|shorts\/)|youtu\.be\/)/i;
    if (urlPattern.test(query)) {
      searching = true;
      error = '';
      try {
        selectedInspection = (await youtubeApi.inspectUrl(query)).item;
      } catch (cause) {
        error = (cause as Error).message;
      } finally {
        searching = false;
      }
      return;
    }

    tab = 'search';
    activeSearch = query;
    searching = true;
    results = [];
    error = '';
    try {
      const response = await youtubeApi.search(query);
      if (!destroyed && activeSearch === query) results = response.items;
    } catch (cause) {
      if (!destroyed) error = (cause as Error).message;
    } finally {
      if (!destroyed) searching = false;
    }
  }

  async function chooseResult(item: YouTubeSearchItem) {
    error = '';
    inspectingVideoId = item.video_id;
    try {
      selectedInspection = (await youtubeApi.inspect(item.video_id)).item;
    } catch (cause) {
      error = (cause as Error).message;
    } finally {
      inspectingVideoId = '';
    }
  }

  async function startDownload(detail: {
    planToken: string;
    selectionSha256: string;
    authorized: boolean;
  }) {
    if (!selectedInspection) return;
    try {
      job = (await youtubeApi.download(
        detail.planToken,
        detail.selectionSha256,
        detail.authorized,
      )).job;
      jobs = [job, ...jobs.filter((entry) => entry.job_id !== job?.job_id)];
      selectedInspection = null;
      downloadDrawerOpen = true;
      void refreshJobs(false);
    } catch (cause) {
      error = (cause as Error).message;
    }
  }

  async function cancelJob() {
    if (!job) return;
    try {
      await youtubeApi.cancelJob(job.job_id);
      await refreshJobs(false);
    } catch (cause) {
      error = (cause as Error).message;
    }
  }

  async function resumeJob() {
    if (!job) return;
    error = '';
    try {
      job = (await youtubeApi.resumeJob(job.job_id)).job;
      await refreshJobs(true);
    } catch (cause) {
      error = (cause as Error).message;
    }
  }

  async function addToKaraoke(item: YouTubeLibraryItem) {
    if (!$enabledModules.includes('karaoke')) {
      error = 'Enable the Karaoke module from the Keivotos drawer before adding this local video.';
      return;
    }
    error = '';
    try {
      const imported = await karaokeApi.importYouTube(item.item_id);
      showToast({
        tone: 'success',
        title: imported.already_imported ? 'Karaoke item updated' : 'Added to Karaoke',
        message: `${imported.subtitles_attached} subtitle track${imported.subtitles_attached === 1 ? '' : 's'} attached.`,
      });
      activeModule.set('karaoke');
    } catch (cause) {
      error = (cause as Error).message;
    }
  }

  function openInFiles(item: YouTubeLibraryItem) {
    filesNavigationRequest.set({
      sourceId: item.files_source_id,
      relativePath: item.files_relative_path,
      reveal: true,
    });
    activeModule.set('files');
  }

  async function updateLocalCopy(item: YouTubeLibraryItem) {
    error = '';
    inspectingVideoId = item.video_id;
    try {
      selectedInspection = (await youtubeApi.inspect(item.video_id)).item;
    } catch (cause) {
      error = (cause as Error).message;
    } finally {
      inspectingVideoId = '';
    }
  }

  function openItemMenu(event: MouseEvent, item: YouTubeLibraryItem) {
    event.preventDefault();
    event.stopPropagation();
    menuX = event.clientX;
    menuY = event.clientY;
    menuActions = [
      { id: 'play', label: 'Play local video', run: () => selectedLocal = item },
      {
        id: 'queue',
        label: queueIds.includes(item.item_id) ? 'Remove from queue' : 'Add to queue',
        description: 'The queue contains only videos you choose',
        run: () => {
          const queued = queueIds.includes(item.item_id);
          queueIds = queued
            ? queueIds.filter((itemId) => itemId !== item.item_id)
            : [...queueIds, item.item_id];
          showToast({
            title: queued ? 'Removed from queue' : 'Added to queue',
            message: item.title,
            tone: 'success',
          });
        },
      },
      {
        id: 'update',
        label: 'Update local copy',
        description: 'Download a clean replacement and keep the old file available in Files',
        run: () => updateLocalCopy(item),
      },
      { id: 'karaoke', label: 'Add to Karaoke', run: () => void addToKaraoke(item) },
      { id: 'files', label: 'Show exact file in Files', run: () => openInFiles(item) },
    ];
    menuOpen = true;
  }

  function matchesCategory(item: YouTubeSearchItem, category: string): boolean {
    if (category === 'All') return true;
    const text = `${item.title} ${item.categories.join(' ')}`.toLowerCase();
    if (category === 'Music') return text.includes('music') || text.includes('song') || text.includes('mv');
    if (category === 'Karaoke') return text.includes('karaoke') || text.includes('lyrics');
    if (category === 'Live performance') return item.live_status === 'is_live' || text.includes('live');
    return text.includes('animation') || text.includes('anime') || text.includes('animated');
  }

  function compact(value: number | null): string {
    if (value === null) return '';
    return Intl.NumberFormat(undefined, {
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(value);
  }

  function duration(value: number | null): string {
    if (!value) return '';
    const seconds = Math.round(value);
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const remainder = seconds % 60;
    return hours
      ? `${hours}:${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`
      : `${minutes}:${String(remainder).padStart(2, '0')}`;
  }

  function date(value: string | null): string {
    if (!value) return '';
    if (/^\d{8}$/.test(value)) {
      return `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)}`;
    }
    return value;
  }

  function bytes(value: number | null): string {
    if (!value) return '';
    const units = ['B', 'KiB', 'MiB', 'GiB'];
    let amount = value;
    let index = 0;
    while (amount >= 1024 && index < units.length - 1) {
      amount /= 1024;
      index += 1;
    }
    return `${amount.toFixed(index ? 1 : 0)} ${units[index]}`;
  }
</script>

<div class="flex h-full min-h-0 flex-col bg-[#0f0f0f] text-white">
  <header class="z-20 flex h-14 shrink-0 items-center gap-3 border-b border-[var(--border-default)] bg-[var(--bg-elevated)] px-3 sm:px-5">
    <button type="button" class="grid h-10 w-10 shrink-0 place-items-center rounded-full transition-colors hover:bg-[var(--module-accent-hover)]" on:click={() => showAppMenu = true} aria-label="Open Keivotos menu">
      <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" /></svg>
    </button>
    <button type="button" class="flex shrink-0 items-center gap-2" on:click={() => { tab = 'library'; error = ''; void loadLibrary(); }}>
      <span class="grid h-8 w-11 place-items-center rounded-lg bg-red-600 text-sm font-black tracking-tight">K▶</span>
      <span class="hidden text-lg font-semibold tracking-tight sm:block">YouTube Downloads</span>
    </button>
    <form class="mx-auto flex w-full max-w-[720px]" on:submit|preventDefault={submitSearch}>
      <label class="flex h-10 min-w-0 flex-1 items-center rounded-l-full border border-[#303030] bg-[#121212] pl-5 focus-within:border-blue-500">
        <input class="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-white/35" bind:value={searchInput} placeholder="Search YouTube or paste a video URL" aria-label="Search YouTube" />
      </label>
      <button type="submit" class="grid h-10 w-16 place-items-center rounded-r-full border border-l-0 border-[#303030] bg-[#222] hover:bg-[#303030]" aria-label="Search" disabled={searching}>
        {#if searching}
          <span class="h-4 w-4 animate-spin rounded-full border-2 border-white/25 border-t-white"></span>
        {:else}
          ⌕
        {/if}
      </button>
    </form>
    <button
      type="button"
      class="relative flex h-10 items-center gap-2 rounded-full border px-3 text-xs font-semibold transition hover:bg-white/7 {activeJobs.length ? 'border-red-400 bg-red-500/10' : 'border-white/10'}"
      on:click={() => downloadDrawerOpen = true}
      aria-label="Open YouTube download queue"
    >
      <span>⇩</span><span class="hidden lg:inline">{activeJobs.length ? `${activeJobs.length} downloading` : 'Downloads'}</span>
      {#if activeJobs.length}<span class="absolute inset-x-3 bottom-1 h-0.5 overflow-hidden rounded bg-white/10"><span class="block h-full bg-red-500" style={`width:${aggregateProgress * 100}%`}></span></span>{/if}
    </button>
  </header>

  <main class="min-h-0 flex-1 overflow-y-auto">
    <div class="mx-auto max-w-[1700px] px-4 pb-12 pt-3 sm:px-6">
      <div class="mb-5 flex flex-wrap items-center gap-3">
        <div class="flex rounded-xl bg-[#1a1a1a] p-1">
          <button type="button" class="rounded-lg px-4 py-2 text-sm font-semibold transition {tab === 'search' ? 'bg-white text-black' : 'text-white/60 hover:text-white'}" on:click={() => tab = 'search'}>Search</button>
          <button type="button" class="rounded-lg px-4 py-2 text-sm font-semibold transition {tab === 'library' ? 'bg-white text-black' : 'text-white/60 hover:text-white'}" on:click={() => { tab = 'library'; error = ''; void loadLibrary(); }}>Library</button>
        </div>
        {#if tab === 'search'}
          <div class="flex gap-2 overflow-x-auto">
            {#each ['All', 'Music', 'Karaoke', 'Live performance', 'Animation'] as chip}
              <button type="button" class="whitespace-nowrap rounded-lg px-3 py-2 text-sm {chip === activeCategory ? 'bg-white text-black' : 'bg-[#272727] text-white/80 hover:bg-[#333]'}" on:click={() => activeCategory = chip}>{chip}</button>
            {/each}
          </div>
        {:else}
          <span class="ml-auto text-sm text-white/35">{library.length} item{library.length === 1 ? '' : 's'}</span>
        {/if}
      </div>

      {#if karaokeIntent}
        <div class="mb-5 flex items-center gap-3 rounded-xl border border-cyan-300/20 bg-cyan-300/7 px-4 py-3 text-sm text-cyan-100">
          <span class="grid h-8 w-8 place-items-center rounded-full bg-cyan-300 font-black text-black">K</span>
          <span class="flex-1">Karaoke fallback: download a video, then add the Files asset and any subtitle sidecars to Karaoke.</span>
          <button type="button" class="text-cyan-100/60 hover:text-white" on:click={() => karaokeIntent = false}>×</button>
        </div>
      {/if}

      {#if error}
        <div class="mb-5 rounded-xl border border-red-500/25 bg-red-500/10 p-4 text-sm text-red-100">{error}</div>
      {/if}

      {#if tab === 'search'}
        {#if searching}
          <div class="grid gap-x-4 gap-y-8 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {#each Array(8) as _}<div><div class="aspect-video animate-pulse rounded-xl bg-[#272727]"></div><div class="mt-3 h-4 w-3/4 animate-pulse rounded bg-[#272727]"></div></div>{/each}
          </div>
        {:else if visibleResults.length}
          <h1 class="mb-5 text-xl font-semibold">Results for "{activeSearch}"</h1>
          <div class="grid gap-x-4 gap-y-9 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {#each visibleResults as result (result.video_id)}
              <article class="group min-w-0" aria-busy={inspectingVideoId === result.video_id}>
                <button type="button" class="block w-full rounded-xl text-left transition" class:ring-2={inspectingVideoId === result.video_id} class:ring-red-500={inspectingVideoId === result.video_id} on:click={() => chooseResult(result)} disabled={Boolean(inspectingVideoId)}>
                  <div class="relative aspect-video overflow-hidden rounded-xl bg-[#222]">
                    {#if result.thumbnail_cache_id}
                      <img class="h-full w-full object-cover transition duration-300 group-hover:scale-[1.02]" src={youtubeApi.thumbnailUrl(result.thumbnail_cache_id)} alt="" loading="lazy" />
                    {:else}
                      <div class="grid h-full place-items-center text-5xl text-white/10">▶</div>
                    {/if}
                    {#if result.duration}<span class="absolute bottom-1.5 right-1.5 rounded bg-black/85 px-1.5 py-0.5 text-xs font-semibold">{duration(result.duration)}</span>{/if}
                    {#if downloadedVideoIds.has(result.video_id)}<span class="absolute left-2 top-2 rounded-full bg-emerald-500 px-2 py-1 text-[10px] font-bold text-black">DOWNLOADED</span>{/if}
                    <div class="absolute inset-0 grid place-items-center bg-black/0 opacity-0 transition group-hover:bg-black/25 group-hover:opacity-100"><span class="grid h-12 w-12 place-items-center rounded-full bg-red-600 shadow-xl">⇩</span></div>
                    {#if inspectingVideoId === result.video_id}<div class="absolute inset-0 grid place-items-center bg-black/65"><span class="h-9 w-9 animate-spin rounded-full border-2 border-white/25 border-t-white"></span></div>{/if}
                  </div>
                  <div class="mt-3 flex gap-3">
                    <span class="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-[#272727] text-sm font-semibold">{(result.channel || '?').slice(0, 1).toUpperCase()}</span>
                    <div class="min-w-0">
                      <h2 class="line-clamp-2 text-sm font-semibold leading-5">{result.title}</h2>
                      <p class="mt-1 truncate text-xs text-white/50">{result.channel || 'Unknown channel'}</p>
                      <p class="text-xs text-white/40">{result.view_count ? `${compact(result.view_count)} views` : ''}{result.upload_date ? ` · ${date(result.upload_date)}` : ''}</p>
                    </div>
                  </div>
                </button>
              </article>
            {/each}
          </div>
        {:else if activeSearch}
          <div class="rounded-2xl border border-white/10 p-12 text-center"><h1 class="text-xl font-semibold">No result</h1><p class="mt-2 text-sm text-white/45">Try a title, artist, series, or paste fewer words.</p></div>
        {:else}
          <div class="rounded-3xl bg-gradient-to-br from-red-600/15 via-[#181818] to-cyan-400/8 px-7 py-16">
            <span class="rounded-full bg-red-600 px-3 py-1 text-xs font-bold">LOCAL ACQUISITION</span>
            <h1 class="mt-5 max-w-2xl text-4xl font-semibold tracking-tight">Search or paste a YouTube URL above.</h1>
            <p class="mt-4 max-w-2xl text-sm leading-7 text-white/50">Search by title to browse results, or paste a video URL to jump straight to format selection. 720p, 1080p, higher variants, optional companion audio, subtitles, and captions. Everything stays local.</p>
          </div>
        {/if}
      {:else}
        {#if loadingLibrary}
          <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">{#each Array(8) as _}<div class="aspect-video animate-pulse rounded-xl bg-[#272727]"></div>{/each}</div>
        {:else if library.length}
          <div class="grid gap-x-4 gap-y-9 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {#each library as item (item.item_id)}
              <article class="group relative min-w-0" on:contextmenu={(event) => openItemMenu(event, item)}>
                <div class="block w-full cursor-pointer text-left" role="button" tabindex="0" on:click={() => selectedLocal = item} on:keydown={(event) => { if (event.key === 'Enter' || event.key === ' ') selectedLocal = item; }}>
                  <div class="relative aspect-video overflow-hidden rounded-xl bg-[#222]">
                    {#if item.thumbnail_path}<img class="h-full w-full object-cover transition group-hover:scale-[1.02]" src={youtubeApi.mediaUrl(item.item_id, item.thumbnail_path)} alt="" />{:else}<div class="grid h-full place-items-center text-5xl text-white/10">▶</div>{/if}
                    <span class="absolute bottom-1.5 right-1.5 rounded bg-black/85 px-2 py-1 text-xs font-semibold">{item.quality_label}</span>
                    <span class="absolute left-2 top-2 rounded-full bg-black/70 px-2 py-1 text-[10px]">{item.subtitles.length ? `${item.subtitles.length} SUB` : 'VIDEO'}</span>
                    <button type="button" class="absolute right-2 top-2 grid h-8 w-8 place-items-center rounded-full bg-black/75 text-lg opacity-100 hover:bg-black sm:opacity-0 sm:group-hover:opacity-100" aria-label={`More actions for ${item.title}`} on:click={(event) => openItemMenu(event, item)}>⋯</button>
                  </div>
                  <h2 class="mt-3 line-clamp-2 text-sm font-semibold leading-5">{item.title}</h2>
                  <p class="mt-1 truncate text-xs text-white/45">{item.channel}</p>
                </div>
                <div class="mt-3 flex gap-2">
                  <button type="button" class="flex-1 rounded-full bg-[#272727] py-2 text-xs font-semibold hover:bg-[#333]" on:click={() => selectedLocal = item}>Play local</button>
                  <button type="button" class="flex-1 rounded-full border border-cyan-300/25 py-2 text-xs font-semibold text-cyan-100 hover:bg-cyan-300/8" on:click={() => addToKaraoke(item)}>Add to Karaoke</button>
                </div>
              </article>
            {/each}
          </div>
        {:else}
          <div class="rounded-2xl border border-white/10 p-12 text-center"><h2 class="text-xl font-semibold">No local videos yet</h2><button type="button" class="mt-5 rounded-full bg-red-600 px-6 py-3 text-sm font-bold" on:click={() => tab = 'search'}>Search YouTube</button></div>
        {/if}
      {/if}
    </div>
  </main>
</div>

{#if downloadDrawerOpen}
  <div class="fixed inset-0 z-[125] bg-black/55" role="presentation" on:click={(event) => { if (event.target === event.currentTarget) downloadDrawerOpen = false; }}>
    <aside class="absolute inset-y-0 right-0 flex w-[min(460px,96vw)] flex-col border-l border-white/10 bg-[#111] text-white shadow-2xl" aria-label="YouTube download queue" tabindex="-1" use:focusTrap={{ close: () => downloadDrawerOpen = false }}>
      <header class="flex items-center justify-between border-b border-white/10 px-5 py-4"><div><p class="text-[10px] font-bold uppercase tracking-[0.2em] text-red-400">Persistent sequential queue</p><h2 class="mt-1 text-lg font-semibold">YouTube downloads</h2></div><button type="button" class="grid h-9 w-9 place-items-center rounded-full hover:bg-white/8" aria-label="Close downloads" on:click={() => downloadDrawerOpen = false}>×</button></header>
      {#if activeJobs.length}<div class="border-b border-white/8 px-5 py-3"><div class="flex justify-between text-xs text-white/50"><span>{activeJobs.length} active or queued</span><span>{Math.round(aggregateProgress * 100)}%</span></div><div class="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10"><div class="h-full rounded-full bg-red-500" style={`width:${aggregateProgress * 100}%`}></div></div></div>{/if}
      <div class="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
        {#each jobs as entry (entry.job_id)}
          <section class="rounded-2xl border border-white/8 bg-white/[0.025] p-4">
            <div class="flex items-start gap-3">
              <span class="grid h-9 w-9 shrink-0 place-items-center rounded-xl {entry.status === 'completed' ? 'bg-emerald-400/10 text-emerald-300' : entry.status === 'failed' ? 'bg-red-400/10 text-red-300' : 'bg-red-500/10 text-red-300'}">⇩</span>
              <div class="min-w-0 flex-1">
                <div class="flex items-center justify-between gap-2"><span class="truncate text-sm font-semibold">{entry.video_id}</span><span class="text-[10px] uppercase text-white/35">{entry.status}</span></div>
                <p class="mt-1 text-xs capitalize text-white/45">{entry.phase} · {Math.round(entry.progress * 100)}%</p>
                <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10"><div class="h-full rounded-full bg-red-500" style={`width:${entry.progress * 100}%`}></div></div>
                <p class="mt-1.5 text-xs text-white/35">{bytes(entry.downloaded_bytes)}{entry.total_bytes ? ` of ${bytes(entry.total_bytes)}` : ''}{entry.speed ? ` · ${bytes(entry.speed)}/s` : ''}{entry.eta ? ` · ${Math.round(entry.eta)}s left` : ''}</p>
                {#if entry.error}<p class="mt-2 break-words text-xs leading-relaxed {entry.status === 'completed' ? 'text-amber-200' : 'text-red-200'}">{entry.error}</p>{/if}
                <div class="mt-3 flex gap-2">
                  {#if ['queued', 'running'].includes(entry.status)}
                    <button type="button" class="rounded-lg border border-white/10 px-3 py-1.5 text-xs hover:bg-white/5" on:click={() => { job = entry; void cancelJob(); }}>Cancel</button>
                  {:else if ['failed', 'cancelled', 'interrupted'].includes(entry.status)}
                    <button type="button" class="rounded-lg border border-red-400/25 px-3 py-1.5 text-xs text-red-100 hover:bg-red-400/8" on:click={() => { job = entry; void resumeJob(); }}>Resume</button>
                  {/if}
                </div>
              </div>
            </div>
          </section>
        {:else}
          <div class="grid h-full place-items-center p-8 text-center text-sm text-white/40">No YouTube job has been recorded yet.</div>
        {/each}
      </div>
    </aside>
  </div>
{/if}

{#if selectedInspection}
  <YouTubeDownloadSheet
    item={selectedInspection}
    {karaokeIntent}
    on:close={() => selectedInspection = null}
    on:started={(event) => startDownload(event.detail)}
  />
{/if}

{#if menuOpen}
  <ActionMenu open={menuOpen} x={menuX} y={menuY} items={menuActions} on:close={() => menuOpen = false} />
{/if}

{#if selectedLocal}
  <YouTubePlayer
    item={selectedLocal}
    queue={playerQueue}
    sourceVariants={library}
    on:close={() => selectedLocal = null}
    on:previous={() => {
      const index = playerQueue.findIndex((item) => item.item_id === selectedLocal?.item_id);
      if (index > 0) selectedLocal = playerQueue[index - 1];
    }}
    on:next={() => {
      const index = playerQueue.findIndex((item) => item.item_id === selectedLocal?.item_id);
      if (index >= 0 && index < playerQueue.length - 1) selectedLocal = playerQueue[index + 1];
    }}
    on:shuffle={() => {
      const alternatives = playerQueue.filter((item) => item.item_id !== selectedLocal?.item_id);
      if (alternatives.length) selectedLocal = alternatives[Math.floor(Math.random() * alternatives.length)];
    }}
    on:select={(event) => {
      const next = playerQueue.find((item) => item.item_id === event.detail);
      if (next) selectedLocal = next;
    }}
  />
{/if}

{#if showAppMenu}
  <AppDrawer on:close={() => showAppMenu = false} />
{/if}

<style>
  :global(.youtube-icon-button) {
    display: grid;
    width: 2.5rem;
    height: 2.5rem;
    place-items: center;
    border-radius: 9999px;
    color: rgb(255 255 255 / 0.75);
  }
  :global(.youtube-icon-button:hover) {
    background: rgb(255 255 255 / 0.1);
    color: white;
  }
</style>
