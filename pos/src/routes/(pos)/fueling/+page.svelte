<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import Header from '$lib/components/Header.svelte';
	import { getDispenser } from '$lib/api/bridge.mock';
	import type { HoseState } from '$lib/api/types';

	let orderId = '';
	let dispenserId = 0;
	let hoseId = 0;
	let side: 'A' | 'B' = 'A';
	let presetAmount = 0;
	let unitPrice = 0;
	let customerName = '';
	let priceList = 'STANDARD';
	let plate = '';
	let hoseStatus = 'AUTHORIZED';
	let pollTimer: ReturnType<typeof setInterval> | null = null;

	onMount(() => {
		orderId = $page.url.searchParams.get('order') ?? '';
		dispenserId = Number($page.url.searchParams.get('dispenser') ?? '0');
		hoseId = Number($page.url.searchParams.get('hose') ?? '0');
		side = ($page.url.searchParams.get('side') ?? 'A') as 'A' | 'B';
		presetAmount = parseFloat($page.url.searchParams.get('amount') ?? '0');
		unitPrice = parseFloat($page.url.searchParams.get('price') ?? '0');
		customerName = decodeURIComponent($page.url.searchParams.get('customerName') ?? '');
		priceList = $page.url.searchParams.get('priceList') ?? 'STANDARD';
		plate = decodeURIComponent($page.url.searchParams.get('plate') ?? '');

		// Poll dispenser status every 3s
		pollDispenser();
		pollTimer = setInterval(pollDispenser, 3000);
	});

	onDestroy(() => {
		if (pollTimer) clearInterval(pollTimer);
	});

	function findHose(d: { dispenserId: number; sides: { A: HoseState[]; B: HoseState[] } }): HoseState | null {
		return d.sides[side]?.find(h => h.hoseId === hoseId) ?? null;
	}

	let completed = false;

	async function pollDispenser() {
		if (completed) return;
		try {
			const d = await getDispenser(dispenserId);
			const hose = findHose(d);
			if (hose) {
				const prevStatus = hoseStatus;
				hoseStatus = hose.status;

				// Detect transition to IDLE → redirect to confirmation
				if (prevStatus !== 'IDLE' && hose.status === 'IDLE') {
					completed = true;
					if (pollTimer) clearInterval(pollTimer);

					// Build confirmation URL
					const params = new URLSearchParams({
						order: orderId,
						dispenser: String(dispenserId),
						hose: String(hoseId),
						side,
						amount: String(presetAmount), // mock: 85% of preset
						volume: String((presetAmount / (unitPrice || 3.103)).toFixed(3)),
						preset: String(presetAmount),
						price: String(unitPrice),
						customerName,
						priceList,
						plate
					});
					goto(`/confirmation?${params.toString()}`);
				}
			}
		} catch {
			// ignore poll errors
		}
	}

	function handleBack() {
		if (pollTimer) clearInterval(pollTimer);
		goto('/');
	}
</script>

<Header title="Despachando" showBack={true} onBack={handleBack} />

<main class="flex-1 flex flex-col items-center justify-center px-6 py-8">
	<div class="w-full max-w-sm">
		<!-- Status indicator -->
		<div class="text-center mb-8">
			<div class="w-24 h-24 mx-auto mb-4 rounded-full border-4
				{hoseStatus === 'FUELLING' ? 'border-blue-500 animate-pulse' :
				 hoseStatus === 'IDLE' ? 'border-green-500' : 'border-purple-500'}
				flex items-center justify-center">
				{#if hoseStatus === 'FUELLING'}
					<svg class="w-12 h-12 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
							d="M13 10V3L4 14h7v7l9-11h-7z" />
					</svg>
				{:else if hoseStatus === 'IDLE'}
					<svg class="w-10 h-10 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
					</svg>
				{:else}
					<svg class="w-12 h-12 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
							d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
					</svg>
				{/if}
			</div>
			<h2 class="text-lg font-semibold text-gray-700">
				{hoseStatus === 'AUTHORIZED' ? 'Surtidor autorizado' :
				 hoseStatus === 'STARTING' ? 'Iniciando despacho...' :
				 hoseStatus === 'FUELLING' ? 'Despachando...' :
				 hoseStatus === 'PAUSED' ? 'Despacho pausado' :
				 hoseStatus === 'IDLE' ? 'Despacho completado' :
				 'Completando...'}
			</h2>
			<p class="text-sm text-gray-500 mt-1">Surtidor {dispenserId} — Lado {side}</p>
			{#if customerName || plate}
				<p class="text-sm text-gray-400 mt-2">{customerName}{plate ? ` · ${plate}` : ''}</p>
			{/if}
		</div>

		<!-- Dispatch info -->
		<div class="card p-4 space-y-3 mb-4">
			<div class="flex justify-between">
				<span class="text-sm text-gray-500">Orden</span>
				<span class="text-sm font-semibold">#{orderId}</span>
			</div>
			<div class="flex justify-between">
				<span class="text-sm text-gray-500">Monto preset</span>
				<span class="text-sm font-semibold">${presetAmount.toFixed(2)}</span>
			</div>
			<div class="flex justify-between">
				<span class="text-sm text-gray-500">Precio</span>
				<span class="text-sm font-semibold">${unitPrice.toFixed(3)}/L</span>
			</div>
			{#if priceList !== 'STANDARD'}
				<div class="flex justify-between">
					<span class="text-sm text-gray-500">Lista</span>
					<span class="text-sm font-semibold text-purple-600">{priceList}</span>
				</div>
			{/if}
			{#if plate}
				<div class="flex justify-between">
					<span class="text-sm text-gray-500">Placa</span>
					<span class="text-sm font-mono font-semibold">{plate}</span>
				</div>
			{/if}
		</div>

		<!-- Back button -->
		<button
			class="touch-btn w-full bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-xl py-3 font-medium"
			on:click={handleBack}
		>
			Volver al inicio
		</button>

		<!-- Tip -->
		<div class="text-center mt-4">
			<p class="text-xs text-gray-400">
				Puede regresar al inicio y atender otro surtidor.
				Cuando termine, vuelva aquí para cobrar.
			</p>
		</div>
	</div>
</main>
