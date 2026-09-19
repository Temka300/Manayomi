<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { focusTrap } from '../../lib/focusTrap';
  import type { RedditProfile } from '../../lib/redditApi';
  import RedditPostCard from './RedditPostCard.svelte';

  export let profile: RedditProfile;
  export let refreshing = false;

  const dispatch = createEventDispatcher<{
    close: void;
    open: string;
    community: string;
    refresh: string;
  }>();

  function compact(value: number): string {
    return Intl.NumberFormat(undefined, {
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(value);
  }

  function date(value: number | null): string {
    return value === null ? 'Unknown date' : new Date(value * 1000).toLocaleDateString();
  }
</script>

<div
  class="fixed inset-0 z-[80] bg-black/70 backdrop-blur-sm"
  role="presentation"
  on:click={(event) => { if (event.target === event.currentTarget) dispatch('close'); }}
>
  <div
    class="mx-auto flex h-full w-full max-w-[1060px] flex-col bg-[#0f1011] text-[#d7dadc] shadow-2xl shadow-black"
    role="dialog"
    aria-modal="true"
    aria-labelledby="reddit-profile-title"
    tabindex="-1"
    use:focusTrap={{ close: () => dispatch('close') }}
  >
    <header class="flex shrink-0 items-center gap-3 border-b border-[#343536] bg-[#1a1a1b] px-4 py-3">
      <span class="grid h-10 w-10 place-items-center rounded-full bg-[#272729] text-sm font-bold text-[#ff4500]">
        {profile.username.slice(0, 1).toUpperCase()}
      </span>
      <div class="min-w-0 flex-1">
        <h1 id="reddit-profile-title" class="truncate text-lg font-bold">u/{profile.username}</h1>
        <p class="text-xs text-[#818384]">Locally archived profile activity</p>
      </div>
      <button
        type="button"
        class="rounded-full border border-white/10 px-3 py-2 text-xs font-semibold hover:bg-white/10 disabled:opacity-45"
        disabled={refreshing}
        on:click={() => dispatch('refresh', profile.username)}
      >{refreshing ? 'Refreshing…' : 'Refresh profile'}</button>
      <button
        type="button"
        class="grid h-9 w-9 place-items-center rounded-full text-[#818384] hover:bg-[#272729] hover:text-white"
        aria-label="Close profile"
        on:click={() => dispatch('close')}
      >×</button>
    </header>

    <div class="min-h-0 flex-1 overflow-y-auto">
      <div class="mx-auto max-w-[820px] px-4 py-5">
        <dl class="mb-5 grid grid-cols-3 gap-3">
          <div class="rounded-xl border border-[#343536] bg-[#1a1a1b] p-4">
            <dt class="text-xs text-[#818384]">Posts</dt>
            <dd class="mt-1 text-xl font-bold">{compact(profile.stats.posts)}</dd>
          </div>
          <div class="rounded-xl border border-[#343536] bg-[#1a1a1b] p-4">
            <dt class="text-xs text-[#818384]">Comments</dt>
            <dd class="mt-1 text-xl font-bold">{compact(profile.stats.comments)}</dd>
          </div>
          <div class="rounded-xl border border-[#343536] bg-[#1a1a1b] p-4">
            <dt class="text-xs text-[#818384]">Saved score</dt>
            <dd class="mt-1 text-xl font-bold">{compact(profile.stats.score)}</dd>
          </div>
        </dl>

        <h2 class="mb-3 text-sm font-bold uppercase tracking-wide text-[#818384]">Archived posts</h2>
        {#if profile.posts.length}
          <div class="space-y-3">
            {#each profile.posts as post (post.id)}
              <RedditPostCard
                {post}
                on:open={(event) => dispatch('open', event.detail)}
                on:community={(event) => dispatch('community', event.detail)}
              />
            {/each}
          </div>
        {:else}
          <div class="rounded-xl border border-[#343536] bg-[#1a1a1b] p-6 text-center text-sm text-[#818384]">
            No posts from this profile are in the local archive yet.
          </div>
        {/if}

        <h2 class="mb-3 mt-7 text-sm font-bold uppercase tracking-wide text-[#818384]">Archived comments</h2>
        {#if profile.comments.length}
          <div class="space-y-2">
            {#each profile.comments as comment (comment.id)}
              <button
                type="button"
                class="block w-full rounded-xl border border-[#343536] bg-[#1a1a1b] p-4 text-left hover:border-[#4a4a55]"
                on:click={() => dispatch('open', comment.post_id)}
              >
                <div class="mb-2 text-xs text-[#818384]">
                  {#if comment.subreddit}
                    <span class="font-semibold text-[#d7dadc]">r/{comment.subreddit}</span>
                    <span class="px-1">•</span>
                  {/if}
                  {date(comment.created_utc)}
                  {#if comment.score !== null}<span class="px-1">•</span>{compact(comment.score)} points{/if}
                </div>
                <p class="line-clamp-5 whitespace-pre-wrap text-sm leading-6">{comment.body || '[removed]'}</p>
              </button>
            {/each}
          </div>
        {:else}
          <div class="rounded-xl border border-[#343536] bg-[#1a1a1b] p-6 text-center text-sm text-[#818384]">
            No comments from this profile are in the local archive yet.
          </div>
        {/if}
      </div>
    </div>
  </div>
</div>
