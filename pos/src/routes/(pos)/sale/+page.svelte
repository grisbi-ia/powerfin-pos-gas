<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { pendingOrders, orderByHose } from '$lib/stores/pendingOrders';
	import SaleWizard from '$lib/components/SaleWizard.svelte';
	import type { PendingOrder } from '$lib/stores/pendingOrders';

	let dispenserId = 0;
	let side: 'A' | 'B' = 'A';
	let mode: 'sale' | 'collect' = 'sale';
	let collectOrder: PendingOrder | null = null;

	$: {
		dispenserId = Number($page.url.searchParams.get('dispenser') ?? '0');
		side = ($page.url.searchParams.get('side') ?? 'A') as 'A' | 'B';
		mode = ($page.url.searchParams.get('mode') ?? 'sale') as 'sale' | 'collect';

		if (mode === 'collect') {
			const orderId = $page.url.searchParams.get('order') ?? '';
			const hoseId = Number($page.url.searchParams.get('hose') ?? '0');
			const key = `${dispenserId}-${hoseId}`;
			collectOrder = $orderByHose.get(key) ?? $pendingOrders.get(orderId) ?? null;
		}
	}

	function handleDone() {
		goto('/');
	}
</script>

<SaleWizard {dispenserId} {side} {mode} {collectOrder} on:done={handleDone} />
