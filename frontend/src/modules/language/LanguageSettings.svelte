<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import {
    languageApi,
    type LanguageImportJob,
    type LanguageImportPreview,
    type LanguageSettings,
    type LanguageStatus,
  } from '../../lib/languageApi';
  import {
    languageAutoplay,
    languageStudyProfile,
    languageGridSize,
    languagePageSize,
    type LanguagePageSize,
  } from './stores';

  let status: LanguageStatus | null = null;
  let settings: LanguageSettings | null = null;
  let profiles: Array<{ note_type: string; mapping: Record<string, unknown> }> = [];
  let loading = true;
  let busy = false;
  let error = '';
  let message = '';
  let port = 8765;
  let syncMode: 'incremental' | 'full' = 'incremental';
  let apiKey = '';
  let clearApiKey = false;
  let krdictApiKey = '';
  let clearKrdictApiKey = false;
  let probe: Record<string, unknown> | null = null;
  let deck = '한국어::2. Refold KO1K v2';
  let preview: LanguageImportPreview | null = null;
  let profilesConfirmed = false;
  let mergeIds: string[] = [];
  let job: LanguageImportJob | null = null;
  let poller: ReturnType<typeof setTimeout> | null = null;
  let destroyed = false;

  $: storage = status?.storage ?? {};
  $: cachedProbe = probe ?? settings?.cached_probe ?? status?.anki.cached_probe ?? null;
  $: decks = Array.isArray(cachedProbe?.decks) ? cachedProbe.decks as string[] : [];
  $: active = job && ['queued', 'running', 'cancelling'].includes(job.status);

  async function refresh() {
    loading = true;
    error = '';
    try {
      const [nextStatus, nextSettings, nextProfiles] = await Promise.all([
        languageApi.status(),
        languageApi.settings(),
        languageApi.profiles(),
      ]);
      status = nextStatus;
      settings = nextSettings;
      profiles = nextProfiles.items;
      port = nextSettings.port;
      syncMode = nextSettings.sync_mode;
      job = nextStatus.jobs.find((value) =>
        ['queued', 'running', 'cancelling'].includes(value.status)
      ) ?? nextStatus.jobs[0] ?? null;
      if (active) pollJob();
    } catch (cause) {
      error = (cause as Error).message;
    } finally {
      loading = false;
    }
  }

  async function saveSettings() {
    busy = true;
    error = '';
    message = '';
    try {
      settings = await languageApi.saveSettings(
        port,
        syncMode,
        apiKey,
        clearApiKey,
        krdictApiKey,
        clearKrdictApiKey,
      );
      apiKey = '';
      clearApiKey = false;
      krdictApiKey = '';
      clearKrdictApiKey = false;
      message = 'Languages connection settings saved.';
    } catch (cause) {
      error = (cause as Error).message;
    } finally {
      busy = false;
    }
  }

  async function runProbe() {
    busy = true;
    error = '';
    message = '';
    try {
      probe = await languageApi.probe();
      if (probe.reachable) {
        message = `Connected to AnkiConnect v${probe.version}. Nothing was imported.`;
        if (!decks.includes(deck) && decks[0]) deck = String(decks[0]);
      } else {
        error = String(probe.error || 'AnkiConnect is unavailable.');
      }
    } catch (cause) {
      error = (cause as Error).message;
    } finally {
      busy = false;
    }
  }

  async function previewImport() {
    busy = true;
    error = '';
    message = '';
    try {
      preview = (await languageApi.preview(deck)).preview;
      mergeIds = preview.duplicates.map((value) => value.manual_word_id);
      profilesConfirmed = preview.note_types.every((noteType) =>
        profiles.some((profile) => profile.note_type === noteType)
      );
      message = `Previewed ${preview.note_count.toLocaleString()} notes. No local data was changed.`;
    } catch (cause) {
      error = (cause as Error).message;
    } finally {
      busy = false;
    }
  }

  async function confirmProfiles() {
    if (!preview) return;
    busy = true;
    error = '';
    try {
      for (const profile of preview.proposed_profiles) {
        const noteType = String(profile.note_type || '');
        if (noteType) await languageApi.saveProfile(noteType, profile);
      }
      profiles = (await languageApi.profiles()).items;
      profilesConfirmed = preview.note_types.every((noteType) =>
        profiles.some((profile) => profile.note_type === noteType)
      );
      message = 'Field mapping confirmed locally.';
    } catch (cause) {
      error = (cause as Error).message;
    } finally {
      busy = false;
    }
  }

  async function startImport() {
    if (!preview || !profilesConfirmed) return;
    busy = true;
    error = '';
    try {
      job = (await languageApi.startImport(preview, mergeIds)).job;
      preview = null;
      message = 'Read-only Anki mirror started.';
      pollJob();
    } catch (cause) {
      error = (cause as Error).message;
    } finally {
      busy = false;
    }
  }

  async function pollJob() {
    if (!job || destroyed) return;
    try {
      job = (await languageApi.importJob(job.job_id)).job;
      if (['queued', 'running', 'cancelling'].includes(job.status)) {
        poller = setTimeout(pollJob, 650);
      } else if (job.status === 'completed') {
        status = await languageApi.status();
        message = 'Anki mirror complete.';
      }
    } catch (cause) {
      error = (cause as Error).message;
    }
  }

  async function cancelJob() {
    if (!job) return;
    try {
      job = (await languageApi.cancelImport(job.job_id)).job;
      pollJob();
    } catch (cause) {
      error = (cause as Error).message;
    }
  }

  function toggleMerge(wordId: string) {
    mergeIds = mergeIds.includes(wordId)
      ? mergeIds.filter((value) => value !== wordId)
      : [...mergeIds, wordId];
  }

  onMount(refresh);
  onDestroy(() => {
    destroyed = true;
    if (poller) clearTimeout(poller);
  });
