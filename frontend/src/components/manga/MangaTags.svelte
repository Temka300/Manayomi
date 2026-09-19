<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import { mangaApi, type HehTag } from './mangaApi';

  const dispatch = createEventDispatcher<{ selectTag: { name: string } }>();
  let sort: 'popular' | 'a-z' = 'popular';
  let tags: HehTag[] = [];
  let loading = false;
  let error = '';
  let query = '';

  $: normalizedQuery = query.trim().toLowerCase();
  $: visibleTags = normalizedQuery
    ? tags.filter((tag) => tag.name.toLowerCase().includes(normalizedQuery))
    : tags;

  async function load(nextSort: 'popular' | 'a-z') {
    sort = nextSort;
    loading = true;
    error = '';
    try {
      tags = (await mangaApi.hehTags(sort)).tags;
    } catch (reason) {
      error = reason instanceof Error ? reason.message : String(reason);
    } finally {
      loading = false;
    }
  }

  function countLabel(count: number): string {
    return count.toLocaleString();
  }

  onMount(() => void load('popular'));
</script>

<section class="h-full overflow-y-auto px-2 py-4 sm:px-4 sm:py-5" aria-labelledby="heh-tags-title">
  <div class="mx-auto max-w-[92rem]">
    <div class="heh-tag-toolbar sticky top-0 z-10 mb-3 rounded-xl border border-[#29293b] bg-[#101018]/95 p-3 shadow-lg shadow-black/20 backdrop-blur-md">
      <div class="flex items-center justify-between gap-3">
        <div class="min-w-0 text-left">
          <p class="text-[9px] font-semibold uppercase tracking-[0.22em] text-purple-400/60">HeH Library</p>
          <h2 id="heh-tags-title" class="mt-0.5 text-lg font-bold text-purple-100 sm:text-xl">Tags</h2>
        </div>
        <div class="inline-flex shrink-0 rounded-lg border border-[#303046] bg-[#12121c] p-1">
          <button class="rounded-md px-2.5 py-1.5 text-xs font-semibold sm:px-3 sm:text-sm {sort === 'popular' ? 'bg-purple-600 text-white' : 'text-gray-400 hover:text-gray-200'}" type="button" disabled={loading} on:click={() => void load('popular')}>Popular</button>
          <button class="rounded-md px-2.5 py-1.5 text-xs font-semibold sm:px-3 sm:text-sm {sort === 'a-z' ? 'bg-purple-600 text-white' : 'text-gray-400 hover:text-gray-200'}" type="button" disabled={loading} on:click={() => void load('a-z')}>A–Z</button>
        </div>
      </div>
      <label class="mt-2.5 flex h-9 items-center gap-2 rounded-lg border border-[#303046] bg-[#15151f] px-2.5 focus-within:border-purple-500/60">
        <svg class="h-4 w-4 shrink-0 text-gray-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
          <circle cx="10.8" cy="10.8" r="6.3" stroke-width="1.8" />
          <path d="m16 16 4 4" stroke-linecap="round" stroke-width="1.8" />
        </svg>
        <input
          class="min-w-0 flex-1 bg-transparent text-sm text-gray-200 placeholder-gray-600 outline-none"
          type="search"
          placeholder="Find a downloaded tag"
          aria-label="Find a downloaded tag"
          bind:value={query}
        />
      </label>
      <p class="mt-2 text-[11px] text-gray-600" aria-live="polite">
        {visibleTags.length.toLocaleString()} of {tags.length.toLocaleString()} downloaded tags with exact Library counts.
      </p>
    </div>

    {#if loading && tags.length === 0}
      <p class="rounded-xl border border-[#29293b] bg-[#12121a] p-8 text-center text-sm text-gray-500">Loading downloaded tags…</p>
    {:else if error}
      <div class="rounded-xl border border-red-500/30 bg-red-500/5 p-5 text-center">
        <p class="text-sm text-red-300">{error}</p>
        <button class="mt-3 rounded-lg border border-red-400/30 px-3 py-1.5 text-xs text-red-200" type="button" on:click={() => void load(sort)}>Try again</button>
      </div>
    {:else}
      <div class="heh-tag-columns rounded-xl border border-[#29293b] bg-[#111119] p-2 sm:p-3" aria-busy={loading}>
        {#if visibleTags.length === 0}
          <p class="px-3 py-10 text-center text-sm text-gray-500">No downloaded tags match “{query.trim()}”.</p>
        {:else}
          {#each visibleTags as tag (tag.slug)}
            <button class="heh-tag-entry mb-1 flex w-full min-w-0 items-stretch overflow-hidden rounded-md border border-transparent bg-[#1a1a25] text-left hover:border-purple-500/35 hover:bg-purple-500/10" type="button" title="Show downloaded manga tagged {tag.name}" on:click={() => dispatch('selectTag', { name: tag.name })}>
              <span class="min-w-0 flex-1 truncate bg-white/5 px-2 py-1 text-xs text-gray-300">{tag.name}</span>
              <span class="shrink-0 px-2 py-1 text-[11px] font-semibold tabular-nums text-purple-300/75">{countLabel(tag.count)}</span>
            </button>
          {/each}
        {/if}
      </div>
    {/if}
  </div>
</section>

<style>
  .heh-tag-columns { column-count: 2; column-gap: 0.45rem; }
  .heh-tag-entry { break-inside: avoid; }
  @media (max-width: 339px) { .heh-tag-columns { column-count: 1; } }
  @media (min-width: 560px) { .heh-tag-columns { column-count: 3; column-gap: 0.7rem; } }
  @media (min-width: 760px) { .heh-tag-columns { column-count: 4; } }
  @media (min-width: 1040px) { .heh-tag-columns { column-count: 5; } }
  @media (min-width: 1360px) { .heh-tag-columns { column-count: 6; } }
</style>
