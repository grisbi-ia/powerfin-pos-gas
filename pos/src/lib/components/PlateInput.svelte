<script lang="ts">
	import type { VehicleResult } from '$lib/api/types';
	import * as powerfin from '$lib/api/powerfin.mock';

	export let onResult: (result: VehicleResult) => void;
	export let disabled = false;

	let plate = '';
	let searching = false;
	let error = '';

	function normalizePlate(value: string): string {
		return value.toUpperCase().replace(/-/g, '');
	}

	async function handleSearch() {
		if (plate.length < 3) return;

		searching = true;
		error = '';
		try {
			const result = await powerfin.lookupVehicle('mock-token', normalizePlate(plate));
			onResult(result);
		} catch {
			error = 'Error al buscar vehículo';
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
</div>