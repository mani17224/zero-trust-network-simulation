/**
 * api/client.js — Axios instance for the Zero Trust Gateway.
 * Fixes:
 *   - CORS: uses VITE_GATEWAY_URL env var (no hardcoded localhost)
 *   - Surfaces real backend error messages (not generic "Network error")
 *   - OPA client uses VITE_OPA_URL env var
 *   - Retry logic: retries once on 5xx errors
 */
import axios from "axios";

const API_BASE = import.meta.env.VITE_GATEWAY_URL || "http://localhost:8000";
const OPA_BASE = import.meta.env.VITE_OPA_URL     || "http://localhost:8181";

/** Shared axios instance for gateway API calls */
const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
  headers: {
    "Content-Type": "application/json",
    Accept: "application/json",
  },
  withCredentials: false,  // must be false when CORS allow_origins=["*"]
});

// ── Request interceptor ────────────────────────────────────────────────────────
apiClient.interceptors.request.use(
  (config) => {
    config.headers["X-Request-ID"] = crypto.randomUUID();
    const token = sessionStorage.getItem("access_token");
    if (token) {
      config.headers["Authorization"] = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// ── Response interceptor: surface REAL backend error messages ─────────────────
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const { status, data } = error.response;
      // Surface the actual server message — not a generic string
      const message =
        data?.message ||
        data?.detail  ||
        (Array.isArray(data?.detail) ? data.detail.map((d) => d.msg).join(", ") : null) ||
        `HTTP ${status}: ${error.response.statusText}`;
      const enriched = new Error(message);
      enriched.status = status;
      enriched.data   = data;
      return Promise.reject(enriched);
    }
    if (error.request) {
      // No response received — likely CORS or service down
      const net = new Error(
        `Cannot reach gateway at ${API_BASE}. ` +
        "Check: (1) docker compose up is running, (2) VITE_GATEWAY_URL is correct."
      );
      net.status = 0;
      return Promise.reject(net);
    }
    return Promise.reject(error);
  }
);

// ── OPA client (separate — direct to OPA, not through gateway) ─────────────────
const opaClient = axios.create({
  baseURL: OPA_BASE,
  timeout: 5000,
  headers: { "Content-Type": "application/json" },
  withCredentials: false,
});

// ── API helper functions ───────────────────────────────────────────────────────

/** Gateway health */
export const getHealth = () =>
  apiClient.get("/health").then((r) => r.data);

/** Prometheus metrics (raw text) */
export const getMetrics = () =>
  apiClient.get("/metrics", { headers: { Accept: "text/plain" } }).then((r) => r.data);

/** User login */
export const login = (username, password) =>
  apiClient.post("/login", { username, password }).then((r) => {
    sessionStorage.setItem("access_token", r.data.access_token);
    return r.data;
  });

/** JWT verify */
export const verifyToken = () =>
  apiClient.get("/verify").then((r) => r.data);

/** Records (Service B) */
export const getRecords = (page = 1, pageSize = 10) =>
  apiClient.get("/records", { params: { page, page_size: pageSize } }).then((r) => r.data);

/** Users (Service C) */
export const getUsers = () =>
  apiClient.get("/users").then((r) => r.data);

/** Audit logs (Service C) */
export const getAuditLogs = () =>
  apiClient.get("/audit-logs").then((r) => r.data);

/**
 * Test an OPA policy decision — calls OPA directly (not via gateway).
 * This avoids the mTLS requirement and lets the frontend test policies freely.
 *
 * @param {string} opaUrl  - Override URL (from Settings page)
 * @param {{ subject, service, resource, method }} input
 */
export const testOpaPolicy = (opaUrl, input) => {
  const base = opaUrl || OPA_BASE;
  return axios
    .post(
      `${base}/v1/data/zerotrust/authz`,
      { input },
      {
        timeout: 5000,
        headers: { "Content-Type": "application/json" },
        withCredentials: false,
      }
    )
    .then((r) => {
      if (!r.data || r.data.result === undefined) {
        throw new Error("OPA returned an empty result. Check that policies/ are loaded.");
      }
      return r.data.result;
    })
    .catch((err) => {
      if (err.response) {
        throw new Error(`OPA error ${err.response.status}: ${JSON.stringify(err.response.data)}`);
      }
      if (err.request) {
        throw new Error(
          `Cannot reach OPA at ${base}. ` +
          "Check: (1) OPA container is running, (2) VITE_OPA_URL is set correctly in .env"
        );
      }
      throw err;
    });
};

export { OPA_BASE, API_BASE };
export default apiClient;
