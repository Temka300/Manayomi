<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { fade, fly } from 'svelte/transition';
  import type { RedditMediaJob } from '../../lib/redditApi';
  import { focusTrap } from '../../lib/focusTrap';

  export let jobs: RedditMediaJob[] = [];

  const dispatch = createEventDispatcher<{ close: void }>();

  function close() {
    dispatch('close');
  }

  function backdropClick(event: MouseEvent) {
    if (event.target === event.currentTarget) close();
  }

  function statusLabel(job: RedditMediaJob): string {
    if (job.status === 'completed_with_errors') return 'Finished with errors';
    if (job.status === 'completed') return 'Finished';
    if (job.status === 'failed') return 'Failed';
    if (job.status === 'queued') return 'Queued';
    return job.phase || 'Downloading';
  }
</script>

<svelte:window on:keydown={(event) => event.key === 'Escape' && close()} />

<div
  class="fixed inset-0 z-[95] bg-black/55 backdrop-blur-[2px]"
  role="presentation"
  on:click={backdropClick}
  transition:fade={{ duration: 140 }}
>
  <div
    class="ml-auto flex h-full w-full max-w-[420px] flex-col border-l border-[#343536] bg-[#0f1011] text-[#d7dadc] shadow-2xl"
    role="dialog"
    aria-modal="true"
    aria-labelledby="reddit-downloads-title"
    tabindex="-1"
    use:focusTrap={{ close }}
    transition:fly={{ x: 420, duration: 220 }}
  >
    <header class="flex h-16 shrink-0 items-center gap-3 border-b border-[#343536] bg-[#1a1a1b] px-5">
      <div class="min-w-0 flex-1">
        <h1 id="reddit-downloads-title" class="font-bold">Reddit downloads</h1>
        <p class="text-xs text-[#818384]">Current and recent media jobs</p>
      </div>
      <button type="button" class="grid h-9 w-9 place-items-center rounded-full text-[#818384] hover:bg-white/10 hover:text-white" aria-label="Close downloads" on:click={close}>
        <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-width="2" d="M6 6l12 12M18 6L6 18" />
        </svg>
      </button>
    </header>

    <div class="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
      {#if jobs.length === 0}
        <div class="rounded-xl border border-[#343536] bg-[#1a1a1b] p-7 text-center text-sm text-[#818384]">
          No Reddit media downloads yet.
        </div>
      {:else}
        {#each jobs as job (job.job_id)}
          <article class="rounded-xl border border-[#343536] bg-[#1a1a1b] p-4">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <strong class="block truncate text-sm">{job.target_kind} {job.target_id}</strong>
                <span class="text-xs text-[#a7a8aa]">{statusLabel(job)}</span>
              </div>
              <span class="shrink-0 text-xs font-semibold {job.status === 'failed' ? 'text-red-300' : 'text-[#4fbcff]'}">
                {Math.round(job.progress * 100)}%
              </span>
            </div>
            <div class="mt-3 h-2 overflow-hidden rounded-full bg-black/40">
              <div
                class="h-full rounded-full transition-[width] duration-300 {job.status === 'failed' ? 'bg-red-400' : 'bg-[#4fbcff]'}"
                style={`width:${Math.max(job.progress > 0 ? 2 : 0, job.progress * 100)}%`}
              ></div>
            </div>
            <p class="mt-2 text-xs text-[#818384]">
              {job.completed} of {job.planned} saved{job.failed ? ` · ${job.failed} failed` : ''}
            </p>
            {#if job.error}
              <p class="mt-2 break-words text-xs leading-5 text-red-300">{job.error}</p>
            {/if}
          </article>
        {/each}
      {/if}
    </div>
  </div>
</div>
