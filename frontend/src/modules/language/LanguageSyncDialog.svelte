<script lang="ts">
  import { createEventDispatcher, onDestroy } from 'svelte';
  import {
    languageApi,
    type LanguageImportJob,
    type LanguageImportPreview,
  } from '../../lib/languageApi';

  const dispatch = createEventDispatcher<{ close: void; completed: void }>();
  let phase: 'probe' | 'scope' | 'preview' | 'job' = 'probe';
  let decks: string[] = [];
  let deck = '한국어::2. Refold KO1K v2';
  let preview: LanguageImportPreview | null = null;
  let profileConfirmed = false;
  let unmappedNoteTypes: string[] = [];
  let mergeIds: string[] = [];
  let job: LanguageImportJob | null = null;
  let busy = false;
  let error = '';
  let message = '';
  let timer: ReturnType<typeof setTimeout> | null = null;
  let destroyed = false;

  async function probe() {
    busy = true;
    error = '';
    try {
      const result = await languageApi.probe();
      if (!result.reachable) throw new Error(String(result.error || 'AnkiConnect is unavailable.'));
      decks = Array.isArray(result.decks) ? result.decks as string[] : [];
      if (!decks.includes(deck) && decks[0]) deck = decks[0];
      message = `Connected to AnkiConnect v${result.version}. Nothing imported yet.`;
      phase = 'scope';
    } catch (cause) {
      error = (cause as Error).message;
    } finally {
      busy = false;
    }
  }

  async function buildPreview() {
    busy = true;
    error = '';
    try {
      preview = (await languageApi.preview(deck)).preview;
      const profiles = (await languageApi.profiles()).items;
      const savedNoteTypes = new Set(profiles.map((profile) => profile.note_type));
      const proposedNoteTypes = new Set(
        preview.proposed_profiles.map((profile) => String(profile.note_type || '')),
      );
      profileConfirmed = preview.note_types.every((noteType) =>
        savedNoteTypes.has(noteType)
      );
      unmappedNoteTypes = preview.note_types.filter(
        (noteType) => !savedNoteTypes.has(noteType) && !proposedNoteTypes.has(noteType),
      );
      mergeIds = preview.duplicates.map((value) => value.manual_word_id);
      phase = 'preview';
    } catch (cause) {
      error = (cause as Error).message;
    } finally {
      busy = false;
    }
  }

  async function confirmProfile() {
    if (!preview) return;
    busy = true;
    error = '';
    try {
      for (const profile of preview.proposed_profiles) {
        const noteType = String(profile.note_type || '');
        if (noteType) await languageApi.saveProfile(noteType, profile);
      }
      const profiles = (await languageApi.profiles()).items;
      profileConfirmed = preview.note_types.every((noteType) =>
        profiles.some((profile) => profile.note_type === noteType)
      );
      unmappedNoteTypes = preview.note_types.filter((noteType) =>
        !profiles.some((profile) => profile.note_type === noteType)
      );
    } catch (cause) {
      error = (cause as Error).message;
    } finally {
      busy = false;
    }
  }

  async function start() {
    if (!preview || !profileConfirmed) return;
    busy = true;
    error = '';
    try {
      job = (await languageApi.startImport(preview, mergeIds)).job;
      phase = 'job';
      poll();
    } catch (cause) {
      error = (cause as Error).message;
    } finally {
      busy = false;
    }
  }

  async function poll() {
    if (!job || destroyed) return;
    try {
      job = (await languageApi.importJob(job.job_id)).job;
      if (job.status === 'completed') {
        dispatch('completed');
      } else if (['queued', 'running', 'cancelling'].includes(job.status)) {
        timer = setTimeout(poll, 650);
      }
    } catch (cause) {
      error = (cause as Error).message;
    }
  }

  async function cancel() {
    if (!job) return;
    job = (await languageApi.cancelImport(job.job_id)).job;
    poll();
  }

  function toggleMerge(wordId: string) {
    mergeIds = mergeIds.includes(wordId)
      ? mergeIds.filter((value) => value !== wordId)
      : [...mergeIds, wordId];
  }

  onDestroy(() => {
    destroyed = true;
    if (timer) clearTimeout(timer);
  });
</script>

