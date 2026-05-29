/**
 * Bridge client that talks to the real FusionBridge REST API.
 * Converts the pump-level format from FusionBridge to the new hose-level
 * DispenserState format using the dispenser config from PowerFin.
 *
 * When VITE_USE_MOCKS=true, uses shared-state mock with per-hose granularity.
 */

import { USE_MOCKS_BRIDGE } from './env';
import type { AuthorizeData, DispenserState, HoseState, AppConfig } from './types';
import * as realBridge from './bridge';
import * as mockBridge from './bridge.mock';

// ── Format conversion (for real FusionBridge: pump-level → hose-level) ──

interface FusionBridgeDispenser {
	dispenserId: number;
	status: string;
	subStatus: string;
	hoseCount: number;
	presetAmount: number;
	grade?: string;
	activeHose?: number;
	connected: boolean;
}

interface FusionBridgeResponse {
	dispensers: FusionBridgeDispenser[];
	fusionConnected: boolean;
}

/**
 * Converts FusionBridge's pump-level format to the new DispenserState
 * with sides using the config layout.
 */
export function convertToDispenserState(
	fbResponse: FusionBridgeResponse,
	config: AppConfig | null
): { dispensers: DispenserState[]; fusionConnected: boolean } {
	const configDispensers = config?.dispensers ?? [];

	// Build a lookup: Fusion pump ID → { dispenserId, side, hoseConfig }
	const pumpToDispenser = new Map<number, { dispenserId: number; side: 'A' | 'B'; hose: { hose_id: number; fusion_hose_id: number; fusion_pump_id: number; grade_id: string; grade_name: string } }>();
	for (const cfg of configDispensers) {
		for (const sideKey of ['A', 'B'] as const) {
			for (const h of cfg.sides[sideKey]) {
				const pumpId = h.fusion_pump_id ?? cfg.fusion_pump_id;
				pumpToDispenser.set(pumpId, { dispenserId: cfg.dispenser_id, side: sideKey, hose: h });
			}
		}
	}

	// Initialize one DispenserState per config dispenser (all IDLE)
	const dispenserMap = new Map<number, DispenserState>();
	for (const cfg of configDispensers) {
		const initHose = (h: { hose_id: number; fusion_hose_id: number; fusion_pump_id: number; grade_id: string; grade_name: string }, sideKey: 'A' | 'B'): HoseState => ({
			hoseId: h.hose_id, dispenserId: cfg.dispenser_id, side: sideKey,
			fusionHoseId: h.fusion_hose_id, gradeId: h.grade_id, gradeName: h.grade_name,
			status: 'IDLE', subStatus: '', presetAmount: 0, attendantName: null, shiftId: null
		});
		dispenserMap.set(cfg.dispenser_id, {
			dispenserId: cfg.dispenser_id,
			fusionPumpId: cfg.fusion_pump_id,
			name: cfg.name,
			connected: true,
			online: true,
			sides: {
				A: cfg.sides.A.map(h => initHose(h, 'A')),
				B: cfg.sides.B.map(h => initHose(h, 'B'))
			}
		});
	}

	// Merge Fusion pump states into their config dispensers
	// Track per-pump online status: dispenser is online if ANY pump is not CLOSED/ERROR
	const dispenserPumpStates = new Map<number, boolean[]>();
	for (const fb of fbResponse.dispensers) {
		const mapping = pumpToDispenser.get(fb.dispenserId);
		if (!mapping) {
			console.warn('[bridge-client] No config mapping for Fusion pump ' + fb.dispenserId + ' — state "' + fb.status + '" not shown');
			continue;
		}
		const cfg = configDispensers.find(c => c.dispenser_id === mapping.dispenserId);
		if (!cfg) continue;
		const d = dispenserMap.get(mapping.dispenserId);
		if (!d) continue;

		const activeFusionHose = fb.activeHose ?? 0;
		const isGlobalState = ['CLOSED', 'ERROR', 'STOPPED'].includes(fb.status);

		// Track this pump's online status
		if (!dispenserPumpStates.has(mapping.dispenserId)) {
			dispenserPumpStates.set(mapping.dispenserId, []);
		}
		dispenserPumpStates.get(mapping.dispenserId)!.push(fb.status !== 'CLOSED' && fb.status !== 'ERROR');

		// Connection: dispenser is disconnected only if ALL pumps are disconnected
		if (!fb.connected) d.connected = false;

		// Update each hose that belongs to this pump
		for (const sideKey of ['A', 'B'] as const) {
			for (const h of d.sides[sideKey]) {
				const belongsToPump = (cfg.sides[sideKey].find(sh => sh.hose_id === h.hoseId)?.fusion_pump_id ?? cfg.fusion_pump_id) === fb.dispenserId;
				if (!belongsToPump) continue;

				const isActiveHose = activeFusionHose > 0 && h.fusionHoseId === activeFusionHose;
				if (isActiveHose || isGlobalState) {
					h.status = fb.status;
					h.subStatus = fb.subStatus;
					h.presetAmount = fb.presetAmount;
				}
			}
		}
	}

	// Calculate online: dispenser is online if at least one pump is not CLOSED/ERROR
	for (const [dispId, pumpStates] of dispenserPumpStates) {
		const d = dispenserMap.get(dispId);
		if (d) d.online = pumpStates.some(s => s);
	}

	return { dispensers: Array.from(dispenserMap.values()), fusionConnected: fbResponse.fusionConnected };
}

