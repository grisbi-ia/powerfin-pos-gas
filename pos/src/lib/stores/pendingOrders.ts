import { writable, derived } from 'svelte/store';

export interface PendingOrder {
	orderId: string;
	dispenserId: number;
	hoseId: number;
	side: 'A' | 'B';
	customerName: string;
	plate: string;
	presetAmount: number;
	finalAmount: number;
	finalVolume: string;
	unitPrice: number;
	priceList: string;
	status: 'FUELLING' | 'COMPLETED';
	createdAt: string;
}

function createPendingOrdersStore() {
	const { subscribe, update } = writable<Map<string, PendingOrder>>(new Map());

	return {
		subscribe,

		addOrder(order: PendingOrder) {
			update(state => {
				state.set(order.orderId, order);
				return new Map(state);
			});
		},

		/** Mark order as completed; keyed by orderId or found by (dispenserId, hoseId) */
		completeOrder(dispenserId: number, hoseId?: number) {
			update(state => {
				for (const [id, order] of state) {
					const matchesDispenser = order.dispenserId === dispenserId;
					const matchesHose = hoseId ? order.hoseId === hoseId : true;
					if (matchesDispenser && matchesHose && order.status === 'FUELLING') {
						state.set(id, { ...order, status: 'COMPLETED' as const });
					}
				}
				return new Map(state);
			});
		},

		removeOrder(orderId: string) {
			update(state => {
				state.delete(orderId);
				return new Map(state);
			});
		}
	};
}

export const pendingOrders = createPendingOrdersStore();

/** Map of pending orders keyed by "dispenserId-hoseId" */
export const orderByHose = derived(pendingOrders, $orders => {
	const map = new Map<string, PendingOrder>();
	for (const order of $orders.values()) {
		const key = `${order.dispenserId}-${order.hoseId}`;
		map.set(key, order);
	}
	return map;
});
