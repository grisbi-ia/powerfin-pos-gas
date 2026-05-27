<script lang="ts">
	import { fusionConnected } from '$lib/stores/dispensers';
</script>

{#if !$fusionConnected}
	<div class="bg-warning/10 border-b border-warning/30 px-4 py-2 text-center">
		<div class="flex items-center justify-center gap-2">
			<svg class="w-4 h-4 text-warning" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
					d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
			</svg>
			<span class="text-warning text-xs font-medium">
				Sin conexión con FusionBridge — reconectando...
			</span>
		</div>
	</div>
{/if}
