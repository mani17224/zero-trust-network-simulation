/**
 * store/index.js — Zustand global state.
 * Fix: opaUrl defaults to VITE_OPA_URL env var; gatewayUrl to VITE_GATEWAY_URL.
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";

const useStore = create(
  persist(
    (set, get) => ({
      // ── Theme ──────────────────────────────────────────────────────────────
      theme: "dark",
      toggleTheme: () => set((s) => ({ theme: s.theme === "dark" ? "light" : "dark" })),

      // ── Settings — default from VITE_ env vars ────────────────────────────
      opaUrl:     import.meta.env.VITE_OPA_URL     || "http://localhost:8181",
      vaultUrl:   "http://localhost:8200",
      gatewayUrl: import.meta.env.VITE_GATEWAY_URL || "http://localhost:8000",
      setOpaUrl:     (url) => set({ opaUrl: url }),
      setVaultUrl:   (url) => set({ vaultUrl: url }),
      setGatewayUrl: (url) => set({ gatewayUrl: url }),

      refreshInterval: 5000,
      setRefreshInterval: (ms) => set({ refreshInterval: ms }),

      // ── Notifications ──────────────────────────────────────────────────────
      notifications: [],
      addNotification: (type, message) => {
        const n = { id: crypto.randomUUID(), type, message, ts: Date.now() };
        set((s) => ({ notifications: [n, ...s.notifications].slice(0, 20) }));
        setTimeout(() => get().dismissNotification(n.id), 5000);
      },
      dismissNotification: (id) =>
        set((s) => ({ notifications: s.notifications.filter((n) => n.id !== id) })),
      clearNotifications: () => set({ notifications: [] }),

      // ── Live metrics ───────────────────────────────────────────────────────
      liveStats: { total: 0, allowed: 0, denied: 0, activePeers: 0 },
      setLiveStats: (stats) => set({ liveStats: stats }),

      timeSeries: [],
      pushTimeSeriesPoint: (point) =>
        set((s) => ({ timeSeries: [...s.timeSeries, point].slice(-20) })),

      // ── Topology ───────────────────────────────────────────────────────────
      selectedNode: null,
      setSelectedNode: (node) => set({ selectedNode: node }),

      // ── Sidebar ───────────────────────────────────────────────────────────
      sidebarCollapsed: false,
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
    }),
    {
      name: "zerotrust-store",
      partialize: (s) => ({
        theme:           s.theme,
        opaUrl:          s.opaUrl,
        vaultUrl:        s.vaultUrl,
        gatewayUrl:      s.gatewayUrl,
        refreshInterval: s.refreshInterval,
        sidebarCollapsed:s.sidebarCollapsed,
      }),
    }
  )
);

export default useStore;
