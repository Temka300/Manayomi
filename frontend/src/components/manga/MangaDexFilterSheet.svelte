<script lang="ts">
  import { createEventDispatcher, tick } from 'svelte';
  import type {
    MangaDexBrowseFilters,
    MangaDexFilterCatalog,
    MangaDexFilterOption,
    MangaDexTag
  } from './mangaApi';

  export let open = false;
  export let catalog: MangaDexFilterCatalog | null = null;
  export let values: MangaDexBrowseFilters;
  export let loading = false;
  export let error = '';
  export let hasActive = false;

  const dispatch = createEventDispatcher<{
    close: void;
    apply: void;
    clear: void;
    retry: void;
    change: MangaDexBrowseFilters;
  }>();

  type MultiKey =
    | 'originalLanguages'
    | 'contentRatings'
    | 'publicationDemographics'
    | 'statuses'
    | 'includedTags';

  const TAG_GROUPS: { key: 'content' | 'format' | 'genre' | 'theme'; label: string }[] = [
    { key: 'content', label: 'Content' },
    { key: 'format', label: 'Format' },
    { key: 'genre', label: 'Genre' },
    { key: 'theme', label: 'Theme' }
  ];

  let panel: HTMLElement;
  let wasOpen = false;

  $: if (open && !wasOpen) {
    wasOpen = true;
    void tick().then(() => panel?.focus());
  } else if (!open) {
    wasOpen = false;
  }

  function update(change: Partial<MangaDexBrowseFilters>) {
    dispatch('change', { ...values, ...change });
  }

  function toggle(key: MultiKey, value: string) {
    const current = values[key];
    const next = current.includes(value)
      ? current.filter((item) => item !== value)
      : [...current, value];
    update({ [key]: next });
  }

  function selectedSummary(
    selected: string[],
    options: Array<MangaDexFilterOption | MangaDexTag>,
    fallback: string
  ): string {
    if (!selected.length) return fallback;
    const labels = selected.map((value) => {
      const option = options.find((candidate) =>
        'value' in candidate ? candidate.value === value : candidate.id === value
      );
      return option ? ('label' in option ? option.label : option.name) : value;
    });
    return labels.length <= 2 ? labels.join(', ') : `${labels.length} selected`;
  }

  function groupSelected(group: 'content' | 'format' | 'genre' | 'theme'): string[] {
    const ids = new Set((catalog?.tag_groups[group] ?? []).map((tag) => tag.id));
    return values.includedTags.filter((id) => ids.has(id));
  }

  function onWindowKeydown(event: KeyboardEvent) {
    if (open && event.key === 'Escape') dispatch('close');
  }

  function onWindowClick(event: MouseEvent) {
    if (open && panel && !panel.contains(event.target as Node)) dispatch('close');
  }
</script>

<svelte:window on:keydown={onWindowKeydown} on:click={onWindowClick} />

