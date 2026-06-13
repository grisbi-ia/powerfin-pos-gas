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
	let cashTimer: ReturnType<typeof setInterval> | null = null;
	let sseConnection: ReturnType<typeof realBridge.connectToEvents> | null = null;
	let ssePollDebounce: ReturnType<typeof setTimeout> | null = null;
	let loading = true;
	let error = '';
	let pollIntervalMs = 2000;
	let openingShift = false;
	let shiftError = '';
	let verifyingSide: 'A' | 'B' | null = null;
	let refreshingAll = false;
	let cashOverLimit = false;
	let cashInHand = 0;

	// Cancel confirmation state
	let cancelConfirm: { dispenserId: number; side: 'A' | 'B'; hoseId: number; fusionPumpId: number; presetAmount: number; orderId?: string } | null = null;
	let cancelling = false;

	// Stop confirmation state (during FUELLING)
	let stopConfirm: { dispenserId: number; side: 'A' | 'B'; hoseId: number; fusionPumpId: number; presetAmount: number; orderId?: string } | null = null;
	let stopping = false;
	let stopModalTimer: ReturnType<typeof setTimeout> | null = null;

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
			if (!get(auth).token) return;
			const serverOrders = await powerfin.getActiveDispatches(get(auth).token!);
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

		// 3. Reconcile with PowerFin immediately on mount (source of truth)
		await reconcileWithPowerFin();

		await pollDispensers();

		// 4. Fast polling for dispenser state (every 2s)
		pollTimer = setInterval(() => { pollDispensers(); }, pollIntervalMs);

		// 5. Aggressive PowerFin reconciliation (every 3s)
		reconcileTimer = setInterval(reconcileWithPowerFin, RECONCILE_INTERVAL_MS);

		// 6. Cash limit check (every 30s)
		cashTimer = setInterval(checkCashLimit, 30_000);
		checkCashLimit();  // immediate first check

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
							pendingOrders.completeOrder(pumpNumber, hoseId > 0 ? hoseId : undefined, finalAmount, finalVolume, orderId || undefined);
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
		if (cashTimer) clearInterval(cashTimer);
		if (ssePollDebounce) clearTimeout(ssePollDebounce);
		if (stopModalTimer) clearTimeout(stopModalTimer);
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

	async function checkCashLimit() {
		const t = get(auth).token;
		const s = get(shift);
		const cfg = get(config);
		if (!t || !s || !cfg?.max_cash_in_hand) return;
		try {
			const summary = await powerfin.getShiftCashSummary(t, s.shift_id);
			cashInHand = summary.current_balance;
			cashOverLimit = cashInHand > cfg.max_cash_in_hand;
		} catch { /* silently ignore */ }
	}

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

	// ── Stop active dispensing (during FUELLING) ────────────
	function handleStopClick(dispenserId: number, side: 'A' | 'B', hose: HoseState) {
		const key = `${dispenserId}-${hose.hoseId}`;
		const pendingOrder = get(orderByHose).get(key);

		const cfg = get(config);
		const dispCfg = cfg?.dispensers?.find(d => d.dispenser_id === dispenserId);
		const hoseCfg = dispCfg?.sides[side]?.find(h => h.hose_id === hose.hoseId);
		const fusionPumpId = hoseCfg?.fusion_pump_id ?? dispCfg?.fusion_pump_id ?? dispenserId;

		stopConfirm = {
			dispenserId, side, hoseId: hose.hoseId, fusionPumpId,
			presetAmount: hose.presetAmount,
			orderId: pendingOrder?.orderId
		};

		// Auto-dismiss modal after 8s to prevent stale UI
		if (stopModalTimer) clearTimeout(stopModalTimer);
		stopModalTimer = setTimeout(() => { stopConfirm = null; }, 8_000);
	}

	async function executeStop() {
		if (!stopConfirm) return;
		stopping = true;

		try {
			// Send STOP to Wayne via FusionBridge (uses fusionPumpId)
			const ok = await realBridge.stopDispenser(stopConfirm.fusionPumpId);
			if (!ok) {
				console.error('[stop] Failed to stop dispenser');
			}
			// Do NOT cancel the dispatch — fuel was partially dispensed.
			// The pendingOrder stays FUELLING until NEW_TRANSACTION fires
			// with the partial amount, then flows into normal collection.

			// Refresh dispenser states to see STOPPED status
			await pollDispensers();
		} catch (err) {
			console.error('[stop] Failed:', err);
		} finally {
			stopping = false;
			stopConfirm = null;
			if (stopModalTimer) { clearTimeout(stopModalTimer); stopModalTimer = null; }
		}
	}

	function dismissStop() {
		stopConfirm = null;
		if (stopModalTimer) { clearTimeout(stopModalTimer); stopModalTimer = null; }
	}
