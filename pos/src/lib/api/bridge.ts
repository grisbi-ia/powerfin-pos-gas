import type { AuthorizeData, DispenserState } from './types';

const BRIDGE_URL = 'http://localhost:8090';

// ── REST ─────────────────────────────────────────────────────

export async function getDispensers(): Promise<{ dispensers: DispenserState[]; fusionConnected: boolean }> {
	const res = await fetch(`${BRIDGE_URL}/api/dispensers`);
	if (!res.ok) throw new Error('Error fetching dispensers');
	return res.json();
}

export async function getDispenser(id: number): Promise<DispenserState> {
	const res = await fetch(`${BRIDGE_URL}/api/dispensers/${id}`);
	if (!res.ok) throw new Error(`Dispenser ${id} not found`);
	return res.json();
}

export async function authorizeDispatch(data: AuthorizeData): Promise<{ status: string }> {
	const res = await fetch(`${BRIDGE_URL}/api/dispatch/authorize`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data)
	});
	if (!res.ok) throw new Error('Authorization failed');
	return res.json();
}

export async function cancelDispenser(dispenserId: number): Promise<boolean> {
	const res = await fetch(`${BRIDGE_URL}/api/dispatch/cancel`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ dispenser_id: dispenserId })
	});
	return res.ok;
}

export async function getPrintPolicy(): Promise<{ policy: string }> {
	const res = await fetch(`${BRIDGE_URL}/api/print/policy`);
	if (!res.ok) throw new Error('Error fetching print policy');
	return res.json();
}

export async function printReceipt(data: unknown): Promise<{ status: string }> {
	const res = await fetch(`${BRIDGE_URL}/api/print`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data)
	});
	if (!res.ok) throw new Error('Print failed');
	return res.json();
}

// ── SSE ──────────────────────────────────────────────────────

export function connectToEvents(
	onEvent: (event: string, data: Record<string, unknown>) => void,
	onError?: (error: Event) => void
): EventSource {
	const eventSource = new EventSource(`${BRIDGE_URL}/api/events`);

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
