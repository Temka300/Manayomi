<script lang="ts">
  import { miniPlayerExpandRequest, miniPlayerState, miniPlayerStyle } from '../../lib/stores';

  let video: HTMLVideoElement;
  let playing = true;
  let currentTime = 0;
  let duration = 0;
  let seekingVia: 'none' | 'scrub' = 'none';

  $: state = $miniPlayerState;
  $: style = $miniPlayerStyle;

  function togglePlay() {
    if (!video) return;
    if (video.paused) video.play().catch(() => {});
    else video.pause();
  }

  function close() {
    if (video) {
      video.pause();
      video.src = '';
    }
    miniPlayerState.set(null);
  }

  function expand() {
    if (!state || !video) return;
    miniPlayerExpandRequest.set({
      module: state.module,
      itemId: state.itemId,
      position: video.currentTime,
    });
    miniPlayerState.set(null);
  }

  function handleTimeUpdate() {
    if (seekingVia === 'none') currentTime = video.currentTime;
  }

  function handleLoadedMetadata() {
    if (state) {
      duration = video.duration || state.duration;
      video.currentTime = state.position;
      video.play().catch(() => {});
    }
  }

  function scrubStart(event: PointerEvent) {
    seekingVia = 'scrub';
    const bar = event.currentTarget as HTMLElement;
    bar.setPointerCapture(event.pointerId);
    scrubMove(event);
  }

  function scrubMove(event: PointerEvent) {
    if (seekingVia !== 'scrub') return;
    const bar = event.currentTarget as HTMLElement;
    const rect = bar.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
    currentTime = ratio * duration;
  }

  function scrubEnd() {
    if (seekingVia !== 'scrub') return;
    if (video) video.currentTime = currentTime;
    seekingVia = 'none';
  }

  function formatTime(value: number): string {
    if (!Number.isFinite(value) || value < 0) return '0:00';
    const minutes = Math.floor(value / 60);
    const seconds = Math.floor(value % 60);
    return `${minutes}:${String(seconds).padStart(2, '0')}`;
  }

  $: progress = duration > 0 ? (currentTime / duration) * 100 : 0;
  $: accentColor = state?.accent ?? '#67e8f9';
</script>

