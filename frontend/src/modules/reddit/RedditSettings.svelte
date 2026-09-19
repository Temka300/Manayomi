<script lang="ts">
  import { onMount } from 'svelte';

  import { redditApi, type RedditStatus } from '../../lib/redditApi';
  import {
    redditCaptureDefaults,
    resetRedditCaptureDefaults,
    type RedditCaptureDefaults,
  } from './settings';

  let status: RedditStatus | null = null;
  let loading = false;
  let error = '';

  onMount(() => {
    void refreshStatus();
  });

  async function refreshStatus(): Promise<void> {
    if (loading) return;
    loading = true;
    error = '';
    try {
      status = await redditApi.status();
    } catch (cause) {
      error = cause instanceof Error ? cause.message : String(cause);
    } finally {
      loading = false;
    }
  }

  function toggleDefault(key: keyof RedditCaptureDefaults): void {
    redditCaptureDefaults.update(value => ({
      ...value,
      [key]: !value[key],
    }));
  }

  function formatNumber(value: number | undefined): string {
    return Intl.NumberFormat().format(value ?? 0);
  }

  function formatBytes(value: number | undefined): string {
    if (!value) return '0 B';
    const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
    let amount = value;
    let index = 0;
    while (amount >= 1024 && index < units.length - 1) {
      amount /= 1024;
      index += 1;
    }
    return `${amount.toFixed(index === 0 ? 0 : amount >= 10 ? 1 : 2)} ${units[index]}`;
  }

  function defaultLabel(): string {
    const enabled = [
      $redditCaptureDefaults.images ? 'images/GIFs' : '',
      $redditCaptureDefaults.videos ? 'videos' : '',
      $redditCaptureDefaults.linkedFiles ? 'linked files' : '',
    ].filter(Boolean);
    return enabled.length ? enabled.join(', ') : 'metadata only';
  }
</script>

