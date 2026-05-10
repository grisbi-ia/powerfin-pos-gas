import type { AuthorizeData, DispenserState } from './types';

// ── Mock dispenser states ────────────────────────────────────

const MOCK_DISPENSERS: Map<number, DispenserState> = new Map([
	[1, {
		dispenserId: 1,
		status: 'IDLE',
		subStatus: '',
		presetAmount: 0,
		hoseCount: 2,
		connected: true,
		online: true
	}],
	[2, {
		dispenserId: 2,
		status: 'IDLE',
		subStatus: '',
		presetAmount: 0,
		hoseCount: 2,
		connected: true,
		online: true
	}],
	[3, {
		dispenserId: 3,
		status: 'CLOSED',
		subStatus: '',
		presetAmount: 0,
		hoseCount: 2,
		connected: false,
		online: false
	}],
	[4, {
		dispenserId: 4,
		status: 'CLOSED',
		subStatus: '',
		presetAmount: 0,
		hoseCount: 2,
		connected: false,
		online: false
	}]
]);

let mockFusionConnected = true;
const activeEventSources = new Set<MockEventSource>();

function broadcastToAll(event: string, data: Record<string, unknown>) {
	for (const es of activeEventSources) {
		es.emit(event, data);
	}
}

// ── Mock delay ───────────────────────────────────────────────

function delay(ms = 200): Promise<void> {
	return new Promise(resolve => setTimeout(resolve, ms));
}

// ── Mock REST ────────────────────────────────────────────────

export async function getDispensers(): Promise<{ dispensers: DispenserState[]; fusionConnected: boolean }> {
	await delay(200);
	return {
		dispensers: Array.from(MOCK_DISPENSERS.values()),
		fusionConnected: mockFusionConnected
	};
}

export async function getDispenser(id: number): Promise<DispenserState> {
	await delay(100);
	const d = MOCK_DISPENSERS.get(id);
	if (!d) throw new Error(`Dispenser ${id} not found`);
	return { ...d };
}

export async function authorizeDispatch(data: AuthorizeData): Promise<{ status: string }> {
	await delay(400);
	const dispenser = MOCK_DISPENSERS.get(data.dispenser_id);
	if (dispenser) {
		MOCK_DISPENSERS.set(data.dispenser_id, {
			...dispenser,
			status: 'AUTHORIZED',
			subStatus: data.preset_type === 'MONEY' ? 'MONEY_PRESET' : 'VOLUME_PRESET',
			presetAmount: parseFloat(data.preset_value) || 0
		});

		// Simulate fueling events — broadcast to ALL connected clients
		setTimeout(() => broadcastToAll('PUMP_STATUS_CHANGE', {
			dispenserId: data.dispenser_id,
			status: 'AUTHORIZED',
			subStatus: data.preset_type === 'MONEY' ? 'MONEY_PRESET' : 'VOLUME_PRESET',
			presetAmount: parseFloat(data.preset_value) || 0
		}), 1000);

		setTimeout(() => {
			const d = MOCK_DISPENSERS.get(data.dispenser_id);
			if (d) {
				MOCK_DISPENSERS.set(data.dispenser_id, { ...d, status: 'FUELLING', subStatus: 'MONEY_PRESET' });
				broadcastToAll('PUMP_STATUS_CHANGE', {
					dispenserId: data.dispenser_id,
					status: 'FUELLING',
					subStatus: 'MONEY_PRESET',
					presetAmount: parseFloat(data.preset_value) || 0
				});
			}

			// Simulate delivery progress
			broadcastToAll('DELIVERY_PROGRESS', {
				dispenserId: data.dispenser_id,
				volume: '1.500',
				amount: '15.00'
			});
		}, 3000);

		setTimeout(() => {
			const d = MOCK_DISPENSERS.get(data.dispenser_id);
			if (d) {
				MOCK_DISPENSERS.set(data.dispenser_id, { ...d, status: 'FUELLING', subStatus: 'MONEY_PRESET' });
				broadcastToAll('DELIVERY_PROGRESS', {
					dispenserId: data.dispenser_id,
					volume: '3.200',
					amount: '32.00'
				});
			}
		}, 4500);

		setTimeout(() => {
			const d = MOCK_DISPENSERS.get(data.dispenser_id);
			if (d) {
				const finalAmount = parseFloat(data.preset_value) * 0.85;
				const finalVolume = finalAmount / (data.unit_price ?? 1.500);
				MOCK_DISPENSERS.set(data.dispenser_id, {
					...d,
					status: 'IDLE',
					subStatus: '',
					presetAmount: 0
				});
				broadcastToAll('PUMP_STATUS_CHANGE', {
					dispenserId: data.dispenser_id,
					status: 'IDLE',
					subStatus: '',
					presetAmount: 0
				});
			}
		}, 6000);
	}
	return { status: 'AUTHORIZED' };
}

