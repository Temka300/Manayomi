<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import {
    redditMediaUrl,
    type RedditLocalMedia,
    type RedditPost,
  } from '../../lib/redditApi';
  import RedditLinkCards from './RedditLinkCards.svelte';
  import { renderRedditBody } from './redditBody';

  export let post: RedditPost;
  const dispatch = createEventDispatcher<{
    open: string;
    community: string;
    profile: string;
    menu: { event: MouseEvent; post: RedditPost; anchorX: number; anchorY: number };
  }>();
  let failedMedia = new Set<string>();

  $: preview = post.media.local.find((item) =>
    !failedMedia.has(item.sha256)
    && (item.content_type?.startsWith('image/') || item.content_type?.startsWith('video/'))
  ) ?? null;
  $: attachments = post.media.local.filter((item) =>
    item.sha256 !== preview?.sha256
  );

  function markMediaFailed(media: RedditLocalMedia) {
    failedMedia = new Set([...failedMedia, media.sha256]);
  }

  function openMenu(event: MouseEvent) {
    const bounds = (event.currentTarget as HTMLElement).getBoundingClientRect();
    dispatch('menu', {
      event,
      post,
      anchorX: bounds.left,
      anchorY: bounds.bottom,
    });
  }

  function compactNumber(value: number | null): string {
    if (value === null) return '—';
    return Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 }).format(value);
  }

  function relativeTime(value: number | null): string {
    if (value === null) return 'unknown date';
    const seconds = Math.max(0, Date.now() / 1000 - value);
    if (seconds < 3600) return `${Math.max(1, Math.floor(seconds / 60))}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    if (seconds < 86400 * 365) return `${Math.floor(seconds / 86400)}d ago`;
    return new Date(value * 1000).toLocaleDateString();
  }
</script>

<article
  data-reddit-post-id={post.id}
  class="reddit-card overflow-hidden rounded-xl border border-[#34343d] bg-[#1a1a1b] shadow-[0_12px_36px_rgba(0,0,0,0.18)] transition-colors hover:border-[#4a4a55]"
  on:contextmenu|preventDefault={openMenu}
>
  <div class="flex">
    <aside class="flex w-11 shrink-0 flex-col items-center gap-1 bg-[#151516] py-3 text-[#818384]" aria-label="Archived score">
      <svg class="h-5 w-5 text-[#d7dadc]" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M12 4l7 8h-4v8H9v-8H5l7-8z" />
      </svg>
      <strong class="text-xs text-[#d7dadc]">{compactNumber(post.score)}</strong>
      <svg class="h-5 w-5 rotate-180" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M12 4l7 8h-4v8H9v-8H5l7-8z" />
      </svg>
    </aside>

    <div class="min-w-0 flex-1">
      <div class="px-4 pt-3 text-xs text-[#818384]">
        {#if post.subreddit}
          <button
            type="button"
            class="font-semibold text-[#d7dadc] hover:underline"
            on:click={() => dispatch('community', post.subreddit ?? '')}
          >r/{post.subreddit}</button>
          <span class="px-1">•</span>
        {/if}
        <span>Posted by </span>
        {#if post.author}
          <button type="button" class="hover:text-white hover:underline" on:click={() => dispatch('profile', post.author ?? '')}>u/{post.author}</button>
        {:else}
          <span>u/[deleted]</span>
        {/if}
        <span class="px-1">•</span>
        <time>{relativeTime(post.created_utc)}</time>
        {#if post.latest_observed_at}
          <span class="ml-1 text-[#68696b]" title={`Latest local observation: ${post.latest_observed_at}`}>archived</span>
        {/if}
      </div>

      <button
        class="block w-full px-4 pb-2 pt-2 text-left"
        type="button"
        on:click={() => dispatch('open', post.id)}
      >
        <span class="flex flex-wrap items-center gap-2">
          <h2 class="text-lg font-medium leading-6 text-[#d7dadc]">{post.title || '(untitled post)'}</h2>
          {#if post.flair_text}
            <span class="rounded-full bg-[#343536] px-2 py-0.5 text-[11px] font-semibold text-[#d7dadc]">{post.flair_text}</span>
          {/if}
          {#if post.nsfw}
            <span class="rounded border border-[#ff585b] px-1.5 py-0.5 text-[10px] font-bold text-[#ff585b]">NSFW</span>
          {/if}
        </span>
      </button>

      {#if preview}
        <button
          type="button"
          class="block w-full bg-black/45"
          aria-label="Open saved post"
          on:click={() => dispatch('open', post.id)}
        >
          {#if preview.content_type?.startsWith('video/')}
            <!-- svelte-ignore a11y_media_has_caption -->
            <video
              class="max-h-[640px] w-full bg-black object-contain"
              src={redditMediaUrl(preview.sha256)}
              controls
              preload="metadata"
              on:error={() => markMediaFailed(preview as RedditLocalMedia)}
              on:click|stopPropagation
            ></video>
          {:else}
            <img
              class="max-h-[720px] w-full bg-black object-contain"
              src={redditMediaUrl(preview.sha256)}
              alt=""
              loading="lazy"
              on:error={() => markMediaFailed(preview as RedditLocalMedia)}
            />
          {/if}
        </button>
      {:else if post.selftext}
        <button
          class="block w-full px-4 pb-3 text-left"
          type="button"
          on:click={() => dispatch('open', post.id)}
        >
          <div class="post-body line-clamp-5 whitespace-pre-wrap text-sm leading-6 text-[#b8b9ba]">{@html renderRedditBody(post.selftext)}</div>
        </button>
      {/if}

      {#if attachments.length}
        <div class="mx-4 mb-3 flex flex-wrap gap-2">
          {#each attachments as attachment (attachment.sha256)}
            <a
              href={redditMediaUrl(attachment.sha256)}
              class="max-w-full truncate rounded-full border border-[#343536] bg-[#111213] px-3 py-1.5 text-xs font-semibold text-[#4fbcff] hover:border-[#4fbcff]/60"
            >
              Saved: {attachment.display_name}
            </a>
          {/each}
        </div>
      {/if}

      <RedditLinkCards links={post.links} />

      {#if post.media.queued_count > 0 && post.media.local.length === 0}
        <div class="mx-4 mb-2 rounded-md border border-dashed border-[#3d3d45] px-3 py-2 text-xs text-[#818384]">
          {post.media.queued_count} media reference{post.media.queued_count === 1 ? '' : 's'} saved; local bytes have not been downloaded.
        </div>
      {/if}

      <footer class="flex items-center gap-1 px-2 pb-2 text-xs font-semibold text-[#818384]">
        <button
          type="button"
          class="flex items-center gap-1.5 rounded px-2 py-2 hover:bg-[#272729] hover:text-[#d7dadc]"
          on:click={() => dispatch('open', post.id)}
        >
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M4 4h16v12H8l-4 4V4zm3 4v2h10V8H7zm0 4v2h7v-2H7z" />
          </svg>
          {compactNumber(post.archived_comment_count)} archived comments
        </button>
        {#if post.upvote_ratio !== null}
          <span class="rounded px-2 py-2">{Math.round(post.upvote_ratio * 100)}% upvoted</span>
        {/if}
        {#if post.locked}<span class="rounded px-2 py-2 text-amber-300">Locked</span>{/if}
        {#if post.archived}<span class="rounded px-2 py-2">Archived</span>{/if}
        <button
          type="button"
          class="ml-auto grid h-8 w-8 place-items-center rounded-full text-lg leading-none hover:bg-[#272729] hover:text-white"
          aria-label="More actions for saved post"
          title="More actions"
          on:click={openMenu}
        >•••</button>
      </footer>
    </div>
  </div>
</article>

<style>
  .post-body :global(a) {
    color: #4fbcff;
    text-decoration: none;
  }
  .post-body :global(a:hover) {
    text-decoration: underline;
  }
  .post-body :global(img) {
    display: block;
    max-width: 100%;
    max-height: 540px;
    border-radius: 0.5rem;
    margin-top: 0.5rem;
    margin-bottom: 0.25rem;
    object-fit: contain;
  }
</style>
