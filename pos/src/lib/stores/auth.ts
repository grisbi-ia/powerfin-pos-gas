import { writable, derived } from 'svelte/store';
import type { User } from '$lib/api/types';

interface AuthState {
	token: string | null;
	user: User | null;
}

function createAuthStore() {
	const stored = typeof localStorage !== 'undefined'
		? localStorage.getItem('auth')
		: null;

	const initialState: AuthState = stored ? JSON.parse(stored) : { token: null, user: null };

	const { subscribe, set, update } = writable<AuthState>(initialState);

	return {
		subscribe,

		login(token: string, user: User) {
			const state = { token, user };
			localStorage.setItem('auth', JSON.stringify(state));
			set(state);
		},

		logout() {
			localStorage.removeItem('auth');
			set({ token: null, user: null });
		},

		getToken(): string | null {
			let current: AuthState = { token: null, user: null };
			subscribe(s => current = s)();
			return current.token;
		}
	};
}

export const auth = createAuthStore();

export const isAuthenticated = derived(auth, $auth => $auth.token !== null);
export const currentUser = derived(auth, $auth => $auth.user);
