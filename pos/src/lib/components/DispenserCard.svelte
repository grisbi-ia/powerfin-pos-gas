<script lang="ts">
	import type { DispenserState, HoseState } from '$lib/api/types';
	import { orderByHose } from '$lib/stores/pendingOrders';
	import type { PendingOrder } from '$lib/stores/pendingOrders';

	export let dispenser: DispenserState;
	export let onSideClick: (dispenserId: number, side: 'A' | 'B', hose: HoseState) => void = () => {};

	$: isOnline = dispenser.online && dispenser.connected;

	function getStatusColor(status: string, isPendingCollection: boolean): string {
		if (isPendingCollection) return 'bg-green-500';
		switch (status) {
			case 'IDLE': return 'bg-green-500';
			case 'CALLING': return 'bg-blue-500';
			case 'AUTHORIZED': return 'bg-yellow-500';
			case 'STARTING':
			case 'FUELLING': return 'bg-orange-500';
			case 'PAUSED': return 'bg-purple-500';
			case 'STOPPED':
			case 'ERROR':
			case 'CLOSED': return 'bg-red-500';
			default: return 'bg-gray-400';
		}
	}

	function getStatusLabel(hose: HoseState, isPendingCollection: boolean): string {
		if (isPendingCollection) return 'Cobrar';
		const labels: Record<string, string> = {
			IDLE: 'Disponible', CALLING: 'Llamando', AUTHORIZED: 'Autorizado',
			STARTING: 'Iniciando', FUELLING: 'Despachando', PAUSED: 'Pausado',
			STOPPED: 'Detenido', CLOSED: 'Cerrado', ERROR: 'Error'
		};
		return labels[hose.status] ?? hose.status;
	}

	function isHoseBusy(hose: HoseState): boolean {
		return ['AUTHORIZED', 'CALLING', 'STARTING', 'FUELLING', 'PAUSED'].includes(hose.status);
	}

	function getSideInfo(orders: Map<string, PendingOrder>, side: 'A' | 'B'): {
		status: string; primaryHose: HoseState | null;
		allIdle: boolean; isPendingCollection: boolean;
		pendingAmount: number; pendingCustomer: string;
	} {
		const hoses = dispenser.sides[side];
		const allIdle = hoses.every(h => h.status === 'IDLE');
		const busyHose = hoses.find(h => isHoseBusy(h));

		// Check for pending collection on any hose of this side
		let pendingCollectionHose: HoseState | null = null;
		let pendingOrder: PendingOrder | undefined;
		for (const h of hoses) {
			const key = `${dispenser.dispenserId}-${h.hoseId}`;
			const order = orders.get(key);
			if (order?.status === 'COMPLETED' && h.status === 'IDLE') {
				pendingCollectionHose = h;
				pendingOrder = order;
				break;
			}
		}

		if (pendingCollectionHose && pendingOrder) {
			return {
				status: 'PENDING_COLLECTION',
				primaryHose: pendingCollectionHose,
				allIdle: false,
				isPendingCollection: true,
				pendingAmount: pendingOrder.finalAmount || pendingOrder.presetAmount * 0.85,
				pendingCustomer: pendingOrder.customerName
			};
		}

		if (busyHose) {
			return {
				status: busyHose.status,
				primaryHose: busyHose,
				allIdle: false,
				isPendingCollection: false,
				pendingAmount: 0,
				pendingCustomer: ''
			};
		}

		return {
			status: 'IDLE',
			primaryHose: hoses[0],
			allIdle,
			isPendingCollection: false,
			pendingAmount: 0,
			pendingCustomer: ''
		};
	}

	interface SideInfo {
		side: 'A' | 'B';
		status: string;
		primaryHose: HoseState | null;
		allIdle: boolean;
		isPendingCollection: boolean;
		pendingAmount: number;
		pendingCustomer: string;
		color: string;
		label: string;
	}

	$: sides = (['A', 'B'] as const).map(s => {
		const info = getSideInfo($orderByHose, s);
		const color = getStatusColor(info.status, info.isPendingCollection);
		const label = getStatusLabel(
			info.primaryHose ?? { status: info.status, subStatus: '', presetAmount: 0, attendantName: null } as HoseState,
			info.isPendingCollection
		);
		return { side: s, ...info, color, label } satisfies SideInfo;
	});