{#if open}
  <div
    class="md-filter-popover absolute left-0 top-full z-[70] mt-2 overflow-y-auto rounded-xl border border-[#303046] bg-[#111119] shadow-2xl shadow-black/60"
    role="dialog"
    aria-label="MangaDex filters"
    tabindex="-1"
    bind:this={panel}
  >
    <header class="sticky top-0 z-10 flex items-center justify-between border-b border-[#29293d] bg-[#111119] px-3 py-2">
      <div>
        <h2 class="text-xs font-semibold text-purple-100">MangaDex filters</h2>
        <p class="text-[10px] text-gray-600">Tags are loaded from MangaDex</p>
      </div>
      <button type="button" class="grid h-7 w-7 place-items-center rounded-full text-xs text-gray-500 hover:bg-white/5 hover:text-purple-100" aria-label="Close MangaDex filters" on:click={() => dispatch('close')}>✕</button>
    </header>

    {#if loading}
      <p class="p-5 text-center text-xs text-gray-500">Loading MangaDex filter words…</p>
    {:else if error}
      <div class="p-3 text-xs">
        <p class="rounded-lg border border-red-500/30 bg-red-500/10 p-2 text-red-300">{error}</p>
        <button type="button" class="mt-2 rounded-md border border-[#343447] px-3 py-1.5 text-gray-200" on:click={() => dispatch('retry')}>Retry</button>
      </div>
    {:else if catalog}
      <form class="p-3" on:submit|preventDefault={() => dispatch('apply')}>
        <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <label class="filter-field">
            <span>Translated language</span>
            <select value={values.language} on:change={(event) => update({ language: event.currentTarget.value })}>
              <option value="all">All languages</option>
              {#each catalog.languages as option (option.value)}<option value={option.value}>{option.label}</option>{/each}
            </select>
          </label>

          <label class="filter-field">
            <span>Sort</span>
            <select value={values.sort} on:change={(event) => update({ sort: event.currentTarget.value })}>
              {#each catalog.sorts as option (option.value)}<option value={option.value}>{option.label}</option>{/each}
            </select>
          </label>

          <details class="filter-dropdown">
            <summary><span>Original language</span><b>{selectedSummary(values.originalLanguages, catalog.languages, 'Any')}</b></summary>
            <div class="option-list">
              {#each catalog.languages as option (option.value)}
                <label><input type="checkbox" checked={values.originalLanguages.includes(option.value)} on:change={() => toggle('originalLanguages', option.value)} /><span>{option.label}</span></label>
              {/each}
            </div>
          </details>

          <details class="filter-dropdown">
            <summary><span>Content rating</span><b>{selectedSummary(values.contentRatings, catalog.content_ratings, 'All')}</b></summary>
            <div class="option-list short">
              {#each catalog.content_ratings as option (option.value)}
                <label><input type="checkbox" checked={values.contentRatings.includes(option.value)} on:change={() => toggle('contentRatings', option.value)} /><span>{option.label}</span></label>
              {/each}
            </div>
          </details>

          <details class="filter-dropdown">
            <summary><span>Publication demographic</span><b>{selectedSummary(values.publicationDemographics, catalog.publication_demographics, 'Any')}</b></summary>
            <div class="option-list short">
              {#each catalog.publication_demographics as option (option.value)}
                <label><input type="checkbox" checked={values.publicationDemographics.includes(option.value)} on:change={() => toggle('publicationDemographics', option.value)} /><span>{option.label}</span></label>
              {/each}
            </div>
          </details>

          <details class="filter-dropdown">
            <summary><span>Status</span><b>{selectedSummary(values.statuses, catalog.statuses, 'Any')}</b></summary>
            <div class="option-list short">
              {#each catalog.statuses as option (option.value)}
                <label><input type="checkbox" checked={values.statuses.includes(option.value)} on:change={() => toggle('statuses', option.value)} /><span>{option.label}</span></label>
              {/each}
            </div>
          </details>

          <label class="filter-field">
            <span>Tags mode</span>
            <select value={values.tagsMode} on:change={(event) => update({ tagsMode: event.currentTarget.value as 'AND' | 'OR' })}>
              {#each catalog.tag_modes as option (option.value)}<option value={option.value}>{option.label}</option>{/each}
            </select>
          </label>

          {#each TAG_GROUPS as group (group.key)}
            <details class="filter-dropdown">
              <summary><span>{group.label}</span><b>{selectedSummary(groupSelected(group.key), catalog.tag_groups[group.key], 'Any')}</b></summary>
              <div class="option-list">
                {#each catalog.tag_groups[group.key] as tag (tag.id)}
                  <label><input type="checkbox" checked={values.includedTags.includes(tag.id)} on:change={() => toggle('includedTags', tag.id)} /><span>{tag.name}</span></label>
                {/each}
              </div>
            </details>
          {/each}
        </div>

        <div class="sticky bottom-0 -mx-3 -mb-3 mt-3 flex items-center justify-end gap-2 border-t border-[#29293d] bg-[#111119] px-3 py-2">
          {#if hasActive}<button type="button" class="rounded-md px-2 py-1.5 text-[11px] text-gray-400 hover:text-gray-200" on:click={() => dispatch('clear')}>Clear</button>{/if}
          <button type="submit" class="rounded-md bg-purple-600 px-4 py-1.5 text-[11px] font-semibold text-white hover:bg-purple-500">Apply</button>
        </div>
      </form>
    {/if}
  </div>
{/if}

<style>
  .md-filter-popover { width:min(42rem,calc(100vw - 1rem)); max-height:min(42rem,calc(100dvh - 8rem)); transform-origin:left top; animation:md-filter-in 180ms cubic-bezier(.22,1,.36,1); }
  .filter-field { display:grid; gap:.25rem; }
  .filter-field > span, .filter-dropdown summary > span { color:#777788; font-size:.625rem; font-weight:700; letter-spacing:.05em; text-transform:uppercase; }
  .filter-field select { height:2.25rem; width:100%; border:1px solid #2c2c40; border-radius:.5rem; background:#171721; padding:0 .55rem; color:#e5e7eb; font-size:.75rem; }
  .filter-dropdown { position:relative; min-width:0; }
  .filter-dropdown summary { display:flex; height:2.25rem; cursor:pointer; list-style:none; align-items:center; justify-content:space-between; gap:.5rem; border:1px solid #2c2c40; border-radius:.5rem; background:#171721; padding:0 .6rem; }
  .filter-dropdown summary::-webkit-details-marker { display:none; }
  .filter-dropdown summary b { min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:#d1d5db; font-size:.6875rem; font-weight:500; }
  .filter-dropdown[open] summary { border-color:rgba(168,85,247,.65); }
  .option-list { max-height:12rem; overflow-y:auto; border:1px solid #303046; border-top:0; border-radius:0 0 .5rem .5rem; background:#13131d; padding:.35rem; }
  .option-list.short { max-height:9rem; }
  .option-list label { display:flex; cursor:pointer; align-items:center; gap:.5rem; border-radius:.35rem; padding:.35rem .4rem; color:#d1d5db; font-size:.75rem; }
  .option-list label:hover { background:rgba(255,255,255,.04); }
  .option-list input { accent-color:#a855f7; }
  @keyframes md-filter-in { from{opacity:0;transform:translate3d(-.75rem,-.2rem,0) scaleX(.97)} to{opacity:1;transform:none} }
  @media (max-width:639px) { .md-filter-popover { position:fixed; left:.5rem; right:.5rem; top:3.75rem; width:auto; max-height:calc(100dvh - 7.75rem - env(safe-area-inset-bottom)); } }
  @media (prefers-reduced-motion:reduce) { .md-filter-popover{animation-duration:1ms} }
</style>
