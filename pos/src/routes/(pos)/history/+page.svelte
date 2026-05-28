<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import Header from '$lib/components/Header.svelte';
	import { auth } from '$lib/stores/auth';
	import { shift } from '$lib/stores/shift';
	import { config } from '$lib/stores/config';
	import * as powerfin from '$lib/api/powerfin';
	import * as bridge from '$lib/api/bridge';
	import type { DispatchOrder, CashMovement } from '$lib/api/types';

	let dispatches: DispatchOrder[] = [];
	let movements: CashMovement[] = [];
	let loading = true;
	let error = '';
	let activeTab: 'dispatches' | 'cash' = 'dispatches';
	let printing: string | null = null; // order_id being printed
	let printError: string | null = null;
	let refreshTimer: ReturnType<typeof setInterval> | null = null;
	let dispatchCount = 0;
	let dispatchTotal = 0;
	let incomeTotal = 0;
	let expenseTotal = 0;

	async function loadData() {
		if (!$auth.token || !$shift) return;
		try {
			[dispatches, movements] = await Promise.all([
				powerfin.getShiftDispatches($auth.token, $shift.shift_id),
				powerfin.getCashMovements($auth.token, $shift.shift_id)
			]);

			// Sort dispatches newest first
			dispatches.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

			// Calculate totals
			dispatchCount = dispatches.filter(d => d.status === 'COMPLETED' || d.status === 'COLLECTED').length;
			dispatchTotal = dispatches
				.filter(d => d.status === 'COMPLETED' || d.status === 'COLLECTED')
				.reduce((s, d) => s + (d.final_amount ?? 0), 0);
			incomeTotal = movements
				.filter(m => m.type === 'INCOME')
				.reduce((s, m) => s + m.amount, 0);
			expenseTotal = movements
				.filter(m => m.type === 'EXPENSE' || m.type === 'SAFE_DROP' || m.type === 'TRANSFER_OUT')
				.reduce((s, m) => s + m.amount, 0);

			error = '';
		} catch {
			error = 'Error al cargar historial';
		} finally {
			loading = false;
		}
	}

	function formatCurrency(value: number | undefined | null): string {
		return '$ ' + (value ?? 0).toFixed(2);
	}

	function formatTime(iso: string): string {
		const d = new Date(iso);
		return d.toLocaleTimeString('es-EC', { hour: '2-digit', minute: '2-digit' });
	}

	function formatDate(iso: string): string {
		const d = new Date(iso);
		return d.toLocaleDateString('es-EC', { day: '2-digit', month: 'short' }) + ' ' +
			d.toLocaleTimeString('es-EC', { hour: '2-digit', minute: '2-digit' });
	}

	function statusColor(status: string): string {
		switch (status) {
			case 'COMPLETED': return 'bg-green-100 text-green-700';
			case 'COLLECTED': return 'bg-blue-100 text-blue-700';
			case 'CANCELLED': return 'bg-red-100 text-red-600';
			case 'FUELLING': return 'bg-yellow-100 text-yellow-700';
			case 'AUTHORIZED': return 'bg-orange-100 text-orange-700';
			default: return 'bg-gray-100 text-gray-600';
		}
	}

	function statusLabel(status: string): string {
		switch (status) {
			case 'COMPLETED': return 'Completado';
			case 'COLLECTED': return 'Cobrado';
			case 'CANCELLED': return 'Cancelado';
			case 'FUELLING': return 'Despachando';
			case 'AUTHORIZED': return 'Autorizado';
			case 'PENDING': return 'Pendiente';
			default: return status;
		}
	}

	function movementIcon(type: string): string {
		switch (type) {
			case 'INCOME': return '💰';
			case 'EXPENSE': return '💸';
			case 'TRANSFER_OUT': return '📤';
			case 'SAFE_DROP': return '🏦';
			default: return '📋';
		}
	}

	function movementLabel(type: string): string {
		switch (type) {
			case 'INCOME': return 'Ingreso';
			case 'EXPENSE': return 'Egreso';
			case 'TRANSFER_OUT': return 'Transferencia enviada';
			case 'SAFE_DROP': return 'Depósito caja fuerte';
			default: return type;
		}
	}

	async function handleReprint(order: DispatchOrder) {
		if (!$config) return;
		const dispenser = $config.dispensers.find(d => d.dispenser_id === order.dispenser_id);
		const island = dispenser?.printer_island ?? 1;

		printing = order.order_id;
		printError = null;
		try {
			await bridge.printReceipt({
				type: 'FUEL_RECEIPT',
				island,
				dispenserId: order.dispenser_id,
				fuelData: {
					dispenserId: order.dispenser_id,
					orderId: order.order_id,
					volume: order.final_volume ?? '0',
					amount: (order.final_amount ?? 0).toFixed(2),
					unitPrice: (order.unit_price ?? 0).toFixed(3),
					paymentMethod: order.payment_method,
					grade: order.grade,
					customerName: order.customer_name,
					plate: order.plate
				}
			});
		} catch {
			printError = order.order_id;
		} finally {
			printing = null;
		}
	}

	onMount(() => {
		loadData();
		refreshTimer = setInterval(loadData, 15_000);
	});

	onDestroy(() => {
		if (refreshTimer) clearInterval(refreshTimer);
	});
