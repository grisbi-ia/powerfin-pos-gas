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

	const dispensers: DispenserState[] = fbResponse.dispensers.map(fb => {
		const cfg = configDispensers.find(c => c.dispenser_id === fb.dispenserId);
		const name = cfg?.name ?? `Surtidor ${fb.dispenserId}`;
		const activeFusionHose = fb.activeHose ?? 0;

		const buildSide = (sideKey: 'A' | 'B', hoses: Array<{ hose_id: number; fusion_hose_id: number; grade_id: string; grade_name: string }>): HoseState[] => {
			return hoses.map((h) => {
				// Active only if this hose's fusion_hose_id matches the activeFusionHose reported by Fusion
				const isActive = activeFusionHose > 0 && h.fusion_hose_id === activeFusionHose;
				return {
					hoseId: h.hose_id,
					dispenserId: fb.dispenserId,
					side: sideKey,
					fusionHoseId: h.fusion_hose_id,
					gradeId: h.grade_id,
					gradeName: h.grade_name,
					status: isActive ? fb.status : 'IDLE',
					subStatus: isActive ? fb.subStatus : '',
					presetAmount: isActive ? fb.presetAmount : 0,
					attendantName: null,
					shiftId: null
				};
			});
		};

		const sides = {
			A: cfg ? buildSide('A', cfg.sides.A) : [],
			B: cfg ? buildSide('B', cfg.sides.B) : []
		};

		return {
			dispenserId: fb.dispenserId,
			fusionPumpId: fb.dispenserId,
			name,
			connected: fb.connected,
			online: fb.status !== 'CLOSED' && fb.status !== 'ERROR',
			sides
		};
	});

	return { dispensers, fusionConnected: fbResponse.fusionConnected };
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
