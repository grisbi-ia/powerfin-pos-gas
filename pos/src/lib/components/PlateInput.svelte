<script lang="ts">
	import type { VehicleResult } from '$lib/api/types';
	import * as powerfin from '$lib/api/powerfin.mock';

	export let onResult: (result: VehicleResult) => void;
	export let disabled = false;

	let plate = '';
	let searching = false;
	let error = '';
	let debounceTimer: ReturnType<typeof setTimeout>;

	function normalizePlate(value: string): string {
		return value.toUpperCase().replace(/\s+/g, '');
	}

	async function handleInput() {
		clearTimeout(debounceTimer);
		error = '';

		if (plate.length < 3) {
			return;
		}

		debounceTimer = setTimeout(async () => {
			searching = true;
			error = '';
			try {
				const result = await powerfin.lookupVehicle('mock-token', plate);
				onResult(result);
			} catch {
				error = 'Error al buscar vehículo';
			} finally {
				searching = false;
			}
		}, 400);
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			e.preventDefault();
		}
	}
</script>

<div class="w-full">
	<label for="plate-input" class="block text-sm font-semibold text-gray-700 mb-1">
		Placa del vehículo
	</label>

	<div class="relative">
		<input
			id="plate-input"
			type="text"
			bind:value={plate}
			on:input={handleInput}
			on:keydown={handleKeydown}
			placeholder="Ej: ABC-1234"
			class="w-full rounded-xl border border-gray-200 px-4 py-3 text-lg font-mono
				uppercase tracking-wider text-center
				focus:border-primary focus:outline-none
				disabled:bg-gray-100 disabled:cursor-not-allowed"
			{disabled}
			maxlength="10"
		/>

		{#if searching}
			<div class="absolute right-3 top-1/2 -translate-y-1/2">
				<div class="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
			</div>
		{/if}
	</div>

	{#if error}
		<p class="text-red-500 text-xs mt-1 text-center">{error}</p>
	{/if}

	<p class="text-xs text-gray-400 mt-1 text-center">
		Ingrese la placa y presione Enter o espere
	</p>
</div>