<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import AppDrawer from '../../components/AppDrawer.svelte';
  import ActionMenu from '../../components/ui/ActionMenu.svelte';
  import { runWithToast, type ActionMenuItem } from '../../lib/ui';
  import {
    redditApi,
    type RedditCommunity,
    type RedditCommunitySummary,
    type RedditCaptureResult,
    type RedditMediaJob,
    type RedditPost,
    type RedditPostDetail,
    type RedditProfile,
    type RedditProfileSummary,
    type RedditSearchItem,
    type RedditStatus,
  } from '../../lib/redditApi';
  import RedditCommunityView from './RedditCommunityView.svelte';
  import RedditCaptureDrawer from './RedditCaptureDrawer.svelte';
  import RedditDownloadActivity from './RedditDownloadActivity.svelte';
  import RedditPostCard from './RedditPostCard.svelte';
  import RedditProfileView from './RedditProfileView.svelte';
  import RedditThreadView from './RedditThreadView.svelte';
  import { redditFavoriteCommunities } from './settings';

  const PAGE_SIZE = 25;
  const CAPTURE_COMMAND = '.venv\\Scripts\\python.exe scripts\\reddit_capture.py --url "<reddit-url>" --arctic-shift-api';
  type View = 'home' | 'popular' | 'communities' | 'profiles';

  let view: View = 'home';
  let posts: RedditPost[] = [];
  let communities: RedditCommunitySummary[] = [];
  let profiles: RedditProfileSummary[] = [];
  let nextCursor: string | null = null;
  let hasMore = true;
  let loading = false;
  let initialLoading = true;
  let error = '';
  let showAppMenu = false;
  let showCapturePanel = false;
  let captureInitialUrl = '';
  let downloadActivityOpen = false;
  let mediaJobs: RedditMediaJob[] = [];
  let mediaJobsTimer: ReturnType<typeof setTimeout> | null = null;
  let searchInput = '';
  let activeSearch = '';
  let searchResults: RedditSearchItem[] = [];
  let searching = false;
  let selectedPost: RedditPostDetail | null = null;
  let selectedCommunity: RedditCommunity | null = null;
  let selectedProfile: RedditProfile | null = null;
  let detailLoading = false;
  let listLoading = false;
  let refreshing = '';
  let menuOpen = false;
  let menuX = 0;
  let menuY = 0;
  let menuActions: ActionMenuItem[] = [];
  let status: RedditStatus | null = null;
  let sentinel: HTMLDivElement;
  let observer: IntersectionObserver | null = null;
  let destroyed = false;
  $: displayedCommunities = [...communities].sort((left, right) => {
    const leftFavorite = $redditFavoriteCommunities.some((item) => item.toLocaleLowerCase() === left.subreddit.toLocaleLowerCase());
    const rightFavorite = $redditFavoriteCommunities.some((item) => item.toLocaleLowerCase() === right.subreddit.toLocaleLowerCase());
    if (leftFavorite !== rightFavorite) return leftFavorite ? -1 : 1;
    return left.subreddit.localeCompare(right.subreddit);
  });

  onMount(() => {
    observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting) && !activeSearch && view === 'home') {
          void loadMore();
        }
      },
      { rootMargin: '500px 0px' },
    );
    if (sentinel) observer.observe(sentinel);
    void Promise.all([loadStatus(), loadMore(), refreshMediaJobs()]);
  });

  onDestroy(() => {
    destroyed = true;
    observer?.disconnect();
    if (mediaJobsTimer) clearTimeout(mediaJobsTimer);
  });

  $: activeMediaJobs = mediaJobs.filter((job) => job.status === 'queued' || job.status === 'running');
  $: mediaProgress = activeMediaJobs.length
    ? activeMediaJobs.reduce((total, job) => total + job.progress, 0) / activeMediaJobs.length
    : 0;

  async function refreshMediaJobs() {
    try {
      mediaJobs = (await redditApi.mediaJobs()).jobs;
    } catch {
      // Download status is supplementary; normal archive browsing remains available.
    } finally {
      if (!destroyed && mediaJobs.some((job) => job.status === 'queued' || job.status === 'running')) {
        mediaJobsTimer = setTimeout(() => void refreshMediaJobs(), 850);
      }
    }
  }

  function downloadStarted(event: CustomEvent<RedditMediaJob>) {
    const job = event.detail;
    mediaJobs = [job, ...mediaJobs.filter((item) => item.job_id !== job.job_id)];
    if (mediaJobsTimer) clearTimeout(mediaJobsTimer);
    mediaJobsTimer = setTimeout(() => void refreshMediaJobs(), 400);
  }

  function openCapture(initialUrl = '') {
    captureInitialUrl = initialUrl;
    showCapturePanel = true;
  }

  async function loadStatus() {
    try {
      const result = await redditApi.status();
      if (!destroyed) status = result;
    } catch (cause) {
      if (!destroyed) error = (cause as Error).message;
    }
  }

  async function loadMore() {
    if (loading || !hasMore || activeSearch || !['home', 'popular'].includes(view)) return;
    loading = true;
    error = '';
    try {
      const page = await redditApi.feed({
        limit: PAGE_SIZE,
        cursor: nextCursor ?? undefined,
        sort: view === 'popular' ? 'popular' : 'new',
      });
      if (destroyed) return;
      const known = new Set(posts.map((post) => post.id));
      posts = [...posts, ...page.items.filter((post) => !known.has(post.id))];
      nextCursor = page.next_cursor;
      hasMore = page.has_more;
    } catch (cause) {
      if (!destroyed) error = (cause as Error).message;
    } finally {
      if (!destroyed) {
        loading = false;
        initialLoading = false;
      }
    }
  }

  async function refreshFeed(nextView: View = view) {
    view = nextView;
    posts = [];
    nextCursor = null;
    hasMore = true;
    activeSearch = '';
    searchResults = [];
    initialLoading = true;
    await Promise.all([
      ['home', 'popular'].includes(view) ? loadMore() : Promise.resolve(),
      loadStatus(),
    ]);
  }

  async function captured(_event: CustomEvent<RedditCaptureResult>) {
    await Promise.all([refreshFeed('home'), loadCommunities(), loadProfiles()]);
  }

  async function setView(next: View) {
    clearSearch();
    selectedCommunity = null;
    selectedProfile = null;
    if (next === 'home' || next === 'popular') {
      await refreshFeed(next);
      return;
    }
    view = next;
    if (next === 'communities') await loadCommunities();
    if (next === 'profiles') await loadProfiles();
  }

  async function loadCommunities() {
    listLoading = true;
    error = '';
    try {
      communities = (await redditApi.communities()).items;
    } catch (cause) {
      error = (cause as Error).message;
    } finally {
      listLoading = false;
      initialLoading = false;
    }
  }

  async function loadProfiles() {
    listLoading = true;
    error = '';
    try {
      profiles = (await redditApi.profiles()).items;
    } catch (cause) {
      error = (cause as Error).message;
    } finally {
      listLoading = false;
      initialLoading = false;
    }
  }

  async function submitSearch() {
    const query = searchInput.trim();
    if (!query) {
      activeSearch = '';
      searchResults = [];
      return;
    }
    searching = true;
    error = '';
    activeSearch = query;
    try {
      const result = await redditApi.search(query, { limit: 100 });
      if (!destroyed && activeSearch === query) searchResults = result.items;
    } catch (cause) {
      if (!destroyed) error = (cause as Error).message;
    } finally {
      if (!destroyed) searching = false;
    }
  }

  function clearSearch() {
    searchInput = '';
    activeSearch = '';
    searchResults = [];
  }

  async function openPost(postId: string) {
    detailLoading = true;
    error = '';
    selectedProfile = null;
    selectedCommunity = null;
    try {
      selectedPost = await redditApi.post(postId);
    } catch (cause) {
      error = (cause as Error).message;
    } finally {
      detailLoading = false;
    }
  }

  async function openCommunity(subreddit: string) {
    if (!subreddit) return;
    error = '';
    selectedPost = null;
    selectedProfile = null;
    try {
      selectedCommunity = await redditApi.community(subreddit);
    } catch (cause) {
      error = (cause as Error).message;
    }
  }

  async function openProfile(username: string) {
    if (!username) return;
    error = '';
    selectedPost = null;
    selectedCommunity = null;
    try {
      selectedProfile = await redditApi.profile(username);
    } catch (cause) {
      error = (cause as Error).message;
    }
  }

  async function refreshPost(postId: string) {
    if (refreshing) return;
    refreshing = `post:${postId}`;
    try {
      await runWithToast(
        () => redditApi.refreshPost(postId),
        {
          pending: 'Refreshing Reddit post snapshot',
          success: 'Post observations and comments updated',
          failure: 'The Reddit post could not be refreshed',
          retry: () => refreshPost(postId),
        },
      );
      await refreshFeed(view === 'popular' ? 'popular' : 'home');
      if (selectedPost?.post.id === postId) selectedPost = await redditApi.post(postId);
    } catch {
      // The retryable toast owns the error presentation.
    } finally {
      refreshing = '';
    }
  }

  async function refreshCommunity(subreddit: string) {
    if (refreshing) return;
    refreshing = `community:${subreddit}`;
    try {
      await runWithToast(
        () => redditApi.refreshCommunity(subreddit),
        {
          pending: `Refreshing r/${subreddit}`,
          success: `r/${subreddit} snapshot updated`,
          failure: `r/${subreddit} could not be refreshed`,
          retry: () => refreshCommunity(subreddit),
        },
      );
      await loadCommunities();
      if (selectedCommunity?.subreddit === subreddit) selectedCommunity = await redditApi.community(subreddit);
    } catch {
      // The retryable toast owns the error presentation.
    } finally {
      refreshing = '';
    }
  }

  async function refreshProfile(username: string) {
    if (refreshing) return;
    refreshing = `profile:${username}`;
    try {
      await runWithToast(
        () => redditApi.capture(`https://www.reddit.com/user/${encodeURIComponent(username)}/`),
        {
          pending: `Refreshing u/${username}`,
          success: `u/${username} activity updated`,
          failure: `u/${username} could not be refreshed`,
          retry: () => refreshProfile(username),
        },
      );
      await loadProfiles();
      selectedProfile = await redditApi.profile(username);
    } catch {
      // The retryable toast owns the error presentation.
    } finally {
      refreshing = '';
    }
  }

  function openPostMenu(
    event: MouseEvent,
    post: RedditPost,
    anchorX?: number,
    anchorY?: number,
  ) {
    event.preventDefault();
    event.stopPropagation();
    const point = event.type === 'click'
      ? postMenuPoint(post.id, anchorX, anchorY)
      : actionMenuPoint(event, anchorX, anchorY);
    menuX = point.x;
    menuY = point.y;
    menuActions = [
      { id: 'open', label: 'Open archived thread', icon: '↗', run: () => openPost(post.id) },
      { id: 'refresh', label: 'Refresh snapshot', description: 'Capture current comments, score, and upvote ratio', icon: '↻', run: () => refreshPost(post.id) },
      {
        id: 'update-media',
        label: 'Update downloaded media',
        description: 'Check this post again and download missing or failed media',
        icon: '↓',
        run: () => openCapture(post.permalink ? `https://www.reddit.com${post.permalink}` : `https://www.reddit.com/comments/${post.id}`),
      },
      ...(post.subreddit ? [{ id: 'community', label: `Open r/${post.subreddit}`, icon: 'r/', run: () => openCommunity(post.subreddit ?? '') }] : []),
      ...(post.author ? [{ id: 'profile', label: `Open u/${post.author}`, icon: 'u/', run: () => openProfile(post.author ?? '') }] : []),
    ];
    menuOpen = true;
  }

  function isFavoriteCommunity(subreddit: string): boolean {
    return $redditFavoriteCommunities.some(
      (item) => item.toLocaleLowerCase() === subreddit.toLocaleLowerCase(),
    );
  }

  function toggleFavoriteCommunity(subreddit: string) {
    redditFavoriteCommunities.update((items) => (
      isFavoriteCommunity(subreddit)
        ? items.filter((item) => item.toLocaleLowerCase() !== subreddit.toLocaleLowerCase())
        : [...items, subreddit]
    ));
  }

  function openCommunityMenu(event: MouseEvent, community: RedditCommunitySummary) {
    event.preventDefault();
    event.stopPropagation();
    const point = actionMenuPoint(event);
    menuX = point.x;
    menuY = point.y;
    menuActions = [
      { id: 'open', label: `Open r/${community.subreddit}`, icon: '↗', run: () => openCommunity(community.subreddit) },
      { id: 'refresh', label: 'Refresh community snapshot', icon: '↻', run: () => refreshCommunity(community.subreddit) },
      {
        id: 'favorite',
        label: isFavoriteCommunity(community.subreddit) ? 'Remove from favorites' : 'Add to favorites',
        icon: isFavoriteCommunity(community.subreddit) ? '★' : '☆',
        run: () => toggleFavoriteCommunity(community.subreddit),
      },
    ];
    menuOpen = true;
  }

  function openProfileMenu(event: MouseEvent, profile: RedditProfileSummary) {
    event.preventDefault();
    event.stopPropagation();
    const point = actionMenuPoint(event);
    menuX = point.x;
    menuY = point.y;
    menuActions = [
      { id: 'open', label: `Open u/${profile.author}`, icon: '↗', run: () => openProfile(profile.author) },
      { id: 'refresh', label: 'Refresh profile activity', icon: '↻', run: () => refreshProfile(profile.author) },
    ];
    menuOpen = true;
  }

  function actionMenuPoint(
    event: MouseEvent,
    anchorX?: number,
    anchorY?: number,
  ): { x: number; y: number } {
    if (event.clientX > 0 && event.clientY > 0) {
      return { x: event.clientX, y: event.clientY };
    }
    if (anchorX !== undefined && anchorY !== undefined) {
      return { x: anchorX, y: anchorY };
    }
    const trigger = event.currentTarget;
    if (trigger instanceof HTMLElement) {
      const bounds = trigger.getBoundingClientRect();
      return { x: bounds.left, y: bounds.bottom };
    }
    return { x: window.innerWidth / 2, y: window.innerHeight / 2 };
  }

  function postMenuPoint(
    postId: string,
    anchorX?: number,
    anchorY?: number,
  ): { x: number; y: number } {
    const card = Array.from(
      document.querySelectorAll<HTMLElement>('[data-reddit-post-id]'),
    ).find((element) => element.dataset.redditPostId === postId);
    const trigger = card?.querySelector<HTMLElement>(
      'button[aria-label="More actions for saved post"]',
    );
    if (trigger) {
      const bounds = trigger.getBoundingClientRect();
      return { x: bounds.left, y: bounds.bottom };
    }
    if (anchorX !== undefined && anchorY !== undefined) {
      return { x: anchorX, y: anchorY };
    }
    return { x: window.innerWidth / 2, y: window.innerHeight / 2 };
  }

  function viewClass(item: View): string {
    return view === item
      ? 'bg-[#272729] text-white'
      : 'text-[#a7a8aa] hover:bg-[#1a1a1b] hover:text-white';
  }

  async function copyCaptureCommand() {
    try {
      await navigator.clipboard.writeText(CAPTURE_COMMAND);
    } catch {
      // The command remains selectable in the UI when clipboard access is denied.
    }
  }

  function compact(value: number | undefined): string {
    return Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 }).format(value ?? 0);
  }

  function resultDate(value: number | null): string {
    return value === null ? '' : new Date(value * 1000).toLocaleDateString();
  }
