<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import Header from '$lib/components/Header.svelte';
	import PrintPrompt from '$lib/components/PrintPrompt.svelte';
	import type { PrintPolicy } from '$lib/api/types';
	import { config } from '$lib/stores/config';
	import { pendingOrders } from '$lib/stores/pendingOrders';

	// Mock imports
	import * as bridge from '$lib/api/bridge.mock';

	let orderId = '';
	let dispenserId = 0;
	let hoseId = 0;
	let side: 'A' | 'B' = 'A';
	let finalAmount = 0;
	let finalVolume = '';
	let presetAmount = 0;
	let unitPrice = 0;
	let customerName = '';
	let priceList = '';
	let plate = '';
	let printPolicy: PrintPolicy = 'ASK';
	let printing = false;
	let paymentMethod = '';
	let confirmed = false;
	let referenceCode = '';

	$: paymentMethods = $config?.payment_methods ?? [{ code: 'EFECTIVO', name: 'Efectivo', requires_reference: false }];
	$: selectedMethod = paymentMethods.find(m => m.code === paymentMethod);
	$: needsReference = selectedMethod?.requires_reference ?? false;

	$: change = presetAmount > 0 ? Math.max(0, presetAmount - finalAmount) : 0;
	$: canConfirm = paymentMethod !== '' && (!needsReference || referenceCode.trim() !== '');

	onMount(async () => {
		orderId = $page.url.searchParams.get('order') ?? '';
		dispenserId = Number($page.url.searchParams.get('dispenser') ?? '0');
		hoseId = Number($page.url.searchParams.get('hose') ?? '0');
		side = ($page.url.searchParams.get('side') ?? 'A') as 'A' | 'B';
		finalAmount = parseFloat($page.url.searchParams.get('amount') ?? '0');
		finalVolume = $page.url.searchParams.get('volume') ?? '0.00';
		presetAmount = parseFloat($page.url.searchParams.get('preset') ?? '0');
		unitPrice = parseFloat($page.url.searchParams.get('price') ?? '0');
		customerName = decodeURIComponent($page.url.searchParams.get('customerName') ?? '');
		priceList = $page.url.searchParams.get('priceList') ?? 'STANDARD';
		plate = decodeURIComponent($page.url.searchParams.get('plate') ?? '');

		// Fallback: if no URL data, load from pending orders store
		if (finalAmount === 0 && orderId) {
			const foundOrder = $pendingOrders.get(orderId);
			if (foundOrder) {
				dispenserId = foundOrder.dispenserId;
				hoseId = foundOrder.hoseId;
				side = foundOrder.side;
				// Mock: 85% of preset
				finalAmount = foundOrder.finalAmount || (foundOrder.presetAmount);
				finalVolume = foundOrder.finalVolume || ((foundOrder.presetAmount) / (foundOrder.unitPrice || 3.103)).toFixed(3);
				presetAmount = foundOrder.presetAmount;
				unitPrice = foundOrder.unitPrice;
				customerName = foundOrder.customerName;
				priceList = foundOrder.priceList;
				plate = foundOrder.plate;
			}
		}

		// Get print policy from bridge
		try {
			const policyResult = await bridge.getPrintPolicy();
			printPolicy = policyResult.policy as PrintPolicy;
		} catch {
			printPolicy = 'ASK';
		}
	});

	async function handleConfirm() {
		if (!paymentMethod) return;
		confirmed = true;

		if (printPolicy === 'ALWAYS') {
			await handlePrint();
		}
	}

	async function handlePrint() {
		printing = true;
		try {
			await bridge.printReceipt({
				type: 'FUEL_RECEIPT',
				dispenserId,
				fuelData: {
					dispenserId,
					orderId,
					volume: finalVolume,
					amount: finalAmount.toFixed(2),
					unitPrice: unitPrice.toFixed(3),
					paymentMethod,
					grade: 'SUPER'
				}
			});
		} finally {
			printing = false;
		}
	}

	function handleNewSale() {
		pendingOrders.removeOrder(orderId);
		goto('/');
	}
</script>

<Header title="Confirmar Venta" showBack={false} />

