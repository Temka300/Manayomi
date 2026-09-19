<script lang="ts">
  import { dismissToast, toasts, type ToastMessage } from '../../lib/ui';

  let runningAction = '';

  function toneClasses(tone: ToastMessage['tone']): string {
    if (tone === 'success') return 'border-emerald-300/25 bg-[#0d1b18] text-emerald-100';
    if (tone === 'warning') return 'border-amber-300/25 bg-[#1d190f] text-amber-100';
    if (tone === 'error') return 'border-red-300/30 bg-[#211114] text-red-100';
    return 'border-purple-300/25 bg-[#151322] text-purple-100';
  }

  function progressClasses(tone: ToastMessage['tone']): string {
    if (tone === 'success') return 'bg-emerald-300';
    if (tone === 'warning') return 'bg-amber-300';
    if (tone === 'error') return 'bg-red-300';
    return 'bg-purple-300';
  }

  async function runAction(toast: ToastMessage): Promise<void> {
    if (!toast.action || runningAction) return;
    runningAction = toast.id;
    try {
      await toast.action.run();
      dismissToast(toast.id);
    } finally {
      runningAction = '';
    }
  }
</script>

<div
  class="pointer-events-none fixed inset-x-3 top-3 z-[300] flex flex-col items-end gap-2 sm:inset-x-auto sm:right-4 sm:top-4 sm:w-[380px]"
  aria-live="polite"
  aria-label="Notifications"
>
  {#each $toasts as toast (toast.id)}
    <section
      class="pointer-events-auto w-full overflow-hidden rounded-2xl border shadow-2xl shadow-black/45 backdrop-blur-xl {toneClasses(toast.tone)}"
      role={toast.tone === 'error' ? 'alert' : 'status'}
    >
      <div class="flex items-start gap-3 px-4 py-3.5">
        <span class="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-white/7 text-xs font-bold">
          {toast.tone === 'success' ? '✓' : toast.tone === 'error' ? '!' : toast.tone === 'warning' ? '!' : 'i'}
        </span>
        <div class="min-w-0 flex-1">
          <h2 class="text-sm font-semibold">{toast.title}</h2>
          {#if toast.message}<p class="mt-1 break-words text-xs leading-relaxed opacity-65">{toast.message}</p>{/if}
          {#if toast.action}
            <button
              type="button"
              class="mt-2 rounded-lg border border-current/20 bg-white/5 px-2.5 py-1.5 text-xs font-semibold hover:bg-white/10 disabled:opacity-50"
              disabled={runningAction === toast.id}
              on:click={() => runAction(toast)}
            >
              {runningAction === toast.id ? 'Working…' : toast.action.label}
            </button>
          {/if}
        </div>
        <button
          type="button"
          class="grid h-7 w-7 shrink-0 place-items-center rounded-lg opacity-55 hover:bg-white/8 hover:opacity-100"
          aria-label="Dismiss notification"
          on:click={() => dismissToast(toast.id)}
        >×</button>
      </div>
      {#if toast.progress !== undefined}
        <div class="h-1 bg-black/20">
          <div
            class="h-full transition-[width] duration-300 {progressClasses(toast.tone)}"
            style="width: {Math.max(0, Math.min(1, toast.progress)) * 100}%"
          ></div>
        </div>
      {/if}
    </section>
  {/each}
</div>

