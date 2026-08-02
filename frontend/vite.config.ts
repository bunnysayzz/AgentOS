/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    environmentOptions: {
      jsdom: {
        // Give jsdom a proper origin so localStorage/sessionStorage exist
        url: 'http://localhost:5173',
      },
    },
    setupFiles: ['./src/test/setup.ts'],
    // Inline axios through the Vite pipeline so vi.mock('axios') in each
    // test file gets a truly isolated module (otherwise the CJS dep is
    // shared across test files and only the first vi.mock factory wins).
    server: {
      deps: {
        inline: ['axios'],
      },
    },
    css: false,
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    env: {
      VITE_API_URL: 'http://localhost:8000/api/v1',
    },
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/main.tsx', 'src/test/**'],
    },
  },
})
