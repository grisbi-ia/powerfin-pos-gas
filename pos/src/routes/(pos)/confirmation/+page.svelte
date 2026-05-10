<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import Header from '$lib/components/Header.svelte';
	import PrintPrompt from '$lib/components/PrintPrompt.svelte';
	import type { PrintPolicy } from '$lib/api/types';

	// Mock imports
	import * as bridge from '$lib/api/bridge.mock';

	let orderId = '';
	let dispenserId = 0;
	let finalAmount = 0;
	let finalVolume = '';
	let presetAmount = 0;
	let paymentMethod = '';
	let unitPrice = 0;
	let printPolicy: PrintPolicy = 'ASK';
	let printing = false;

	$: change = presetAmount > 0 ? Math.max(0, presetAmount - finalAmount) : 0;

	onMount(async () => {
		orderId = $page.url.searchParams.get('order') ?? '';
		dispenserId = Number($page.url.searchParams.get('dispenser') ?? '0');
		finalAmount = parseFloat($page.url.searchParams.get('amount') ?? '0');
		finalVolume = $page.url.searchParams.get('volume') ?? '0.00';
		presetAmount = parseFloat($page.url.searchParams.get('preset') ?? '0');
		paymentMethod = $page.url.searchParams.get('method') ?? '';
		unitPrice = parseFloat($page.url.searchParams.get('price') ?? '0');

		// Get print policy from bridge
		try {
			const policyResult = await bridge.getPrintPolicy();
			printPolicy = policyResult.policy as PrintPolicy;

			if (printPolicy === 'ALWAYS') {
				await handlePrint();
			}
		} catch {
			printPolicy = 'ASK';
		}
	});

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
		goto('/');
	}
</script>

<Header title="Venta Completada" showBack={false} />

<main class="flex-1 px-4 py-6 overflow-y-auto">
	<div class="w-full max-w-sm mx-auto">
		<!-- Success icon -->
		<div class="text-center mb-6">
			<div class="w-20 h-20 mx-auto mb-3 rounded-full bg-green-100 flex items-center justify-center">
				<svg class="w-10 h-10 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
				</svg>
			</div>
			<h2 class="text-xl font-bold text-gray-800">Venta Completada</h2>
			<p class="text-sm text-gray-500 mt-1">#{orderId}</p>
		</div>

		<!-- Sale summary -->
		<div class="card p-4 mb-4">
			<h3 class="text-sm font-semibold text-gray-700 mb-3">Resumen del despacho</h3>

			<div class="space-y-2">
				<div class="flex justify-between text-sm">
					<span class="text-gray-500">Surtidor</span>
					<span class="font-medium">{dispenserId}</span>
				</div>
				<div class="flex justify-between text-sm">
					<span class="text-gray-500">Volumen</span>
					<span class="font-medium">{finalVolume} L</span>
				</div>
				<div class="flex justify-between text-sm">
					<span class="text-gray-500">Precio unitario</span>
					<span class="font-medium">${unitPrice.toFixed(3)}</span>
				</div>
				<div class="flex justify-between text-sm">
					<span class="text-gray-500">Forma de pago</span>
					<span class="font-medium">{paymentMethod}</span>
				</div>

				<hr class="border-gray-100" />

				<div class="flex justify-between text-lg font-bold">
					<span class="text-gray-700">Total</span>
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
		<button
			class="touch-btn w-full bg-primary text-white rounded-xl py-4 text-lg font-semibold"
			on:click={handleNewSale}
		>
			Nueva Venta
		</button>
	</div>
</main>
