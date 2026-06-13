import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';

/**
 * Strip the Origin header from proxied requests so backends treat them
 * as same-origin. This is needed when accessing the dev server from
 * another device on the LAN (e.g. http://192.168.1.10:5173).
 *
 * Without this, the browser's Origin header (e.g. http://192.168.1.10:5173)
 * reaches FusionBridge and PowerFin ERP, which may reject it if not in
 * their CORS allow list.
 */
function stripOriginHeader(proxy: any) {
	proxy.on('proxyReq', (proxyReq: any, _req: any) => {
		proxyReq.removeHeader('Origin');
	});
}

export default defineConfig({
	plugins: [
		sveltekit(),
		VitePWA({
			registerType: 'autoUpdate',
			devOptions: { enabled: true },
			includeAssets: ['favicon.png', 'icons/icon-512.png'],
			manifest: {
				name: 'Powerfin GAS',
				short_name: 'Powerfin GAS',
				description: 'Sistema de despacho de combustible',
				theme_color: '#1E3A5F',
				background_color: '#1E3A5F',
				display: 'standalone',
				orientation: 'portrait',
				scope: '/',
				start_url: '/',
				icons: [
					{
						src: 'icons/icon-512.png',
						sizes: '512x512',
						type: 'image/png',
						purpose: 'any maskable'
					}
				]
			}
		})
	],
	server: {
		port: 5173,
		host: true,
		proxy: {
			// FusionBridge → :8090 (dispensers, dispatch, print, events, health)
			'/bridge': {
				target: 'http://localhost:8090',
				changeOrigin: true,
				rewrite: (path) => path.replace(/^\/bridge/, ''),
				configure: stripOriginHeader
			},
			// PowerFin ERP → :8080 (login, config, customers, shifts, dispatches, etc.)
			'/api/pos': {
				target: 'http://localhost:8080',
				changeOrigin: true,
				configure: stripOriginHeader
			}
		}
	}
});
