<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import AppDrawer from '../../components/AppDrawer.svelte';
  import GridSizeMenu from '../../components/GridSizeMenu.svelte';
  import ActionMenu from '../../components/ui/ActionMenu.svelte';
  import type { ActionMenuItem } from '../../lib/ui';
  import {
    imageSizeByValue,
  } from '../../lib/stores';
  import {
    languageApi,
    type LanguageList,
    type LanguagePracticeStats,
    type LanguageStage,
    type LanguageWord,
    type ManualWordInput,
    type WordsQuery,
  } from '../../lib/languageApi';
  import LanguageAnalyzer from './LanguageAnalyzer.svelte';
  import LanguageBrowser from './LanguageBrowser.svelte';
  import LanguageComposer from './LanguageComposer.svelte';
  import LanguageDetail from './LanguageDetail.svelte';
  import LanguageHangulAtlas from './LanguageHangulAtlas.svelte';
  import LanguageNameDialog from './LanguageNameDialog.svelte';
  import LanguagePractice from './LanguagePractice.svelte';
  import LanguageSyncDialog from './LanguageSyncDialog.svelte';
  import LanguageWordMenu from './LanguageWordMenu.svelte';
  import {
    languageGridSize,
    languageFilterPresets,
    languagePageSize,
    languageStudyProfile,
    type LanguageFilterPreset,
  } from './stores';

  type View = 'words' | 'browser' | 'atlas' | 'analyzer' | 'today' | 'sentences' | 'grammar' | 'decks';

  let view: View = 'words';
  let items: LanguageWord[] = [];
  let total = 0;
  let page = 1;
  let loading = true;
  let appending = false;
  let error = '';
  let query = '';
  let stage = '';
  let source = '';
  let favoritesOnly = false;
  let missingOnly = false;
  let suspendedOnly = false;
  let deckFilter = '';
  let selectedListId = '';
  let sort = 'index';
  let descending = false;
  let lists: LanguageList[] = [];
  let decks: Array<{ deck: string; words: number; missing: number }> = [];
  let practiceStats: LanguagePracticeStats | null = null;
  let showAppMenu = false;
  let showComposer = false;
  let editingWord: LanguageWord | null = null;
  let composerDraft: Partial<ManualWordInput> | null = null;
  let detailWord: LanguageWord | null = null;
  let browserSelectedWord: LanguageWord | null = null;
  let showPractice = false;
  let showSync = false;
  let selectMode = false;
  let selectedIds: string[] = [];
  let bulkListId = '';
  let scrollRoot: HTMLElement;
  let searchTimer: ReturnType<typeof setTimeout> | null = null;
  let nameDialog: 'list' | 'filter' | null = null;
  let nameDialogBusy = false;
  let nameDialogError = '';
  let menuOpen = false;
  let menuX: number | null = null;
  let menuY: number | null = null;
  let menuActions: ActionMenuItem[] = [];

  $: gridMin = Math.min(imageSizeByValue[$languageGridSize].gridMin, 380);
  $: pageCount = $languagePageSize === 'all'
    ? 1
    : Math.max(1, Math.ceil(total / $languagePageSize));
  $: visiblePracticeWords = selectedIds.length
    ? items.filter((word) => selectedIds.includes(word.word_id))
    : items;
  $: activeList = lists.find((list) => list.list_id === selectedListId);
  $: filtersActive = Boolean(stage || source || missingOnly || suspendedOnly || sort !== 'index' || descending);

  function queryPayload(offset = 0): WordsQuery {
    return {
      query,
      stage,
      source,
      favorites: favoritesOnly,
      missing: missingOnly ? true : undefined,
      suspended: suspendedOnly ? true : undefined,
      deck: deckFilter,
      list_id: selectedListId,
      content: view === 'sentences' ? 'sentences' : view === 'grammar' ? 'grammar' : 'all',
      sort,
      descending,
      offset,
      limit: $languagePageSize === 'all' ? 120 : $languagePageSize,
    };
  }

  async function loadWords(reset = true) {
    if (reset) {
      page = 1;
      loading = true;
    }
    error = '';
    try {
      if (view === 'today') {
        const response = await languageApi.today();
        items = response.items;
        total = response.items.length;
      } else {
        const offset = $languagePageSize === 'all'
          ? 0
          : (page - 1) * $languagePageSize;
        const response = await languageApi.words(queryPayload(offset));
        items = response.items;
        total = response.total;
      }
    } catch (cause) {
      error = (cause as Error).message;
      items = [];
      total = 0;
    } finally {
      loading = false;
    }
  }

  async function appendWords() {
    if ($languagePageSize !== 'all' || appending || items.length >= total) return;
    appending = true;
    try {
      const response = await languageApi.words(queryPayload(items.length));
      const existing = new Set(items.map((word) => word.word_id));
      items = [
        ...items,
        ...response.items.filter((word) => !existing.has(word.word_id)),
      ];
      total = response.total;
    } catch (cause) {
      error = (cause as Error).message;
    } finally {
      appending = false;
    }
  }

  async function loadChrome() {
    try {
      const [nextLists, nextDecks, nextPracticeStats] = await Promise.all([
        languageApi.lists(),
        languageApi.decks(),
        languageApi.practiceStats(),
      ]);
      lists = nextLists.items;
      decks = nextDecks.items;
      practiceStats = nextPracticeStats;
      if (!bulkListId && lists[0]) bulkListId = lists[0].list_id;
    } catch (cause) {
      error = (cause as Error).message;
    }
  }

  async function refresh() {
    await Promise.all([loadWords(), loadChrome()]);
  }

  function scheduleSearch() {
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = setTimeout(() => void loadWords(), 220);
  }

  function switchView(next: View) {
    view = next;
    if (next !== 'words') favoritesOnly = false;
    selectedListId = '';
    deckFilter = '';
    selectedIds = [];
    selectMode = false;
    browserSelectedWord = null;
    if (next !== 'analyzer') void loadWords();
  }

  function chooseList(listId: string) {
    view = 'words';
    selectedListId = listId;
    deckFilter = '';
    page = 1;
    selectedIds = [];
    void loadWords();
  }

  function onScroll() {
    if (
      $languagePageSize === 'all'
      && scrollRoot
      && scrollRoot.scrollHeight - scrollRoot.scrollTop - scrollRoot.clientHeight < 900
    ) {
      void appendWords();
    }
  }

  async function goPage(next: number) {
    page = Math.max(1, Math.min(pageCount, next));
    loading = true;
    error = '';
    try {
      const response = await languageApi.words(
        queryPayload((page - 1) * Number($languagePageSize)),
      );
      items = response.items;
      total = response.total;
      scrollRoot?.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (cause) {
      error = (cause as Error).message;
    } finally {
      loading = false;
    }
  }

  function openWord(word: LanguageWord) {
    if (selectMode) {
      toggleSelected(word.word_id);
      return;
    }
    detailWord = word;
  }

  async function playWord(event: MouseEvent, word: LanguageWord) {
    event.stopPropagation();
    if (!word.media_by_role.word_audio) return;
    const audio = new Audio(languageApi.mediaUrl(word.word_id, 'word_audio'));
    try {
      await audio.play();
    } catch {
      error = 'Audio playback needs a click in this browser.';
    }
  }

  async function toggleFavorite(event: MouseEvent, word: LanguageWord) {
    event.stopPropagation();
    try {
      await languageApi.favorite(word.word_id, !word.favorite);
      updateWord({ ...word, favorite: !word.favorite });
    } catch (cause) {
      error = (cause as Error).message;
    }
  }

  function updateWord(word: LanguageWord) {
    items = items.map((value) => value.word_id === word.word_id ? word : value);
    if (detailWord?.word_id === word.word_id) detailWord = word;
  }

  function removeWord(wordId: string) {
    items = items.filter((word) => word.word_id !== wordId);
    total = Math.max(0, total - 1);
    detailWord = null;
    showComposer = false;
    editingWord = null;
  }

  function edit(word: LanguageWord) {
    editingWord = word;
    composerDraft = null;
    showComposer = true;
  }

  function addWord(draft: Partial<ManualWordInput> | null = null) {
    editingWord = null;
    composerDraft = draft;
    showComposer = true;
  }

  function neighboringWord(direction: -1 | 1) {
    if (!detailWord || !items.length) return;
    const index = items.findIndex((word) => word.word_id === detailWord?.word_id);
    const next = items[(index + direction + items.length) % items.length];
    if (next) detailWord = next;
  }

  function toggleSelected(wordId: string) {
    selectedIds = selectedIds.includes(wordId)
      ? selectedIds.filter((value) => value !== wordId)
      : [...selectedIds, wordId];
  }

  async function bulk(action: 'favorite' | 'unfavorite' | 'add_to_list') {
    if (!selectedIds.length) return;
    try {
      await languageApi.bulk(
        selectedIds,
        action,
        action === 'add_to_list' ? bulkListId : undefined,
      );
      if (action === 'favorite' || action === 'unfavorite') {
        const favorite = action === 'favorite';
        items = items.map((word) =>
          selectedIds.includes(word.word_id) ? { ...word, favorite } : word
        );
      }
      if (action === 'add_to_list') await loadChrome();
      selectedIds = [];
      selectMode = false;
    } catch (cause) {
      error = (cause as Error).message;
    }
  }

  async function favoriteFromMenu(word: LanguageWord) {
    try {
      await languageApi.favorite(word.word_id, !word.favorite);
      updateWord({ ...word, favorite: !word.favorite });
    } catch (cause) {
      error = (cause as Error).message;
    }
  }

  async function addToList(word: LanguageWord, listId: string) {
    try {
      await languageApi.setListMembership(listId, [word.word_id], true);
      await loadChrome();
    } catch (cause) {
      error = (cause as Error).message;
    }
  }

  function openWordContextMenu(event: MouseEvent, word: LanguageWord): void {
    event.preventDefault();
    event.stopPropagation();
    menuX = event.clientX;
    menuY = event.clientY;
    menuActions = [
      {
        id: 'details',
        label: 'Open word details',
        icon: '↗',
        run: () => openWord(word),
      },
      {
        id: 'edit',
        label: 'Edit local fields',
        icon: '✎',
        run: () => edit(word),
      },
      {
        id: 'favorite',
        label: word.favorite ? 'Remove from favorites' : 'Add to favorites',
        icon: word.favorite ? '★' : '☆',
        run: () => favoriteFromMenu(word),
      },
      ...lists.map((list, index): ActionMenuItem => ({
        id: `list-${list.list_id}`,
        label: `Add to ${list.name}`,
        icon: '◇',
        separatorBefore: index === 0,
        run: () => addToList(word, list.list_id),
      })),
    ];
    menuOpen = true;
  }

  function changeSort(next: string) {
    if (sort === next) descending = !descending;
    else {
      sort = next;
      descending = false;
    }
    void loadWords();
  }

  async function openWordById(wordId: string) {
    try {
      detailWord = (await languageApi.word(wordId)).word;
    } catch (cause) {
      error = (cause as Error).message;
    }
  }

  function createList() {
    nameDialogError = '';
    nameDialog = 'list';
  }

  function saveFilter() {
    nameDialogError = '';
    nameDialog = 'filter';
  }

  async function submitName(name: string) {
    nameDialogBusy = true;
    nameDialogError = '';
    try {
      if (nameDialog === 'list') {
        const created = await languageApi.createList(name);
        lists = [created.item, ...lists];
        bulkListId = created.item.list_id;
        chooseList(created.item.list_id);
      } else if (nameDialog === 'filter') {
        const preset: LanguageFilterPreset = {
          id: crypto.randomUUID(),
          name,
          stage,
          source,
          missing: missingOnly,
          suspended: suspendedOnly,
          sort,
          descending,
        };
        languageFilterPresets.update((values) => [
          preset,
          ...values.filter((value) => value.name.toLocaleLowerCase() !== name.toLocaleLowerCase()),
        ].slice(0, 30));
      }
      nameDialog = null;
    } catch (cause) {
      nameDialogError = (cause as Error).message;
    } finally {
      nameDialogBusy = false;
    }
  }

  function clearFilters() {
    stage = '';
    source = '';
    missingOnly = false;
    suspendedOnly = false;
    sort = 'index';
    descending = false;
    void loadWords();
  }

  function applyFilterPreset(presetId: string) {
    const preset = $languageFilterPresets.find((value) => value.id === presetId);
    if (!preset) return;
    stage = preset.stage;
    source = preset.source;
    missingOnly = preset.missing;
    suspendedOnly = preset.suspended;
    sort = preset.sort;
    descending = preset.descending;
    void loadWords();
  }

  function stageClass(stage: LanguageStage): string {
    return stage === 'mature'
      ? 'bg-emerald-400'
      : stage === 'young'
        ? 'bg-sky-400'
        : stage === 'learning'
          ? 'bg-amber-400'
          : 'bg-slate-500';
  }

  function meanings(word: LanguageWord): { primary: string; secondary: string; primaryLabel: string; secondaryLabel: string } {
    const english = word.senses.find((sense) => sense.lang === 'en')?.text ?? word.senses[0]?.text ?? '';
    const mongolian = word.senses.find((sense) => sense.lang === 'mn')?.text ?? '';
    const mongolianFirst = $languageStudyProfile.primaryMeaning === 'mn';
    return {
      primary: mongolianFirst ? mongolian : english,
      secondary: mongolianFirst ? english : mongolian,
      primaryLabel: mongolianFirst ? 'MN' : 'EN',
      secondaryLabel: mongolianFirst ? 'EN' : 'MN',
    };
  }

  function pageNumbers(): number[] {
    const start = Math.max(1, page - 2);
    const end = Math.min(pageCount, start + 4);
    return Array.from({ length: end - start + 1 }, (_, index) => start + index);
  }

  function viewTitle(): string {
    if (view === 'words') return activeList?.name ?? (favoritesOnly ? 'Favorites' : 'Every word you learned');
    if (view === 'browser') return 'Library Browser';
    if (view === 'atlas') return 'Hangul Atlas';
    if (view === 'analyzer') return 'Korean Sentence Analyzer';
    if (view === 'today') return 'Due in Anki today';
    if (view === 'sentences') return 'Sentence reading';
    if (view === 'grammar') return 'Grammar notes';
    return 'Mirrored decks';
  }

  $: if ($languagePageSize) {
    page = 1;
  }

  onMount(async () => {
    await refresh();
  });
  onDestroy(() => {
    if (searchTimer) clearTimeout(searchTimer);
  });
</script>

{#if detailWord}
  <LanguageDetail
    word={detailWord}
    on:close={() => detailWord = null}
    on:edit={(event) => edit(event.detail)}
    on:changed={(event) => updateWord(event.detail)}
    on:previous={() => neighboringWord(-1)}
    on:next={() => neighboringWord(1)}
  />
{/if}

{#if showComposer}
  <LanguageComposer
    word={editingWord}
    draft={composerDraft}
    on:close={() => { showComposer = false; editingWord = null; composerDraft = null; }}
    on:saved={(event) => {
      const existed = items.some((word) => word.word_id === event.detail.word_id);
      if (existed) updateWord(event.detail);
      else { items = [event.detail, ...items]; total += 1; }
      detailWord = event.detail;
      showComposer = false;
      editingWord = null;
      composerDraft = null;
      void loadChrome();
    }}
    on:retired={(event) => removeWord(event.detail)}
  />
{/if}

{#if showPractice}
  <LanguagePractice words={visiblePracticeWords} on:close={() => { showPractice = false; void Promise.all([loadWords(false), loadChrome()]); }} />
{/if}

{#if nameDialog}
  <LanguageNameDialog
    title={nameDialog === 'list' ? 'Create a word list' : 'Save this filter set'}
    description={nameDialog === 'list' ? 'Lists stay local and can be filled from any word menu.' : 'Save the current stage, source, status, and sorting choices for quick reuse.'}
    label={nameDialog === 'list' ? 'List name' : 'Filter set name'}
    confirmLabel={nameDialog === 'list' ? 'Create list' : 'Save filter'}
    busy={nameDialogBusy}
    error={nameDialogError}
    on:close={() => nameDialog = null}
    on:submit={(event) => submitName(event.detail)}
  />
{/if}

{#if showSync}
  <LanguageSyncDialog
    on:close={() => showSync = false}
    on:completed={() => { void refresh(); }}
  />
{/if}

<div class="flex h-full min-h-0 flex-col bg-[#0d0c11] text-white">
  <header class="z-20 flex h-14 shrink-0 items-center gap-2 border-b border-[var(--border-default)] bg-[var(--bg-elevated)] px-3 sm:gap-3 sm:px-5">
    <button type="button" class="grid h-10 w-10 shrink-0 place-items-center rounded-full transition-colors hover:bg-[var(--module-accent-hover)]" on:click={() => showAppMenu = true} aria-label="Open Keivotos menu">
      <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" /></svg>
    </button>
    <button type="button" class="flex shrink-0 items-center gap-2" on:click={() => switchView('words')}>
      <img src="/language-logo.svg" alt="" class="h-10 w-10 rounded-xl" />
      <span class="hidden text-lg font-bold text-amber-50 sm:block">Languages</span>
    </button>
    <label class="mx-auto flex h-10 min-w-0 max-w-2xl flex-1 items-center gap-2 rounded-full border border-white/10 bg-black/25 px-4 focus-within:border-amber-300/50">
      <span class="text-white/30">⌕</span>
      <input class="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-white/25" bind:value={query} on:input={scheduleSearch} placeholder="Search words, meanings, tags…" aria-label="Search Languages" />
      {#if query}<button type="button" class="text-white/30 hover:text-white" on:click={() => { query = ''; void loadWords(); }}>✕</button>{/if}
    </label>
    {#if view !== 'browser'}
      <GridSizeMenu value={languageGridSize} />
    {/if}
    <button type="button" class="header-icon" class:text-amber-200={selectMode} on:click={() => { selectMode = !selectMode; selectedIds = []; }} title="Select words" aria-label="Select words">✓</button>
    <button type="button" class="hidden rounded-xl border border-amber-300/20 px-3 py-2 text-xs font-semibold text-amber-100 hover:bg-amber-300/8 sm:block" on:click={() => showSync = true}>Sync Anki</button>
    <button type="button" class="rounded-xl bg-amber-300 px-3 py-2 text-xs font-bold text-[#251a05] hover:bg-amber-200" on:click={() => addWord()}>+ Add word</button>
  </header>

  <div class="flex min-h-0 flex-1">
    <nav class="hidden w-56 shrink-0 overflow-y-auto border-r border-white/8 bg-[#100f14] p-3 sm:block" aria-label="Languages sections">
      <p class="px-3 pb-2 pt-1 text-[10px] font-bold uppercase tracking-[0.18em] text-white/25">Library</p>
      <button type="button" class="language-nav" class:active={view === 'words' && !favoritesOnly && !selectedListId} on:click={() => { favoritesOnly = false; switchView('words'); }}>▦ Words</button>
      <button type="button" class="language-nav" class:active={view === 'browser'} on:click={() => switchView('browser')}>▤ Browser</button>
      <button type="button" class="language-nav" class:active={view === 'atlas'} on:click={() => switchView('atlas')}>✦ Hangul Atlas</button>
      <button type="button" class="language-nav" class:active={view === 'today'} on:click={() => switchView('today')}>◷ Today</button>
      <button type="button" class="language-nav" class:active={view === 'sentences'} on:click={() => switchView('sentences')}>≋ Sentences</button>
      <button type="button" class="language-nav" class:active={view === 'grammar'} on:click={() => switchView('grammar')}>¶ Grammar</button>
      <button type="button" class="language-nav" class:active={view === 'decks'} on:click={() => switchView('decks')}>▤ Decks</button>
      <button type="button" class="language-nav" class:active={favoritesOnly} on:click={() => { favoritesOnly = true; view = 'words'; selectedListId = ''; void loadWords(); }}>★ Favorites</button>
      <div class="mt-5 border-t border-white/8 pt-4">
        <p class="px-3 pb-2 text-[10px] font-bold uppercase tracking-[0.18em] text-white/25">Study</p>
        <button type="button" class="language-nav analyzer-nav" class:active={view === 'analyzer'} on:click={() => switchView('analyzer')}>⌁ Analyzer <span class="ml-auto rounded-full bg-teal-300/8 px-1.5 py-0.5 text-[8px] text-teal-200/55">KIWI</span></button>
        {#if practiceStats}
          <div class="mx-2 mt-2 grid grid-cols-2 gap-1 rounded-xl border border-white/7 bg-black/15 p-2">
            <div><span class="block text-[9px] uppercase tracking-wider text-white/20">Accuracy</span><strong class="text-xs text-emerald-200/75">{practiceStats.totals.accuracy === null ? '—' : `${Math.round(practiceStats.totals.accuracy * 100)}%`}</strong></div>
            <div><span class="block text-[9px] uppercase tracking-wider text-white/20">Streak</span><strong class="text-xs text-amber-200/75">{practiceStats.streak.current_days} day{practiceStats.streak.current_days === 1 ? '' : 's'}</strong></div>
            <div class="col-span-2 mt-1 text-[9px] text-white/25">{practiceStats.totals.answers} answers · {practiceStats.totals.practiced_words} words</div>
          </div>
        {/if}
      </div>
      <div class="mt-5 border-t border-white/8 pt-4">
        <div class="flex items-center justify-between px-3"><p class="text-[10px] font-bold uppercase tracking-[0.18em] text-white/25">Lists</p><button type="button" class="text-lg text-white/25 hover:text-amber-200" on:click={createList}>+</button></div>
        {#each lists as list}<button type="button" class="language-nav mt-1" class:active={selectedListId === list.list_id} on:click={() => chooseList(list.list_id)}>◇ {list.name}<span class="ml-auto text-[10px] text-white/20">{list.word_ids.length}</span></button>{/each}
      </div>
      <div class="mt-5 border-t border-white/8 pt-4">
        <button type="button" class="language-nav text-amber-100/70" on:click={() => showPractice = true}>▶ Practice visible</button>
      </div>
    </nav>

    <main class="flex min-w-0 flex-1 flex-col pb-16 sm:pb-0">
      <div class="flex shrink-0 flex-wrap items-center gap-2 border-b border-white/7 bg-[#111016] px-3 py-2 sm:px-5">
        {#if view === 'analyzer'}
          <span class="rounded-full border border-teal-300/15 bg-teal-300/6 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-teal-100/55">Local engine · explicit dictionary only</span>
          <span class="flex-1"></span>
          <button type="button" class="filter-chip" on:click={() => switchView('words')}>Cards</button>
          <button type="button" class="filter-chip" on:click={() => switchView('browser')}>Browser</button>
          <button type="button" class="filter-chip" on:click={() => switchView('atlas')}>Atlas</button>
        {:else}
        {#each [
          ['', 'All stages'],
          ['new', 'New'],
          ['learning', 'Learning'],
          ['young', 'Young'],
          ['mature', 'Mature'],
        ] as value}<button type="button" class="filter-chip" class:active={stage === value[0]} on:click={() => { stage = value[0]; void loadWords(); }}>{value[1]}</button>{/each}
        <span class="mx-1 h-5 w-px bg-white/8"></span>
        <button type="button" class="filter-chip" class:active={missingOnly} on:click={() => { missingOnly = !missingOnly; void loadWords(); }}>Missing</button>
        <button type="button" class="filter-chip" class:active={suspendedOnly} on:click={() => { suspendedOnly = !suspendedOnly; void loadWords(); }}>Suspended</button>
        <select class="filter-select" bind:value={source} on:change={() => loadWords()} aria-label="Source filter"><option value="">All sources</option><option value="anki">Anki</option><option value="manual">Manual</option></select>
        <select class="filter-select" bind:value={sort} on:change={() => loadWords()} aria-label="Sort words"><option value="index">Deck order</option><option value="korean">Korean A–Z</option><option value="english">English A–Z</option><option value="mongolian">Mongolian A–Z</option><option value="interval">Mastery</option><option value="updated">Updated</option><option value="deck">Deck</option></select>
        <button type="button" class="filter-chip" on:click={() => { descending = !descending; void loadWords(); }} title="Reverse order">{descending ? '↓' : '↑'}</button>
        {#if $languageFilterPresets.length}
          <select class="filter-select max-w-36" value="" on:change={(event) => { applyFilterPreset(event.currentTarget.value); event.currentTarget.value = ''; }} aria-label="Apply saved filter set">
            <option value="">Saved filters</option>
            {#each $languageFilterPresets as preset}<option value={preset.id}>{preset.name}</option>{/each}
          </select>
        {/if}
        <button type="button" class="filter-chip" on:click={saveFilter}>Save filter</button>
        {#if filtersActive}<button type="button" class="filter-chip text-amber-100" on:click={clearFilters}>Clear all</button>{/if}
        <span class="flex-1"></span>
        <div class="view-shortcuts sm:hidden">
          <button type="button" class="filter-chip" class:active={view === 'words'} on:click={() => switchView('words')}>Cards</button>
          <button type="button" class="filter-chip" class:active={view === 'browser'} on:click={() => switchView('browser')}>Browser</button>
          <button type="button" class="filter-chip" class:active={view === 'atlas'} on:click={() => switchView('atlas')}>Atlas</button>
          <button type="button" class="filter-chip" on:click={() => switchView('analyzer')}>Analyzer</button>
        </div>
        <select class="filter-select" value={$languagePageSize} on:change={(event) => { languagePageSize.set(event.currentTarget.value === 'all' ? 'all' : Number(event.currentTarget.value) as 30|60|120); void loadWords(); }} aria-label="Words per page"><option value="30">30</option><option value="60">60</option><option value="120">120</option><option value="all">All</option></select>
        {/if}
      </div>

      <div class="min-h-0 flex-1 overflow-y-auto" bind:this={scrollRoot} on:scroll={onScroll}>
        <div class="mx-auto max-w-[1800px] p-4 sm:p-6">
          <div class="mb-5 flex flex-wrap items-end justify-between gap-3">
            <div>
              <p class="text-[10px] font-semibold uppercase tracking-[0.22em] text-amber-300/55">{view === 'analyzer' ? 'Offline morphology workbench' : selectedListId ? 'Word list' : 'Local study library'}</p>
              <h1 class="mt-1 text-2xl font-bold">
                {viewTitle()}
              </h1>
              {#if !['analyzer', 'decks'].includes(view)}
                <div class="mt-2 flex flex-wrap items-center gap-3 text-[10px] text-white/35" aria-label="Mastery legend">
                  <span class="font-semibold uppercase tracking-wider text-white/25">Mastery</span>
                  <span><i class="legend-dot bg-slate-500"></i>New</span>
                  <span><i class="legend-dot bg-amber-400"></i>Learning</span>
                  <span><i class="legend-dot bg-sky-400"></i>Young</span>
                  <span><i class="legend-dot bg-emerald-400"></i>Mature</span>
                </div>
              {/if}
            </div>
            {#if view === 'today' && items.length}
              <button type="button" class="rounded-xl bg-amber-300 px-4 py-2 text-xs font-bold text-[#251a05]" on:click={() => showPractice = true}>Practice {items.length} due word{items.length === 1 ? '' : 's'}</button>
            {:else if view !== 'analyzer'}
              <span class="text-sm text-white/30">{total.toLocaleString()} item{total === 1 ? '' : 's'}</span>
            {/if}
          </div>

          {#if error}<div class="mb-5 rounded-2xl border border-red-400/20 bg-red-400/8 p-4 text-sm text-red-200">{error}</div>{/if}

          {#if loading}
            <div class="grid gap-4" style={`grid-template-columns:repeat(auto-fill,minmax(${gridMin}px,1fr))`}>{#each Array(12) as _}<div class="h-52 animate-pulse rounded-2xl bg-white/5"></div>{/each}</div>
          {:else if view === 'analyzer'}
            <LanguageAnalyzer
              on:openword={(event) => openWordById(event.detail)}
              on:addword={(event) => addWord(event.detail)}
            />
          {:else if view === 'decks'}
            {#if decks.length}
              <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {#each decks as deck}<button type="button" class="rounded-2xl border border-white/8 bg-[#121119] p-5 text-left hover:border-amber-300/25" on:click={() => { view = 'words'; query = ''; selectedListId = ''; deckFilter = deck.deck; void loadWords(); }}><p class="text-sm font-semibold text-white/75">{deck.deck || 'Keivotos'}</p><div class="mt-4 flex gap-4 text-xs text-white/30"><span>{deck.words} words</span>{#if deck.missing}<span class="text-red-200/60">{deck.missing} missing</span>{/if}</div></button>{/each}
              </div>
            {:else}
              <div class="empty-study-state"><strong>No mirrored decks yet</strong><span>Run an explicit read-only Anki preview when AnkiConnect is available, or keep using manual words.</span></div>
            {/if}
          {:else if view === 'sentences'}
            {#if items.length}
              <div class="mx-auto max-w-4xl space-y-3">
              {#each items as word}
                <button type="button" class="w-full rounded-2xl border border-white/8 bg-[#121119] p-5 text-left hover:border-amber-300/20" on:click={() => openWord(word)}>
                  <p class="text-lg leading-8 text-white/75">{word.examples[0].sentence}</p>
                  <div class="mt-3 flex items-center justify-between text-xs"><span class="font-semibold text-amber-200/65">{word.headword}</span><span class="text-white/25">{word.examples[0].translations.map((value) => value.text).join(' · ')}</span></div>
                </button>
              {/each}
              </div>
            {:else}
              <div class="empty-study-state"><strong>No example sentences match</strong><span>Clear the filters or add an example sentence while editing a word.</span><button type="button" on:click={clearFilters}>Clear filters</button></div>
            {/if}
          {:else if view === 'grammar'}
            {#if items.length}
              <div class="mx-auto max-w-4xl space-y-4">
              {#each items as word}
                <article class="rounded-2xl border border-amber-300/12 bg-amber-300/4 p-6">
                  <button type="button" class="text-2xl font-bold text-amber-100 hover:text-amber-200" on:click={() => openWord(word)}>{word.headword}</button>
                  {#each word.notes_text.filter((note) => note.kind === 'grammar') as note}<p class="mt-4 whitespace-pre-wrap text-sm leading-7 text-white/55">{note.body}</p>{/each}
                </article>
              {/each}
              </div>
            {:else}
              <div class="empty-study-state"><strong>No grammar notes match</strong><span>Clear the filters or add a grammar note while editing a word.</span><button type="button" on:click={clearFilters}>Clear filters</button></div>
            {/if}
          {:else if items.length && view === 'browser'}
            <LanguageBrowser
              {items}
              {lists}
              selectedWord={browserSelectedWord}
              {sort}
              {descending}
              offset={$languagePageSize === 'all' ? 0 : (page - 1) * Number($languagePageSize)}
              on:select={(event) => browserSelectedWord = event.detail}
              on:closeinspector={() => browserSelectedWord = null}
              on:details={(event) => openWord(event.detail)}
              on:edit={(event) => edit(event.detail)}
              on:favorite={(event) => favoriteFromMenu(event.detail)}
              on:addtolist={(event) => addToList(event.detail.word, event.detail.listId)}
              on:sort={(event) => changeSort(event.detail)}
            />
          {:else if items.length && view === 'atlas'}
            <LanguageHangulAtlas
              {items}
              {lists}
              on:details={(event) => openWord(event.detail)}
              on:edit={(event) => edit(event.detail)}
              on:favorite={(event) => favoriteFromMenu(event.detail)}
              on:addtolist={(event) => addToList(event.detail.word, event.detail.listId)}
            />
          {:else if items.length}
            <div class="grid gap-4" style={`grid-template-columns:repeat(auto-fill,minmax(${gridMin}px,1fr))`}>
              {#each items as word, cardIndex (word.word_id)}
                <article
                  class="language-card group relative flex min-h-52 overflow-hidden rounded-2xl border bg-[#14131a] p-5 text-left {selectedIds.includes(word.word_id) ? 'border-amber-300/55 ring-1 ring-amber-300/20' : 'border-white/8 hover:border-amber-300/28'} {word.notes_text.some((note) => note.kind === 'grammar') ? 'grammar-card' : ''}"
                  style={`animation-delay:${Math.min(cardIndex, 14) * 22}ms`}
                  on:contextmenu={(event) => openWordContextMenu(event, word)}
                >
                  {#if word.media_by_role.image}<img class="absolute inset-0 h-full w-full object-cover opacity-[.13] transition-opacity group-hover:opacity-[.2]" src={languageApi.mediaUrl(word.word_id, 'image')} alt="" loading="lazy" /><div class="absolute inset-0 bg-gradient-to-t from-[#14131a] via-[#14131a]/80 to-[#14131a]/25"></div>{/if}
                  <div class="relative flex min-w-0 flex-1 flex-col">
                    <div class="flex min-h-6 items-start justify-between gap-2">
                      <div class="flex flex-wrap gap-1">{#if word.missing}<span class="card-flag text-red-200">Missing</span>{/if}{#if word.suspended}<span class="card-flag">Suspended</span>{/if}{#if word.edited}<span class="card-flag text-sky-200">Edited</span>{/if}{#if word.possible_duplicate}<span class="card-flag text-amber-200">Duplicate?</span>{/if}</div>
                      <div class="flex items-center gap-1">
                        {#if selectMode}<span class="grid h-5 w-5 place-items-center rounded border border-white/20 text-xs {selectedIds.includes(word.word_id) ? 'bg-amber-300 text-[#251a05]' : ''}">{selectedIds.includes(word.word_id) ? '✓' : ''}</span>{/if}
                        {#if word.media_by_role.word_audio}<button type="button" class="card-action" aria-label={`Play ${word.headword}`} on:click={(event) => playWord(event, word)}>♪</button>{/if}
                        <button type="button" aria-label={word.favorite ? `Unfavorite ${word.headword}` : `Favorite ${word.headword}`} class="card-action {word.favorite ? 'text-amber-300 opacity-100' : ''}" on:click={(event) => toggleFavorite(event, word)}>{word.favorite ? '★' : '☆'}</button>
                        <LanguageWordMenu
                          {word}
                          {lists}
                          on:edit={(event) => edit(event.detail)}
                          on:details={(event) => openWord(event.detail)}
                          on:favorite={(event) => favoriteFromMenu(event.detail)}
                          on:addtolist={(event) => addToList(event.detail.word, event.detail.listId)}
                        />
                      </div>
                    </div>
                    <button type="button" class="mt-auto block w-full pt-7 text-left" on:click={() => openWord(word)}>
                      <h2 class="truncate text-3xl font-black tracking-tight text-white">{word.headword}</h2>
                      {#if word.sentence_form !== word.headword}<p class="mt-1 truncate text-sm text-amber-100/45">{word.sentence_form}</p>{/if}
                      <p class="mt-4 line-clamp-2 text-sm font-medium leading-5 text-amber-50/80"><span class="mr-1 text-[9px] text-white/25">{meanings(word).primaryLabel}</span>{meanings(word).primary || 'No primary meaning mapped'}</p>
                      {#if $languageStudyProfile.showSecondaryMeaning}<p class="mt-1 line-clamp-2 text-xs leading-5 text-sky-100/45"><span class="mr-1 text-[9px] text-white/20">{meanings(word).secondaryLabel}</span>{meanings(word).secondary}</p>{/if}
                    </button>
                    <div class="mt-5 flex items-center gap-2">
                      <div class="h-1 flex-1 overflow-hidden rounded-full bg-white/8"><div class="h-full rounded-full transition-all {stageClass(word.stage)}" style={`width:${Math.max(5, Math.min(100, word.weakest_interval / 21 * 100))}%`}></div></div>
                      <span class="text-[10px] font-semibold capitalize tracking-wide text-white/55">{word.stage}</span>
                      {#if word.practice.answers}<span class="rounded-full bg-white/5 px-1.5 py-0.5 text-[9px] text-emerald-100/55">{Math.round((word.practice.accuracy ?? 0) * 100)}% · {word.practice.answers}</span>{/if}
                    </div>
                  </div>
                </article>
              {/each}
            </div>
            {#if appending}<p class="py-8 text-center text-xs text-white/25">Loading more words…</p>{/if}
          {:else}
            <div class="mx-auto flex min-h-[55vh] max-w-lg flex-col items-center justify-center text-center">
              <img src="/language-logo.svg" alt="" class="h-20 w-20 opacity-80" />
              <h2 class="mt-5 text-2xl font-bold">{query || stage || favoritesOnly || selectedListId ? 'No words match this view' : 'Show every word you learned'}</h2>
              <p class="mt-3 text-sm leading-6 text-white/35">{view === 'today' ? 'Today is a cached Anki snapshot from your last explicit mirror.' : 'Mirror your KO1K deck read-only, or start with a word of your own.'}</p>
              <div class="mt-6 flex gap-3"><button type="button" class="rounded-xl border border-amber-300/25 px-4 py-2.5 text-sm text-amber-100 hover:bg-amber-300/8" on:click={() => showSync = true}>Connect to Anki</button><button type="button" class="rounded-xl bg-amber-300 px-4 py-2.5 text-sm font-bold text-[#251a05]" on:click={() => addWord()}>Add a word</button></div>
            </div>
          {/if}

          {#if $languagePageSize !== 'all' && pageCount > 1 && ['words', 'browser', 'atlas', 'sentences', 'grammar'].includes(view)}
            <nav class="mt-8 flex items-center justify-center gap-1" aria-label="Languages pages">
              <button type="button" class="page-button" on:click={() => goPage(page - 1)} disabled={page === 1}>←</button>
              {#each pageNumbers() as value}<button type="button" class="page-button" class:active={page === value} on:click={() => goPage(value)}>{value}</button>{/each}
              <button type="button" class="page-button" on:click={() => goPage(page + 1)} disabled={page === pageCount}>→</button>
            </nav>
          {/if}
        </div>
      </div>
    </main>
  </div>

  <nav class="fixed inset-x-0 bottom-0 z-40 grid h-16 grid-cols-4 border-t border-white/8 bg-[#100f14]/98 px-2 backdrop-blur sm:hidden" aria-label="Languages sections">
    <button type="button" class="text-xs font-semibold {view === 'words' ? 'text-amber-200' : 'text-white/35'}" on:click={() => switchView('words')}><span class="block text-lg">▦</span>Words</button>
    <button type="button" class="text-xs font-semibold {view === 'today' ? 'text-amber-200' : 'text-white/35'}" on:click={() => switchView('today')}><span class="block text-lg">◷</span>Today</button>
    <button type="button" class="text-xs font-semibold {view === 'analyzer' ? 'text-teal-200' : 'text-white/35'}" on:click={() => switchView('analyzer')}><span class="block text-lg">⌁</span>Analyzer</button>
    <button type="button" class="text-xs font-semibold {view === 'browser' ? 'text-amber-200' : 'text-white/35'}" on:click={() => switchView('browser')}><span class="block text-lg">▤</span>Browser</button>
  </nav>

  {#if selectMode}
    <div class="absolute bottom-20 left-1/2 z-40 flex max-w-[calc(100vw-2rem)] -translate-x-1/2 items-center gap-2 rounded-2xl border border-amber-300/20 bg-[#17151c]/95 p-2 shadow-2xl backdrop-blur sm:bottom-5">
      <span class="px-2 text-xs font-semibold text-amber-100">{selectedIds.length} selected</span>
      <button type="button" class="bulk-button" on:click={() => bulk('favorite')} disabled={!selectedIds.length}>Favorite</button>
      {#if lists.length}<select class="bulk-button max-w-36" bind:value={bulkListId}>{#each lists as list}<option value={list.list_id}>{list.name}</option>{/each}</select><button type="button" class="bulk-button" on:click={() => bulk('add_to_list')} disabled={!selectedIds.length || !bulkListId}>Add to list</button>{/if}
      <button type="button" class="bulk-button text-amber-100" on:click={() => showPractice = true} disabled={!selectedIds.length}>Practise</button>
      <button type="button" class="bulk-button" on:click={() => { selectedIds = []; selectMode = false; }}>✕</button>
    </div>
  {/if}
</div>

{#if showAppMenu}<AppDrawer on:close={() => showAppMenu = false} />{/if}

<ActionMenu
  open={menuOpen}
  x={menuX}
  y={menuY}
  items={menuActions}
  label="Word actions"
  on:close={() => menuOpen = false}
/>

<style>
  .header-icon { display:grid; height:2.5rem; width:2.5rem; place-items:center; border-radius:999px; color:rgba(255,255,255,.55); }
  .header-icon:hover { background:rgba(255,255,255,.07); color:white; }
  .language-nav { display:flex; width:100%; align-items:center; gap:.6rem; border-radius:.7rem; padding:.55rem .75rem; text-align:left; font-size:.78rem; color:rgba(255,255,255,.42); }
  .language-nav:hover,.language-nav.active { background:rgba(245,158,11,.09); color:rgb(254 243 199); }
  .filter-chip,.filter-select { border:1px solid rgba(255,255,255,.08); border-radius:999px; background:rgba(0,0,0,.16); padding:.35rem .65rem; color:rgba(255,255,255,.4); font-size:.65rem; outline:none; }
  .filter-chip:hover,.filter-chip.active { border-color:rgba(251,191,36,.25); background:rgba(245,158,11,.08); color:rgb(254 243 199); }
  .language-card { animation:language-card-in 260ms both; transition:transform 160ms,border-color 160ms,box-shadow 160ms; }
  .language-card:hover { transform:translateY(-3px); box-shadow:0 16px 34px rgba(0,0,0,.24); }
  .grammar-card { background:linear-gradient(145deg,rgba(120,75,10,.15),#14131a 62%); }
  .card-flag { border:1px solid rgba(255,255,255,.08); border-radius:999px; background:rgba(0,0,0,.3); padding:.2rem .45rem; font-size:.55rem; font-weight:700; text-transform:uppercase; letter-spacing:.05em; color:rgba(255,255,255,.42); }
  .card-action { display:grid; height:1.8rem; width:1.8rem; place-items:center; border-radius:999px; color:rgba(255,255,255,.4); opacity:.72; transition:opacity 150ms,background 150ms,color 150ms; }
  .group:hover .card-action,.card-action:focus { opacity:1; }
  .card-action:hover { background:rgba(255,255,255,.08); color:white; }
  .page-button,.bulk-button { border:1px solid rgba(255,255,255,.09); border-radius:.65rem; padding:.5rem .7rem; color:rgba(255,255,255,.5); font-size:.7rem; }
  .page-button:hover,.page-button.active,.bulk-button:hover { border-color:rgba(251,191,36,.3); color:rgb(254 243 199); }
  .page-button:disabled,.bulk-button:disabled { opacity:.3; }
  .legend-dot { display:inline-block; height:.45rem; width:.45rem; margin-right:.28rem; border-radius:999px; vertical-align:middle; }
  .empty-study-state { display:flex; min-height:20rem; max-width:34rem; margin:0 auto; flex-direction:column; align-items:center; justify-content:center; text-align:center; }
  .empty-study-state strong { color:rgba(255,255,255,.82); font-size:1.2rem; }
  .empty-study-state span { margin-top:.6rem; color:rgba(255,255,255,.35); font-size:.78rem; line-height:1.7; }
  .empty-study-state button { margin-top:1rem; border:1px solid rgba(251,191,36,.25); border-radius:.7rem; padding:.55rem .85rem; color:rgb(254 243 199); font-size:.75rem; }
  @keyframes language-card-in { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
</style>
