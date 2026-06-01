/**
 * hooks/useCertificates.js — React Query hooks for certificate management.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import useStore from "../store";

function daysUntilExpiry(expiryDateStr) {
  const now = new Date();
  const expiry = new Date(expiryDateStr);
  return Math.ceil((expiry - now) / (1000 * 60 * 60 * 24));
}

function getExpiryStatus(days) {
  if (days < 0)  return "expired";
  if (days < 7)  return "critical";
  if (days < 30) return "warning";
  return "ok";
}

/** Mock certificate data — in production, fetch from Vault or a cert API */
const MOCK_CERTS = [
  { id: "gateway",          cn: "gateway.zerotrust.local",          issuer: "Zero Trust Intermediate CA", san: ["gateway.zerotrust.local","localhost","127.0.0.1"], validFrom: "2025-01-01T00:00:00Z", validTo: new Date(Date.now() + 18 * 60 * 60 * 1000).toISOString(), service: "gateway" },
  { id: "service-a",        cn: "service-a.zerotrust.local",        issuer: "Zero Trust Intermediate CA", san: ["service-a.zerotrust.local","localhost","127.0.0.1"], validFrom: "2025-01-01T00:00:00Z", validTo: new Date(Date.now() + 22 * 60 * 60 * 1000).toISOString(), service: "service-a" },
  { id: "service-b",        cn: "service-b.zerotrust.local",        issuer: "Zero Trust Intermediate CA", san: ["service-b.zerotrust.local","localhost","127.0.0.1"], validFrom: "2025-01-01T00:00:00Z", validTo: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(), service: "service-b" },
  { id: "service-c",        cn: "service-c.zerotrust.local",        issuer: "Zero Trust Intermediate CA", san: ["service-c.zerotrust.local","localhost","127.0.0.1"], validFrom: "2025-01-01T00:00:00Z", validTo: new Date(Date.now() + 6 * 24 * 60 * 60 * 1000).toISOString(), service: "service-c" },
  { id: "monitoring-agent", cn: "monitoring.zerotrust.local",       issuer: "Zero Trust Intermediate CA", san: ["monitoring.zerotrust.local","localhost","127.0.0.1"], validFrom: "2025-01-01T00:00:00Z", validTo: new Date(Date.now() + 20 * 60 * 60 * 1000).toISOString(), service: "monitoring-agent" },
];

export function useCertificates() {
  return useQuery({
    queryKey: ["certificates"],
    queryFn: async () =>
      MOCK_CERTS.map((cert) => {
        const days = daysUntilExpiry(cert.validTo);
        return { ...cert, daysUntilExpiry: days, status: getExpiryStatus(days) };
      }),
    refetchInterval: 60000,
  });
}

export function useRenewCertificate() {
  const queryClient = useQueryClient();
  const vaultUrl = useStore((s) => s.vaultUrl);
  return useMutation({
    mutationFn: async (serviceId) => {
      await new Promise((r) => setTimeout(r, 1500));
      return { renewed: true, service: serviceId };
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["certificates"] }),
  });
}
