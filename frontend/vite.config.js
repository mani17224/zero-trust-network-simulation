import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  const gatewayTarget = env.VITE_GATEWAY_URL || "http://localhost:8000";
  const opaTarget     = env.VITE_OPA_URL     || "http://localhost:8181";

  return {
    plugins: [react()],
    server: {
      port: 3000,
      proxy: {
        // Gateway API proxy — avoids CORS in local dev
        "/api": {
          target:      gatewayTarget,
          changeOrigin: true,
          rewrite:     (path) => path.replace(/^\/api/, ""),
        },
        // OPA proxy — avoids CORS when browser calls OPA directly in dev
        "/opa": {
          target:      opaTarget,
          changeOrigin: true,
          rewrite:     (path) => path.replace(/^\/opa/, ""),
        },
      },
    },
    build: {
      outDir:    "dist",
      sourcemap: false,
      rollupOptions: {
        output: {
          manualChunks: {
            vendor:  ["react", "react-dom", "react-router-dom"],
            query:   ["@tanstack/react-query"],
            charts:  ["recharts"],
            zustand: ["zustand"],
          },
        },
      },
    },
    // Make VITE_ env vars available in code
    define: {
      __GATEWAY_URL__: JSON.stringify(gatewayTarget),
      __OPA_URL__:     JSON.stringify(opaTarget),
    },
  };
});
