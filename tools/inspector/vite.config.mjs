import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [
    react(),
    {
      name: "inspector-session",
      transformIndexHtml: () =>
        process.env.ARIADNE_INSPECTOR_SESSION
          ? [
              {
                tag: "meta",
                attrs: {
                  name: "inspector-session",
                  content: process.env.ARIADNE_INSPECTOR_SESSION,
                },
                injectTo: "head",
              },
            ]
          : [],
    },
  ],
  server: {
    host: "127.0.0.1",
    port: 4173,
    strictPort: true,
    proxy: {
      "/api": `http://127.0.0.1:${process.env.ARIADNE_INSPECTOR_API_PORT || "8787"}`,
    },
  },
  preview: { host: "127.0.0.1", port: 4173 },
});
