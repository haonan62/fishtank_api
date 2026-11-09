import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import { defineConfig } from 'vitest/config'

// In development the api runs separately (flask --app fishtank run), vite forwards api calls to it.
// "npm run build" writes dist/, which Flask serves itself, so production needs no proxy.
// the config runs in node, declared here so the ui does not need the node types
declare const process: { env: Record<string, string | undefined> }

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    // The ui installs like an app, and its pages and the catalogue work without a connection.
    // A new build takes over by itself the next time the app is opened.
    VitePWA({
      registerType: 'autoUpdate',
      injectRegister: 'script-defer',
      includeAssets: ['favicon.svg', 'icons/apple-touch-icon.png'],
      manifest: {
        name: 'Fishtank',
        short_name: 'Fishtank',
        description: 'Find out which tropical fish can share a tank, and build one in harmony.',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        background_color: '#f6f8f7',
        theme_color: '#f6f8f7',
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/icons/maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        // fonts for scripts fish names never use load from the network when needed
        globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
        globIgnores: ['**/*-{cyrillic,cyrillic-ext,greek,greek-ext,vietnamese}-*.woff2'],
        // every page of the ui is index.html, the api and health checks are not pages
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/fishtank_api/, /^\/healthz$/, /^\/readyz$/],
        cleanupOutdatedCaches: true,
        runtimeCaching: [
          {
            // the catalogue: fresh when online, the last one seen when offline
            // workbox only matches a regular expression to another site when it matches from the start, so this stays on ours
            urlPattern: /\/fishtank_api\/fish$/,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'catalogue',
              networkTimeoutSeconds: 5,
              expiration: { maxEntries: 2 },
              cacheableResponse: { statuses: [200] },
            },
          },
        ],
      },
    }),
  ],
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
