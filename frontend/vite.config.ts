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
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        // Split stable vendors out of the app chunk so they load once and
        // cache across deploys. Firebase is the heaviest dependency by far.
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom', 'zustand', '@tanstack/react-query'],
          'vendor-firebase': ['firebase/app', 'firebase/auth', 'firebase/firestore', 'firebase/storage'],
          'vendor-ui': ['framer-motion', 'lucide-react', 'clsx', 'tailwind-merge', 'axios'],
        },
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
