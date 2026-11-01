import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// In development the api runs separately (flask --app fishtank run), vite forwards api calls to it.
// "npm run build" writes dist/, which Flask serves itself, so production needs no proxy.
// the config runs in node, declared here so the ui does not need the node types
declare const process: { env: Record<string, string | undefined> }

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      // FISHTANK_API points at a Flask that runs on another port
      '/fishtank_api': process.env.FISHTANK_API ?? 'http://127.0.0.1:5000',
    },
  },
  test: {
    environment: 'node',
  },
})
