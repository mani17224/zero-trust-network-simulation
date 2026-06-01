# authz.rego — Zero Trust Authorization Policy
# Implements role-based access control for all services
# Every request must be explicitly authorized — deny by default
package zerotrust.authz

import future.keywords.in
import future.keywords.if

# ─── Default Deny ─────────────────────────────────────────────────────────────
# Zero Trust principle: deny everything unless explicitly allowed
default allow := false

# ─── Reasons ──────────────────────────────────────────────────────────────────
default reason := "access denied"

reason := "public endpoint" if {
    input.resource == "/health"
}

reason := "monitoring access" if {
    input.resource == "/metrics"
}

reason := "access granted" if {
    allow
}

# ─── Public Endpoints (no auth required) ──────────────────────────────────────
# Health check endpoint is open to all services and external monitors
allow if {
    input.resource == "/health"
}

# ─── Metrics Endpoint (monitoring role only) ───────────────────────────────────
allow if {
    input.resource == "/metrics"
    "monitoring" in roles_for_subject
}

# ─── Service-A Routes ─────────────────────────────────────────────────────────
# GET /verify → any authenticated service (valid CN in registry)
allow if {
    input.service == "service-a"
    input.method == "GET"
    input.resource == "/verify"
    subject_is_registered
}

# POST /login → only "gateway" service
allow if {
    input.service == "service-a"
    input.method == "POST"
    input.resource == "/login"
    input.subject == "gateway"
}

# ─── Service-B Routes ─────────────────────────────────────────────────────────
# FIX 2: all three blocks now restrict to input.resource == "/records"

# admin role: all methods on /records
allow if {
    input.service == "service-b"
    input.resource == "/records"
    "admin" in roles_for_subject
}

# writer role: GET + POST on /records (only if not admin)
allow if {
    input.service == "service-b"
    input.resource == "/records"
    input.method in {"GET", "POST"}
    "writer" in roles_for_subject
    not "admin" in roles_for_subject
}

# reader role: GET only on /records (only if not writer or admin)
allow if {
    input.service == "service-b"
    input.resource == "/records"
    input.method == "GET"
    "reader" in roles_for_subject
    not "writer" in roles_for_subject
    not "admin" in roles_for_subject
}

# ─── Service-C Routes ─────────────────────────────────────────────────────────
# admin role only — all methods
allow if {
    input.service == "service-c"
    "admin" in roles_for_subject
}

# ─── Helper: Roles for Current Subject ────────────────────────────────────────
# Looks up roles assigned to the request subject in data.json
roles_for_subject := roles if {
    roles := data.roles[input.subject]
} else := []

# ─── Helper: Subject is in the Service Registry ────────────────────────────────
subject_is_registered if {
    input.subject in data.service_registry
}

# ─── Audit Metadata (always included in response) ─────────────────────────────
# Returns structured metadata for logging and audit trail
audit := {
    "subject":   input.subject,
    "service":   input.service,
    "resource":  input.resource,
    "method":    input.method,
    "roles":     roles_for_subject,
    "allow":     allow,
    "reason":    reason,
    "timestamp": time.now_ns(),
}
