import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// In development the api runs separately (flask --app fishtank run), vite forwards api calls to it.
// "npm run build" writes dist/, which Flask serves itself, so production needs no proxy.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/fishtank_api': 'http://127.0.0.1:5000',
    },
  },
  test: {
    environment: 'node',
  },
})
