<script lang="ts">
  import { createEventDispatcher, onMount, tick } from 'svelte';
  import { focusTrap } from '../../lib/focusTrap';

  export let title = 'Name this item';
  export let description = '';
  export let label = 'Name';
  export let confirmLabel = 'Save';
  export let initialValue = '';
  export let busy = false;
  export let error = '';

  const dispatch = createEventDispatcher<{ close: void; submit: string }>();
  let value = initialValue;
  let input: HTMLInputElement | null = null;

  onMount(async () => {
    await tick();
    input?.focus();
    input?.select();
  });

  function close() {
    if (!busy) dispatch('close');
  }

  function submit() {
    const clean = value.trim();
    if (clean && !busy) dispatch('submit', clean);
  }
</script>

<div class="fixed inset-0 z-[150] grid place-items-center bg-black/70 p-4 backdrop-blur-sm" role="presentation" on:click={(event) => { if (event.target === event.currentTarget) close(); }}>
  <div
    class="w-full max-w-md rounded-2xl border border-white/10 bg-[#17151d] p-5 text-white shadow-2xl"
    role="dialog"
    aria-modal="true"
    aria-labelledby="language-name-dialog-title"
    tabindex="-1"
    use:focusTrap={{ close }}
  >
    <div class="flex items-start gap-4">
      <div class="min-w-0 flex-1">
        <h2 id="language-name-dialog-title" class="text-lg font-bold text-amber-50">{title}</h2>
        {#if description}<p class="mt-1 text-xs leading-5 text-white/40">{description}</p>{/if}
      </div>
      <button type="button" class="grid h-8 w-8 place-items-center rounded-full text-white/40 hover:bg-white/7 hover:text-white" aria-label="Close dialog" on:click={close}>×</button>
    </div>
    <form class="mt-5" on:submit|preventDefault={submit}>
      <label for="language-name-value" class="text-[10px] font-semibold uppercase tracking-wider text-white/35">{label}</label>
      <input
        id="language-name-value"
        bind:this={input}
        bind:value
        maxlength="120"
        autocomplete="off"
        class="mt-2 h-11 w-full rounded-xl border border-white/10 bg-black/25 px-3 text-sm outline-none focus:border-amber-300/45"
      />
      {#if error}<p class="mt-3 text-xs text-red-300">{error}</p>{/if}
      <div class="mt-5 flex justify-end gap-2">
        <button type="button" class="rounded-xl border border-white/10 px-4 py-2 text-xs text-white/55 hover:bg-white/5" on:click={close}>Cancel</button>
        <button type="submit" class="rounded-xl bg-amber-300 px-4 py-2 text-xs font-bold text-[#251a05] disabled:opacity-40" disabled={busy || !value.trim()}>{busy ? 'Saving…' : confirmLabel}</button>
      </div>
    </form>
  </div>
</div>
