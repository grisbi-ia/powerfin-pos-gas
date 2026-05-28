<script lang="ts">
	import { auth, currentUser } from '$lib/stores/auth';
	import { shift } from '$lib/stores/shift';
	import { goto } from '$app/navigation';

	import * as powerfin from '$lib/api/powerfin';

	let loading = false;
	let error = '';

	const now = new Date();
	const dateStr = now.toLocaleDateString('es-EC', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
	const timeStr = now.toLocaleTimeString('es-EC', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

	async function handleOpenShift() {
		loading = true;
		error = '';

		try {
			const token = $auth.token!;
			const result = await powerfin.openShift(token, {
				opening_cash: 0,
				notes: ''
			});
			shift.set(result);
			goto('/');
		} catch {
			error = 'Error al abrir el turno. Intente nuevamente.';
		} finally {
			loading = false;
		}
	}
</script>

<div class="min-h-screen flex flex-col items-center justify-center px-6 py-10">
	<div class="w-full max-w-md">
		<div class="text-center mb-8">
			<div class="text-5xl mb-4">🔓</div>
			<h2 class="text-2xl font-bold text-gray-800">Apertura de Turno</h2>
			<p class="text-gray-500 mt-1">Confirme los datos para iniciar operaciones</p>
		</div>

		<!-- Datos del usuario y turno -->
		<div class="card p-6 mb-4">
			<div class="space-y-3">
				<div class="flex justify-between items-center py-1">
					<span class="text-sm text-gray-500">Usuario</span>
					<span class="text-sm font-semibold text-gray-800">{$currentUser?.name ?? '—'}</span>
				</div>
				<hr class="border-gray-100" />
				<div class="flex justify-between items-center py-1">
					<span class="text-sm text-gray-500">Rol</span>
					<span class="text-sm font-semibold text-gray-800">{$currentUser?.role === 'SUPERVISOR' ? 'Supervisor' : 'Despachador'}</span>
				</div>
				<hr class="border-gray-100" />
				<div class="flex justify-between items-center py-1">
					<span class="text-sm text-gray-500">Estación</span>
					<span class="text-sm font-semibold text-gray-800">{$currentUser?.location_name ?? '—'}</span>
				</div>
				<hr class="border-gray-100" />
				<div class="flex justify-between items-center py-1">
					<span class="text-sm text-gray-500">Fecha</span>
					<span class="text-sm font-semibold text-gray-800">{dateStr}</span>
				</div>
				<hr class="border-gray-100" />
				<div class="flex justify-between items-center py-1">
					<span class="text-sm text-gray-500">Hora apertura</span>
					<span class="text-sm font-semibold text-gray-800">{timeStr}</span>
				</div>
				<hr class="border-gray-100" />
				<div class="flex justify-between items-center py-1">
					<span class="text-sm text-gray-500">Efectivo inicial</span>
					<span class="text-sm font-bold text-gray-800">$ 0.00</span>
				</div>
			</div>
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
			{loading ? 'Abriendo turno...' : 'Confirmar y Abrir Turno'}
		</button>

		<button
			class="touch-btn w-full text-gray-400 rounded-xl py-3 text-sm mt-3"
			on:click={() => goto('/')}
		>
			Cancelar
		</button>
	</div>
</div>