// ── Public API (mock-aware: preserves per-hose state when USE_MOCKS) ──

export async function getDispensers(config?: AppConfig | null): Promise<{ dispensers: DispenserState[]; fusionConnected: boolean }> {
	if (USE_MOCKS_BRIDGE) return mockBridge.getDispensers();

	const fbResponse = await realBridge.getDispensersRaw();
	const converted = convertToDispenserState(fbResponse, config ?? null);
	return converted;
}

export async function getDispenser(id: number, config?: AppConfig | null): Promise<DispenserState> {
	if (USE_MOCKS_BRIDGE) return mockBridge.getDispenser(id);

	const fb = await realBridge.getDispenserRaw(id);
	const converted = convertToDispenserState(
		{ dispensers: [fb], fusionConnected: true },
		config ?? null
	);
	return converted.dispensers[0];
}

export async function authorizeDispatch(data: AuthorizeData): Promise<{ status: string }> {
	if (USE_MOCKS_BRIDGE) return mockBridge.authorizeDispatch(data);
	return realBridge.authorizeDispatch(data);
}

export async function cancelDispenser(dispenserId: number, _hoseId: number): Promise<boolean> {
	if (USE_MOCKS_BRIDGE) return mockBridge.cancelDispenser(dispenserId, _hoseId);
	return realBridge.cancelDispenser(dispenserId);
}

export async function getPrintPolicy(): Promise<{ policy: string }> {
	if (USE_MOCKS_BRIDGE) return mockBridge.getPrintPolicy();
	return realBridge.getPrintPolicy();
}

export async function printReceipt(data: unknown): Promise<{ status: string }> {
	if (USE_MOCKS_BRIDGE) return mockBridge.printReceipt(data);
	return realBridge.printReceipt(data);
}

export async function paymentLock(saleId: string, lockId?: string): Promise<{ status: string; sale_id: string; lock_id: string }> {
	if (USE_MOCKS_BRIDGE) return { status: 'LOCKED', sale_id: saleId, lock_id: lockId || saleId };
	return realBridge.paymentLock(saleId, lockId);
}

export async function paymentClear(saleId: string, method: string, lockId?: string): Promise<{ status: string; sale_id: string }> {
	if (USE_MOCKS_BRIDGE) return { status: 'CLEARED', sale_id: saleId };
	return realBridge.paymentClear(saleId, method, lockId);
}

export async function paymentUnlock(saleId: string, lockId?: string): Promise<{ status: string; sale_id: string }> {
	if (USE_MOCKS_BRIDGE) return { status: 'UNLOCKED', sale_id: saleId };
	return realBridge.paymentUnlock(saleId, lockId);
}
