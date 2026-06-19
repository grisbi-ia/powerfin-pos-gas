<script lang="ts">
	import { onMount } from 'svelte';
	import type { VehicleResult, PredefinedVehicle } from '$lib/api/types';
	import * as powerfin from '$lib/api/powerfin';
	import { auth } from '$lib/stores/auth';
	import { get } from 'svelte/store';

	export let onResult: (result: VehicleResult) => void;
	export let disabled = false;

	let plate = '';
	let searching = false;
	let error = '';
	let predefinedAvailable = false;
	let predefinedLoading = false;

	function normalizePlate(value: string): string {
		return value.toUpperCase().replace(/-/g, '');
	}

	async function handleSearch() {
		if (plate.length < 3) return;

		searching = true;
		error = '';
		try {
			const token = get(auth).token;
			if (!token) { error = 'No hay sesión activa'; return; }
			const result = await powerfin.lookupVehicle(token, normalizePlate(plate));
			onResult(result);
		} catch {
			error = 'Error al buscar vehículo';
		} finally {
			searching = false;
		}
	}

	async function handlePredefinedClick() {
		searching = true;
		error = '';
		try {
			const token = get(auth).token;
			if (!token) { error = 'No hay sesión activa'; return; }
			const vehicle = await powerfin.getNextPredefinedVehicle(token);
			plate = vehicle.plate;
		} catch (e) {
			error = 'No hay vehículos internos disponibles';
		} finally {
			searching = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			e.preventDefault();
			handleSearch();
		}
	}

	onMount(async () => {
		const token = get(auth).token;
		if (!token) return;
		predefinedLoading = true;
		try {
			const vehicles = await powerfin.getPredefinedVehicles(token);
			predefinedAvailable = vehicles.length > 0;
		} catch {
			// Silently ignore — predefined vehicles are optional
		} finally {
			predefinedLoading = false;
		}
	});
</script>

<div class="w-full">
	<label for="plate-input" class="block text-sm font-semibold text-gray-700 mb-1">
		Placa del vehículo
	</label>

	<div class="flex gap-2">
		<input
			id="plate-input"
			type="text"
			bind:value={plate}
			on:keydown={handleKeydown}
			placeholder="Ej: ABC1234"
			class="flex-1 rounded-xl border border-gray-200 px-4 py-3 text-lg font-mono
				uppercase tracking-wider text-center
				focus:border-primary focus:outline-none
				disabled:bg-gray-100 disabled:cursor-not-allowed"
			{disabled}
			maxlength="10"
		/>

		<button
			type="button"
			class="touch-btn bg-primary hover:bg-primary/90 text-white rounded-xl px-6 py-3 font-bold disabled:opacity-50"
			on:click={handleSearch}
			disabled={disabled || plate.length < 3}
		>
			{searching ? '...' : 'Buscar'}
		</button>
	</div>

	{#if error}
		<p class="text-red-500 text-xs mt-1 text-center">{error}</p>
	{/if}

	{#if searching}
		<div class="flex justify-center mt-2">
			<div class="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
		</div>
	{/if}

	<!-- Predefined vehicle button for container sales -->
	{#if predefinedAvailable}
		<div class="mt-4 pt-3 border-t border-gray-100">
			<button
				type="button"
				class="touch-btn w-full rounded-xl border-2 border-dashed border-amber-400 bg-amber-50
					px-4 py-3 text-sm font-semibold text-amber-700
					hover:bg-amber-100 hover:border-amber-500
					active:bg-amber-200 transition-colors
					disabled:opacity-50 disabled:cursor-not-allowed"
				on:click={handlePredefinedClick}
				disabled={disabled || searching}
			>
				🧉 Pedir Vehículo Interno
			</button>
			<p class="text-xs text-gray-400 text-center mt-1">
				Para ventas por envase o sin placa
			</p>
		</div>
	{:else if predefinedLoading}
		<div class="mt-4 flex justify-center">
			<div class="w-4 h-4 border-2 border-gray-300 border-t-transparent rounded-full animate-spin"></div>
		</div>
	{/if}
</div>