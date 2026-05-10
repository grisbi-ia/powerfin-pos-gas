<script lang="ts">
	import type { DispenserState } from '$lib/api/types';

	export let dispenser: DispenserState;

	$: statusColor = getStatusColor(dispenser.status);
	$: statusLabel = getStatusLabel(dispenser.status, dispenser.subStatus);
	$: isActive = ['AUTHORIZED', 'CALLING', 'STARTING', 'FUELLING', 'PAUSED'].includes(dispenser.status);
	$: isOnline = dispenser.online && dispenser.connected;

	function getStatusColor(status: string): string {
		switch (status) {
			case 'IDLE': return 'bg-dispenser-idle';
			case 'CALLING': return 'bg-dispenser-calling';
			case 'FUELLING':
			case 'STARTING': return 'bg-dispenser-fuelling';
			case 'AUTHORIZED': return 'bg-dispenser-authorized';
			case 'CLOSED':
			case 'ERROR': return 'bg-dispenser-error';
			default: return 'bg-dispenser-closed';
		}
	}

	function getStatusLabel(status: string, subStatus: string): string {
		const labels: Record<string, string> = {
			IDLE: 'Disponible',
			CALLING: 'Llamando',
			AUTHORIZED: 'Autorizado',
			STARTING: 'Iniciando',
			FUELLING: 'Despachando',
			PAUSED: 'Pausado',
			CLOSED: 'Cerrado',
			ERROR: 'Error'
		};
		let label = labels[status] ?? status;
		if (subStatus && (subStatus === 'MONEY_PRESET' || subStatus === 'VOLUME_PRESET')) {
			label += ' (Preset)';
		}
		return label;
	}
</script>

<button
	class="touch-btn card p-4 w-full text-left relative overflow-hidden
		{isActive ? 'ring-2 ring-primary ring-offset-2' : ''}"
	on:click
>
	<!-- Status indicator -->
	<div class="flex items-center gap-3">
		<div class="w-3 h-3 rounded-full {statusColor} {isActive ? 'animate-pulse' : ''}"></div>
		<div class="flex-1 min-w-0">
			<div class="text-sm font-semibold text-gray-900">
				Surtidor {dispenser.dispenserId}
				{#if !isOnline}
					<span class="text-red-400 text-xs ml-1">(offline)</span>
				{/if}
			</div>
			<div class="text-xs text-gray-500">{statusLabel}</div>
		</div>

		{#if dispenser.presetAmount > 0}
			<div class="text-right">
				<div class="text-sm font-bold text-primary">${dispenser.presetAmount.toFixed(2)}</div>
				<div class="text-xxs text-gray-400">Preset</div>
			</div>
		{/if}
	</div>

	<!-- Hose info -->
	<div class="mt-2 flex gap-1">
		{#each Array(dispenser.hoseCount) as _, i}
			<div class="px-2 py-0.5 rounded-md bg-gray-100 text-xxs text-gray-600">
				P{i + 1}
			</div>
		{/each}
	</div>

	{#if dispenser.grade}
		<div class="mt-1 text-xxs text-gray-400">{dispenser.grade}</div>
	{/if}
</button>
