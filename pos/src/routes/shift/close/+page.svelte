<script lang="ts">
	import { goto } from '$app/navigation';
	import Header from '$lib/components/Header.svelte';
	import { auth } from '$lib/stores/auth';
	import { shift } from '$lib/stores/shift';
	import { config } from '$lib/stores/config';
	import * as powerfin from '$lib/api/powerfin';
	import * as bridge from '$lib/api/bridge';
	import type { CloseShiftResponse } from '$lib/api/types';

	let loading = false;
	let error = '';
	let showConfirm = false;
	let closed = false;
	let printing = false;
	let printed = false;
	let result: CloseShiftResponse | null = null;

	function formatCurrency(v: number | string): string {
		const num = typeof v === 'number' ? v : Number(v ?? 0);
		return '$ ' + num.toFixed(2);
	}

	async function handleCloseShift() {
		if (!$shift) return;
		loading = true;
		error = '';

		try {
			const res = await powerfin.closeShift($auth.token!, $shift.shift_id, { notes: '' });
			result = res;
			closed = true;
			shift.clear();
		} catch {
			error = 'Error al cerrar el turno';
		} finally {
			loading = false;
		}
	}

	async function handlePrint() {
		if (!result || !$config || printing) return;
		printing = true;
		const loc = $config.location;
		const totalCash = result.opening_cash + result.cash_income + result.sales_cash - result.cash_expense - result.cash_deposits - result.cash_transfers_out + result.cash_transfers_in - result.cash_safe_drops;
		const totalSales = result.sales_cash + result.non_cash_sales.reduce((s, n) => s + n.total, 0);
		try {
			await bridge.printReceipt({
				type: 'SHIFT_CLOSE',
				printerIp: $config?.cash_printer_ip || '',
				printerPort: $config?.cash_printer_port || 9100,
				shiftData: {
					locationName: loc?.name || '',
					locationAddress: loc?.address || '',
					locationRuc: loc?.ruc || '',
					locationPhone: loc?.phone || '',
					date: new Date().toLocaleDateString('es-EC'),
					time: new Date().toLocaleTimeString('es-EC'),
					userName: ($shift as any)?.user_name || '',
					shiftId: String(result.shift_id),
					openedAt: '',
					closedAt: result.closed_at ? new Date(result.closed_at).toLocaleString('es-EC') : '',
					openingCash: result.opening_cash.toFixed(2),
					salesCash: result.sales_cash.toFixed(2),
					salesCashCount: String(result.sales_cash_count),
					income: result.cash_income.toFixed(2),
					incomeCount: String(result.cash_income_count),
					expense: result.cash_expense.toFixed(2),
					expenseCount: String(result.cash_expense_count),
					deposits: result.cash_deposits.toFixed(2),
					depositsCount: String(result.cash_deposits_count),
					transfersOut: result.cash_transfers_out.toFixed(2),
					transfersOutCount: String(result.cash_transfers_out_count),
					transfersIn: result.cash_transfers_in.toFixed(2),
					transfersInCount: String(result.cash_transfers_in_count),
					safeDrops: result.cash_safe_drops.toFixed(2),
					safeDropsCount: String(result.cash_safe_drops_count),
					surplus: result.surplus > 0 ? result.surplus.toFixed(2) : '',
					shortage: result.shortage > 0 ? result.shortage.toFixed(2) : '',
					totalCash: totalCash.toFixed(2),
					totalSales: totalSales.toFixed(2),
					nonCashSales: result.non_cash_sales.map(n => ({
						method_name: n.method_name,
						count: n.count,
						total: n.total.toFixed(2),
					})),
				}
			});
			printed = true;
		} catch {
			error = 'Error al imprimir — revise la impresora';
		} finally {
			printing = false;
		}
	}

	function handleBack() { goto('/'); }
</script>

<Header title="Cerrar Turno" showBack={!closed} onBack={handleBack} />

