<script lang="ts">
  import { Calendar, CalendarDays, TrendingUp } from 'lucide-svelte';
  import type { Period } from './types';

  let { mode = 'daily' as Period, onchange }: {
    mode: Period;
    onchange: (m: Period) => void;
  } = $props();

  const modes: { key: Period; label: string; icon: typeof Calendar }[] = [
    { key: 'daily', label: 'Diario', icon: Calendar },
    { key: 'monthly', label: 'Mensual', icon: CalendarDays },
    { key: 'annual', label: 'Anual', icon: TrendingUp },
  ];
</script>

<div class="flex bg-gray-100 rounded-lg p-1">
  {#each modes as m}
    <button
      class="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md transition-colors
             {mode === m.key
               ? 'bg-white text-gray-900 shadow-sm'
               : 'text-gray-500 hover:text-gray-700'}"
      onclick={() => onchange(m.key)}
    >
      <m.icon class="w-4 h-4" />
      {m.label}
    </button>
  {/each}
</div>
