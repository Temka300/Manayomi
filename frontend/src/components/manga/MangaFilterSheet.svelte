<script lang="ts">
  import { createEventDispatcher, tick } from 'svelte';

  export let open = false;
  export let title = 'Filters';
  export let values: Record<string, string> = {};
  export let hasActive = false;
  export let sort = 'recent';
  export let language = 'all';

  const dispatch = createEventDispatcher<{
    close: void;
    apply: void;
    clear: void;
    change: { key: string; value: string };
    sortChange: string;
    languageChange: string;
  }>();

  const FIELDS = [
    { key: 'tags', label: 'Tags' },
    { key: 'categories', label: 'Categories' },
    { key: 'groups', label: 'Groups' },
    { key: 'artists', label: 'Artists' },
    { key: 'parodies', label: 'Parodies' },
    { key: 'characters', label: 'Characters' }
  ];

  let panel: HTMLElement;
  let wasOpen = false;

  $: if (open && !wasOpen) {
    wasOpen = true;
    void tick().then(() => panel?.querySelector<HTMLInputElement>('input')?.focus());
  } else if (!open) {
    wasOpen = false;
  }

  function onWindowKeydown(event: KeyboardEvent) {
    if (open && event.key === 'Escape') dispatch('close');
  }

  function onWindowClick(event: MouseEvent) {
    if (open && panel && !panel.contains(event.target as Node)) dispatch('close');
  }
</script>

<svelte:window on:keydown={onWindowKeydown} on:click={onWindowClick} />

{#if open}
  <div
    class="filter-popover absolute left-0 top-full z-[70] mt-2 overflow-y-auto rounded-xl border border-[#303046] bg-[#111119] shadow-2xl shadow-black/60"
    role="dialog"
    aria-label={title}
    tabindex="-1"
    bind:this={panel}
  >
    <header class="flex items-center justify-between border-b border-[#29293d] px-2.5 py-2">
      <h2 class="text-xs font-semibold text-purple-100">{title}</h2>
      <button
        type="button"
        class="grid h-6 w-6 place-items-center rounded-full text-xs text-gray-500 hover:bg-white/5 hover:text-purple-100"
        aria-label="Close {title}"
        on:click={() => dispatch('close')}
      >✕</button>
    </header>

    <form class="p-2.5" on:submit|preventDefault={() => dispatch('apply')}>
      <div class="mb-2 grid grid-cols-2 gap-1.5">
        <label class="grid gap-0.5">
          <span class="text-[10px] font-semibold uppercase tracking-wide text-gray-500">Sort</span>
          <select class="h-7 min-w-0 rounded-md border border-[#2c2c40] bg-[#171721] px-1.5 text-xs text-gray-100" value={sort} on:change={(event) => dispatch('sortChange', event.currentTarget.value)}>
            <option value="recent">Newest</option>
            <option value="popular-today">Popular today</option>
            <option value="popular-week">Popular this week</option>
            <option value="popular-month">Popular this month</option>
            <option value="popular">Popular all-time</option>
          </select>
        </label>
        <label class="grid gap-0.5">
          <span class="text-[10px] font-semibold uppercase tracking-wide text-gray-500">Language</span>
          <select class="h-7 min-w-0 rounded-md border border-[#2c2c40] bg-[#171721] px-1.5 text-xs text-gray-100" value={language} on:change={(event) => dispatch('languageChange', event.currentTarget.value)}>
            <option value="all">All languages</option>
            <option value="english">English</option>
            <option value="japanese">Japanese</option>
            <option value="chinese">Chinese</option>
          </select>
        </label>
      </div>
      <div class="grid gap-1.5">
        {#each FIELDS as field (field.key)}
          <label class="grid gap-0.5">
            <span class="text-[10px] font-semibold uppercase tracking-wide text-gray-500">{field.label}</span>
            <input
              class="h-7 w-full rounded-md border border-[#2c2c40] bg-[#171721] px-2 text-xs text-gray-100 placeholder-gray-600 focus:border-purple-500/70 focus:outline-none"
              placeholder="e.g. four word tag"
              value={values[field.key] ?? ''}
              on:input={(event) => dispatch('change', {
                key: field.key,
                value: (event.currentTarget as HTMLInputElement).value
              })}
            />
          </label>
        {/each}
      </div>

      <div class="mt-2.5 flex items-center justify-end gap-1.5">
        {#if hasActive}
          <button
            type="button"
            class="rounded-md px-2 py-1.5 text-[11px] text-gray-400 hover:text-gray-200"
            on:click={() => dispatch('clear')}
          >Clear</button>
        {/if}
        <button
          type="submit"
          class="rounded-md bg-purple-600 px-3 py-1.5 text-[11px] font-semibold text-white hover:bg-purple-500"
        >Apply</button>
      </div>
    </form>
  </div>
{/if}

<style>
  .filter-popover {
    width: min(17rem, calc(100vw - 1rem));
    max-height: min(28rem, calc(100dvh - 8rem));
    transform-origin: left top;
    animation: filter-popover-in 180ms cubic-bezier(0.22, 1, 0.36, 1);
  }

  @keyframes filter-popover-in {
    from {
      opacity: 0;
      transform: translate3d(-0.75rem, -0.2rem, 0) scaleX(0.96);
    }
    to {
      opacity: 1;
      transform: translate3d(0, 0, 0) scaleX(1);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .filter-popover {
      animation-duration: 1ms;
    }
  }
</style>
