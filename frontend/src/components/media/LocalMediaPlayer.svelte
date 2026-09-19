<script lang="ts">
  import { createEventDispatcher, onDestroy, onMount, tick } from 'svelte';
  import type JASSUBType from 'jassub';
  import type {
    MediaAudioOption,
    MediaProgress,
    MediaQueueItem,
    MediaSourceOption,
    MinimizeDetail,
    SubtitleCue,
    SubtitleTrack,
  } from '../../lib/media';
  import { miniPlayerState } from '../../lib/stores';
  import LyricsPanel from './LyricsPanel.svelte';

  export let src: string;
  export let title: string;
  export let subtitle = '';
  export let poster: string | null = null;
  export let tracks: SubtitleTrack[] = [];
  export let initialPosition = 0;
  export let initialTrackId: string | null = null;
  export let initialOffset = 0;
  export let initialRepeatMode: 'off' | 'all' | 'one' = 'off';
  export let initialShuffle = false;
  export let qualityLabel = '';
  export let sourceOptions: MediaSourceOption[] = [];
  export let audioOptions: MediaAudioOption[] = [];
  export let hasPrevious = false;
  export let hasNext = false;
  export let queueItems: MediaQueueItem[] = [];
  export let currentItemId = '';
  export let accent = '#67e8f9';
  export let appName = 'Keivotos';
  export let backLabel = 'Back';
  export let panelLabel = 'Subtitles & lyrics';
  export let panelComponent: typeof LyricsPanel | null = LyricsPanel;
  export let allowSubtitleAttach = false;
  export let performanceMode = false;
  export let showTranslations = true;
  export let showCenterControls = true;
  export let showDarkenOverlay = true;
  export let controlRevealMode: 'click' | 'pointer' = 'click';

  const dispatch = createEventDispatcher<{
    close: void;
    minimize: MinimizeDetail;
    previous: void;

    next: void;
    shuffle: void;
    select: string;
    progress: MediaProgress;
    attach: File;
    started: void;
  }>();

  type NativeAudioTrack = { id?: string; label?: string; language?: string; enabled: boolean };
  type VideoWithAudioTracks = HTMLVideoElement & {
    audioTracks?: { length: number; [index: number]: NativeAudioTrack };
  };

  let player: HTMLDivElement;
  let video: HTMLVideoElement;
  let controlsVisible = true;
  let playing = false;
  let buffering = false;
  let duration = 0;
  let currentTime = 0;
  let buffered = 0;
  let volume = 1;
  let muted = false;
  let speed = 1;
  let selectedTrackId: string | null = initialTrackId ?? tracks[0]?.track_id ?? null;
  let subtitleOffset = initialOffset;
  let panelOpen = false;
  let queueOpen = false;
  let settingsOpen = false;
  let repeatMode: 'off' | 'all' | 'one' = initialRepeatMode;
  let shuffle = initialShuffle;
  let hideTimer: ReturnType<typeof setTimeout> | null = null;
  let progressTimer: ReturnType<typeof setInterval> | null = null;
  let assRenderer: JASSUBType | null = null;
  let rendererKey = '';
  let initialized = false;
  let mediaError = '';
  let selectedSourceId = '';
  let detectedAudioOptions: MediaAudioOption[] = [];
  let selectedAudioId = '';
  let pendingSourcePosition: number | null = null;
  let resumeAfterSourceChange = false;
  let loopCue: SubtitleCue | null = null;
  let startedEmitted = false;
  const originalCueTimes = new WeakMap<TextTrackCue, { start: number; end: number }>();

  $: allSources = sourceOptions.length
    ? sourceOptions
    : [{ id: 'primary', label: qualityLabel || 'Original', src }];
  $: if (!selectedSourceId || !allSources.some((option) => option.id === selectedSourceId)) {
    selectedSourceId = allSources.find((option) => option.src === src)?.id ?? allSources[0]?.id ?? '';
  }
  $: activeSource = allSources.find((option) => option.id === selectedSourceId) ?? allSources[0];
  $: activeSrc = activeSource?.src ?? src;
  $: selectedTrack = selectedTrackId !== null
    ? (tracks.find((track) => track.track_id === selectedTrackId) ?? tracks[0] ?? null)
    : null;
  $: if (tracks.length && selectedTrackId !== null && !tracks.some((track) => track.track_id === selectedTrackId)) {
    selectedTrackId = tracks[0].track_id;
  }
  $: if (video && selectedTrack) void syncSubtitleRenderer(selectedTrack);
  $: if (video && !selectedTrack) void destroyAssRenderer();
  $: visibleAudioOptions = audioOptions.length ? audioOptions : detectedAudioOptions;

  onMount(() => {
    miniPlayerState.set(null);
    player.focus();
    progressTimer = setInterval(() => emitProgress(false), 10_000);
    if ('mediaSession' in navigator) {
      navigator.mediaSession.metadata = new MediaMetadata({
        title,
        artist: subtitle || appName,
      });
      navigator.mediaSession.setActionHandler('play', () => void play());
      navigator.mediaSession.setActionHandler('pause', pause);
      navigator.mediaSession.setActionHandler('seekbackward', () => seekBy(-10));
      navigator.mediaSession.setActionHandler('seekforward', () => seekBy(10));
      navigator.mediaSession.setActionHandler('previoustrack', () => dispatch('previous'));
      navigator.mediaSession.setActionHandler('nexttrack', () => dispatch('next'));
    }
  });

  onDestroy(() => {
    clearHideTimer();
    if (progressTimer) clearInterval(progressTimer);
    emitProgress(false);
    void destroyAssRenderer();
    if ('mediaSession' in navigator) {
      for (const action of ['play', 'pause', 'seekbackward', 'seekforward', 'previoustrack', 'nexttrack'] as MediaSessionAction[]) {
        try {
          navigator.mediaSession.setActionHandler(action, null);
        } catch {
          // Unsupported Media Session action.
        }
      }
    }
  });

  async function syncSubtitleRenderer(track: SubtitleTrack): Promise<void> {
    const nextKey = `${track.track_id}:${track.sha256 ?? track.url}`;
    if (!video || rendererKey === nextKey) {
      if (assRenderer) assRenderer.timeOffset = subtitleOffset;
      return;
    }
    await destroyAssRenderer();
    rendererKey = nextKey;
    if (!['ass', 'ssa'].includes(track.format.toLowerCase())) return;
    try {
      const { default: JASSUB } = await import('jassub');
      assRenderer = new JASSUB({
        video,
        subUrl: track.url,
        queryFonts: 'local',
        timeOffset: subtitleOffset,
      });
      await assRenderer.ready;
    } catch (cause) {
      console.error('ASS subtitle renderer failed:', cause);
      assRenderer = null;
    }
  }

  async function destroyAssRenderer(): Promise<void> {
    const renderer = assRenderer;
    assRenderer = null;
    rendererKey = '';
    if (renderer) await renderer.destroy();
  }

  function loadedMetadata(): void {
    duration = Number.isFinite(video.duration) ? video.duration : 0;
    const requestedPosition = pendingSourcePosition ?? (!initialized ? initialPosition : null);
    if (requestedPosition !== null) {
      video.currentTime = Math.min(
        Math.max(requestedPosition, 0),
        Math.max(duration - 0.1, 0),
      );
      pendingSourcePosition = null;
      initialized = true;
    }
    updateTime();
    detectNativeAudioTracks();
    syncNativeTracks();
    if (resumeAfterSourceChange) {
      resumeAfterSourceChange = false;
      void play();
    }
  }

  function updateTime(): void {
    currentTime = video.currentTime || 0;
    duration = Number.isFinite(video.duration) ? video.duration : duration;
    if (video.buffered.length) buffered = video.buffered.end(video.buffered.length - 1);
    if (loopCue && currentTime + subtitleOffset >= loopCue.end) {
      seekTo(Math.max(0, loopCue.start - subtitleOffset));
      if (video.paused) void play();
    }
  }

  async function play(): Promise<void> {
    try {
      await video.play();
    } catch (cause) {
      console.error('Local media playback failed:', cause);
    }
  }

  function pause(): void {
    video.pause();
  }

  function togglePlay(): void {
    if (video.paused) void play();
    else pause();
  }

  function seekBy(seconds: number): void {
    video.currentTime = Math.max(
      0,
      Math.min(duration || video.duration || 0, video.currentTime + seconds),
    );
    updateTime();
  }

  function seekTo(seconds: number): void {
    video.currentTime = Math.max(0, Math.min(duration || video.duration || 0, seconds));
    updateTime();
  }

  function setProgress(event: Event): void {
    seekTo(Number((event.currentTarget as HTMLInputElement).value));
  }

  function setVolume(event: Event): void {
    volume = Number((event.currentTarget as HTMLInputElement).value);
    video.volume = volume;
    muted = volume === 0;
    video.muted = muted;
  }

  function toggleMute(): void {
    muted = !muted;
    video.muted = muted;
  }

  function setSpeed(value: number): void {
    speed = value;
    video.playbackRate = value;
  }

  function setSubtitleTrack(id: string): void {
    selectedTrackId = id || null;
    rendererKey = '';
    queueMicrotask(syncNativeTracks);
    emitProgress(false);
  }

  function setSubtitleOffset(value: number): void {
    subtitleOffset = value;
    if (assRenderer) assRenderer.timeOffset = value;
    syncNativeTracks();
    emitProgress(false);
  }

  function stageClick(event: MouseEvent): void {
    const target = event.target as HTMLElement;
    if (target.closest('button, input, select, a, label, [data-player-control-stop]')) return;
    if (controlsVisible) {
      clearHideTimer();
      controlsVisible = false;
    } else {
      revealControls();
    }
  }

  function pointerMoved(): void {
    if (controlRevealMode === 'pointer') revealControls();
  }

  function overlayStateChanged(): void {
    controlsVisible = true;
    if (panelOpen || queueOpen || settingsOpen) {
      clearHideTimer();
    } else {
      scheduleHide();
    }
  }

  function togglePanel(): void {
    panelOpen = !panelOpen;
    queueOpen = false;
    overlayStateChanged();
  }

  function toggleQueue(): void {
    queueOpen = !queueOpen;
    panelOpen = false;
    overlayStateChanged();
  }

  function toggleSettings(): void {
    settingsOpen = !settingsOpen;
    overlayStateChanged();
  }

  function syncNativeTracks(): void {
    if (!video) return;
    const trackElements = Array.from(video.querySelectorAll<HTMLTrackElement>('track[data-track-id]'));
    for (const element of trackElements) {
      const trackId = element.dataset.trackId ?? '';
      const nativeTrack = element.track;
      nativeTrack.mode = trackId === selectedTrackId ? 'showing' : 'disabled';
      if (!nativeTrack.cues) continue;
      for (const cue of Array.from(nativeTrack.cues)) {
        let original = originalCueTimes.get(cue);
        if (!original) {
          original = { start: cue.startTime, end: cue.endTime };
          originalCueTimes.set(cue, original);
        }
        cue.startTime = Math.max(0, original.start - subtitleOffset);
        cue.endTime = Math.max(cue.startTime + 0.01, original.end - subtitleOffset);
      }
    }
  }

  function detectNativeAudioTracks(): void {
    const nativeTracks = (video as VideoWithAudioTracks).audioTracks;
    if (!nativeTracks?.length) {
      detectedAudioOptions = [];
      return;
    }
    detectedAudioOptions = Array.from({ length: nativeTracks.length }, (_, index) => {
      const track = nativeTracks[index];
      return {
        id: track.id || String(index),
        label: track.label || track.language || `Audio ${index + 1}`,
        language: track.language,
      };
    });
    const activeIndex = Array.from({ length: nativeTracks.length }, (_, index) => index)
      .find((index) => nativeTracks[index].enabled) ?? 0;
    selectedAudioId = detectedAudioOptions[activeIndex]?.id ?? '';
  }

  function setAudioTrack(id: string): void {
    const nativeTracks = (video as VideoWithAudioTracks).audioTracks;
    if (!nativeTracks?.length) return;
    const index = visibleAudioOptions.findIndex((option) => option.id === id);
    if (index < 0 || index >= nativeTracks.length) return;
    for (let position = 0; position < nativeTracks.length; position += 1) {
      nativeTracks[position].enabled = position === index;
    }
    selectedAudioId = id;
  }

  async function setSource(id: string): Promise<void> {
    if (id === selectedSourceId) return;
    pendingSourcePosition = video.currentTime || 0;
    resumeAfterSourceChange = !video.paused;
    selectedSourceId = id;
    mediaError = '';
    await tick();
    video.load();
  }

  function nextTrack(): void {
    dispatch(shuffle && (hasPrevious || hasNext) ? 'shuffle' : 'next');
  }

  function clearHideTimer(): void {
    if (hideTimer) clearTimeout(hideTimer);
    hideTimer = null;
  }

  function revealControls(): void {
    controlsVisible = true;
    scheduleHide();
  }

  function scheduleHide(): void {
    clearHideTimer();
    if (playing && !panelOpen && !queueOpen && !settingsOpen) {
      hideTimer = setTimeout(() => {
        controlsVisible = false;
      }, 3000);
    }
  }

  function stateChanged(): void {
    playing = !video.paused;
    if (playing && !startedEmitted) {
      startedEmitted = true;
      dispatch('started');
    }
    if (!playing) controlsVisible = true;
    scheduleHide();
  }

  function playbackError(): void {
    const code = video?.error?.code;
    mediaError = code
      ? `This local media could not be played (media error ${code}).`
      : 'This local media could not be played.';
    controlsVisible = true;
  }

  function ended(): void {
    playing = false;
    controlsVisible = true;
    emitProgress(true);
    if (repeatMode === 'one') {
      video.currentTime = 0;
      void play();
    } else if (shuffle && (hasPrevious || hasNext)) {
      dispatch('shuffle');
    } else if (hasNext || repeatMode === 'all') {
      dispatch('next');
    }
  }

  function emitProgress(completed: boolean): void {
    if (!video) return;
    dispatch('progress', {
      position: video.currentTime || 0,
      duration: Number.isFinite(video.duration) ? video.duration : 0,
      completed,
      subtitleTrackId: selectedTrackId,
      subtitleOffset,
      repeatMode,
      shuffle,
    });
  }

  function cycleRepeat(): void {
    repeatMode = repeatMode === 'off' ? 'all' : repeatMode === 'all' ? 'one' : 'off';
    emitProgress(false);
  }

  async function toggleFullscreen(): Promise<void> {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await player.requestFullscreen();
  }

  async function togglePictureInPicture(): Promise<void> {
    if (!document.pictureInPictureEnabled || video.disablePictureInPicture) return;
    if (document.pictureInPictureElement) await document.exitPictureInPicture();
    else await video.requestPictureInPicture();
  }

  function attachSubtitle(event: Event): void {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (file) dispatch('attach', file);
  }

  function keydown(event: KeyboardEvent): void {
    const target = event.target as HTMLElement;
    if (['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON'].includes(target.tagName)) return;
    const key = event.key.toLowerCase();
    if (/^[0-9]$/.test(key)) {
      seekTo((duration || 0) * Number(key) / 10);
      event.preventDefault();
      return;
    }
    const actions: Record<string, () => void> = {
      ' ': togglePlay,
      k: togglePlay,
      j: () => seekBy(-10),
      l: () => seekBy(10),
      arrowleft: () => seekBy(-5),
      arrowright: () => seekBy(5),
      m: toggleMute,
      c: togglePanel,
      f: () => void toggleFullscreen(),
      '>': () => setSpeed(Math.min(2, speed + 0.25)),
      '<': () => setSpeed(Math.max(0.25, speed - 0.25)),
      escape: () => {
        if (document.fullscreenElement) void document.exitFullscreen();
        else if (settingsOpen) {
          settingsOpen = false;
          overlayStateChanged();
        } else if (queueOpen) {
          queueOpen = false;
          overlayStateChanged();
        } else if (panelOpen) {
          panelOpen = false;
          overlayStateChanged();
        }
        else if (video && !video.paused && !video.ended) {
          dispatch('minimize', { src: activeSrc, position: video.currentTime, duration: video.duration || 0 });
        } else {
          dispatch('close');
        }
      },
    };
    if (event.shiftKey && key === 'n') actions.next = () => dispatch('next');
    if (event.shiftKey && key === 'p') actions.previous = () => dispatch('previous');
    const action = actions[
      event.shiftKey && key === 'n'
        ? 'next'
        : event.shiftKey && key === 'p'
          ? 'previous'
          : key
    ];
    if (action) {
      event.preventDefault();
      action();
      revealControls();
    }
  }

  function formatTime(value: number): string {
    if (!Number.isFinite(value) || value < 0) return '0:00';
    const hours = Math.floor(value / 3600);
    const minutes = Math.floor((value % 3600) / 60);
    const seconds = Math.floor(value % 60);
    return hours
      ? `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
      : `${minutes}:${String(seconds).padStart(2, '0')}`;
  }
</script>

<!-- svelte-ignore a11y_no_noninteractive_tabindex a11y_no_noninteractive_element_interactions -->
<div
  bind:this={player}
  class="local-media-player fixed inset-0 z-[120] overflow-hidden bg-black text-white outline-none"
  role="application"
  aria-label={`Local player: ${title}`}
  tabindex="0"
  style={`--player-accent:${accent}`}
  on:click={stageClick}
  on:pointermove={pointerMoved}
  on:keydown={keydown}
>
  <!-- svelte-ignore a11y_media_has_caption -->
  <video
    bind:this={video}
    class="h-full w-full object-contain"
    src={activeSrc}
    {poster}
    playsinline
    preload="metadata"
    on:loadedmetadata={loadedMetadata}
    on:timeupdate={updateTime}
    on:progress={updateTime}
    on:play={stateChanged}
    on:pause={() => {
      stateChanged();
      emitProgress(false);
    }}
    on:waiting={() => buffering = true}
    on:playing={() => buffering = false}
    on:ended={ended}
    on:error={playbackError}
  >
    {#each tracks.filter((track) => track.format.toLowerCase() === 'vtt') as track (track.track_id)}
      <track
        kind="captions"
        src={track.url}
        srclang={track.language || 'und'}
        label={track.label}
        data-track-id={track.track_id}
        default={track.track_id === selectedTrackId}
        on:load={syncNativeTracks}
      />
    {/each}
  </video>

  {#if showDarkenOverlay}
    <div class="pointer-events-none absolute inset-0 bg-gradient-to-b from-black/60 via-transparent to-black/85 transition-opacity {controlsVisible ? 'opacity-100' : 'opacity-0'}"></div>
  {/if}

  {#if buffering}
    <div class="pointer-events-none absolute inset-0 grid place-items-center">
      <div class="buffering h-12 w-12 animate-spin rounded-full border-4 border-white/20" aria-label="Buffering"></div>
    </div>
  {/if}

  {#if mediaError}
    <div class="absolute inset-0 z-10 grid place-items-center bg-black/65 p-6">
      <div class="max-w-md rounded-2xl border border-red-300/20 bg-[#1b1013] p-5 text-center">
        <p class="font-semibold text-red-100">{mediaError}</p>
        <p class="mt-2 text-sm text-white/45">The source remains untouched. Return to the library and inspect the local file or receipt.</p>
      </div>
    </div>
  {/if}

  <div
    class="absolute inset-x-0 top-0 z-30 flex items-center gap-3 p-4 transition duration-200 {controlsVisible ? 'translate-y-0 opacity-100' : '-translate-y-4 pointer-events-none opacity-0'}"
    data-player-control-stop
  >
    <button type="button" class="player-button" on:click={() => {
      if (video && !video.paused && !video.ended) {
        dispatch('minimize', { src: activeSrc, position: video.currentTime, duration: video.duration || 0 });
      } else {
        dispatch('close');
      }
    }} aria-label={backLabel} title={backLabel}>
      <svg class="control-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M15 5l-7 7 7 7M8 12h11" /></svg>
    </button>
    {#if panelComponent}
      <button
        type="button"
        class="accent-pill flex items-center gap-2 rounded-full px-4 py-2 text-sm font-bold"
        on:click={togglePanel}
        aria-expanded={panelOpen}
      ><svg class="h-4 w-4" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M9 4v11.1A4 4 0 107 19V8l10-2v7.1A4 4 0 1019 17V2L9 4z" /></svg>{panelLabel}</button>
    {/if}
    {#if queueItems.length > 1}
      <button
        type="button"
        class="rounded-full border border-white/15 bg-black/25 px-4 py-2 text-sm font-semibold text-white/75 hover:bg-white/10"
        aria-expanded={queueOpen}
        on:click={toggleQueue}
      >Queue {queueItems.length}</button>
    {/if}
    <div class="min-w-0 flex-1">
      <h1 class="truncate text-sm font-semibold drop-shadow">{title}</h1>
      {#if subtitle}<p class="truncate text-xs text-white/55">{subtitle}</p>{/if}
    </div>
    {#if activeSource?.label}<span class="rounded-full bg-black/45 px-3 py-1 text-xs text-white/65">{activeSource.label}</span>{/if}
  </div>

  {#if showCenterControls}
    <div
      class="absolute inset-0 z-20 grid place-items-center transition duration-200 {controlsVisible ? 'scale-100 opacity-100' : 'scale-95 pointer-events-none opacity-0'}"
    >
      <div class="center-transport flex items-center gap-5" data-player-control-stop>
        <button type="button" class="center-seek" on:click={() => seekBy(-10)} aria-label="Rewind 10 seconds" title="Rewind 10 seconds (J)">
          <svg viewBox="0 0 32 32" aria-hidden="true"><path d="M10 10H4V4M5 10a12 12 0 11-1 9" /><text x="16" y="20">10</text></svg>
        </button>
        <button
          type="button"
          class="center-play grid h-20 w-20 place-items-center rounded-full bg-white/95 text-black shadow-2xl transition hover:scale-105 focus-visible:outline focus-visible:outline-4"
          on:click={togglePlay}
          aria-label={playing ? 'Pause' : 'Play'}
          title={playing ? 'Pause (K)' : 'Play (K)'}
        >
          {#if playing}
            <svg class="h-8 w-8" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M7 5h4v14H7zm6 0h4v14h-4z" /></svg>
          {:else}
            <svg class="ml-1 h-8 w-8" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M7 4l13 8-13 8z" /></svg>
          {/if}
        </button>
        <button type="button" class="center-seek" on:click={() => seekBy(10)} aria-label="Forward 10 seconds" title="Forward 10 seconds (L)">
          <svg viewBox="0 0 32 32" aria-hidden="true"><path d="M22 10h6V4m-1 6a12 12 0 10 1 9" /><text x="16" y="20">10</text></svg>
        </button>
      </div>
    </div>
  {/if}

  <div
    class="absolute inset-x-0 bottom-0 z-30 p-3 sm:p-4 transition duration-200 {controlsVisible ? 'translate-y-0 opacity-100' : 'translate-y-4 pointer-events-none opacity-0'}"
    data-player-control-stop
  >
    <div class="relative mb-2">
      <div class="pointer-events-none absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded-full bg-white/20">
        <div class="h-full rounded-full bg-white/25" style={`width:${duration ? Math.min(buffered / duration * 100, 100) : 0}%`}></div>
      </div>
      <input
        class="player-range relative z-10 h-5 w-full cursor-pointer"
        type="range"
        min="0"
        max={duration || 0}
        step="0.05"
        value={currentTime}
        aria-label="Playback position"
        on:input={setProgress}
      />
    </div>
    <div class="flex min-w-0 items-center gap-1 sm:gap-2">
      <button type="button" class="player-button disabled:opacity-25" disabled={!hasPrevious} on:click={() => dispatch('previous')} aria-label="Previous item" title="Previous">
        <svg class="control-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" stroke="none" d="M6 5h2v14H6zm3 7l10-7v14z" /></svg>
      </button>
      <button type="button" class="player-button disabled:opacity-25" disabled={!hasNext && !shuffle} on:click={nextTrack} aria-label="Next item" title="Next">
        <svg class="control-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" stroke="none" d="M16 5h2v14h-2zM5 5l10 7-10 7z" /></svg>
      </button>
      <button type="button" class="player-button" on:click={toggleMute} aria-label={muted ? 'Unmute' : 'Mute'}>
        <svg class="control-icon" viewBox="0 0 24 24" aria-hidden="true">
          <path fill="currentColor" stroke="none" d="M4 9v6h4l5 4V5L8 9H4z" />
          {#if muted}
            <path d="M16 9l5 6m0-6l-5 6" />
          {:else}
            <path d="M16 8a6 6 0 010 8m2.5-10.5a9 9 0 010 13" />
          {/if}
        </svg>
      </button>
      <input class="player-range w-16 sm:w-24" type="range" min="0" max="1" step="0.01" value={muted ? 0 : volume} aria-label="Volume" on:input={setVolume} />
      <span class="hidden text-xs tabular-nums text-white/75 min-[520px]:inline">{formatTime(currentTime)} / {formatTime(duration)}</span>
      <span class="min-w-1 flex-1"></span>
      <button
        type="button"
        class="mode-button hidden min-[460px]:flex {shuffle ? 'active' : ''}"
        disabled={!hasPrevious && !hasNext}
        on:click={() => {
          shuffle = !shuffle;
          emitProgress(false);
        }}
        aria-pressed={shuffle}
        aria-label={`Shuffle ${shuffle ? 'on' : 'off'}`}
      >
        <svg class="control-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h3c4 0 6 10 10 10h3m-3-3l3 3-3 3M4 17h3c1.5 0 2.7-1.3 3.8-3m2.4-4c1.1-1.7 2.3-3 3.8-3h3m-3-3l3 3-3 3" /></svg>
      </button>
      <button type="button" class="mode-button {repeatMode !== 'off' ? 'active' : ''}" on:click={cycleRepeat} aria-label={`Repeat ${repeatMode}`} aria-pressed={repeatMode !== 'off'}>
        <svg class="control-icon" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M17 2l4 4-4 4M3 11V9a3 3 0 013-3h15M7 22l-4-4 4-4m14-1v2a3 3 0 01-3 3H3" />
          {#if repeatMode === 'one'}<text class="repeat-one" x="18.5" y="6.5">1</text>{/if}
        </svg>
      </button>
      {#if panelComponent}
        <button type="button" class="mode-button hidden min-[560px]:flex {panelOpen ? 'active' : ''}" on:click={togglePanel} aria-label={`Toggle ${panelLabel.toLowerCase()}`} aria-pressed={panelOpen}>
          <svg class="control-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M6 10h5m-5 4h8m2-4h2m-2 4h2" /></svg>
        </button>
      {/if}
      <div class="relative">
        <button type="button" class="player-button {settingsOpen ? 'active-button' : ''}" on:click={toggleSettings} aria-label="Player settings" aria-expanded={settingsOpen}>
          <svg class="control-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 8a4 4 0 100 8 4 4 0 000-8zM4.9 7.1l-1.4-2 2.6-2.6 2 1.4a9 9 0 012.4-1V.5h3v2.4a9 9 0 012.4 1l2-1.4 2.6 2.6-1.4 2a9 9 0 011 2.4h2.4v3h-2.4a9 9 0 01-1 2.4l1.4 2-2.6 2.6-2-1.4a9 9 0 01-2.4 1v2.4h-3v-2.4a9 9 0 01-2.4-1l-2 1.4-2.6-2.6 1.4-2a9 9 0 01-1-2.4H.5v-3h2.4a9 9 0 011-2.4z" /></svg>
        </button>
        {#if settingsOpen}
          <div class="player-settings absolute bottom-14 right-0 z-50 max-h-[min(70vh,480px)] w-72 overflow-y-auto rounded-2xl border border-white/12 bg-[#11151b]/98 p-3 shadow-2xl" data-player-control-stop>
            <p class="px-2 pb-2 text-xs font-semibold uppercase tracking-wider text-white/40">Playback speed</p>
            <div class="grid grid-cols-4 gap-1">
              {#each [0.5, 0.75, 1, 1.25, 1.5, 2] as value}
                <button type="button" class="setting-choice {speed === value ? 'active' : ''}" on:click={() => setSpeed(value)}>{value}×</button>
              {/each}
            </div>
            {#if allSources.length > 1}
              <label class="mt-4 block px-2 text-xs font-semibold uppercase tracking-wider text-white/40">
                Video quality
                <select class="player-select" value={selectedSourceId} on:change={(event) => setSource(event.currentTarget.value)}>
                  {#each allSources as option}<option value={option.id}>{option.label}</option>{/each}
                </select>
              </label>
            {/if}
            {#if visibleAudioOptions.length > 1}
              <label class="mt-4 block px-2 text-xs font-semibold uppercase tracking-wider text-white/40">
                Audio
                <select class="player-select" value={selectedAudioId} on:change={(event) => setAudioTrack(event.currentTarget.value)}>
                  {#each visibleAudioOptions as option}<option value={option.id}>{option.label}</option>{/each}
                </select>
              </label>
            {/if}
            {#if tracks.length}
              <label class="mt-4 block px-2 text-xs font-semibold uppercase tracking-wider text-white/40">
                Subtitle track
                <select class="player-select" value={selectedTrackId ?? ''} on:change={(event) => setSubtitleTrack(event.currentTarget.value)}>
                  <option value="">None</option>
                  {#each tracks as track}<option value={track.track_id}>{track.label} · {track.format.toUpperCase()}</option>{/each}
                </select>
              </label>
            {/if}
            {#if allowSubtitleAttach}
              <label class="mt-4 flex cursor-pointer items-center justify-center rounded-xl border border-dashed border-white/15 px-3 py-3 text-xs font-semibold text-white/60 hover:border-white/30 hover:text-white">
                Attach subtitle or lyrics
                <input class="sr-only" type="file" accept=".ass,.ssa,.srt,.vtt,.lrc,text/plain" on:change={attachSubtitle} />
              </label>
            {/if}
            <p class="mt-3 px-2 text-[10px] leading-relaxed text-white/30">
              Controls: pointer movement reveals · background click hides · K play/pause · J/L ±10s · C text
            </p>
          </div>
        {/if}
      </div>
      <button type="button" class="player-button hidden sm:grid" on:click={togglePictureInPicture} aria-label="Picture in picture" title="Picture in picture">
        <svg class="control-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="1" /><rect x="12" y="11" width="7" height="5" rx="1" /></svg>
      </button>
      <button type="button" class="player-button" on:click={toggleFullscreen} aria-label="Fullscreen" title="Fullscreen">
        <svg class="control-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9V4h5m6 0h5v5m0 6v5h-5M9 20H4v-5" /></svg>
      </button>
    </div>
  </div>

  {#if panelOpen && panelComponent}
    <svelte:component
      this={panelComponent}
      {tracks}
      {selectedTrackId}
      {currentTime}
      {accent}
      {performanceMode}
      {showTranslations}
      {loopCue}
      title={panelLabel}
      offset={subtitleOffset}
      on:close={() => {
        panelOpen = false;
        overlayStateChanged();
      }}
      on:select={(event: CustomEvent<string>) => setSubtitleTrack(event.detail)}
      on:seek={(event: CustomEvent<number>) => seekTo(event.detail)}
      on:offset={(event: CustomEvent<number>) => setSubtitleOffset(event.detail)}
      on:loop={(event: CustomEvent<SubtitleCue | null>) => loopCue = event.detail}
    />
  {/if}

  {#if queueOpen}
    <aside class="absolute inset-y-0 right-0 z-40 flex w-[min(390px,92vw)] flex-col border-l border-white/10 bg-[#07090d]/95 shadow-2xl backdrop-blur-xl" aria-label="Playback queue" data-player-control-stop>
      <header class="flex items-center justify-between border-b border-white/10 px-4 py-4">
        <div><h2 class="text-lg font-semibold">Queue</h2><p class="text-xs text-white/45">{queueItems.length} local items</p></div>
        <button type="button" class="player-button" aria-label="Close queue" on:click={() => {
          queueOpen = false;
          overlayStateChanged();
        }}>×</button>
      </header>
      <div class="min-h-0 flex-1 overflow-y-auto p-3">
        {#each queueItems as item, index (item.id)}
          <button
            type="button"
            class="queue-item mb-1 flex w-full items-start gap-3 rounded-xl px-3 py-3 text-left {item.id === currentItemId ? 'active' : 'text-white/60 hover:bg-white/5 hover:text-white'}"
            aria-current={item.id === currentItemId ? 'true' : undefined}
            on:click={() => {
              queueOpen = false;
              overlayStateChanged();
              dispatch('select', item.id);
            }}
          >
            <span class="w-7 shrink-0 pt-0.5 text-xs tabular-nums text-white/30">{index + 1}</span>
            <span class="min-w-0"><strong class="block truncate text-sm">{item.title}</strong>{#if item.subtitle}<span class="mt-1 block truncate text-xs text-white/35">{item.subtitle}</span>{/if}</span>
          </button>
        {/each}
      </div>
    </aside>
  {/if}
</div>

<style>
  :global(.player-button) {
    display: grid;
    width: 3rem;
    height: 3rem;
    flex: 0 0 auto;
    place-items: center;
    border-radius: 9999px;
    color: rgb(255 255 255 / 0.78);
    font-size: 0.875rem;
    font-weight: 700;
    transition: background-color 150ms, color 150ms, transform 150ms;
  }

  :global(.control-icon) {
    width: 1.45rem;
    height: 1.45rem;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.8;
    stroke-linecap: round;
    stroke-linejoin: round;
  }

  .center-seek {
    display: grid;
    width: 3.75rem;
    height: 3.75rem;
    place-items: center;
    border: 1px solid rgb(255 255 255 / 0.22);
    border-radius: 9999px;
    background: rgb(0 0 0 / 0.48);
    color: white;
    box-shadow: 0 12px 36px rgb(0 0 0 / 0.35);
    transition: background-color 150ms, transform 150ms;
  }

  .center-seek:hover {
    background: rgb(255 255 255 / 0.16);
    transform: scale(1.05);
  }

  .center-seek svg {
    width: 2rem;
    height: 2rem;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.8;
    stroke-linecap: round;
    stroke-linejoin: round;
  }

  .center-seek text {
    fill: currentColor;
    stroke: none;
    font-size: 0.56rem;
    font-weight: 800;
    text-anchor: middle;
  }

  :global(.player-button:hover),
  :global(.player-button.active-button) {
    background: color-mix(in srgb, var(--player-accent) 16%, transparent);
    color: white;
  }

  :global(.player-button:focus-visible),
  .center-play:focus-visible {
    outline-color: var(--player-accent);
    outline-offset: 2px;
  }

  .accent-pill {
    background: var(--player-accent);
    color: #080b0e;
  }

  .accent-pill:hover {
    background: color-mix(in srgb, var(--player-accent) 82%, white);
    color: #050709;
  }

  .buffering {
    border-top-color: var(--player-accent);
  }

  .player-range {
    accent-color: var(--player-accent);
  }

  .mode-button {
    display: flex;
    min-width: 3rem;
    height: 3rem;
    flex: 0 0 auto;
    align-items: center;
    justify-content: center;
    border: 1px solid rgb(255 255 255 / 0.1);
    border-radius: 0.75rem;
    color: rgb(255 255 255 / 0.52);
    font-size: 0.875rem;
  }

  .repeat-one {
    fill: currentColor;
    stroke: none;
    font-size: 0.48rem;
    font-weight: 900;
    text-anchor: middle;
  }

  .mode-button.active,
  .setting-choice.active {
    border-color: color-mix(in srgb, var(--player-accent) 38%, transparent);
    background: color-mix(in srgb, var(--player-accent) 15%, transparent);
    color: color-mix(in srgb, var(--player-accent) 78%, white);
  }

  .setting-choice {
    border-radius: 0.5rem;
    background: rgb(255 255 255 / 0.05);
    padding: 0.5rem;
    font-size: 0.75rem;
  }

  .setting-choice:hover {
    background: rgb(255 255 255 / 0.1);
  }

  .player-select {
    margin-top: 0.5rem;
    width: 100%;
    border-radius: 0.55rem;
    background: rgb(255 255 255 / 0.1);
    padding: 0.55rem;
    color: white;
    font-size: 0.875rem;
    font-weight: 400;
    letter-spacing: normal;
    text-transform: none;
  }

  .queue-item.active {
    background: color-mix(in srgb, var(--player-accent) 12%, transparent);
    color: color-mix(in srgb, var(--player-accent) 75%, white);
  }

  @media (max-width: 430px) {
    :global(.player-button) {
      width: 2.65rem;
      height: 2.65rem;
    }

    .mode-button {
      min-width: 2.65rem;
      height: 2.65rem;
    }

    .center-transport {
      gap: 0.75rem;
    }

    .center-seek {
      width: 3.25rem;
      height: 3.25rem;
    }

    .player-settings {
      right: -3rem;
      width: min(18rem, calc(100vw - 1rem));
    }
  }

  @media (prefers-reduced-motion: reduce) {
    :global(.player-button),
    .center-play,
    .mode-button {
      transition: none;
    }

    :global(.local-media-player *),
    :global(.local-media-player *::before),
    :global(.local-media-player *::after) {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      scroll-behavior: auto !important;
      transition-duration: 0.01ms !important;
    }
  }
</style>
