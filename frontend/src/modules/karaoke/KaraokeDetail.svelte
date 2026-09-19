<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import KaraokePlayer from './KaraokePlayer.svelte';
  import {
    karaokeApi,
    type KaraokeItem,
    type KaraokePlaylist,
    type PlaybackState,
  } from '../../lib/karaokeApi';
  import { activeModule, filesNavigationRequest } from '../../lib/stores';
  import type { MediaProgress } from '../../lib/media';

  export let item: KaraokeItem;
  export let playlists: KaraokePlaylist[] = [];
  export let queue: KaraokeItem[] = [];

  const dispatch = createEventDispatcher<{
    close: void;
    changed: KaraokeItem;
    previous: void;
    next: void;
    shuffle: void;
    select: string;
    playlists: KaraokePlaylist[];
  }>();

  let playing = false;
  let favoriteBusy = false;
  let playlistOpen = false;
  let newPlaylistName = '';
  let attaching = false;
  let error = '';
  let performanceMode = false;
  let showTranslations = true;

  const categoryLabels: Record<string, string> = {
    series: 'Series',
    languages: 'Languages',
    singers: 'Sung by',
    songwriters: 'Composed by',
    creators: 'Created by',
    karaoke_authors: 'Karaoke created by',
    video_content: 'Video content',
    origins: 'Origin',
    platforms: 'Platforms',
    groups: 'Group',
    collections: 'Collection',
    franchises: 'Franchise',
    source: 'Source',
  };

  const categoryColors: Record<string, string> = {
    series: 'bg-emerald-600',
    languages: 'bg-emerald-600',
    singers: 'bg-amber-600',
    songwriters: 'bg-orange-600',
    creators: 'bg-fuchsia-700',
    karaoke_authors: 'bg-fuchsia-700',
    video_content: 'bg-blue-600',
    origins: 'bg-blue-600',
    platforms: 'bg-blue-600',
    groups: 'bg-neutral-900',
    collections: 'bg-slate-500/20 text-slate-100',
    franchises: 'bg-emerald-600',
    source: 'bg-cyan-700',
  };

  $: posterUrl = item.thumbnail
    ? karaokeApi.mediaUrl(item.item_id, item.thumbnail)
    : null;

  function duration(value: number | null): string {
    if (!value) return 'Unknown duration';
    const seconds = Math.round(value);
    const minutes = Math.floor(seconds / 60);
    const remainder = seconds % 60;
    return `${minutes} minute${minutes === 1 ? '' : 's'} ${remainder} second${remainder === 1 ? '' : 's'}`;
  }

  function date(value: string): string {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
  }

  async function toggleFavorite() {
    if (favoriteBusy) return;
    favoriteBusy = true;
    error = '';
    const previous = item.favorite;
    item = { ...item, favorite: !previous };
    dispatch('changed', item);
    try {
      await karaokeApi.favorite(item.item_id, !previous);
    } catch (cause) {
      item = { ...item, favorite: previous };
      dispatch('changed', item);
      error = (cause as Error).message;
    } finally {
      favoriteBusy = false;
    }
  }

  async function addToPlaylist(playlistId: number) {
    error = '';
    try {
      const result = await karaokeApi.addToPlaylist(playlistId, item.item_id);
      playlists = playlists.map((playlist) =>
        playlist.playlist_id === playlistId ? result.playlist : playlist
      );
      dispatch('playlists', playlists);
      playlistOpen = false;
    } catch (cause) {
      error = (cause as Error).message;
    }
  }

  async function createPlaylist() {
    const name = newPlaylistName.trim();
    if (!name) return;
    error = '';
    try {
      const result = await karaokeApi.createPlaylist(name);
      playlists = [result.playlist, ...playlists];
      dispatch('playlists', playlists);
      newPlaylistName = '';
      await addToPlaylist(result.playlist.playlist_id);
    } catch (cause) {
      error = (cause as Error).message;
    }
  }

  async function attachLyrics(eventOrFile: Event | File) {
    const file = eventOrFile instanceof File
      ? eventOrFile
      : (eventOrFile.currentTarget as HTMLInputElement).files?.[0];
    if (!(eventOrFile instanceof File)) {
      (eventOrFile.currentTarget as HTMLInputElement).value = '';
    }
    if (!file) return;
    attaching = true;
    error = '';
    try {
      const contentBase64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onerror = () => reject(reader.error ?? new Error('Could not read subtitle'));
        reader.onload = () => {
          const value = String(reader.result ?? '');
          resolve(value.slice(value.indexOf(',') + 1));
        };
        reader.readAsDataURL(file);
      });
      const result = await karaokeApi.attachLyrics(
        item.item_id,
        file.name,
        contentBase64,
      );
      item = result.item;
      dispatch('changed', item);
    } catch (cause) {
      error = (cause as Error).message;
    } finally {
      attaching = false;
    }
  }

  async function saveProgress(
    value: MediaProgress,
  ) {
    try {
      const result = await karaokeApi.savePlayback(item.item_id, {
        // Karaoke always starts from the beginning; only player preferences
        // and completion/play-count history persist.
        position_seconds: 0,
        duration_seconds: value.duration,
        completed: value.completed ? 1 : 0,
        lyric_id: value.subtitleTrackId,
        lyric_offset_seconds: value.subtitleOffset,
        repeat_mode: value.repeatMode,
        shuffle: value.shuffle ? 1 : 0,
      } as Partial<PlaybackState> & { position_seconds: number });
      item = { ...item, playback: result.playback };
    } catch (cause) {
      console.error('Could not save karaoke playback state:', cause);
    }
  }

  async function recordPlay() {
    try {
      const result = await karaokeApi.recordPlay(item.item_id);
      item = { ...item, playback: result.playback };
      dispatch('changed', item);
    } catch (cause) {
      console.error('Could not record Karaoke play:', cause);
    }
  }

  function openInFiles() {
    filesNavigationRequest.set({
      sourceId: item.files_source_id,
      relativePath: item.files_relative_path,
      reveal: true,
    });
    activeModule.set('files');
  }
