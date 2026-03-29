import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import path from "path";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: [
        "icon-192.svg",
        "icon-512.svg",
        "apple-touch-icon.svg",
      ],
      manifest: {
        name: "סמארט-כל — רשימת קניות חכמה",
        short_name: "סמארט-כל",
        description: "רשימת קניות חכמה שלומדת את ההרגלים שלך ומשווה מחירים",
        dir: "rtl",
        lang: "he",
        theme_color: "#22c55e",
        background_color: "#f3f4f6",
        display: "standalone",
        scope: "/",
        start_url: "/",
        icons: [
          {
            src: "icon-192.svg",
            sizes: "192x192",
            type: "image/svg+xml",
            purpose: "any",
          },
          {
            src: "icon-512.svg",
            sizes: "512x512",
            type: "image/svg+xml",
            purpose: "any maskable",
          },
          {
            src: "apple-touch-icon.svg",
            sizes: "180x180",
            type: "image/svg+xml",
            purpose: "apple touch icon",
          },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,svg,png,woff2}"],
        runtimeCaching: [
          {
            urlPattern: /^https?:\/\/.*\/api\/v1\/list/,
            handler: "NetworkFirst",
            options: {
              cacheName: "api-list-cache",
              expiration: {
                maxEntries: 50,
                maxAgeSeconds: 60 * 60 * 24, // 24 hours
              },
              networkTimeoutSeconds: 5,
            },
          },
          {
            urlPattern: /^https?:\/\/.*\/api\/v1\/categories/,
            handler: "StaleWhileRevalidate",
            options: {
              cacheName: "api-categories-cache",
              expiration: {
                maxEntries: 20,
                maxAgeSeconds: 60 * 60 * 24 * 7, // 7 days
              },
            },
          },
          {
            urlPattern: /^https?:\/\/.*\/api\/v1\//,
            handler: "NetworkFirst",
            options: {
              cacheName: "api-general-cache",
              expiration: {
                maxEntries: 100,
                maxAgeSeconds: 60 * 60 * 24, // 24 hours
              },
              networkTimeoutSeconds: 10,
            },
          },
          {
            urlPattern: /^https:\/\/accounts\.google\.com\//,
            handler: "NetworkOnly",
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
  },
});
