<script lang="ts">
  import { createEventDispatcher, onDestroy, onMount } from 'svelte';
  import {
    mangaApi,
    type CoverProgressMode,
    type MangaCategory,
    type MangaRoot,
    type MangaSettings,
    type ScanProgress
  } from './mangaApi';

  const dispatch = createEventDispatcher<{ settingsChanged: MangaSettings }>();

  const COVER_PROGRESS_OPTIONS: { value: CoverProgressMode; label: string }[] = [
    { value: 'off', label: 'Off' },
    { value: 'bar', label: 'Bar only' },
    { value: 'percent', label: 'Percentage' },
    { value: 'pages', label: 'Page count' }
  ];

  let roots: MangaRoot[] = [];
  let settings: MangaSettings | null = null;
  let categories: MangaCategory[] = [];
  let scan: ScanProgress | null = null;
  let enrich: { running: boolean; message: string; unmatched: number; processed: number; total: number } | null = null;
  let migrate: { running: boolean; message: string; processed: number; total: number } | null = null;
  let newRootPath = '';
  let newCategoryName = '';
  let newIgnoredTag = '';
  let message = '';
  let scanTimer: ReturnType<typeof setInterval> | null = null;

  async function refresh() {
    [roots, settings, categories, scan] = [
      (await mangaApi.roots()).roots,
      await mangaApi.settings(),
      (await mangaApi.categories()).categories,
      await mangaApi.scanProgress()
    ];
    try {
      enrich = await (await fetch('/api/manga/enrich')).json();
      migrate = await (await fetch('/api/manga/migrate')).json();
    } catch {
      /* older server without job endpoints */
    }
    if (scan.running || enrich?.running || migrate?.running) startPolling();
  }

  function startPolling() {
    if (scanTimer) return;
    scanTimer = setInterval(async () => {
      scan = await mangaApi.scanProgress();
      try {
        enrich = await (await fetch('/api/manga/enrich')).json();
        migrate = await (await fetch('/api/manga/migrate')).json();
      } catch {
        /* transient */
      }
      if (!scan.running && !enrich?.running && !migrate?.running && scanTimer) {
        clearInterval(scanTimer);
        scanTimer = null;
        roots = (await mangaApi.roots()).roots;
      }
    }, 1000);
  }

  async function startMigrate(root: MangaRoot) {
    if (!confirm(`Convert flat <id>.cbz files under "${root.path}" into nested title folders? This MOVES files on disk.`)) return;
    message = '';
    const response = await fetch('/api/manga/migrate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ root_id: root.id })
    });
    if (!response.ok) message = (await response.json()).detail ?? 'Could not start convert';
    else startPolling();
  }

  async function startEnrich() {
    message = '';
    const response = await fetch('/api/manga/enrich', { method: 'POST' });
    if (!response.ok) message = (await response.json()).detail ?? 'Could not start enrich';
    else startPolling();
  }

  async function save(changes: Partial<MangaSettings>) {
    settings = await mangaApi.updateSettings(changes);
    dispatch('settingsChanged', settings);
  }

  async function addRoot() {
    message = '';
    try {
      await mangaApi.addRoot(newRootPath);
      newRootPath = '';
      roots = (await mangaApi.roots()).roots;
    } catch (e) {
      message = e instanceof Error ? e.message : String(e);
    }
  }

  async function removeRoot(root: MangaRoot) {
    if (!confirm(`Forget "${root.path}"? Files on disk are never touched — this only un-indexes ${root.manga_count} manga.`)) return;
    await mangaApi.removeRoot(root.id);
    roots = (await mangaApi.roots()).roots;
  }

  async function relocateRoot(root: MangaRoot) {
    const destination = prompt(
      'Choose the folder that now contains this same manga tree. Keivotos will update stored paths only; it will not move files.',
      root.path
    );
    if (!destination || destination.trim() === root.path) return;
    message = '';
    try {
      const preview = await mangaApi.previewRootRelocation(root.id, destination.trim());
      if (!confirm(
        `Verified ${preview.verified_files} indexed manga at the new location. Update the stored root and index paths? No files will be moved or deleted.`
      )) return;
      const result = await mangaApi.relocateRoot(root.id, destination.trim());
      roots = (await mangaApi.roots()).roots;
      message = `Updated ${result.indexed_files} indexed paths to ${result.new_path}.`;
    } catch (e) {
      message = e instanceof Error ? e.message : String(e);
    }
  }

  async function startScan(root: MangaRoot, enrich: boolean) {
    message = '';
    try {
      await mangaApi.startScan(root.id, enrich);
      scan = await mangaApi.scanProgress();
      startPolling();
    } catch (e) {
      message = e instanceof Error ? e.message : String(e);
    }
  }

  async function addCategory() {
    if (!newCategoryName.trim()) return;
    try {
      categories = (await mangaApi.createCategory(newCategoryName)).categories;
      newCategoryName = '';
    } catch (e) {
      message = e instanceof Error ? e.message : String(e);
    }
  }

  async function removeCategory(category: MangaCategory) {
    if (!confirm(`Delete category "${category.name}"? Manga stay in the library.`)) return;
    categories = (await mangaApi.deleteCategory(category.id)).categories;
  }

  async function addIgnoredTag() {
    if (!settings || !newIgnoredTag.trim()) return;
    await save({ ignored_tags: [...settings.ignored_tags, newIgnoredTag.trim().toLowerCase()] });
    newIgnoredTag = '';
  }

  async function removeIgnoredTag(tag: string) {
    if (!settings) return;
    await save({ ignored_tags: settings.ignored_tags.filter((t) => t !== tag) });
  }

  onMount(() => void refresh());
  onDestroy(() => {
    if (scanTimer) clearInterval(scanTimer);
  });
