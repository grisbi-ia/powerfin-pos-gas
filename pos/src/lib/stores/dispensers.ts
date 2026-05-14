import { writable, derived } from 'svelte/store';
import type { DispenserState, HoseState } from '$lib/api/types';

interface DispensersState {
	dispensers: Map<number, DispenserState>;
	fusionConnected: boolean;
}

function createDispensersStore() {
	const { subscribe, update, set } = writable<DispensersState>({
		dispensers: new Map(),
		fusionConnected: false
	});

	return {
		subscribe,

		/** Replace full dispenser state (e.g. from polling or SSE init) */
		updateDispenser(d: DispenserState) {
			update(state => {
				state.dispensers.set(d.dispenserId, d);
				return { ...state, dispensers: new Map(state.dispensers) };
			});
		},

		/** Update a single hose's state within a dispenser */
		updateHose(dispenserId: number, side: 'A' | 'B', hoseId: number, updates: Partial<HoseState>) {
			update(state => {
				const dispenser = state.dispensers.get(dispenserId);
				if (!dispenser) return state;
				const sideHoses = [...dispenser.sides[side]];
				const idx = sideHoses.findIndex(h => h.hoseId === hoseId);
				if (idx < 0) return state;
				sideHoses[idx] = { ...sideHoses[idx], ...updates };
				const updated: DispenserState = {
					...dispenser,
					sides: { ...dispenser.sides, [side]: sideHoses }
				};
				state.dispensers.set(dispenserId, updated);
				return { ...state, dispensers: new Map(state.dispensers) };
			});
		},

		setFusionConnected(connected: boolean) {
			update(state => ({ ...state, fusionConnected: connected }));
		},

		reset() {
			set({ dispensers: new Map(), fusionConnected: false });
		}
	};
}

export const dispensers = createDispensersStore();
export const dispenserList = derived(dispensers, $d => Array.from($d.dispensers.values()));
export const fusionConnected = derived(dispensers, $d => $d.fusionConnected);
