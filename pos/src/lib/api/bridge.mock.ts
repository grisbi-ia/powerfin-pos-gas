import type { AuthorizeData, DispenserState, HoseState, HoseStatusEvent } from './types';

// ── Helper: build initial hose state ─────────────────────────

function buildHose(
	hoseId: number,
	dispenserId: number,
	side: 'A' | 'B',
	fusionHoseId: number,
	gradeId: string,
	gradeName: string
): HoseState {
	return {
		hoseId,
		dispenserId,
		side,
		fusionHoseId,
		gradeId,
		gradeName,
		status: 'IDLE',
		subStatus: '',
		presetAmount: 0,
		attendantName: null,
		shiftId: null
	};
}

// ── Mock dispenser states (hose-level granularity) ───────────

const MOCK_DISPENSERS: Map<number, DispenserState> = new Map([
	[1, {
		dispenserId: 1,
		fusionPumpId: 1,
		name: 'Surtidor 1',
		connected: true,
		online: true,
		sides: {
			A: [
				buildHose(1, 1, 'A', 1, 'SUPER', 'Gasolina Super'),
				buildHose(2, 1, 'A', 2, 'EXTRA', 'Gasolina Extra')
			],
			B: [
				buildHose(3, 1, 'B', 3, 'DIESEL', 'Diesel'),
				buildHose(4, 1, 'B', 4, 'SUPER', 'Gasolina Super')
			]
		}
	}],
	[2, {
		dispenserId: 2,
		fusionPumpId: 2,
		name: 'Surtidor 2',
		connected: true,
		online: true,
		sides: {
			A: [
				buildHose(5, 2, 'A', 1, 'SUPER', 'Gasolina Super'),
				buildHose(6, 2, 'A', 2, 'EXTRA', 'Gasolina Extra')
			],
			B: [
				buildHose(7, 2, 'B', 3, 'DIESEL', 'Diesel'),
				buildHose(8, 2, 'B', 4, 'SUPER', 'Gasolina Super')
			]
		}
	}]
]);

let mockFusionConnected = true;
const activeEventSources = new Set<MockEventSource>();

function broadcastToAll(event: string, data: Record<string, unknown>) {
	for (const es of activeEventSources) {
		es.emit(event, data);
	}
}

// ── Helper: find a specific hose in the mock data ────────────

function findHose(dispenserId: number, hoseId: number): { dispenser: DispenserState; hose: HoseState } | null {
	const dispenser = MOCK_DISPENSERS.get(dispenserId);
	if (!dispenser) return null;
	for (const side of ['A', 'B'] as const) {
		const hose = dispenser.sides[side].find(h => h.hoseId === hoseId);
		if (hose) return { dispenser, hose };
	}
	return null;
}

function updateHose(dispenserId: number, hoseId: number, updates: Partial<HoseState>): boolean {
	const found = findHose(dispenserId, hoseId);
	if (!found) return false;
	const { dispenser } = found;
	const sideKey = updates.side ?? found.hose.side;
	const sideHoses = dispenser.sides[sideKey];
	const idx = sideHoses.findIndex(h => h.hoseId === hoseId);
	if (idx < 0) return false;
	const updated = [...sideHoses];
	updated[idx] = { ...updated[idx], ...updates };
	MOCK_DISPENSERS.set(dispenserId, {
		...dispenser,
		sides: { ...dispenser.sides, [sideKey]: updated }
	});
	return true;
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
	return JSON.parse(JSON.stringify(d));
}

