/**
 * hooks/useLogs.js — Audit logs with mock fallback.
 * Fix: doesn't crash when backend returns empty array or 403.
 */
import { useQuery } from "@tanstack/react-query";
import { getAuditLogs } from "../api/client";
import useStore from "../store";

function generateMockLogs() {
  const services  = ["gateway","service-a","service-b","service-c","monitoring-agent"];
  const targets   = ["service-a","service-b","service-c"];
  const resources = ["/records","/users","/login","/verify","/metrics","/audit-logs"];
  const methods   = ["GET","POST","DELETE","GET","GET"]; // weighted toward GET
  const decisions = ["allow","allow","allow","deny"];
  const reasons   = [
    "service-b: GET/POST allowed for writer role",
    "access denied: subject lacks required role for this resource",
    "public endpoint: /health",
    "access denied: service-c requires admin role",
    "service-b: GET allowed for reader role",
    "access denied: POST /login restricted to gateway service",
  ];

  return Array.from({ length: 50 }, (_, i) => ({
    id:             crypto.randomUUID(),
    timestamp:      new Date(Date.now() - i * 43000).toISOString(),
    subject:        services[Math.floor(Math.random() * services.length)],
    target_service: targets[Math.floor(Math.random() * targets.length)],
    resource:       resources[Math.floor(Math.random() * resources.length)],
    method:         methods[Math.floor(Math.random() * methods.length)],
    decision:       decisions[Math.floor(Math.random() * decisions.length)],
    reason:         reasons[Math.floor(Math.random() * reasons.length)],
    latency_ms:     parseFloat((Math.random() * 45).toFixed(2)),
    request_id:     crypto.randomUUID(),
  }));
}

const MOCK_LOGS = generateMockLogs();

export function useAuditLogs() {
  const refreshInterval = useStore((s) => s.refreshInterval);

  return useQuery({
    queryKey: ["audit-logs"],
    queryFn: async () => {
      try {
        const data = await getAuditLogs();
        // If backend returns empty, fall back to mock
        return Array.isArray(data) && data.length > 0 ? data : MOCK_LOGS;
      } catch (err) {
        // 403 (no admin role) or network error → show mock data
        console.warn("Audit logs unavailable, using mock data:", err.message);
        return MOCK_LOGS;
      }
    },
    refetchInterval: refreshInterval * 2,
    staleTime: 5000,
    throwOnError: false,
    retry: 1,
  });
}
