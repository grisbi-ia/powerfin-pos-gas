<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import Header from '$lib/components/Header.svelte';
	import CustomerSearch from '$lib/components/CustomerSearch.svelte';
	import AmountInput from '$lib/components/AmountInput.svelte';
	import type { Customer } from '$lib/api/types';

	// Mock imports
	import * as powerfin from '$lib/api/powerfin.mock';
	import * as bridge from '$lib/api/bridge.mock';

	let dispenserId = 0;
	$: dispenserId = Number($page.url.searchParams.get('dispenser') ?? '0');

	let selectedCustomer: Customer | null = null;
	let amount = '';
	let paymentMethod = 'EFECTIVO';
	let loading = false;
	let error = '';
	let unitPrice = 1.500;

	const paymentMethods = ['EFECTIVO', 'TARJETA', 'QR', 'CREDITO'];

	$: hoseId = dispenserId * 2 - 1; // Simple mapping: dispenser 1 → hose 1, dispenser 2 → hose 3

	async function handleCustomerSelect(customer: Customer | null) {
		selectedCustomer = customer;
		if (customer) {
			try {
				const price = await powerfin.getCustomerPrice('mock-token', customer.customer_id, 'SUPER');
				unitPrice = price.unit_price;
			} catch {
				unitPrice = 1.500;
			}
		} else {
			unitPrice = 1.500;
		}
	}

	async function handleAuthorize() {
		if (!amount || parseFloat(amount) <= 0) {
			error = 'Ingrese un monto válido';
			return;
		}

		loading = true;
		error = '';

		try {
			const orderResult = await powerfin.createDispatch('mock-token', {
				dispenser_id: dispenserId,
				hose_id: hoseId,
				preset_type: 'MONEY',
				preset_value: amount,
				payment_method: paymentMethod,
				customer_id: selectedCustomer?.customer_id,
				plate: selectedCustomer?.plates[0]
			});

			const orderId = orderResult.order_id;

			await bridge.authorizeDispatch({
				order_id: orderId,
				dispenser_id: dispenserId,
				preset_type: 'MONEY',
				preset_value: amount,
				payment_method: paymentMethod,
				customer_id: selectedCustomer?.customer_id,
				plate: selectedCustomer?.plates[0],
				unit_price: unitPrice,
				price_list: selectedCustomer?.price_list
			});

			goto(`/fueling?order=${orderId}&dispenser=${dispenserId}&amount=${amount}&method=${paymentMethod}&price=${unitPrice}`);
		} catch (e) {
			error = 'Error al autorizar el despacho';
		} finally {
			loading = false;
		}
	}
</script>

<Header title="Nueva Venta" showBack={true} onBack={() => goto('/')} />

<main class="flex-1 px-4 py-4 overflow-y-auto">
	<!-- Dispenser info -->
	<div class="card p-4 mb-4">
		<div class="flex items-center justify-between">
			<div>
				<div class="text-xs text-gray-400">Surtidor</div>
				<div class="text-lg font-bold text-gray-800">{dispenserId}</div>
			</div>
			<div class="text-right">
				<div class="text-xs text-gray-400">Precio actual</div>
				<div class="text-lg font-bold text-primary">${unitPrice.toFixed(3)}/L</div>
			</div>
		</div>
	</div>

	<!-- Customer search -->
	<div class="card p-4 mb-4">
		<CustomerSearch onSelect={handleCustomerSelect} disabled={loading} />
	</div>

	<!-- Amount -->
	<div class="card p-4 mb-4">
		<AmountInput onAmount={(a) => amount = a} disabled={loading} />
	</div>

	<!-- Payment method -->
	<div class="card p-4 mb-4">
		<label class="block text-sm font-semibold text-gray-700 mb-2">
			Forma de pago
		</label>
		<div class="grid grid-cols-2 gap-2">
			{#each paymentMethods as method}
				<button
					class="touch-btn py-3 rounded-xl border-2 text-sm font-medium transition-colors
						{paymentMethod === method
							? 'border-primary bg-primary/5 text-primary'
							: 'border-gray-200 text-gray-600 hover:border-gray-300'}"
					on:click={() => paymentMethod = method}
					disabled={loading}
				>
					{method}
				</button>
			{/each}
		</div>
	</div>

	<!-- Summary -->
	{#if amount}
		<div class="card p-4 mb-4 bg-primary/5 border-primary/20">
			<div class="flex justify-between text-sm">
				<span class="text-gray-600">Litros estimados:</span>
				<span class="font-semibold">{(parseFloat(amount) / unitPrice).toFixed(2)} L</span>
			</div>
			<div class="flex justify-between text-sm mt-1">
				<span class="text-gray-600">Precio unitario:</span>
				<span class="font-semibold">${unitPrice.toFixed(3)}</span>
			</div>
			{#if selectedCustomer}
				<div class="flex justify-between text-sm mt-1">
					<span class="text-gray-600">Lista:</span>
					<span class="font-semibold text-purple-600">{selectedCustomer.price_list_name}</span>
				</div>
			{/if}
		</div>
	{/if}

	{#if error}
		<div class="bg-red-50 text-red-600 text-sm text-center rounded-xl py-3 mb-4">{error}</div>
	{/if}

	<!-- Authorize button -->
	<button
		class="touch-btn w-full bg-green-500 hover:bg-green-600 text-white rounded-xl py-4
			text-lg font-bold disabled:opacity-50 disabled:cursor-not-allowed"
		on:click={handleAuthorize}
		disabled={loading || !amount}
	>
		{loading ? 'Autorizando...' : 'Autorizar Despacho'}
	</button>
</main>