</script>

<div class="card overflow-hidden {isOnline ? '' : 'opacity-50'}">
	<!-- Header -->
	<div class="px-4 py-2 bg-gray-50 border-b border-gray-100 flex items-center justify-between">
		<div class="flex items-center gap-2">
			<div class="w-2.5 h-2.5 rounded-full {isOnline ? 'bg-green-500' : 'bg-red-400'}"></div>
			<span class="text-sm font-semibold text-gray-800">{dispenser.name}</span>
		</div>
		{#if !isOnline}
			<span class="text-xs text-red-400">offline</span>
		{/if}
	</div>

	<!-- Two sides -->
	<div class="grid grid-cols-2 divide-x divide-gray-100">
		{#each sides as info}
			{@const isBusy = info.primaryHose ? isHoseBusy(info.primaryHose) : false}
			{@const pulse = isBusy && (info.status === 'FUELLING' || info.status === 'STARTING')}

			<button
				class="touch-btn p-3 text-left transition-colors
					{info.allIdle ? 'hover:bg-green-50 active:bg-green-100' : ''}
					{info.isPendingCollection ? 'bg-green-50 hover:bg-green-100 ring-1 ring-green-300' : ''}
					{isBusy ? 'bg-yellow-50' : ''}
					{!isOnline || (!info.allIdle && !isBusy && !info.isPendingCollection) ? 'cursor-not-allowed' : ''}"
				on:click={() => info.primaryHose && onSideClick(dispenser.dispenserId, info.side, info.primaryHose)}
				disabled={!isOnline || (!info.allIdle && !isBusy && !info.isPendingCollection)}
			>
				<!-- Side label -->
				<div class="text-xs text-gray-400 mb-1">Lado {info.side}</div>

				<!-- Status dot + label -->
				<div class="flex items-center gap-1.5 mb-2">
					<div class="w-2 h-2 rounded-full {info.color} {pulse ? 'animate-pulse' : ''}"></div>
					<span class="text-xs font-medium
						{info.allIdle ? 'text-green-700' : info.isPendingCollection ? 'text-green-700' : isBusy ? 'text-orange-700' : 'text-gray-500'}">
						{info.label}
					</span>
				</div>

				<!-- Busy hose: show attendant + preset -->
				{#if isBusy && info.primaryHose}
					<div class="text-xs text-gray-500">
						{info.primaryHose.attendantName ?? ''}
					</div>
					{#if info.primaryHose.presetAmount > 0}
						<div class="text-sm font-bold text-primary mt-0.5">
							${info.primaryHose.presetAmount.toFixed(2)}
						</div>
					{/if}
				{/if}

				<!-- Pending collection: show amount to collect -->
				{#if info.isPendingCollection}
					{#if info.pendingCustomer}
						<div class="text-xs text-gray-500">{info.pendingCustomer}</div>
					{/if}
					<div class="text-base font-bold text-green-700 mt-0.5">
						${info.pendingAmount.toFixed(2)}
					</div>
					<div class="text-xs text-green-600 font-medium mt-0.5">Tocar para cobrar →</div>
				{/if}

				<!-- Available: show grades -->
				{#if info.allIdle}
					<div class="flex flex-wrap gap-1 mt-1">
						{#each dispenser.sides[info.side] as h}
							<span class="px-1.5 py-0.5 rounded text-xs bg-gray-100 text-gray-600">
								{h.gradeName}
							</span>
						{/each}
					</div>
					<div class="text-xs text-primary font-medium mt-1">Vender →</div>
				{/if}
			</button>
		{/each}
	</div>
</div>
