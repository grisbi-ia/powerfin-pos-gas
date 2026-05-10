<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { shift, shiftIsOpen } from '$lib/stores/shift';
	import { config, configLoaded } from '$lib/stores/config';
	import { dispensers, dispenserList, fusionConnected } from '$lib/stores/dispensers';
	import { goto } from '$app/navigation';
	import Header from '$lib/components/Header.svelte';
	import OfflineBanner from '$lib/components/OfflineBanner.svelte';
	import DispenserCard from '$lib/components/DispenserCard.svelte';

	// Mock imports
	import * as powerfin from '$lib/api/powerfin.mock';
	import { connectToEvents, getDispensers } from '$lib/api/bridge.mock';

	let eventSource: { close: () => void } | null = null;
	let loading = true;
	let error = '';

	onMount(async () => {
		// 1. Load config
		if (!$configLoaded && $auth.token) {
			try {
				const appConfig = await powerfin.fetchConfig($auth.token);
				(await import('$lib/stores/config')).configStore.setConfig(appConfig);
			} catch {
				error = 'Error cargando configuración';
			}
		}

		// 2. Check shift
		if ($auth.token) {
			try {
				const currentShift = await powerfin.getCurrentShift($auth.token);
				if (!currentShift) {
					goto('/shift/open');
					return;
				}
				if (!$shift) shift.set(currentShift);
			} catch {
				// No shift — redirect
				goto('/shift/open');
				return;
			}
		}

		// 3. Load dispenser states
		try {
			const result = await getDispensers();
			for (const d of result.dispensers) {
				dispensers.updateDispenser(d);
			}
			dispensers.setFusionConnected(result.fusionConnected);
		} catch {
			error = 'FusionBridge no disponible';
			dispensers.setFusionConnected(false);
		}

		// 4. Connect SSE
		eventSource = connectToEvents(
			(event, data) => {
				switch (event) {
					case 'INIT':
						dispensers.setFusionConnected(data.fusionConnected as boolean);
						break;
					case 'PUMP_STATUS_CHANGE':
						dispensers.updateDispenser({
							dispenserId: data.dispenserId as number,
							status: data.status as string,
							subStatus: data.subStatus as string,
							presetAmount: (data.presetAmount as number) ?? 0
						});
						break;
					case 'FUSION_STATUS':
						dispensers.setFusionConnected(data.connected as boolean);
						break;
				}
			},
			() => {
				dispensers.setFusionConnected(false);
			}
		);

		loading = false;
	});

	onDestroy(() => {
		eventSource?.close();
	});

	function handleNewDispatch(dispenserId: number) {
		goto(`/pos/new-dispatch?dispenser=${dispenserId}`);
	}

	function handleHistory() {
		goto('/pos/history');
	}

	function handleCloseShift() {
		goto('/shift/close');
	}
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
		<!-- Dispenser grid -->
		<div class="grid gap-3">
			{#each $dispenserList as d (d.dispenserId)}
				<DispenserCard dispenser={d} on:click={() => handleNewDispatch(d.dispenserId)} />
			{:else}
				<div class="text-center py-12 text-gray-400">
					<p>No hay surtidores configurados</p>
				</div>
			{/each}
		</div>

		{#if error}
			<div class="mt-4 bg-red-50 text-red-600 text-sm text-center rounded-xl py-3">{error}</div>
		{/if}

		<!-- Summary -->
		{#if $shift}
			<div class="card mt-4 p-4">
				<div class="text-xs text-gray-500">Turno #{$shift.shift_id}</div>
				<div class="text-sm text-gray-700 mt-1">
					Inicio: {new Date($shift.opened_at).toLocaleTimeString('es-EC', { hour: '2-digit', minute: '2-digit' })}
				</div>
			</div>
		{/if}
	{/if}
</main>

<!-- Bottom bar -->
<nav class="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-4 py-3">
	<div class="flex justify-around">
		<button
			class="touch-btn flex flex-col items-center gap-1 text-primary"
			on:click={() => goto('/pos')}
		>
			<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
			</svg>
			<span class="text-xs">Inicio</span>
		</button>

		<button
			class="touch-btn flex flex-col items-center gap-1 text-gray-400"
			on:click={handleHistory}
		>
			<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
			</svg>
			<span class="text-xs">Historial</span>
		</button>

		<button
			class="touch-btn flex flex-col items-center gap-1 text-gray-400"
			on:click={handleCloseShift}
		>
			<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
			</svg>
			<span class="text-xs">Cerrar turno</span>
		</button>
	</div>
</nav>
