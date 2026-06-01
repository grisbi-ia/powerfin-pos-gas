import * as mock from './bridge.mock';
import { USE_MOCKS_BRIDGE } from './env';
import type { AuthorizeData, DispenserState } from './types';

// Dev: Vite proxies /bridge/* → localhost:8090
// Prod: Nginx proxies /bridge/* → FusionBridge (same domain, no CORS)
const BRIDGE_PREFIX = '/bridge';

function bridgeUrl(path: string): string {
	return `${BRIDGE_PREFIX}${path}`;
}

// ── REST ─────────────────────────────────────────────────────

export async function getDispensersRaw(): Promise<{ dispensers: Array<{ dispenserId: number; status: string; subStatus: string; hoseCount: number; presetAmount: number; grade?: string; activeHose?: number; connected: boolean }>; fusionConnected: boolean }> {
	if (USE_MOCKS_BRIDGE) {
		const mockResult = await mock.getDispensers();
		// Mock returns DispenserState[], convert back to raw format for compat
		const dispensers = mockResult.dispensers.map(d => ({
			dispenserId: d.dispenserId,
			status: d.sides.A[0]?.status ?? 'IDLE',
			subStatus: d.sides.A[0]?.subStatus ?? '',
			hoseCount: d.sides.A.length + d.sides.B.length,
			presetAmount: d.sides.A[0]?.presetAmount ?? 0,
			grade: d.sides.A[0]?.gradeId,
			activeHose: d.sides.A[0]?.fusionHoseId ?? 1,
			connected: d.connected
		}));
		return { dispensers, fusionConnected: mockResult.fusionConnected };
	}
	const res = await fetch(bridgeUrl('/api/dispensers'));
	if (!res.ok) throw new Error('Error fetching dispensers');
	return res.json();
}

export async function getDispenserRaw(id: number): Promise<{ dispenserId: number; status: string; subStatus: string; hoseCount: number; presetAmount: number; grade?: string; activeHose?: number; connected: boolean }> {
	if (USE_MOCKS_BRIDGE) {
		const d = await mock.getDispenser(id);
		return {
			dispenserId: d.dispenserId,
			status: d.sides.A[0]?.status ?? 'IDLE',
			subStatus: d.sides.A[0]?.subStatus ?? '',
			hoseCount: d.sides.A.length + d.sides.B.length,
			presetAmount: d.sides.A[0]?.presetAmount ?? 0,
			grade: d.sides.A[0]?.gradeId,
			activeHose: d.sides.A[0]?.fusionHoseId ?? 1,
			connected: d.connected
		};
	}
	const res = await fetch(bridgeUrl(`/api/dispensers/${id}`));
	if (!res.ok) throw new Error(`Dispenser ${id} not found`);
	return res.json();
}

export async function authorizeDispatch(data: AuthorizeData): Promise<{ status: string }> {
	if (USE_MOCKS_BRIDGE) return mock.authorizeDispatch(data);
	const res = await fetch(bridgeUrl('/api/dispatch/authorize'), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data)
	});
	if (!res.ok) throw new Error('Authorization failed');
	return res.json();
}

export async function cancelDispenser(fusionPumpId: number): Promise<boolean> {
	if (USE_MOCKS_BRIDGE) {
		return mock.cancelDispenser(fusionPumpId, 0);
	}
	const res = await fetch(bridgeUrl('/api/dispatch/cancel'), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ dispenser_id: fusionPumpId })
	});
	return res.ok;
}

export async function getPrintPolicy(): Promise<{ policy: string }> {
	if (USE_MOCKS_BRIDGE) return mock.getPrintPolicy();
	const res = await fetch(bridgeUrl('/api/print/policy'));
	if (!res.ok) throw new Error('Error fetching print policy');
	return res.json();
}

export async function printReceipt(data: unknown): Promise<{ status: string }> {
	if (USE_MOCKS_BRIDGE) return mock.printReceipt(data);
	const res = await fetch(bridgeUrl('/api/print'), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data)
	});
	if (!res.ok) throw new Error('Print failed');
	return res.json();
}

export async function paymentLock(saleId: string, lockId?: string): Promise<{ status: string; sale_id: string; lock_id: string }> {
	const res = await fetch(bridgeUrl('/api/dispatch/payment-lock'), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ sale_id: saleId, lock_id: lockId || saleId })
	});
	if (!res.ok) throw new Error('Payment lock failed');
	return res.json();
}

export async function paymentClear(saleId: string, method: string, lockId?: string): Promise<{ status: string; sale_id: string }> {
	const res = await fetch(bridgeUrl('/api/dispatch/payment-clear'), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ sale_id: saleId, lock_id: lockId || saleId, method })
	});
	if (!res.ok) throw new Error('Payment clear failed');
	return res.json();
}

export async function paymentUnlock(saleId: string, lockId?: string): Promise<{ status: string; sale_id: string }> {
	const res = await fetch(bridgeUrl('/api/dispatch/payment-unlock'), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ sale_id: saleId, lock_id: lockId || saleId })
	});
	if (!res.ok) throw new Error('Payment unlock failed');
	return res.json();
}

// ── SSE ──────────────────────────────────────────────────────

export function connectToEvents(
	onEvent: (event: string, data: Record<string, unknown>) => void,
	onError?: (error: Event) => void
): EventSource | import('./bridge.mock').MockEventSource {
	if (USE_MOCKS_BRIDGE) return mock.connectToEvents(onEvent, onError);

	const eventSource = new EventSource(bridgeUrl('/api/events'));

	// Listen for all named events
	const eventTypes = [
		'INIT', 'PUMP_STATUS_CHANGE', 'NEW_TRANSACTION',
		'DELIVERY_PROGRESS', 'TRANSACTION_LOCK', 'SALE_CLEARED',
		'PRICE_CHANGE', 'CONFIG_CHANGE', 'FUSION_STATUS'
	];

	for (const type of eventTypes) {
		eventSource.addEventListener(type, (e: MessageEvent) => {
			try {
				const data = JSON.parse(e.data);
				onEvent(type, data);
			} catch {
				onEvent(type, { raw: e.data });
			}
		});
	}

	eventSource.onerror = (e) => {
		if (onError) onError(e);
	};

	return eventSource;
}
