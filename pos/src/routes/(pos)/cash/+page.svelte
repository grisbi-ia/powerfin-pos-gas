<script lang="ts">
	import { goto } from '$app/navigation';
	import Header from '$lib/components/Header.svelte';
	import { auth } from '$lib/stores/auth';
	import { shift } from '$lib/stores/shift';
	import * as powerfin from '$lib/api/powerfin';

	function handleOpenShift() {
		goto('/shift/open');
	}
</script>

<Header title="Caja" showBack={true} onBack={() => goto('/')} />

<main class="flex-1 px-4 py-4 pb-24">
	<!-- Botones de acción rápida -->
	<div class="grid grid-cols-2 gap-3 mb-4">
		<button
			class="touch-btn card p-4 text-center hover:shadow-md transition disabled:opacity-40"
			on:click={() => goto('/cash/movement?type=INCOME')}
			disabled={!$shift}
		>
			<div class="text-2xl mb-1">💰</div>
			<div class="text-sm font-semibold text-green-700">Ingreso</div>
		</button>
		<button
			class="touch-btn card p-4 text-center hover:shadow-md transition disabled:opacity-40"
			on:click={() => goto('/cash/movement?type=EXPENSE')}
			disabled={!$shift}
		>
			<div class="text-2xl mb-1">💸</div>
			<div class="text-sm font-semibold text-red-600">Egreso</div>
		</button>
		<button
			class="touch-btn card p-4 text-center hover:shadow-md transition disabled:opacity-40"
			on:click={() => goto('/cash/movement?type=DEPOSIT')}
			disabled={!$shift}
		>
			<div class="text-2xl mb-1">🏦</div>
			<div class="text-sm font-semibold text-amber-600">Depósito</div>
		</button>
		<button
			class="touch-btn card p-4 text-center hover:shadow-md transition disabled:opacity-40"
			on:click={() => goto('/cash/transfer')}
			disabled={!$shift}
		>
			<div class="text-2xl mb-1">📤</div>
			<div class="text-sm font-semibold text-blue-700">Transferir</div>
		</button>
	</div>

	<!-- Resumen de Turno + Lecturas de Medidores -->
	<div class="grid grid-cols-2 gap-3 mb-3">
		<button
			class="touch-btn card p-3 text-center hover:shadow-md transition disabled:opacity-40 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200"
			on:click={() => goto('/cash/summary')}
			disabled={!$shift}
		>
			<div class="text-xl mb-1">📊</div>
			<div class="text-xs font-semibold text-blue-700">Resumen de Turno</div>
		</button>
		<button
			class="touch-btn card p-3 text-center hover:shadow-md transition disabled:opacity-40 bg-gradient-to-r from-teal-50 to-emerald-50 border border-teal-200"
			on:click={() => goto('/shift/meters')}
			disabled={!$shift}
		>
			<div class="text-xl mb-1">📏</div>
			<div class="text-xs font-semibold text-teal-700">Lecturas Medidores</div>
		</button>
	</div>

	<!-- Cerrar Turno -->
	<button
		class="touch-btn card p-4 text-center hover:shadow-md transition w-full mb-4 disabled:opacity-40"
		on:click={() => goto('/shift/close')}
		disabled={!$shift}
	>
		<div class="text-2xl mb-1">🔒</div>
		<div class="text-sm font-semibold text-red-600">Cerrar Turno</div>
	</button>

	{#if !$shift}
		<div class="card p-4 text-center">
			<p class="text-sm text-gray-500 mb-3">Debe abrir su turno para realizar movimientos de caja.</p>
			<button
				class="touch-btn w-full bg-primary text-white rounded-xl py-4 text-lg font-semibold"
				on:click={handleOpenShift}
			>
				🔓 Abrir Turno
			</button>
		</div>
	{/if}
</main>
