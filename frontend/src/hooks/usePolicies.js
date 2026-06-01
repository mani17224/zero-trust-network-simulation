/**
 * hooks/usePolicies.js — OPA policy hooks.
 * Fix: useTestPolicy reads opaUrl from store (updated by Settings page).
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { testOpaPolicy } from "../api/client";
import useStore from "../store";

const STATIC_POLICIES = [
  { id: "health-open",   name: "Health Endpoint Open",      resource: "/health",  role: "any",            enabled: true,  rego: 'allow if {\n  input.resource == "/health"\n}' },
  { id: "metrics-mon",   name: "Metrics: Monitoring Only",  resource: "/metrics", role: "monitoring",     enabled: true,  rego: 'allow if {\n  input.resource == "/metrics"\n  "monitoring" in roles_for_subject\n}' },
  { id: "svc-a-verify",  name: "Service-A: GET /verify",    resource: "/verify",  role: "any_registered", enabled: true,  rego: 'allow if {\n  input.service == "service-a"\n  input.method == "GET"\n  input.resource == "/verify"\n  subject_is_registered\n}' },
  { id: "svc-a-login",   name: "Service-A: POST /login",    resource: "/login",   role: "gateway only",   enabled: true,  rego: 'allow if {\n  input.service == "service-a"\n  input.method == "POST"\n  input.resource == "/login"\n  input.subject == "gateway"\n}' },
  { id: "svc-b-reader",  name: "Service-B: Reader GET",     resource: "/records", role: "reader",         enabled: true,  rego: 'allow if {\n  input.service == "service-b"\n  input.method == "GET"\n  "reader" in roles_for_subject\n}' },
  { id: "svc-b-writer",  name: "Service-B: Writer POST",    resource: "/records", role: "writer",         enabled: true,  rego: 'allow if {\n  input.service == "service-b"\n  input.method in {"GET","POST"}\n  "writer" in roles_for_subject\n}' },
  { id: "svc-b-admin",   name: "Service-B: Admin DELETE",   resource: "/records/*",role: "admin",         enabled: true,  rego: 'allow if {\n  input.service == "service-b"\n  "admin" in roles_for_subject\n}' },
  { id: "svc-c-admin",   name: "Service-C: Admin Only",     resource: "/users",   role: "admin",          enabled: true,  rego: 'allow if {\n  input.service == "service-c"\n  "admin" in roles_for_subject\n}' },
];

export function usePolicies() {
  return useQuery({
    queryKey: ["policies"],
    queryFn:  async () => STATIC_POLICIES,
    staleTime: 60000,
  });
}

export function useTestPolicy() {
  // Always read latest opaUrl from store (updated via Settings page)
  const opaUrl = useStore((s) => s.opaUrl);
  return useMutation({
    mutationFn: (input) => testOpaPolicy(opaUrl, input),
  });
}
