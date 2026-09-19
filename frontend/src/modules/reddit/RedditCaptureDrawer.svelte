<script lang="ts">
  import { createEventDispatcher, onDestroy, onMount, tick } from 'svelte';
  import { get } from 'svelte/store';
  import { fade, fly } from 'svelte/transition';
  import {
    redditApi,
    type RedditCaptureResult,
    type RedditMediaJob,
    type RedditMediaDownloadResult,
    type RedditMediaPlan,
    type RedditMediaSelection,
  } from '../../lib/redditApi';
  import { focusTrap } from '../../lib/focusTrap';
  import { redditCaptureDefaults } from './settings';

  const dispatch = createEventDispatcher<{
    close: void;
    captured: RedditCaptureResult;
    downloadstarted: RedditMediaJob;
  }>();

  export let initialUrl = '';

  let url = initialUrl;
  let saving = false;
  let downloading = false;
  let error = '';
  let mediaError = '';
  let result: RedditCaptureResult | null = null;
  let mediaPlan: RedditMediaPlan | null = null;
  let downloadResult: RedditMediaDownloadResult | null = null;
  let downloadJob: RedditMediaJob | null = null;
  let saveImages = false;
  let saveVideos = false;
  let saveLinkedFiles = false;
  let retryFailed = true;
  let input: HTMLInputElement;
  let controller: AbortController | null = null;
  let pollTimer: ReturnType<typeof setTimeout> | null = null;

  onMount(async () => {
    const defaults = get(redditCaptureDefaults);
    saveImages = defaults.images;
    saveVideos = defaults.videos;
    saveLinkedFiles = defaults.linkedFiles;
    retryFailed = defaults.retryFailed;
    await tick();
    input?.focus();
  });

  onDestroy(() => {
    controller?.abort();
    if (pollTimer) clearTimeout(pollTimer);
  });

  function requestClose() {
    if (!saving && !downloading) dispatch('close');
  }

  function keydown(event: KeyboardEvent) {
    if (event.key === 'Escape') requestClose();
  }

  function backdropClick(event: MouseEvent) {
    if (event.target === event.currentTarget) requestClose();
  }

  async function save() {
    const value = url.trim();
    if (!value || saving) return;
    saving = true;
    error = '';
    mediaError = '';
    result = null;
    mediaPlan = null;
    downloadResult = null;
    downloadJob = null;
    controller = new AbortController();
    try {
      result = await redditApi.capture(value, controller.signal);
      dispatch('captured', result);
      const selection = mediaSelection(result);
      if (selection && (saveImages || saveVideos || saveLinkedFiles)) {
        try {
          mediaPlan = (
            await redditApi.mediaPlan(selection, controller.signal)
          ).plan;
        } catch (cause) {
          if ((cause as Error).name !== 'AbortError') {
            mediaError = (cause as Error).message;
          }
        }
      }
    } catch (cause) {
      if ((cause as Error).name !== 'AbortError') {
        error = (cause as Error).message;
      }
    } finally {
      saving = false;
      controller = null;
    }
  }

  function mediaSelection(captureResult: RedditCaptureResult): RedditMediaSelection | null {
    if (captureResult.indexed.target_kind === 'user') return null;
    return {
      target_kind: captureResult.indexed.target_kind,
      target_id: captureResult.indexed.target_id,
      images: saveImages,
      videos: saveVideos,
      linked_files: saveLinkedFiles,
      retry_failed: retryFailed,
    };
  }

  async function downloadSelected() {
    if (!result || !mediaPlan || downloading || mediaPlan.selected_assets === 0) return;
    const selection = mediaSelection(result);
    if (!selection) return;
    downloading = true;
    mediaError = '';
    controller = new AbortController();
    try {
      const started = await redditApi.startMediaJob(
        selection,
        mediaPlan.confirmation,
        controller.signal,
      );
      downloadJob = started.job;
      dispatch('downloadstarted', started.job);
      void pollDownload();
    } catch (cause) {
      if ((cause as Error).name !== 'AbortError') {
        mediaError = (cause as Error).message;
      }
    } finally {
      downloading = false;
      controller = null;
    }
  }

  async function pollDownload() {
    const jobId = downloadJob?.job_id;
    if (!jobId) return;
    try {
      const current = (await redditApi.mediaJob(jobId)).job;
      downloadJob = current;
      dispatch('downloadstarted', current);
      if (current.status === 'queued' || current.status === 'running') {
        pollTimer = setTimeout(() => void pollDownload(), 700);
        return;
      }
      downloadResult = current.result;
      if (downloadResult && result) {
        mediaPlan = downloadResult.plan;
        dispatch('captured', result);
      }
      if (current.error) mediaError = current.error;
    } catch (cause) {
      mediaError = (cause as Error).message;
    }
  }

  function captureDescription(captureResult: RedditCaptureResult): string {
    if (captureResult.indexed.target_kind === 'post') {
      const count = captureResult.indexed.comments ?? 0;
      const comments = Intl.NumberFormat().format(count);
      return `Indexed the post and ${comments} archived comment${count === 1 ? '' : 's'}.`;
    }
    if (captureResult.indexed.target_kind === 'user') {
      const posts = captureResult.indexed.posts ?? 0;
      const comments = captureResult.indexed.comments ?? 0;
      return `Indexed ${posts} recent post${posts === 1 ? '' : 's'} and ${comments} recent comment${comments === 1 ? '' : 's'} for this profile.`;
    }
    const pages = Intl.NumberFormat().format(captureResult.capture.wiki_page_count);
    return `Indexed community information, rules, image references, and ${pages} wiki page${captureResult.capture.wiki_page_count === 1 ? '' : 's'}.`;
  }

  function formatBytes(value: number): string {
    if (value < 1024) return `${value} B`;
    const units = ['KiB', 'MiB', 'GiB', 'TiB'];
    let amount = value / 1024;
    let index = 0;
    while (amount >= 1024 && index < units.length - 1) {
      amount /= 1024;
      index += 1;
    }
    return `${amount.toFixed(amount >= 10 ? 1 : 2)} ${units[index]}`;
  }
