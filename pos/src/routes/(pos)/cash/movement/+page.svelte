<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import Header from '$lib/components/Header.svelte';
	import { auth } from '$lib/stores/auth';
	import { shift } from '$lib/stores/shift';
	import { config } from '$lib/stores/config';
	import * as powerfin from '$lib/api/powerfin';
	import * as bridge from '$lib/api/bridge';

	const type = ($page.url.searchParams.get('type') ?? 'INCOME') as 'INCOME' | 'EXPENSE';
	const isIncome = type === 'INCOME';

	let amount: number | null = null;
	let observation = '';
	let loading = false;
	let error = '';
	let showPrintModal = false;

	async function handleSubmit() {
		if (!amount || amount <= 0) {
			error = 'Ingrese un valor válido';
			return;
		}
		if (!$auth.token || !$shift) return;

		loading = true;
		error = '';

		try {
			await powerfin.createCashMovement($auth.token, {
				shift_id: $shift.shift_id,
				type,
				amount,
				observation: observation.trim()
			});
			showPrintModal = true;
		} catch (err: any) {
			error = err?.message || 'Error al registrar el movimiento';
		} finally {
			loading = false;
		}
	}

	async function handlePrint() {
		printing = true;
		try {
			const loc = $config?.location;
			const defaultIp = $config?.dispensers?.[0]?.printer_ip || '192.168.1.31';
			const defaultPort = $config?.dispensers?.[0]?.printer_port || 9100;
			await bridge.printReceipt({
				type: 'CASH_MOVEMENT',
				printerIp: defaultIp,
				printerPort: defaultPort,
				cashData: {
					movementType: type,
					date: new Date().toLocaleDateString('es-EC'),
					time: new Date().toLocaleTimeString('es-EC'),
					userName: ($shift as any)?.user_name || '',
					amount: amount?.toFixed(2) || '0.00',
					observation: observation.trim(),
					locationName: loc?.name || '',
					locationAddress: loc?.address || '',
					locationRuc: loc?.ruc || '',
					locationPhone: loc?.phone || '',
				}
			});
		} catch {
			// Print failure is non-blocking
		} finally {
			printing = false;
		}
		goto('/cash');
	}

	function handleSkip() {
		goto('/cash');
	}

	let printing = false;
</script>

<Header
	title={isIncome ? 'Registrar Ingreso' : 'Registrar Egreso'}
	showBack={true}
	onBack={() => goto('/cash')}
/>

<main class="flex-1 px-4 py-6">
	{#if !$shift}
		<div class="card p-6 text-center mt-8">
			<div class="text-3xl mb-3">🔒</div>
			<h2 class="text-lg font-bold text-gray-800 mb-2">Turno no aperturado</h2>
			<p class="text-sm text-gray-500 mb-4">Debe abrir su turno para registrar movimientos.</p>
			<button
				class="touch-btn bg-primary text-white rounded-xl px-6 py-3 text-sm font-semibold"
				on:click={() => goto('/')}
			>
				Ir al inicio
			</button>
		</div>
	{:else}
	<div class="card p-6">
		<!-- Tipo -->
		<div class="text-center mb-6">
			<div class="text-4xl mb-2">{isIncome ? '💰' : '💸'}</div>
			<div class="text-lg font-bold {isIncome ? 'text-green-700' : 'text-red-600'}">
				{isIncome ? 'Ingreso de dinero' : 'Egreso de dinero'}
			</div>
			<div class="text-xs text-gray-400 mt-1">
				{isIncome ? 'Incrementa el saldo de caja' : 'Disminuye el saldo de caja'}
			</div>
		</div>

		<!-- Valor -->
		<label for="amount" class="block text-sm font-semibold text-gray-700 mb-2">
			Valor:
		</label>
		<div class="relative mb-4">
			<span class="absolute left-4 top-1/2 -translate-y-1/2 text-lg text-gray-400">$</span>
			<input
				id="amount"
				type="number"
				bind:value={amount}
				step="0.01"
				min="0.01"
				class="w-full rounded-xl border border-gray-200 pl-10 pr-4 py-4 text-2xl font-bold focus:border-primary focus:outline-none"
				placeholder="0.00"
			/>
		</div>

		<!-- Botones rápidos -->
		<div class="flex flex-wrap gap-2 mb-4">
			{#each [5, 10, 20, 50, 100, 200] as val}
				<button
					class="touch-btn px-4 py-2 rounded-lg border border-gray-200 text-sm font-medium text-gray-600 hover:border-primary hover:text-primary transition"
					on:click={() => { amount = (amount ?? 0) + val; }}
				>
					+${val}
				</button>
			{/each}
		</div>

		<!-- Observación -->
		<label for="observation" class="block text-sm font-semibold text-gray-700 mb-2">
			Observación:
		</label>
		<textarea
			id="observation"
			bind:value={observation}
			rows="2"
			class="w-full rounded-xl border border-gray-200 px-4 py-3 text-sm focus:border-primary focus:outline-none resize-none mb-6"
			placeholder="Ej: Cambio inicial, depósito del día..."
		></textarea>

		{#if error}
			<div class="bg-red-50 text-red-600 text-sm text-center rounded-lg py-2 mb-4">{error}</div>
		{/if}

		<div class="grid grid-cols-2 gap-3">
			<button
				class="touch-btn bg-gray-200 text-gray-700 rounded-xl py-4 font-semibold"
				on:click={() => goto('/cash')}
			>
				Cancelar
			</button>
			<button
				class="touch-btn rounded-xl py-4 font-semibold text-white disabled:opacity-50 {isIncome ? 'bg-green-600' : 'bg-red-600'}"
				on:click={handleSubmit}
				disabled={loading || !amount}
			>
				{loading ? 'Registrando...' : isIncome ? 'Registrar Ingreso' : 'Registrar Egreso'}
			</button>
		</div>
	</div>
	{/if}

	<!-- Print confirmation modal -->
	{#if showPrintModal}
		<div class="fixed inset-0 bg-black/50 flex items-end sm:items-center justify-center z-50">
			<div class="bg-white rounded-t-2xl sm:rounded-2xl w-full sm:max-w-sm p-6 shadow-xl animate-slide-up">
				<div class="text-center mb-4">
					<div class="text-4xl mb-2">{isIncome ? '💰' : '💸'}</div>
					<div class="text-lg font-bold text-gray-800">
						{isIncome ? 'Ingreso registrado' : 'Egreso registrado'}
					</div>
					<div class="text-sm text-gray-500 mt-1">
						$ {amount?.toFixed(2)}
					</div>
				</div>
				<div class="text-sm text-gray-600 text-center mb-4">
					¿Desea imprimir el comprobante?
				</div>
				<div class="grid grid-cols-2 gap-3">
					<button
						class="touch-btn bg-gray-200 text-gray-700 rounded-xl py-3 font-semibold"
						on:click={handleSkip}
						disabled={printing}
					>
						No
					</button>
					<button
						class="touch-btn bg-blue-600 text-white rounded-xl py-3 font-semibold disabled:opacity-50"
						on:click={handlePrint}
						disabled={printing}
					>
						{printing ? 'Imprimiendo...' : '🖨 Sí'}
					</button>
				</div>
			</div>
		</div>
	{/if}
</main>
