/**
 * FusionBridge mock — local browser state (single terminal).
 *
 * Simulates dispenser lifecycle:
 *   IDLE → AUTHORIZED → STARTING → FUELLING → IDLE (+ SALE_COMPLETED)
 */

import type { AuthorizeData, DispenserState, HoseState, HoseStatusEvent } from './types';

// ── Local state (Map in memory) ──────────────────────────────

function buildHose(hoseId: number, dispenserId: number, side: 'A' | 'B',
	fusionHoseId: number, gradeId: string, gradeName: string): HoseState {
	return { hoseId, dispenserId, side, fusionHoseId, gradeId, gradeName,
		status: 'IDLE', subStatus: '', presetAmount: 0, attendantName: null, shiftId: null };
}

const DEFAULT_DISPENSERS: DispenserState[] = [
	{
		dispenserId: 1, fusionPumpId: 1, name: 'Surtidor 1', connected: true, online: true,
		sides: {
			A: [buildHose(1,1,'A',1,'SUPER','Gasolina Super'), buildHose(2,1,'A',2,'EXTRA','Gasolina Extra'), buildHose(3,1,'A',3,'DIESEL','Diesel'), buildHose(4,1,'A',4,'SUPER','Gasolina Super')],
			B: [buildHose(5,1,'B',5,'SUPER','Gasolina Super'), buildHose(6,1,'B',6,'EXTRA','Gasolina Extra'), buildHose(7,1,'B',7,'DIESEL','Diesel'), buildHose(8,1,'B',8,'SUPER','Gasolina Super')]
		}
	},
	{
		dispenserId: 2, fusionPumpId: 2, name: 'Surtidor 2', connected: true, online: true,
		sides: {
			A: [buildHose(9,2,'A',1,'SUPER','Gasolina Super'), buildHose(10,2,'A',2,'EXTRA','Gasolina Extra'), buildHose(11,2,'A',3,'DIESEL','Diesel'), buildHose(12,2,'A',4,'SUPER','Gasolina Super')],
			B: [buildHose(13,2,'B',5,'SUPER','Gasolina Super'), buildHose(14,2,'B',6,'EXTRA','Gasolina Extra'), buildHose(15,2,'B',7,'DIESEL','Diesel'), buildHose(16,2,'B',8,'SUPER','Gasolina Super')]
		}
	},
	{
		dispenserId: 3, fusionPumpId: 3, name: 'Surtidor 3', connected: true, online: true,
		sides: {
			A: [buildHose(17,3,'A',1,'SUPER','Gasolina Super'), buildHose(18,3,'A',2,'DIESEL','Diesel')],
			B: [buildHose(19,3,'B',3,'EXTRA','Gasolina Extra'), buildHose(20,3,'B',4,'SUPER','Gasolina Super')]
		}
	},
	{
		dispenserId: 4, fusionPumpId: 4, name: 'Surtidor 4', connected: true, online: true,
		sides: {
			A: [buildHose(21,4,'A',1,'SUPER','Gasolina Super'), buildHose(22,4,'A',2,'DIESEL','Diesel')],
			B: [buildHose(23,4,'B',3,'EXTRA','Gasolina Extra'), buildHose(24,4,'B',4,'SUPER','Gasolina Super')]
		}
	}
];

let dispensers: DispenserState[] = JSON.parse(JSON.stringify(DEFAULT_DISPENSERS));
let listeners: Array<(event: string, data: Record<string, unknown>) => void> = [];

function findHose(dispenserId: number, fusionHoseId: number) {
	const d = dispensers.find(d => d.dispenserId === dispenserId);
	if (!d) return null;
	for (const sideKey of ['A', 'B'] as const) {
		const idx = d.sides[sideKey].findIndex(h => h.fusionHoseId === fusionHoseId);
		if (idx >= 0) return { dispenser: d, sideKey, idx };
	}
	return null;
}

