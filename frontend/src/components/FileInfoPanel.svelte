<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { filesApi, type Annotation, type AnnotationLink, type ApiError } from '../lib/filesApi';
  import {
    fileGlyph,
    isListableArchive,
    linkKindLabel,
    previewMode,
    type Subject,
  } from '../lib/filePreview';
  import { showToast } from '../lib/ui';

  export let subject: Subject;

  const dispatch = createEventDispatcher<{ close: void; changed: void }>();
  const TEXT_CAP = 1024 * 1024;
  const LINK_KINDS = ['source', 'discussion', 'mirror', 'author', 'other'];
  const relativeTime = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });

  let annotation: Annotation | null = null;
  let indexedAt: string | null = null;
  let loading = false;
  let error = '';
  let actionError = '';
  let textPreview: string | null = null;
  let textTruncated = false;
  let mediaWidth: number | null = null;
  let mediaHeight: number | null = null;
  let loadedKey = '';

  let editing = false;
  let saving = false;
  let draftDescription = '';
  let draftLinks: AnnotationLink[] = [];
  let uploading = false;
  let fileInput: HTMLInputElement;

  $: key = `${subject.sourceId}::${subject.path}`;
  $: if (key !== loadedKey) {
    loadedKey = key;
    void load(subject);
  }
  $: mode = subject.isDir ? 'none' : previewMode(subject.ext);
  $: fileHref = filesApi.fileUrl(subject.sourceId, subject.path);
  $: hasOrigin =
    annotation !== null &&
    (annotation.description.trim() !== '' ||
      annotation.links.length > 0 ||
      annotation.attachments.length > 0);

  async function load(current: Subject) {
    loading = true;
    error = '';
    actionError = '';
    annotation = null;
    indexedAt = null;
    editing = false;
    textPreview = null;
    textTruncated = false;
    mediaWidth = null;
    mediaHeight = null;
    archive = null;
    archiveError = '';
    picking = false;
    try {
      const info = await filesApi.getInfo(current.sourceId, current.path);
      annotation = info.annotation;
      indexedAt = info.indexed_at;
    } catch (e) {
      error = (e as Error).message;
    } finally {
      loading = false;
    }
    if (!current.isDir && previewMode(current.ext) === 'text') {
      await loadText(current);
    }
  }

  function startEditing() {
    draftDescription = annotation?.description ?? '';
    draftLinks = (annotation?.links ?? []).map((link) => ({ ...link }));
    if (draftLinks.length === 0) addLink();
    actionError = '';
    editing = true;
  }

  function cancelEditing() {
    editing = false;
    actionError = '';
  }

  function addLink() {
    draftLinks = [...draftLinks, { url: '', label: '', kind: 'source' }];
  }

  function removeLink(index: number) {
    draftLinks = draftLinks.filter((_, i) => i !== index);
  }

  // --- Archive contents --------------------------------------------------
  let archive: import('../lib/filesApi').ArchiveListing | null = null;
  let archiveError = '';
  let archiveLoading = false;

  $: canListArchive = !subject.isDir && isListableArchive(subject.ext);

  async function loadArchive() {
    archiveLoading = true;
    archiveError = '';
    try {
      archive = await filesApi.listArchive(subject.sourceId, subject.path);
    } catch (e) {
      archiveError = (e as Error).message;
    } finally {
      archiveLoading = false;
    }
  }

  // --- Copy origin from another subject ---------------------------------
  let picking = false;
  let pickerPaths: string[] = [];
  let pickerFilter = '';
  let copying = false;

  $: pickerMatches = pickerPaths
    .filter((candidate) => candidate !== subject.path)
    .filter((candidate) => candidate.toLowerCase().includes(pickerFilter.toLowerCase()))
    .slice(0, 50);

  async function openPicker() {
    actionError = '';
    picking = true;
    pickerFilter = '';
    try {
      pickerPaths = await filesApi.listAnnotated(subject.sourceId);
    } catch (e) {
      actionError = (e as Error).message;
      pickerPaths = [];
    }
  }

  async function copyFrom(fromPath: string, overwrite = false) {
    copying = true;
    actionError = '';
    try {
      annotation = await filesApi.copyInfo(
        subject.sourceId,
        fromPath,
        subject.sourceId,
        subject.path,
        overwrite,
      );
      picking = false;
      dispatch('changed');
    } catch (e) {
      const error = e as ApiError;
      if (error.status === 409 && !overwrite) {
        copying = false;
        if (confirm(`${error.message}.\n\nReplace this description?`)) {
          await copyFrom(fromPath, true);
        }
        return;
      }
      actionError = error.message;
    } finally {
      copying = false;
    }
  }

  async function save() {
    const links = draftLinks
      .map((link) => ({ url: link.url.trim(), label: link.label.trim(), kind: link.kind }))
      .filter((link) => link.url !== '');
    for (const link of links) {
      if (!/^https?:\/\//i.test(link.url)) {
        actionError = `Links must start with http:// or https:// — check: ${link.url}`;
        return;
      }
    }
    saving = true;
    actionError = '';
    try {
      annotation = await filesApi.saveInfo({
        source_id: subject.sourceId,
        path: subject.path,
        description: draftDescription.trim(),
        links,
      });
      editing = false;
      dispatch('changed');
    } catch (e) {
      actionError = (e as Error).message;
    } finally {
      saving = false;
    }
  }

  async function deleteInfo() {
    saving = true;
    actionError = '';
    try {
      await filesApi.deleteInfo(subject.sourceId, subject.path);
      annotation = null;
      editing = false;
      dispatch('changed');
    } catch (e) {
      actionError = (e as Error).message;
    } finally {
      saving = false;
    }
  }

  async function onUploadChange(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;
    uploading = true;
    actionError = '';
    try {
      annotation = await filesApi.uploadAttachment(subject.sourceId, subject.path, file);
      dispatch('changed');
    } catch (e) {
      actionError = (e as Error).message;
    } finally {
      uploading = false;
    }
  }

  async function removeAttachment(attachmentId: number) {
    actionError = '';
    try {
      await filesApi.deleteAttachment(attachmentId);
      const info = await filesApi.getInfo(subject.sourceId, subject.path);
      annotation = info.annotation;
      indexedAt = info.indexed_at;
      dispatch('changed');
    } catch (e) {
      actionError = (e as Error).message;
    }
  }

  async function loadText(current: Subject) {
    try {
      const res = await fetch(filesApi.fileUrl(current.sourceId, current.path), {
        headers: { Range: `bytes=0-${TEXT_CAP - 1}` },
      });
      if (!res.ok && res.status !== 206) return;
      textPreview = await res.text();
      textTruncated = (current.size ?? 0) > TEXT_CAP;
    } catch {
      // Preview is best-effort.
    }
  }

  async function openExternally() {
    actionError = '';
    try {
      await filesApi.openFile(subject.sourceId, subject.path);
    } catch (e) {
      actionError = (e as Error).message;
    }
  }

  async function reveal() {
    actionError = '';
    try {
      await filesApi.revealFile(subject.sourceId, subject.path);
    } catch (e) {
      actionError = (e as Error).message;
    }
  }

  async function copyPath() {
    try {
      await navigator.clipboard.writeText(subject.absolutePath);
      showToast({ title: 'Path copied', message: subject.absolutePath, tone: 'success' });
    } catch {
      // Clipboard can be unavailable.
    }
  }

  function readImageDimensions(event: Event) {
    const image = event.currentTarget as HTMLImageElement;
    mediaWidth = image.naturalWidth || null;
    mediaHeight = image.naturalHeight || null;
  }

  function readVideoDimensions(event: Event) {
    const video = event.currentTarget as HTMLVideoElement;
    mediaWidth = video.videoWidth || null;
    mediaHeight = video.videoHeight || null;
  }

  function formatSize(bytes: number | null): string {
    if (bytes == null) return '—';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let n = bytes;
    let i = 0;
    while (n >= 1024 && i < units.length - 1) {
      n /= 1024;
      i += 1;
    }
    return `${i === 0 ? n : n < 10 ? n.toFixed(1) : Math.round(n)} ${units[i]}`;
  }

  function dateMillis(value: number | string | null, unixSeconds = false): number | null {
    if (value === null || value === '') return null;
    const millis = typeof value === 'number'
      ? value * (unixSeconds ? 1000 : 1)
      : Date.parse(value);
    return Number.isFinite(millis) ? millis : null;
  }

  function formatDate(value: number | string | null, unixSeconds = false): string {
    const millis = dateMillis(value, unixSeconds);
    return millis === null ? '—' : new Date(millis).toLocaleString();
  }

  function formatRelativeDate(value: number | string | null, unixSeconds = false): string {
    const millis = dateMillis(value, unixSeconds);
    if (millis === null) return '';
    const difference = millis - Date.now();
    const absolute = Math.abs(difference);
    if (absolute < 45_000) return 'just now';
    const units: Array<[Intl.RelativeTimeFormatUnit, number]> = [
      ['year', 365 * 24 * 60 * 60 * 1000],
      ['month', 30 * 24 * 60 * 60 * 1000],
      ['week', 7 * 24 * 60 * 60 * 1000],
      ['day', 24 * 60 * 60 * 1000],
      ['hour', 60 * 60 * 1000],
      ['minute', 60 * 1000],
    ];
    const [unit, duration] = units.find(([, threshold]) => absolute >= threshold) ?? ['minute', 60_000];
    return relativeTime.format(Math.round(difference / duration), unit);
  }
