"""
metrics.py — Prometheus metrics for the Zero Trust Gateway.
Tracks request counts, deny counts, and OPA query latency.
"""
from __future__ import annotations

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    REGISTRY,
)

# ── Request Counters ────────────────────────────────────────────────────────────
REQUEST_COUNT = Counter(
    "gateway_requests_total",
    "Total number of requests processed by the gateway",
    labelnames=["method", "service", "status_code", "subject"],
)

DENIED_COUNT = Counter(
    "gateway_requests_denied_total",
    "Total number of requests denied by OPA policy",
    labelnames=["method", "service", "subject", "reason_category"],
)

ALLOWED_COUNT = Counter(
    "gateway_requests_allowed_total",
    "Total number of requests allowed through the gateway",
    labelnames=["method", "service", "subject"],
)

# ── OPA Latency Histogram ──────────────────────────────────────────────────────
OPA_LATENCY = Histogram(
    "gateway_opa_query_duration_seconds",
    "Time spent querying OPA for authorization decisions",
    labelnames=["service", "allow"],
    buckets=(0.001, 0.005, 0.010, 0.025, 0.050, 0.100, 0.250, 0.500, 1.0, 2.5),
)

# ── Upstream Latency Histogram ─────────────────────────────────────────────────
UPSTREAM_LATENCY = Histogram(
    "gateway_upstream_duration_seconds",
    "Time spent waiting for upstream microservice response",
    labelnames=["service", "status_code"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# ── Request Duration Histogram ─────────────────────────────────────────────────
REQUEST_DURATION = Histogram(
    "gateway_request_duration_seconds",
    "Total request duration from receipt to response",
    labelnames=["method", "service", "status_code"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# ── Active Connections Gauge ───────────────────────────────────────────────────
ACTIVE_CONNECTIONS = Gauge(
    "gateway_active_connections",
    "Number of currently active connections to the gateway",
)

# ── OPA Cache Metrics ──────────────────────────────────────────────────────────
OPA_CACHE_HITS = Counter(
    "gateway_opa_cache_hits_total",
    "Number of OPA decisions served from cache",
)

OPA_CACHE_MISSES = Counter(
    "gateway_opa_cache_misses_total",
    "Number of OPA decisions that required a real query",
)

# ── mTLS Certificate Metrics ───────────────────────────────────────────────────
MTLS_AUTH_FAILURES = Counter(
    "gateway_mtls_auth_failures_total",
    "Number of requests rejected due to missing or invalid client certificate",
    labelnames=["failure_reason"],
)

# ── Build Info ─────────────────────────────────────────────────────────────────
GATEWAY_INFO = Info(
    "gateway",
    "Zero Trust Gateway build and version information",
)


def initialize_metrics(app_version: str, app_name: str) -> None:
    """Set gateway info metric on startup."""
    GATEWAY_INFO.info({
        "version": app_version,
        "name": app_name,
    })


def record_request(
    method: str,
    service: str,
    status_code: int,
    subject: str,
    allowed: bool,
    deny_reason: str = "",
) -> None:
    """Record a completed request in all relevant counters."""
    REQUEST_COUNT.labels(
        method=method,
        service=service,
        status_code=str(status_code),
        subject=subject,
    ).inc()

    if allowed:
        ALLOWED_COUNT.labels(
            method=method,
            service=service,
            subject=subject,
        ).inc()
    else:
        # Categorize deny reason for better metrics grouping
        category = _categorize_deny_reason(deny_reason)
        DENIED_COUNT.labels(
            method=method,
            service=service,
            subject=subject,
            reason_category=category,
        ).inc()


def record_opa_latency(service: str, allow: bool, duration_seconds: float) -> None:
    """Record OPA query latency."""
    OPA_LATENCY.labels(
        service=service,
        allow=str(allow).lower(),
    ).observe(duration_seconds)


def record_upstream_latency(
    service: str, status_code: int, duration_seconds: float
) -> None:
    """Record upstream microservice response latency."""
    UPSTREAM_LATENCY.labels(
        service=service,
        status_code=str(status_code),
    ).observe(duration_seconds)


def record_request_duration(
    method: str, service: str, status_code: int, duration_seconds: float
) -> None:
    """Record total end-to-end request duration."""
    REQUEST_DURATION.labels(
        method=method,
        service=service,
        status_code=str(status_code),
    ).observe(duration_seconds)


def record_mtls_failure(reason: str) -> None:
    """Record an mTLS authentication failure."""
    MTLS_AUTH_FAILURES.labels(failure_reason=reason).inc()


def _categorize_deny_reason(reason: str) -> str:
    """Categorize a deny reason string into a metric-friendly label."""
    reason_lower = reason.lower()
    if "role" in reason_lower:
        return "insufficient_role"
    if "subject" in reason_lower or "registry" in reason_lower:
        return "unknown_subject"
    if "gateway" in reason_lower:
        return "wrong_subject"
    if "admin" in reason_lower:
        return "requires_admin"
    return "policy_denied"


def get_metrics_output() -> tuple[bytes, str]:
    """Generate Prometheus metrics output for /metrics endpoint."""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
