import { writable, derived } from 'svelte/store';
import type { AppConfig } from '$lib/api/types';

function createConfigStore() {
	const { subscribe, set } = writable<{ config: AppConfig | null; loaded: boolean }>({
		config: null,
		loaded: false
	});

	return {
		subscribe,
		setConfig(config: AppConfig) {
			set({ config, loaded: true });
		}
	};
}

export const configStore = createConfigStore();
export const config = derived(configStore, $c => $c.config);
export const configLoaded = derived(configStore, $c => $c.loaded);