function updateHose(dispenserId: number, fusionHoseId: number, updates: Partial<HoseState>): boolean {
	const found = findHose(dispenserId, fusionHoseId);
	if (!found) return false;
	const updatedHoses = [...found.dispenser.sides[found.sideKey]];
	updatedHoses[found.idx] = { ...updatedHoses[found.idx], ...updates };
	dispensers = dispensers.map(d => {
		if (d.dispenserId !== dispenserId) return d;
		return { ...d, sides: { ...d.sides, [found.sideKey]: updatedHoses } };
	});
	return true;
}

function emit(event: string, data: Record<string, unknown>) {
	for (const fn of listeners) { try { fn(event, data); } catch { /* */ } }
}

function delay(ms = 200) { return new Promise(r => setTimeout(r, ms)); }

// ── REST API ─────────────────────────────────────────────────

export async function getDispensers(): Promise<{ dispensers: DispenserState[]; fusionConnected: boolean }> {
	await delay(100);
	return { dispensers: JSON.parse(JSON.stringify(dispensers)), fusionConnected: true };
}

export async function getDispenser(id: number): Promise<DispenserState> {
	await delay(50);
	const d = dispensers.find(d => d.dispenserId === id);
	if (!d) throw new Error(`Dispenser ${id} not found`);
	return JSON.parse(JSON.stringify(d));
}

export async function authorizeDispatch(data: AuthorizeData): Promise<{ status: string }> {
	const hose = findHose(data.dispenser_id, data.hose_id)?.dispenser
		?.sides[data.side]?.find(h => h.hoseId === data.hose_id);
	if (!hose) throw new Error(`Hose ${data.hose_id} not found`);

	const presetAmount = parseFloat(data.preset_value) || 0;

	// Step 0: AUTHORIZED (immediate)
	updateHose(data.dispenser_id, data.hose_id, {
		status: 'AUTHORIZED',
		subStatus: data.preset_type === 'MONEY' ? 'MONEY_PRESET' : 'VOLUME_PRESET',
		presetAmount, attendantName: 'Carlos', shiftId: 47
	});
	emit('HOSE_STATUS', {
		type: 'HOSE_STATUS', dispenserId: data.dispenser_id, hoseId: data.hose_id,
		side: data.side, fusionHoseId: hose.fusionHoseId,
		status: 'AUTHORIZED', subStatus: data.preset_type === 'MONEY' ? 'MONEY_PRESET' : 'VOLUME_PRESET',
		attendantName: 'Carlos', presetAmount
	} satisfies HoseStatusEvent);

	// Step 1: STARTING (3s)
	setTimeout(() => {
		updateHose(data.dispenser_id, data.hose_id, { status: 'STARTING', subStatus: '' });
		emit('HOSE_STATUS', {
			type: 'HOSE_STATUS', dispenserId: data.dispenser_id, hoseId: data.hose_id,
			side: data.side, fusionHoseId: hose.fusionHoseId,
			status: 'STARTING', subStatus: '', attendantName: 'Carlos'
		} satisfies HoseStatusEvent);
	}, 3000);

	// Step 2: FUELLING (6s)
	setTimeout(() => {
		updateHose(data.dispenser_id, data.hose_id, { status: 'FUELLING', subStatus: '' });
		emit('HOSE_STATUS', {
			type: 'HOSE_STATUS', dispenserId: data.dispenser_id, hoseId: data.hose_id,
			side: data.side, fusionHoseId: hose.fusionHoseId,
			status: 'FUELLING', subStatus: '', attendantName: 'Carlos'
		} satisfies HoseStatusEvent);
		emit('FUELING_PROGRESS', { type: 'FUELING_PROGRESS', dispenserId: data.dispenser_id,
			hoseId: data.hose_id, side: data.side, volume: '8.000', amount: (presetAmount * 0.30).toFixed(2) });
	}, 6000);

	// Step 3: Progress update (10s)
	setTimeout(() => {
		emit('FUELING_PROGRESS', { type: 'FUELING_PROGRESS', dispenserId: data.dispenser_id,
			hoseId: data.hose_id, side: data.side, volume: '18.000', amount: (presetAmount * 0.70).toFixed(2) });
	}, 10000);

	// Step 4: Complete → IDLE (14s)
	setTimeout(() => {
		const finalVolume = (presetAmount / 1.5).toFixed(3);
		updateHose(data.dispenser_id, data.hose_id, { status: 'IDLE', subStatus: '',
			presetAmount: 0, attendantName: null, shiftId: null });
		emit('HOSE_STATUS', {
			type: 'HOSE_STATUS', dispenserId: data.dispenser_id, hoseId: data.hose_id,
			side: data.side, fusionHoseId: hose.fusionHoseId,
			status: 'IDLE', subStatus: '', presetAmount: 0
		} satisfies HoseStatusEvent);
		emit('SALE_COMPLETED', { type: 'SALE_COMPLETED', dispenserId: data.dispenser_id,
			hoseId: data.hose_id, side: data.side, orderId: data.order_id,
			volume: finalVolume, amount: presetAmount.toFixed(2) });
	}, 14000);

	await delay(400);
	return { status: 'AUTHORIZED' };
}

