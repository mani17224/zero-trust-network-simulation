# Architecture — Zero Trust Network Simulation

## Zero Trust Principles

This project implements all three core Zero Trust tenets:

| Principle | Implementation |
|-----------|---------------|
| **Never trust, always verify** | Every request is authenticated via mTLS CN + OPA policy, regardless of source IP or network location |
| **Least privilege access** | Role assignments are minimal; service-a has only `reader`, gateway has `writer+reader` but not `admin` |
| **Assume breach** | All inter-service communication is encrypted (mTLS). WireGuard encrypts the network layer. Audit logs capture every decision |

## How WireGuard + mTLS + OPA Work Together

```
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 1: Network — WireGuard VPN (UDP/51820)                       │
│  All nodes communicate over encrypted WireGuard tunnel              │
│  iptables blocks all direct eth0 access to service ports            │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 2: Transport — mTLS (TLS 1.3)                                │
│  Every HTTP connection requires a client certificate                │
│  Certificates issued by Vault PKI (24h TTL, auto-renewed)           │
│  CN from cert identifies the calling service                        │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 3: Authorization — Open Policy Agent (OPA)                   │
│  Gateway queries OPA with: {subject, service, resource, method}     │
│  OPA evaluates Rego policy against data.json role assignments       │
│  Returns: {allow: bool, reason: string, audit: object}              │
│  Default deny — every rule must explicitly allow                    │
└─────────────────────────────────────────────────────────────────────┘
```

## Step-by-Step Request Lifecycle

```
Client                Gateway            OPA           Service-B
  │                      │                │                │
  │──[1] HTTPS request──▶│                │                │
  │    (mTLS cert attached)               │                │
  │                      │               │                │
  │                   [2] Extract CN      │                │
  │                   "gateway.zerotrust.local"            │
  │                      │               │                │
  │                   [3] Check CN allowlist               │
  │                   ✓ gateway is in allowlist            │
  │                      │               │                │
  │                   [4]──POST /v1/data/zerotrust/authz──▶│
  │                      │  { subject: "gateway",         │
  │                      │    service: "service-b",        │
  │                      │    resource: "/records",        │
  │                      │    method: "GET" }              │
  │                      │               │                │
  │                      │          [5] Evaluate Rego      │
  │                      │          roles["gateway"]       │
  │                      │          = ["writer","reader"]  │
  │                      │          reader → GET allowed   │
  │                      │               │                │
  │                   [6]◀──{ allow: true, reason: "..." }─│
  │                      │               │                │
  │                   [7] Forward request to service-b     │
  │                      │──────── mTLS GET /records ─────▶│
  │                      │               │                │
  │                      │◀───────── 200 JSON ────────────│
  │◀─────── 200 JSON ────│               │                │
  │                      │               │                │
  │                   [8] Log decision to structured JSON  │
  │                   [9] Update Prometheus counters       │
```

**Step numbers explained:**

1. Client sends HTTPS request with its mTLS client certificate attached
2. Gateway extracts the Common Name (CN) from the certificate's subject field
3. Gateway validates CN against the configured allowlist (env var `ALLOWED_CLIENT_CNS`)
4. Gateway POSTs an authorization input document to OPA at `/v1/data/zerotrust/authz`
5. OPA evaluates the `authz.rego` policy against `data.json` role assignments
6. OPA returns `{allow, reason, audit}` — gateway caches this for 10 seconds
7. If allowed, gateway reverse-proxies the request to the target service over mTLS
8. The complete decision is written to structured JSON logs (subject, resource, decision, latency)
9. Prometheus counters are incremented for the request, allow/deny decision, and OPA latency

## Security Threat Model

### Attacks Prevented

| Attack | Prevention |
|--------|-----------|
| **Man-in-the-middle** | All traffic encrypted via WireGuard (network) + mTLS (transport) |
| **Impersonation / spoofing** | Client cert CN must be in allowlist; cert must be signed by our Vault CA |
| **Lateral movement** | OPA enforces least-privilege; service-a cannot call service-c even if it reaches the gateway |
| **Privilege escalation** | Role assignments are centralized in `data.json`; no service can grant itself extra roles |
| **Rogue service** | Unknown CNs are rejected at the gateway CN allowlist check before OPA is even queried |
| **Cert replay** | Certificates have 24-hour TTL; Vault maintains CRL for immediate revocation |
| **Direct service access** | iptables rules on service nodes block all ports except WireGuard (UDP 51820) from eth0 |
| **OPA unavailability** | Gateway fails closed — OPA timeout/error → deny all requests |
| **Expired certs** | `renew_certs.sh` auto-renews certs with < 24h remaining; designed to run as cron |

### Limitations (Known, Out of Scope for Demo)

- Service-to-service calls are proxied through the gateway for OPA evaluation; direct service calls bypass OPA (mitigated by iptables + CN allowlists on each service)
- JWT tokens in Service A use a shared secret (HS256); production should use RS256 with key rotation
- Vault is run in dev mode for this simulation; production requires HA Vault with proper unsealing
- WireGuard configs contain placeholder keys; the setup script generates real keys when run

## Component Responsibilities

| Component | Responsibility | Does NOT do |
|-----------|---------------|-------------|
| **WireGuard** | Encrypts network layer, isolates VPN subnet | Authentication, authorization |
| **Vault PKI** | Issues and signs mTLS certificates, manages CRL | Network routing, policy decisions |
| **OPA** | Evaluates Rego policies, returns allow/deny | Certificate validation, network encryption |
| **Gateway** | mTLS enforcement, CN validation, OPA query, reverse proxy | Business logic |
| **Services A/B/C** | Business logic, CN allowlist check | OPA queries (delegated to gateway) |
| **Prometheus** | Metrics collection from all services | Alerting (use Alertmanager for that) |
| **Grafana** | Visualization of metrics | Data storage |
