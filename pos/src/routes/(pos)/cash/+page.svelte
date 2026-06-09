<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import Header from '$lib/components/Header.svelte';
	import { auth } from '$lib/stores/auth';
	import { shift } from '$lib/stores/shift';
	import { config } from '$lib/stores/config';
	import * as powerfin from '$lib/api/powerfin';
	import * as bridge from '$lib/api/bridge';
	import type { CashMovement, ShiftCashSummary } from '$lib/api/types';

	let summary: ShiftCashSummary | null = null;
	let movements: CashMovement[] = [];
	let loading = true;
	let error = '';
	let refreshTimer: ReturnType<typeof setInterval> | null = null;
	let reprintingId: number | null = null;

	async function loadData() {
		if (!$auth.token || !$shift) return;
		try {
			[summary, movements] = await Promise.all([
				powerfin.getShiftCashSummary($auth.token, $shift.shift_id),
				powerfin.getCashMovements($auth.token, $shift.shift_id)
			]);
			error = '';
		} catch {
			error = 'Error al cargar datos de caja';
		} finally {
			loading = false;
		}
	}

	function formatCurrency(value: number | string): string {
		const num = typeof value === 'number' ? value : parseFloat(value || '0');
		return '$ ' + num.toFixed(2);
	}

	function movementIcon(type: string): string {
		switch (type) {
			case 'INCOME': return '💰';
			case 'EXPENSE': return '💸';
			case 'TRANSFER_IN': return '📥';
			case 'TRANSFER_OUT': return '📤';
			case 'SAFE_DROP': return '🏦';
			default: return '📋';
		}
	}

	function movementLabel(type: string): string {
		switch (type) {
			case 'INCOME': return 'Ingreso';
			case 'EXPENSE': return 'Egreso';
			case 'TRANSFER_IN': return 'Transferencia recibida';
			case 'TRANSFER_OUT': return 'Transferencia enviada';
			case 'SAFE_DROP': return 'Depósito caja fuerte';
			default: return type;
		}
	}

	function formatTime(iso: string): string {
		return new Date(iso).toLocaleTimeString('es-EC', { hour: '2-digit', minute: '2-digit' });
	}

	async function reprintMovement(m: CashMovement) {
		reprintingId = m.movement_id;
		try {
			const loc = $config?.location;
			const defaultIp = $config?.dispensers?.[0]?.printer_ip || '192.168.1.31';
			const defaultPort = $config?.dispensers?.[0]?.printer_port || 9100;
			await bridge.printReceipt({
				type: 'CASH_MOVEMENT',
				printerIp: defaultIp,
				printerPort: defaultPort,
				cashData: {
					movementType: m.type === 'TRANSFER_IN' ? 'INCOME' : m.type === 'TRANSFER_OUT' || m.type === 'SAFE_DROP' ? m.type : m.type,
					date: new Date(m.created_at).toLocaleDateString('es-EC'),
					time: new Date(m.created_at).toLocaleTimeString('es-EC'),
					userName: ($shift as any)?.user_name || '',
					amount: m.amount.toFixed(2),
					observation: m.observation,
					locationName: loc?.name || '',
					locationAddress: loc?.address || '',
					locationRuc: loc?.ruc || '',
					locationPhone: loc?.phone || '',
				}
			});
		} catch {
			// non-blocking
		} finally {
			reprintingId = null;
		}
	}

	onMount(() => {
		loadData();
		refreshTimer = setInterval(loadData, 10_000);
	});

	onDestroy(() => {
		if (refreshTimer) clearInterval(refreshTimer);
	});
</script>

<Header title="Caja" showBack={true} onBack={() => goto('/')} />