export async function cancelDispenser(dispenserId: number, hoseId: number): Promise<boolean> {
	await delay(200);
	const ok = updateHose(dispenserId, hoseId, { status: 'IDLE', subStatus: '',
		presetAmount: 0, attendantName: null, shiftId: null });
	if (ok) {
		const found = findHose(dispenserId, hoseId);
		emit('HOSE_STATUS', { type: 'HOSE_STATUS', dispenserId, hoseId,
			side: found?.dispenser.sides[found.sideKey][found.idx].side ?? 'A',
			fusionHoseId: found?.dispenser.sides[found.sideKey][found.idx].fusionHoseId ?? 0,
			status: 'IDLE', subStatus: '', presetAmount: 0 });
	}
	return ok;
}

export async function getPrintPolicy(): Promise<{ policy: string }> {
	await delay(100);
	return { policy: 'ASK' };
}

export async function printReceipt(_data: unknown): Promise<{ status: string }> {
	await delay(300);
	return { status: 'PRINTED' };
}

// ── Mock SSE (local events) ──────────────────────────────────

export class MockEventSource {
	private closed = false;
	onerror: ((e: unknown) => void) | null = null;

	constructor() {
		listeners.push((event, data) => {
			if (this.closed) return;
			// Route events through the registered handler
			this._handler?.(event, data);
		});

		// Send INIT + current states after a tick
		setTimeout(() => {
			if (this.closed) return;
			this._handler?.('INIT', { fusionConnected: true });
			for (const d of dispensers) {
				for (const side of ['A', 'B'] as const) {
					for (const hose of d.sides[side]) {
						this._handler?.('HOSE_STATUS', {
							type: 'HOSE_STATUS', dispenserId: d.dispenserId, hoseId: hose.hoseId,
							side: hose.side, fusionHoseId: hose.fusionHoseId,
							status: hose.status, subStatus: hose.subStatus,
							attendantName: hose.attendantName ?? undefined, presetAmount: hose.presetAmount
						});
					}
				}
			}
		}, 500);
	}

	private _handler: ((event: string, data: Record<string, unknown>) => void) | null = null;

	addEventListener(type: string, handler: (data: Record<string, unknown>) => void): void {
		const prev = this._handler;
		this._handler = (event, data) => {
			if (event === type) handler(data);
			prev?.(event, data);
		};
	}

	close(): void { this.closed = true; }
}

export function connectToEvents(
	onEvent: (event: string, data: Record<string, unknown>) => void,
	_onError?: (error: Event) => void
): MockEventSource {
	const es = new MockEventSource();
	const eventTypes = ['INIT', 'HOSE_STATUS', 'NEW_TRANSACTION',
		'FUELING_PROGRESS', 'SALE_COMPLETED', 'TRANSACTION_LOCK', 'SALE_CLEARED',
		'PRICE_CHANGE', 'CONFIG_CHANGE', 'FUSION_STATUS'];
	for (const type of eventTypes) {
		es.addEventListener(type, (data) => onEvent(type, data));
	}
	return es;
}
