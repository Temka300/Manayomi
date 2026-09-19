<script lang="ts">
  import type { RedditCommentNode } from '../../lib/redditApi';
  import { renderRedditBody } from './redditBody';

  export let node: RedditCommentNode;
  export let depth = 0;
  export let detached = false;

  let collapsed = false;

  function compact(value: number | null): string {
    return value === null
      ? '—'
      : Intl.NumberFormat(undefined, {
          notation: 'compact',
          maximumFractionDigits: 1,
        }).format(value);
  }
</script>

<article
  class="relative min-w-0 border-l border-[#3b3b42] py-2 pl-3"
  class:bg-amber-950={detached}
  style={`margin-left: ${depth === 0 ? 0 : depth < 7 ? 14 : 4}px`}
>
  <div class="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-xs text-[#818384]">
    {#if node.children.length}
      <button
        type="button"
        class="grid h-5 w-5 shrink-0 place-items-center rounded border border-white/10 text-[11px] hover:bg-white/8 hover:text-white"
        aria-label={collapsed ? `Expand replies to ${node.author ?? 'deleted user'}` : `Collapse replies to ${node.author ?? 'deleted user'}`}
        aria-expanded={!collapsed}
        on:click={() => collapsed = !collapsed}
      >{collapsed ? '+' : '−'}</button>
    {:else}
      <span class="h-5 w-5 shrink-0"></span>
    {/if}
    <span class="min-w-0 break-all font-semibold text-[#c8c9ca]">u/{node.author ?? '[deleted]'}</span>
    <span>•</span>
    <span>{compact(node.score)} points</span>
    {#if node.children.length}<span class="text-[#626366]">{node.children.length} direct repl{node.children.length === 1 ? 'y' : 'ies'}</span>{/if}
    {#if detached}<span class="text-amber-300">detached branch</span>{/if}
  </div>
  <div class="comment-body mt-1 min-w-0 break-words whitespace-pre-wrap text-sm leading-6 text-[#d7dadc]">
    {#if node.body}
      {@html renderRedditBody(node.body)}
    {:else}
      [{node.body_state}]
    {/if}
  </div>
  {#if collapsed}
    <button type="button" class="mt-2 text-xs font-semibold text-[#4fbcff] hover:underline" on:click={() => collapsed = false}>
      Show {node.children.length} hidden repl{node.children.length === 1 ? 'y' : 'ies'}
    </button>
  {:else if node.children.length}
    <div class="mt-1">
      {#each node.children as child (child.id)}
        <svelte:self node={child} depth={depth + 1} {detached} />
      {/each}
    </div>
  {/if}
</article>

<style>
  .comment-body :global(a) {
    color: #4fbcff;
    text-decoration: none;
  }
  .comment-body :global(a:hover) {
    text-decoration: underline;
  }
  .comment-body :global(img) {
    display: block;
    max-width: 100%;
    max-height: 540px;
    border-radius: 0.5rem;
    margin-top: 0.5rem;
    margin-bottom: 0.25rem;
    object-fit: contain;
  }
</style>