</script>

<div class="mx-auto max-w-3xl space-y-4 p-3 sm:space-y-6 sm:p-4">
  {#if message}
    <p class="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-200">{message}</p>
  {/if}

  <section class="rounded-xl border border-[#26263a] bg-[#14141c] p-3 sm:p-4">
    <h2 class="mb-3 text-sm font-semibold text-gray-200">Library folders</h2>
    {#each roots as root (root.id)}
      <div class="mb-2 flex flex-wrap items-center gap-2 rounded-lg bg-[#191922] px-3 py-2 text-sm">
        <span class="min-w-0 flex-1 break-all text-gray-300 sm:truncate" title={root.path}>{root.path}</span>
        <span class="text-xs text-gray-500">{root.manga_count} manga</span>
        <button class="rounded border border-[#2c2c40] px-2 py-1 text-xs text-gray-300 hover:border-purple-400/60" on:click={() => startScan(root, false)} disabled={scan?.running}>Scan</button>
        <button class="rounded border border-[#2c2c40] px-2 py-1 text-xs text-gray-300 hover:border-purple-400/60" title="Scan and fetch missing metadata from nHentai (needs online access enabled)" on:click={() => startScan(root, true)} disabled={scan?.running}>Scan + fetch</button>
        <button class="rounded border border-[#2c2c40] px-2 py-1 text-xs text-gray-300 hover:border-purple-400/60" title="Move flat <id>.cbz files into the nested title folders (fetches titles; explicit file moves)" on:click={() => startMigrate(root)} disabled={migrate?.running}>Convert</button>
        <button class="rounded border border-sky-500/30 px-2 py-1 text-xs text-sky-200 hover:bg-sky-500/10" title="Update the index after this entire folder was moved elsewhere" on:click={() => relocateRoot(root)}>Relocate</button>
        <button class="rounded border border-red-500/30 px-2 py-1 text-xs text-red-300 hover:bg-red-500/10" on:click={() => removeRoot(root)}>Forget</button>
      </div>
    {/each}
    <div class="mt-2 flex flex-col gap-2 sm:flex-row">
      <input class="min-w-0 flex-1 rounded-lg border border-[#2c2c40] bg-[#15151f] px-3 py-1.5 text-sm text-gray-200 placeholder-gray-600" placeholder="D:\path\to\manga-folder" bind:value={newRootPath} />
      <button class="w-full rounded-lg border border-purple-500/40 bg-purple-500/10 px-3 py-1.5 text-sm text-purple-200 hover:bg-purple-500/20 sm:w-auto" on:click={addRoot}>Add folder</button>
    </div>

    {#if scan && (scan.running || scan.finished_at)}
      <div class="mt-3 rounded-lg bg-[#191922] p-3 text-sm">
        {#if scan.running}
          <p class="text-gray-300">Scanning… {scan.processed}/{scan.total} — {scan.current_file}</p>
          <div class="mt-2 h-1.5 overflow-hidden rounded bg-[#26263a]">
            <div class="h-full bg-purple-500 transition-all" style="width: {scan.total ? (scan.processed / scan.total) * 100 : 0}%"></div>
          </div>
        {:else}
          <p class="text-gray-400">{scan.message}{scan.errors ? ` — ${scan.errors} errors (see log)` : ''}</p>
        {/if}
      </div>
    {/if}

    {#if enrich}
      <div class="mt-3 flex flex-wrap items-center gap-2 rounded-lg bg-[#191922] p-3 text-sm">
        <span class="min-w-0 flex-1 text-gray-400">
          {#if enrich.running}
            Fetching metadata… {enrich.processed}/{enrich.total}
          {:else}
            {enrich.unmatched} manga still missing nHentai metadata{enrich.message !== 'idle' ? ` — ${enrich.message}` : ''}
          {/if}
        </span>
        <button class="rounded border border-[#2c2c40] px-2 py-1 text-xs text-gray-300 hover:border-purple-400/60" disabled={enrich.running || enrich.unmatched === 0} on:click={startEnrich}>Fetch missing metadata</button>
      </div>
    {/if}
    {#if migrate && (migrate.running || migrate.message !== 'idle')}
      <div class="mt-2 rounded-lg bg-[#191922] p-3 text-sm text-gray-400">
        {#if migrate.running}Converting… {migrate.processed}/{migrate.total}{:else}{migrate.message}{/if}
      </div>
    {/if}
  </section>

  <section class="rounded-xl border border-[#26263a] bg-[#14141c] p-3 sm:p-4">
    <h2 class="mb-1 text-sm font-semibold text-gray-200">nHentai access</h2>
    <p class="mb-3 text-xs text-gray-500">
      Online browsing, downloads, and metadata fetches stay off until you enable them.
      If nHentai blocks requests, paste a fresh cf_clearance cookie and the matching browser User-Agent.
    </p>
    {#if settings}
      <label class="mb-3 flex items-center gap-2 text-sm text-gray-300">
        <input type="checkbox" checked={settings.nhentai_enabled} on:change={(e) => save({ nhentai_enabled: e.currentTarget.checked })} />
        Enable online nHentai access
      </label>
      <div class="grid gap-2 sm:grid-cols-2">
        <label class="text-xs text-gray-500">cf_clearance cookie
          <input class="mt-1 w-full rounded-lg border border-[#2c2c40] bg-[#15151f] px-3 py-1.5 text-sm text-gray-200" value={settings.cf_clearance} on:change={(e) => save({ cf_clearance: e.currentTarget.value })} />
        </label>
        <label class="text-xs text-gray-500">User-Agent
          <input class="mt-1 w-full rounded-lg border border-[#2c2c40] bg-[#15151f] px-3 py-1.5 text-sm text-gray-200" value={settings.user_agent} on:change={(e) => save({ user_agent: e.currentTarget.value })} />
        </label>
        <label class="text-xs text-gray-500">Request delay (ms, 250–10000)
          <input type="number" min="250" max="10000" class="mt-1 w-full rounded-lg border border-[#2c2c40] bg-[#15151f] px-3 py-1.5 text-sm text-gray-200" value={settings.request_delay_ms} on:change={(e) => save({ request_delay_ms: Number(e.currentTarget.value) })} />
        </label>
      </div>
    {/if}
  </section>

  <section class="rounded-xl border border-[#26263a] bg-[#14141c] p-3 sm:p-4">
    <h2 class="mb-3 text-sm font-semibold text-gray-200">Appearance</h2>
    {#if settings}
      <label class="mb-2 flex items-center gap-2 text-sm text-gray-300">
        <input type="checkbox" checked={settings.blur_covers} on:change={(e) => save({ blur_covers: e.currentTarget.checked })} />
        Blur covers by default (hover peeks; eye button toggles per session)
      </label>
      <label class="flex items-center gap-2 text-sm text-gray-300">
        <input type="checkbox" checked={settings.show_ignored} on:change={(e) => save({ show_ignored: e.currentTarget.checked })} />
        Show blacklisted manga as clearly labelled blacked-out cards (off excludes them before paging)
      </label>
      <label class="mt-3 flex items-center justify-between gap-3 text-sm text-gray-300">
        <span>Reading progress on covers<span class="block text-xs text-gray-500">A white line marks how far you've read; add a percentage or page count.</span></span>
        <select
          class="shrink-0 rounded-lg border border-[#2c2c40] bg-[#15151f] px-2 py-1.5 text-sm text-gray-200"
          value={settings.cover_progress}
          on:change={(e) => save({ cover_progress: e.currentTarget.value as CoverProgressMode })}
        >
          {#each COVER_PROGRESS_OPTIONS as option (option.value)}
            <option value={option.value}>{option.label}</option>
          {/each}
        </select>
      </label>
      <div class="mt-3">
        <h3 class="mb-1 text-xs font-semibold text-gray-400">Blacklist</h3>
        <div class="flex flex-wrap gap-1">
          {#each settings.ignored_tags as tag (tag)}
            <button class="rounded-full border border-[#2c2c40] px-2 py-0.5 text-xs text-gray-300 hover:border-red-400/60" title="Remove" on:click={() => removeIgnoredTag(tag)}>{tag} ✕</button>
          {/each}
        </div>
        <div class="mt-2 flex flex-col gap-2 sm:flex-row">
          <input class="min-w-0 flex-1 rounded-lg border border-[#2c2c40] bg-[#15151f] px-3 py-1.5 text-sm text-gray-200 placeholder-gray-600" placeholder="tag to blacklist" bind:value={newIgnoredTag} on:keydown={(e) => e.key === 'Enter' && addIgnoredTag()} />
          <button class="w-full rounded-lg border border-[#2c2c40] px-3 py-1.5 text-sm text-gray-300 sm:w-auto" on:click={addIgnoredTag}>Add</button>
        </div>
      </div>
    {/if}
  </section>

  <section class="rounded-xl border border-[#26263a] bg-[#14141c] p-3 sm:p-4">
    <h2 class="mb-3 text-sm font-semibold text-gray-200">Library categories</h2>
    {#each categories as category (category.id)}
      <div class="mb-1 flex items-center gap-2 rounded-lg bg-[#191922] px-3 py-1.5 text-sm">
        <span class="min-w-0 flex-1 truncate text-gray-300">{category.name}</span>
        <span class="text-xs text-gray-500">{category.manga_count}</span>
        <button class="rounded border border-red-500/30 px-2 py-0.5 text-xs text-red-300 hover:bg-red-500/10" on:click={() => removeCategory(category)}>Delete</button>
      </div>
    {/each}
    <div class="mt-2 flex flex-col gap-2 sm:flex-row">
      <input class="min-w-0 flex-1 rounded-lg border border-[#2c2c40] bg-[#15151f] px-3 py-1.5 text-sm text-gray-200 placeholder-gray-600" placeholder="New category name" bind:value={newCategoryName} on:keydown={(e) => e.key === 'Enter' && addCategory()} />
      <button class="w-full rounded-lg border border-[#2c2c40] px-3 py-1.5 text-sm text-gray-300 sm:w-auto" on:click={addCategory}>Create</button>
    </div>
  </section>
</div>
