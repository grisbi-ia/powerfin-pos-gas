import { writable, derived } from 'svelte/store';
import type { DispenserState } from '$lib/api/types';

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

		updateDispenser(d: Partial<DispenserState> & { dispenserId: number }) {
			update(state => {
				const existing = state.dispensers.get(d.dispenserId) ?? {
					dispenserId: d.dispenserId,
					status: 'UNKNOWN',
					subStatus: '',
					presetAmount: 0,
					hoseCount: 0,
					connected: false,
					online: false
				};
				state.dispensers.set(d.dispenserId, { ...existing, ...d });
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
