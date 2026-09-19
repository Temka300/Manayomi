<script lang="ts">
  import type { RedditOutboundLink } from '../../lib/redditApi';

  export let links: RedditOutboundLink[] = [];
</script>

{#if links.length}
  <section class="mx-4 mb-3 space-y-2" aria-label="Linked files and pages">
    {#each links as link (link.url)}
      <a
        href={link.url}
        target="_blank"
        rel="noopener noreferrer"
        class="flex min-w-0 items-center gap-3 overflow-hidden rounded-lg border border-[#343536] bg-[#111213] px-3 py-2.5 hover:border-[#5a5b62] hover:bg-[#18191a]"
      >
        <span class="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-[#272729] text-[#4fbcff]">
          <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M10 13a5 5 0 007.1 0l2-2a5 5 0 00-7.1-7.1l-1.1 1.1M14 11a5 5 0 00-7.1 0l-2 2A5 5 0 0012 20.1l1.1-1.1" />
          </svg>
        </span>
        <span class="min-w-0 flex-1">
          <span class="block truncate text-xs text-[#818384]">{link.host}</span>
          <span class="block truncate text-sm font-medium text-[#d7dadc]">{link.label}</span>
        </span>
        <span class="shrink-0 rounded-full bg-[#272729] px-2 py-1 text-[10px] font-semibold text-[#a7a8aa]">
          {link.download_kind ? 'Linked file' : 'Open link'}
        </span>
      </a>
    {/each}
  </section>
{/if}
