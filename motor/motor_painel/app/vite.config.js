import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: './',
  server: {
    proxy: {
      '/dados': {
        target: 'http://localhost:8378',
        changeOrigin: true,
      },
    },
  },
})