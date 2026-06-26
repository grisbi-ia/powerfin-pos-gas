<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { ChevronLeft, ChevronRight } from 'lucide-svelte';
  import type { ChipItem } from './types';

  let {
    items = [] as ChipItem[],
    selectedValue = '',
    onselect,
  }: {
    items: ChipItem[];
    selectedValue: string;
    onselect: (value: string) => void;
  } = $props();

  let scrollerEl = $state<HTMLDivElement>();

  function scrollToActive() {
    if (!scrollerEl) return;
    const activeEl = scrollerEl.querySelector('[data-active="true"]');
    if (activeEl) {
      activeEl.scrollIntoView({ inline: 'center', behavior: 'smooth', block: 'nearest' });
    }
  }

  function scrollLeft() {
    if (!scrollerEl) return;
    scrollerEl.scrollBy({ left: -120, behavior: 'smooth' });
  }

  function scrollRight() {
    if (!scrollerEl) return;
    scrollerEl.scrollBy({ left: 120, behavior: 'smooth' });
  }

  onMount(() => { scrollToActive(); });

  // Re-scroll when selectedValue changes externally (mode change)
  $effect(() => {
    selectedValue;
    tick().then(() => scrollToActive());
  });
</script>

<div class="flex items-center gap-1">
  <button
    class="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center
           text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
    onclick={scrollLeft}
    aria-label="Desplazar izquierda"
  >
    <ChevronLeft class="w-4 h-4" />
  </button>

  <div
    bind:this={scrollerEl}
    class="flex-1 flex gap-1.5 overflow-x-auto scroll-smooth pb-2 px-1
           [&::-webkit-scrollbar]:h-0.5
           [&::-webkit-scrollbar-track]:bg-transparent
           [&::-webkit-scrollbar-thumb]:bg-gray-300
           [&::-webkit-scrollbar-thumb]:rounded-full"
  >
    {#each items as item}
      <button
        data-active={item.value === selectedValue}
        class="flex-shrink-0 flex flex-col items-center justify-center
               w-10 h-10 rounded-full text-sm font-medium
               transition-colors relative
               {item.value === selectedValue
                 ? 'bg-primary-500 text-white shadow-sm'
                 : item.isPast === false
                   ? 'bg-gray-50 text-gray-300 cursor-default'
                   : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}"
        onclick={() => item.isPast !== false && onselect(item.value)}
        disabled={item.isPast === false}
      >
        {item.label}
        {#if item.sublabel}
          <span class="absolute -bottom-3.5 text-[10px] leading-none
                       {item.value === selectedValue ? 'text-primary-500 font-semibold' : 'text-gray-400'}">
            {item.sublabel}
          </span>
        {/if}
      </button>
    {/each}
  </div>

  <button
    class="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center
           text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
    onclick={scrollRight}
    aria-label="Desplazar derecha"
  >
    <ChevronRight class="w-4 h-4" />
  </button>
</div>
