<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import AppDrawer from '../../components/AppDrawer.svelte';
  import ActionMenu from '../../components/ui/ActionMenu.svelte';
  import { focusTrap } from '../../lib/focusTrap';
  import { showToast, type ActionMenuItem } from '../../lib/ui';
  import {
    karaokeApi,
    type AcquisitionJob,
    type AcquisitionPlan,
    type KaraokeItem,
    type KaraokePlaylist,
    type KaraMoeItem,
  } from '../../lib/karaokeApi';
  import { activeModule, enabledModules, filesNavigationRequest, miniPlayerExpandRequest } from '../../lib/stores';
  import { moduleHandoff } from '../handoff';
  import KaraokeDetail from './KaraokeDetail.svelte';

  type Tab = 'library' | 'discover';

  let tab: Tab = 'library';
  let items: KaraokeItem[] = [];
  let playlists: KaraokePlaylist[] = [];
  let selectedItem: KaraokeItem | null = null;
  let selectedPlaylistId: number | null = null;
  let showFavoritesOnly = false;
  let searchInput = '';
  let karaResults: KaraMoeItem[] = [];
  let loading = true;
  let searching = false;
  let error = '';
  let showAppMenu = false;
  let plan: AcquisitionPlan | null = null;
  let authorized = false;
  let job: AcquisitionJob | null = null;
  let jobs: AcquisitionJob[] = [];
  let jobDrawerOpen = false;
  let playlistManagerOpen = false;
  let editingPlaylistId: number | null = null;
  let playlistDraftName = '';
  let playlistDraftDescription = '';
  let playlistBusy = false;
  let jobTimer: ReturnType<typeof setTimeout> | null = null;
  let destroyed = false;
  let menuOpen = false;
  let menuX: number | null = null;
  let menuY: number | null = null;
  let menuActions: ActionMenuItem[] = [];
  let queueIds: string[] = [];

  $: if ($miniPlayerExpandRequest?.module === 'karaoke') {
    const expandItem = items.find((item) => item.item_id === $miniPlayerExpandRequest?.itemId);
    if (expandItem) selectedItem = expandItem;
    miniPlayerExpandRequest.set(null);
  }

  $: visibleItems = items.filter((item) => {
    if (showFavoritesOnly && !item.favorite) return false;
    if (selectedPlaylistId !== null) {
      const playlist = playlists.find((value) => value.playlist_id === selectedPlaylistId);
      if (!playlist?.items.some((entry) => entry.item_key === item.item_id)) return false;
    }
    const query = searchInput.trim().toLocaleLowerCase();
    if (!query) return true;
    return [
      item.title,
      item.subtitle,
      ...Object.values(item.tags).flat(),
    ].some((value) => value.toLocaleLowerCase().includes(query));
  });
  $: activeJobs = jobs.filter((value) => ['queued', 'running'].includes(value.status));
  $: aggregateProgress = activeJobs.length
    ? activeJobs.reduce((sum, value) => sum + value.progress, 0) / activeJobs.length
    : 0;
  $: managedPlaylist = playlists.find((value) => value.playlist_id === editingPlaylistId) ?? null;
  $: manualQueue = queueIds
    .map((itemId) => items.find((item) => item.item_id === itemId))
    .filter((item): item is KaraokeItem => Boolean(item));
  $: playerQueue = selectedItem
    ? manualQueue.some((item) => item.item_id === selectedItem?.item_id)
      ? manualQueue
      : [selectedItem, ...manualQueue]
    : manualQueue;

  onMount(() => void loadLibrary());
  onDestroy(() => {
    destroyed = true;
    if (jobTimer) clearTimeout(jobTimer);
  });

  async function loadLibrary() {
    loading = true;
    error = '';
    try {
      const [library, playlistResult, jobResult] = await Promise.all([
        karaokeApi.library(),
        karaokeApi.playlists(),
        karaokeApi.jobs(),
      ]);
      if (!destroyed) {
        items = library.items;
        playlists = playlistResult.playlists;
        jobs = jobResult.jobs;
        job = jobs.find((value) => ['running', 'queued'].includes(value.status)) ?? jobs[0] ?? null;
        if (selectedItem) {
          selectedItem = items.find((item) => item.item_id === selectedItem?.item_id) ?? selectedItem;
        }
      }
    } catch (cause) {
      if (!destroyed) error = (cause as Error).message;
    } finally {
      if (!destroyed) loading = false;
    }
  }

  async function submitSearch() {
    if (tab !== 'discover') return;
    const query = searchInput.trim();
    if (!query) return;
    searching = true;
    error = '';
    plan = null;
    try {
      const result = await karaokeApi.searchKaraMoe(query);
      if (!destroyed) karaResults = result.items;
    } catch (cause) {
      if (!destroyed) error = (cause as Error).message;
    } finally {
      if (!destroyed) searching = false;
    }
  }

  function switchTab(next: Tab) {
    tab = next;
    searchInput = '';
    error = '';
    if (next === 'discover') {
      karaResults = [];
      plan = null;
    }
  }

  async function openItem(item: KaraokeItem) {
    error = '';
    try {
      const result = await karaokeApi.item(item.item_id);
      selectedItem = result.item;
    } catch (cause) {
      error = (cause as Error).message;
    }
  }

  function updateItem(item: KaraokeItem) {
    items = items.map((entry) => entry.item_id === item.item_id ? item : entry);
    selectedItem = item;
  }

  function openItemMenu(event: MouseEvent, item: KaraokeItem): void {
    event.preventDefault();
    event.stopPropagation();
    menuX = event.clientX;
    menuY = event.clientY;
    menuActions = [
      {
        id: 'open',
        label: 'Open song',
        icon: '▶',
        run: () => openItem(item),
      },
      {
        id: 'queue',
        label: queueIds.includes(item.item_id) ? 'Remove from queue' : 'Add to queue',
        description: 'The queue contains only songs you choose',
        icon: queueIds.includes(item.item_id) ? '−' : '+',
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
        id: 'favorite',
        label: item.favorite ? 'Remove from favorites' : 'Add to favorites',
        icon: item.favorite ? '★' : '☆',
        run: async () => {
          await karaokeApi.favorite(item.item_id, !item.favorite);
          const updated = { ...item, favorite: !item.favorite };
          updateItem(updated);
          showToast({
            title: updated.favorite ? 'Added to favorites' : 'Removed from favorites',
            tone: 'success',
          });
        },
      },
      {
        id: 'update',
        label: ['incomplete', 'missing'].includes(item.media_health.status)
          ? 'Replace broken copy'
          : 'Update local copy',
        description: item.media_health.status === 'incomplete'
          ? `${formatBytes(item.media_health.actual_bytes)} of ${formatBytes(item.media_health.expected_bytes)} is present`
          : 'Download and validate a fresh version before switching',
        icon: '↻',
        disabled: item.provider !== 'kara-moe',
        run: () => prepareUpdate(item),
      },
      {
        id: 'files',
        label: 'Open in Files',
        icon: '▤',
        run: () => {
          filesNavigationRequest.set({
            sourceId: item.files_source_id,
            relativePath: item.files_relative_path,
            reveal: true,
          });
          activeModule.set('files');
        },
      },
    ];
    menuOpen = true;
  }

  async function prepareUpdate(item: KaraokeItem) {
    if (item.provider !== 'kara-moe') return;
    error = '';
    authorized = false;
    try {
      plan = (await karaokeApi.planKaraMoe(item.provider_id)).plan;
    } catch (cause) {
      error = (cause as Error).message;
    }
  }

  async function prepareDownload(result: KaraMoeItem) {
    error = '';
    authorized = false;
    try {
      plan = (await karaokeApi.planKaraMoe(result.provider_id)).plan;
    } catch (cause) {
      error = (cause as Error).message;
    }
  }

  async function confirmDownload() {
    if (!plan || !authorized) return;
    error = '';
    try {
      job = (await karaokeApi.downloadKaraMoe(
        plan.token,
        plan.selection_sha256,
        authorized,
      )).job;
      jobs = [job, ...jobs.filter((value) => value.job_id !== job?.job_id)];
      plan = null;
      jobDrawerOpen = true;
      pollJob();
    } catch (cause) {
      error = (cause as Error).message;
    }
  }

  async function pollJob() {
    if (!job || destroyed) return;
    try {
      job = (await karaokeApi.job(job.job_id)).job;
      jobs = jobs.map((value) => value.job_id === job?.job_id ? job! : value);
      if (job.status === 'completed') {
        await loadLibrary();
        tab = 'library';
        return;
      }
      if (['failed', 'cancelled', 'interrupted'].includes(job.status)) return;
      jobTimer = setTimeout(pollJob, 700);
    } catch (cause) {
      error = (cause as Error).message;
    }
  }

  async function cancelJob() {
    if (!job) return;
    try {
      await karaokeApi.cancelJob(job.job_id);
      job = (await karaokeApi.job(job.job_id)).job;
      jobs = jobs.map((value) => value.job_id === job?.job_id ? job! : value);
    } catch (cause) {
      error = (cause as Error).message;
    }
  }

  async function resumeJob() {
    if (!job) return;
    error = '';
    try {
      job = (await karaokeApi.resumeJob(job.job_id)).job;
      jobs = jobs.map((value) => value.job_id === job?.job_id ? job! : value);
      pollJob();
    } catch (cause) {
      error = (cause as Error).message;
    }
  }

  function fallbackToYouTube() {
    const query = searchInput.trim();
    if (!$enabledModules.includes('youtube')) {
      error = 'Enable the YouTube module from the Keivotos drawer before using fallback search.';
      return;
    }
    moduleHandoff.set({ target: 'youtube', query, intent: 'karaoke' });
    activeModule.set('youtube');
  }

  function neighboringItem(direction: -1 | 1) {
    if (!selectedItem) return;
    const index = playerQueue.findIndex((item) => item.item_id === selectedItem?.item_id);
    const next = playerQueue[(index + direction + playerQueue.length) % playerQueue.length];
    if (next) void openItem(next);
  }

  function randomItem() {
    if (!selectedItem || playerQueue.length < 2) return;
    const candidates = playerQueue.filter((item) => item.item_id !== selectedItem?.item_id);
    const next = candidates[Math.floor(Math.random() * candidates.length)];
    if (next) void openItem(next);
  }

  function openPlaylistManager(playlist?: KaraokePlaylist) {
    const selected = playlist ?? playlists[0] ?? null;
    editingPlaylistId = selected?.playlist_id ?? null;
    playlistDraftName = selected?.name ?? '';
    playlistDraftDescription = selected?.description ?? '';
    playlistManagerOpen = true;
  }

  function chooseManagedPlaylist(playlist: KaraokePlaylist) {
    editingPlaylistId = playlist.playlist_id;
    playlistDraftName = playlist.name;
    playlistDraftDescription = playlist.description;
  }

  async function saveManagedPlaylist() {
    if (!managedPlaylist || !playlistDraftName.trim()) return;
    playlistBusy = true;
    try {
      const result = await karaokeApi.updatePlaylist(
        managedPlaylist.playlist_id,
        playlistDraftName,
        playlistDraftDescription,
      );
      playlists = playlists.map((value) =>
        value.playlist_id === result.playlist.playlist_id ? result.playlist : value
      );
      showToast({ title: 'Playlist saved', tone: 'success' });
    } catch (cause) {
      showToast({ title: 'Could not save playlist', message: (cause as Error).message, tone: 'error', persistent: true });
    } finally {
      playlistBusy = false;
    }
  }

  async function deleteManagedPlaylist() {
    if (!managedPlaylist) return;
    if (!confirm(`Delete the playlist "${managedPlaylist.name}"? Songs and media will stay untouched.`)) return;
    playlistBusy = true;
    try {
      await karaokeApi.deletePlaylist(managedPlaylist.playlist_id);
      playlists = playlists.filter((value) => value.playlist_id !== managedPlaylist.playlist_id);
      if (selectedPlaylistId === managedPlaylist.playlist_id) selectedPlaylistId = null;
      chooseManagedPlaylist(playlists[0] ?? ({ playlist_id: 0, name: '', description: '', items: [] } as KaraokePlaylist));
      if (!playlists.length) {
        editingPlaylistId = null;
        playlistManagerOpen = false;
      }
      showToast({ title: 'Playlist deleted', message: 'The songs and local files were not changed.', tone: 'success' });
    } catch (cause) {
      showToast({ title: 'Could not delete playlist', message: (cause as Error).message, tone: 'error', persistent: true });
    } finally {
      playlistBusy = false;
    }
  }

  async function removeManagedItem(itemId: string) {
    if (!managedPlaylist) return;
    playlistBusy = true;
    try {
      const result = await karaokeApi.removeFromPlaylist(managedPlaylist.playlist_id, itemId);
      playlists = playlists.map((value) => value.playlist_id === result.playlist.playlist_id ? result.playlist : value);
    } catch (cause) {
      showToast({ title: 'Could not remove playlist item', message: (cause as Error).message, tone: 'error', persistent: true });
    } finally {
      playlistBusy = false;
    }
  }

  async function moveManagedItem(itemId: string, direction: -1 | 1) {
    if (!managedPlaylist) return;
    const order = managedPlaylist.items.map((value) => value.item_key);
    const index = order.indexOf(itemId);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= order.length) return;
    [order[index], order[target]] = [order[target], order[index]];
    playlistBusy = true;
    try {
      const result = await karaokeApi.reorderPlaylist(managedPlaylist.playlist_id, order);
      playlists = playlists.map((value) => value.playlist_id === result.playlist.playlist_id ? result.playlist : value);
    } catch (cause) {
      showToast({ title: 'Could not reorder playlist', message: (cause as Error).message, tone: 'error', persistent: true });
    } finally {
      playlistBusy = false;
    }
  }

  function duration(value: number | null): string {
    if (!value) return '';
    const seconds = Math.round(value);
    return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
  }

  function playlistItem(itemId: string): KaraokeItem | undefined {
    return items.find((value) => value.item_id === itemId);
  }

  function formatBytes(value: number | null): string {
    if (!value) return 'Size reported after connection';
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

{#if selectedItem}
  <KaraokeDetail
    item={selectedItem}
    {playlists}
    queue={playerQueue}
    on:close={() => selectedItem = null}
    on:changed={(event) => updateItem(event.detail)}
    on:previous={() => neighboringItem(-1)}
    on:next={() => neighboringItem(1)}
    on:shuffle={randomItem}
    on:select={(event) => {
      const next = playerQueue.find((item) => item.item_id === event.detail);
      if (next) void openItem(next);
    }}
    on:playlists={(event) => playlists = event.detail}
  />
{:else}
  <div class="flex h-full min-h-0 flex-col bg-[#0c1113] text-white">
    <header class="z-20 flex h-14 shrink-0 items-center gap-3 border-b border-[var(--border-default)] bg-[var(--bg-elevated)] px-3 sm:px-5">
      <button type="button" class="grid h-10 w-10 shrink-0 place-items-center rounded-full transition-colors hover:bg-[var(--module-accent-hover)]" on:click={() => showAppMenu = true} aria-label="Open Keivotos menu">
        <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" /></svg>
      </button>
      <button type="button" class="flex shrink-0 items-center gap-3" on:click={() => { tab = 'library'; searchInput = ''; error = ''; }}>
        <span class="grid h-10 w-10 place-items-center rounded-2xl bg-gradient-to-br from-cyan-300 to-emerald-400 text-xl font-black text-[#072126]">K</span>
        <span class="hidden text-lg font-semibold sm:block">Karaoke</span>
      </button>
      <form class="mx-auto flex w-full max-w-2xl gap-2" on:submit|preventDefault={submitSearch}>
        <label class="flex h-11 min-w-0 flex-1 items-center gap-2 rounded-full border border-white/10 bg-black/25 px-4 focus-within:border-cyan-300">
          <span class="text-white/35">⌕</span>
          <input
            class="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-white/30"
            bind:value={searchInput}
            placeholder={tab === 'discover' ? 'Search Kara.moe songs, series, singers…' : 'Filter your local Karaoke library'}
            aria-label={tab === 'discover' ? 'Search Kara.moe' : 'Filter Karaoke library'}
          />
        </label>
        {#if tab === 'discover'}
          <button type="submit" class="rounded-full bg-cyan-300 px-5 text-sm font-bold text-[#071416] hover:bg-cyan-200" disabled={searching}>{searching ? 'Searching…' : 'Search'}</button>
        {/if}
      </form>
      <button
        type="button"
        class="relative flex h-10 shrink-0 items-center gap-2 rounded-full border px-3 text-xs font-semibold {activeJobs.length ? 'border-cyan-300/35 bg-cyan-300/10 text-cyan-100' : 'border-white/10 text-white/55 hover:bg-white/5'}"
        aria-expanded={jobDrawerOpen}
        on:click={() => jobDrawerOpen = !jobDrawerOpen}
      >
        <span>⇩</span>
        <span class="hidden sm:inline">Downloads</span>
        {#if activeJobs.length}<span>{activeJobs.length}</span>{/if}
        {#if activeJobs.length}<span class="absolute inset-x-2 bottom-0 h-0.5 overflow-hidden rounded-full bg-white/10"><span class="block h-full bg-cyan-300" style={`width:${aggregateProgress * 100}%`}></span></span>{/if}
      </button>
    </header>

    <main class="min-h-0 flex-1 overflow-y-auto">
      <div class="mx-auto max-w-[1600px] p-4 sm:p-7">
        <div class="mb-5 flex flex-wrap items-center gap-3">
          <div class="flex rounded-xl bg-[#0f1618] p-1">
            <button type="button" class="rounded-lg px-4 py-2 text-sm font-semibold transition {tab === 'library' ? 'bg-white text-black' : 'text-white/60 hover:text-white'}" on:click={() => switchTab('library')}>Library</button>
            <button type="button" class="rounded-lg px-4 py-2 text-sm font-semibold transition {tab === 'discover' ? 'bg-white text-black' : 'text-white/60 hover:text-white'}" on:click={() => switchTab('discover')}>Kara.moe</button>
          </div>

          {#if tab === 'library'}
            <button
              type="button"
              class="rounded-lg border px-3 py-2 text-sm font-semibold transition {showFavoritesOnly ? 'border-amber-300/40 bg-amber-300/15 text-amber-200' : 'border-white/10 text-white/55 hover:bg-white/5'}"
              aria-pressed={showFavoritesOnly}
              on:click={() => showFavoritesOnly = !showFavoritesOnly}
            >★ Favorites</button>

            {#if playlists.length}
              <div class="flex gap-2 overflow-x-auto">
                <button type="button" class="whitespace-nowrap rounded-lg px-3 py-2 text-sm {selectedPlaylistId === null ? 'bg-cyan-300 text-black font-semibold' : 'bg-[#1a2528] text-white/55 hover:text-white'}" on:click={() => selectedPlaylistId = null}>All songs</button>
                {#each playlists as playlist}
                  <button type="button" class="whitespace-nowrap rounded-lg px-3 py-2 text-sm {selectedPlaylistId === playlist.playlist_id ? 'bg-cyan-300 text-black font-semibold' : 'bg-[#1a2528] text-white/55 hover:text-white'}" on:click={() => selectedPlaylistId = playlist.playlist_id}>{playlist.name}</button>
                {/each}
              </div>
              <button type="button" class="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-white/10 text-white/40 hover:bg-white/5 hover:text-white" title="Manage playlists" aria-label="Manage playlists" on:click={() => openPlaylistManager()}>⚙</button>
            {/if}

            <span class="ml-auto text-sm text-white/35">{visibleItems.length} item{visibleItems.length === 1 ? '' : 's'}</span>
          {/if}
        </div>

        {#if error}
          <div class="mb-5 rounded-2xl border border-red-400/20 bg-red-400/10 p-4 text-sm text-red-100">{error}</div>
        {/if}

        {#if tab === 'discover'}
          {#if searching}
            <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {#each Array(8) as _}<div class="aspect-[16/11] animate-pulse rounded-2xl bg-white/5"></div>{/each}
            </div>
          {:else if karaResults.length}
            <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {#each karaResults as result (result.provider_id)}
                <article class="overflow-hidden rounded-2xl border border-white/8 bg-[#131b1e] transition hover:-translate-y-0.5 hover:border-cyan-300/30">
                  <div class="grid aspect-video place-items-center bg-gradient-to-br from-cyan-950 via-[#17272b] to-fuchsia-950">
                    <span class="text-5xl font-black text-white/10">K</span>
                  </div>
                  <div class="p-4">
                    <div class="flex items-start gap-3">
                      <div class="min-w-0 flex-1">
                        <h2 class="line-clamp-2 font-semibold">{result.title}</h2>
                        <p class="mt-1 line-clamp-1 text-sm text-cyan-200/70">{result.subtitle || 'Kara.moe karaoke'}</p>
                      </div>
                      {#if result.duration}<span class="rounded bg-black/35 px-2 py-1 text-xs">{duration(result.duration)}</span>{/if}
                    </div>
                    <div class="mt-3 flex flex-wrap gap-1.5">
                      {#each (result.tags.languages ?? []).slice(0, 2) as language}<span class="rounded-full bg-emerald-500/15 px-2 py-1 text-[11px] text-emerald-200">{language}</span>{/each}
                      {#each (result.tags.series ?? []).slice(0, 1) as series}<span class="rounded-full bg-blue-500/15 px-2 py-1 text-[11px] text-blue-200">{series}</span>{/each}
                    </div>
                    <button type="button" class="mt-4 w-full rounded-full bg-cyan-300 py-2.5 text-sm font-bold text-black hover:bg-cyan-200" on:click={() => prepareDownload(result)}>Download karaoke video</button>
                  </div>
                </article>
              {/each}
            </div>
          {:else if searchInput.trim()}
            <section class="rounded-3xl border border-dashed border-white/12 bg-white/[0.025] px-6 py-16 text-center">
              <div class="mx-auto grid h-16 w-16 place-items-center rounded-2xl bg-white/5 text-2xl">⌕</div>
              <h2 class="mt-5 text-xl font-semibold">No Kara.moe result</h2>
              <p class="mx-auto mt-2 max-w-lg text-sm leading-6 text-white/45">Keep the same query and look for a downloadable local video through the optional YouTube module.</p>
              <button type="button" class="mt-5 rounded-full bg-red-600 px-6 py-3 text-sm font-bold hover:bg-red-500" on:click={fallbackToYouTube}>Search YouTube instead</button>
            </section>
          {:else}
            <section class="rounded-3xl border border-white/8 bg-gradient-to-br from-cyan-400/10 to-fuchsia-500/5 px-6 py-16 text-center">
              <h2 class="text-2xl font-semibold">Search Kara.moe</h2>
              <p class="mx-auto mt-3 max-w-xl text-sm leading-6 text-white/50">Find official karaoke videos with timed lyrics, series metadata, singers, and creators from the Kara.moe repository.</p>
            </section>
          {/if}
        {:else if loading}
          <div class="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
            {#each Array(10) as _}<div class="aspect-[4/3] animate-pulse rounded-2xl bg-white/5"></div>{/each}
          </div>
        {:else if visibleItems.length}
          <div class="grid gap-x-5 gap-y-8 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
            {#each visibleItems as item (item.item_id)}
              <div role="group" aria-label={item.title} class="group relative min-w-0" on:contextmenu={(event) => openItemMenu(event, item)}>
              <button type="button" class="min-w-0 text-left" on:click={() => openItem(item)}>
                <div class="relative aspect-video overflow-hidden rounded-2xl bg-gradient-to-br from-cyan-950 via-[#162125] to-fuchsia-950 shadow-lg">
                  {#if item.thumbnail}
                    <img class="h-full w-full object-cover transition duration-300 group-hover:scale-[1.03]" src={karaokeApi.mediaUrl(item.item_id, item.thumbnail)} alt="" loading="lazy" />
                  {:else}
                    <div class="grid h-full place-items-center text-5xl font-black text-white/8">K</div>
                  {/if}
                  <div class="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent"></div>
                  {#if item.duration}<span class="absolute bottom-2 right-2 rounded bg-black/75 px-2 py-1 text-xs">{duration(item.duration)}</span>{/if}
                  <span class="absolute bottom-2 left-2 rounded-full px-2 py-1 text-[10px] font-bold {item.lyrics.length ? 'bg-cyan-300 text-black' : 'bg-amber-400 text-black'}">{item.lyrics.length ? 'LYRICS' : 'VIDEO'}</span>
                  {#if ['incomplete', 'missing'].includes(item.media_health.status)}
                    <span class="absolute left-2 top-2 rounded-full bg-red-600 px-2 py-1 text-[10px] font-bold text-white">BROKEN</span>
                  {/if}
                </div>
                <div class="mt-3 flex gap-3">
                  <span class="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-cyan-300/10 text-sm font-black text-cyan-200">{item.title.slice(0, 1).toUpperCase()}</span>
                  <div class="min-w-0">
                    <h2 class="line-clamp-2 text-sm font-semibold leading-5 group-hover:text-cyan-200">{item.title}</h2>
                    <p class="mt-1 truncate text-xs text-white/40">{item.subtitle || item.provider}</p>
                  </div>
                  {#if item.favorite}<span class="text-amber-300" aria-label="Favorite">★</span>{/if}
                </div>
              </button>
              <button
                type="button"
                class="absolute right-2 top-2 grid h-9 w-9 place-items-center rounded-full bg-black/65 text-sm text-white/75 opacity-80 backdrop-blur hover:bg-black hover:text-white focus:opacity-100"
                aria-label={`More actions for ${item.title}`}
                on:click={(event) => openItemMenu(event, item)}
              >•••</button>
              </div>
            {/each}
          </div>
        {:else}
          <section class="rounded-3xl border border-dashed border-white/12 px-6 py-16 text-center">
            {#if showFavoritesOnly}
              <h2 class="text-xl font-semibold">No favorites yet</h2>
              <p class="mt-2 text-sm text-white/45">Favorite a local song from its detail page.</p>
            {:else if selectedPlaylistId !== null}
              <h2 class="text-xl font-semibold">This playlist is empty</h2>
              <p class="mt-2 text-sm text-white/45">Add songs from the song detail page.</p>
            {:else if searchInput.trim()}
              <h2 class="text-xl font-semibold">No matches</h2>
              <p class="mt-2 text-sm text-white/45">Try a different filter term.</p>
            {:else}
              <h2 class="text-xl font-semibold">Your Karaoke library is empty</h2>
              <p class="mt-2 text-sm text-white/45">Find a song on Kara.moe to download its official karaoke video.</p>
              <button type="button" class="mt-5 rounded-full bg-cyan-300 px-6 py-3 text-sm font-bold text-black" on:click={() => switchTab('discover')}>Find on Kara.moe</button>
            {/if}
          </section>
        {/if}
      </div>
    </main>
  </div>
{/if}

<ActionMenu
  open={menuOpen}
  x={menuX}
  y={menuY}
  items={menuActions}
  label="Karaoke song actions"
  on:close={() => menuOpen = false}
/>

{#if jobDrawerOpen}
  <div class="fixed inset-0 z-[130] bg-black/45" on:click={(event) => { if (event.target === event.currentTarget) jobDrawerOpen = false; }} role="presentation">
    <aside
      class="absolute inset-y-0 right-0 flex w-[min(430px,96vw)] flex-col border-l border-white/10 bg-[#0c1214] text-white shadow-2xl"
      aria-label="Karaoke download activity"
      use:focusTrap={{ close: () => jobDrawerOpen = false }}
      tabindex="-1"
    >
      <header class="flex items-center justify-between border-b border-white/10 px-5 py-4">
        <div><p class="text-[10px] font-bold uppercase tracking-[0.2em] text-cyan-300">Persistent queue</p><h2 class="mt-1 text-lg font-semibold">Karaoke downloads</h2></div>
        <button type="button" class="grid h-9 w-9 place-items-center rounded-full hover:bg-white/8" aria-label="Close downloads" on:click={() => jobDrawerOpen = false}>×</button>
      </header>
      {#if activeJobs.length}
        <div class="border-b border-white/8 px-5 py-3">
          <div class="flex justify-between text-xs text-white/55"><span>{activeJobs.length} active or queued</span><span>{Math.round(aggregateProgress * 100)}%</span></div>
          <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10"><div class="h-full rounded-full bg-cyan-300" style={`width:${aggregateProgress * 100}%`}></div></div>
        </div>
      {/if}
      <div class="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
        {#if jobs.length}
          {#each jobs as entry (entry.job_id)}
            <section class="rounded-2xl border border-white/8 bg-white/[0.025] p-4">
              <div class="flex items-start gap-3">
                <span class="grid h-9 w-9 shrink-0 place-items-center rounded-xl {entry.status === 'completed' ? 'bg-emerald-400/10 text-emerald-300' : entry.status === 'failed' ? 'bg-red-400/10 text-red-300' : 'bg-cyan-300/10 text-cyan-200'}">⇩</span>
                <div class="min-w-0 flex-1">
                  <div class="flex items-center justify-between gap-2"><span class="truncate text-sm font-semibold">{entry.provider_id}</span><span class="text-[10px] uppercase text-white/35">{entry.status}</span></div>
                  <p class="mt-1 text-xs capitalize text-white/45">{entry.phase}</p>
                  <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10"><div class="h-full rounded-full bg-cyan-300" style={`width:${entry.progress * 100}%`}></div></div>
                  {#if entry.error}<p class="mt-2 break-words text-xs leading-relaxed text-red-200">{entry.error}</p>{/if}
                  <div class="mt-3 flex gap-2">
                    {#if ['queued', 'running'].includes(entry.status)}
                      <button type="button" class="rounded-lg border border-white/10 px-3 py-1.5 text-xs hover:bg-white/5" on:click={() => { job = entry; void cancelJob(); }}>Cancel</button>
                    {:else if ['failed', 'cancelled', 'interrupted'].includes(entry.status)}
                      <button type="button" class="rounded-lg border border-cyan-300/25 px-3 py-1.5 text-xs text-cyan-100 hover:bg-cyan-300/8" on:click={() => { job = entry; void resumeJob(); }}>Resume</button>
                    {/if}
                  </div>
                </div>
              </div>
            </section>
          {/each}
        {:else}
          <div class="grid h-full place-items-center p-8 text-center text-sm text-white/40">No Karaoke job has been recorded yet.</div>
        {/if}
      </div>
    </aside>
  </div>
{/if}

{#if playlistManagerOpen}
  <div class="fixed inset-0 z-[135] grid place-items-center bg-black/70 p-3 backdrop-blur-sm" on:click={(event) => { if (event.target === event.currentTarget) playlistManagerOpen = false; }} role="presentation">
    <div
      class="grid max-h-[min(760px,94vh)] w-full max-w-4xl grid-cols-[220px_minmax(0,1fr)] overflow-hidden rounded-3xl border border-white/10 bg-[#101719] text-white shadow-2xl"
      role="dialog"
      aria-modal="true"
      aria-label="Manage Karaoke playlists"
      tabindex="-1"
      use:focusTrap={{ close: () => playlistManagerOpen = false }}
    >
      <aside class="min-h-0 overflow-y-auto border-r border-white/8 p-3">
        <div class="px-2 pb-3 text-[10px] font-bold uppercase tracking-[0.2em] text-cyan-300">Playlists</div>
        {#each playlists as playlist}
          <button type="button" class="mb-1 flex w-full items-center gap-3 rounded-xl p-3 text-left text-sm transition {playlist.playlist_id === editingPlaylistId ? 'bg-cyan-300/12 text-cyan-100' : 'text-white/55 hover:bg-white/5 hover:text-white'}" on:click={() => chooseManagedPlaylist(playlist)}>{playlist.name}<span class="ml-auto text-[10px] opacity-45">{playlist.items.length}</span></button>
        {/each}
      </aside>
      <div class="flex min-h-0 flex-col">
        <header class="flex items-center justify-between border-b border-white/8 px-5 py-4"><div><h2 class="text-lg font-semibold">Manage playlist</h2><p class="text-xs text-white/40">Rename, reorder, or remove items. Local media stays untouched.</p></div><button type="button" class="grid h-9 w-9 place-items-center rounded-full hover:bg-white/8" aria-label="Close playlist manager" on:click={() => playlistManagerOpen = false}>×</button></header>
        {#if managedPlaylist}
          <div class="grid gap-3 border-b border-white/8 p-4 sm:grid-cols-[1fr_1.4fr_auto]">
            <input class="rounded-xl border border-white/10 bg-black/25 px-3 py-2 text-sm outline-none focus:border-cyan-300" bind:value={playlistDraftName} aria-label="Playlist name" />
            <input class="rounded-xl border border-white/10 bg-black/25 px-3 py-2 text-sm outline-none focus:border-cyan-300" bind:value={playlistDraftDescription} placeholder="Optional description" aria-label="Playlist description" />
            <button type="button" class="rounded-xl bg-cyan-300 px-4 py-2 text-sm font-bold text-black disabled:opacity-40" disabled={playlistBusy || !playlistDraftName.trim()} on:click={saveManagedPlaylist}>Save</button>
          </div>
          <div class="min-h-0 flex-1 overflow-y-auto p-4">
            {#if managedPlaylist.items.length}
              {#each managedPlaylist.items as entry, index (entry.item_key)}
                <div class="mb-2 flex items-center gap-3 rounded-xl border border-white/8 bg-black/15 p-3">
                  <span class="w-7 text-xs tabular-nums text-white/30">{index + 1}</span>
                  <div class="min-w-0 flex-1"><div class="truncate text-sm font-semibold">{playlistItem(entry.item_key)?.title ?? entry.item_key}</div><div class="truncate text-xs text-white/35">{playlistItem(entry.item_key)?.subtitle ?? 'Unavailable from the current library view'}</div></div>
                  <button type="button" class="grid h-8 w-8 place-items-center rounded-lg hover:bg-white/8 disabled:opacity-25" disabled={playlistBusy || index === 0} aria-label="Move item up" on:click={() => moveManagedItem(entry.item_key, -1)}>↑</button>
                  <button type="button" class="grid h-8 w-8 place-items-center rounded-lg hover:bg-white/8 disabled:opacity-25" disabled={playlistBusy || index === managedPlaylist.items.length - 1} aria-label="Move item down" on:click={() => moveManagedItem(entry.item_key, 1)}>↓</button>
                  <button type="button" class="rounded-lg px-3 py-1.5 text-xs text-red-300 hover:bg-red-400/10 disabled:opacity-40" disabled={playlistBusy} on:click={() => removeManagedItem(entry.item_key)}>Remove</button>
                </div>
              {/each}
            {:else}
              <div class="rounded-2xl border border-dashed border-white/10 p-10 text-center text-sm text-white/40">This playlist is empty.</div>
            {/if}
          </div>
          <footer class="flex justify-end border-t border-white/8 p-4"><button type="button" class="rounded-xl border border-red-300/20 px-4 py-2 text-sm text-red-200 hover:bg-red-400/10 disabled:opacity-40" disabled={playlistBusy} on:click={deleteManagedPlaylist}>Delete playlist</button></footer>
        {:else}
          <div class="grid min-h-80 place-items-center p-10 text-center text-sm text-white/40">Create a playlist from a song detail, then manage it here.</div>
        {/if}
      </div>
    </div>
  </div>
{/if}

{#if plan}
  <div class="fixed inset-0 z-[90] grid place-items-center bg-black/75 p-4 backdrop-blur-sm">
    <dialog open class="m-0 w-full max-w-xl rounded-3xl border border-white/10 bg-[#121a1d] p-6 text-white shadow-2xl" aria-label="Confirm Kara.moe download" use:focusTrap={{ close: () => plan = null }}>
      <p class="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-300">{plan.replacement ? 'Replacement plan' : 'Acquisition plan'}</p>
      <h2 class="mt-2 text-2xl font-semibold">{plan.item.title}</h2>
      <dl class="mt-5 grid gap-3 rounded-2xl bg-black/25 p-4 text-sm sm:grid-cols-2">
        <div><dt class="text-white/35">Official asset</dt><dd class="mt-1">Kara.moe hardsub MP4</dd></div>
        <div><dt class="text-white/35">Estimated size</dt><dd class="mt-1">{formatBytes(plan.estimated_bytes)}</dd></div>
        <div class="sm:col-span-2"><dt class="text-white/35">Local destination</dt><dd class="mt-1 break-all">{plan.selection.destination}</dd></div>
      </dl>
      <p class="mt-4 text-xs leading-5 text-white/45">
        {plan.replacement
          ? 'The new copy must match the provider-declared size before the player switches to it. The old broken file remains available in Files for manual cleanup.'
          : 'Keivotos will preserve the source metadata and normalized lyrics, then generate clearly labeled VTT/LRC derivatives.'}
      </p>
      <label class="mt-5 flex cursor-pointer items-start gap-3 rounded-xl border border-amber-300/20 bg-amber-300/7 p-4 text-sm leading-5">
        <input class="mt-1 h-4 w-4 accent-cyan-300" type="checkbox" bind:checked={authorized} />
        <span>I confirm that I am authorized to download and keep this karaoke media.</span>
      </label>
      <div class="mt-6 flex justify-end gap-3">
        <button type="button" class="rounded-full px-5 py-2.5 text-sm font-semibold text-white/60 hover:bg-white/5" on:click={() => plan = null}>Cancel</button>
        <button type="button" class="rounded-full bg-cyan-300 px-6 py-2.5 text-sm font-bold text-black disabled:cursor-not-allowed disabled:opacity-40" disabled={!authorized} on:click={confirmDownload}>{plan.replacement ? 'Download replacement' : 'Download locally'}</button>
      </div>
    </dialog>
  </div>
{/if}

{#if showAppMenu}
  <AppDrawer on:close={() => showAppMenu = false} />
{/if}
