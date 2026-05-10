<script lang="ts">
	import '../app.css';
	import { auth } from '$lib/stores/auth';
	import { shift } from '$lib/stores/shift';
	import { configStore } from '$lib/stores/config';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	// Mock imports — swap to real imports when backends are available
	import * as powerfin from '$lib/api/powerfin.mock';
	import * as bridge from '$lib/api/bridge.mock';

	$: currentPath = $page.url.pathname;

	onMount(async () => {
		// If we have a token but no user loaded yet, load config
		if ($auth.token && !$configStore.loaded) {
			try {
				const appConfig = await powerfin.fetchConfig($auth.token);
				configStore.setConfig(appConfig);
			} catch {
				auth.logout();
			}
		}
	});

	// Redirect logic
	$: if ($auth.token) {
		// Authenticated
		if (currentPath === '/login' || currentPath === '/') {
			goto('/pos', { replaceState: true });
		}
	} else {
		if (currentPath !== '/login') {
			goto('/login', { replaceState: true });
		}
	}
</script>

<slot />
