<script lang="ts">
	import { auth, currentUser } from '$lib/stores/auth';
	import { shift } from '$lib/stores/shift';
	import { fusionConnected } from '$lib/stores/dispensers';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	export let title = 'Powerfin POS';
	export let showBack = false;
	export let onBack: (() => void) | null = null;

	function handleLogout() {
		auth.logout();
		shift.clear();
		goto('/login');
	}
</script>

<header class="bg-primary text-white px-4 py-3">
	<div class="flex items-center justify-between">
		<div class="flex items-center gap-3">
			{#if showBack}
				<button class="touch-btn p-1 -ml-1" on:click={() => onBack?.() ?? history.back()}>
					<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
					</svg>
				</button>
			{/if}
			<div>
				<h1 class="text-lg font-bold">{title}</h1>
				<p class="text-xs text-blue-200">
					{$currentUser?.name ?? ''}
					{#if $shift}
						— Turno #{$shift.shift_id}
					{/if}
				</p>
			</div>
		</div>

		<div class="flex items-center gap-2">
			<!-- Fusion status -->
			<div class="flex items-center gap-1">
				<div class="w-2 h-2 rounded-full {$fusionConnected ? 'bg-green-400' : 'bg-red-400'}"></div>
				<span class="text-xs text-blue-200">{$fusionConnected ? 'Online' : 'Offline'}</span>
			</div>

			<button
				class="touch-btn text-blue-200 hover:text-white text-xs underline"
				on:click={handleLogout}
			>
				Salir
			</button>
		</div>
	</div>
</header>
