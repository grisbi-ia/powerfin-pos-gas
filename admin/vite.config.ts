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
    proxy: {
      '/api': 'http://localhost:8080'
    }
  }
});
