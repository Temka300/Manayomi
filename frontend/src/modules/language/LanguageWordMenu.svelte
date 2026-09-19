<script lang="ts">
  import { createEventDispatcher, onDestroy, onMount } from 'svelte';
  import type { LanguageList, LanguageWord } from '../../lib/languageApi';

  export let word: LanguageWord;
  export let lists: LanguageList[] = [];
  export let compact = false;

  const dispatch = createEventDispatcher<{
    edit: LanguageWord;
    details: LanguageWord;
    favorite: LanguageWord;
    addtolist: { word: LanguageWord; listId: string };
  }>();

  let root: HTMLDivElement;
  let open = false;
  let showLists = false;

  function choose(action: 'edit' | 'details' | 'favorite') {
    dispatch(action, word);
    open = false;
    showLists = false;
  }

  function addToList(listId: string) {
    dispatch('addtolist', { word, listId });
    open = false;
    showLists = false;
  }

  function closeFromOutside(event: MouseEvent) {
    if (open && root && !root.contains(event.target as Node)) {
      open = false;
      showLists = false;
    }
  }

  function onKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape' && open) {
      event.stopPropagation();
      open = false;
      showLists = false;
    }
  }

  function containMenuKeydown(event: KeyboardEvent) {
    event.stopPropagation();
    if (event.key === 'Escape' && open) {
      open = false;
      showLists = false;
    }
  }

  onMount(() => {
    document.addEventListener('click', closeFromOutside);
    document.addEventListener('keydown', onKeydown);
  });
  onDestroy(() => {
    document.removeEventListener('click', closeFromOutside);
    document.removeEventListener('keydown', onKeydown);
  });
</script>

<div class="word-menu relative" bind:this={root}>
  <button
    type="button"
    class:compact
    class="menu-trigger"
    aria-label={`More actions for ${word.headword}`}
    aria-haspopup="menu"
    aria-expanded={open}
    title="More actions"
    on:click|stopPropagation={() => { open = !open; showLists = false; }}
    on:keydown={containMenuKeydown}
  >•••</button>

  {#if open}
    <div class="menu-panel" role="menu">
      <button type="button" role="menuitem" on:click|stopPropagation={() => choose('edit')} on:keydown={containMenuKeydown}>
        <span>✎</span><span><strong>Edit word</strong><small>Local override</small></span>
      </button>
      <button type="button" role="menuitem" on:click|stopPropagation={() => choose('details')} on:keydown={containMenuKeydown}>
        <span>↗</span><span><strong>Open details</strong><small>Audio, notes and progress</small></span>
      </button>
      <button type="button" role="menuitem" on:click|stopPropagation={() => choose('favorite')} on:keydown={containMenuKeydown}>
        <span>{word.favorite ? '★' : '☆'}</span><span><strong>{word.favorite ? 'Unfavorite' : 'Favorite'}</strong><small>Keep in your library filter</small></span>
      </button>
      {#if lists.length}
        <button type="button" role="menuitem" on:click|stopPropagation={() => showLists = !showLists} on:keydown={containMenuKeydown}>
          <span>＋</span><span><strong>Add to list</strong><small>{lists.length} available</small></span><span class="chevron">{showLists ? '⌃' : '⌄'}</span>
        </button>
        {#if showLists}
          <div class="list-choices">
            {#each lists as list}
              <button type="button" role="menuitem" on:click|stopPropagation={() => addToList(list.list_id)} on:keydown={containMenuKeydown}>
                <span>◇</span><span class="truncate">{list.name}</span>
              </button>
            {/each}
          </div>
        {/if}
      {/if}
    </div>
  {/if}
</div>

<style>
  .menu-trigger {
    display:grid;
    height:1.85rem;
    min-width:1.85rem;
    place-items:center;
    border-radius:999px;
    color:rgba(255,255,255,.46);
    font-size:.68rem;
    font-weight:800;
    letter-spacing:.02em;
    opacity:.72;
    transition:opacity 150ms,background 150ms,color 150ms;
  }
  :global(.group:hover) .menu-trigger,.menu-trigger:focus-visible,.menu-trigger[aria-expanded="true"],.menu-trigger.compact { opacity:1; }
  .menu-trigger:hover,.menu-trigger[aria-expanded="true"] { background:rgba(255,255,255,.08); color:white; }
  .menu-panel {
    position:absolute;
    z-index:70;
    right:0;
    top:calc(100% + .4rem);
    width:15rem;
    overflow:hidden;
    border:1px solid rgba(255,255,255,.11);
    border-radius:.9rem;
    background:rgba(22,20,28,.98);
    padding:.35rem;
    box-shadow:0 22px 60px rgba(0,0,0,.48);
    backdrop-filter:blur(18px);
    animation:menu-in 120ms ease-out both;
  }
  .menu-panel>button,.list-choices button {
    display:grid;
    width:100%;
    grid-template-columns:1.3rem minmax(0,1fr) auto;
    align-items:center;
    gap:.55rem;
    border-radius:.65rem;
    padding:.55rem .6rem;
    text-align:left;
    color:rgba(255,255,255,.68);
  }
  .menu-panel>button:hover,.list-choices button:hover { background:rgba(251,191,36,.08); color:rgb(254 243 199); }
  strong { display:block; font-size:.7rem; font-weight:700; }
  small { display:block; margin-top:.08rem; font-size:.58rem; color:rgba(255,255,255,.28); }
  .chevron { color:rgba(255,255,255,.25); }
  .list-choices { max-height:10rem; overflow-y:auto; border-top:1px solid rgba(255,255,255,.07); padding:.3rem 0 0 1rem; }
  .list-choices button { grid-template-columns:1rem minmax(0,1fr); font-size:.66rem; }
  @keyframes menu-in { from { opacity:0; transform:translateY(-4px) scale(.98); } to { opacity:1; transform:translateY(0) scale(1); } }
  :global(html[data-motion='reduced']) .menu-panel { animation:none; }
</style>