</script>

<div class="flex h-full min-h-0 flex-col bg-[#030303] text-[#d7dadc]">
  <header class="z-20 flex h-14 shrink-0 items-center gap-3 border-b border-[var(--border-default)] bg-[var(--bg-elevated)] px-3">
    <button
      type="button"
      class="grid h-10 w-10 shrink-0 place-items-center rounded-full transition-colors hover:bg-[var(--module-accent-hover)]"
      aria-label="Open Keivotos menu"
      title="Keivotos modules"
      on:click={() => showAppMenu = true}
    >
      <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
      </svg>
    </button>
    <button type="button" class="flex shrink-0 items-center gap-2" on:click={() => setView('home')}>
      <span class="grid h-9 w-9 place-items-center rounded-full bg-[#ff4500] text-white">
        <svg class="h-6 w-6" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M12 2a10 10 0 100 20 10 10 0 000-20zm5.4 11.3c0 2.5-2.4 4.5-5.4 4.5s-5.4-2-5.4-4.5c0-1 .4-1.8 1.1-2.5-.1-.2-.2-.5-.2-.8a1.5 1.5 0 012.7-.9c.6-.2 1.2-.3 1.8-.3l.8-3.7 2.6.6a1.3 1.3 0 112.5.5 1.3 1.3 0 01-1.8.4l-2.2-.5-.6 2.8c.6 0 1.2.2 1.7.4a1.5 1.5 0 012.8.7c0 .3-.1.6-.2.8.5.7.8 1.5.8 2.5z" />
        </svg>
      </span>
      <span class="hidden text-lg font-bold sm:inline">Reddit Archive</span>
    </button>

    <form class="mx-auto flex w-full max-w-[690px]" on:submit|preventDefault={submitSearch}>
      <label class="flex h-10 w-full items-center gap-2 rounded-full border border-[#343536] bg-[#272729] px-4 focus-within:border-white/35 focus-within:bg-[#1a1a1b]">
        <svg class="h-4 w-4 shrink-0 text-[#818384]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <circle cx="11" cy="11" r="7" stroke-width="2" />
          <path d="M20 20l-3.5-3.5" stroke-width="2" stroke-linecap="round" />
        </svg>
        <input
          class="min-w-0 flex-1 bg-transparent text-sm text-[#d7dadc] outline-none placeholder:text-[#818384]"
          bind:value={searchInput}
          placeholder="Search saved posts and comments"
          aria-label="Search saved Reddit archive"
        />
        {#if searchInput}
          <button type="button" class="text-[#818384] hover:text-white" aria-label="Clear search" on:click={clearSearch}>×</button>
        {/if}
      </label>
      <button
        type="submit"
        class="ml-2 rounded-full bg-[#d7dadc] px-4 text-xs font-bold text-[#1a1a1b] hover:bg-white"
        aria-label="Search local archive"
      >Search</button>
    </form>

    <button
      type="button"
      class="hidden rounded-full border border-[#d7dadc] px-4 py-2 text-xs font-bold text-[#d7dadc] hover:bg-white/10 sm:block"
      on:click={() => refreshFeed(view)}
    >Refresh</button>
    <button
      type="button"
      class="relative grid h-9 w-9 shrink-0 place-items-center rounded-full border border-[#343536] text-[#d7dadc] hover:bg-white/10"
      aria-label="Reddit download activity"
      title="Reddit download activity"
      on:click={() => downloadActivityOpen = true}
    >
      <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path stroke-linecap="round" stroke-width="2" d="M12 3v12m0 0l-4-4m4 4l4-4M5 20h14" />
      </svg>
      {#if activeMediaJobs.length}
        <span class="absolute -right-1 -top-1 grid h-4 min-w-4 place-items-center rounded-full bg-[#4fbcff] px-1 text-[9px] font-bold text-black">
          {activeMediaJobs.length}
        </span>
        <span class="absolute inset-x-1 bottom-0 h-0.5 overflow-hidden rounded-full bg-white/15">
          <span class="block h-full bg-[#4fbcff]" style={`width:${mediaProgress * 100}%`}></span>
        </span>
      {/if}
    </button>
    <button
      type="button"
      class="flex h-9 shrink-0 items-center gap-2 rounded-full bg-[#ff4500] px-3 text-xs font-bold text-white hover:bg-[#ff5414]"
      aria-label="Save a Reddit link"
      title="Save a Reddit link"
      on:click={() => openCapture()}
    >
      <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path stroke-linecap="round" stroke-width="2" d="M12 5v14M5 12h14" />
      </svg>
      <span class="hidden md:inline">Save link</span>
    </button>
  </header>

  <div class="flex min-h-0 flex-1 justify-center overflow-hidden">
    <aside class="hidden w-[220px] shrink-0 overflow-y-auto border-r border-[#202124] px-3 py-5 md:block">
      <nav class="space-y-1 text-sm font-semibold">
        <button type="button" class="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left {viewClass('home')}" on:click={() => setView('home')}>
          <svg class="h-5 w-5 text-[#ff4500]" fill="currentColor" viewBox="0 0 24 24"><path d="M3 11l9-8 9 8v10h-6v-6H9v6H3V11z" /></svg>
          Home
        </button>
        <button type="button" class="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left {viewClass('popular')}" on:click={() => setView('popular')}>
          <span class="grid h-5 w-5 place-items-center rounded-full border border-current text-xs">↗</span>
          Popular
        </button>
        <button type="button" class="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left {viewClass('communities')}" on:click={() => setView('communities')}>
          <span class="grid h-5 w-5 place-items-center text-base">◉</span>
          Communities
        </button>
        <button type="button" class="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left {viewClass('profiles')}" on:click={() => setView('profiles')}>
          <span class="grid h-5 w-5 place-items-center text-base">♙</span>
          Profiles
        </button>
      </nav>
      <div class="mt-6 border-t border-[#343536] pt-4 text-xs leading-5 text-[#818384]">
        Everything here is local. Refresh actions add a new observation without replacing earlier snapshots.
      </div>
    </aside>

    <main class="min-w-0 flex-1 overflow-y-auto pb-16 md:pb-0" aria-busy={loading || searching || detailLoading || listLoading}>
      <div class="mx-auto grid max-w-[1240px] grid-cols-1 gap-5 px-3 py-5 lg:grid-cols-[minmax(0,760px)_300px]">
        <section class="min-w-0">
          {#if error}
            <div class="mb-4 flex items-start justify-between gap-3 rounded-lg border border-red-900/60 bg-red-950/45 px-4 py-3 text-sm text-red-200">
              <span>{error}</span>
              <button type="button" class="text-red-300 hover:text-white" aria-label="Dismiss error" on:click={() => error = ''}>×</button>
            </div>
          {/if}

          {#if activeSearch}
            <div class="mb-3 flex items-center justify-between">
              <h1 class="text-sm font-semibold text-[#d7dadc]">Results for “{activeSearch}”</h1>
              <button type="button" class="text-xs font-semibold text-[#4fbcff] hover:underline" on:click={clearSearch}>Back to saved feed</button>
            </div>
            {#if searching}
              <div class="rounded-xl border border-[#343536] bg-[#1a1a1b] p-8 text-center text-sm text-[#818384]">Searching the local index…</div>
            {:else if searchResults.length === 0}
              <div class="rounded-xl border border-[#343536] bg-[#1a1a1b] p-8 text-center text-sm text-[#818384]">No saved posts or comments match this search.</div>
            {:else}
              <div class="space-y-2">
                {#each searchResults as result (`${result.record_type}-${result.id}`)}
                  <button
                    type="button"
                    class="block w-full rounded-xl border border-[#343536] bg-[#1a1a1b] px-4 py-3 text-left hover:border-[#4a4a55]"
                    on:click={() => openPost(result.post_id)}
                  >
                    <div class="text-xs text-[#818384]">
                      <span class="font-semibold text-[#d7dadc]">{result.record_type === 'post' ? 'Post' : 'Comment'}</span>
                      {#if result.subreddit}<span> in r/{result.subreddit}</span>{/if}
                      {#if result.author}<span> by u/{result.author}</span>{/if}
                      {#if result.created_utc}<span> • {resultDate(result.created_utc)}</span>{/if}
                    </div>
                    {#if result.title}<h2 class="mt-1 font-medium text-[#d7dadc]">{result.title}</h2>{/if}
                    {#if result.body}<p class="mt-1 line-clamp-3 whitespace-pre-wrap text-sm leading-6 text-[#b8b9ba]">{result.body}</p>{/if}
                  </button>
                {/each}
              </div>
            {/if}
          {:else if view === 'communities'}
            <div class="mb-4 flex items-end justify-between">
              <div>
                <p class="text-xs font-semibold uppercase tracking-[0.18em] text-[#ff4500]">Local directory</p>
                <h1 class="mt-1 text-2xl font-bold">Downloaded communities</h1>
              </div>
              <span class="text-xs text-[#818384]">{communities.length} communities</span>
            </div>
            {#if listLoading}
              <div class="space-y-2">{#each Array(6) as _}<div class="h-16 animate-pulse rounded-xl bg-[#1a1a1b]"></div>{/each}</div>
            {:else if communities.length}
              <div class="space-y-2">
                {#each displayedCommunities as community (community.subreddit)}
                  <div role="group" aria-label={`r/${community.subreddit}`} class="flex items-center gap-3 rounded-xl border border-[#343536] bg-[#1a1a1b] p-3 hover:border-[#4a4a55]" on:contextmenu={(event) => openCommunityMenu(event, community)}>
                    <button type="button" class="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-[#272729] font-bold text-[#ff4500]" on:click={() => openCommunity(community.subreddit)}>r/</button>
                    <button type="button" class="min-w-0 flex-1 text-left" on:click={() => openCommunity(community.subreddit)}>
                      <strong class="block truncate">r/{community.subreddit}</strong>
                      <span class="text-xs text-[#818384]">{compact(community.posts)} posts · {compact(community.comments)} comments · {compact(community.snapshots)} snapshots</span>
                    </button>
                    <button
                      type="button"
                      class="grid h-9 w-9 place-items-center rounded-full text-xl {isFavoriteCommunity(community.subreddit) ? 'text-[#ffb000]' : 'text-[#818384]'} hover:bg-white/10"
                      aria-label={isFavoriteCommunity(community.subreddit) ? `Remove r/${community.subreddit} from favorites` : `Add r/${community.subreddit} to favorites`}
                      on:click={() => toggleFavoriteCommunity(community.subreddit)}
                    >{isFavoriteCommunity(community.subreddit) ? '★' : '☆'}</button>
                    <button
                      type="button"
                      class="rounded-full border border-white/10 px-3 py-2 text-xs font-semibold hover:bg-white/10 disabled:opacity-40"
                      disabled={Boolean(refreshing)}
                      on:click={() => refreshCommunity(community.subreddit)}
                    >{refreshing === `community:${community.subreddit}` ? 'Refreshing…' : 'Refresh'}</button>
                    <button type="button" class="grid h-9 w-9 place-items-center rounded-full text-lg text-[#818384] hover:bg-white/10 hover:text-white" aria-label={`More actions for r/${community.subreddit}`} on:click={(event) => openCommunityMenu(event, community)}>•••</button>
                  </div>
                {/each}
              </div>
            {:else}
              <div class="rounded-xl border border-[#343536] bg-[#1a1a1b] p-8 text-center text-sm text-[#818384]">No subreddit snapshots have been downloaded yet.</div>
            {/if}
          {:else if view === 'profiles'}
            <div class="mb-4 flex items-end justify-between">
              <div>
                <p class="text-xs font-semibold uppercase tracking-[0.18em] text-[#ff4500]">Local directory</p>
                <h1 class="mt-1 text-2xl font-bold">Archived profiles</h1>
              </div>
              <button type="button" class="rounded-full bg-[#ff4500] px-4 py-2 text-xs font-bold text-white" on:click={() => openCapture()}>Add profile URL</button>
            </div>
            {#if listLoading}
              <div class="space-y-2">{#each Array(6) as _}<div class="h-16 animate-pulse rounded-xl bg-[#1a1a1b]"></div>{/each}</div>
            {:else if profiles.length}
              <div class="grid gap-2 sm:grid-cols-2">
                {#each profiles as profile (profile.author)}
                  <div role="group" aria-label={`u/${profile.author}`} class="flex items-center gap-3 rounded-xl border border-[#343536] bg-[#1a1a1b] p-4 hover:border-[#4a4a55]" on:contextmenu={(event) => openProfileMenu(event, profile)}>
                    <span class="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-[#272729] font-bold text-[#ff4500]">{profile.author.slice(0, 1).toUpperCase()}</span>
                    <button type="button" class="min-w-0 flex-1 text-left" on:click={() => openProfile(profile.author)}>
                      <strong class="block truncate">u/{profile.author}</strong>
                      <span class="text-xs text-[#818384]">{compact(profile.posts)} posts · {compact(profile.comments)} comments</span>
                    </button>
                    <button type="button" class="grid h-9 w-9 place-items-center rounded-full text-lg text-[#818384] hover:bg-white/10 hover:text-white" aria-label={`More actions for u/${profile.author}`} on:click={(event) => openProfileMenu(event, profile)}>•••</button>
                  </div>
                {/each}
              </div>
            {:else}
              <div class="rounded-xl border border-[#343536] bg-[#1a1a1b] p-8 text-center text-sm text-[#818384]">No user profiles have been captured yet. Paste a Reddit user URL to start one.</div>
            {/if}
          {:else if initialLoading}
            <div class="space-y-3">
              {#each Array(4) as _}
                <div class="h-40 animate-pulse rounded-xl border border-[#343536] bg-[#1a1a1b]"></div>
              {/each}
            </div>
          {:else if posts.length === 0}
            <div class="rounded-xl border border-[#343536] bg-[#1a1a1b] p-8 text-center">
              <div class="mx-auto grid h-14 w-14 place-items-center rounded-full bg-[#272729] text-[#ff4500]">
                <svg class="h-7 w-7" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-width="1.8" d="M5 4h14v16l-7-4-7 4V4z" /></svg>
              </div>
              <h1 class="mt-4 text-xl font-semibold">Your saved Reddit feed is empty</h1>
              <p class="mx-auto mt-2 max-w-lg text-sm leading-6 text-[#818384]">Capture a Reddit post URL with the local script. Subreddit URLs save only community information, never a post listing.</p>
              <code class="mt-4 block select-all overflow-x-auto rounded-lg bg-[#0f1011] px-3 py-2 text-left text-xs text-[#b8b9ba]">{CAPTURE_COMMAND}</code>
            </div>
          {:else}
            {#if view === 'popular'}
              <div class="mb-3">
                <p class="text-xs font-semibold uppercase tracking-[0.18em] text-[#ff4500]">Highest saved score</p>
                <h1 class="mt-1 text-xl font-bold">Popular in your local archive</h1>
              </div>
            {/if}
            <div class="space-y-3">
              {#each posts as post (post.id)}
                <RedditPostCard
                  {post}
                  on:open={(event) => openPost(event.detail)}
                  on:community={(event) => openCommunity(event.detail)}
                  on:profile={(event) => openProfile(event.detail)}
                  on:menu={(event) => openPostMenu(
                    event.detail.event,
                    event.detail.post,
                    event.detail.anchorX,
                    event.detail.anchorY,
                  )}
                />
              {/each}
            </div>
          {/if}

          <div bind:this={sentinel} class={view === 'home' ? 'h-10' : 'hidden'} aria-hidden="true"></div>
          {#if view === 'home' && !activeSearch && loading && !initialLoading}
            <div class="pb-6 text-center text-sm text-[#818384]">Loading more saved posts…</div>
          {:else if ['home', 'popular'].includes(view) && !activeSearch && posts.length > 0 && !hasMore}
            <div class="pb-6 text-center text-xs text-[#68696b]">You reached the beginning of this local archive.</div>
          {/if}
        </section>

        <aside class="hidden space-y-4 lg:block">
          <section class="overflow-hidden rounded-xl border border-[#343536] bg-[#1a1a1b]">
            <div class="h-9 bg-[#ff4500]"></div>
            <div class="p-4">
              <h2 class="font-bold text-[#d7dadc]">Local archive</h2>
              <p class="mt-2 text-xs leading-5 text-[#a7a8aa]">Everything shown here comes from your SQLite index and local media store. The UI does not hotlink Reddit images.</p>
              {#if status}
                <dl class="mt-4 grid grid-cols-2 gap-3">
                  <div><dt class="text-[11px] text-[#818384]">Posts</dt><dd class="text-lg font-semibold">{compact(status.counts.posts)}</dd></div>
                  <div><dt class="text-[11px] text-[#818384]">Comments</dt><dd class="text-lg font-semibold">{compact(status.counts.comments)}</dd></div>
                  <div><dt class="text-[11px] text-[#818384]">Communities</dt><dd class="text-lg font-semibold">{compact(status.counts.communities)}</dd></div>
                  <div><dt class="text-[11px] text-[#818384]">Local media</dt><dd class="text-lg font-semibold">{compact(status.counts.media_objects)}</dd></div>
                </dl>
              {/if}
            </div>
          </section>

          <section class="rounded-xl border border-[#343536] bg-[#1a1a1b] p-4">
            <h2 class="text-sm font-bold">Save another link</h2>
            <p class="mt-2 text-xs leading-5 text-[#818384]">Paste one post, subreddit, or user-profile URL. The same bounded capture engine runs from the UI.</p>
            <code class="mt-3 block select-all break-all rounded bg-[#0f1011] p-3 text-[11px] leading-5 text-[#b8b9ba]">{CAPTURE_COMMAND}</code>
            <button type="button" class="mt-3 w-full rounded-full border border-[#d7dadc] py-2 text-xs font-bold hover:bg-white/10" on:click={copyCaptureCommand}>Copy command</button>
          </section>

          <div class="px-2 text-[11px] leading-5 text-[#68696b]">
            Scores and ratios are observations captured at a point in time. Reddit does not expose exact separate upvote/downvote totals.
          </div>
        </aside>
      </div>
    </main>
  </div>
  <nav class="fixed inset-x-0 bottom-0 z-40 grid h-16 grid-cols-4 border-t border-[#343536] bg-[#111213]/98 px-2 backdrop-blur md:hidden" aria-label="Reddit sections">
    <button type="button" class="text-xs font-semibold {view === 'home' ? 'text-[#ff4500]' : 'text-[#818384]'}" on:click={() => setView('home')}><span class="block text-lg">⌂</span>Home</button>
    <button type="button" class="text-xs font-semibold {view === 'popular' ? 'text-[#ff4500]' : 'text-[#818384]'}" on:click={() => setView('popular')}><span class="block text-lg">↗</span>Popular</button>
    <button type="button" class="text-xs font-semibold {view === 'communities' ? 'text-[#ff4500]' : 'text-[#818384]'}" on:click={() => setView('communities')}><span class="block text-lg">◉</span>Communities</button>
    <button type="button" class="text-xs font-semibold {view === 'profiles' ? 'text-[#ff4500]' : 'text-[#818384]'}" on:click={() => setView('profiles')}><span class="block text-lg">♙</span>Profiles</button>
  </nav>
</div>

{#if showAppMenu}
  <AppDrawer on:close={() => showAppMenu = false} />
{/if}

{#if showCapturePanel}
  <RedditCaptureDrawer
    initialUrl={captureInitialUrl}
    on:close={() => showCapturePanel = false}
    on:captured={captured}
    on:downloadstarted={downloadStarted}
  />
{/if}

{#if downloadActivityOpen}
  <RedditDownloadActivity jobs={mediaJobs} on:close={() => downloadActivityOpen = false} />
{/if}

{#if detailLoading && !selectedPost}
  <div class="fixed inset-0 z-[75] grid place-items-center bg-black/55 text-sm text-[#d7dadc]">Loading saved thread…</div>
{/if}

{#if selectedPost}
  <RedditThreadView
    detail={selectedPost}
    on:close={() => selectedPost = null}
    on:community={(event) => openCommunity(event.detail)}
    on:profile={(event) => openProfile(event.detail)}
    on:refresh={(event) => refreshPost(event.detail)}
  />
{/if}

{#if selectedCommunity}
  <RedditCommunityView
    community={selectedCommunity}
    on:close={() => selectedCommunity = null}
    on:refresh={(event) => refreshCommunity(event.detail)}
  />
{/if}

{#if selectedProfile}
  <RedditProfileView
    profile={selectedProfile}
    refreshing={refreshing === `profile:${selectedProfile.username}`}
    on:close={() => selectedProfile = null}
    on:open={(event) => openPost(event.detail)}
    on:community={(event) => openCommunity(event.detail)}
    on:refresh={(event) => refreshProfile(event.detail)}
  />
{/if}

<ActionMenu open={menuOpen} x={menuX} y={menuY} items={menuActions} on:close={() => menuOpen = false} />
