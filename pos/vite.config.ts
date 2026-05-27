import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		port: 5173,
		host: true,
		proxy: {
			// FusionBridge → :8090 (dispensers, dispatch, print, events, health)
			'/bridge': {
				target: 'http://localhost:8090',
				changeOrigin: true,
				rewrite: (path) => path.replace(/^\/bridge/, '')
			},
			// PowerFin ERP → :8080 (login, config, customers, shifts, dispatches, etc.)
			'/api/pos': {
				target: 'http://localhost:8080',
				changeOrigin: true
			}
		}
	}
});