{#if state}
  {#if style === 'card'}
    <!-- Card style: floating video window -->
    <div class="fixed bottom-4 right-4 z-[110] w-80 overflow-hidden rounded-xl shadow-2xl" style="background:#0a0a0f; border:1px solid rgba(255,255,255,0.08);">
      <!-- Video area -->
      <div class="relative aspect-video w-full bg-black">
        <!-- svelte-ignore a11y_media_has_caption -->
        <video
          bind:this={video}
          class="h-full w-full object-contain"
          src={state.src}
          on:timeupdate={handleTimeUpdate}
          on:loadedmetadata={handleLoadedMetadata}
          on:play={() => playing = true}
          on:pause={() => playing = false}
          on:ended={close}
        ></video>

        <!-- Overlay controls -->
        <div class="absolute inset-0 flex items-center justify-center bg-black/0 transition-colors hover:bg-black/30" role="group">
          <!-- Expand (top-left) -->
          <button
            type="button"
            class="absolute left-2 top-2 grid h-8 w-8 place-items-center rounded-md bg-black/50 text-white/80 transition-colors hover:bg-black/70 hover:text-white"
            title="Expand to full player"
            aria-label="Expand to full player"
            on:click={expand}
          >
            <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" /></svg>
          </button>

          <!-- Close (top-right) -->
          <button
            type="button"
            class="absolute right-2 top-2 grid h-8 w-8 place-items-center rounded-md bg-black/50 text-white/80 transition-colors hover:bg-black/70 hover:text-white"
            title="Close mini player"
            aria-label="Close mini player"
            on:click={close}
          >
            <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12" /></svg>
          </button>

          <!-- Center play/pause -->
          <button
            type="button"
            class="grid h-10 w-10 place-items-center rounded-full bg-black/50 text-white opacity-0 transition-opacity hover:bg-black/70 [div:hover>&]:opacity-100"
            title={playing ? 'Pause' : 'Play'}
            aria-label={playing ? 'Pause' : 'Play'}
            on:click={togglePlay}
          >
            {#if playing}
              <svg class="h-6 w-6" viewBox="0 0 24 24" fill="currentColor"><path d="M6 4h4v16H6zM14 4h4v16h-4z" /></svg>
            {:else}
              <svg class="h-6 w-6" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>
            {/if}
          </button>

          <!-- Progress bar at bottom of video -->
          <div
            class="absolute inset-x-0 bottom-0 flex h-6 cursor-pointer items-end"
            role="slider"
            aria-label="Seek"
            aria-valuemin={0}
            aria-valuemax={duration}
            aria-valuenow={currentTime}
            tabindex="0"
            on:pointerdown={scrubStart}
            on:pointermove={scrubMove}
            on:pointerup={scrubEnd}
            on:lostpointercapture={scrubEnd}
          >
            <div class="h-1 w-full bg-white/20 transition-[height] [div:hover>&]:h-1.5">
              <div class="h-full transition-none" style="width:{progress}%;background:{accentColor}"></div>
            </div>
          </div>

          <!-- Time overlay -->
          <div class="pointer-events-none absolute bottom-1.5 left-2 text-[11px] font-medium text-white/80 drop-shadow">{formatTime(currentTime)} / {formatTime(duration)}</div>
        </div>
      </div>

      <!-- Title bar -->
      <div class="px-3 py-2" style="background:{accentColor}18;">
        <div class="truncate text-sm font-semibold" style="color:{accentColor};">{state.title}</div>
        <div class="truncate text-xs" style="color: var(--text-muted, #6b6b80);">{state.subtitle}</div>
      </div>
    </div>
  {:else}
    <!-- Bar style: full-width bottom bar -->
    <div
      class="fixed inset-x-0 bottom-0 z-[110] flex items-center gap-3 border-t px-3 py-2"
      style="background: var(--bg-elevated, #111118); border-color: var(--border-default, #292938);"
    >
      <!-- Progress bar (scrubable) -->
      <div
        class="absolute inset-x-0 top-0 h-1 cursor-pointer"
        style="background: var(--bg-base, #0d0d13);"
        role="slider"
        aria-label="Seek"
        aria-valuemin={0}
        aria-valuemax={duration}
        aria-valuenow={currentTime}
        tabindex="0"
        on:pointerdown={scrubStart}
        on:pointermove={scrubMove}
        on:pointerup={scrubEnd}
        on:lostpointercapture={scrubEnd}
      >
        <div class="h-full transition-none" style="width:{progress}%;background:{accentColor}"></div>
      </div>

      <!-- svelte-ignore a11y_media_has_caption -->
      <video
        bind:this={video}
        class="hidden"
        src={state.src}
        on:timeupdate={handleTimeUpdate}
        on:loadedmetadata={handleLoadedMetadata}
        on:play={() => playing = true}
        on:pause={() => playing = false}
        on:ended={close}
      ></video>

      <!-- Poster thumbnail -->
      {#if state.poster}
        <div class="h-10 w-10 shrink-0 overflow-hidden rounded" style="background: var(--bg-base, #0d0d13);">
          <img src={state.poster} alt="" class="h-full w-full object-cover" />
        </div>
      {/if}

      <!-- Title and subtitle -->
      <div class="min-w-0 flex-1">
        <div class="truncate text-sm font-medium" style="color: var(--text-primary, #e0e0e8);">{state.title}</div>
        <div class="truncate text-xs" style="color: var(--text-muted, #6b6b80);">{state.subtitle} · {formatTime(currentTime)}</div>
      </div>

      <!-- Expand -->
      <button
        type="button"
        class="grid h-8 w-8 shrink-0 place-items-center rounded-full transition-colors hover:bg-white/10"
        style="color: var(--text-secondary, #a0a0b0);"
        title="Expand to full player"
        aria-label="Expand to full player"
        on:click={expand}
      >
        <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" /></svg>
      </button>

      <!-- Play/pause -->
      <button
        type="button"
        class="grid h-9 w-9 shrink-0 place-items-center rounded-full transition-colors"
        style="background:{accentColor}20; color:{accentColor};"
        title={playing ? 'Pause' : 'Play'}
        aria-label={playing ? 'Pause' : 'Play'}
        on:click={togglePlay}
      >
        {#if playing}
          <svg class="h-5 w-5" viewBox="0 0 24 24" fill="currentColor"><path d="M6 4h4v16H6zM14 4h4v16h-4z" /></svg>
        {:else}
          <svg class="h-5 w-5" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>
        {/if}
      </button>

      <!-- Close -->
      <button
        type="button"
        class="grid h-8 w-8 shrink-0 place-items-center rounded-full transition-colors"
        style="color: var(--text-muted, #6b6b80);"
        title="Close mini player"
        aria-label="Close mini player"
        on:click={close}
      >
        <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12" /></svg>
      </button>
    </div>
  {/if}
{/if}
