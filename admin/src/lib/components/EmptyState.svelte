<script lang="ts">
  let { message = 'No se encontraron resultados.' } = $props();
</script>

<div class="flex flex-col items-center justify-center py-12 text-center px-4">
  <div class="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center mb-4">
    <span class="text-2xl">📭</span>
  </div>
  <h3 class="text-sm font-medium text-gray-900 mb-1">Sin resultados</h3>
  <p class="text-sm text-gray-500 max-w-sm">{message}</p>
</div>
