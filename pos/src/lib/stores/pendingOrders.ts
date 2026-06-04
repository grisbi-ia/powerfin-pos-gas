import { writable, derived, get } from 'svelte/store';
import type { DispatchOrder } from '$lib/api/types';

export interface PendingOrder {
	orderId: string;
	dispenserId: number;
	fusionPumpId: number;
	fusionHoseId: number;
	hoseId: number;
	side: 'A' | 'B';
	customerId?: string;
	customerName: string;
	plate: string;
	presetAmount: number;
	finalAmount: number;
	finalVolume: string;
	unitPrice: number;
	priceList: string;
	status: 'FUELLING' | 'COMPLETED';
	createdAt: string;
	authorizedBy?: string;
	authorizedByUserId?: number;
	invoiceNumber?: string;
}

const STORAGE_KEY = 'pendingOrders';

// ── localStorage helpers ────────────────────────────────────────

function loadFromStorage(): Map<string, PendingOrder> {
	try {
		if (typeof localStorage === 'undefined') return new Map();
		const stored = localStorage.getItem(STORAGE_KEY);
		if (!stored) return new Map();
		const parsed = JSON.parse(stored) as Record<string, PendingOrder>;
		return new Map(Object.entries(parsed));
	} catch {
		return new Map();
	}
}

function saveToStorage(orders: Map<string, PendingOrder>) {
	try {
		if (typeof localStorage === 'undefined') return;
		const obj: Record<string, PendingOrder> = {};
		for (const [key, order] of orders) {
			obj[key] = order;
		}
		localStorage.setItem(STORAGE_KEY, JSON.stringify(obj));
	} catch {
		// localStorage quota exceeded or unavailable — non-critical
	}
}

// ── Store ────────────────────────────────────────────────────────