</script>

<div class="mx-auto max-w-3xl space-y-4">
  <section class="overflow-hidden rounded-2xl border border-amber-300/15 bg-[radial-gradient(circle_at_85%_-30%,rgba(245,158,11,.17),transparent_55%),#14120f]">
    <div class="flex flex-wrap items-center justify-between gap-4 border-b border-white/7 px-5 py-4">
      <div>
        <p class="text-[10px] font-semibold uppercase tracking-[0.2em] text-amber-300">Languages module</p>
        <h3 class="mt-1 text-lg font-bold text-white">Your learned-word mirror</h3>
      </div>
      <button type="button" class="rounded-xl border border-white/10 px-3 py-2 text-xs text-white/65 hover:bg-white/5" on:click={refresh}>Refresh local state</button>
    </div>
    <div class="grid gap-3 p-4 sm:grid-cols-4">
      {#each [
        ['Words', status?.counts.words ?? 0],
        ['Manual', status?.counts.manual ?? 0],
        ['Media', status?.counts.media ?? 0],
        ['Lists', status?.counts.lists ?? 0],
      ] as value}
        <div class="rounded-xl border border-white/7 bg-black/20 p-4"><div class="text-[10px] uppercase tracking-wider text-white/35">{value[0]}</div><div class="mt-1 text-2xl font-bold text-amber-100">{loading ? '…' : Number(value[1]).toLocaleString()}</div></div>
      {/each}
    </div>
  </section>

  <section id="setting-language-dictionary" class="rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)] p-4">
    <div class="flex items-start justify-between gap-4">
      <div>
        <h4 class="text-sm font-semibold text-[var(--text-primary)]">KRDICT enrichment · explicit only</h4>
        <p class="mt-1 text-xs leading-5 text-[var(--text-muted)]">The Analyzer works offline without this. A saved key enables a button that looks up the selected lemma in the official Korean Learners' Dictionary for English and Mongolian. No lookup runs automatically.</p>
      </div>
      <span class="rounded-full px-2.5 py-1 text-[10px] font-semibold {settings?.has_krdict_api_key ? 'bg-teal-400/10 text-teal-200' : 'bg-white/5 text-white/35'}">{settings?.has_krdict_api_key ? 'Configured' : 'Optional'}</span>
    </div>
    <div class="mt-4 grid gap-3 sm:grid-cols-[1fr_auto_auto]">
      <label><span class="mb-1 block text-[10px] uppercase text-white/30">KRDICT API key</span><input class="setting-input" type="password" bind:value={krdictApiKey} placeholder={settings?.has_krdict_api_key ? 'Saved securely · leave blank to keep' : '32-character key from KRDICT'} /></label>
      <label class="mt-5 flex items-center gap-2 text-xs text-white/40"><input type="checkbox" bind:checked={clearKrdictApiKey} /> Clear key</label>
      <button type="button" class="setting-button mt-5" on:click={saveSettings} disabled={busy}>Save dictionary key</button>
    </div>
  </section>

  {#if error}<p class="rounded-xl border border-red-400/15 bg-red-500/6 px-4 py-3 text-xs text-red-300">{error}</p>{/if}
  {#if message}<p class="rounded-xl border border-emerald-400/15 bg-emerald-500/6 px-4 py-3 text-xs text-emerald-200">{message}</p>{/if}

  <section id="setting-language-anki" class="rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)] p-4">
    <div class="flex items-start justify-between gap-4">
      <div>
        <h4 class="text-sm font-semibold text-[var(--text-primary)]">AnkiConnect · read only</h4>
        <p class="mt-1 text-xs leading-5 text-[var(--text-muted)]">Keivotos reads notes, cards, reviews, and media only after you press a button. It never writes to Anki or schedules a card.</p>
      </div>
      <span class="rounded-full px-2.5 py-1 text-[10px] font-semibold {cachedProbe?.reachable ? 'bg-emerald-400/10 text-emerald-200' : 'bg-white/5 text-white/35'}">{cachedProbe?.reachable ? 'Connected' : 'Not probed'}</span>
    </div>
    <div class="mt-4 grid gap-3 sm:grid-cols-[8rem_1fr_auto]">
      <label><span class="mb-1 block text-[10px] uppercase text-white/30">Port</span><input class="setting-input" type="number" min="1" max="65535" bind:value={port} /></label>
      <label><span class="mb-1 block text-[10px] uppercase text-white/30">Optional API key</span><input class="setting-input" type="password" bind:value={apiKey} placeholder={settings?.has_api_key ? 'Saved securely · leave blank to keep' : 'Usually blank'} /></label>
      <label class="mt-5 flex items-center gap-2 text-xs text-white/40"><input type="checkbox" bind:checked={clearApiKey} /> Clear key</label>
    </div>
    <div class="mt-3 flex flex-wrap gap-2">
      <button type="button" class="setting-button" on:click={saveSettings} disabled={busy}>Save settings</button>
      <button type="button" class="setting-button accent" on:click={runProbe} disabled={busy}>Probe Anki</button>
    </div>
  </section>

  <section id="setting-language-profiles" class="rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)] p-4">
    <h4 class="text-sm font-semibold text-[var(--text-primary)]">Deck scope and field profile</h4>
    <div class="mt-3 grid gap-3 sm:grid-cols-[1fr_auto]">
      {#if decks.length}
        <select class="setting-input" bind:value={deck}>{#each decks as value}<option value={value}>{value}</option>{/each}</select>
      {:else}
        <input class="setting-input" bind:value={deck} placeholder="Anki deck path" />
      {/if}
      <button type="button" class="setting-button accent" on:click={previewImport} disabled={busy || !deck.trim()}>Preview mirror</button>
    </div>
    <div class="mt-3 flex items-center gap-3 text-xs text-white/40">
      <span>Mode</span>
      <select class="rounded-lg border border-white/8 bg-black/20 px-3 py-2" bind:value={syncMode} on:change={saveSettings}><option value="incremental">Incremental</option><option value="full">Full refresh</option></select>
      <span>{profiles.length} confirmed profile{profiles.length === 1 ? '' : 's'}</span>
    </div>

    {#if preview}
      <div class="mt-4 rounded-2xl border border-amber-300/15 bg-amber-300/5 p-4">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div><strong class="text-sm text-amber-100">{preview.note_count.toLocaleString()} notes</strong><p class="mt-1 text-xs text-white/35">{preview.note_types.join(', ') || 'No note types found'}</p></div>
          <span class="text-[10px] text-white/25">Expires {new Date(preview.expires_at).toLocaleTimeString()}</span>
        </div>
        {#if !profilesConfirmed}
          <button type="button" class="setting-button mt-3" on:click={confirmProfiles} disabled={busy || !preview.proposed_profiles.length}>Review and confirm proposed KO1K mapping</button>
        {:else}
          <p class="mt-3 text-xs text-emerald-200/70">Field profile confirmed locally.</p>
        {/if}
        {#if preview.duplicates.length}
          <div class="mt-4 border-t border-white/8 pt-3">
            <p class="text-xs font-semibold text-white/55">Possible manual duplicates</p>
            {#each preview.duplicates as duplicate}
              <label class="mt-2 flex items-center gap-2 text-xs text-white/45"><input type="checkbox" checked={mergeIds.includes(duplicate.manual_word_id)} on:change={() => toggleMerge(duplicate.manual_word_id)} /> Merge and preserve “{duplicate.headword}” as local overrides</label>
            {/each}
          </div>
        {/if}
        <button type="button" class="mt-4 w-full rounded-xl bg-amber-300 px-4 py-3 text-sm font-bold text-[#251a05] disabled:opacity-35" on:click={startImport} disabled={busy || !profilesConfirmed}>Start confirmed read-only mirror</button>
      </div>
    {/if}

    {#if job}
      <div class="mt-4 rounded-2xl border border-white/8 bg-black/20 p-4">
        <div class="flex justify-between text-xs"><span class="capitalize text-white/65">{job.phase}</span><span class="text-white/35">{Math.round(job.progress * 100)}%</span></div>
        <div class="mt-2 h-2 overflow-hidden rounded-full bg-white/8"><div class="h-full rounded-full bg-amber-300 transition-all" style={`width:${job.progress * 100}%`}></div></div>
        <p class="mt-2 text-[10px] text-white/30">{job.processed} / {job.total} notes · {job.counts.media ?? 0} media</p>
        {#if job.error}<p class="mt-2 text-xs text-red-300">{job.error}</p>{/if}
        {#if active}<button type="button" class="setting-button mt-3" on:click={cancelJob}>Cancel cooperatively</button>{/if}
      </div>
    {/if}
  </section>

  <section id="setting-language-storage" class="rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)] p-4">
    <div class="flex items-center justify-between gap-3">
      <h4 class="text-sm font-semibold text-[var(--text-primary)]">Storage, Files and export</h4>
      <a class="setting-button" href={languageApi.exportUrl} download>Export JSON</a>
    </div>
    <div class="mt-3 space-y-2 text-xs">
      {#each Object.entries(storage) as [label, path]}
        <div class="rounded-lg bg-black/20 px-3 py-2"><span class="mr-2 font-semibold capitalize text-[var(--text-secondary)]">{label}</span><span class="break-all text-gray-600">{path}</span></div>
      {/each}
    </div>
    <p class="mt-3 text-xs leading-5 text-emerald-200/60">Media is versioned and create-only. Authored words, edits, notes, lists, profiles, and practice history stay in the precious suite user database.</p>
  </section>

  <section id="setting-language-display" class="rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)] p-4">
    <h4 class="text-sm font-semibold text-[var(--text-primary)]">Display defaults</h4>
    <div class="mt-3 grid gap-3 sm:grid-cols-3">
      <label><span class="mb-1 block text-[10px] uppercase text-white/30">Card size</span><select class="setting-input" bind:value={$languageGridSize}>{#each ['small','medium','large','huge','gigantic','absurd'] as value}<option value={value}>{value}</option>{/each}</select></label>
      <label><span class="mb-1 block text-[10px] uppercase text-white/30">Page size</span><select class="setting-input" value={$languagePageSize} on:change={(event) => languagePageSize.set(event.currentTarget.value === 'all' ? 'all' : Number(event.currentTarget.value) as LanguagePageSize)}><option value="30">30</option><option value="60">60</option><option value="120">120</option><option value="all">All · infinite</option></select></label>
      <label class="mt-5 flex items-center gap-2 text-xs text-white/45"><input type="checkbox" bind:checked={$languageAutoplay} /> Autoplay word audio</label>
    </div>
    <div class="mt-4 border-t border-white/7 pt-4">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h5 class="text-xs font-semibold text-[var(--text-primary)]">Study and meaning profile</h5>
          <p class="mt-1 text-xs leading-5 text-[var(--text-muted)]">Korean-only tools are labelled explicitly. Choose which authored meaning appears first across the general Languages library.</p>
        </div>
        <span class="rounded-full border border-teal-300/15 bg-teal-300/5 px-3 py-1 text-[10px] font-semibold text-teal-100/60">Korean → EN + MN</span>
      </div>
      <div class="mt-3 grid gap-3 sm:grid-cols-2">
        <label><span class="mb-1 block text-[10px] uppercase text-white/30">Primary meaning</span><select class="setting-input" bind:value={$languageStudyProfile.primaryMeaning}><option value="en">English first</option><option value="mn">Mongolian first</option></select></label>
        <label class="mt-5 flex items-center gap-2 text-xs text-white/45"><input type="checkbox" bind:checked={$languageStudyProfile.showSecondaryMeaning} /> Show the second meaning on cards</label>
      </div>
    </div>
  </section>
</div>

<style>
  .setting-input { width:100%; border:1px solid rgba(255,255,255,.09); border-radius:.65rem; background:rgba(0,0,0,.22); padding:.55rem .7rem; color:rgba(255,255,255,.8); font-size:.75rem; outline:none; }
  .setting-input:focus { border-color:rgba(251,191,36,.5); }
  .setting-button { display:inline-flex; align-items:center; justify-content:center; border:1px solid rgba(255,255,255,.1); border-radius:.65rem; padding:.55rem .8rem; color:rgba(255,255,255,.65); font-size:.75rem; font-weight:600; }
  .setting-button:hover { background:rgba(255,255,255,.05); }
  .setting-button.accent { border-color:rgba(251,191,36,.25); color:rgb(254 243 199); }
  .setting-button:disabled { opacity:.4; }
</style>
