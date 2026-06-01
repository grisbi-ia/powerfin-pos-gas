<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { get } from 'svelte/store';
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
	let verifyingSide: 'A' | 'B' | null = null;
	let refreshingAll = false;

	// Cancel confirmation state
	let cancelConfirm: { dispenserId: number; side: 'A' | 'B'; hoseId: number; fusionPumpId: number; presetAmount: number; orderId?: string } | null = null;
	let cancelling = false;

	const RECONCILE_INTERVAL_MS = 3_000;

	// Debounced poll trigger for real-time SSE events (avoids polling flood)
	function triggerSsePoll() {
		if (ssePollDebounce) clearTimeout(ssePollDebounce);
		ssePollDebounce = setTimeout(() => {
			pollDispensers();
		}, 150);
	}

	// Orders are completed ONLY via NEW_TRANSACTION SSE event from FusionBridge.
	// If an SSE event is missed (reconnect), PowerFin reconciliation (every 3s)
	// will sync the correct status. Never auto-complete based on hose state alone
	// — a rejected PRESET also leaves the hose IDLE but the sale never happened.

	// ── Reconciliation with PowerFin (every 3s) ────────────
	async function reconcileWithPowerFin() {
		try {
			if (!get(shift) || !get(auth).token) return;
			const serverOrders = await powerfin.getShiftDispatches(get(auth).token!, get(shift)!.shift_id);
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
		if (!get(auth).token) return;
		openingShift = true;
		shiftError = '';
		try {
			const result = await powerfin.openShift(get(auth).token!, {
				opening_cash: 0,
				notes: '',
				user_name: get(currentUser)?.name
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

		if (!get(configLoaded) && get(auth).token) {
			try {
				const appConfig = await powerfin.fetchConfig(get(auth).token!);
				(await import('$lib/stores/config')).configStore.setConfig(appConfig);
				pollIntervalMs = appConfig.polling?.interval_ms ?? 2000;
			} catch { error = 'Error cargando configuración'; }
		}

		// 2. Load shift from server (source of truth)
		if (get(auth).token) {
			try {
				const serverShift = await powerfin.getCurrentShift(get(auth).token!);
				if (serverShift) {
					shift.set(serverShift);
				} else {
					shift.clear();
				}
			} catch {
				// Server unreachable — keep localStorage value if any
			}
		}

		// 3. Reconcile with PowerFin immediately on mount (authoritative source)
		if (get(shift)) await reconcileWithPowerFin();

		await pollDispensers();

		// 4. Fast polling for dispenser state (every 2s)
		pollTimer = setInterval(() => { pollDispensers(); }, pollIntervalMs);

		// 5. Aggressive PowerFin reconciliation (every 3s)
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
					case 'NEW_TRANSACTION': {
						const txData = data as Record<string, unknown>;
						const pumpNumber = Number(txData.pumpNumber || 0);
						const hoseId = Number(txData.hoseId || 0);  // Fusion HO
						const finalAmount = parseFloat(String(txData.amount || '0'));
						const finalVolume = String(txData.volume || '0.00');
					const orderId = String(txData.orderId || '');
					const saleId = String(txData.saleId || '');
						if (pumpNumber > 0) {
							pendingOrders.completeOrder(pumpNumber, hoseId > 0 ? hoseId : undefined, finalAmount, finalVolume);
							console.log(`[SSE] NEW_TRANSACTION: pump=${pumpNumber} hose=${hoseId} amount=${finalAmount} volume=${finalVolume}`);
					// Update PowerFin so other devices see COMPLETED status on reconciliation
					if (orderId && finalAmount > 0 && get(auth).token) {
						powerfin.completeDispatch(get(auth).token!, orderId, {
							order_id: orderId,
							fusion_sale_id: saleId,
							volume: finalVolume,
							amount: String(finalAmount),
							unit_price: String(txData.unitPrice || '0'),
							payment_method: 'EFECTIVO',
							completed_at: new Date().toISOString()
						}).catch(() => { /* fire-and-forget — reconciliation will retry */ });
					}
						}
						triggerSsePoll();
						break;
					}
					case 'TRANSACTION_LOCK':
						triggerSsePoll();
						break;
					case 'SALE_CLEARED':
						triggerSsePoll();
						// Immediate reconciliation — another device may have collected
						reconcileWithPowerFin();
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
			const result = await getDispensersState(get(config));
			for (const d of result.dispensers) {
				dispensers.updateDispenser(d);
			}
			dispensers.setFusionConnected(result.fusionConnected);
			error = '';
		} catch {
			if (loading) error = 'FusionBridge no disponible';
			dispensers.setFusionConnected(false);
		}
	}

	// ── On-demand verification gate ──────────────────────────
	// Before navigating to sale/collect, fetches the real state from
	// FusionBridge and reconciles with PowerFin to prevent:
	//  - Selling on a hose that is being used on another device
	//  - Missing a pending collection that appeared while the UI was stale
	async function handleSideClick(dispenserId: number, side: 'A' | 'B', hose: HoseState) {
		if (!get(shift)) return;

		// Set verifying state — shows spinner on the clicked side
		verifyingSide = side;

		try {
			// Step 1: Fetch ALL dispenser states from FusionBridge (not just one pump)
			// This is critical: a single dispenser can span multiple Fusion pumps
			// (e.g. DIESEL armario = Pump 1 side A + Pump 2 side B)
			await pollDispensers();

			// Step 2: Check fresh hose state from the updated store
			const freshDispensers = get(dispenserList);
			const freshDisp = freshDispensers.find(d => d.dispenserId === dispenserId);
			const freshHose = freshDisp?.sides[side]?.find(h => h.hoseId === hose.hoseId);

			if (freshHose) {
				const busy = ['AUTHORIZED', 'CALLING', 'STARTING', 'FUELLING', 'PAUSED'].includes(freshHose.status);
				if (busy) {
					console.log(`[verify] Hose ${dispenserId}-${side} is busy (${freshHose.status}) — blocked`);
					return;
				}
			}

			// Step 3: Reconcile with PowerFin to get latest orders
			await reconcileWithPowerFin();

			// Step 4: Re-check orderByHose after reconciliation
			const key = `${dispenserId}-${hose.hoseId}`;
			const pendingOrder = get(orderByHose).get(key);

			if (pendingOrder?.status === 'COMPLETED') {
				console.log(`[verify] Pending collection found for ${dispenserId}-${side}: ${pendingOrder.orderId}`);
				goto(`/sale?dispenser=${dispenserId}&side=${side}&hose=${hose.hoseId}&mode=collect&order=${pendingOrder.orderId}`);
				return;
			}

			// Step 5: All clear — proceed to sale
			console.log(`[verify] Hose ${dispenserId}-${side} verified free — starting sale`);
			goto(`/sale?dispenser=${dispenserId}&side=${side}&mode=sale`);
		} catch (err) {
			console.error('[verify] Verification failed:', err);
			// On error, fall back to local state (existing behavior)
			const key = `${dispenserId}-${hose.hoseId}`;
			const pendingOrder = get(orderByHose).get(key);
			const isPendingCollection = pendingOrder?.status === 'COMPLETED' && hose.status === 'IDLE';

			if (isPendingCollection && pendingOrder) {
				goto(`/sale?dispenser=${dispenserId}&side=${side}&hose=${hose.hoseId}&mode=collect&order=${pendingOrder.orderId}`);
			} else {
				goto(`/sale?dispenser=${dispenserId}&side=${side}&mode=sale`);
			}
		} finally {
			verifyingSide = null;
		}
	}

	function handleHistory() { goto('/history'); }
	function handleCash() { goto('/cash'); }
	function handleUsers() { goto('/users'); }
	function handleCloseShift() { goto('/shift/close'); }

	// ── Manual refresh (dispensers + reconciliation) ──────
	async function handleRefresh() {
		refreshingAll = true;
		try {
			await pollDispensers();
			await reconcileWithPowerFin();
		} catch {
			// Silently ignore — UI already updated with whatever succeeded
		} finally {
			refreshingAll = false;
		}
	}

	// ── Cancel authorized dispatch ─────────────────────────
	function handleCancelClick(dispenserId: number, side: 'A' | 'B', hose: HoseState) {
		// Find pending order for this hose
		const key = `${dispenserId}-${hose.hoseId}`;
		const pendingOrder = get(orderByHose).get(key);

		// Look up the correct fusionPumpId from config (different per side for multi-pump dispensers)
		const cfg = get(config);
		const dispCfg = cfg?.dispensers?.find(d => d.dispenser_id === dispenserId);
		const hoseCfg = dispCfg?.sides[side]?.find(h => h.hose_id === hose.hoseId);
		const fusionPumpId = hoseCfg?.fusion_pump_id ?? dispCfg?.fusion_pump_id ?? dispenserId;

		cancelConfirm = {
			dispenserId,
			side,
			hoseId: hose.hoseId,
			fusionPumpId,
			presetAmount: hose.presetAmount,
			orderId: pendingOrder?.orderId
		};
	}

	async function executeCancel() {
		if (!cancelConfirm) return;
		cancelling = true;

		try {
			// 1. Clear preset from Synergy via FusionBridge (uses fusionPumpId, not dispenserId)
			await realBridge.cancelDispenser(cancelConfirm.fusionPumpId);

			// 2. Cancel order in PowerFin (if exists)
			if (cancelConfirm.orderId && get(auth).token) {
				try {
					await powerfin.cancelDispatch(get(auth).token!, cancelConfirm.orderId);
				} catch {
					console.warn('[cancel] PowerFin cancel-dispatch failed — order may need manual cleanup');
				}
			}

			// 3. Remove from local pending orders
			if (cancelConfirm.orderId) {
				pendingOrders.removeOrder(cancelConfirm.orderId);
			}

			// 4. Refresh dispenser states
			await pollDispensers();
		} catch (err) {
			console.error('[cancel] Failed:', err);
		} finally {
			cancelling = false;
			cancelConfirm = null;
		}
	}

	function dismissCancel() {
		cancelConfirm = null;
	}
</script>

<Header title="Powerfin POS" onRefresh={handleRefresh} refreshing={refreshingAll} />
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
				<DispenserCard dispenser={d} onSideClick={handleSideClick} onCancelClick={handleCancelClick} {verifyingSide} />
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

	<!-- Cancel confirmation modal -->
	{#if cancelConfirm}
		<div class="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true">
			<!-- Backdrop -->
			<div class="absolute inset-0 bg-black/50" role="presentation" on:click={dismissCancel} on:keydown={(e) => e.key === 'Escape' && dismissCancel()}></div>
			<!-- Card -->
			<div class="relative bg-white rounded-2xl shadow-xl w-full max-w-sm p-6">
				<div class="text-center mb-4">
					<div class="w-12 h-12 mx-auto mb-3 rounded-full bg-red-100 flex items-center justify-center">
						<span class="text-2xl">⚠️</span>
					</div>
					<h3 class="text-lg font-bold text-gray-800">¿Cancelar autorización?</h3>
					<p class="text-sm text-gray-500 mt-1">
						Surtidor {cancelConfirm.dispenserId} — Lado {cancelConfirm.side}
					</p>
				</div>

				{#if cancelConfirm.presetAmount > 0}
					<div class="bg-gray-50 rounded-xl p-3 mb-4 text-center">
						<span class="text-sm text-gray-500">Monto autorizado: </span>
						<span class="text-lg font-bold text-primary">${cancelConfirm.presetAmount.toFixed(2)}</span>
					</div>
				{/if}

				<div class="grid grid-cols-2 gap-3">
					<button
						class="touch-btn py-3 rounded-xl text-sm font-semibold bg-gray-100 text-gray-700 hover:bg-gray-200"
						on:click={dismissCancel}
						disabled={cancelling}
					>
						No, mantener
					</button>
					<button
						class="touch-btn py-3 rounded-xl text-sm font-semibold bg-red-500 text-white hover:bg-red-600 disabled:opacity-50"
						on:click={executeCancel}
						disabled={cancelling}
					>
						{cancelling ? 'Cancelando...' : 'Sí, cancelar'}
					</button>
				</div>
			</div>
		</div>
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