</script>

<div
  class="flex max-h-[85vh] w-full max-w-[560px] flex-col overflow-hidden rounded-2xl border border-white/10 bg-[var(--bg-elevated)] shadow-2xl shadow-black/80"
  role="dialog"
  aria-label="File info"
  tabindex="-1"
  on:pointerdown|stopPropagation
>
  <!-- Header -->
  <div class="flex items-start gap-3 border-b border-white/5 px-5 py-4">
    <span class="mt-0.5 text-2xl leading-none">{fileGlyph({ is_dir: subject.isDir, ext: subject.ext })}</span>
    <div class="min-w-0 flex-1">
      <div class="truncate text-base font-semibold text-gray-100" title={subject.name}>{subject.name}</div>
      <div class="mt-0.5 text-xs text-[var(--text-muted)]">
        {subject.isDir ? 'Folder' : (subject.ext || 'file').toUpperCase()}
        {#if !subject.isDir && subject.size != null}
          <span class="mx-1 text-gray-600">·</span>
          {formatSize(subject.size)}
        {/if}
      </div>
    </div>
    <div class="flex shrink-0 items-center gap-2">
      {#if !editing && !loading}
        <button
          type="button"
          class="rounded-lg bg-purple-500/20 px-3 py-1.5 text-xs font-medium text-purple-200 transition-colors hover:bg-purple-500/30"
          on:click={startEditing}
        >{hasOrigin ? 'Edit info' : 'Add info'}</button>
      {/if}
      <button
        type="button"
        class="grid h-7 w-7 place-items-center rounded-md text-[var(--text-muted)] transition-colors hover:bg-white/5 hover:text-white"
        title="Close"
        aria-label="Close info"
        on:click={() => dispatch('close')}
      >✕</button>
    </div>
  </div>

  <div class="flex-1 overflow-y-auto">
    <!-- Preview -->
    {#if mode !== 'none'}
      <div class="border-b border-white/5 bg-black/30 p-4">
        {#if mode === 'image'}
          <img
            src={fileHref}
            alt={subject.name}
            class="mx-auto max-h-80 max-w-full rounded-lg object-contain"
            on:load={readImageDimensions}
          />
        {:else if mode === 'video'}
          <!-- svelte-ignore a11y-media-has-caption -->
          <video
            src={fileHref}
            controls
            class="mx-auto max-h-80 max-w-full rounded-lg"
            on:loadedmetadata={readVideoDimensions}
          ></video>
        {:else if mode === 'audio'}
          <audio src={fileHref} controls class="w-full"></audio>
        {:else if mode === 'pdf'}
          <embed src={fileHref} type="application/pdf" class="h-80 w-full rounded-lg" />
        {:else if mode === 'text'}
          {#if textPreview !== null}
            <pre class="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-black/40 p-3 text-[11px] leading-snug text-[var(--text-primary)]">{textPreview}</pre>
            {#if textTruncated}
              <p class="mt-1 text-[10px] text-[var(--text-muted)]">Preview truncated — open externally for the full file.</p>
            {/if}
          {:else}
            <p class="py-6 text-center text-xs text-gray-600">Loading preview…</p>
          {/if}
        {/if}
      </div>
    {/if}

    <!-- Origin -->
    <div class="border-b border-white/5 px-5 py-4">
      <div class="mb-2 flex items-center justify-between">
        <h3 class="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">Origin</h3>
        {#if !editing && !loading}
          <button
            type="button"
            class="text-[11px] text-[var(--text-secondary)] hover:text-purple-200"
            title="Carry another file's origin note onto this one"
            on:click={openPicker}
          >Copy from…</button>
        {/if}
      </div>

      {#if picking}
        <div class="mb-3 rounded-lg border border-[#2a2a3a] bg-[#0d0d14] p-2.5">
          <div class="mb-2 flex items-center gap-2">
            <input
              class="min-w-0 flex-1 rounded border border-[#2a2a3a] bg-[#1e1e2e] px-2 py-1 text-xs text-[var(--text-primary)] outline-none placeholder:text-gray-600 focus:border-purple-500"
              placeholder="Filter files with origin info…"
              bind:value={pickerFilter}
            />
            <button
              type="button"
              class="shrink-0 text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)]"
              on:click={() => (picking = false)}
            >Cancel</button>
          </div>
          {#if pickerMatches.length === 0}
            <p class="px-1 py-2 text-xs text-gray-600">
              {pickerPaths.length === 0
                ? 'Nothing in this folder has origin info yet.'
                : 'No match.'}
            </p>
          {:else}
            <ul class="max-h-40 overflow-y-auto">
              {#each pickerMatches as candidate (candidate)}
                <li>
                  <button
                    type="button"
                    class="w-full truncate rounded px-2 py-1 text-left text-xs text-[var(--text-primary)] hover:bg-white/5 hover:text-white disabled:opacity-40"
                    title={candidate}
                    disabled={copying}
                    on:click={() => copyFrom(candidate)}
                  >{candidate || '(this folder)'}</button>
                </li>
              {/each}
            </ul>
          {/if}
          <p class="mt-1 px-1 text-[10px] text-gray-600">
            Adds to this note — links and screenshots merge, nothing is removed.
          </p>
        </div>
      {/if}

      {#if loading}
        <p class="text-sm text-[var(--text-muted)]">Loading…</p>
      {:else if error}
        <p class="text-xs text-red-300">{error}</p>
      {:else if editing}
        <div class="space-y-3">
          <div>
            <label class="mb-1 block text-[10px] uppercase tracking-wide text-[var(--text-muted)]" for="origin-desc">Description</label>
            <textarea
              id="origin-desc"
              rows="3"
              bind:value={draftDescription}
              placeholder="Where is this from? What is it?"
              class="w-full resize-y rounded-lg border border-[#2a2a3a] bg-[#1e1e2e] px-3 py-2 text-xs text-[var(--text-primary)] outline-none placeholder:text-gray-600 focus:border-purple-500"
            ></textarea>
          </div>

          <div class="space-y-2">
            <span class="block text-[10px] uppercase tracking-wide text-[var(--text-muted)]">Links</span>
            {#each draftLinks as link, index (index)}
              <div class="space-y-1 rounded-lg border border-white/5 bg-black/20 p-2">
                <div class="flex gap-1.5">
                  <select
                    bind:value={link.kind}
                    class="shrink-0 rounded border border-[#2a2a3a] bg-[#1e1e2e] px-1 py-1 text-[11px] text-[var(--text-primary)] outline-none focus:border-purple-500"
                  >
                    {#each LINK_KINDS as kind}
                      <option value={kind}>{linkKindLabel(kind)}</option>
                    {/each}
                  </select>
                  <input
                    bind:value={link.label}
                    placeholder="Label (optional)"
                    class="min-w-0 flex-1 rounded border border-[#2a2a3a] bg-[#1e1e2e] px-2 py-1 text-[11px] text-[var(--text-primary)] outline-none placeholder:text-gray-600 focus:border-purple-500"
                  />
                  <button
                    type="button"
                    class="shrink-0 rounded px-1.5 text-[var(--text-muted)] hover:text-red-300"
                    title="Remove link"
                    aria-label="Remove link"
                    on:click={() => removeLink(index)}
                  >✕</button>
                </div>
                <input
                  bind:value={link.url}
                  placeholder="https://…"
                  class="w-full rounded border border-[#2a2a3a] bg-[#1e1e2e] px-2 py-1 text-[11px] text-[var(--text-primary)] outline-none placeholder:text-gray-600 focus:border-purple-500"
                />
              </div>
            {/each}
            <button
              type="button"
              class="text-[11px] text-purple-300 hover:text-purple-200"
              on:click={addLink}
            >+ Add link</button>
          </div>

          {#if actionError}
            <p class="text-[11px] text-red-300">{actionError}</p>
          {/if}

          <div class="flex items-center gap-2 pt-1">
            <button
              type="button"
              class="rounded-lg bg-purple-500/30 px-3 py-1.5 text-xs font-medium text-purple-100 transition-colors hover:bg-purple-500/40 disabled:opacity-40"
              on:click={save}
              disabled={saving}
            >{saving ? 'Saving…' : 'Save'}</button>
            <button
              type="button"
              class="rounded-lg border border-[#2a2a3a] px-3 py-1.5 text-xs text-[var(--text-primary)] transition-colors hover:text-white disabled:opacity-40"
              on:click={cancelEditing}
              disabled={saving}
            >Cancel</button>
            {#if hasOrigin}
              <button
                type="button"
                class="ml-auto text-[11px] text-red-300/80 hover:text-red-300 disabled:opacity-40"
                on:click={deleteInfo}
                disabled={saving}
              >Remove all</button>
            {/if}
          </div>
        </div>
      {:else if hasOrigin && annotation}
        {#if annotation.description}
          <p class="mb-3 whitespace-pre-wrap break-words text-sm leading-relaxed text-[var(--text-primary)]">{annotation.description}</p>
        {/if}
        {#if annotation.links.length}
          <ul class="mb-3 space-y-1.5">
            {#each annotation.links as link (link.url + link.kind)}
              <li class="flex items-start gap-2 text-sm">
                <span class="mt-0.5 shrink-0 rounded bg-white/5 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-[var(--text-secondary)]">{linkKindLabel(link.kind)}</span>
                <a href={link.url} target="_blank" rel="noopener noreferrer" class="min-w-0 break-words text-purple-300 hover:text-purple-200">
                  {link.label || link.url}
                </a>
              </li>
            {/each}
          </ul>
        {/if}
        {#if annotation.created_at}
          <p class="mb-3 text-xs text-[var(--text-muted)]">
            Annotated {formatRelativeDate(annotation.created_at)}
          </p>
        {/if}
      {:else}
        <p class="text-sm text-[var(--text-muted)]">No origin info yet.</p>
      {/if}

      <!-- Attachments — always visible when not editing -->
      {#if !editing && !loading && !error}
        <div class="mt-3 flex items-start gap-3">
          {#if annotation && annotation.attachments.length}
            <div class="flex flex-1 flex-wrap gap-1.5">
              {#each annotation.attachments as attachment (attachment.id)}
                <div class="group relative overflow-hidden rounded-lg border border-white/5 bg-black/30">
                  {#if attachment.media_type.startsWith('video/')}
                    <!-- svelte-ignore a11y-media-has-caption -->
                    <video src={filesApi.attachmentUrl(attachment.id)} class="h-16 w-20 object-cover" muted></video>
                  {:else}
                    <img src={filesApi.attachmentUrl(attachment.id)} alt={attachment.caption || attachment.file_name} class="h-16 w-20 object-cover" />
                  {/if}
                  <button
                    type="button"
                    class="absolute right-0.5 top-0.5 hidden h-5 w-5 place-items-center rounded bg-black/70 text-[10px] text-[var(--text-primary)] group-hover:grid hover:text-red-300"
                    title="Remove attachment"
                    aria-label="Remove attachment"
                    on:click={() => removeAttachment(attachment.id)}
                  >✕</button>
                </div>
              {/each}
            </div>
          {/if}
          <input
            bind:this={fileInput}
            type="file"
            accept="image/*,video/*"
            class="hidden"
            on:change={onUploadChange}
          />
          <button
            type="button"
            class="shrink-0 rounded-lg border border-dashed border-white/10 px-3 py-1.5 text-[11px] text-[var(--text-secondary)] transition-colors hover:border-purple-500/40 hover:text-purple-200 disabled:opacity-40"
            on:click={() => fileInput.click()}
            disabled={uploading}
          >{uploading ? 'Uploading…' : '+ Image / video'}</button>
        </div>
      {/if}
    </div>

    <!-- Details -->
    <div class="border-b border-white/5 px-5 py-4">
      <h3 class="mb-3 text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">Details</h3>
      <div class="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
        <div>
          <dt class="text-[11px] text-[var(--text-muted)]">Format</dt>
          <dd class="text-[var(--text-primary)]">{subject.isDir ? 'Folder' : (subject.ext || 'File').toUpperCase()}</dd>
        </div>
        <div>
          <dt class="text-[11px] text-[var(--text-muted)]">Size</dt>
          <dd class="text-[var(--text-primary)]">{subject.isDir ? '—' : formatSize(subject.size)}</dd>
        </div>
        {#if (mode === 'image' || mode === 'video') && (mediaWidth || mediaHeight)}
          <div>
            <dt class="text-[11px] text-[var(--text-muted)]">Dimensions</dt>
            <dd class="text-[var(--text-primary)]">{mediaWidth} × {mediaHeight}</dd>
          </div>
        {/if}
        <div>
          <dt class="text-[11px] text-[var(--text-muted)]">Modified</dt>
          <dd class="text-[var(--text-primary)]">
            {formatDate(subject.mtime, true)}
            {#if subject.mtime !== null}
              <span class="text-[11px] text-[var(--text-muted)]"> · {formatRelativeDate(subject.mtime, true)}</span>
            {/if}
          </dd>
        </div>
        <div>
          <dt class="text-[11px] text-[var(--text-muted)]">Added</dt>
          <dd class="text-[var(--text-primary)]">
            {formatDate(indexedAt)}
            {#if indexedAt}
              <span class="text-[11px] text-[var(--text-muted)]"> · {formatRelativeDate(indexedAt)}</span>
            {/if}
          </dd>
        </div>
        <div>
          <dt class="text-[11px] text-[var(--text-muted)]">MD5</dt>
          <dd class="truncate font-mono text-xs text-[var(--text-secondary)]" title={annotation?.content_hash ?? ''}>{annotation?.content_hash ?? 'not computed'}</dd>
        </div>
      </div>
      <div class="mt-3">
        <dt class="text-[11px] text-[var(--text-muted)]">Path</dt>
        <dd>
          <button
            type="button"
            class="mt-0.5 w-full break-words text-left font-mono text-xs leading-relaxed text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            title="Click to copy"
            on:click={copyPath}
          >{subject.absolutePath}</button>
        </dd>
      </div>
    </div>

    <!-- Archive contents -->
    {#if canListArchive}
      <div class="border-b border-white/5 px-5 py-4">
        <div class="mb-2 flex items-center justify-between">
          <h3 class="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">Contents</h3>
          {#if archive === null && !archiveLoading}
            <button
              type="button"
              class="text-xs text-purple-300 hover:text-purple-200"
              on:click={loadArchive}
            >Show contents</button>
          {/if}
        </div>

        {#if archiveLoading}
          <p class="text-sm text-[var(--text-muted)]">Reading…</p>
        {:else if archiveError}
          <p class="text-sm text-red-300">{archiveError}</p>
        {:else if archive}
          <p class="mb-2 text-xs text-[var(--text-muted)]">
            {archive.total_entries} item{archive.total_entries === 1 ? '' : 's'} ·
            {formatSize(archive.total_size)} unpacked · {formatSize(archive.compressed_size)} stored
          </p>
          <ul class="max-h-48 overflow-y-auto rounded-lg bg-black/20 p-1.5">
            {#each archive.entries as entry (entry.name)}
              <li class="flex items-baseline gap-2 px-1.5 py-0.5 text-xs">
                <span class="min-w-0 flex-1 truncate font-mono text-[var(--text-primary)]" title={entry.name}>
                  {entry.is_dir ? '📁' : ''}{entry.name}
                </span>
                {#if !entry.is_dir}
                  <span class="shrink-0 text-[10px] text-[var(--text-muted)]">{formatSize(entry.size)}</span>
                {/if}
              </li>
            {/each}
          </ul>
          {#if archive.truncated}
            <p class="mt-1 text-[10px] text-[var(--text-muted)]">
              Showing the first {archive.entries.length} of {archive.total_entries}.
            </p>
          {/if}
        {/if}
      </div>
    {/if}

    {#if actionError && !editing}
      <p class="px-5 py-2 text-[11px] text-red-300">{actionError}</p>
    {/if}
  </div>

  <!-- Footer actions -->
  <div class="flex gap-2 border-t border-white/5 px-5 py-3">
    <button
      type="button"
      class="flex-1 rounded-lg border border-[#2a2a3a] bg-[#1e1e2e] px-3 py-2 text-sm text-[var(--text-primary)] transition-colors hover:border-purple-500/50 hover:text-white"
      on:click={openExternally}
    >Open</button>
    <button
      type="button"
      class="flex-1 rounded-lg border border-[#2a2a3a] bg-[#1e1e2e] px-3 py-2 text-sm text-[var(--text-primary)] transition-colors hover:border-purple-500/50 hover:text-white"
      on:click={reveal}
    >Show in folder</button>
    <button
      type="button"
      class="flex-1 rounded-lg border border-[#2a2a3a] bg-[#1e1e2e] px-3 py-2 text-sm text-[var(--text-primary)] transition-colors hover:border-purple-500/50 hover:text-white"
      on:click={copyPath}
    >Copy path</button>
  </div>
</div>
