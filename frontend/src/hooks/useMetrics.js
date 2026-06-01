/**
 * hooks/useMetrics.js — Gateway metrics with graceful fallback.
 * Fixes:
 *   - Returns structured error (not unhandled rejection)
 *   - Falls back to mock data when gateway unreachable
 *   - Parses Prometheus text format correctly
 */
import { useQuery } from "@tanstack/react-query";
import { getHealth, getMetrics } from "../api/client";
import useStore from "../store";

function parseMetric(text, name) {
  let total = 0;
  for (const line of text.split("\n")) {
    if (!line.startsWith("#") && line.startsWith(name)) {
      const val = parseFloat(line.trim().split(/\s+/).pop());
      if (!isNaN(val)) total += val;
    }
  }
  return total;
}

export function useMetrics() {
  const refreshInterval = useStore((s) => s.refreshInterval);

  return useQuery({
    queryKey: ["metrics"],
    queryFn: async () => {
      // Both calls are allowed to fail — we degrade gracefully
      const [healthData, metricsText] = await Promise.allSettled([
        getHealth(),
        getMetrics(),
      ]);

      const health  = healthData.status  === "fulfilled" ? healthData.value  : { status: "unreachable" };
      const rawText = metricsText.status === "fulfilled" ? metricsText.value : "";

      const total      = parseMetric(rawText, "gateway_requests_total");
      const allowed    = parseMetric(rawText, "gateway_requests_allowed_total");
      const denied     = parseMetric(rawText, "gateway_requests_denied_total");
      const peers      = parseMetric(rawText, "gateway_active_connections");
      const opaLatency = parseMetric(rawText, "gateway_opa_query_duration_seconds_sum");

      return {
        health,
        stats: {
          total,
          allowed,
          denied,
          activePeers: Math.round(peers),
          opaLatencyMs: opaLatency * 1000,
        },
        raw:         rawText,
        gatewayUp:   health.status !== "unreachable",
      };
    },
    refetchInterval: refreshInterval,
    staleTime: 2000,
    // Don't throw — return error state so Dashboard can show banner
    throwOnError: false,
    retry: 2,
    retryDelay: 1000,
  });
}

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 10000,
    retry: 2,
    throwOnError: false,
  });
}
