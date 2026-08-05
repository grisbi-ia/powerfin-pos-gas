<script lang="ts">
	import { goto } from '$app/navigation';
	import Header from '$lib/components/Header.svelte';
	import { auth } from '$lib/stores/auth';
	import { shift } from '$lib/stores/shift';
	import { config } from '$lib/stores/config';
	import * as powerfin from '$lib/api/powerfin';
	import type { MechanicalMeterConfig, MeterReadingItem, ShiftMeterPair } from '$lib/api/types';
	import { onMount } from 'svelte';

	let loading = false;
	let error = '';
	let success = '';
	let warnings: string[] = [];
	let openingReadings: Record<number, string> = {};
	let existingPairs: ShiftMeterPair[] = [];
	let hasOpenings = false;  // true if any opening reading already exists
	let lastUpdated: Record<number, string> = {};  // meter_id → timestamp of last update

	// Collect all active meters
	$: allMeters = ($config?.dispensers || []).flatMap(d =>
		(d.mechanical_meters || [])
			.filter(m => m.is_active)
			.map(m => ({ ...m, dispenser_name: d.name }))
	);

	$: metersByDispenser = allMeters.reduce((acc, m) => {
		const key = m.dispenser_id;
		if (!acc[key]) acc[key] = { name: m.dispenser_name, meters: [] };
		acc[key].meters.push(m);
		return acc;
	}, {} as Record<number, { name: string; meters: MechanicalMeterConfig[] }>);

	onMount(async () => {
		if (!$shift) return;
		try {
			const res = await powerfin.getShiftMeterReadings($auth.token!, $shift.shift_id);
			existingPairs = res.meters || [];
			for (const pair of existingPairs) {
				if (pair.opening_reading != null) {
					openingReadings[pair.meter_id] = String(pair.opening_reading);
					hasOpenings = true;
				}
			}
		} catch { /* ignore */ }
	});

	async function handleSaveOpenings() {
		if (!$shift || hasOpenings) return;
		loading = true;
		error = '';
		success = '';
		warnings = [];

		const readings: MeterReadingItem[] = Object.entries(openingReadings)
			.filter(([, v]) => String(v ?? '').trim() !== '')
			.map(([meterId, value]) => ({
				meter_id: parseInt(meterId),
				reading_value: String(value)
			}));

		try {
			await powerfin.updateShiftMeterReadings($auth.token!, $shift.shift_id, {
				reading_type: 'OPENING',
				meter_readings: readings
			});
			success = '✅ Lecturas registradas correctamente';
			hasOpenings = true;
			// Refresh pairs
			const res = await powerfin.getShiftMeterReadings($auth.token!, $shift.shift_id);
			existingPairs = res.meters || [];
		} catch (e: any) {
			error = e?.message || 'Error al guardar lecturas';
		} finally {
			loading = false;
		}
	}

	function fmt(v: number | string | null | undefined): string {
		if (v == null || v === '') return '—';
		return Number(v).toFixed(2);
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

<Header title="Lecturas de Medidores" showBack={true} onBack={() => goto('/cash')} />

<main class="flex-1 px-4 py-6 pb-24">
	<div class="text-center mb-6">
		<div class="text-4xl mb-2">📏</div>
		<h2 class="text-xl font-bold text-gray-800">Registrar Lecturas Iniciales</h2>
		<p class="text-gray-500 text-sm mt-1">
			{#if $shift}
				Turno #{$shift.shift_id} — {$shift.status === 'OPEN' ? 'Abierto' : 'Cerrado'}
			{/if}
		</p>
	</div>

	{#if error}
		<div class="bg-red-50 text-red-600 text-sm text-center rounded-lg py-2 mb-4">{error}</div>
	{/if}
	{#if success}
		<div class="bg-green-50 text-green-700 text-sm text-center rounded-lg py-2 mb-4">{success}</div>
	{/if}
	{#if warnings.length > 0}
		{#each warnings as w}
			<div class="bg-amber-50 text-amber-700 text-sm rounded-lg py-2 px-3 mb-2">{w}</div>
		{/each}
	{/if}

	{#if $shift?.status === 'OPEN'}
		{#if allMeters.length > 0}
			{#if hasOpenings}
				<div class="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4 text-sm text-blue-700">
					🔒 Las lecturas de apertura ya fueron registradas. No se pueden modificar.
				</div>
			{/if}

			{#each Object.values(metersByDispenser) as group}
				<div class="card p-4 mb-4">
					<h3 class="text-sm font-bold text-gray-500 uppercase mb-3">{group.name}</h3>
					{#each group.meters as m}
						<div class="mb-3 last:mb-0">
							<label class="block text-sm text-gray-600 mb-1">
								{m.name}
								{#if m.grade_name} ({m.grade_name}){/if}
								{#if m.hose_side} — Lado {m.hose_side}{/if}
							</label>
							{#if hasOpenings}
								<div class="w-full px-4 py-3 text-lg font-mono text-right bg-gray-50 border border-gray-200 rounded-lg text-gray-700">
									{fmt(openingReadings[m.meter_id])}
								</div>
							{:else}
								<input
									type="number" step="0.01" min="0"
									inputmode="decimal"
									bind:value={openingReadings[m.meter_id]}
									placeholder="0.00"
									class="w-full px-4 py-3 text-lg font-mono text-right border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
								/>
							{/if}
						</div>
					{/each}
				</div>
			{/each}

			{#if !hasOpenings}
				<button
					class="touch-btn w-full bg-primary text-white rounded-xl py-4 text-lg font-semibold disabled:opacity-50"
					on:click={handleSaveOpenings}
					disabled={loading}
				>
					{loading ? 'Guardando...' : '💾 Guardar Lecturas'}
				</button>
			{/if}
		{:else}
			<div class="card p-6 text-center text-gray-400">
				<p>No hay medidores mecánicos configurados.</p>
				<p class="text-xs mt-1">Configúrelos desde el Admin → Dispensadores</p>
			</div>
		{/if}
	{:else if $shift?.status === 'CLOSED'}
		<!-- Show existing readings for a closed shift -->
		{#if existingPairs.length > 0}
			<div class="card p-5 mb-4">
				<h3 class="text-sm font-semibold text-gray-700 mb-3">📏 Lecturas del Turno</h3>
				<div class="overflow-x-auto">
					<table class="w-full text-xs">
						<thead>
							<tr class="text-left text-gray-400 border-b border-gray-100">
								<th class="pb-1 font-medium">Medidor</th>
								<th class="pb-1 font-medium text-right">Apertura</th>
								<th class="pb-1 font-medium text-right">Cierre</th>
								<th class="pb-1 font-medium text-right">Diferencia</th>
							</tr>
						</thead>
						<tbody>
							{#each existingPairs as pair}
								<tr class="border-b border-gray-50">
									<td class="py-1.5">
										<div class="font-medium text-gray-700">{pair.meter_name}</div>
										<div class="text-gray-400">{pair.dispenser_name || ''}{#if pair.grade_name} · {pair.grade_name}{/if}</div>
									</td>
									<td class="py-1.5 text-right font-mono">{pair.opening_reading != null ? Number(pair.opening_reading).toFixed(2) : '—'}</td>
									<td class="py-1.5 text-right font-mono">{pair.closing_reading != null ? Number(pair.closing_reading).toFixed(2) : '—'}</td>
									<td class="py-1.5 text-right font-mono font-semibold">{pair.difference != null ? Number(pair.difference).toFixed(2) : '—'}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{:else}
			<div class="card p-6 text-center text-gray-400">
				<p>No se registraron lecturas en este turno.</p>
			</div>
		{/if}
	{:else}
		<div class="card p-6 text-center text-gray-400">
			<p>No hay un turno activo.</p>
		</div>
	{/if}
</main>
