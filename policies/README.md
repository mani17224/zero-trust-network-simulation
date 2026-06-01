# OPA Authorization Policies — Zero Trust Network Simulation

## Overview

All authorization decisions flow through Open Policy Agent (OPA). The gateway
queries OPA **before** forwarding any request to a microservice. Default deny
means every request must match an explicit allow rule.

## Policy Files

| File | Purpose |
|------|---------|
| `authz.rego` | Main authorization policy with all allow/deny rules |
| `authz_test.rego` | Unit tests for every rule (run with `opa test`) |
| `conftest.rego` | Shared helpers: role expansion, input validation |
| `data.json` | Role assignments and service registry |

## Access Control Matrix

| Subject | /health | /metrics | service-a GET /verify | service-a POST /login | service-b GET | service-b POST | service-b DELETE | service-c |
|---------|---------|----------|-----------------------|-----------------------|---------------|----------------|------------------|-----------|
| gateway | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| service-a | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| service-b | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ |
| monitoring-agent | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| admin-service | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ |
| unknown | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

## Role Assignments

```json
{
  "gateway":          ["writer", "reader"],
  "service-a":        ["reader"],
  "service-b":        ["reader", "writer"],
  "monitoring-agent": ["monitoring"],
  "admin-service":    ["admin", "reader", "writer"]
}
```

## Rule Explanations

### `/health` — Open to All
```rego
allow if { input.resource == "/health" }
```
Health checks must be available to load balancers and probes without auth.

### `/metrics` — Monitoring Role Only
```rego
allow if {
    input.resource == "/metrics"
    "monitoring" in roles_for_subject
}
```
Only `monitoring-agent` has the `monitoring` role.

### `service-a GET /verify` — Any Registered Service
```rego
allow if {
    input.service == "service-a"
    input.method == "GET"
    input.resource == "/verify"
    subject_is_registered
}
```
Any service in the registry can verify a JWT (needed for cross-service auth).

### `service-a POST /login` — Gateway Only
```rego
allow if {
    input.service == "service-a"
    input.method == "POST"
    input.resource == "/login"
    input.subject == "gateway"
}
```
Only the gateway can authenticate users. Prevents services from directly logging in.

### `service-b` — RBAC by Role
- `reader` role → GET only
- `writer` role → GET + POST
- `admin` role → all methods including DELETE

### `service-c` — Admin Only
All routes on service-c require the `admin` role. No exceptions.

## Running Policy Tests

```bash
# Run all OPA unit tests
opa test policies/ -v

# Run with coverage
opa test policies/ -v --coverage

# Evaluate a single decision manually
opa eval \
  --data policies/ \
  --input - \
  'data.zerotrust.authz.allow' <<EOF
{
  "subject": "gateway",
  "service": "service-b",
  "resource": "/records",
  "method": "POST"
}
EOF

# Start OPA server
opa run --server --addr :8181 policies/
```

## OPA Input Schema

Every authorization request must include:

```json
{
  "subject":  "gateway",        // CN from mTLS client certificate
  "service":  "service-b",      // target microservice name
  "resource": "/records",       // request path
  "method":   "POST"            // HTTP method
}
```

## OPA Response Schema

```json
{
  "result": {
    "allow":  true,
    "reason": "service-b: GET/POST allowed for writer role",
    "audit": {
      "subject":   "gateway",
      "service":   "service-b",
      "resource":  "/records",
      "method":    "POST",
      "roles":     ["writer", "reader"],
      "allow":     true,
      "reason":    "service-b: GET/POST allowed for writer role",
      "timestamp": 1700000000000000000
    }
  }
}
```