<div class="fixed inset-0 z-[116] grid place-items-center bg-black/70 p-4 backdrop-blur-sm" on:click|self={() => dispatch('close')} role="presentation">
  <section class="w-full max-w-xl rounded-3xl border border-amber-300/15 bg-[#121116] p-5 shadow-2xl">
    <header class="flex items-start justify-between gap-4">
      <div><p class="text-[10px] font-bold uppercase tracking-[0.22em] text-amber-300">Read-only Anki mirror</p><h2 class="mt-1 text-xl font-bold text-white">{phase === 'job' ? 'Mirroring your words' : 'Connect Languages'}</h2></div>
      <button type="button" class="grid h-9 w-9 place-items-center rounded-full text-white/45 hover:bg-white/7" on:click={() => dispatch('close')} aria-label="Close Anki mirror">✕</button>
    </header>

    {#if phase === 'probe'}
      <p class="mt-5 text-sm leading-6 text-white/45">Open Anki with AnkiConnect running. Keivotos will make an explicit loopback probe and import nothing.</p>
      <button type="button" class="sync-primary mt-6" on:click={probe} disabled={busy}>{busy ? 'Probing…' : 'Probe AnkiConnect'}</button>
    {:else if phase === 'scope'}
      <p class="mt-4 text-xs text-emerald-200/70">{message}</p>
      <label class="mt-5 block"><span class="mb-1 block text-[10px] uppercase text-white/30">Deck scope</span>
        {#if decks.length}<select class="sync-input" bind:value={deck}>{#each decks as value}<option value={value}>{value}</option>{/each}</select>{:else}<input class="sync-input" bind:value={deck} />{/if}
      </label>
      <button type="button" class="sync-primary mt-4" on:click={buildPreview} disabled={busy || !deck.trim()}>{busy ? 'Reading…' : 'Preview changes'}</button>
    {:else if phase === 'preview' && preview}
      <div class="mt-5 rounded-2xl border border-white/8 bg-black/20 p-4">
        <strong class="text-2xl text-amber-100">{preview.note_count.toLocaleString()}</strong><span class="ml-2 text-sm text-white/40">notes found</span>
        <p class="mt-1 text-xs text-white/30">{preview.note_types.join(', ') || 'No note types'}</p>
      </div>
      {#if !profileConfirmed}
        {#if preview.proposed_profiles.length && !unmappedNoteTypes.length}
          <button type="button" class="sync-secondary mt-4" on:click={confirmProfile} disabled={busy}>Confirm proposed field mapping</button>
        {:else}
          <p class="mt-4 rounded-xl border border-amber-300/15 bg-amber-300/5 px-3 py-2 text-xs leading-5 text-amber-100/70">
            No safe automatic mapping is available for {unmappedNoteTypes.join(', ') || preview.note_types.join(', ')}. Configure that note type in Languages Settings, then build a fresh preview.
          </p>
        {/if}
      {:else}<p class="mt-4 text-xs text-emerald-200/70">Field mapping confirmed.</p>{/if}
      {#if preview.duplicates.length}
        <div class="mt-4 space-y-2 border-t border-white/8 pt-4">
          <p class="text-xs font-semibold text-white/55">Possible manual duplicates</p>
          {#each preview.duplicates as duplicate}<label class="flex gap-2 text-xs text-white/45"><input type="checkbox" checked={mergeIds.includes(duplicate.manual_word_id)} on:change={() => toggleMerge(duplicate.manual_word_id)} />Merge “{duplicate.headword}” while preserving authored values</label>{/each}
        </div>
      {/if}
      <p class="mt-4 text-xs leading-5 text-white/30">This copies media create-only and refreshes local card progress. It never changes Anki.</p>
      <button type="button" class="sync-primary mt-4" on:click={start} disabled={busy || !profileConfirmed}>Start mirror</button>
    {:else if phase === 'job' && job}
      <div class="mt-6">
        <div class="flex justify-between text-sm"><span class="capitalize text-white/65">{job.phase}</span><span class="text-white/35">{Math.round(job.progress * 100)}%</span></div>
        <div class="mt-3 h-2 overflow-hidden rounded-full bg-white/8"><div class="h-full rounded-full bg-amber-300 transition-all" style={`width:${job.progress * 100}%`}></div></div>
        <p class="mt-3 text-xs text-white/30">{job.processed} / {job.total} notes · {job.counts.media ?? 0} media copied</p>
        {#if job.status === 'completed'}<p class="mt-4 text-sm text-emerald-200">Mirror complete.</p><button type="button" class="sync-primary mt-4" on:click={() => dispatch('close')}>Done</button>
        {:else if ['queued','running','cancelling'].includes(job.status)}<button type="button" class="sync-secondary mt-4" on:click={cancel}>Cancel cooperatively</button>{/if}
        {#if job.error}<p class="mt-4 text-xs text-red-300">{job.error}</p>{/if}
      </div>
    {/if}
    {#if error}<p class="mt-4 rounded-xl border border-red-400/15 bg-red-400/7 px-3 py-2 text-xs text-red-200">{error}</p>{/if}
  </section>
</div>

<style>
  .sync-input { width:100%; border:1px solid rgba(255,255,255,.1); border-radius:.75rem; background:rgba(0,0,0,.22); padding:.7rem .8rem; color:white; font-size:.8rem; outline:none; }
  .sync-primary,.sync-secondary { width:100%; border-radius:.8rem; padding:.75rem 1rem; font-size:.8rem; font-weight:700; }
  .sync-primary { background:rgb(252 211 77); color:#251a05; }
  .sync-secondary { border:1px solid rgba(251,191,36,.25); color:rgb(254 243 199); }
  button:disabled { opacity:.4; }
</style>