<div class="mx-auto max-w-3xl space-y-4">
  <section
    class="rounded-2xl border border-orange-400/20 bg-[radial-gradient(circle_at_85%_0%,rgba(255,69,0,.18),transparent_38%),linear-gradient(135deg,#1d1512,#101017_72%)] px-4 py-3.5"
    aria-label="Current Reddit defaults"
  >
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div class="min-w-0">
        <h3 class="mb-2 text-sm font-semibold text-orange-100">Reddit</h3>
        <div class="flex flex-wrap gap-2 text-[11px]">
          <span class="rounded-full border border-white/5 bg-black/20 px-2.5 py-1 text-[var(--text-primary)]">Save: {defaultLabel()}</span>
          <span class="rounded-full border border-white/5 bg-black/20 px-2.5 py-1 text-[var(--text-primary)]">Failed files: {$redditCaptureDefaults.retryFailed ? 'retry' : 'skip'}</span>
          <span class="rounded-full border border-white/5 bg-black/20 px-2.5 py-1 text-[var(--text-primary)]">{status?.runtime.capture_busy ? 'Capture active' : 'Capture idle'}</span>
        </div>
      </div>
      <button
        class="shrink-0 rounded-lg border border-white/10 bg-black/15 px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-white/5 hover:text-[var(--text-primary)]"
        type="button"
        on:click={resetRedditCaptureDefaults}
      >
        Reset defaults
      </button>
    </div>
  </section>

  <section id="setting-reddit-download-defaults" class="overflow-hidden rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)]">
    <div class="border-b border-[#242432] px-4 py-3">
      <h4 class="text-sm font-semibold text-[var(--text-primary)]">Save-link defaults</h4>
      <p class="mt-1 text-xs leading-relaxed text-[var(--text-muted)]">These choices prefill the Save Link drawer. Every download still requires review and confirmation.</p>
    </div>
    <div class="divide-y divide-[var(--border-subtle)]">
      {#each [
        { key: 'images', label: 'Images and GIFs', description: 'Queue Reddit-hosted image and animation assets.' },
        { key: 'videos', label: 'Videos', description: 'Queue supported Reddit video assets.' },
        { key: 'linkedFiles', label: 'Linked files', description: 'Queue supported downloadable files linked by the post or its comments.' },
        { key: 'retryFailed', label: 'Retry failed files', description: 'Include previously failed matching assets when preparing a new plan.' },
      ] as option}
        <div class="flex items-center justify-between gap-5 px-4 py-3">
          <div>
            <div class="text-sm font-medium text-[var(--text-primary)]">{option.label}</div>
            <p class="mt-0.5 text-xs leading-relaxed text-[var(--text-muted)]">{option.description}</p>
          </div>
          <button
            class="min-w-14 shrink-0 rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors {$redditCaptureDefaults[option.key as keyof RedditCaptureDefaults] ? 'border-orange-300/35 bg-orange-500/15 text-orange-100' : 'border-[#343442] bg-[var(--bg-base)] text-[var(--text-muted)] hover:text-[var(--text-primary)]'}"
            type="button"
            aria-pressed={$redditCaptureDefaults[option.key as keyof RedditCaptureDefaults]}
            on:click={() => toggleDefault(option.key as keyof RedditCaptureDefaults)}
          >
            {$redditCaptureDefaults[option.key as keyof RedditCaptureDefaults] ? 'On' : 'Off'}
          </button>
        </div>
      {/each}
    </div>
  </section>

  <section id="setting-reddit-archive-health" class="overflow-hidden rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)]">
    <div class="flex flex-wrap items-center justify-between gap-3 border-b border-[#242432] px-4 py-3">
      <div>
        <h4 class="text-sm font-semibold text-[var(--text-primary)]">Local archive</h4>
        <p class="mt-1 text-xs text-[var(--text-muted)]">Read-only health and indexing totals from Reddit SQLite.</p>
      </div>
      <button
        class="rounded-lg border border-[#343442] px-3 py-1.5 text-xs font-semibold text-[var(--text-primary)] hover:bg-white/5 disabled:opacity-50"
        type="button"
        disabled={loading}
        on:click={refreshStatus}
      >
        {loading ? 'Refreshing…' : 'Refresh'}
      </button>
    </div>
    {#if error}
      <div class="border-b border-red-400/10 bg-red-500/[0.055] px-4 py-3 text-xs text-red-300">{error}</div>
    {/if}
    <div class="grid grid-cols-2 gap-px bg-[var(--border-subtle)] sm:grid-cols-3 lg:grid-cols-6">
      {#each [
        ['Posts', status?.counts.posts],
        ['Comments', status?.counts.comments],
        ['Communities', status?.counts.communities],
        ['Local media', status?.counts.media_objects],
        ['Queued', status?.counts.queued_assets],
        ['Duplicate refs', status?.counts.duplicate_alias_candidates],
      ] as fact}
        <div class="bg-[var(--bg-elevated)] px-4 py-3">
          <div class="text-[10px] uppercase tracking-wider text-gray-600">{fact[0]}</div>
          <div class="mt-1 text-lg font-bold text-[var(--text-primary)]">{formatNumber(fact[1] as number | undefined)}</div>
        </div>
      {/each}
    </div>
    <div class="space-y-2 border-t border-[#242432] px-4 py-3 text-xs">
      <div class="flex items-center justify-between gap-4"><span class="text-[var(--text-muted)]">Archive initialized</span><span class="text-[var(--text-primary)]">{status?.initialized ? 'Yes' : 'No'}</span></div>
      <div class="flex items-center justify-between gap-4"><span class="text-[var(--text-muted)]">Recorded jobs</span><span class="text-[var(--text-primary)]">{formatNumber(status?.jobs.length)}</span></div>
      <div class="flex items-center justify-between gap-4"><span class="text-[var(--text-muted)]">Capture process</span><span class="text-[var(--text-primary)]">{status?.runtime.capture_busy ? 'Busy' : 'Idle'}</span></div>
      <div class="flex items-center justify-between gap-4"><span class="text-[var(--text-muted)]">Media process</span><span class="text-[var(--text-primary)]">{status?.runtime.download_busy ? 'Busy' : 'Idle'}</span></div>
      <p class="pt-1 text-[11px] leading-relaxed text-gray-600">Duplicate refs count extra archive asset roles that resolve to the same owner/content hash. Existing readable aliases are reported but never removed; new publication converges automatically.</p>
    </div>
  </section>

  <section id="setting-reddit-storage-policy" class="overflow-hidden rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)]">
    <div class="border-b border-[#242432] px-4 py-3">
      <h4 class="text-sm font-semibold text-[var(--text-primary)]">Storage and Files</h4>
      <p class="mt-1 text-xs leading-relaxed text-[var(--text-muted)]">Captured JSON and SQLite stay under the Reddit module. Downloaded bytes are content-addressed and a readable library is published to Files.</p>
    </div>
    <dl class="divide-y divide-[var(--border-subtle)] text-xs">
      <div class="px-4 py-3"><dt class="text-[var(--text-muted)]">SQLite database</dt><dd class="mt-1 break-all font-mono text-[11px] text-[var(--text-primary)]">{status?.database_path ?? 'Unavailable'}</dd></div>
      <div class="px-4 py-3"><dt class="text-[var(--text-muted)]">Archive root</dt><dd class="mt-1 break-all font-mono text-[11px] text-[var(--text-primary)]">{status?.storage.archive ?? 'Unavailable'}</dd></div>
      <div class="px-4 py-3"><dt class="text-[var(--text-muted)]">Media object store</dt><dd class="mt-1 break-all font-mono text-[11px] text-[var(--text-primary)]">{status?.storage.media ?? 'Unavailable'}</dd></div>
      <div class="px-4 py-3"><dt class="text-[var(--text-muted)]">Files module view</dt><dd class="mt-1 break-all font-mono text-[11px] text-[var(--text-primary)]">{status?.storage.files_library ?? 'Created after the first successful download'}</dd></div>
    </dl>
  </section>

  <section id="setting-reddit-download-safety" class="overflow-hidden rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)]">
    <div class="border-b border-[#242432] px-4 py-3">
      <h4 class="text-sm font-semibold text-[var(--text-primary)]">Download safety</h4>
      <p class="mt-1 text-xs leading-relaxed text-[var(--text-muted)]">A plan is built from the selected saved post or community. You confirm its exact count and fingerprint before network transfer starts.</p>
    </div>
    <div class="grid gap-px bg-[var(--border-subtle)] sm:grid-cols-2">
      <div class="bg-[var(--bg-elevated)] px-4 py-3"><div class="text-[10px] uppercase tracking-wider text-gray-600">Files per run</div><div class="mt-1 text-sm font-semibold text-[var(--text-primary)]">{formatNumber(status?.limits.max_files)}</div></div>
      <div class="bg-[var(--bg-elevated)] px-4 py-3"><div class="text-[10px] uppercase tracking-wider text-gray-600">Maximum one file</div><div class="mt-1 text-sm font-semibold text-[var(--text-primary)]">{formatBytes(status?.limits.max_file_bytes)}</div></div>
      <div class="bg-[var(--bg-elevated)] px-4 py-3"><div class="text-[10px] uppercase tracking-wider text-gray-600">Maximum one run</div><div class="mt-1 text-sm font-semibold text-[var(--text-primary)]">{formatBytes(status?.limits.max_run_bytes)}</div></div>
      <div class="bg-[var(--bg-elevated)] px-4 py-3"><div class="text-[10px] uppercase tracking-wider text-gray-600">Free space reserved</div><div class="mt-1 text-sm font-semibold text-[var(--text-primary)]">{formatBytes(status?.limits.min_free_bytes)}</div></div>
    </div>
    <p class="border-t border-[#242432] px-4 py-3 text-xs leading-relaxed text-[var(--text-muted)]">Redirects, DNS targets, response size, MIME type, containment, and free space are checked. Unsupported destinations remain visible outbound links instead of being fetched.</p>
  </section>

  <section id="setting-reddit-capture-provider" class="rounded-xl border border-orange-400/15 bg-orange-500/[0.045] px-4 py-3.5">
    <h4 class="text-sm font-semibold text-orange-100">Capture source and scope</h4>
    <p class="mt-1 text-xs leading-relaxed text-orange-100/60">Save Link contacts the bounded Arctic Shift JSON service. A post URL preserves one post, available comments, observations, and gap markers. A subreddit URL preserves only community about, rules, moderators, wiki pages, and image references—never its post listing. A public user URL preserves at most 100 matching posts and 100 matching comments. Exact source responses are stored before indexing.</p>
  </section>
</div>
