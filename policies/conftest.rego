# conftest.rego — Shared helpers and utilities for Zero Trust OPA policies
# Imported automatically by OPA when running tests in the same directory
package zerotrust.conftest

import future.keywords.in
import future.keywords.if

# ─── HTTP Method Sets ──────────────────────────────────────────────────────────
read_methods  := {"GET", "HEAD", "OPTIONS"}
write_methods := {"POST", "PUT", "PATCH"}
all_methods   := {"GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"}

# ─── Role Hierarchy ────────────────────────────────────────────────────────────
# Admin implies writer implies reader
role_implies := {
    "admin":  {"admin", "writer", "reader"},
    "writer": {"writer", "reader"},
    "reader": {"reader"},
    "monitoring": {"monitoring"},
}

# Expand a set of roles to include all implied roles
expand_roles(roles) := expanded if {
    expanded := union({implied |
        role := roles[_]
        implied := role_implies[role]
    })
} else := roles

# ─── Input Validation ──────────────────────────────────────────────────────────
# Check that all required input fields are present
valid_input if {
    input.subject != ""
    input.service != ""
    input.resource != ""
    input.method != ""
}

# Check that method is a known HTTP verb
valid_method if {
    input.method in all_methods
}

# ─── Subject Helpers ──────────────────────────────────────────────────────────
# Check if a subject exists in the role assignments
subject_has_roles(subject) if {
    data.roles[subject]
}

# Get roles for an arbitrary subject (used in tests)
get_roles_for(subject) := roles if {
    roles := data.roles[subject]
} else := set()

# Check if subject has a specific role (with expansion)
subject_has_role(subject, role) if {
    assigned := get_roles_for(subject)
    expanded := expand_roles(assigned)
    role in expanded
}

# ─── Resource Helpers ─────────────────────────────────────────────────────────
# Normalize resource path by stripping trailing slash and query string
normalize_resource(resource) := normalized if {
    # Strip query string
    parts := split(resource, "?")
    path  := parts[0]
    # Strip trailing slash (unless root)
    path != "/"
    normalized := trim_suffix(path, "/")
} else := resource

# Check if resource starts with a given prefix
resource_under(resource, prefix) if {
    startswith(resource, prefix)
}

# ─── Audit Log Builder ────────────────────────────────────────────────────────
# Constructs a structured audit entry — used by gateway logger
build_audit_entry(subject, service, resource, method, decision, reason) := entry if {
    entry := {
        "subject":   subject,
        "service":   service,
        "resource":  resource,
        "method":    method,
        "allow":     decision,
        "reason":    reason,
        "timestamp": time.now_ns(),
    }
}

# ─── Service Tier Classification ──────────────────────────────────────────────
# Returns the security tier for a given service name
service_tier(service) := tier if {
    tiers := {
        "service-a": "auth",
        "service-b": "data",
        "service-c": "admin",
        "gateway":   "gateway",
    }
    tier := tiers[service]
} else := "unknown"

# ─── Test Helpers ─────────────────────────────────────────────────────────────
# Build a standard input object for tests
make_input(subject, service, resource, method) := {
    "subject":  subject,
    "service":  service,
    "resource": resource,
    "method":   method,
}
