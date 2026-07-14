<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import Header from '$lib/components/Header.svelte';
	import { auth } from '$lib/stores/auth';
	import { shift } from '$lib/stores/shift';
	import * as powerfin from '$lib/api/powerfin';

	let loading = true;
	let error = '';
	let summary: import('$lib/api/types').ShiftCashSummary | null = null;

	$: totalSales = summary
		? summary.total_sales_cash + (summary.non_cash_sales ?? []).reduce((s: number, n) => s + n.total, 0)
		: 0;

	function fmt(v: number): string {
		return '$ ' + v.toFixed(2);
	}

	onMount(async () => {
		if (!$shift || !$auth.token) { error = 'No hay turno abierto'; loading = false; return; }
		try {
			summary = await powerfin.getShiftCashSummary($auth.token, $shift.shift_id);
		} catch {
			error = 'Error al cargar el resumen';
		} finally {
			loading = false;
		}
	});
</script>

<Header title="Resumen de Turno" showBack={true} onBack={() => goto('/cash')} />

<main class="flex-1 px-4 py-4 pb-24">
	{#if loading}
		<div class="flex justify-center py-10">
			<div class="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
		</div>
	{:else if error}
		<div class="card p-6 text-center">
			<div class="text-2xl mb-2">⚠️</div>
			<p class="text-gray-500">{error}</p>
			<button class="touch-btn mt-4 bg-primary text-white rounded-xl px-6 py-3 font-semibold"
				on:click={() => goto('/cash')}>Volver a Caja</button>
		</div>
	{:else if summary}
		<!-- Turno info -->
		<div class="card p-4 mb-3 text-center">
			<div class="text-xs text-gray-400">Turno #{summary.shift_id}</div>
			<div class="text-2xl font-bold text-gray-800 mt-1">{fmt(summary.current_balance)}</div>
			<div class="text-xs text-gray-500">Efectivo en Caja</div>
		</div>

		<!-- Ventas -->
		<div class="card p-4 mb-3">
			<h3 class="text-sm font-semibold text-gray-700 mb-3">💰 Ventas del Turno</h3>
			<div class="space-y-2">
				<div class="flex justify-between text-sm">
					<span class="text-gray-500">Efectivo</span>
					<span class="font-medium text-green-700">{fmt(summary.total_sales_cash)}</span>
				</div>
				{#each summary.non_cash_sales ?? [] as nc}
					<div class="flex justify-between text-sm">
						<span class="text-gray-500">{nc.payment_method}</span>
						<span class="font-medium text-blue-700">{fmt(nc.total)}</span>
					</div>
				{/each}
				<hr class="border-gray-100" />
				<div class="flex justify-between text-sm font-semibold">
					<span class="text-gray-700">Total Ventas</span>
					<span class="text-gray-800">{fmt(totalSales)}</span>
				</div>
			</div>
		</div>

		<!-- Movimientos de Caja -->
		<div class="card p-4 mb-3">
			<h3 class="text-sm font-semibold text-gray-700 mb-3">📋 Movimientos de Caja</h3>
			<div class="space-y-2 text-sm">
				<div class="flex justify-between">
					<span class="text-green-600">+ Ingresos</span>
					<span class="font-medium">{fmt(summary.total_income)}</span>
				</div>
				<div class="flex justify-between">
					<span class="text-red-600">− Egresos</span>
					<span class="font-medium">{fmt(summary.total_expense)}</span>
				</div>
				{#if summary.total_deposits > 0}
				<div class="flex justify-between">
					<span class="text-amber-600">− Depósitos</span>
					<span class="font-medium">{fmt(summary.total_deposits)}</span>
				</div>
				{/if}
				{#if summary.total_transfers_sent > 0}
				<div class="flex justify-between">
					<span class="text-red-600">− Transferencias enviadas</span>
					<span class="font-medium">{fmt(summary.total_transfers_sent)}</span>
				</div>
				{/if}
				{#if summary.total_transfers_received > 0}
				<div class="flex justify-between">
					<span class="text-green-600">+ Transferencias recibidas</span>
					<span class="font-medium">{fmt(summary.total_transfers_received)}</span>
				</div>
				{/if}
				{#if summary.total_safe_drops > 0}
				<div class="flex justify-between">
					<span class="text-red-600">− Safe Drops</span>
					<span class="font-medium">{fmt(summary.total_safe_drops)}</span>
				</div>
				{/if}
			</div>
		</div>

		<!-- Resultado -->
		<div class="card p-4 mb-3 bg-gray-50">
			<h3 class="text-sm font-semibold text-gray-700 mb-2">🧮 Efectivo Resultante</h3>
			<div class="space-y-1 text-xs text-gray-500">
				<div class="flex justify-between">
					<span>Apertura</span><span>{fmt(summary.opening_cash)}</span>
				</div>
				<div class="flex justify-between">
					<span>+ Ventas efectivo</span><span>{fmt(summary.total_sales_cash)}</span>
				</div>
				<div class="flex justify-between">
					<span>+ Ingresos</span><span>{fmt(summary.total_income)}</span>
				</div>
				<div class="flex justify-between">
					<span>+ Transferencias recibidas</span><span>{fmt(summary.total_transfers_received)}</span>
				</div>
				<div class="flex justify-between">
					<span>− Egresos</span><span>{fmt(summary.total_expense)}</span>
				</div>
				<div class="flex justify-between">
					<span>− Depósitos</span><span>{fmt(summary.total_deposits)}</span>
				</div>
				<div class="flex justify-between">
					<span>− Transferencias enviadas</span><span>{fmt(summary.total_transfers_sent)}</span>
				</div>
				<div class="flex justify-between">
					<span>− Safe Drops</span><span>{fmt(summary.total_safe_drops)}</span>
				</div>
				<hr class="border-gray-300 my-1" />
				<div class="flex justify-between text-base font-bold text-gray-800">
					<span>Efectivo en Caja</span>
					<span class={summary.current_balance >= 0 ? 'text-green-700' : 'text-red-600'}>
						{fmt(summary.current_balance)}
					</span>
				</div>
			</div>
		</div>

		<!-- Botones -->
		<div class="grid grid-cols-2 gap-3">
			<button class="touch-btn bg-gray-100 text-gray-700 rounded-xl py-4 font-medium"
				on:click={() => goto('/cash')}>← Volver a Caja</button>
			<button class="touch-btn bg-red-500 text-white rounded-xl py-4 font-semibold"
				on:click={() => goto('/shift/close')}>🔒 Cerrar Turno</button>
		</div>
	{/if}
</main>
