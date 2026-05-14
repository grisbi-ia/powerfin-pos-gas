<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { shift } from '$lib/stores/shift';
	import { config, configLoaded } from '$lib/stores/config';
	import { dispensers, dispenserList, fusionConnected } from '$lib/stores/dispensers';
	import { pendingOrders, orderByHose } from '$lib/stores/pendingOrders';
	import { goto } from '$app/navigation';
	import Header from '$lib/components/Header.svelte';
	import OfflineBanner from '$lib/components/OfflineBanner.svelte';
	import DispenserCard from '$lib/components/DispenserCard.svelte';
	import type { HoseState } from '$lib/api/types';

	// Real bridge for end-to-end testing
	import * as powerfin from '$lib/api/powerfin.mock';
	import * as realBridge from '$lib/api/bridge';
	import { convertToDispenserState } from '$lib/api/bridge-client';

	let pollTimer: ReturnType<typeof setInterval> | null = null;
	let loading = true;
	let error = '';
	let pollIntervalMs = 2000;

	// ── Auto-complete pending orders when hose goes IDLE ─────
	function autoCompleteOrders() {
		const orders = $orderByHose;
		if (orders.size === 0) return;
		for (const d of $dispenserList) {
			for (const sideKey of ['A', 'B'] as const) {
				for (const hose of d.sides[sideKey]) {
					if (hose.status === 'IDLE') {
						const key = `${d.dispenserId}-${hose.hoseId}`;
						const order = orders.get(key);
						if (order && order.status === 'FUELLING') {
							pendingOrders.completeOrder(d.dispenserId, hose.hoseId);
						}
					}
				}
			}
		}
	}

	onMount(async () => {
		if (!$configLoaded && $auth.token) {
			try {
				const appConfig = await powerfin.fetchConfig($auth.token);
				(await import('$lib/stores/config')).configStore.setConfig(appConfig);
				pollIntervalMs = appConfig.polling?.interval_ms ?? 2000;
			} catch { error = 'Error cargando configuración'; }
		}

		if ($auth.token) {
			try {
				const serverShift = await powerfin.getCurrentShift($auth.token);
				if (!serverShift) { shift.clear(); goto('/shift/open'); return; }
				shift.set(serverShift);
			} catch {
				if (!$shift) { goto('/shift/open'); return; }
			}
		}

		await pollDispensers();
		autoCompleteOrders();
		pollTimer = setInterval(() => { pollDispensers(); autoCompleteOrders(); }, pollIntervalMs);
		loading = false;
	});

	onDestroy(() => { if (pollTimer) clearInterval(pollTimer); });

	// ── Poll dispenser state and apply to correct side ──────
	async function pollDispensers() {
		try {
			const result = await realBridge.getDispensersRaw();
			const converted = convertToDispenserState(result, $config);
			for (const d of converted.dispensers) {
				// Route pump status to the hose that has a pending order,
				// not always Side A. If no pending order, Side A gets it.
				const anyOrder = [...$orderByHose.values()].find(
					o => o.dispenserId === d.dispenserId && o.status === 'FUELLING'
				);
				if (anyOrder) {
					const targetSide = anyOrder.side;
					const targetHoseId = anyOrder.hoseId;
					// Copy pump status from side A[0] to the correct hose
					const srcHose = d.sides.A[0];
					for (const sideKey of ['A', 'B'] as const) {
						for (const hose of d.sides[sideKey]) {
							if (sideKey === targetSide && hose.hoseId === targetHoseId) {
								hose.status = srcHose.status;
								hose.subStatus = srcHose.subStatus;
								hose.presetAmount = srcHose.presetAmount;
							} else {
								hose.status = 'IDLE';
								hose.subStatus = '';
								hose.presetAmount = 0;
							}
						}
					}
				}
				dispensers.updateDispenser(d);
			}
			dispensers.setFusionConnected(converted.fusionConnected);
			error = '';
		} catch {
			if (loading) error = 'FusionBridge no disponible';
			dispensers.setFusionConnected(false);
		}
	}

	function handleSideClick(dispenserId: number, side: 'A' | 'B', hose: HoseState) {
		const busy = ['AUTHORIZED', 'CALLING', 'STARTING', 'FUELLING', 'PAUSED'].includes(hose.status);
		const key = `${dispenserId}-${hose.hoseId}`;
		const pendingOrder = $orderByHose.get(key);
		const isPendingCollection = pendingOrder?.status === 'COMPLETED' && hose.status === 'IDLE';

		if (busy) return;
		if (isPendingCollection && pendingOrder) {
			goto(`/sale?dispenser=${dispenserId}&side=${side}&hose=${hose.hoseId}&mode=collect&order=${pendingOrder.orderId}`);
			return;
		}
		goto(`/sale?dispenser=${dispenserId}&side=${side}&mode=sale`);
	}

	function handleHistory() { goto('/history'); }
	function handleCloseShift() { goto('/shift/close'); }
</script>

<Header title="Powerfin POS" />
<OfflineBanner />

<main class="flex-1 px-4 py-4 pb-24">
	{#if loading}
		<div class="flex items-center justify-center py-20">
			<div class="text-center">
				<div class="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto"></div>
				<p class="text-gray-400 mt-4 text-sm">Conectando...</p>
			</div>
		</div>
	{:else}
		<div class="grid gap-3">
			{#each $dispenserList as d (d.dispenserId)}
				<DispenserCard dispenser={d} onSideClick={handleSideClick} />
			{:else}
				<div class="text-center py-12 text-gray-400"><p>No hay surtidores configurados</p></div>
			{/each}
		</div>

		{#if error}
			<div class="mt-4 bg-red-50 text-red-600 text-sm text-center rounded-xl py-3">{error}</div>
		{/if}

		{#if $shift}
			<div class="card mt-4 p-4">
				<div class="text-xs text-gray-500">Turno #{$shift.shift_id}</div>
				<div class="text-sm text-gray-700 mt-1">Inicio: {new Date($shift.opened_at).toLocaleTimeString('es-EC', { hour: '2-digit', minute: '2-digit' })}</div>
			</div>
		{/if}
	{/if}
</main>

<nav class="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-4 py-3">
	<div class="flex justify-around">
		<button class="touch-btn flex flex-col items-center gap-1 text-primary" on:click={() => goto('/')}>
			<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" /></svg>
			<span class="text-xs">Inicio</span>
		</button>
		<button class="touch-btn flex flex-col items-center gap-1 text-gray-400" on:click={handleHistory}>
			<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
			<span class="text-xs">Historial</span>
		</button>
		<button class="touch-btn flex flex-col items-center gap-1 text-gray-400" on:click={handleCloseShift}>
			<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>
			<span class="text-xs">Cerrar turno</span>
		</button>
	</div>
</nav>