<main class="flex-1 px-4 py-4 pb-24">
	{#if !$shift}
		<div class="card p-6 text-center mt-8">
			<div class="text-3xl mb-3">🔒</div>
			<h2 class="text-lg font-bold text-gray-800 mb-2">Turno no aperturado</h2>
			<p class="text-sm text-gray-500 mb-4">Debe abrir su turno para acceder a la caja.</p>
			<button
				class="touch-btn bg-primary text-white rounded-xl px-6 py-3 text-sm font-semibold"
				on:click={() => goto('/')}
			>
				Ir al inicio
			</button>
		</div>
	{:else if loading}
		<div class="text-center text-gray-500 py-8">Cargando...</div>
	{:else if error}
		<div class="bg-red-50 text-red-600 text-sm text-center rounded-xl py-3">{error}</div>
	{:else}
		<!-- Saldo actual -->
		<div class="card p-5 mb-4 bg-gradient-to-br from-primary to-blue-700 text-white">
			<p class="text-sm text-blue-200 mb-1">Saldo en caja</p>
			<p class="text-3xl font-bold">{formatCurrency(summary?.current_balance ?? 0)}</p>
			<div class="grid grid-cols-2 gap-2 mt-3 text-xs text-blue-200">
				<div>
					<span class="block">Apertura</span>
					<span class="font-semibold text-white">{formatCurrency(summary?.opening_cash ?? 0)}</span>
				</div>
				<div>
					<span class="block">Ventas efectivo</span>
					<span class="font-semibold text-white">{formatCurrency(summary?.total_sales_cash ?? 0)}</span>
				</div>
			</div>
		</div>

		<!-- Botones de acción rápida -->
		<div class="grid grid-cols-3 gap-3 mb-4">
			<button
				class="touch-btn card p-4 text-center hover:shadow-md transition"
				on:click={() => goto('/cash/movement?type=INCOME')}
			>
				<div class="text-2xl mb-1">💰</div>
				<div class="text-sm font-semibold text-green-700">Ingreso</div>
			</button>
			<button
				class="touch-btn card p-4 text-center hover:shadow-md transition"
				on:click={() => goto('/cash/movement?type=EXPENSE')}
			>
				<div class="text-2xl mb-1">💸</div>
				<div class="text-sm font-semibold text-red-600">Egreso</div>
			</button>
			<button
				class="touch-btn card p-4 text-center hover:shadow-md transition"
				on:click={() => goto('/cash/transfer')}
			>
				<div class="text-2xl mb-1">📤</div>
				<div class="text-sm font-semibold text-blue-700">Transferir</div>
			</button>
		</div>

		<!-- Movimientos del día -->
		<div class="card p-4">
			<h2 class="text-sm font-semibold text-gray-700 mb-3">Movimientos del turno</h2>

			{#if movements.length === 0}
				<div class="text-center text-sm text-gray-400 py-4">
					Sin movimientos registrados
				</div>
			{:else}
				<div class="divide-y divide-gray-100">
					{#each movements as m}
						<div class="flex items-center gap-3 py-2.5">
							<div class="text-xl">{movementIcon(m.type)}</div>
							<div class="flex-1 min-w-0">
								<div class="text-sm font-medium text-gray-800">{movementLabel(m.type)}</div>
								<div class="flex gap-2 text-xs text-gray-400">
									<span>{formatTime(m.created_at)}</span>
									{#if m.observation}
										<span class="truncate">— {m.observation}</span>
									{/if}
									{#if m.related_user_name}
										<span>→ {m.related_user_name}</span>
									{/if}
								</div>
							</div>
							<div class="flex items-center gap-1">
								<div class="text-sm font-semibold {m.type === 'INCOME' || m.type === 'TRANSFER_IN' ? 'text-green-600' : 'text-red-600'}">
									{m.type === 'INCOME' || m.type === 'TRANSFER_IN' ? '+' : '-'}{formatCurrency(m.amount)}
								</div>
								<button
									class="touch-btn text-gray-400 hover:text-blue-600 px-1 text-sm"
									title="Reimprimir comprobante"
									on:click|stopPropagation={() => reprintMovement(m)}
									disabled={reprintingId === m.movement_id}
								>
									{reprintingId === m.movement_id ? '⏳' : '🖨'}
								</button>
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	{/if}
</main>
