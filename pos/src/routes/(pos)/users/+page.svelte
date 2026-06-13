<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import Header from '$lib/components/Header.svelte';
	import { auth } from '$lib/stores/auth';
	import * as powerfin from '$lib/api/powerfin';
	import { SAFE_VAULT_ROLE } from '$lib/api/types';
	import type { OnlineUser } from '$lib/api/types';

	let users: OnlineUser[] = [];
	let loading = true;
	let error = '';
	let refreshTimer: ReturnType<typeof setInterval> | null = null;

	async function loadUsers() {
		if (!$auth.token) return;
		try {
			users = await powerfin.getOnlineUsers($auth.token);
			error = '';
		} catch {
			error = 'Error al cargar usuarios';
		} finally {
			loading = false;
		}
	}

	function userIcon(role: string): string {
		switch (role) {
			case SAFE_VAULT_ROLE: return '🏦';
			case 'DISPATCHER': return '👤';
			case 'SUPERVISOR': return '👔';
			default: return '👤';
		}
	}

	function roleLabel(role: string): string {
		switch (role) {
			case SAFE_VAULT_ROLE: return 'Caja Fuerte';
			case 'DISPATCHER': return 'Despachador';
			case 'SUPERVISOR': return 'Supervisor';
			default: return role;
		}
	}

	onMount(() => {
		loadUsers();
		refreshTimer = setInterval(loadUsers, 15_000);
	});

	onDestroy(() => {
		if (refreshTimer) clearInterval(refreshTimer);
	});
</script>

<Header title="Usuarios en Línea" showBack={true} onBack={() => goto('/')} />

<main class="flex-1 px-4 py-4 pb-24">
	{#if loading}
		<div class="text-center text-gray-500 py-8">Cargando...</div>
	{:else if error}
		<div class="bg-red-50 text-red-600 text-sm text-center rounded-xl py-3">{error}</div>
	{:else if users.length === 0}
		<div class="card p-6 text-center mt-8">
			<div class="text-3xl mb-3">📭</div>
			<p class="text-gray-500">No hay usuarios en línea</p>
		</div>
	{:else}
		<!-- Lista de usuarios -->
		<div class="space-y-3">
			{#each users as user}
				<div class="card p-4" class:opacity-60={user.role === SAFE_VAULT_ROLE}>
					<div class="flex items-center gap-3">
						<div class="text-2xl">{userIcon(user.role)}</div>
						<div class="flex-1 min-w-0">
							<div class="text-sm font-semibold text-gray-800">{user.name}</div>
							<div class="text-xs text-gray-400">
								{roleLabel(user.role)}
								{#if user.shift_id > 0}
									· Turno #{user.shift_id}
								{/if}
							</div>
						</div>
						{#if user.role !== SAFE_VAULT_ROLE}
							<div class="flex items-center gap-1">
								<div class="w-2 h-2 rounded-full bg-green-400"></div>
								<span class="text-xs text-green-600 font-medium">Activo</span>
							</div>
						{/if}
					</div>
				</div>
			{/each}
		</div>
	{/if}
</main>
