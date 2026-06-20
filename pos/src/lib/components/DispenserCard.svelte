<script lang="ts">
	import type { DispenserState, HoseState } from '$lib/api/types';
	import { orderByHose } from '$lib/stores/pendingOrders';
	import { currentUser } from '$lib/stores/auth';
	import { shift } from '$lib/stores/shift';
	import type { PendingOrder } from '$lib/stores/pendingOrders';

	export let dispenser: DispenserState;
	export let onSideClick: (dispenserId: number, side: 'A' | 'B', hose: HoseState) => void = () => {};
	export let onCancelClick: (dispenserId: number, side: 'A' | 'B', hose: HoseState) => void = () => {};
	export let onStopClick: (dispenserId: number, side: 'A' | 'B', hose: HoseState) => void = () => {};
	export let verifyingSide: 'A' | 'B' | null = null;

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
		pendingPresetType: 'MONEY' | 'VOLUME';
	} {
		const hoses = dispenser.sides[side];
		const allIdle = hoses.every(h => h.status === 'IDLE');
		const busyHose = hoses.find(h => isHoseBusy(h));

		// Check for pending collection on any hose of this side.
		// Also catches AUTHORIZED dispatches stuck on IDLE hoses (phone-off bug).
		let pendingCollectionHose: HoseState | null = null;
		let pendingOrder: PendingOrder | undefined;
		for (const h of hoses) {
			const key = `${dispenser.dispenserId}-${h.hoseId}`;
			const order = orders.get(key);
			// Normal: COMPLETED + IDLE → collect. Bug recovery: FUELLING + IDLE → collect.
			if ((order?.status === 'COMPLETED' || order?.status === 'FUELLING') && h.status === 'IDLE') {
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
				pendingAmount: pendingOrder.finalAmount || pendingOrder.presetAmount,
				pendingCustomer: pendingOrder.customerName,
				pendingPresetType: (pendingOrder.status === 'COMPLETED' || pendingOrder.finalAmount > 0) ? 'MONEY' : (pendingOrder.presetType || 'MONEY')
			};
		}

		if (busyHose) {
			return {
				status: busyHose.status,
				primaryHose: busyHose,
				allIdle: false,
				isPendingCollection: false,
				pendingAmount: 0,
				pendingCustomer: '',
				pendingPresetType: 'MONEY'
			};
		}

		// Use actual hose status (may be CLOSED, ERROR, etc. — not always IDLE)
		const primaryHose = hoses[0] ?? null;
		return {
			status: primaryHose?.status ?? 'IDLE',
			primaryHose,
			allIdle,
			isPendingCollection: false,
			pendingAmount: 0,
			pendingCustomer: '',
			pendingPresetType: 'MONEY'
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
		pendingPresetType: 'MONEY' | 'VOLUME';
		color: string;
		label: string;
	}

	$: sides = dispenser && (['A', 'B'] as const).map(s => {
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
			{@const isVerifying = verifyingSide === info.side}

			<button
				class="touch-btn p-3 text-left transition-colors
					{info.side === 'A' ? 'bg-blue-50/20' : 'bg-amber-50/20'}
					{info.allIdle && !isVerifying ? 'hover:bg-green-50 active:bg-green-100' : ''}
					{info.isPendingCollection && !isVerifying ? 'bg-green-50 hover:bg-green-100 ring-1 ring-green-300' : ''}
					{isBusy && !isVerifying ? 'bg-yellow-50' : ''}
					{isVerifying ? 'bg-blue-50' : ''}
					{!isOnline || (!info.allIdle && !isBusy && !info.isPendingCollection) || isVerifying ? 'cursor-not-allowed' : ''}"
				on:click={() => info.primaryHose && !isVerifying && onSideClick(dispenser.dispenserId, info.side, info.primaryHose)}
				disabled={!isOnline || (!info.allIdle && !isBusy && !info.isPendingCollection) || isVerifying}
			>
				<!-- Side label -->
				<div class="text-lg font-bold mb-1 {info.side === 'A' ? 'text-blue-700' : 'text-amber-700'}">Lado {dispenser.dispenserId}{info.side}</div>

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
				<!-- Cancel button ───────────────────────────────────────────
				     Appears when:
				       a) Hose is AUTHORIZED/CALLING/STARTING (pre-dispatch, normal)
				       b) Hose is IDLE but order.status is FUELLING → nozzle was
				          lifted and hung up without dispensing fuel. Wayne returned
				          to IDLE without NEW_TRANSACTION → dispatch is orphaned.
				          (v0.19.7: frontend shows Cancel; backend double-barrier
				          blocks if fuel was actually dispensed — see cancel_dispatch)
				     ──────────────────────────────────────────────────────────── -->
				{@const pendingOrder = info.primaryHose ? $orderByHose.get(dispenser.dispenserId + '-' + info.primaryHose.hoseId) : null}
				{@const canCancel = (['AUTHORIZED', 'CALLING', 'STARTING'].includes(info.primaryHose?.status ?? '') ||
					(info.primaryHose?.status === 'IDLE' && pendingOrder?.status === 'FUELLING')) &&
					pendingOrder != null &&
					pendingOrder.authorizedByUserId === $currentUser?.user_id &&
					$shift != null}
				{#if canCancel}
					<button
						class="touch-btn mt-2 w-full py-1.5 rounded-lg border border-red-300 text-red-600 text-xs font-semibold
							hover:bg-red-50 active:bg-red-100 transition-colors"
						on:click|stopPropagation={() => { const h = info.primaryHose; if (h) onCancelClick(dispenser.dispenserId, info.side, h); }}
					>
						✕ Cancelar
					</button>
				{/if}
				<!-- Stop button (during FUELLING — small icon, deliberate action only) -->
				{@const canStop = (info.status === 'FUELLING' || info.status === 'STARTING') &&
					pendingOrder != null &&
					pendingOrder.authorizedByUserId === $currentUser?.user_id &&
					$shift != null}
				{#if canStop}
					<button
						class="touch-btn mt-2 ml-auto block w-8 h-8 rounded-full border border-orange-300 text-orange-500 text-xs
							hover:bg-orange-50 active:bg-orange-100 transition-colors flex items-center justify-center"
						title="Detener despacho"
						on:click|stopPropagation={() => { const h = info.primaryHose; if (h) onStopClick(dispenser.dispenserId, info.side, h); }}
					>
						⏹
					</button>
				{/if}
				{/if}

				<!-- Pending collection: show amount to collect -->
				{#if info.isPendingCollection}
					{#if info.pendingCustomer}
						<div class="text-xs text-gray-500">{info.pendingCustomer}</div>
					{/if}
					<div class="text-base font-bold text-green-700 mt-0.5">
						{#if info.pendingPresetType === 'VOLUME' && info.pendingAmount > 0}
							{info.pendingAmount} GAL
						{:else}
							${info.pendingAmount.toFixed(2)}
						{/if}
					</div>
					<div class="text-xs text-green-600 font-medium mt-0.5">Tocar para cobrar →</div>
				{/if}

				<!-- Verifying -->
				{#if isVerifying}
					<div class="flex items-center gap-2 mt-1">
						<div class="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
						<span class="text-xs text-blue-600 font-medium">Verificando...</span>
					</div>
				{/if}

			</button>
		{/each}
	</div>
</div>
