<script lang="ts">
	import type { VehicleResult } from '$lib/api/types';

	export let vehicle: VehicleResult;
	export let onConfirm: () => void;
	export let onChangeBilling: () => void;
</script>

<div class="card p-4">
	<div class="text-center mb-4">
		<div class="text-xs text-gray-500 uppercase tracking-wide">Datos del propietario</div>
		<div class="text-sm text-gray-400 mt-1">Para facturación</div>
	</div>

	<div class="bg-blue-50 rounded-xl p-3 mb-4 text-center">
		<div class="text-xs text-blue-500">Placa</div>
		<div class="text-lg font-mono font-bold text-blue-700">{vehicle.plate}</div>
	</div>

	<div class="bg-gray-50 rounded-xl p-4 mb-4">
		<div class="text-sm font-medium text-gray-800">{vehicle.owner?.name ?? 'N/A'}</div>
		<div class="text-xs text-gray-500 mt-1">
			{vehicle.owner?.id_type}: {vehicle.owner?.id_number}
		</div>
		{#if vehicle.owner?.email}
			<div class="text-xs text-gray-500 mt-1">{vehicle.owner.email}</div>
		{/if}
		{#if vehicle.owner?.phone}
			<div class="text-xs text-gray-500 mt-1">{vehicle.owner.phone}</div>
		{/if}
	</div>

	{#if vehicle.price_list !== 'STANDARD'}
		<div class="bg-purple-50 rounded-xl px-3 py-2 mb-4 text-center">
			<span class="text-purple-700 font-medium text-sm">{vehicle.price_list_name}</span>
		</div>
	{/if}

	<div class="text-center text-sm text-gray-500 mb-4">
		¿Los datos de facturación son correctos?
	</div>

	<div class="flex gap-3">
		<button
			class="touch-btn flex-1 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-xl py-3 font-medium"
			on:click={onChangeBilling}
		>
			Cambiar
		</button>
		<button
			class="touch-btn flex-1 bg-green-500 hover:bg-green-600 text-white rounded-xl py-3 font-bold"
			on:click={onConfirm}
		>
			Correcto
		</button>
	</div>
</div>