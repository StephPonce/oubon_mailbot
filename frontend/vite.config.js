import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ command }) => ({
  plugins: [react()],
  // Strip console.*/debugger from production bundles (~120 console
  // statements were shipping to prod). Dev keeps them for debugging.
  esbuild: command === 'build' ? { drop: ['console', 'debugger'] } : {},
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        secure: false,
        // Discovery requests with sentiment + caption generation + image
        // enhancement can take 60-90s on first hit (subsequent hits cached).
        // Vite's default proxy timeout is 30s, which surfaces as the
        // misleading "Origin not allowed by CORS, Status 504" error in
        // Safari — actually a proxy timeout, not a CORS issue.
        timeout: 120_000,        // socket inactivity timeout
        proxyTimeout: 120_000,   // upstream response timeout
      },
    },
  },
}));
