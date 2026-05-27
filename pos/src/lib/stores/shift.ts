import { writable, derived } from 'svelte/store';
import type { Shift } from '$lib/api/types';

function createShiftStore() {
	const stored = typeof localStorage !== 'undefined'
		? localStorage.getItem('shift')
		: null;

	const initial: Shift | null = stored ? JSON.parse(stored) : null;

	const { subscribe, set, update } = writable<Shift | null>(initial);

	return {
		subscribe,
		set(shift: Shift) {
			localStorage.setItem('shift', JSON.stringify(shift));
			set(shift);
		},
		clear() {
			localStorage.removeItem('shift');
			set(null);
		}
	};
}

export const shift = createShiftStore();
export const shiftIsOpen = derived(shift, $s => $s?.status === 'OPEN');