function createPendingOrdersStore() {
	const initial = loadFromStorage();
	const { subscribe, update, set } = writable<Map<string, PendingOrder>>(initial);

	return {
		subscribe,

		/** Add a new order (on authorize). Persists to localStorage immediately. */
		addOrder(order: PendingOrder) {
			update(state => {
				const next = new Map(state);
				next.set(order.orderId, order);
				saveToStorage(next);
				return next;
			});
		},

		/**
		 * Mark order as completed when Fusion reports sale done.
		 * Matches by (fusionPumpId, fusionHoseId) to support multi-hose pumps.
		 * Optionally updates finalAmount and finalVolume from the actual dispense.
		 */
		completeOrder(fusionPumpId: number, fusionHoseId?: number, finalAmount?: number, finalVolume?: string) {
			update(state => {
				const next = new Map(state);
				for (const [id, order] of next) {
					const matchesPump = order.fusionPumpId === fusionPumpId;
					const matchesHose = fusionHoseId != null ? order.fusionHoseId === fusionHoseId : true;
					if (matchesPump && matchesHose && order.status === 'FUELLING') {
						const updates: Partial<PendingOrder> = { status: 'COMPLETED' as const };
						if (finalAmount !== undefined && finalAmount > 0) updates.finalAmount = finalAmount;
						if (finalVolume !== undefined && finalVolume !== '0.00' && finalVolume !== '0') updates.finalVolume = finalVolume;
						next.set(id, { ...order, ...updates });
					}
				}
				saveToStorage(next);
				return next;
			});
		},

		/**
		 * Update an existing order with server data (amounts, invoice, etc).
		 * Only updates fields that are present in the partial.
		 */
		updateOrder(orderId: string, updates: Partial<PendingOrder>) {
			update(state => {
				const next = new Map(state);
				const existing = next.get(orderId);
				if (existing) {
					next.set(orderId, { ...existing, ...updates });
					saveToStorage(next);
				}
				return next;
			});
		},

		/** Remove an order (collected or cancelled). */
		removeOrder(orderId: string) {
			update(state => {
				const next = new Map(state);
				next.delete(orderId);
				saveToStorage(next);
				return next;
			});
		},

		/** Update billing info on an existing order (post-dispatch). */
		updateOrderBilling(orderId: string, customerName: string, plate: string, customerId?: string) {
			const updates: Partial<PendingOrder> = { customerName, plate };
			if (customerId !== undefined) updates.customerId = customerId;
			this.updateOrder(orderId, updates);
		},

		/** Reload from localStorage explicitly (e.g. after a page refresh
		 * where the store may have been recreated before the module loaded).
		 */
		reloadFromStorage() {
			set(loadFromStorage());
		},

		/**
		 * Reconcile local pendingOrders with PowerFin's authoritative list.
		 *
		 * Rules:
		 *  - Server has an order we don't → add it (another device authorized it)
		 *  - We have an order the server doesn't → remove it (collected/cancelled elsewhere)
		 *  - Both have it → update ours with server's authoritative data
		 *
		 * Returns the count of changes made (for logging / UI feedback).
		 */
		reconcile(serverOrders: DispatchOrder[]): number {
			let changes = 0;
			update(state => {
				const next = new Map(state);
				const serverMap = new Map(serverOrders.map(o => [o.order_id, o]));

				// 1. Remove local orders NOT in server (collected/cancelled elsewhere)
				for (const [orderId] of next) {
					if (!serverMap.has(orderId)) {
						next.delete(orderId);
						changes++;
					}
				}

				// 2. Add/update orders from server
				for (const server of serverOrders) {
					const existing = next.get(server.order_id);

					// Orders that are COLLECTED or CANCELLED should not be in pending
					if (server.status === 'COLLECTED' || server.status === 'CANCELLED') {
						if (existing) {
							next.delete(server.order_id);
							changes++;
						}
						continue;
					}

					// Skip PENDING orders (not yet authorized on Fusion side)
					if (server.status === 'PENDING') continue;

					const localStatus: 'FUELLING' | 'COMPLETED' =
						server.status === 'COMPLETED' ? 'COMPLETED' : 'FUELLING';

					const order: PendingOrder = {
						orderId: server.order_id,
						dispenserId: server.dispenser_id,
						fusionPumpId: server.dispenser_id,
						fusionHoseId: server.hose_id,
						hoseId: server.hose_id,
						side: server.side,
						customerName: server.customer_name ?? 'Sin nombre',
						plate: server.plate ?? '',
						presetAmount: parseFloat(server.preset_value) || 0,
						finalAmount: server.final_amount ?? 0,
						finalVolume: server.final_volume ?? '0.00',
						unitPrice: server.unit_price,
						priceList: 'STANDARD',
						status: localStatus,
						createdAt: server.created_at,
						authorizedBy: server.authorized_by_user_id != null ? String(server.authorized_by_user_id) : undefined,
						authorizedByUserId: server.authorized_by_user_id,
						invoiceNumber: server.invoice_number
					};

					if (!existing) {
						// New order from another device
						next.set(server.order_id, order);
						changes++;
					} else {
						// Update existing: server is authoritative for amounts & status
						const updated = { ...existing };
						if (server.final_amount != null) updated.finalAmount = server.final_amount;
						if (server.final_volume != null) updated.finalVolume = server.final_volume;
						if (server.invoice_number != null) updated.invoiceNumber = server.invoice_number;
						if (server.status === 'COMPLETED' && updated.status === 'FUELLING') {
							updated.status = 'COMPLETED';
						}
						next.set(server.order_id, updated);
						// Only count as change if something actually changed
						if (JSON.stringify(existing) !== JSON.stringify(updated)) changes++;
					}
				}

				if (changes > 0) saveToStorage(next);
				return next;
			});

			return changes;
		},

		/** Clear all orders (e.g. on shift close). */
		clear() {
			set(new Map());
			try { localStorage.removeItem(STORAGE_KEY); } catch { /* */ }
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

/**
 * Convenience: get a snapshot of pendingOrders without subscribing.
 * Use sparingly — prefer reactive $pendingOrders in components.
 */
export function getPendingOrdersSnapshot(): PendingOrder[] {
	return Array.from(get(pendingOrders).values());
}