<main class="flex-1 px-4 py-6 pb-24">
	{#if $shift && !closed}
		<div class="card p-6 mb-4">
			<h2 class="text-lg font-semibold text-gray-800 mb-3">Cerrar Turno #{$shift.shift_id}</h2>
			<p class="text-sm text-gray-500 mb-4">
				Inicio: {new Date($shift.opened_at).toLocaleString('es-EC')}
			</p>

			<div class="bg-amber-50 text-amber-700 text-sm rounded-lg p-3 mb-4">
				⚠️ Antes de cerrar, asegúrese de haber realizado todos sus depósitos y transferencias.
				Su efectivo en caja debe ser CERO.
			</div>

			{#if error}
				<div class="bg-red-50 text-red-600 text-sm text-center rounded-lg py-2 mb-4">{error}</div>
			{/if}

			{#if !showConfirm}
				<button
					class="touch-btn w-full bg-danger text-white rounded-xl py-4 text-lg font-semibold"
					on:click={() => showConfirm = true}
				>
					Cerrar Turno
				</button>
			{/if}
		</div>
	{/if}

	{#if !$shift && !closed}
		<div class="card p-6 text-center">
			<div class="text-3xl mb-3">🔒</div>
			<p class="text-gray-500">No hay un turno abierto.</p>
			<button class="touch-btn mt-4 bg-primary text-white rounded-xl px-6 py-3" on:click={handleBack}>
				Ir al inicio
			</button>
		</div>
	{/if}

	<!-- Resultado post-cierre -->
	{#if closed && result}
		<div class="card p-5 mb-4 text-center">
			<div class="text-4xl mb-2">
				{result.surplus === 0 && result.shortage === 0 ? '✅' : '⚠️'}
			</div>
			<h2 class="text-lg font-semibold text-gray-800 mb-1">Turno Cerrado</h2>

			{#if result.surplus === 0 && result.shortage === 0}
				<p class="text-green-600 font-semibold">Cuadre perfecto — diferencia $0.00</p>
			{:else if result.surplus > 0}
				<p class="text-amber-600 font-semibold">Sobrante: {formatCurrency(result.surplus)}</p>
			{:else if result.shortage > 0}
				<p class="text-red-600 font-semibold">Faltante: {formatCurrency(result.shortage)}</p>
			{/if}
		</div>

		<!-- Sección 1: Resumen de Efectivo -->
		<div class="card p-5 mb-4">
			<h3 class="text-sm font-semibold text-gray-700 mb-3">💰 Resumen de Efectivo</h3>

			<div class="space-y-2 text-sm">
				<div class="flex justify-between">
					<span class="text-gray-500">Apertura</span>
					<span class="font-medium">{formatCurrency(result.opening_cash)}</span>
				</div>

				{#if result.cash_income_count > 0}
					<div class="flex justify-between">
						<span class="text-gray-500">Ingresos ({result.cash_income_count})</span>
						<span class="font-medium text-green-600">+{formatCurrency(result.cash_income)}</span>
					</div>
				{/if}

				{#if result.cash_expense_count > 0}
					<div class="flex justify-between">
						<span class="text-gray-500">Egresos ({result.cash_expense_count})</span>
						<span class="font-medium text-red-600">-{formatCurrency(result.cash_expense)}</span>
					</div>
				{/if}

				{#if result.cash_deposits_count > 0}
					<div class="flex justify-between">
						<span class="text-gray-500">Depósitos ({result.cash_deposits_count})</span>
						<span class="font-medium text-red-600">-{formatCurrency(result.cash_deposits)}</span>
					</div>
				{/if}

				{#if result.cash_transfers_out_count > 0}
					<div class="flex justify-between">
						<span class="text-gray-500">Transferencias enviadas ({result.cash_transfers_out_count})</span>
						<span class="font-medium text-red-600">-{formatCurrency(result.cash_transfers_out)}</span>
					</div>
				{/if}

				{#if result.cash_transfers_in_count > 0}
					<div class="flex justify-between">
						<span class="text-gray-500">Transferencias recibidas ({result.cash_transfers_in_count})</span>
						<span class="font-medium text-green-600">+{formatCurrency(result.cash_transfers_in)}</span>
					</div>
				{/if}

				{#if result.cash_safe_drops_count > 0}
					<div class="flex justify-between">
						<span class="text-gray-500">Safe Drops ({result.cash_safe_drops_count})</span>
						<span class="font-medium text-red-600">-{formatCurrency(result.cash_safe_drops)}</span>
					</div>
				{/if}

				<div class="flex justify-between">
					<span class="text-gray-500">Ventas Efectivo ({result.sales_cash_count})</span>
					<span class="font-medium text-green-600">+{formatCurrency(result.sales_cash)}</span>
				</div>

				{#if result.surplus > 0}
					<div class="border-t border-gray-200 pt-2 flex justify-between font-semibold">
						<span class="text-amber-600">Sobrante de Efectivo</span>
						<span>{formatCurrency(result.surplus)}</span>
					</div>
				{:else if result.shortage > 0}
					<div class="border-t border-gray-200 pt-2 flex justify-between font-semibold">
						<span class="text-red-600">Faltante de Efectivo</span>
						<span class="text-red-600">-{formatCurrency(result.shortage)}</span>
					</div>
				{:else}
					<div class="border-t border-gray-200 pt-2 flex justify-between font-semibold">
						<span class="text-green-600">Efectivo en CERO</span>
						<span>{formatCurrency(0)}</span>
					</div>
				{/if}
			</div>
		</div>

		<!-- Sección 2: Otras formas de pago -->
		{#if result.non_cash_sales.length > 0}
			<div class="card p-5 mb-4">
				<h3 class="text-sm font-semibold text-gray-700 mb-3">💳 Otras Formas de Pago</h3>
				<div class="space-y-2 text-sm">
					{#each result.non_cash_sales as sale}
						<div class="flex justify-between">
							<span class="text-gray-500">{sale.method_name} ({sale.count})</span>
							<span class="font-medium">{formatCurrency(sale.total)}</span>
						</div>
					{/each}
				</div>
			</div>
		{/if}

		<!-- Botones -->
		{#if printing}
			<div class="mb-4 text-center text-sm text-blue-600 animate-pulse">Enviando a impresora…</div>
		{:else if printed}
			<div class="mb-4 bg-green-50 text-green-700 text-sm text-center rounded-xl py-3 flex items-center justify-center gap-2">
				<span>✅</span> Impresión enviada — puede volver a imprimir si lo necesita
			</div>
		{/if}

		{#if error}
			<div class="bg-red-50 text-red-600 text-sm text-center rounded-lg py-2 mb-3">{error}</div>
		{/if}

		<div class="grid grid-cols-2 gap-3">
			<button class="touch-btn bg-primary text-white rounded-xl py-4 font-semibold disabled:opacity-50" on:click={handlePrint} disabled={printing}>
				{printing ? 'Imprimiendo…' : printed ? '🖨 Reimprimir' : '🖨 Imprimir'}
			</button>
			<button class="touch-btn bg-gray-200 text-gray-700 rounded-xl py-4 font-semibold" on:click={handleBack}>
				Ir al inicio
			</button>
		</div>
	{/if}
</main>

<!-- Modal de confirmación -->
{#if showConfirm}
	<div class="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true">
		<div class="absolute inset-0 bg-black/50" on:click={() => showConfirm = false}></div>
		<div class="relative bg-white rounded-2xl shadow-xl w-full max-w-sm p-6">
			<div class="text-center mb-4">
				<div class="w-12 h-12 mx-auto mb-3 rounded-full bg-red-100 flex items-center justify-center">
					<span class="text-2xl">⚠️</span>
				</div>
				<h3 class="text-lg font-semibold text-gray-800">¿Cerrar turno?</h3>
				<p class="text-sm text-gray-500 mt-1">Esta acción no se puede deshacer. ¿Está seguro de que desea cerrar el turno #{$shift?.shift_id}?</p>
			</div>
			<div class="grid grid-cols-2 gap-3">
				<button class="touch-btn bg-gray-200 text-gray-700 rounded-xl py-3 font-semibold" on:click={() => showConfirm = false}>
					Cancelar
				</button>
				<button
					class="touch-btn bg-danger text-white rounded-xl py-3 font-semibold disabled:opacity-50"
					on:click={() => { showConfirm = false; handleCloseShift(); }}
					disabled={loading}
				>
					{loading ? 'Cerrando...' : 'Sí, Cerrar'}
				</button>
			</div>
		</div>
	</div>
{/if}