</script>

<div class="h-full min-h-0 overflow-y-auto bg-[#182225] text-white">
  <div class="sticky top-0 z-20 flex items-center gap-3 border-b border-white/10 bg-[#11191b]/95 px-4 py-3 backdrop-blur">
    <button type="button" class="grid h-10 w-10 place-items-center rounded-full hover:bg-white/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-300" on:click={() => dispatch('close')} aria-label="Back to Karaoke library">←</button>
    <span class="min-w-0 flex-1 truncate text-sm font-semibold">{item.title}</span>
    <button type="button" class="rounded-full bg-cyan-300 px-5 py-2 text-sm font-bold text-[#071619] hover:bg-cyan-200" on:click={() => playing = true}>▶ Play</button>
  </div>

  <main class="mx-auto grid w-full max-w-7xl gap-8 p-4 sm:p-7 lg:grid-cols-[minmax(0,1fr)_380px]">
    <section class="min-w-0">
      <div class="overflow-hidden rounded-3xl border border-white/10 bg-[#101719] shadow-2xl">
        <div class="relative aspect-video bg-gradient-to-br from-cyan-950 via-[#131d20] to-fuchsia-950">
          {#if posterUrl}
            <img class="h-full w-full object-cover" src={posterUrl} alt="" />
            <div class="absolute inset-0 bg-gradient-to-t from-black/80 via-black/5 to-transparent"></div>
          {/if}
          <button
            type="button"
            class="absolute inset-0 grid place-items-center focus-visible:outline focus-visible:outline-4 focus-visible:outline-cyan-300"
            on:click={() => playing = true}
            aria-label={`Play ${item.title}`}
          >
            <span class="grid h-20 w-20 place-items-center rounded-full bg-white/95 pl-1 text-3xl text-black shadow-2xl transition hover:scale-105">▶</span>
          </button>
          <div class="absolute bottom-5 left-5 right-5">
            <div class="flex flex-wrap gap-2">
              <span class="rounded-full bg-black/55 px-3 py-1 text-xs backdrop-blur">{item.provider === 'kara-moe' ? 'Kara.moe hardsub' : 'Local Files asset'}</span>
              {#if item.lyrics.some((track) => ['ass', 'ssa'].includes(track.format))}
                <span class="rounded-full bg-cyan-300 px-3 py-1 text-xs font-bold text-black">ASS karaoke</span>
              {:else if item.lyrics.length}
                <span class="rounded-full bg-emerald-500 px-3 py-1 text-xs font-bold text-black">Timed lyrics</span>
              {:else}
                <span class="rounded-full bg-amber-400 px-3 py-1 text-xs font-bold text-black">Video only</span>
              {/if}
            </div>
          </div>
        </div>
      </div>

      <div class="mt-7">
        <h1 class="text-3xl font-light tracking-tight sm:text-4xl">{item.title}</h1>
        {#if item.subtitle}<p class="mt-2 text-xl text-cyan-300">{item.subtitle}</p>{/if}
        {#if item.year}<p class="mt-1 text-lg text-cyan-200">{item.year}</p>{/if}

        <div class="relative mt-6 flex flex-wrap gap-3">
          <button
            type="button"
            class="rounded-lg px-5 py-3 text-sm font-semibold transition {item.favorite ? 'bg-amber-400 text-black' : 'bg-[#887715] hover:bg-[#a28d17]'}"
            on:click={toggleFavorite}
            disabled={favoriteBusy}
            aria-pressed={item.favorite}
          >★ {item.favorite ? 'In favorites' : 'Add to favorites'}</button>
          <button type="button" class="rounded-lg bg-blue-600 px-5 py-3 text-sm font-semibold hover:bg-blue-500" on:click={() => playlistOpen = !playlistOpen} aria-expanded={playlistOpen}>☷ Add to playlist</button>
          <label class="cursor-pointer rounded-lg border border-white/15 px-5 py-3 text-sm font-semibold hover:bg-white/5">
            {attaching ? 'Attaching…' : '＋ Attach lyrics'}
            <input class="sr-only" type="file" accept=".ass,.ssa,.srt,.vtt,.lrc,text/plain" on:change={attachLyrics} disabled={attaching} />
          </label>
          <button type="button" class="rounded-lg border border-white/15 px-5 py-3 text-sm font-semibold hover:bg-white/5" on:click={openInFiles}>Open in Files</button>
          <button type="button" class="rounded-lg border px-5 py-3 text-sm font-semibold {performanceMode ? 'border-cyan-300/40 bg-cyan-300/10 text-cyan-100' : 'border-white/15 hover:bg-white/5'}" aria-pressed={performanceMode} on:click={() => performanceMode = !performanceMode}>Performance mode</button>
          <button type="button" class="rounded-lg border px-5 py-3 text-sm font-semibold {showTranslations ? 'border-fuchsia-300/30 bg-fuchsia-300/8 text-fuchsia-100' : 'border-white/15 text-white/55 hover:bg-white/5'}" aria-pressed={showTranslations} on:click={() => showTranslations = !showTranslations}>Translations {showTranslations ? 'on' : 'off'}</button>

          {#if playlistOpen}
            <div class="absolute left-0 top-full z-30 mt-2 w-[min(360px,90vw)] rounded-2xl border border-white/10 bg-[#101719] p-3 shadow-2xl">
              {#if playlists.length}
                <div class="max-h-52 overflow-y-auto">
                  {#each playlists as playlist}
                    <button type="button" class="flex w-full items-center justify-between rounded-xl px-3 py-3 text-left text-sm hover:bg-white/7" on:click={() => addToPlaylist(playlist.playlist_id)}>
                      <span>{playlist.name}</span>
                      <span class="text-xs text-white/35">{playlist.items.length}</span>
                    </button>
                  {/each}
                </div>
              {/if}
              <form class="mt-2 flex gap-2 border-t border-white/10 pt-3" on:submit|preventDefault={createPlaylist}>
                <input class="min-w-0 flex-1 rounded-lg bg-white/7 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-cyan-300" bind:value={newPlaylistName} placeholder="New playlist" maxlength="120" />
                <button type="submit" class="rounded-lg bg-cyan-300 px-3 text-sm font-bold text-black">Create</button>
              </form>
            </div>
          {/if}
        </div>

        {#if error}<p class="mt-4 rounded-xl border border-red-400/25 bg-red-400/10 p-3 text-sm text-red-100">{error}</p>{/if}

        <div class="mt-7 border-t border-white/15">
          <div class="grid gap-3 border-b border-white/15 py-3 text-sm sm:grid-cols-2">
            <span>◷ {duration(item.duration)}</span>
            <span>Created locally: {date(item.added_at)}</span>
          </div>
          {#each Object.entries(item.tags) as [category, values]}
            {#if values.length}
              <div class="grid gap-3 border-b border-white/15 py-3 sm:grid-cols-[250px_1fr] sm:items-center">
                <span class="text-sm font-medium text-white/85">{categoryLabels[category] ?? category.replaceAll('_', ' ')}</span>
                <div class="flex flex-wrap gap-2">
                  {#each values as value}
                    <span class="rounded-lg px-3 py-2 text-sm {categoryColors[category] ?? 'bg-slate-700'}">{value}</span>
                  {/each}
                </div>
              </div>
            {/if}
          {/each}
        </div>
      </div>
    </section>

    <aside class="space-y-4">
      <section class="rounded-2xl border border-white/10 bg-[#101719] p-5">
        <h2 class="font-semibold">Local artifacts</h2>
        <dl class="mt-4 space-y-3 text-sm">
          <div><dt class="text-white/40">Video</dt><dd class="mt-1 break-all text-white/75">{item.primary_video}</dd></div>
          <div><dt class="text-white/40">SHA-256</dt><dd class="mt-1 break-all font-mono text-xs text-white/55">{item.primary_sha256}</dd></div>
          <div><dt class="text-white/40">Source receipt</dt><dd class="mt-1 break-all text-white/75">{item.receipt_path}</dd></div>
        </dl>
      </section>
      <section class="rounded-2xl border border-white/10 bg-[#101719] p-5">
        <h2 class="font-semibold">Playback history</h2>
        <div class="mt-4 grid grid-cols-2 gap-3">
          <div class="rounded-xl bg-white/5 p-3"><div class="text-[10px] uppercase tracking-wider text-white/35">Play count</div><div class="mt-1 text-2xl font-bold text-cyan-100">{item.playback?.play_count ?? 0}</div></div>
          <div class="rounded-xl bg-white/5 p-3"><div class="text-[10px] uppercase tracking-wider text-white/35">Completed</div><div class="mt-1 text-sm font-semibold text-white/75">{item.playback?.completed ? 'Yes' : 'Not yet'}</div></div>
        </div>
        <p class="mt-3 text-xs leading-relaxed text-white/40">{item.playback?.last_played_at ? `Last played ${date(item.playback.last_played_at)}` : 'Not played in Keivotos yet.'}</p>
      </section>
      <section class="rounded-2xl border border-white/10 bg-[#101719] p-5">
        <div class="flex items-center justify-between">
          <h2 class="font-semibold">Lyrics tracks</h2>
          <span class="text-xs text-white/35">{item.lyrics.length}</span>
        </div>
        {#if item.lyrics.length}
          <div class="mt-3 space-y-2">
            {#each item.lyrics as track}
              <div class="rounded-xl bg-white/5 p-3">
                <div class="flex items-center justify-between gap-3">
                  <span class="truncate text-sm">{track.label}</span>
                  <span class="rounded bg-white/10 px-2 py-1 text-[10px] font-bold">{track.format.toUpperCase()}</span>
                </div>
                <p class="mt-1 text-xs text-white/35">{track.source_kind} · {track.cues.length} cues</p>
              </div>
            {/each}
          </div>
        {:else}
          <p class="mt-3 text-sm leading-6 text-white/45">This item is playable, but it needs a local subtitle before the interactive lyrics drawer can follow it.</p>
        {/if}
      </section>
    </aside>
  </main>
</div>

{#if playing}
  <KaraokePlayer
    {item}
    {queue}
    {performanceMode}
    {showTranslations}
    on:close={() => playing = false}
    on:previous={() => dispatch('previous')}
    on:next={() => dispatch('next')}
    on:shuffle={() => dispatch('shuffle')}
    on:select={(event) => dispatch('select', event.detail)}
    on:progress={(event) => saveProgress(event.detail)}
    on:attach={(event) => attachLyrics(event.detail)}
    on:started={recordPlay}
  />
{/if}
