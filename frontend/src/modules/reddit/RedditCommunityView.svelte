<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { focusTrap } from '../../lib/focusTrap';
  import {
    redditMediaUrl,
    type RedditCommunity,
  } from '../../lib/redditApi';

  export let community: RedditCommunity;
  const dispatch = createEventDispatcher<{ close: void; refresh: string }>();

  function text(value: unknown): string {
    return typeof value === 'string' ? value : '';
  }

  function number(value: unknown): string {
    return typeof value === 'number'
      ? Intl.NumberFormat().format(value)
      : '—';
  }

  $: icon = community.media?.local.find((item) =>
    item.content_type?.startsWith('image/')
    && ['subreddit-icon', 'subreddit-banner'].includes(item.role)
  ) ?? null;

  function keydown(event: KeyboardEvent) {
    if (event.key === 'Escape') dispatch('close');
  }

  function backdropClick(event: MouseEvent) {
    if (event.target === event.currentTarget) dispatch('close');
  }
</script>

<svelte:window on:keydown={keydown} />

<div class="fixed inset-0 z-[80] bg-black/70 backdrop-blur-sm" role="presentation" on:click={backdropClick}>
  <div
    class="ml-auto flex h-full w-full max-w-[720px] flex-col border-l border-[#343536] bg-[#0f1011] shadow-2xl"
    role="dialog"
    aria-modal="true"
    aria-label={`Saved r/${community.subreddit} community information`}
    tabindex="-1"
    use:focusTrap={{ close: () => dispatch('close') }}
  >
    <div class="h-24 shrink-0 bg-gradient-to-r from-[#ff4500] via-[#d63a00] to-[#7b260d]"></div>
    <header class="-mt-8 flex shrink-0 items-end gap-4 border-b border-[#343536] bg-[#1a1a1b] px-5 pb-4">
      <div class="grid h-20 w-20 shrink-0 place-items-center overflow-hidden rounded-full border-4 border-[#1a1a1b] bg-white text-3xl font-bold text-[#ff4500]">
        {#if icon}
          <img class="h-full w-full object-cover" src={redditMediaUrl(icon.sha256)} alt="" />
        {:else}
          r/
        {/if}
      </div>
      <div class="min-w-0 flex-1 pb-1">
        <h1 class="truncate text-2xl font-bold text-[#d7dadc]">r/{community.subreddit}</h1>
        <p class="truncate text-sm text-[#818384]">{text(community.about?.title) || 'Saved community snapshot'}</p>
      </div>
      <button
        type="button"
        class="mb-2 rounded-full border border-white/10 px-3 py-2 text-xs font-semibold text-[#d7dadc] hover:bg-white/10"
        on:click={() => dispatch('refresh', community.subreddit)}
      >Refresh</button>
      <button
        type="button"
        class="mb-2 grid h-9 w-9 place-items-center rounded-full text-[#818384] hover:bg-[#272729] hover:text-white"
        aria-label="Close community"
        on:click={() => dispatch('close')}
      >
        <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-width="2" d="M6 6l12 12M18 6L6 18" />
        </svg>
      </button>
    </header>

    <div class="min-h-0 flex-1 space-y-4 overflow-y-auto p-5">
      <section class="rounded-xl border border-[#343536] bg-[#1a1a1b] p-4">
        <h2 class="text-sm font-bold uppercase tracking-wide text-[#d7dadc]">About community</h2>
        {#if community.about}
          <p class="mt-3 whitespace-pre-wrap text-sm leading-6 text-[#c7c8c9]">
            {text(community.about.public_description) || text(community.about.description) || 'No description was present in this snapshot.'}
          </p>
          <div class="mt-4 grid grid-cols-2 gap-3 text-sm">
            <div class="rounded-lg bg-[#272729] p-3">
              <strong class="block text-lg text-[#d7dadc]">{number(community.about.subscribers)}</strong>
              <span class="text-xs text-[#818384]">members at capture</span>
            </div>
            <div class="rounded-lg bg-[#272729] p-3">
              <strong class="block text-lg text-[#d7dadc]">{community.history.about}</strong>
              <span class="text-xs text-[#818384]">about snapshots</span>
            </div>
          </div>
        {:else}
          <p class="mt-3 text-sm text-[#818384]">No about snapshot has been saved.</p>
        {/if}
      </section>

      <section class="rounded-xl border border-[#343536] bg-[#1a1a1b] p-4">
        <h2 class="text-sm font-bold uppercase tracking-wide text-[#d7dadc]">Rules</h2>
        {#if community.rules?.items.length}
          <ol class="mt-3 space-y-3">
            {#each community.rules.items as rule, index}
              <li class="flex gap-3 text-sm">
                <span class="font-bold text-[#818384]">{index + 1}.</span>
                <div>
                  <h3 class="font-semibold text-[#d7dadc]">{text(rule.short_name) || 'Untitled rule'}</h3>
                  {#if text(rule.description)}
                    <p class="mt-1 whitespace-pre-wrap leading-6 text-[#aeb0b1]">{text(rule.description)}</p>
                  {/if}
                </div>
              </li>
            {/each}
          </ol>
        {:else}
          <p class="mt-3 text-sm text-[#818384]">The latest saved snapshot contains no rules.</p>
        {/if}
      </section>

      <section class="rounded-xl border border-[#343536] bg-[#1a1a1b] p-4">
        <div class="flex items-center justify-between">
          <h2 class="text-sm font-bold uppercase tracking-wide text-[#d7dadc]">Wiki</h2>
          <span class="text-xs text-[#818384]">{community.wiki.length} latest page{community.wiki.length === 1 ? '' : 's'}</span>
        </div>
        {#if community.wiki.length}
          <div class="mt-3 space-y-3">
            {#each community.wiki as page}
              <details class="rounded-lg bg-[#272729] px-3 py-2">
                <summary class="cursor-pointer text-sm font-semibold text-[#d7dadc]">{text(page.path)}</summary>
                <pre class="mt-3 whitespace-pre-wrap font-sans text-sm leading-6 text-[#b8b9ba]">{text(page.content)}</pre>
              </details>
            {/each}
          </div>
        {:else}
          <p class="mt-3 text-sm text-[#818384]">No wiki pages have been saved.</p>
        {/if}
      </section>

      <section class="rounded-xl border border-[#343536] bg-[#1a1a1b] p-4">
        <h2 class="text-sm font-bold uppercase tracking-wide text-[#d7dadc]">Moderators</h2>
        {#if community.moderators?.items.length}
          <div class="mt-3 flex flex-wrap gap-2">
            {#each community.moderators.items as moderator}
              <span class="rounded-full bg-[#272729] px-3 py-1.5 text-sm text-[#d7dadc]">u/{text(moderator.username)}</span>
            {/each}
          </div>
        {:else}
          <p class="mt-3 text-sm leading-6 text-amber-200">
            No local moderator snapshot is available. The direct Arctic Shift adapter cannot claim current moderator membership.
          </p>
        {/if}
      </section>
    </div>
  </div>
</div>
