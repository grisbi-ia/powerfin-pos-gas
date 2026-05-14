<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import PinKeyboard from '$lib/components/PinKeyboard.svelte';
	import { goto } from '$app/navigation';

	// Mock imports — swap to real imports when PowerFin ERP is available
	import * as powerfin from '$lib/api/powerfin';

	let username = 'carlos';
	let pin = '';
	let error = '';
	let loading = false;

	async function handleLogin() {
		if (pin.length < 3) {
			error = 'Ingrese un PIN válido';
			return;
		}

		loading = true;
		error = '';

		try {
			const response = await powerfin.login({ username, pin });
			auth.login(response.access_token, response.user);
			goto('/');
		} catch {
			error = 'Credenciales inválidas';
			pin = '';
		} finally {
			loading = false;
		}
	}

	function handlePinDigit(digit: string) {
		if (pin.length < 4) pin += digit;
	}

	function handlePinDelete() {
		pin = pin.slice(0, -1);
	}
</script>

<div class="min-h-screen flex flex-col items-center justify-center bg-primary px-6">
	<div class="w-full max-w-sm">
		<!-- Logo -->
		<div class="text-center mb-10">
			<h1 class="text-3xl font-bold text-white">Powerfin POS</h1>
			<p class="text-blue-200 mt-1 text-sm">Gasolinera NEOPAUTE</p>
		</div>

		<!-- Username -->
		<div class="mb-6">
			<label for="username" class="block text-blue-200 text-xs font-medium mb-1">Usuario</label>
			<input
				id="username"
				type="text"
				bind:value={username}
				class="w-full bg-white/10 text-white placeholder-blue-300 rounded-xl px-4 py-3
					border border-white/20 focus:border-white/40 focus:outline-none text-lg"
				placeholder="Nombre de usuario"
			/>
		</div>

		<!-- PIN display -->
		<div class="mb-6 text-center">
			<span class="block text-blue-200 text-xs font-medium mb-2">PIN</span>
			<div class="flex justify-center gap-3">
				{#each [0, 1, 2, 3] as i}
					<div
						class="w-5 h-5 rounded-full border-2 transition-colors
							{i < pin.length ? 'bg-white border-white' : 'border-white/30'}"
					></div>
				{/each}
			</div>
		</div>

		<!-- Error -->
		{#if error}
			<div class="bg-red-500/20 text-red-200 text-sm text-center rounded-lg py-2 mb-4">
				{error}
			</div>
		{/if}

		<!-- PinKeyboard -->
		<PinKeyboard
			onDigit={handlePinDigit}
			onDelete={handlePinDelete}
			onEnter={handleLogin}
			{loading}
		/>

		<div class="text-center mt-6">
			<p class="text-blue-300 text-xs">PIN demo: <span class="font-mono text-white">1234</span></p>
		</div>
	</div>
</div>