export async function authorizeDispatch(data: AuthorizeData): Promise<{ status: string }> {
	await delay(400);

	const updated = updateHose(data.dispenser_id, data.hose_id, {
		status: 'AUTHORIZED',
		subStatus: data.preset_type === 'MONEY' ? 'MONEY_PRESET' : 'VOLUME_PRESET',
		presetAmount: parseFloat(data.preset_value) || 0,
		attendantName: 'Carlos',
		shiftId: 47
	});

	if (!updated) {
		throw new Error(`Hose ${data.hose_id} not found on dispenser ${data.dispenser_id}`);
	}

	const hose = findHose(data.dispenser_id, data.hose_id)?.hose;
	if (!hose) throw new Error('Hose disappeared');

	// Simulate fueling sequence via broadcast
	setTimeout(() => {
		broadcastToAll('HOSE_STATUS', {
			type: 'HOSE_STATUS',
			dispenserId: data.dispenser_id,
			hoseId: data.hose_id,
			side: data.side,
			fusionHoseId: hose.fusionHoseId,
			status: 'AUTHORIZED',
			subStatus: data.preset_type === 'MONEY' ? 'MONEY_PRESET' : 'VOLUME_PRESET',
			attendantName: 'Carlos',
			presetAmount: parseFloat(data.preset_value) || 0
		} satisfies HoseStatusEvent);
	}, 1000);

	setTimeout(() => {
		updateHose(data.dispenser_id, data.hose_id, { status: 'FUELLING' });
		broadcastToAll('HOSE_STATUS', {
			type: 'HOSE_STATUS',
			dispenserId: data.dispenser_id,
			hoseId: data.hose_id,
			side: data.side,
			fusionHoseId: hose.fusionHoseId,
			status: 'FUELLING',
			subStatus: '',
			attendantName: 'Carlos'
		} satisfies HoseStatusEvent);

		broadcastToAll('FUELING_PROGRESS', {
			type: 'FUELING_PROGRESS',
			dispenserId: data.dispenser_id,
			hoseId: data.hose_id,
			side: data.side,
			volume: '1.500',
			amount: '15.00'
		});
	}, 3000);

	setTimeout(() => {
		broadcastToAll('FUELING_PROGRESS', {
			type: 'FUELING_PROGRESS',
			dispenserId: data.dispenser_id,
			hoseId: data.hose_id,
			side: data.side,
			volume: '3.200',
			amount: '32.00'
		});
	}, 4500);

	setTimeout(() => {
		updateHose(data.dispenser_id, data.hose_id, {
			status: 'IDLE',
			subStatus: '',
			presetAmount: 0,
			attendantName: null,
			shiftId: null
		});
		broadcastToAll('HOSE_STATUS', {
			type: 'HOSE_STATUS',
			dispenserId: data.dispenser_id,
			hoseId: data.hose_id,
			side: data.side,
			fusionHoseId: hose.fusionHoseId,
			status: 'IDLE',
			subStatus: '',
			attendantName: undefined,
			presetAmount: 0
		} satisfies HoseStatusEvent);

		broadcastToAll('SALE_COMPLETED', {
			type: 'SALE_COMPLETED',
			dispenserId: data.dispenser_id,
			hoseId: data.hose_id,
			side: data.side,
			orderId: data.order_id,
			volume: '38.000',
			amount: data.preset_value
		});
	}, 6000);

	return { status: 'AUTHORIZED' };
}

export async function cancelDispenser(dispenserId: number, hoseId: number): Promise<boolean> {
	await delay(200);
	return updateHose(dispenserId, hoseId, {
		status: 'IDLE',
		subStatus: '',
		presetAmount: 0,
		attendantName: null,
		shiftId: null
	});
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
	private closed = false;

	constructor() {
		activeEventSources.add(this);

		// Send INIT after connection, then current hose states
		setTimeout(() => {
			this.send('INIT', { fusionConnected: mockFusionConnected });

			for (const d of MOCK_DISPENSERS.values()) {
				for (const side of ['A', 'B'] as const) {
					for (const hose of d.sides[side]) {
						this.send('HOSE_STATUS', {
							type: 'HOSE_STATUS',
							dispenserId: d.dispenserId,
							hoseId: hose.hoseId,
							side: hose.side,
							fusionHoseId: hose.fusionHoseId,
							status: hose.status,
							subStatus: hose.subStatus,
							attendantName: hose.attendantName ?? undefined,
							presetAmount: hose.presetAmount
						} satisfies HoseStatusEvent);
					}
				}
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

	onerror: ((e: unknown) => void) | null = null;

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
		'INIT', 'HOSE_STATUS', 'NEW_TRANSACTION',
		'FUELING_PROGRESS', 'SALE_COMPLETED', 'TRANSACTION_LOCK', 'SALE_CLEARED',
		'PRICE_CHANGE', 'CONFIG_CHANGE', 'FUSION_STATUS'
	];

	for (const type of eventTypes) {
		es.addEventListener(type, (data) => onEvent(type, data));
	}

	return es;
}
