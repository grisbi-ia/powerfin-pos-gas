<script lang="ts" generics="T extends Record<string, any>">
  import { ChevronLeft, ChevronRight } from 'lucide-svelte';

  let { page = 1, pages = 1, total = 0, onPage = (_p: number) => {} } = $props();

  function pages_(): number[] {
    const p: number[] = [];
    const start = Math.max(1, page - 2);
    const end = Math.min(pages, page + 2);
    for (let i = start; i <= end; i++) p.push(i);
    return p;
  }
</script>

{#if pages > 1}
  <div class="px-4 py-3 border-t border-gray-200 flex items-center justify-between">
    <span class="text-sm text-gray-500">{total} resultados</span>
    <div class="flex items-center gap-1">
      <button class="p-2 text-gray-500 hover:text-gray-700 rounded-md disabled:opacity-30"
              disabled={page <= 1} onclick={() => onPage(page - 1)}>
        <ChevronLeft class="w-4 h-4" />
      </button>
      {#each pages_() as p}
        <button class="w-8 h-8 text-sm rounded-md transition-colors
                       {p === page ? 'bg-primary-500 text-white' : 'text-gray-600 hover:bg-gray-100'}"
                onclick={() => onPage(p)}>
          {p}
        </button>
      {/each}
      <button class="p-2 text-gray-500 hover:text-gray-700 rounded-md disabled:opacity-30"
              disabled={page >= pages} onclick={() => onPage(page + 1)}>
        <ChevronRight class="w-4 h-4" />
      </button>
    </div>
  </div>
{/if}
