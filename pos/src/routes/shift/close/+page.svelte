<script lang="ts">
	import { goto } from '$app/navigation';
	import Header from '$lib/components/Header.svelte';
	import { auth } from '$lib/stores/auth';
	import { shift } from '$lib/stores/shift';

	// Mock imports
	import * as powerfin from '$lib/api/powerfin.mock';

	let closingCash = 0;
	let notes = '';
	let loading = false;
	let error = '';

	async function handleCloseShift() {
		if (!$shift) return;
		loading = true;
		error = '';

		try {
			await powerfin.closeShift($auth.token!, $shift.shift_id, {
				closing_cash: closingCash,
				notes
			});
			shift.clear();
			goto('/login');
		} catch {
			error = 'Error al cerrar el turno';
		} finally {
			loading = false;
		}
	}
</script>

<Header title="Cerrar Turno" showBack={true} />

<main class="flex-1 px-4 py-6">
	{#if $shift}
		<div class="card p-6 mb-4">
			<h2 class="text-lg font-semibold text-gray-800 mb-3">Cerrar Turno #{$shift.shift_id}</h2>

			<div class="text-sm text-gray-500 space-y-1 mb-4">
				<p>Inicio: {new Date($shift.opened_at).toLocaleString('es-EC')}</p>
				<p>Apertura: {new Date().toLocaleDateString('es-EC')}</p>
			</div>

			<label for="closing-cash" class="block text-sm font-semibold text-gray-700 mb-2">
				Efectivo final:
			</label>
			<input
				id="closing-cash"
				type="number"
				bind:value={closingCash}
				step="0.01"
				min="0"
				class="w-full rounded-xl border border-gray-200 px-4 py-3 text-lg focus:border-primary focus:outline-none mb-4"
				placeholder="0.00"
			/>

			{#if error}
				<div class="bg-red-50 text-red-600 text-sm text-center rounded-lg py-2 mb-4">{error}</div>
			{/if}

			<button
				class="touch-btn w-full bg-danger text-white rounded-xl py-4 text-lg font-semibold
					disabled:opacity-50"
				on:click={handleCloseShift}
				disabled={loading}
			>
				{loading ? 'Cerrando...' : 'Cerrar Turno'}
			</button>
		</div>
	{/if}
</main>
