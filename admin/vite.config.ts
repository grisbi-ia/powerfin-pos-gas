import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [sveltekit()],
  css: {
    postcss: './postcss.config.js',
  },
  optimizeDeps: {
    include: ['svelte-sonner'],
  },
  ssr: {
    noExternal: ['svelte-sonner'],
  },
  test: {
    include: ['src/**/*.{test,spec}.{js,ts}']
  },
  server: {
    allowedHosts: ['neoguayas-paute.apx5.com', 'localhost', '127.0.0.1', '192.168.1.25'],
    proxy: {
      '/api': 'http://localhost:8080'
    }
  }
});
