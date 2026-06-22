<script lang="ts">
  import { AlertCircle, X } from 'lucide-svelte';

  let { message = 'Error al cargar datos.', onRetry = null as (() => void) | null } = $props();

  let visible = $state(true);
</script>

{#if visible}
  <div class="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
    <AlertCircle class="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
    <div class="flex-1">
      <h4 class="text-sm font-medium text-red-800">Error</h4>
      <p class="text-sm text-red-600 mt-1">{message}</p>
      {#if onRetry}
        <button class="mt-2 text-sm font-medium text-red-700 hover:text-red-800 underline"
                onclick={onRetry}>Reintentar</button>
      {/if}
    </div>
    <button class="text-red-400 hover:text-red-600" onclick={() => visible = false}>
      <X class="w-4 h-4" />
    </button>
  </div>
{/if}
