import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// The Vite dev server proxies API calls to the FastAPI backend, so the browser
// sees one origin and the backend needs no CORS configuration.
const BACKEND_TARGET = process.env.BACKEND_URL ?? 'http://127.0.0.1:8000';
const DEV_PORT = 5173;
const COVERAGE_THRESHOLD = 85;

export default defineConfig({
  plugins: [react()],
  server: {
    port: DEV_PORT,
    proxy: {
      '/inspections': { target: BACKEND_TARGET, changeOrigin: true },
      '/health': { target: BACKEND_TARGET, changeOrigin: true },
      '/batches': { target: BACKEND_TARGET, changeOrigin: true },
      '/categories': { target: BACKEND_TARGET, changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{js,jsx}'],
      exclude: ['src/main.jsx', 'src/test/**', 'src/**/*.test.{js,jsx}'],
      reporter: ['text', 'html'],
      thresholds: {
        statements: COVERAGE_THRESHOLD,
        branches: COVERAGE_THRESHOLD,
        functions: COVERAGE_THRESHOLD,
        lines: COVERAGE_THRESHOLD,
      },
    },
  },
});
