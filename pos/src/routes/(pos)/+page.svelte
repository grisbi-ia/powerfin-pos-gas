<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { auth, currentUser } from '$lib/stores/auth';
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
	import * as powerfin from '$lib/api/powerfin';
	import * as realBridge from '$lib/api/bridge';
	import { getDispensers as getDispensersState } from '$lib/api/bridge-client';


	let pollTimer: ReturnType<typeof setInterval> | null = null;
	let reconcileTimer: ReturnType<typeof setInterval> | null = null;
	let sseConnection: ReturnType<typeof realBridge.connectToEvents> | null = null;
	let ssePollDebounce: ReturnType<typeof setTimeout> | null = null;
	let loading = true;
	let error = '';
	let pollIntervalMs = 2000;
	let openingShift = false;
	let shiftError = '';
	const RECONCILE_INTERVAL_MS = 30_000;

	// Debounced poll trigger for real-time SSE events (avoids polling flood)
	function triggerSsePoll() {
		if (ssePollDebounce) clearTimeout(ssePollDebounce);
		ssePollDebounce = setTimeout(() => {
			pollDispensers();
		}, 150);
	}

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

	// ── Reconciliation with PowerFin (every 30s) ────────────
	async function reconcileWithPowerFin() {
		try {
			if (!$shift || !$auth.token) return;
			const serverOrders = await powerfin.getShiftDispatches($auth.token, $shift.shift_id);
			const changes = pendingOrders.reconcile(serverOrders);
			if (changes > 0) {
				console.log(`[pendingOrders] Reconciled: ${changes} change(s) from PowerFin`);
			}
		} catch {
			// PowerFin unreachable — keep local data, retry next interval
		}
	}

	// ── Open shift ───────────────────────────────────────────
	async function handleOpenShift() {
		if (!$auth.token) return;
		openingShift = true;
		shiftError = '';
		try {
			const result = await powerfin.openShift($auth.token, {
				opening_cash: 0,
				notes: ''
			});
			shift.set(result);
		} catch {
			shiftError = 'Error al abrir el turno';
		} finally {
			openingShift = false;
		}
	}

	onMount(async () => {
		// 1. Reload pendingOrders from localStorage (survives page refresh)
		pendingOrders.reloadFromStorage();

		if (!$configLoaded && $auth.token) {
			try {
				const appConfig = await powerfin.fetchConfig($auth.token);
				(await import('$lib/stores/config')).configStore.setConfig(appConfig);
				pollIntervalMs = appConfig.polling?.interval_ms ?? 2000;
			} catch { error = 'Error cargando configuración'; }
		}

		// 2. Load shift from server (source of truth)
		if ($auth.token) {
			try {
				const serverShift = await powerfin.getCurrentShift($auth.token);
				if (serverShift) {
					shift.set(serverShift);
				} else {
					shift.clear();
				}
			} catch {
				// Server unreachable — keep localStorage value if any
			}
		}

		// 3. Reconcile with PowerFin (authoritative source)
		if ($shift) await reconcileWithPowerFin();

		await pollDispensers();

		// 4. Fast polling for dispenser state (every 2s)
		pollTimer = setInterval(() => { pollDispensers(); }, pollIntervalMs);

		// 5. Slow polling for PowerFin reconciliation (every 30s)
		reconcileTimer = setInterval(reconcileWithPowerFin, RECONCILE_INTERVAL_MS);

		// 6. Real-time SSE events
		console.log('[SSE] Connecting to FusionBridge events...');
		sseConnection = realBridge.connectToEvents(
			(eventType, data) => {
				switch (eventType) {
					case 'PUMP_STATUS_CHANGE':
					case 'DELIVERY_PROGRESS':
						triggerSsePoll();
						break;
					case 'NEW_TRANSACTION':
						triggerSsePoll();
						break;
					case 'TRANSACTION_LOCK':
					case 'SALE_CLEARED':
						triggerSsePoll();
						break;
					case 'FUSION_STATUS':
						dispensers.setFusionConnected((data as Record<string,unknown>).connected === true);
						break;
				}
			},
			(e) => { console.error('[SSE] Connection error:', e); }
		);

		loading = false;
	});

	onDestroy(() => {
		if (pollTimer) clearInterval(pollTimer);
		if (reconcileTimer) clearInterval(reconcileTimer);
		if (ssePollDebounce) clearTimeout(ssePollDebounce);
		if (sseConnection && 'close' in sseConnection) {
			(sseConnection as { close(): void }).close();
		}
	});

	// ── Poll dispenser state ──────────────────────────────────
	async function pollDispensers() {
		try {
			const result = await getDispensersState($config);
			for (const d of result.dispensers) {
				dispensers.updateDispenser(d);
			}
			dispensers.setFusionConnected(result.fusionConnected);
			error = '';
			autoCompleteOrders();
		} catch {
			if (loading) error = 'FusionBridge no disponible';
			dispensers.setFusionConnected(false);
		}
	}

	function handleSideClick(dispenserId: number, side: 'A' | 'B', hose: HoseState) {
		// Block all operations without an open shift
		if (!$shift) return;

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
	function handleCash() { goto('/cash'); }
	function handleUsers() { goto('/users'); }
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
		<!-- Sin turno abierto: mostrar botón de apertura + surtidores bloqueados -->
		{#if !$shift}
			<div class="card p-6 mb-4 text-center">
				<div class="text-3xl mb-3">🔒</div>
				<h2 class="text-lg font-bold text-gray-800 mb-2">Turno no aperturado</h2>
				<p class="text-sm text-gray-500 mb-4">
					Debe abrir su turno para realizar ventas, cobros y movimientos de caja.
				</p>

				<!-- Info del usuario -->
				<div class="bg-gray-50 rounded-xl p-4 mb-4 text-left text-sm">
					<div class="flex justify-between py-1">
						<span class="text-gray-500">Usuario:</span>
						<span class="font-semibold text-gray-800">{$currentUser?.name ?? '—'}</span>
					</div>
					<div class="flex justify-between py-1">
						<span class="text-gray-500">Fecha:</span>
						<span class="font-semibold text-gray-800">{new Date().toLocaleDateString('es-EC', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</span>
					</div>
					<div class="flex justify-between py-1">
						<span class="text-gray-500">Hora:</span>
						<span class="font-semibold text-gray-800">{new Date().toLocaleTimeString('es-EC', { hour: '2-digit', minute: '2-digit' })}</span>
					</div>
				</div>

				{#if shiftError}
					<div class="bg-red-50 text-red-600 text-sm rounded-lg py-2 mb-3">{shiftError}</div>
				{/if}

				<button
					class="touch-btn w-full bg-primary text-white rounded-xl py-4 text-lg font-semibold disabled:opacity-50"
					on:click={handleOpenShift}
					disabled={openingShift}
				>
					{openingShift ? 'Abriendo turno...' : '🔓 Abrir Turno'}
				</button>
			</div>
		{/if}

		<!-- Surtidores (bloqueados visualmente si no hay turno) -->
		<div class="grid gap-3 {!$shift ? 'opacity-50 pointer-events-none' : ''}">
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
		<button class="touch-btn flex flex-col items-center gap-1 {$shift ? 'text-gray-400' : 'text-gray-300'}" on:click={handleCash} disabled={!$shift}>
			<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" /></svg>
			<span class="text-xs">Caja</span>
		</button>
		<button class="touch-btn flex flex-col items-center gap-1 {$shift ? 'text-gray-400' : 'text-gray-300'}" on:click={handleHistory} disabled={!$shift}>
			<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
			<span class="text-xs">Historial</span>
		</button>
		<button class="touch-btn flex flex-col items-center gap-1 text-gray-400" on:click={handleUsers}>
			<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z" /></svg>
			<span class="text-xs">Usuarios</span>
		</button>
		{#if $shift}
			<button class="touch-btn flex flex-col items-center gap-1 text-gray-400" on:click={handleCloseShift}>
				<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>
				<span class="text-xs">Cerrar turno</span>
			</button>
		{/if}
	</div>
</nav>
