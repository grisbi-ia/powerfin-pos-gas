<script lang="ts">
  let { title = '', value = '', icon: IconComponent = null as any, color = 'blue' as 'blue'|'green'|'purple'|'orange' } = $props();

  const colorMap = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    purple: 'bg-purple-50 text-purple-600',
    orange: 'bg-orange-50 text-orange-600',
  };
</script>

<div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 md:p-6">
  <div class="flex items-center gap-3">
    <div class="w-10 h-10 rounded-lg flex items-center justify-center {colorMap[color]}">
      {#if IconComponent}
        <IconComponent class="w-5 h-5" />
      {/if}
    </div>
    <div>
      <p class="text-sm text-gray-500">{title}</p>
      <p class="text-xl md:text-2xl font-bold text-gray-900">{value}</p>
    </div>
  </div>
</div>
