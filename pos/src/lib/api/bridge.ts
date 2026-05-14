import type { AuthorizeData, DispenserState } from './types';

// Derive bridge URL from page hostname so tablets connect to the server, not localhost
function getBridgeUrl(): string {
	if (typeof window !== 'undefined') {
		return `http://${window.location.hostname}:8090`;
	}
	return 'http://localhost:8090'; // SSR fallback
}

let BRIDGE_URL = '';
function bridgeUrl(path: string): string {
	if (!BRIDGE_URL) BRIDGE_URL = getBridgeUrl();
	return `${BRIDGE_URL}${path}`;
}

// ── REST ─────────────────────────────────────────────────────

export async function getDispensersRaw(): Promise<{ dispensers: Array<{ dispenserId: number; status: string; subStatus: string; hoseCount: number; presetAmount: number; grade?: string; connected: boolean }>; fusionConnected: boolean }> {
	const res = await fetch(bridgeUrl('/api/dispensers'));
	if (!res.ok) throw new Error('Error fetching dispensers');
	return res.json();
}

export async function getDispenserRaw(id: number): Promise<{ dispenserId: number; status: string; subStatus: string; hoseCount: number; presetAmount: number; grade?: string; connected: boolean }> {
	const res = await fetch(bridgeUrl(`/api/dispensers/${id}`));
	if (!res.ok) throw new Error(`Dispenser ${id} not found`);
	return res.json();
}

export async function authorizeDispatch(data: AuthorizeData): Promise<{ status: string }> {
	const res = await fetch(bridgeUrl('/api/dispatch/authorize'), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data)
	});
	if (!res.ok) throw new Error('Authorization failed');
	return res.json();
}

export async function cancelDispenser(dispenserId: number): Promise<boolean> {
	const res = await fetch(bridgeUrl('/api/dispatch/cancel'), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ dispenser_id: dispenserId })
	});
	return res.ok;
}

export async function getPrintPolicy(): Promise<{ policy: string }> {
	const res = await fetch(bridgeUrl('/api/print/policy'));
	if (!res.ok) throw new Error('Error fetching print policy');
	return res.json();
}

export async function printReceipt(data: unknown): Promise<{ status: string }> {
	const res = await fetch(bridgeUrl('/api/print'), {
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
