import { writable, derived } from 'svelte/store';
import type { Shift } from '$lib/api/types';

function createShiftStore() {
	const { subscribe, set, update } = writable<Shift | null>(null);

	return {
		subscribe,
		set,
		clear() { set(null); }
	};
}

export const shift = createShiftStore();
export const shiftIsOpen = derived(shift, $s => $s?.status === 'OPEN');
