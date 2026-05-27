<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { shift } from '$lib/stores/shift';
	import { goto } from '$app/navigation';

	// Mock imports
	import * as powerfin from '$lib/api/powerfin';

	let openingCash = 0;
	let notes = '';
	let loading = false;
	let error = '';

	async function handleOpenShift() {
		loading = true;
		error = '';

		try {
			const token = $auth.token!;
			const result = await powerfin.openShift(token, {
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

		<!-- Opening cash -->
		<div class="card p-6 mb-4">
			<label for="cash" class="block text-sm font-semibold text-gray-700 mb-2">
				Efectivo para cambios:
			</label>
			<p class="text-xs text-gray-400 mb-3">
				Monedas y billetes pequeños para dar vuelto a los clientes.
			</p>
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
