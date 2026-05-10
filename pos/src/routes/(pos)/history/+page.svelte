<script lang="ts">
	import { goto } from '$app/navigation';
	import Header from '$lib/components/Header.svelte';
	import { shift } from '$lib/stores/shift';
</script>

<Header title="Historial" showBack={true} />

<main class="flex-1 px-4 py-6">
	<div class="card p-6 text-center">
		<h2 class="text-lg font-semibold text-gray-800 mb-2">
			Historial del Turno
		</h2>

		{#if $shift}
			<p class="text-sm text-gray-500 mb-4">
				Turno #{$shift.shift_id} — {$shift.status === 'OPEN' ? 'Abierto' : 'Cerrado'}
			</p>
		{/if}

		<div class="bg-gray-50 rounded-xl p-4 mb-4">
			<p class="text-xs text-gray-400">Historial de despachos disponible en Fase 6</p>
		</div>

		<button
			class="touch-btn bg-primary text-white rounded-xl px-6 py-3 text-sm"
			on:click={() => goto('/')}
		>
			Volver al inicio
		</button>
	</div>
</main>