<main class="flex-1 px-4 py-6 overflow-y-auto">
	<div class="w-full max-w-sm mx-auto">
		<!-- Success icon -->
		<div class="text-center mb-6">
			<div class="w-20 h-20 mx-auto mb-3 rounded-full bg-green-100 flex items-center justify-center">
				<svg class="w-10 h-10 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
				</svg>
			</div>
			<h2 class="text-xl font-bold text-gray-800">Despacho Completado</h2>
			<p class="text-sm text-gray-500 mt-1">#{orderId}</p>
		</div>

		<!-- Sale summary -->
		<div class="card p-4 mb-4">
			<h3 class="text-sm font-semibold text-gray-700 mb-3">Resumen del despacho</h3>

			<div class="space-y-2">
				<div class="flex justify-between text-sm">
					<span class="text-gray-500">Surtidor</span>
					<span class="font-medium">{dispenserId} — Lado {side}</span>
				</div>
				{#if plate}
					<div class="flex justify-between text-sm">
						<span class="text-gray-500">Placa</span>
						<span class="font-medium font-mono">{plate}</span>
					</div>
				{/if}
				<div class="flex justify-between text-sm">
					<span class="text-gray-500">Volumen</span>
					<span class="font-medium">{finalVolume} L</span>
				</div>
				<div class="flex justify-between text-sm">
					<span class="text-gray-500">Precio unitario</span>
					<span class="font-medium">${unitPrice.toFixed(3)}</span>
				</div>
				{#if customerName}
					<div class="flex justify-between text-sm">
						<span class="text-gray-500">Cliente</span>
						<span class="font-medium">{customerName}</span>
					</div>
				{/if}
				{#if priceList !== 'STANDARD'}
					<div class="flex justify-between text-sm">
						<span class="text-gray-500">Lista</span>
						<span class="font-medium text-purple-600">{priceList}</span>
					</div>
				{/if}

				<hr class="border-gray-100" />

				<div class="flex justify-between text-lg font-bold">
					<span class="text-gray-700">Total a cobrar</span>
					<span class="text-primary">${finalAmount.toFixed(2)}</span>
				</div>
			</div>
		</div>

		<!-- Change -->
		{#if change > 0}
			<div class="card p-4 mb-4 bg-green-50 border-green-200">
				<div class="flex justify-between items-center">
					<span class="text-sm font-medium text-green-700">Vuelto</span>
					<span class="text-xl font-bold text-green-700">${change.toFixed(2)}</span>
				</div>
				<div class="text-xs text-green-600 mt-1">
					Preset: ${presetAmount.toFixed(2)} — Despachado: ${finalAmount.toFixed(2)}
				</div>
			</div>
		{/if}

		<!-- Payment method — after fueling -->
		{#if !confirmed}
			<div class="card p-4 mb-4">
				<label class="block text-sm font-semibold text-gray-700 mb-3">
					Forma de pago
				</label>
				<div class="grid grid-cols-2 gap-2">
					{#each paymentMethods as method}
						<button
							class="touch-btn py-3 rounded-xl border-2 text-sm font-medium transition-colors
								{paymentMethod === method.code
									? 'border-primary bg-primary/5 text-primary'
									: 'border-gray-200 text-gray-600 hover:border-gray-300'}"
							on:click={() => { paymentMethod = method.code; referenceCode = ''; }}
						>
							{method.name}
						</button>
					{/each}
				</div>

				{#if needsReference}
					<div class="mt-3">
						<label for="ref-code" class="block text-sm font-semibold text-gray-700 mb-1">
							Código de transacción ({selectedMethod?.name})
						</label>
						<input
							id="ref-code"
							type="text"
							bind:value={referenceCode}
							placeholder="Nro. de transacción / voucher"
							class="w-full rounded-xl border border-gray-200 px-4 py-3 text-sm
								focus:border-primary focus:outline-none"
						/>
					</div>
				{/if}

				<button
					class="touch-btn w-full bg-green-500 hover:bg-green-600 text-white rounded-xl py-4
						text-lg font-bold mt-4 disabled:opacity-50"
					on:click={handleConfirm}
					disabled={!canConfirm}
				>
					Confirmar — Cobrar ${finalAmount.toFixed(2)}
				</button>
			</div>
		{:else}
			<!-- Confirmed — show payment method -->
			<div class="card p-4 mb-4 bg-green-50 border-green-200">
				<div class="flex justify-between items-center">
					<span class="text-sm text-green-700">Cobrado con</span>
					<span class="text-lg font-bold text-green-700">{selectedMethod?.name}</span>
				</div>
				{#if referenceCode}
					<div class="text-xs text-green-600 mt-1">
						Transacción: {referenceCode}
					</div>
				{/if}
			</div>

			<!-- Print -->
			{#if !printing}
				<div class="mb-4">
					<PrintPrompt
						policy={printPolicy}
						onPrint={handlePrint}
						onSkip={handleNewSale}
					/>
				</div>
			{:else}
				<div class="mb-4 text-center text-sm text-blue-600 animate-pulse">
					Imprimiendo ticket...
				</div>
			{/if}

			<!-- New sale -->
			{#if printPolicy === 'NEVER' || !printing}
				<button
					class="touch-btn w-full bg-primary text-white rounded-xl py-4 text-lg font-semibold"
					on:click={handleNewSale}
				>
					Nueva Venta
				</button>
			{/if}
		{/if}
	</div>
</main>
