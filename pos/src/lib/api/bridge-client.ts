/**
 * Bridge client that talks to the real FusionBridge REST API.
 * Converts the pump-level format from FusionBridge to the new hose-level
 * DispenserState format using the dispenser config from PowerFin.
 *
 * To use mocks instead, import from '$lib/api/bridge.mock'.
 */
import type { AuthorizeData, DispenserState, HoseState, AppConfig } from './types';
import * as realBridge from './bridge';

const BRIDGE_URL = 'http://localhost:8090';

// ── Format conversion ───────────────────────────────────────

interface FusionBridgeDispenser {
	dispenserId: number;
	status: string;
	subStatus: string;
	hoseCount: number;
	presetAmount: number;
	grade?: string;
	connected: boolean;
}

interface FusionBridgeResponse {
	dispensers: FusionBridgeDispenser[];
	fusionConnected: boolean;
}

/**
 * Converts FusionBridge's pump-level format to the new DispenserState
 * with sides using the config layout. Falls back to mock config if
 * real config is not loaded.
 */
export function convertToDispenserState(
	fbResponse: FusionBridgeResponse,
	config: AppConfig | null
): { dispensers: DispenserState[]; fusionConnected: boolean } {
	const configDispensers = config?.dispensers ?? [];

	const dispensers: DispenserState[] = fbResponse.dispensers.map(fb => {
		const cfg = configDispensers.find(c => c.dispenser_id === fb.dispenserId);
		const name = cfg?.name ?? `Surtidor ${fb.dispenserId}`;

		// Build hose states from config sides.
		// Apply pump status only to side A (FusionBridge doesn't track per-hose yet).
		const buildSide = (sideKey: 'A' | 'B', hoses: Array<{ hose_id: number; fusion_hose_id: number; grade_id: string; grade_name: string }>): HoseState[] => {
			return hoses.map((h, idx) => {
				const isActive = sideKey === 'A' && idx === 0;
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

// ── Public API (same signatures as bridge.mock) ──────────────

export async function getDispensers(): Promise<{ dispensers: DispenserState[]; fusionConnected: boolean }> {
	const fbResponse = await realBridge.getDispensersRaw();
	// The config is loaded by the dashboard; we pass null and the dashboard
	// will call convertToDispenserState from the page when config is available
	const converted = convertToDispenserState(fbResponse, null);
	return converted;
}

export async function getDispenser(id: number): Promise<DispenserState> {
	const fb = await realBridge.getDispenserRaw(id);
	const converted = convertToDispenserState(
		{ dispensers: [fb], fusionConnected: true },
		null
	);
	return converted.dispensers[0];
}

export async function authorizeDispatch(data: AuthorizeData): Promise<{ status: string }> {
	return realBridge.authorizeDispatch(data);
}

export async function cancelDispenser(dispenserId: number, _hoseId: number): Promise<boolean> {
	return realBridge.cancelDispenser(dispenserId);
}

export async function getPrintPolicy(): Promise<{ policy: string }> {
	return realBridge.getPrintPolicy();
}

export async function printReceipt(data: unknown): Promise<{ status: string }> {
	return realBridge.printReceipt(data);
}
