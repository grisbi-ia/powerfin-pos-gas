<script lang="ts">
	import type { PrintPolicy } from '$lib/api/types';

	export let policy: PrintPolicy = 'ASK';
	export let onPrint: () => void;
	export let onSkip: () => void;

	$: showButtons = policy === 'ASK';
</script>

{#if policy === 'ALWAYS'}
	<div class="bg-blue-50 rounded-xl px-4 py-3 text-center">
		<div class="flex items-center justify-center gap-2 mb-2">
			<svg class="w-5 h-5 text-blue-500 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
					d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
			</svg>
			<span class="text-blue-700 text-sm font-medium">Imprimiendo ticket...</span>
		</div>
	</div>
{:else if policy === 'ASK'}
	<div class="flex gap-3">
		<button
			class="touch-btn flex-1 bg-white border-2 border-gray-200 rounded-xl py-3 text-sm font-medium text-gray-600"
			on:click={onSkip}
		>
			No, gracias
		</button>
		<button
			class="touch-btn flex-1 bg-primary text-white rounded-xl py-3 text-sm font-semibold flex items-center justify-center gap-2"
			on:click={onPrint}
		>
			<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
					d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
			</svg>
			Imprimir ticket
		</button>
	</div>
{:else}
	<!-- NEVER — no buttons -->
{/if}