export async function cancelDispenser(dispenserId: number): Promise<boolean> {
	await delay(200);
	const dispenser = MOCK_DISPENSERS.get(dispenserId);
	if (dispenser) {
		MOCK_DISPENSERS.set(dispenserId, {
			...dispenser,
			status: 'IDLE',
			subStatus: '',
			presetAmount: 0
		});
	}
	return true;
}

export async function getPrintPolicy(): Promise<{ policy: string }> {
	await delay(100);
	return { policy: 'ASK' };
}

export async function printReceipt(_data: unknown): Promise<{ status: string }> {
	await delay(300);
	return { status: 'PRINTED' };
}

// ── Mock SSE ─────────────────────────────────────────────────

export class MockEventSource {
	private listeners: Map<string, Array<(data: Record<string, unknown>) => void>> = new Map();
	private errorHandler: ((e: unknown) => void) | null = null;
	private closed = false;

	constructor() {
		activeEventSources.add(this);

		// Send INIT event after connection
		setTimeout(() => {
			this.send('INIT', { fusionConnected: mockFusionConnected });

			// Send initial dispenser states
			for (const d of MOCK_DISPENSERS.values()) {
				this.send('PUMP_STATUS_CHANGE', {
					dispenserId: d.dispenserId,
					status: d.status,
					subStatus: d.subStatus,
					presetAmount: d.presetAmount
				});
			}
		}, 500);
	}

	addEventListener(type: string, handler: (data: Record<string, unknown>) => void): void {
		if (!this.listeners.has(type)) {
			this.listeners.set(type, []);
		}
		this.listeners.get(type)!.push(handler);
	}

	send(event: string, data: Record<string, unknown>): void {
		emit(this, event, data);
	}

	emit = (event: string, data: Record<string, unknown>): void => {
		if (this.closed) return;
		const handlers = this.listeners.get(event);
		if (handlers) {
			for (const handler of handlers) {
				try { handler(data); } catch { /* ignore */ }
			}
		}
	}

	set onerror(handler: (e: unknown) => void) {
		this.errorHandler = handler;
	}

	close(): void {
		this.closed = true;
		activeEventSources.delete(this);
	}
}

function emit(es: MockEventSource, event: string, data: Record<string, unknown>) {
	es.emit(event, data);
}

export function connectToEvents(
	onEvent: (event: string, data: Record<string, unknown>) => void,
	_onError?: (error: Event) => void
): MockEventSource {
	const es = new MockEventSource();

	const eventTypes = [
		'INIT', 'PUMP_STATUS_CHANGE', 'NEW_TRANSACTION',
		'DELIVERY_PROGRESS', 'TRANSACTION_LOCK', 'SALE_CLEARED',
		'PRICE_CHANGE', 'CONFIG_CHANGE', 'FUSION_STATUS'
	];

	for (const type of eventTypes) {
		es.addEventListener(type, (data) => onEvent(type, data));
	}

	return es;
}
