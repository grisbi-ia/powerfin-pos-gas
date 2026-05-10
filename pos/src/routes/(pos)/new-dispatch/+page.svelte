<script lang="ts">
	import { goto } from '$app/navigation';
	import Header from '$lib/components/Header.svelte';
	import { page } from '$app/stores';

	let dispenserId = 0;
	$: dispenserId = Number($page.url.searchParams.get('dispenser') ?? '0');
</script>

<Header title="Nueva Venta" showBack={true} />

<main class="flex-1 px-4 py-6">
	<div class="card p-6 text-center">
		<h2 class="text-lg font-semibold text-gray-800 mb-2">
			Surtidor {dispenserId}
		</h2>
		<p class="text-gray-500 text-sm mb-4">
			Pantalla de nueva venta — disponible en Fase 4
		</p>

		<div class="bg-gray-50 rounded-xl p-4 mb-4">
			<div class="text-sm text-gray-600 mb-2">Funcionalidades planeadas:</div>
			<ul class="text-xs text-gray-400 space-y-1">
				<li>Búsqueda de cliente (placa, cédula, nombre)</li>
				<li>Selección de monto o volumen</li>
				<li>Precio según lista del cliente</li>
				<li>Autorización del despacho</li>
			</ul>
		</div>

		<button
			class="touch-btn bg-primary text-white rounded-xl px-6 py-3 text-sm"
			on:click={() => goto('/')}
		>
			Volver al inicio
		</button>
	</div>
</main>
