<script lang="ts">
  import { createEventDispatcher, onMount, tick } from 'svelte';
  import { focusTrap } from '../../lib/focusTrap';
  import type { ActionMenuItem } from '../../lib/ui';

  export let open = false;
  export let items: ActionMenuItem[] = [];
  export let x: number | null = null;
  export let y: number | null = null;
  export let align: 'start' | 'end' = 'end';
  export let label = 'Actions';

  const dispatch = createEventDispatcher<{ close: void }>();
  let menu: HTMLElement | null = null;
  let busy = '';
  let position = '';
  let placementVersion = 0;

  $: if (open) void placeMenu(x, y, items.length);

  onMount(() => {
    if (open) void placeMenu(x, y, items.length);
    function outside(event: PointerEvent): void {
      if (open && menu && !menu.contains(event.target as Node)) dispatch('close');
    }
    window.addEventListener('pointerdown', outside, true);
    return () => window.removeEventListener('pointerdown', outside, true);
  });

  async function placeMenu(nextX: number | null, nextY: number | null, _itemCount: number): Promise<void> {
    const version = ++placementVersion;
    await tick();
    if (version !== placementVersion) return;
    if (!menu || nextX === null || nextY === null) {
      position = '';
      return;
    }
    position = 'position:fixed;left:0;top:0;visibility:hidden;';
    await tick();
    if (version !== placementVersion || !menu) return;
    const bounds = menu.getBoundingClientRect();
    const left = Math.max(8, Math.min(window.innerWidth - bounds.width - 8, nextX));
    const top = Math.max(8, Math.min(window.innerHeight - bounds.height - 8, nextY));
    position = `position:fixed;left:${left}px;top:${top}px;`;
  }

  async function run(item: ActionMenuItem): Promise<void> {
    if (item.disabled || busy) return;
    busy = item.id;
    try {
      await item.run();
      dispatch('close');
    } finally {
      busy = '';
    }
  }
</script>

{#if open}
  <div
    bind:this={menu}
    use:focusTrap={{ close: () => dispatch('close'), initialFocus: '[role="menuitem"]:not([disabled])' }}
    class="z-[260] min-w-[220px] overflow-hidden rounded-xl border border-white/10 bg-[var(--bg-elevated)]/98 p-1.5 text-[var(--text-primary)] shadow-2xl shadow-black/70 backdrop-blur-xl {x === null ? `absolute top-full mt-2 ${align === 'end' ? 'right-0' : 'left-0'}` : ''}"
    style={position}
    role="menu"
    aria-label={label}
    tabindex="-1"
    on:contextmenu|preventDefault
  >
    {#each items as item (item.id)}
      {#if item.separatorBefore}<div class="my-1 h-px bg-white/7" role="separator"></div>{/if}
      <button
        type="button"
        role="menuitem"
        class="flex w-full items-start gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-35 {item.danger ? 'text-red-300 hover:bg-red-500/10' : 'text-[var(--text-primary)] hover:bg-white/7 hover:text-white'}"
        disabled={item.disabled || Boolean(busy)}
        on:click={() => run(item)}
      >
        {#if item.icon}<span class="mt-px w-4 shrink-0 text-center opacity-70">{item.icon}</span>{/if}
        <span class="min-w-0 flex-1">
          <span class="block font-medium">{busy === item.id ? 'Working…' : item.label}</span>
          {#if item.description}<span class="mt-0.5 block text-[11px] leading-snug opacity-50">{item.description}</span>{/if}
        </span>
      </button>
    {/each}
  </div>
{/if}
