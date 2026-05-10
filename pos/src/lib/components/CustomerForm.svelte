<script lang="ts">
	import type { CustomerFormData } from '$lib/api/types';

	export let mode: 'incomplete' | 'registration' = 'registration';
	export let plate = '';
	export let onSubmit: (data: CustomerFormData) => void;
	export let onCancel: () => void;
	export let loading = false;

	let idType: 'CED' | 'RUC' = 'CED';
	let idNumber = '';
	let name = '';
	let email = '';

	$: isValid = (() => {
		if (mode === 'incomplete') {
			return email.length > 0;
		}
		return idNumber.length > 0 && name.length > 0;
	})();

	function handleSubmit() {
		if (mode === 'incomplete') {
			onSubmit({ id_type: 'CED', id_number: '', name: '', email, plate });
		} else {
			onSubmit({ id_type: idType, id_number: idNumber, name, email, plate });
		}
	}
</script>

<div class="card p-4">
	<div class="text-center mb-4">
		{#if mode === 'incomplete'}
			<div class="text-sm font-medium text-gray-700">Datos incompletos</div>
			<div class="text-xs text-gray-400 mt-1">Falta el correo electrónico</div>
		{:else}
			<div class="text-sm font-medium text-gray-700">Registrar nuevo cliente</div>
			<div class="text-xs text-gray-400 mt-1">No se encontró el vehículo</div>
		{/if}
	</div>

	<div class="bg-blue-50 rounded-xl p-3 mb-4 text-center">
		<div class="text-xs text-gray-500">Placa</div>
		<div class="text-lg font-mono font-bold text-blue-600">{plate}</div>
	</div>

	<form on:submit|preventDefault={handleSubmit} class="space-y-3">
		{#if mode === 'registration'}
			<div>
				<label class="block text-xs text-gray-500 mb-1">Tipo de ID</label>
				<div class="flex gap-2">
					<button
						type="button"
						class="flex-1 py-2 rounded-lg text-sm font-medium transition-colors
						{idType === 'CED' ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600'}"
						on:click={() => idType = 'CED'}
					>
						Cédula
					</button>
					<button
						type="button"
						class="flex-1 py-2 rounded-lg text-sm font-medium transition-colors
						{idType === 'RUC' ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600'}"
						on:click={() => idType = 'RUC'}
					>
						RUC
					</button>
				</div>
			</div>

			<div>
				<label for="id-number" class="block text-xs text-gray-500 mb-1">Número de identificación</label>
				<input
					id="id-number"
					type="text"
					bind:value={idNumber}
					class="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm
						focus:border-primary focus:outline-none"
					placeholder={idType === 'CED' ? '0912345678' : '1790012345001'}
				/>
			</div>

			<div>
				<label for="name" class="block text-xs text-gray-500 mb-1">Nombre / Razón Social</label>
				<input
					id="name"
					type="text"
					bind:value={name}
					class="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm
						focus:border-primary focus:outline-none"
					placeholder="Nombres completos"
				/>
			</div>
		{/if}

		<div>
			<label for="email" class="block text-xs text-gray-500 mb-1">Correo electrónico</label>
			<input
				id="email"
				type="email"
				bind:value={email}
				class="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm
					focus:border-primary focus:outline-none"
				placeholder="email@ejemplo.com"
			/>
		</div>

		<div class="flex gap-3 pt-2">
			<button
				type="button"
				class="touch-btn flex-1 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-xl py-3 font-medium"
				on:click={onCancel}
				disabled={loading}
			>
				Cancelar
			</button>
			<button
				type="submit"
				class="touch-btn flex-1 bg-primary hover:bg-primary/90 text-white rounded-xl py-3 font-bold disabled:opacity-50"
				disabled={loading || !isValid}
			>
				{loading ? 'Guardando...' : 'Continuar'}
			</button>
		</div>
	</form>
</div>