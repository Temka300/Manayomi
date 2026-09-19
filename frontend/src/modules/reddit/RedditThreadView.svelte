<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { focusTrap } from '../../lib/focusTrap';
  import {
    redditMediaUrl,
    type RedditPostDetail,
  } from '../../lib/redditApi';
  import RedditCommentBranch from './RedditCommentBranch.svelte';
  import RedditLinkCards from './RedditLinkCards.svelte';
  import { renderRedditBody } from './redditBody';

  export let detail: RedditPostDetail;

  const dispatch = createEventDispatcher<{
    close: void;
    community: string;
    refresh: string;
    profile: string;
  }>();

  $: previews = detail.media.local.filter((item) =>
    item.content_type?.startsWith('image/') || item.content_type?.startsWith('video/')
  );
  $: attachments = detail.media.local.filter((item) =>
    !item.content_type?.startsWith('image/') && !item.content_type?.startsWith('video/')
  );
  $: scorePoints = observationPoints('score');
  $: commentPoints = observationPoints('num_comments');
  $: ratioPoints = observationPoints('upvote_ratio');

  function observationPoints(key: string): string {
    const values = detail.observations
      .map((entry) => Number(entry[key]))
      .filter(Number.isFinite);
    if (values.length < 2) return '';
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = Math.max(1, max - min);
    return values.map((value, index) => {
      const x = (index / Math.max(1, values.length - 1)) * 300;
      const y = 70 - ((value - min) / span) * 60;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
  }

  function compactNumber(value: number | null): string {
    return value === null
      ? '—'
      : Intl.NumberFormat(undefined, {
          notation: 'compact',
          maximumFractionDigits: 1,
        }).format(value);
  }

  function date(value: number | null): string {
    return value === null ? 'Unknown date' : new Date(value * 1000).toLocaleString();
  }
</script>

<div class="fixed inset-0 z-[80] bg-black/70 backdrop-blur-sm" role="presentation" on:click={(event) => { if (event.target === event.currentTarget) dispatch('close'); }}>
  <div
    class="mx-auto flex h-full w-full max-w-[1060px] flex-col bg-[#0f1011] shadow-2xl shadow-black"
    role="dialog"
    aria-modal="true"
    aria-label="Saved Reddit post"
    tabindex="-1"
    use:focusTrap={{ close: () => dispatch('close') }}
  >
    <header class="flex min-h-14 shrink-0 items-center gap-3 border-b border-[#343536] bg-[#1a1a1b] px-4 py-2">
      <div class="flex items-center gap-1 text-sm font-semibold text-[#d7dadc]">
        <span class="text-lg text-[#ff4500]">●</span>
        <span>{compactNumber(detail.post.score)}</span>
      </div>
      <div class="min-w-0 flex-1 truncate text-sm text-[#818384]">
        {#if detail.post.subreddit}
          <button type="button" class="font-semibold text-[#d7dadc] hover:underline" on:click={() => dispatch('community', detail.post.subreddit ?? '')}>r/{detail.post.subreddit}</button>
          <span class="px-1">•</span>
        {/if}
        {#if detail.post.author}
          <button type="button" class="hover:text-white hover:underline" on:click={() => dispatch('profile', detail.post.author ?? '')}>u/{detail.post.author}</button>
        {:else}
          u/[deleted]
        {/if}
        <span> • {date(detail.post.created_utc)}</span>
      </div>
      <button type="button" class="rounded-full border border-white/10 px-3 py-2 text-xs font-semibold hover:bg-white/7" on:click={() => dispatch('refresh', detail.post.id)}>Refresh snapshot</button>
      <button type="button" class="grid h-9 w-9 place-items-center rounded-full text-[#818384] hover:bg-[#272729] hover:text-white" aria-label="Close post" on:click={() => dispatch('close')}>×</button>
    </header>

    <div class="min-h-0 flex-1 overflow-y-auto">
      <article class="border-b border-[#343536] bg-[#1a1a1b] px-5 py-5">
        <div class="flex flex-wrap items-center gap-2">
          <h1 class="text-2xl font-medium leading-8 text-[#d7dadc]">{detail.post.title || '(untitled post)'}</h1>
          {#if detail.post.flair_text}<span class="rounded-full bg-[#343536] px-2 py-1 text-xs font-semibold">{detail.post.flair_text}</span>{/if}
        </div>
        {#if detail.post.selftext}<div class="post-body mt-4 whitespace-pre-wrap text-[15px] leading-7 text-[#d7dadc]">{@html renderRedditBody(detail.post.selftext)}</div>{/if}
        {#if previews.length}
          <div class="mt-5 grid gap-3">
            {#each previews as preview (preview.sha256)}
              <div class="overflow-hidden rounded-lg bg-black">
                {#if preview.content_type?.startsWith('video/')}
                  <!-- svelte-ignore a11y_media_has_caption -->
                  <video class="max-h-[720px] w-full object-contain" src={redditMediaUrl(preview.sha256)} controls preload="metadata"></video>
                {:else}
                  <img class="max-h-[760px] w-full object-contain" src={redditMediaUrl(preview.sha256)} alt="" />
                {/if}
              </div>
            {/each}
          </div>
        {/if}
        {#if attachments.length}
          <div class="mt-4 flex flex-wrap gap-2">
            {#each attachments as attachment (attachment.sha256)}
              <a href={redditMediaUrl(attachment.sha256)} class="max-w-full truncate rounded-full border border-[#343536] bg-[#111213] px-3 py-2 text-xs font-semibold text-[#4fbcff] hover:border-[#4fbcff]/60">Download saved file: {attachment.display_name}</a>
            {/each}
          </div>
        {/if}
        <RedditLinkCards links={detail.post.links} />
        <div class="mt-4 flex flex-wrap gap-3 text-xs text-[#818384]">
          <span>{compactNumber(detail.post.num_comments)} declared comments</span>
          {#if detail.post.upvote_ratio !== null}<span>{Math.round(detail.post.upvote_ratio * 100)}% upvoted</span>{/if}
          <span>{detail.observations.length} saved observation{detail.observations.length === 1 ? '' : 's'}</span>
          {#if detail.comment_tree.placeholders.length}<span class="text-amber-300">{detail.comment_tree.placeholders.length} preserved gap marker{detail.comment_tree.placeholders.length === 1 ? '' : 's'}</span>{/if}
        </div>
      </article>

      {#if detail.observations.length > 1}
        <section class="mx-auto mt-5 grid max-w-[920px] gap-3 px-4 md:grid-cols-3" aria-label="Saved observation history">
          <div class="rounded-xl border border-[#343536] bg-[#1a1a1b] p-4">
            <div class="flex justify-between text-xs"><strong>Score history</strong><span class="text-[#818384]">{detail.observations.length} observations</span></div>
            <svg class="mt-3 h-20 w-full overflow-visible" viewBox="0 0 300 80" preserveAspectRatio="none" role="img" aria-label="Score over saved observations"><polyline points={scorePoints} fill="none" stroke="#ff4500" stroke-width="3" vector-effect="non-scaling-stroke" /></svg>
          </div>
          <div class="rounded-xl border border-[#343536] bg-[#1a1a1b] p-4">
            <div class="flex justify-between text-xs"><strong>Comment-count history</strong><span class="text-[#818384]">Captured values</span></div>
            <svg class="mt-3 h-20 w-full overflow-visible" viewBox="0 0 300 80" preserveAspectRatio="none" role="img" aria-label="Comment count over saved observations"><polyline points={commentPoints} fill="none" stroke="#4fbcff" stroke-width="3" vector-effect="non-scaling-stroke" /></svg>
          </div>
          <div class="rounded-xl border border-[#343536] bg-[#1a1a1b] p-4">
            <div class="flex justify-between text-xs"><strong>Upvote-ratio history</strong><span class="text-[#818384]">Captured values</span></div>
            <svg class="mt-3 h-20 w-full overflow-visible" viewBox="0 0 300 80" preserveAspectRatio="none" role="img" aria-label="Upvote ratio over saved observations"><polyline points={ratioPoints} fill="none" stroke="#facc15" stroke-width="3" vector-effect="non-scaling-stroke" /></svg>
          </div>
        </section>
      {/if}

      <div class="mx-auto max-w-[920px] px-4 py-5">
        <h2 class="mb-4 text-sm font-semibold uppercase tracking-wide text-[#818384]">Archived comments ({detail.post.archived_comment_count})</h2>
        {#if detail.comment_tree.root_comments.length === 0 && detail.comment_tree.detached_comments.length === 0}
          <div class="rounded-lg border border-[#343536] bg-[#1a1a1b] px-4 py-8 text-center text-sm text-[#818384]">No comments were captured for this saved post.</div>
        {:else}
          <div class="space-y-1">
            {#each detail.comment_tree.root_comments as comment (comment.id)}
              <RedditCommentBranch node={comment} />
            {/each}
            {#each detail.comment_tree.detached_comments as comment (comment.id)}
              <RedditCommentBranch node={comment} detached={true} />
            {/each}
          </div>
        {/if}
      </div>
    </div>
  </div>
</div>

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
    max-height: 720px;
    border-radius: 0.5rem;
    margin-top: 0.5rem;
    margin-bottom: 0.25rem;
    object-fit: contain;
  }
</style>
