<script lang="ts">
  let { status = '', label = status } = $props();

  const badgeMap: Record<string, { bg: string; text: string; dot: string }> = {
    ACTIVE:    { bg: 'bg-green-50', text: 'text-green-700', dot: 'bg-green-500' },
    INACTIVE:  { bg: 'bg-red-50', text: 'text-red-700', dot: 'bg-red-500' },
    true:      { bg: 'bg-green-50', text: 'text-green-700', dot: 'bg-green-500' },
    false:     { bg: 'bg-red-50', text: 'text-red-700', dot: 'bg-red-500' },
    COMPLETED:  { bg: 'bg-green-50', text: 'text-green-700', dot: 'bg-green-500' },
    COLLECTED:  { bg: 'bg-green-50', text: 'text-green-700', dot: 'bg-green-500' },
    CANCELLED:  { bg: 'bg-red-50', text: 'text-red-700', dot: 'bg-red-500' },
    OPEN:       { bg: 'bg-yellow-50', text: 'text-yellow-700', dot: 'bg-yellow-500' },
    CLOSED:     { bg: 'bg-gray-50', text: 'text-gray-600', dot: 'bg-gray-400' },
    AUTHORIZED: { bg: 'bg-blue-50', text: 'text-blue-700', dot: 'bg-blue-500' },
    PENDING:    { bg: 'bg-yellow-50', text: 'text-yellow-700', dot: 'bg-yellow-500' },
    DEFAULT:    { bg: 'bg-blue-50', text: 'text-blue-700', dot: 'bg-blue-500' },
  };

  let key = $derived(typeof status === 'boolean' ? String(status) : status);
  let b = $derived(badgeMap[key] || badgeMap.DEFAULT);
</script>

<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium {b.bg} {b.text}">
  <span class="w-1.5 h-1.5 rounded-full {b.dot}"></span>
  {label}
</span>
