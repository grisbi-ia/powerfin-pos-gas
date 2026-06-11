<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import Header from '$lib/components/Header.svelte';
	import { auth } from '$lib/stores/auth';
	import { shift } from '$lib/stores/shift';
	import { config } from '$lib/stores/config';
	import * as powerfin from '$lib/api/powerfin';
	import * as bridge from '$lib/api/bridge';
	import type { OnlineUser } from '$lib/api/types';
	import { SAFE_VAULT_ROLE } from '$lib/api/types';

	let users: OnlineUser[] = [];
	let selectedUserId: number | null = null;
	let amount: number | null = null;
	let observation = '';
	let loading = false;
	let loadingUsers = true;
	let error = '';
	let showPrintModal = false;
	let showConfirmModal = false;
	let printing = false;

	$: selectedUser = users.find(u => u.user_id === selectedUserId);
	$: isSafeVault = selectedUser?.role === SAFE_VAULT_ROLE;
	$: isSelfTransfer = selectedUserId === $shift?.shift_id;

	onMount(async () => {
		if (!$auth.token) return;
		try {
			const allUsers = await powerfin.getOnlineUsers($auth.token);
			// Filter out current user's own shift (can't transfer to yourself)
			// Exception: if current user has multiple shifts, we filter by user_id
			const currentUserId = $shift?.shift_id;
			users = allUsers.filter(u => u.shift_id !== currentUserId);
			loadingUsers = false;
		} catch {
			error = 'Error al cargar usuarios en línea';
			loadingUsers = false;
		}
	});

	async function handleSubmit() {
		if (!amount || amount <= 0) {
			error = 'Ingrese un valor válido';
			return;
		}
		if (selectedUserId === null) {
			error = 'Seleccione un destinatario';
			return;
		}
		error = '';
		showConfirmModal = true;
	}

	async function handleConfirm() {
		if (!$auth.token || !$shift) return;
		showConfirmModal = false;
		loading = true;
		error = '';

		try {
			await powerfin.createTransfer($auth.token, {
				from_shift_id: $shift.shift_id,
				to_user_id: selectedUserId!,
				amount: amount!,
				observation: observation.trim()
			});
			showPrintModal = true;
		} catch (err: any) {
			error = err?.message || 'Error al realizar la transferencia';
		} finally {
			loading = false;
		}
	}

	async function handlePrint() {
		printing = true;
		try {
			const loc = $config?.location;
			const defaultIp = $config?.cash_printer_ip || '';
			const defaultPort = $config?.dispensers?.[0]?.printer_port || 9100;
			const movType = isSafeVault ? 'SAFE_DROP' : 'TRANSFER_OUT';
			await bridge.printReceipt({
				type: 'CASH_MOVEMENT',
				printerIp: defaultIp,
				printerPort: defaultPort,
				cashData: {
					movementType: movType,
					date: new Date().toLocaleDateString('es-EC'),
					time: new Date().toLocaleTimeString('es-EC'),
					userName: ($shift as any)?.user_name || '',
					amount: amount?.toFixed(2) || '0.00',
					observation: observation.trim() || (isSafeVault ? 'Depósito a caja fuerte' : `Transferencia a ${selectedUser?.name}`),
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

	function userIcon(role: string): string {
		switch (role) {
			case SAFE_VAULT_ROLE: return '🏦';
			case 'DISPATCHER': return '👤';
			case 'SUPERVISOR': return '👔';
			default: return '👤';
		}
	}
</script>

<Header title="Transferencia" showBack={true} onBack={() => goto('/cash')} />

<main class="flex-1 px-4 py-6">
	{#if !$shift}
		<div class="card p-6 text-center mt-8">
			<div class="text-3xl mb-3">🔒</div>
			<h2 class="text-lg font-bold text-gray-800 mb-2">Turno no aperturado</h2>
			<p class="text-sm text-gray-500 mb-4">Debe abrir su turno para realizar transferencias.</p>
			<button
				class="touch-btn bg-primary text-white rounded-xl px-6 py-3 text-sm font-semibold"
				on:click={() => goto('/')}
			>
				Ir al inicio
			</button>
		</div>
	{:else}
	<div class="card p-6">
		<div class="text-center mb-6">
			<div class="text-4xl mb-2">📤</div>
			<div class="text-lg font-bold text-blue-700">Transferir dinero</div>
			<div class="text-xs text-gray-400 mt-1">
				Traspaso a otro empleado o depósito a caja fuerte
			</div>
		</div>

		<!-- Destinatario -->
		<label class="block text-sm font-semibold text-gray-700 mb-2">
			Destinatario:
		</label>

		{#if loadingUsers}
			<div class="text-center text-sm text-gray-400 py-3">Cargando usuarios...</div>
		{:else if users.length === 0}
			<div class="text-center text-sm text-gray-400 py-3">No hay otros usuarios en línea</div>
		{:else}
			<div class="space-y-2 mb-4">
				{#each users as user}
					<button
						class="touch-btn w-full flex items-center gap-3 p-3 rounded-xl border-2 transition
							{selectedUserId === user.user_id
								? 'border-primary bg-blue-50'
								: 'border-gray-200 hover:border-gray-300'}"
						on:click={() => { selectedUserId = user.user_id; }}
					>
						<div class="text-2xl">{userIcon(user.role)}</div>
						<div class="flex-1 text-left">
							<div class="text-sm font-semibold text-gray-800">{user.name}</div>
							<div class="text-xs text-gray-400">
								{user.role === SAFE_VAULT_ROLE ? 'Depósito seguro' : 'Despachador — Turno #' + user.shift_id}
							</div>
						</div>
						{#if selectedUserId === user.user_id}
							<div class="text-primary text-lg">✓</div>
						{/if}
					</button>
				{/each}
			</div>
		{/if}

		{#if selectedUser}
			<!-- Valor -->
			<label for="amount" class="block text-sm font-semibold text-gray-700 mb-2">
				Valor a transferir:
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
				{#each [10, 20, 50, 100, 200, 500] as val}
					<button
						class="touch-btn px-4 py-2 rounded-lg border border-gray-200 text-sm font-medium text-gray-600 hover:border-primary hover:text-primary transition"
						on:click={() => { amount = val; }}
					>
						${val}
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
				placeholder={isSafeVault ? 'Ej: Depósito de seguridad, excedente de caja...' : 'Ej: Cambio para turno, traspaso...'}
			></textarea>
		{/if}

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
				class="touch-btn bg-blue-700 text-white rounded-xl py-4 font-semibold disabled:opacity-50"
				on:click={handleSubmit}
				disabled={loading || !amount || selectedUserId === null}
			>
				{loading ? 'Transfiriendo...' : isSafeVault ? 'Depositar' : 'Transferir'}
			</button>
		</div>
	</div>
	{/if}

	<!-- Confirmación modal -->
	{#if showConfirmModal}
		<div class="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true">
			<div class="absolute inset-0 bg-black/50" on:click={() => showConfirmModal = false}></div>
			<div class="relative bg-white rounded-2xl shadow-xl w-full max-w-sm p-6">
				<div class="text-center mb-4">
					<div class="text-4xl mb-2">📤</div>
					<h3 class="text-lg font-semibold text-gray-800">¿Confirmar Transferencia?</h3>
					<p class="text-2xl font-bold mt-2">$ {amount?.toFixed(2)}</p>
					<p class="text-sm text-gray-500 mt-1">Destinatario: {selectedUser?.name}</p>
					{#if observation}
						<p class="text-sm text-gray-500 mt-1">{observation}</p>
					{/if}
				</div>
				<div class="grid grid-cols-2 gap-3">
					<button class="touch-btn bg-gray-200 text-gray-700 rounded-xl py-3 font-semibold" on:click={() => showConfirmModal = false}>
						Cancelar
					</button>
					<button class="touch-btn bg-red-600 text-white rounded-xl py-3 font-semibold" on:click={handleConfirm}>
						Sí, Confirmar
					</button>
				</div>
			</div>
		</div>
	{/if}

	<!-- Print confirmation modal -->
	{#if showPrintModal}
		<div class="fixed inset-0 bg-black/50 flex items-end sm:items-center justify-center z-50">
			<div class="bg-white rounded-t-2xl sm:rounded-2xl w-full sm:max-w-sm p-6 shadow-xl animate-slide-up">
				<div class="text-center mb-4">
					<div class="text-4xl mb-2">{isSafeVault ? '🏦' : '📤'}</div>
					<div class="text-lg font-bold text-gray-800">
						{isSafeVault ? 'Depósito registrado' : 'Transferencia registrada'}
					</div>
					<div class="text-sm text-gray-500 mt-1">
						$ {amount?.toFixed(2)}
						{#if !isSafeVault && selectedUser}
							→ {selectedUser.name}
						{/if}
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
