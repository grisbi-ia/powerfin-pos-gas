<script lang="ts">
	import { auth, currentUser } from '$lib/stores/auth';
	import { shift } from '$lib/stores/shift';
	import { config } from '$lib/stores/config';
	import { goto } from '$app/navigation';

	import * as powerfin from '$lib/api/powerfin';
	import type { MechanicalMeterConfig } from '$lib/api/types';

	let loading = false;
	let error = '';
	let step = 1; // 1 = confirm, 2 = meter readings

	const now = new Date();
	const dateStr = now.toLocaleDateString('es-EC', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
	const timeStr = now.toLocaleTimeString('es-EC', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

	// Collect all active meters grouped by dispenser
	$: allMeters = ($config?.dispensers || []).flatMap(d =>
		(d.mechanical_meters || [])
			.filter(m => m.is_active)
			.map(m => ({ ...m, dispenser_name: d.name }))
	);

	// Reading inputs: map of meter_id -> value string
	let readings: Record<number, string> = {};

	function initReadings() {
		for (const m of allMeters) {
			if (!(m.meter_id in readings)) readings[m.meter_id] = '';
		}
	}

	// Group meters by dispenser for display
	$: metersByDispenser = allMeters.reduce((acc, m) => {
		const key = m.dispenser_id;
		if (!acc[key]) acc[key] = { name: m.dispenser_name, meters: [] };
		acc[key].meters.push(m);
		return acc;
	}, {} as Record<number, { name: string; meters: MechanicalMeterConfig[] }>);

	function goToStep2() {
		if (allMeters.length === 0) {
			// No meters configured: skip to open directly
			handleOpenShift();
			return;
		}
		step = 2;
		initReadings();
	}

	async function handleOpenShift() {
		loading = true;
		error = '';

		const meterReadings = Object.entries(readings)
			.filter(([, v]) => String(v ?? '').trim() !== '')
			.map(([meterId, value]) => ({
				meter_id: parseInt(meterId),
				reading_value: String(value)
			}));

		try {
			const token = $auth.token!;
			const result = await powerfin.openShift(token, {
				opening_cash: 0,
				notes: '',
				meter_readings: meterReadings.length > 0 ? meterReadings : undefined
			});
			shift.set(result);
			goto('/');
		} catch {
			error = 'Error al abrir el turno. Intente nuevamente.';
		} finally {
			loading = false;
		}
	}

	function formatMeterLabel(m: MechanicalMeterConfig): string {
		if (m.meter_type === 'PRODUCT') return `${m.name} (${m.grade_name || ''})`;
		return `${m.name} — Lado ${m.hose_side || ''}`;
	}

	function truncateDecimal(e: Event) {
		const input = e.target as HTMLInputElement;
		const v = input.value;
		const parts = v.split('.');
		if (parts.length > 1 && parts[1].length > 2) {
			input.value = parts[0] + '.' + parts[1].substring(0, 2);
			input.dispatchEvent(new Event('input'));
		}
	}
</script>

<div class="min-h-screen flex flex-col items-center justify-center px-6 py-10">
	<div class="w-full max-w-md">
		{#if step === 1}
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
				on:click={goToStep2}
			>
				Continuar {allMeters.length > 0 ? `(${allMeters.length} medidores)` : ''}
			</button>

			<button
				class="touch-btn w-full text-gray-400 rounded-xl py-3 text-sm mt-3"
				on:click={() => goto('/')}
			>
				Cancelar
			</button>
		{:else}
			<!-- Step 2: Meter Readings -->
			<div class="text-center mb-8">
				<div class="text-5xl mb-4">📏</div>
				<h2 class="text-2xl font-bold text-gray-800">Lecturas Iniciales</h2>
				<p class="text-gray-500 mt-1">Ingrese las lecturas de los medidores mecánicos</p>
			</div>

			{#each Object.values(metersByDispenser) as group}
				<div class="card p-4 mb-4">
					<h3 class="text-sm font-bold text-gray-500 uppercase mb-3">{group.name}</h3>
					{#each group.meters as m}
						<div class="mb-3 last:mb-0">
							<label class="block text-sm text-gray-600 mb-1">
								{formatMeterLabel(m)}
							</label>
							<input
								type="number"
								step="0.01"
								min="0"
								inputmode="decimal"
								bind:value={readings[m.meter_id]}
								placeholder="0.00"
								class="w-full px-4 py-3 text-lg font-mono text-right border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
							/>
						</div>
					{/each}
				</div>
			{/each}

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
				on:click={() => handleOpenShift()}
			>
				Omitir lecturas y abrir turno
			</button>

			<button
				class="touch-btn w-full text-gray-400 rounded-xl py-3 text-sm"
				on:click={() => (step = 1)}
			>
				Volver
			</button>
		{/if}
	</div>
</div>
