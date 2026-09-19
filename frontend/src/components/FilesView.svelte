<script lang="ts">
  import { onMount } from 'svelte';
  import { filesApi, type DuplicateGroup, type FileNode, type SourceInfo } from '../lib/filesApi';
  import { fileGlyph, hasThumbnail, previewMode, roleMediaExtensions, type Subject } from '../lib/filePreview';
  import GridSizeMenu from './GridSizeMenu.svelte';
  import { filesGridSize, filesNavigationRequest, imageSizeByValue, thumbnailTierFor } from '../lib/stores';
  import { SUITE_NAME } from '../lib/product';
  import { suiteModules } from '../lib/stores';
  import {
    displayNameForPath,
    normalizedPath,
    suiteApi,
    type FolderBatchResult,
  } from '../lib/suiteApi';
  import { moduleUi } from '../modules/registry';
  import AppDrawer from './AppDrawer.svelte';
  import FileInfoPanel from './FileInfoPanel.svelte';
  import ManageFoldersDialog from './ManageFoldersDialog.svelte';
  import ActionMenu from './ui/ActionMenu.svelte';
  import { showToast, type ActionMenuItem } from '../lib/ui';

  let sources: SourceInfo[] = [];
  let selectedSourceId: string | null = null;
  let currentParent = '';
  let entries: FileNode[] = [];
  let searchQuery = '';
  let searchResults: FileNode[] | null = null;
  let showManager = false;
  let addingFolder = false;
  let loading = false;
  let busy = false;
  let error = '';
  let showAppMenu = false;
  let duplicateGroups: DuplicateGroup[] | null = null;
  let dedupBusy = false;
  let selectedEntry: FileNode | null = null;
  let annotatedPaths = new Set<string>();
  let infoPanelOpen = false;
  let menuOpen = false;
  let menuX: number | null = null;
  let menuY: number | null = null;
  let menuActions: ActionMenuItem[] = [];
  let renamingEntry: FileNode | null = null;
  let renameValue = '';
  let renameInput: HTMLInputElement | null = null;
  let viewingEntry: FileNode | null = null;
  let mediaFilter: 'media' | 'all' = 'all';

  $: selectedSource = sources.find((s) => s.source_id === selectedSourceId) ?? null;
  $: sidebarSources = sources.filter((source) => source.visible);
  $: selectedRole = selectedSource?.role === 'base' ? 'files' : selectedSource?.role ?? 'files';
  $: roleExtensions = roleMediaExtensions(selectedRole);
  $: hasRoleFilter = roleExtensions !== null;
  $: breadcrumbSources = selectedSource
    ? sources
      .filter((source) => isSameOrAncestorPath(source.path, selectedSource?.path ?? ''))
      .sort((left, right) => pathDepth(left.path) - pathDepth(right.path))
    : [];
  $: crumbs = currentParent === '' ? [] : currentParent.split('/');
  $: filteredEntries = (searchResults ?? entries).filter((entry) => {
    if (mediaFilter !== 'media' || !roleExtensions) return true;
    if (entry.is_dir) return true;
    return roleExtensions.has((entry.ext ?? '').toLowerCase());
  });
  $: displayed = filteredEntries;
  $: subject = buildSubject(selectedEntry, selectedSource, currentParent, sources);
  $: selectedKey = selectedEntry ? selectedEntry.source_id + '/' + selectedEntry.relative_path : null;
  $: viewerMode = viewingEntry ? previewMode(viewingEntry.ext) : 'none';
  $: viewerFileHref = viewingEntry ? filesApi.fileUrl(viewingEntry.source_id, viewingEntry.relative_path) : '';

  let pendingNavigation: { sourceId: string; relativePath: string; reveal: boolean } | null = null;

  onMount(() => {
    const unsubscribe = filesNavigationRequest.subscribe((request) => {
      if (!request) return;
      pendingNavigation = request;
      if (sources.length) void applyPendingNavigation();
    });
    void loadSources().then(applyPendingNavigation);
    return unsubscribe;
  });

  function showInfoPanel(): void {
    infoPanelOpen = true;
  }

  function absolutePathFor(sourcePath: string, relativePath: string): string {
    return normalizedPath(relativePath ? `${sourcePath}/${relativePath}` : sourcePath);
  }

  function buildSubject(
    entry: FileNode | null,
    source: SourceInfo | null,
    parent: string,
    allSources: SourceInfo[],
  ): Subject | null {
    if (entry) {
      const owner = allSources.find((s) => s.source_id === entry.source_id) ?? source;
      const base = owner?.path ?? source?.path ?? '';
      return {
        sourceId: entry.source_id,
        path: entry.relative_path,
        name: entry.name,
        isDir: entry.is_dir,
        ext: entry.ext,
        size: entry.size,
        mtime: entry.mtime,
        absolutePath: absolutePathFor(base, entry.relative_path),
      };
    }
    if (!source) return null;
    const folderName = parent === '' ? source.display_name : parent.split('/').pop() ?? source.display_name;
    return {
      sourceId: source.source_id,
      path: parent,
      name: folderName,
      isDir: true,
      ext: null,
      size: null,
      mtime: null,
      absolutePath: absolutePathFor(source.path, parent),
    };
  }

  async function loadAnnotatedPaths() {
    if (!selectedSourceId) {
      annotatedPaths = new Set();
      return;
    }
    try {
      annotatedPaths = new Set(await filesApi.listAnnotated(selectedSourceId));
      annotationRevision += 1;
      // A tile that 404'd before could have just been given an attachment, so
      // let every failure retry once the origin data has changed.
      thumbFailed = new Set();
    } catch {
      // Badges are non-essential; a failure just leaves them off.
    }
  }

  function selectEntry(entry: FileNode): void {
    if (selectedEntry?.source_id === entry.source_id &&
        selectedEntry?.relative_path === entry.relative_path) return;
    selectedEntry = entry;
  }

  async function loadSources() {
    error = '';
    try {
      const loadedSources = await filesApi.listSources();
      sources = loadedSources;
      const firstVisible = loadedSources.find((source) => source.visible);
      if (firstVisible && !selectedSourceId) {
        await selectSource(firstVisible.source_id);
      }
    } catch (e) {
      error = (e as Error).message;
    }
  }

  async function applyPendingNavigation(): Promise<void> {
    const request = pendingNavigation;
    if (!request || !sources.some((source) => source.source_id === request.sourceId)) return;
    pendingNavigation = null;
    filesNavigationRequest.set(null);
    const normalized = request.relativePath.replace(/\\/g, '/').replace(/^\/+/, '');
    const parent = normalized.includes('/') ? normalized.slice(0, normalized.lastIndexOf('/')) : '';
    await selectSource(request.sourceId, parent);
    if (request.reveal) {
      const entry = entries.find((value) =>
        value.source_id === request.sourceId && value.relative_path === normalized
      );
      if (entry) selectEntry(entry);
    }
  }

  async function selectSource(sourceId: string, parent = '') {
    selectedSourceId = sourceId;
    currentParent = parent;
    selectedEntry = null;
    clearSearch();
    duplicateGroups = null;
    const source = sources.find((s) => s.source_id === sourceId);
    const role = source?.role === 'base' ? 'files' : source?.role ?? 'files';
    mediaFilter = roleMediaExtensions(role) ? 'media' : 'all';
    await loadEntries();
  }

  async function loadEntries() {
    if (!selectedSourceId) {
      entries = [];
      return;
    }
    loading = true;
    error = '';
    try {
      entries = await filesApi.browse(selectedSourceId, currentParent);
    } catch (e) {
      error = (e as Error).message;
      entries = [];
    } finally {
      loading = false;
    }
    void loadAnnotatedPaths();
  }

  async function navigate(parent: string) {
    currentParent = parent;
    selectedEntry = null;
    clearSearch();
    duplicateGroups = null;
    await loadEntries();
  }

  async function showDuplicates() {
    if (dedupBusy) return;
    dedupBusy = true;
    error = '';
    try {
      // Lazily hash size-colliding files in bounded batches until caught up.
      for (let round = 0; round < 50; round += 1) {
        const progress = await filesApi.computeHashes();
        if (progress.remaining === 0) break;
      }
      duplicateGroups = await filesApi.listDuplicates();
      selectedEntry = null;
      clearSearch();
    } catch (e) {
      error = (e as Error).message;
    } finally {
      dedupBusy = false;
    }
  }

  async function openEntry(entry: FileNode) {
    if (!entry.is_dir) {
      const mode = previewMode(entry.ext);
      if (mode !== 'none') {
        viewingEntry = entry;
      } else {
        selectedEntry = entry;
        showInfoPanel();
      }
      return;
    }
    const owner = sources.find((source) => source.source_id === entry.source_id);
    if (owner && owner.source_id !== selectedSourceId) {
      await selectSource(owner.source_id, entry.relative_path);
      return;
    }
    const basePath = owner?.path ?? selectedSource?.path;
    if (basePath) {
      const absolutePath = normalizedPath(`${basePath}/${entry.relative_path}`);
      const nestedSource = sources.find(
        (source) => normalizedPath(source.path) === absolutePath
      );
      if (nestedSource && nestedSource.source_id !== selectedSourceId) {
        await selectSource(nestedSource.source_id);
        return;
      }
    }
    await navigate(entry.relative_path);
  }

  function startRename(entry: FileNode): void {
    renamingEntry = entry;
    renameValue = entry.name;
  }

  async function commitRename(): Promise<void> {
    if (!renamingEntry || !selectedSourceId) return;
    const trimmed = renameValue.trim();
    if (!trimmed || trimmed === renamingEntry.name) {
      renamingEntry = null;
      return;
    }
    const parent = renamingEntry.relative_path.includes('/')
      ? renamingEntry.relative_path.slice(0, renamingEntry.relative_path.lastIndexOf('/'))
      : '';
    const newPath = parent ? `${parent}/${trimmed}` : trimmed;
    try {
      await filesApi.rename(selectedSourceId, renamingEntry.relative_path, newPath);
      renamingEntry = null;
      await loadEntries();
    } catch (e) {
      error = (e as Error).message;
      renamingEntry = null;
    }
  }

  async function deleteEntry(entry: FileNode): Promise<void> {
    const label = entry.is_dir ? `folder "${entry.name}" and all its contents` : `file "${entry.name}"`;
    if (!confirm(`Delete ${label}? This cannot be undone.`)) return;
    try {
      await filesApi.deleteFile(entry.source_id, entry.relative_path);
      if (selectedEntry?.relative_path === entry.relative_path) {
        selectedEntry = null;
        infoPanelOpen = false;
      }
      await loadEntries();
    } catch (e) {
      error = (e as Error).message;
    }
  }

  async function createFolder(): Promise<void> {
    if (!selectedSourceId) return;
    const name = prompt('New folder name:');
    if (!name?.trim()) return;
    const path = currentParent ? `${currentParent}/${name.trim()}` : name.trim();
    try {
      await filesApi.mkdir(selectedSourceId, path);
      await loadEntries();
    } catch (e) {
      error = (e as Error).message;
    }
  }

  function openBackgroundMenu(event: MouseEvent): void {
    if ((event.target as HTMLElement).closest('button, [role="menu"]')) return;
    event.preventDefault();
    menuX = event.clientX;
    menuY = event.clientY;
    menuActions = [
      {
        id: 'new-folder',
        label: 'New folder',
        icon: '📁',
        disabled: !selectedSourceId,
        run: createFolder,
      },
      {
        id: 'select-all',
        label: 'Select all',
        icon: '☑',
        separatorBefore: true,
        disabled: displayed.length === 0,
        run: () => {
          // Multi-select is future work; for now select the first entry.
          if (displayed.length > 0) selectEntry(displayed[0]);
        },
      },
    ];
    menuOpen = true;
  }

  function handleGridKeydown(event: KeyboardEvent): void {
    if (event.target instanceof HTMLInputElement) return;
    if (event.key === 'i' || event.key === 'I') {
      if (selectedEntry) {
        showInfoPanel();
        event.preventDefault();
      }
    } else if (event.key === 'Delete') {
      if (selectedEntry) {
        void deleteEntry(selectedEntry);
        event.preventDefault();
      }
    } else if (event.key === 'F2') {
      if (selectedEntry) {
        startRename(selectedEntry);
        event.preventDefault();
      }
    } else if (event.key === 'Escape') {
      if (infoPanelOpen) {
        infoPanelOpen = false;
        event.preventDefault();
      } else if (selectedEntry) {
        selectedEntry = null;
        event.preventDefault();
      }
    }
  }

  function openEntryMenu(event: MouseEvent | KeyboardEvent, entry: FileNode): void {
    event.preventDefault();
    selectedEntry = entry;
    const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
    menuX = event instanceof MouseEvent ? event.clientX : rect.left + 20;
    menuY = event instanceof MouseEvent ? event.clientY : rect.top + 20;
    const owner = sources.find((source) => source.source_id === entry.source_id) ?? selectedSource;
    const absolutePath = absolutePathFor(owner?.path ?? '', entry.relative_path);
    menuActions = [
      {
        id: 'info',
        label: 'Show info',
        icon: 'ⓘ',
        run: () => { selectedEntry = entry; showInfoPanel(); },
      },
      {
        id: 'open',
        label: entry.is_dir ? 'Open folder' : 'Open',
        icon: '▸',
        run: () => openEntry(entry),
      },
      ...(!entry.is_dir ? [{
        id: 'open-external',
        label: 'Open externally',
        icon: '↗',
        run: async () => {
          try {
            await filesApi.openFile(entry.source_id, entry.relative_path);
          } catch (e) {
            error = (e as Error).message;
          }
        },
      }] : []),
      {
        id: 'reveal',
        label: 'Show in folder',
        icon: '📂',
        run: async () => {
          try {
            await filesApi.revealFile(entry.source_id, entry.relative_path);
          } catch (e) {
            error = (e as Error).message;
          }
        },
      },
      {
        id: 'rename',
        label: 'Rename',
        icon: '✏',
        separatorBefore: true,
        run: () => startRename(entry),
      },
      {
        id: 'copy-path',
        label: 'Copy path',
        icon: '⧉',
        run: async () => {
          await navigator.clipboard.writeText(absolutePath);
          showToast({ title: 'Path copied', message: absolutePath, tone: 'success' });
        },
      },
      {
        id: 'select-all',
        label: 'Select all',
        icon: '☑',
        separatorBefore: true,
        run: () => {
          if (displayed.length > 0) selectEntry(displayed[0]);
        },
      },
      {
        id: 'delete',
        label: 'Delete',
        icon: '🗑',
        danger: true,
        separatorBefore: true,
        run: () => deleteEntry(entry),
      },
    ];
    menuOpen = true;
  }

  async function foldersSaved(event: CustomEvent<FolderBatchResult>) {
    sources = event.detail.sources;
    const selectedStillExists = sources.some((source) => source.source_id === selectedSourceId);
    if (!selectedStillExists) {
      selectedSourceId = null;
      entries = [];
      clearSearch();
      const next = sources.find((source) => source.visible);
      if (next) await selectSource(next.source_id);
    } else {
      await loadEntries();
    }
  }

  async function addRootFolder() {
    if (addingFolder) return;
    addingFolder = true;
    error = '';
    try {
      const picked = await filesApi.pickFolder();
      if (!picked.native) {
        throw new Error('The native Windows folder picker is unavailable.');
      }
      const pickedPath = picked.path;
      if (!pickedPath) return;
      // A one-item batch through the same path Manage folders uses, so quick-add
      // cannot accept a folder the dialog would reject.
      const applied = await suiteApi.applyFolderChanges([
        {
          source_id: null,
          path: pickedPath,
          display_name: displayNameForPath(pickedPath),
          role: 'files',
          visible: true,
          forget: false,
        },
      ]);
      sources = applied.sources;
      const added = applied.sources.find(
        (source) => normalizedPath(source.path) === normalizedPath(pickedPath),
      );
      if (added) await selectSource(added.source_id);
    } catch (e) {
      error = (e as Error).message;
    } finally {
      addingFolder = false;
    }
  }

  async function rescan() {
    if (!selectedSourceId) return;
    busy = true;
    error = '';
    try {
      await filesApi.scanSource(selectedSourceId);
      await loadEntries();
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }

  async function runSearch() {
    const q = searchQuery.trim();
    if (!q) {
      clearSearch();
      return;
    }
    if (!selectedSourceId) return;
    loading = true;
    error = '';
    try {
      searchResults = await filesApi.search(q, selectedSourceId);
    } catch (e) {
      error = (e as Error).message;
    } finally {
      loading = false;
    }
  }

  function clearSearch() {
    searchQuery = '';
    searchResults = null;
  }

  function isSameOrAncestorPath(path: string, child: string): boolean {
    const candidate = normalizedPath(path);
    const descendant = normalizedPath(child);
    return candidate === descendant || descendant.startsWith(`${candidate}/`);
  }

  function pathDepth(path: string): number {
    return normalizedPath(path).split('/').filter(Boolean).length;
  }

  function iconFor(entry: FileNode): string {
    return fileGlyph(entry);
  }

  // Tiles whose thumbnail request failed fall back to the glyph for the rest of
  // the session, so a broken-image box never appears and the 404 is not retried.
  let thumbFailed = new Set<string>();

  function entryKey(entry: FileNode): string {
    return entry.source_id + '/' + entry.relative_path;
  }

  function markThumbFailed(entry: FileNode): void {
    thumbFailed.add(entryKey(entry));
    thumbFailed = thumbFailed;
  }

  // Bumped whenever the annotation set is re-read, i.e. after any origin edit.
  let annotationRevision = 0;

  // Files keeps its own size choice; the scale itself is shared with Danbooru.
  $: gridSize = imageSizeByValue[$filesGridSize];
  $: thumbTier = thumbnailTierFor(gridSize.gridMin);
  // Keeps the picture box proportional to the column so tiles stay square-ish
  // at every step instead of a fixed box floating in a huge tile.
  $: thumbBoxPx = Math.round(gridSize.gridMin * 0.62);

  // The thumbnail response is immutable, so this token is the only thing that
  // makes a tile refresh. mtime/size covers the file being replaced on disk.
  //
  // Annotated entries also fold in the revision: attaching a screenshot changes
  // which image the tile should show but touches neither the file's mtime nor
  // its size, so without this the browser would keep serving the pre-attachment
  // thumbnail and the attach would look like it did nothing. Unannotated
  // entries stay on the stable token and keep caching across edits.
  // ``revision`` is taken as an argument, not read from scope, so that Svelte
  // sees it in the template expression and actually recomputes ``src``.
  function thumbVersion(entry: FileNode, revision: number): string {
    const base = `${entry.mtime ?? 0}-${entry.size ?? 0}`;
    return annotatedPaths.has(entry.relative_path) ? `${base}-r${revision}` : base;
  }

  // Renderable types and folders always ask. An annotated entry also asks even
  // when its own type has no thumbnail, because the user may have attached a
  // screenshot to it - that is the only face a 3D model or archive can have.
  // Everything else stays silent, so a folder of subtitles issues no requests.
  function wantsThumbnail(entry: FileNode): boolean {
    return hasThumbnail(entry) || annotatedPaths.has(entry.relative_path);
  }

  function formatSize(bytes: number | null): string {
    if (bytes == null) return '';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let n = bytes;
    let i = 0;
    while (n >= 1024 && i < units.length - 1) {
      n /= 1024;
      i += 1;
    }
    return `${i === 0 ? n : n < 10 ? n.toFixed(1) : Math.round(n)} ${units[i]}`;
  }
</script>

<!-- Files owns one compact bar: drawer, breadcrumb, then the source tools. -->
<header class="flex h-14 shrink-0 items-center gap-3 border-b border-[var(--border-default)] bg-[var(--bg-elevated)] px-4">
  <button
    class="grid h-10 w-10 shrink-0 place-items-center rounded-full transition-colors hover:bg-[var(--module-accent-hover)]"
    type="button"
    on:click={() => (showAppMenu = true)}
    title="Open {SUITE_NAME} menu"
    aria-label="Open {SUITE_NAME} menu"
  >
    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
    </svg>
  </button>

  <div class="flex w-[17rem] min-w-0 max-w-[38%] shrink-0 items-center gap-1 overflow-x-auto text-sm">
    {#if selectedSource}
      {#if moduleUi(selectedRole).iconSrc}
        <img src={moduleUi(selectedRole).iconSrc ?? ''} alt="" class="mr-1 h-7 w-7 shrink-0 rounded-md" />
      {:else}
        <span class="mr-1 grid h-7 w-7 shrink-0 place-items-center rounded-md bg-white/5 text-base">🗂️</span>
      {/if}
      {#each breadcrumbSources as source, i}
        {#if i > 0}<span class="shrink-0 text-gray-600">/</span>{/if}
        <button
          type="button"
          class="shrink-0 text-[var(--text-primary)] hover:text-white"
          on:click={() => source.source_id === selectedSourceId ? navigate('') : selectSource(source.source_id)}
        >{source.display_name}</button>
      {/each}
      {#each crumbs as crumb, i}
        <span class="shrink-0 text-gray-600">/</span>
        <button
          type="button"
          class="shrink-0 text-[var(--text-primary)] hover:text-white"
          on:click={() => navigate(crumbs.slice(0, i + 1).join('/'))}
        >{crumb}</button>
      {/each}
    {:else}
      <span class="text-[var(--text-muted)]">Select or add a folder</span>
    {/if}
  </div>

  <div class="relative ml-4 mr-2 min-w-64 flex-1 max-w-xl">
      <input
        class="w-full rounded-lg border border-[var(--border-default)] bg-[var(--bg-elevated)] px-3 py-1.5 pr-8 text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)] transition-colors focus:border-[var(--module-accent)] disabled:opacity-40"
        placeholder="Search this folder…"
        bind:value={searchQuery}
        on:keydown={(event) => event.key === 'Enter' && runSearch()}
        disabled={!selectedSource}
      />
      {#if searchResults !== null}
        <button
          type="button"
          class="absolute right-2 top-1/2 -translate-y-1/2 text-sm text-[var(--text-muted)] hover:text-white"
          on:click={() => navigate(currentParent)}
          title="Clear search"
          aria-label="Clear search"
        >✕</button>
      {/if}
  </div>
  <div class="flex shrink-0 items-center gap-2">
    {#if hasRoleFilter}
      <div class="flex h-9 rounded-lg border border-[var(--border-default)] bg-[var(--bg-elevated)] p-0.5">
        <button
          type="button"
          class="rounded-md px-2.5 text-xs font-medium transition-colors {mediaFilter === 'media' ? 'bg-[var(--module-accent-muted)] text-white' : 'text-[var(--text-muted)] hover:text-white'}"
          on:click={() => mediaFilter = 'media'}
          aria-pressed={mediaFilter === 'media'}
        >Media</button>
        <button
          type="button"
          class="rounded-md px-2.5 text-xs font-medium transition-colors {mediaFilter === 'all' ? 'bg-[var(--module-accent-muted)] text-white' : 'text-[var(--text-muted)] hover:text-white'}"
          on:click={() => mediaFilter = 'all'}
          aria-pressed={mediaFilter === 'all'}
        >All</button>
      </div>
    {/if}
    <GridSizeMenu value={filesGridSize} />
    <button
      type="button"
      class="h-9 rounded-lg border border-[var(--border-default)] bg-[var(--bg-elevated)] px-3 text-xs text-[var(--text-primary)] transition-colors hover:border-[var(--module-accent)] hover:text-white disabled:opacity-40"
      on:click={rescan}
      disabled={!selectedSource || busy}
    >Rescan</button>
    <button
      type="button"
      class="h-9 rounded-lg border px-3 text-xs transition-colors disabled:opacity-40 {duplicateGroups !== null ? 'border-[var(--module-accent)] bg-[var(--module-accent-muted)] text-white' : 'border-[var(--border-default)] bg-[var(--bg-elevated)] text-[var(--text-primary)] hover:border-[var(--module-accent)] hover:text-white'}"
      on:click={() => (duplicateGroups !== null ? navigate(currentParent) : showDuplicates())}
      disabled={dedupBusy || sources.length === 0}
      title="Find files with identical content across every source"
    >{dedupBusy ? 'Hashing…' : duplicateGroups !== null ? 'Close duplicates' : 'Duplicates'}</button>
  </div>
</header>

<div class="flex flex-1 min-h-0 overflow-hidden">
  <!-- Sources panel -->
  <aside class="flex flex-col w-72 shrink-0 border-r border-white/5 bg-[var(--bg-base)]">
    <div class="flex items-center border-b border-white/5 px-4 py-3">
      <div class="flex-1 text-xs font-semibold uppercase tracking-wide text-[var(--text-secondary)]">Your folders</div>
      <button
        type="button"
        class="grid h-7 w-7 place-items-center rounded-md text-[var(--text-muted)] transition-colors hover:bg-white/5 hover:text-purple-100 disabled:opacity-40"
        title="Add folder"
        aria-label="Add folder"
        on:click={addRootFolder}
        disabled={addingFolder}
      >
        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-width="1.8" d="M12 5v14M5 12h14" />
        </svg>
      </button>
      <button
        type="button"
        class="grid h-7 w-7 place-items-center rounded-md text-[var(--text-muted)] transition-colors hover:bg-white/5 hover:text-purple-100"
        title="Manage folders"
        aria-label="Manage folders"
        on:click={() => (showManager = true)}
      >
        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M14.7 6.3a4 4 0 01-5 5L4 17v3h3l5.7-5.7a4 4 0 005-5l-2.4 2.4-3-3 2.4-2.4z" />
        </svg>
      </button>
    </div>
    <div class="flex-1 overflow-y-auto">
      {#each sidebarSources as source (source.source_id)}
        <button
          type="button"
          class="group flex w-full items-center gap-2 px-4 py-2.5 text-left text-sm transition-colors
                 {selectedSourceId === source.source_id ? 'bg-white/10 text-white' : 'text-[var(--text-primary)] hover:bg-white/5'}"
          on:click={() => selectSource(source.source_id)}
        >
          {#if moduleUi(source.role === 'base' ? 'files' : source.role).iconSrc}
            <img src={moduleUi(source.role === 'base' ? 'files' : source.role).iconSrc ?? ''} alt="" class="h-5 w-5 rounded" />
          {:else}
            <span class="text-base">🗂️</span>
          {/if}
          <span class="flex-1 min-w-0 truncate" title={source.path}>{source.display_name}</span>
        </button>
      {/each}
      {#if sidebarSources.length === 0}
        <p class="px-4 py-4 text-xs leading-relaxed text-[var(--text-muted)]">
          {sources.length ? 'All registered folders are hidden from this sidebar.' : "You haven't added any folders yet."}
        </p>
      {/if}
    </div>
  </aside>

  <!-- Browse area.
       This row is deliberately uncapped. A cap was tried in V1.1.2 to pull the
       info panel away from the screen edge, but on a wide display it just left
       a dead band to the right of the panel. The resizable panel solves the
       same problem better: dragging it wider moves its left edge toward the
       grid without stranding any space. -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <section
    class="flex flex-col flex-1 min-w-0"
    on:contextmenu={openBackgroundMenu}
    on:keydown={handleGridKeydown}
  >
    {#if error}
      <div class="mx-4 mt-3 px-3 py-2 text-xs rounded bg-red-500/10 border border-red-500/30 text-red-300">{error}</div>
    {/if}

    <div class="flex-1 overflow-y-auto p-4">
      {#if duplicateGroups !== null}
        {#if duplicateGroups.length === 0}
          <p class="text-sm text-[var(--text-muted)]">No duplicate files found across your sources.</p>
        {:else}
          <div class="space-y-4">
            {#each duplicateGroups as group (group.content_hash)}
              <div class="rounded-lg border border-white/5 bg-white/[0.02]">
                <div class="flex items-center gap-2 border-b border-white/5 px-3 py-2">
                  <span class="text-xs font-semibold text-purple-200">{group.files.length}× identical</span>
                  <span class="text-[10px] text-gray-600 truncate" title={group.content_hash}>md5 {group.content_hash}</span>
                  <span class="ml-auto text-[10px] text-[var(--text-muted)]">{formatSize(group.files[0]?.size ?? null)} each</span>
                </div>
                {#each group.files as file (file.source_id + '/' + file.relative_path)}
                  <div class="flex items-center gap-2 px-3 py-1.5 text-xs text-[var(--text-primary)]">
                    <span>{iconFor(file)}</span>
                    <span class="truncate">{file.name}</span>
                    <span class="ml-auto truncate text-[10px] text-[var(--text-muted)]" title={file.relative_path}>
                      {sources.find((s) => s.source_id === file.source_id)?.display_name ?? file.source_id}{file.parent ? ` / ${file.parent}` : ''}
                    </span>
                  </div>
                {/each}
              </div>
            {/each}
          </div>
        {/if}
      {:else if loading}
        <p class="text-sm text-[var(--text-muted)]">Loading…</p>
      {:else if !selectedSource}
        <div class="grid h-full place-items-center text-center">
          <div class="max-w-sm">
            <div class="mb-3 text-5xl">🗂️</div>
            <h2 class="text-lg font-semibold text-[var(--text-primary)]">No folders yet</h2>
            <p class="mt-1 text-sm text-[var(--text-muted)]">
              Add a folder from your computer and Keivotos will index it in place — your files never move.
            </p>
            <button
              type="button"
              class="mt-4 rounded-lg bg-purple-500/25 px-4 py-2 text-sm font-medium text-purple-100 transition-colors hover:bg-purple-500/35"
              on:click={addRootFolder}
            >＋ Add a folder</button>
          </div>
        </div>
      {:else if searchResults !== null && searchResults.length === 0}
        <p class="text-sm text-[var(--text-muted)]">No matches for “{searchQuery}”.</p>
      {:else if displayed.length === 0}
        <p class="text-sm text-[var(--text-muted)]">This folder is empty.</p>
      {:else}
        <div class="grid gap-2" style="grid-template-columns: repeat(auto-fill, minmax({gridSize.gridMin}px, 1fr));">
          {#each displayed as entry (entry.source_id + '/' + entry.relative_path)}
            <button
              type="button"
              class="flex flex-col items-center gap-1 p-3 rounded-lg text-center transition-colors {selectedKey === entry.source_id + '/' + entry.relative_path ? 'border border-purple-500/60 bg-purple-500/15' : 'border border-white/5 bg-white/[0.03] hover:bg-white/[0.07]'}"
              on:click={() => selectEntry(entry)}
              on:dblclick={() => openEntry(entry)}
              on:contextmenu={(event) => openEntryMenu(event, entry)}
              on:keydown={(event) => {
                if (event.key === 'Enter') openEntry(entry);
                else if (event.key === 'F10' && event.shiftKey) openEntryMenu(event, entry);
              }}
              title={entry.relative_path}
            >
              <span
                class="relative flex w-full items-center justify-center text-3xl leading-none"
                style="height: {thumbBoxPx}px;"
              >
                {#if wantsThumbnail(entry) && !thumbFailed.has(entryKey(entry))}
                  <img
                    src={filesApi.thumbnailUrl(entry.source_id, entry.relative_path, thumbTier, thumbVersion(entry, annotationRevision))}
                    alt=""
                    loading="lazy"
                    decoding="async"
                    class="max-w-full rounded object-contain"
                    style="max-height: {thumbBoxPx}px;"
                    on:error={() => markThumbFailed(entry)}
                  />
                {:else}
                  {iconFor(entry)}
                {/if}
                {#if annotatedPaths.has(entry.relative_path)}
                  <span class="absolute -right-1 -top-0.5 h-2 w-2 rounded-full bg-purple-400 ring-2 ring-[#0b0b10]" title="Has origin info"></span>
                {/if}
              </span>
              {#if renamingEntry?.relative_path === entry.relative_path}
                <!-- svelte-ignore a11y_autofocus -->
                <input
                  bind:this={renameInput}
                  bind:value={renameValue}
                  class="w-full rounded border border-purple-500 bg-[#1e1e2e] px-1 py-0.5 text-xs text-[var(--text-primary)] outline-none"
                  autofocus
                  on:blur={commitRename}
                  on:keydown={(event) => {
                    if (event.key === 'Enter') { void commitRename(); event.preventDefault(); }
                    else if (event.key === 'Escape') { renamingEntry = null; event.stopPropagation(); }
                  }}
                  on:click|stopPropagation
                  on:dblclick|stopPropagation
                />
              {:else}
                <span class="w-full truncate text-xs text-[var(--text-primary)]">{entry.name}</span>
              {/if}
              <span class="text-[10px] text-[var(--text-muted)]">
                {entry.is_dir ? 'Folder' : formatSize(entry.size)}
                {#if searchResults !== null && entry.parent}· {entry.parent}{/if}
              </span>
            </button>
          {/each}
        </div>
      {/if}
    </div>
  </section>

</div>

{#if infoPanelOpen && subject}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    class="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 backdrop-blur-sm"
    on:pointerdown|self={() => (infoPanelOpen = false)}
    on:keydown={(e) => { if (e.key === 'Escape') { infoPanelOpen = false; e.stopPropagation(); } }}
  >
    <FileInfoPanel
      {subject}
      on:close={() => (infoPanelOpen = false)}
      on:changed={loadAnnotatedPaths}
    />
  </div>
{/if}

{#if viewingEntry}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    class="fixed inset-0 z-[210] flex flex-col bg-[#0a0a10]/95 backdrop-blur-md"
    on:keydown={(e) => { if (e.key === 'Escape') { viewingEntry = null; e.stopPropagation(); } }}
  >
    <header class="flex shrink-0 items-center gap-3 border-b border-white/5 bg-[var(--bg-elevated)]/80 px-4 py-2.5">
      <span class="text-lg leading-none">{fileGlyph({ is_dir: false, ext: viewingEntry.ext })}</span>
      <div class="min-w-0 flex-1">
        <div class="truncate text-sm font-medium text-gray-100" title={viewingEntry.name}>{viewingEntry.name}</div>
        <div class="text-[11px] text-[var(--text-muted)]">
          {(viewingEntry.ext || 'file').toUpperCase()}
          {#if viewingEntry.size != null}
            <span class="mx-1 text-gray-600">·</span>
            {formatSize(viewingEntry.size)}
          {/if}
        </div>
      </div>
      <div class="flex shrink-0 items-center gap-1.5">
        <button
          type="button"
          class="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-[var(--text-primary)] transition-colors hover:bg-white/10 hover:text-white"
          on:click={() => { if (viewingEntry) { selectedEntry = viewingEntry; showInfoPanel(); } }}
        >Info</button>
        <button
          type="button"
          class="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-[var(--text-primary)] transition-colors hover:bg-white/10 hover:text-white"
          on:click={async () => {
            if (!viewingEntry) return;
            try { await filesApi.openFile(viewingEntry.source_id, viewingEntry.relative_path); }
            catch (e) { error = (e as Error).message; }
          }}
        >Open externally</button>
        <button
          type="button"
          class="grid h-8 w-8 place-items-center rounded-md text-[var(--text-secondary)] transition-colors hover:bg-white/5 hover:text-white"
          title="Close"
          aria-label="Close viewer"
          on:click={() => (viewingEntry = null)}
        >✕</button>
      </div>
    </header>

    <div class="flex flex-1 items-center justify-center overflow-auto p-6">
      {#if viewerMode === 'image'}
        <img
          src={viewerFileHref}
          alt={viewingEntry.name}
          class="max-h-full max-w-full rounded-lg object-contain"
        />
      {:else if viewerMode === 'video'}
        <!-- svelte-ignore a11y-media-has-caption -->
        <video
          src={viewerFileHref}
          controls
          autoplay
          class="max-h-full max-w-full rounded-lg"
        ></video>
      {:else if viewerMode === 'audio'}
        <div class="flex w-full max-w-lg flex-col items-center gap-6">
          <span class="text-6xl">🎵</span>
          <div class="text-center text-sm text-[var(--text-primary)]">{viewingEntry.name}</div>
          <audio src={viewerFileHref} controls autoplay class="w-full"></audio>
        </div>
      {:else if viewerMode === 'pdf'}
        <embed src={viewerFileHref} type="application/pdf" class="h-full w-full rounded-lg" />
      {:else if viewerMode === 'text'}
        <pre class="max-h-full w-full max-w-3xl overflow-auto whitespace-pre-wrap break-words rounded-lg bg-black/40 p-6 text-sm leading-relaxed text-[var(--text-primary)]">Loading…</pre>
      {/if}
    </div>
  </div>
{/if}

{#if showAppMenu}
  <AppDrawer on:close={() => (showAppMenu = false)} />
{/if}

<ActionMenu
  open={menuOpen}
  x={menuX}
  y={menuY}
  items={menuActions}
  label="File actions"
  on:close={() => menuOpen = false}
/>

{#if showManager}
  <ManageFoldersDialog
    {sources}
    modules={$suiteModules}
    on:saved={foldersSaved}
    on:close={() => (showManager = false)}
  />
{/if}
