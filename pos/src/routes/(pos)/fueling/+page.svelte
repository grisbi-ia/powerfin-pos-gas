<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import Header from '$lib/components/Header.svelte';

	// Mock imports
	import { connectToEvents } from '$lib/api/bridge.mock';

	let orderId = '';
	let dispenserId = 0;
	let presetAmount = 0;
	let unitPrice = 0;
	let customerName = '';
	let priceList = 'STANDARD';

	let currentVolume = 0;
	let currentAmount = 0;
	let dispenserStatus = 'AUTHORIZED';
	let eventSource: { close: () => void } | null = null;

	$: progressPct = presetAmount > 0 ? Math.min(100, (currentAmount / presetAmount) * 100) : 0;
	$: remaining = presetAmount > 0 ? Math.max(0, presetAmount - currentAmount) : 0;
	$: estimatedVolume = unitPrice > 0 ? (currentAmount / unitPrice).toFixed(2) : '0.00';

	onMount(() => {
		orderId = $page.url.searchParams.get('order') ?? '';
		dispenserId = Number($page.url.searchParams.get('dispenser') ?? '0');
		presetAmount = parseFloat($page.url.searchParams.get('amount') ?? '0');
		unitPrice = parseFloat($page.url.searchParams.get('price') ?? '0');
		customerName = decodeURIComponent($page.url.searchParams.get('customerName') ?? '');
		priceList = $page.url.searchParams.get('priceList') ?? 'STANDARD';

		// Connect SSE to track progress
		eventSource = connectToEvents(
			(event, data) => {
				if (event === 'DELIVERY_PROGRESS' && (data.dispenserId as number) === dispenserId) {
					currentVolume = parseFloat(data.volume as string) || 0;
					currentAmount = parseFloat(data.amount as string) || 0;
				}

				if (event === 'PUMP_STATUS_CHANGE' && (data.dispenserId as number) === dispenserId) {
					dispenserStatus = data.status as string;
					if (dispenserStatus === 'IDLE' && currentAmount > 0) {
						// Sale completed — go to confirmation
						eventSource?.close();
						goto(`/confirmation?order=${orderId}&dispenser=${dispenserId}&amount=${currentAmount.toFixed(2)}&volume=${estimatedVolume}&preset=${presetAmount}&price=${unitPrice}&customerName=${encodeURIComponent(customerName)}&priceList=${priceList}`);
					}
				}
			}
		);
	});

	onDestroy(() => {
		eventSource?.close();
	});
</script>

<Header title="Despachando" showBack={false} />

<main class="flex-1 flex flex-col items-center justify-center px-6 py-8">
	<div class="w-full max-w-sm">
		<!-- Status indicator -->
		<div class="text-center mb-8">
			<div class="w-24 h-24 mx-auto mb-4 rounded-full border-4 {dispenserStatus === 'FUELLING' ? 'border-blue-500 animate-pulse' : 'border-purple-500'} flex items-center justify-center">
				{#if dispenserStatus === 'FUELLING'}
					<svg class="w-12 h-12 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
							d="M13 10V3L4 14h7v7l9-11h-7z" />
					</svg>
				{:else}
					<svg class="w-12 h-12 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
							d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
					</svg>
				{/if}
			</div>
			<h2 class="text-lg font-semibold text-gray-700">
				{dispenserStatus === 'AUTHORIZED' ? 'Surtidor autorizado' :
				 dispenserStatus === 'STARTING' ? 'Iniciando despacho...' :
				 dispenserStatus === 'FUELLING' ? 'Despachando...' :
				 dispenserStatus === 'PAUSED' ? 'Despacho pausado' :
				 'Completando...'}
			</h2>
			<p class="text-sm text-gray-500 mt-1">Surtidor {dispenserId}</p>
		</div>

		<!-- Progress bar -->
		<div class="mb-6">
			<div class="flex justify-between text-sm text-gray-500 mb-1">
				<span>${currentAmount.toFixed(2)}</span>
				<span>${presetAmount.toFixed(2)}</span>
			</div>
			<div class="w-full h-4 bg-gray-200 rounded-full overflow-hidden">
				<div
					class="h-full rounded-full transition-all duration-500
						{dispenserStatus === 'FUELLING' ? 'bg-blue-500' : 'bg-purple-500'}"
					style="width: {progressPct}%"
				></div>
			</div>
		</div>

		<!-- Live data -->
		<div class="card p-4 space-y-3">
			<div class="flex justify-between">
				<span class="text-sm text-gray-500">Volumen</span>
				<span class="text-sm font-semibold">{estimatedVolume} L</span>
			</div>
			<div class="flex justify-between">
				<span class="text-sm text-gray-500">Monto</span>
				<span class="text-sm font-semibold">${currentAmount.toFixed(2)}</span>
			</div>
			<div class="flex justify-between">
				<span class="text-sm text-gray-500">Restante</span>
				<span class="text-sm font-semibold">${remaining.toFixed(2)}</span>
			</div>
			<div class="flex justify-between">
				<span class="text-sm text-gray-500">Precio</span>
				<span class="text-sm font-semibold">${unitPrice.toFixed(3)}/L</span>
			</div>
		</div>

		<!-- Tip -->
		<div class="text-center mt-6">
			<p class="text-xs text-gray-400">
				{dispenserStatus === 'AUTHORIZED' ? 'Levante la pistola para iniciar el despacho' :
				 dispenserStatus === 'FUELLING' ? 'El despacho está en curso...' :
				 'Cuelgue la pistola para finalizar'}
			</p>
		</div>
	</div>
</main>