</script>

<Header title="Powerfin GAS" onRefresh={handleRefresh} refreshing={refreshingAll} />
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
		<!-- Surtidores -->
		<div class="grid gap-3 {!$shift ? 'opacity-50 pointer-events-none' : ''}">
			{#each $dispenserList as d (d.dispenserId)}
				<DispenserCard dispenser={d} onSideClick={handleSideClick} onCancelClick={handleCancelClick} onStopClick={handleStopClick} {verifyingSide} />
			{:else}
				<div class="text-center py-12 text-gray-400"><p>No hay surtidores configurados</p></div>
			{/each}
		</div>

		{#if error}
			<div class="mt-4 bg-red-50 text-red-600 text-sm text-center rounded-xl py-3">{error}</div>
		{/if}

		{#if $shift}
			<div class="card mt-4 p-4">
				<div class="flex items-center justify-between">
					<div class="text-xs text-gray-500">Turno #{$shift.shift_id}</div>
					{#if cashOverLimit}
						<span class="inline-block w-2.5 h-2.5 bg-red-500 rounded-full animate-pulse" title="Efectivo excede el límite"></span>
					{/if}
				</div>
				<div class="text-sm text-gray-700 mt-1">Inicio: {new Date($shift.opened_at).toLocaleTimeString('es-EC', { hour: '2-digit', minute: '2-digit' })}</div>
				{#if cashOverLimit}
					<div class="text-xs text-red-600 font-semibold mt-2 animate-pulse">⚠️ ALERTA, Límite de dinero en caja excedido</div>
				{/if}
			</div>
		{:else}
			<div class="card mt-4 p-4 bg-amber-50 border border-amber-200">
				<div class="flex items-center gap-2">
					<span class="text-lg">🔒</span>
					<div>
						<p class="text-sm font-semibold text-amber-700">Turno no aperturado</p>
						<p class="text-xs text-amber-500">Abra su turno en el módulo Caja para iniciar ventas</p>
					</div>
				</div>
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

	<!-- Stop confirmation modal (during FUELLING — double barrier: large safe button + small deliberate action) -->
	{#if stopConfirm}
		<div class="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true">
			<!-- Backdrop -->
			<div class="absolute inset-0 bg-black/50" role="presentation" on:click={dismissStop} on:keydown={(e) => e.key === 'Escape' && dismissStop()}></div>
			<!-- Card -->
			<div class="relative bg-white rounded-2xl shadow-xl w-full max-w-sm p-6">
				<div class="text-center mb-4">
					<div class="w-12 h-12 mx-auto mb-3 rounded-full bg-orange-100 flex items-center justify-center">
						<span class="text-2xl">⏹</span>
					</div>
					<h3 class="text-lg font-bold text-gray-800">¿Detener despacho?</h3>
					<p class="text-sm text-gray-500 mt-1">El combustible cargado hasta ahora se cobrará normalmente.</p>
				</div>

				{#if stopConfirm.presetAmount > 0}
					<div class="bg-gray-50 rounded-xl p-3 mb-4 text-center">
						<span class="text-sm text-gray-500">Monto autorizado: </span>
						<span class="text-lg font-bold text-primary">${stopConfirm.presetAmount.toFixed(2)}</span>
					</div>
				{/if}

				<!-- Barrier 1: large, prominent CANCEL (safe default) -->
				<button
					class="touch-btn w-full py-4 rounded-xl text-base font-semibold bg-green-500 text-white hover:bg-green-600 mb-3"
					on:click={dismissStop}
					disabled={stopping}
				>
					CANCELAR — continuar despacho
				</button>

				<!-- Barrier 2: small, subtle DELIBERATE action -->
				<button
					class="touch-btn w-full py-2 text-xs text-gray-400 hover:text-red-500 transition-colors disabled:opacity-30"
					on:click={executeStop}
					disabled={stopping}
				>
					{stopping ? 'Deteniendo...' : 'Detener despacho'}
				</button>
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
		<button class="touch-btn flex flex-col items-center gap-1 text-gray-400" on:click={handleCash}>
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
		{/if}
	</div>
</nav>
