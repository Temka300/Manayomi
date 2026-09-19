<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import MangaBrowse from './MangaBrowse.svelte';
  import MangaDexBrowse from './MangaDexBrowse.svelte';

  type BrowseFilter = 'tags' | 'categories' | 'groups' | 'artists' | 'parodies' | 'characters';
  type Provider = 'nhentai' | 'mangadex';

  export let blur = true;
  export let enabled = false;
  export let coverSize: 'small' | 'current' | 'large' = 'current';
  export let ignoredTags: string[] = [];
  export let showIgnored = true;
  export let initialFilter: { key: BrowseFilter; value: string } | null = null;
  export let hideDownloaded = false;

  const dispatch = createEventDispatcher<{
    openRemote: { galleryId: number; forceCoverVisible: boolean };
    openMangaDex: { titleId: string; forceCoverVisible: boolean };
  }>();

  function savedProvider(): Provider {
    if (typeof localStorage === 'undefined' || initialFilter) return 'nhentai';
    return localStorage.getItem('manayomi:browse-provider') === 'mangadex' ? 'mangadex' : 'nhentai';
  }

  let provider: Provider = savedProvider();
  let filterOpen = false;
  let filterCount = 0;

  function selectProvider(next: Provider) {
    provider = next;
    filterOpen = false;
    filterCount = 0;
    localStorage.setItem('manayomi:browse-provider', next);
  }
</script>

<div class="flex h-full min-h-0 flex-col">
  <div class="provider-strip relative flex shrink-0 items-center justify-center gap-1 border-b border-[#26263a] bg-[#111119] px-2 py-1.5">
    <div class="provider-tabs flex items-center gap-1" role="tablist" aria-label="Browse source">
      <button
        type="button"
        role="tab"
        aria-selected={provider === 'nhentai'}
        class:active={provider === 'nhentai'}
        on:click={() => selectProvider('nhentai')}
      >nHentai</button>
      <button
        type="button"
        role="tab"
        aria-selected={provider === 'mangadex'}
        class:active={provider === 'mangadex'}
        on:click={() => selectProvider('mangadex')}
      >MangaDex</button>
    </div>
    <button
      class="filter-button absolute right-2 grid h-8 grid-flow-col place-items-center gap-1.5 px-2"
      class:active={filterOpen || filterCount > 0}
      type="button"
      aria-label={`Toggle ${provider === 'mangadex' ? 'MangaDex' : 'nHentai'} filters`}
      aria-expanded={filterOpen}
      disabled={provider === 'nhentai' && !enabled}
      on:click|stopPropagation={() => (filterOpen = !filterOpen)}
    >
      <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path d="M4 5h16l-6.5 7.2v5.3l-3 1.5v-6.8L4 5Z" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" /></svg>
      <span class="hidden text-[11px] sm:inline">Filter</span>
      {#if filterCount > 0}<span class="rounded-full bg-purple-400/25 px-1 text-[9px] text-purple-100">{filterCount}</span>{/if}
    </button>
  </div>

  <div class="min-h-0 flex-1">
    {#if provider === 'nhentai'}
      <MangaBrowse
        {blur}
        {enabled}
        {coverSize}
        {ignoredTags}
        {showIgnored}
        {initialFilter}
        {hideDownloaded}
        bind:filterOpen
        bind:filterCount
        on:openRemote={(event) => dispatch('openRemote', event.detail)}
      />
    {:else}
      <MangaDexBrowse
        {blur}
        {coverSize}
        {ignoredTags}
        {showIgnored}
        {hideDownloaded}
        bind:filterOpen
        bind:filterCount
        on:openTitle={(event) => dispatch('openMangaDex', event.detail)}
      />
    {/if}
  </div>
</div>

<style>
  .provider-tabs button, .filter-button {
    min-width: 6.5rem;
    border: 1px solid #303044;
    border-radius: 0.55rem;
    padding: 0.35rem 0.85rem;
    color: #8f8f9f;
    font-size: 0.75rem;
    font-weight: 700;
    transition: border-color 150ms ease, background 150ms ease, color 150ms ease;
  }
  .provider-tabs button:hover, .filter-button:hover { color: #e9d5ff; }
  .provider-tabs button.active, .filter-button.active {
    border-color: rgba(168, 85, 247, 0.58);
    background: rgba(168, 85, 247, 0.15);
    color: #f3e8ff;
  }
  .filter-button:disabled { cursor:not-allowed; opacity:.35; }
  @media (max-width:639px) {
    .provider-strip { justify-content:flex-start; }
    .provider-tabs button { min-width:5.75rem; padding-inline:.6rem; }
  }
</style>