</script>

<Header title="Historial" showBack={true} onBack={() => goto('/')} />

<main class="flex-1 px-4 py-4 pb-24">
	{#if !$shift}
		<div class="card p-6 text-center mt-8">
			<div class="text-3xl mb-3">🔒</div>
			<h2 class="text-lg font-bold text-gray-800 mb-2">Turno no aperturado</h2>
			<p class="text-sm text-gray-500 mb-4">Debe abrir su turno para ver el historial.</p>
			<button class="touch-btn bg-primary text-white rounded-xl px-6 py-3 text-sm font-semibold" on:click={() => goto('/')}>
				Ir al inicio
			</button>
		</div>
	{:else if loading}
		<div class="text-center text-gray-500 py-8">Cargando...</div>
	{:else if error}
		<div class="bg-red-50 text-red-600 text-sm text-center rounded-xl py-3">{error}</div>
	{:else}
		<!-- Resumen -->
		<div class="card p-4 mb-4">
			<div class="text-xs text-gray-500 mb-2">Turno #{$shift.shift_id} · {$shift.status === 'OPEN' ? 'En curso' : 'Cerrado'}</div>
			<div class="grid grid-cols-2 gap-3">
				<div class="bg-gray-50 rounded-lg p-3 text-center">
					<div class="text-lg font-bold text-gray-800">{dispatchCount}</div>
					<div class="text-xs text-gray-400">Despachos</div>
				</div>
				<div class="bg-gray-50 rounded-lg p-3 text-center">
					<div class="text-lg font-bold text-primary">{formatCurrency(dispatchTotal)}</div>
					<div class="text-xs text-gray-400">Total ventas</div>
				</div>
			</div>
		</div>

		<!-- Tabs -->
		<div class="flex border-b border-gray-200 mb-4">
			<button
				class="flex-1 py-3 text-sm font-semibold border-b-2 transition
					{activeTab === 'dispatches' ? 'border-primary text-primary' : 'border-transparent text-gray-400'}"
				on:click={() => { activeTab = 'dispatches'; }}
			>
				⛽ Despachos ({dispatchCount})
			</button>
			<button
				class="flex-1 py-3 text-sm font-semibold border-b-2 transition
					{activeTab === 'cash' ? 'border-primary text-primary' : 'border-transparent text-gray-400'}"
				on:click={() => { activeTab = 'cash'; }}
			>
				💰 Caja ({movements.length})
			</button>
		</div>

		<!-- Tab: Despachos -->
		{#if activeTab === 'dispatches'}
			{#if dispatches.length === 0}
				<div class="text-center text-sm text-gray-400 py-8">
					<div class="text-3xl mb-2">⛽</div>
					Sin despachos en este turno
				</div>
			{:else}
				<div class="space-y-3">
					{#each dispatches as order (order.order_id)}
						<div class="card p-4">
							<div class="flex items-start justify-between mb-2">
								<div class="flex-1 min-w-0">
									<div class="flex items-center gap-2 mb-1">
										<span class="text-xs font-mono text-gray-400">{order.order_id}</span>
										<span class="px-2 py-0.5 rounded-full text-xs font-medium {statusColor(order.status)}">
											{statusLabel(order.status)}
										</span>
									</div>
									<div class="text-xs text-gray-400">
										Surtidor {order.dispenser_id} · Lado {order.side} · Pistola {order.hose_id}
									</div>
								</div>
								<div class="text-right ml-3">
									<div class="text-sm font-bold text-gray-800">
										{formatCurrency(order.final_amount)}
									</div>
									<div class="text-xs text-gray-400">
										{order.final_volume ?? '—'} L · {order.unit_price?.toFixed(3) ?? '—'} /L
									</div>
								</div>
							</div>

							<div class="flex items-center gap-3 text-xs text-gray-400 border-t border-gray-100 pt-2">
								<span>{formatDate(order.created_at)}</span>
								<span>·</span>
								<span>{order.payment_method}</span>
								{#if order.customer_name}
									<span>·</span>
									<span class="truncate">{order.customer_name}</span>
								{/if}
								{#if order.plate}
									<span>·</span>
									<span class="font-mono">{order.plate}</span>
								{/if}
							</div>

							{#if order.invoice_number}
								<div class="text-xs text-gray-400 mt-1">
									Factura: <span class="font-mono text-gray-500">{order.invoice_number}</span>
								</div>
							{/if}

							<!-- Reprint button (only for completed/collected) -->
							{#if order.status === 'COMPLETED' || order.status === 'COLLECTED'}
								<div class="mt-2 pt-2 border-t border-gray-100">
									{#if printError === order.order_id}
										<div class="text-xs text-red-500 mb-1">⚠️ Error al imprimir</div>
									{/if}
									<button
										class="touch-btn flex items-center gap-1 text-xs text-primary hover:text-blue-800 font-medium
											disabled:opacity-50"
										on:click={() => handleReprint(order)}
										disabled={printing === order.order_id}
									>
										{printing === order.order_id ? '🖨 Imprimiendo...' : '🖨 Reimprimir ticket'}
									</button>
								</div>
							{/if}
						</div>
					{/each}
				</div>
			{/if}
		{/if}

		<!-- Tab: Caja -->
		{#if activeTab === 'cash'}
			{#if movements.length === 0}
				<div class="text-center text-sm text-gray-400 py-8">
					<div class="text-3xl mb-2">💰</div>
					Sin movimientos de caja en este turno
				</div>
			{:else}
				<!-- Mini resumen de caja -->
				<div class="grid grid-cols-2 gap-3 mb-4">
					<div class="card p-3 text-center bg-green-50 border-green-200">
						<div class="text-lg font-bold text-green-700">{formatCurrency(incomeTotal)}</div>
						<div class="text-xs text-green-600">Total ingresos</div>
					</div>
					<div class="card p-3 text-center bg-red-50 border-red-200">
						<div class="text-lg font-bold text-red-600">{formatCurrency(expenseTotal)}</div>
						<div class="text-xs text-red-500">Total egresos</div>
					</div>
				</div>

				<div class="space-y-2">
					{#each movements as m (m.movement_id)}
						<div class="card p-3 flex items-center gap-3">
							<div class="text-xl">{movementIcon(m.type)}</div>
							<div class="flex-1 min-w-0">
								<div class="text-sm font-medium text-gray-800">{movementLabel(m.type)}</div>
								<div class="flex gap-2 text-xs text-gray-400">
									<span>{formatDate(m.created_at)}</span>
									{#if m.observation}
										<span class="truncate">— {m.observation}</span>
									{/if}
									{#if m.related_user_name}
										<span>→ {m.related_user_name}</span>
									{/if}
								</div>
							</div>
							<div class="text-sm font-semibold {m.type === 'INCOME' ? 'text-green-600' : 'text-red-600'} text-right">
								<div>{m.type === 'INCOME' ? '+' : '-'}{formatCurrency(m.amount)}</div>
								<div class="text-xs text-gray-400 font-normal">Saldo: {formatCurrency(m.running_balance)}</div>
							</div>
						</div>
					{/each}
				</div>
			{/if}
		{/if}
	{/if}
</main>
