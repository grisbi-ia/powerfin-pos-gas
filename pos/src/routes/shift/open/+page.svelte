<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { shift } from '$lib/stores/shift';
	import { config } from '$lib/stores/config';
	import { goto } from '$app/navigation';

	// Mock imports
	import * as powerfin from '$lib/api/powerfin.mock';

	let selectedDispensers: number[] = [];
	let openingCash = 0;
	let notes = '';
	let loading = false;
	let error = '';

	const dispenserConfigs = $config?.dispensers ?? [];

	function toggleDispenser(id: number) {
		if (selectedDispensers.includes(id)) {
			selectedDispensers = selectedDispensers.filter(d => d !== id);
		} else {
			selectedDispensers = [...selectedDispensers, id];
		}
	}

	async function handleOpenShift() {
		if (selectedDispensers.length === 0) {
			error = 'Seleccione al menos un surtidor';
			return;
		}

		loading = true;
		error = '';

		try {
			const token = $auth.token!;
			const result = await powerfin.openShift(token, {
				dispenser_ids: selectedDispensers,
				opening_cash: openingCash,
				notes
			});
			shift.set(result);
			goto('/');
		} catch {
			error = 'Error al abrir el turno';
		} finally {
			loading = false;
		}
	}
</script>

<div class="min-h-screen flex flex-col items-center justify-center px-6 py-10">
	<div class="w-full max-w-md">
		<div class="text-center mb-8">
			<h2 class="text-2xl font-bold text-gray-800">Abrir Turno</h2>
			<p class="text-gray-500 mt-1">
				{$auth.user?.name ?? 'Usuario'} — {new Date().toLocaleDateString('es-EC', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
			</p>
		</div>

		<!-- Island selection -->
		<div class="card p-6 mb-4">
			<h3 class="text-sm font-semibold text-gray-700 mb-3">Selecciona tu isla:</h3>
			<div class="grid grid-cols-2 gap-3">
				{#each dispenserConfigs as d}
					<button
						class="touch-btn p-4 rounded-xl border-2 text-left transition-colors
							{selectedDispensers.includes(d.dispenser_id)
								? 'border-primary bg-primary/5 text-primary'
								: 'border-gray-200 text-gray-600 hover:border-gray-300'}"
						on:click={() => toggleDispenser(d.dispenser_id)}
					>
						<div class="text-sm font-semibold">{d.name}</div>
						<div class="text-xs text-gray-400 mt-1">{d.hoses.length} pistolas — {d.hoses[0]?.grade_name}</div>
					</button>
				{/each}
			</div>
		</div>

		<!-- Opening cash -->
		<div class="card p-6 mb-4">
			<label for="cash" class="block text-sm font-semibold text-gray-700 mb-2">
				Efectivo inicial:
			</label>
			<input
				id="cash"
				type="number"
				bind:value={openingCash}
				step="0.01"
				min="0"
				class="w-full rounded-xl border border-gray-200 px-4 py-3 text-lg focus:border-primary focus:outline-none"
				placeholder="0.00"
			/>
		</div>

		{#if error}
			<div class="bg-red-50 text-red-600 text-sm text-center rounded-lg py-2 mb-4">{error}</div>
		{/if}

		<button
			class="touch-btn w-full bg-primary text-white rounded-xl py-4 text-lg font-semibold
				disabled:opacity-50 disabled:cursor-not-allowed"
			on:click={handleOpenShift}
			disabled={loading}
		>
			{loading ? 'Abriendo...' : 'Abrir Turno'}
		</button>
	</div>
</div>