</script>

<svelte:window on:keydown={keydown} />

<div
  class="fixed inset-0 z-[90] bg-black/65 backdrop-blur-[2px]"
  role="presentation"
  on:click={backdropClick}
  transition:fade={{ duration: 160 }}
>
  <div
    class="ml-auto flex h-full w-full max-w-[460px] flex-col border-l border-[#343536] bg-[#0f1011] text-[#d7dadc] shadow-2xl"
    role="dialog"
    aria-modal="true"
    aria-labelledby="reddit-capture-title"
    aria-busy={saving || downloading}
    tabindex="-1"
    use:focusTrap={{ close: requestClose }}
    transition:fly={{ x: 460, duration: 240 }}
  >
    <header class="flex shrink-0 items-center gap-3 border-b border-[#343536] bg-[#1a1a1b] px-5 py-4">
      <span class="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-[#ff4500] text-white">
        <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path stroke-linecap="round" stroke-width="2" d="M12 5v14M5 12h14" />
        </svg>
      </span>
      <div class="min-w-0 flex-1">
        <h1 id="reddit-capture-title" class="font-bold">Save a Reddit link</h1>
        <p class="text-xs text-[#818384]">Add a post, community snapshot, or user profile.</p>
      </div>
      <button
        type="button"
        class="grid h-9 w-9 place-items-center rounded-full text-[#818384] hover:bg-[#272729] hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
        aria-label="Close Save link panel"
        disabled={saving || downloading}
        on:click={requestClose}
      >
        <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path stroke-linecap="round" stroke-width="2" d="M6 6l12 12M18 6L6 18" />
        </svg>
      </button>
    </header>

    <div class="min-h-0 flex-1 overflow-y-auto p-5">
      <form class="space-y-4" on:submit|preventDefault={save}>
        <div>
          <label for="reddit-capture-url" class="text-sm font-semibold">Reddit URL</label>
          <input
            id="reddit-capture-url"
            bind:this={input}
            bind:value={url}
            type="url"
            inputmode="url"
            autocomplete="off"
            spellcheck="false"
            required
            disabled={saving}
            placeholder="https://www.reddit.com/r/.../comments/... or /user/..."
            class="mt-2 h-11 w-full rounded-lg border border-[#343536] bg-[#1a1a1b] px-3 text-sm outline-none placeholder:text-[#68696b] focus:border-[#ff4500] disabled:opacity-60"
          />
        </div>

        <div class="rounded-lg border border-[#343536] bg-[#1a1a1b] p-3 text-xs leading-5 text-[#a7a8aa]">
          <strong class="text-[#d7dadc]">Post link:</strong> saves that post and its bounded comments.<br />
          <strong class="text-[#d7dadc]">Subreddit link:</strong> saves about, rules, wiki, and image references only—never its post listing.<br />
          <strong class="text-[#d7dadc]">Profile link:</strong> saves a bounded set of that user's recent posts and comments.
        </div>

        <fieldset class="rounded-lg border border-[#343536] bg-[#1a1a1b] p-3">
          <legend class="px-1 text-xs font-semibold text-[#d7dadc]">Download after saving</legend>
          <p class="mb-3 text-xs leading-5 text-[#818384]">
            First the link is indexed. Then you confirm the exact bounded download plan.
          </p>
          <div class="grid gap-2 text-sm">
            <label class="flex items-center gap-2">
              <input bind:checked={saveImages} type="checkbox" disabled={saving || downloading} class="accent-[#ff4500]" />
              Images and GIFs
            </label>
            <label class="flex items-center gap-2">
              <input bind:checked={saveVideos} type="checkbox" disabled={saving || downloading} class="accent-[#ff4500]" />
              Videos
            </label>
            <label class="flex items-center gap-2">
              <input bind:checked={saveLinkedFiles} type="checkbox" disabled={saving || downloading} class="accent-[#ff4500]" />
              Linked files
            </label>
          </div>
        </fieldset>

        {#if error}
          <div class="rounded-lg border border-red-900/60 bg-red-950/45 px-3 py-2.5 text-sm text-red-200" role="alert">
            {error}
          </div>
        {/if}

        {#if result}
          <div class="rounded-lg border border-emerald-800/60 bg-emerald-950/35 px-3 py-3 text-sm text-emerald-100" role="status">
            <strong class="block">Saved to your local Reddit archive.</strong>
            <span class="mt-1 block text-xs leading-5 text-emerald-200/80">{captureDescription(result)}</span>
          </div>
        {/if}

        {#if mediaError}
          <div class="rounded-lg border border-amber-800/60 bg-amber-950/35 px-3 py-2.5 text-sm text-amber-100" role="alert">
            {mediaError}
          </div>
        {/if}

        {#if mediaPlan && !downloadResult}
          <div class="rounded-lg border border-sky-800/60 bg-sky-950/30 px-3 py-3 text-sm text-sky-100">
            <strong class="block">Download plan ready</strong>
            {#if mediaPlan.selected_assets > 0}
              <span class="mt-1 block text-xs leading-5 text-sky-200/80">
                {mediaPlan.selected_assets} file{mediaPlan.selected_assets === 1 ? '' : 's'} selected.
                {mediaPlan.rejected_policy > 0
                  ? ` ${mediaPlan.rejected_policy} link${mediaPlan.rejected_policy === 1 ? '' : 's'} remain link-only.`
                  : ''}
              </span>
              {#if downloadJob}
                <div class="mt-3" role="status">
                  <div class="mb-1 flex justify-between text-[11px] text-sky-200/80">
                    <span>{downloadJob.phase}</span>
                    <span>{Math.round(downloadJob.progress * 100)}%</span>
                  </div>
                  <div class="h-2 overflow-hidden rounded-full bg-black/35">
                    <div
                      class="h-full rounded-full bg-sky-400 transition-[width] duration-300"
                      style={`width:${Math.max(2, downloadJob.progress * 100)}%`}
                    ></div>
                  </div>
                  <p class="mt-2 text-xs text-sky-200/80">
                    {downloadJob.completed} of {downloadJob.planned} files saved.
                    You can close this panel; progress stays in the Reddit header.
                  </p>
                </div>
              {:else}
                <button
                  type="button"
                  class="mt-3 flex h-10 w-full items-center justify-center gap-2 rounded-full border border-sky-300/60 font-bold hover:bg-sky-400/10 disabled:opacity-45"
                  disabled={downloading || !mediaPlan.can_start}
                  on:click={downloadSelected}
                >
                  {#if downloading}
                    <span class="h-4 w-4 animate-spin rounded-full border-2 border-white/35 border-t-white" aria-hidden="true"></span>
                    Starting…
                  {:else}
                    Download {mediaPlan.selected_assets} file{mediaPlan.selected_assets === 1 ? '' : 's'}
                  {/if}
                </button>
              {/if}
            {:else}
              <span class="mt-1 block text-xs leading-5 text-sky-200/80">
                No new supported files match those options. Outbound links still appear on the saved post.
              </span>
            {/if}
          </div>
        {/if}

        {#if downloadResult}
          <div class="rounded-lg border border-emerald-800/60 bg-emerald-950/35 px-3 py-3 text-sm text-emerald-100" role="status">
            <strong class="block">Media download finished.</strong>
            <span class="mt-1 block text-xs leading-5 text-emerald-200/80">
              Saved {downloadResult.download.completed} file{downloadResult.download.completed === 1 ? '' : 's'}
              ({formatBytes(downloadResult.download.bytes_acquired)}).
              {downloadResult.download.failed > 0
                ? ` ${downloadResult.download.failed} failed and can be retried.`
                : ''}
              {downloadResult.files.published ? ' Downloads are visible in Files.' : ''}
            </span>
          </div>
        {/if}

        <button
          type="submit"
          disabled={saving || downloading || !url.trim()}
          class="flex h-11 w-full items-center justify-center gap-2 rounded-full bg-[#ff4500] px-4 text-sm font-bold text-white hover:bg-[#ff5414] disabled:cursor-not-allowed disabled:opacity-45"
        >
          {#if saving}
            <span class="h-4 w-4 animate-spin rounded-full border-2 border-white/35 border-t-white" aria-hidden="true"></span>
            Saving link…
          {:else}
            Save link
          {/if}
        </button>
      </form>

      <p class="mt-5 text-xs leading-5 text-[#68696b]">
        Saving contacts the bounded Arctic Shift JSON service. Source responses are preserved before indexing. Media bytes download only after you review and confirm the plan.
      </p>
    </div>
  </div>
</div>
