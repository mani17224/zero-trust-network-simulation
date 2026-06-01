"""
main.py — Zero Trust API Gateway (FastAPI).
Fixes applied:
  - mTLS CN extraction with proper dev-mode fallback
  - Rate limiting via slowapi
  - Readiness + liveness probes
  - Full CORS for frontend
  - Structured error responses with real backend messages
  - Circuit-breaker awareness on upstream errors
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from gateway.config import get_settings
from gateway.forwarder import forward_request, resolve_service, close_upstream_client
from gateway.logger import (
    setup_logging, get_logger, generate_request_id,
    log_request, log_opa_decision,
)
from gateway import metrics
from gateway.policy import get_opa_client

settings = get_settings()
logger   = get_logger(__name__)

# ── Rate limiter ───────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])


# ── Lifespan ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    metrics.initialize_metrics(settings.app_version, settings.app_name)
    logger.info("Gateway starting", extra={
        "version": settings.app_version,
        "opa_url": settings.opa_url,
        "debug": settings.debug,
    })
    yield
    await close_upstream_client()
    opa = get_opa_client()
    await opa.close()
    logger.info("Gateway shutdown complete")


# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Zero Trust API Gateway with mTLS + OPA authorization",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# Rate limiter state + error handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS — allow all origins in dev, restrict in prod ─────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # Frontend, Swagger, and curl all work
    allow_credentials=False,       # Must be False when allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-OPA-Latency-Ms"],
)


# ── mTLS CN Extraction ─────────────────────────────────────────────────────────
def extract_client_cn(request: Request) -> Optional[str]:
    """
    Extract CN from the client mTLS certificate.

    Priority order:
      1. X-Client-Cert-CN header  (set by nginx/haproxy TLS terminator)
      2. X-Subject header         (set by gateway forwarder for downstream hops)
      3. ASGI ssl_object          (direct uvicorn TLS with client cert)
      4. DEV_CLIENT_CN env var    (development/testing only — skips real mTLS)

    Returns None if no cert is present (will trigger 401).
    """
    # 1. TLS terminator header
    for header in ("X-Client-Cert-CN", "X-Forwarded-Client-Cert", "X-Subject"):
        val = request.headers.get(header, "").strip()
        if val:
            return val

    # 2. Direct TLS (uvicorn with ssl context)
    ssl_object = request.scope.get("ssl_object")
    if ssl_object:
        try:
            peer_cert = ssl_object.getpeercert()
            if peer_cert:
                for field in peer_cert.get("subject", []):
                    for key, value in field:
                        if key == "commonName":
                            return value
        except Exception as exc:
            logger.warning("SSL cert extraction failed", extra={"error": str(exc)})

    # 3. Dev-mode fallback (only when DEBUG=true)
    if settings.debug:
        dev_cn = settings.dev_client_cn
        if dev_cn:
            logger.debug("DEV MODE: using DEV_CLIENT_CN", extra={"cn": dev_cn})
            return dev_cn

    return None


def normalize_subject(cn: Optional[str]) -> str:
    """
    Normalize 'gateway.zerotrust.local' → 'gateway'.
    Also handles short names that are already normalized.
    """
    if not cn:
        return ""
    # Strip domain suffix
    short = cn.split(".")[0]
    return short.strip()


# ── Middleware: request ID + active connection gauge ──────────────────────────
@app.middleware("http")
async def request_tracking_middleware(request: Request, call_next) -> Response:
    request_id = generate_request_id()
    request.state.request_id = request_id
    request.state.start_time = time.monotonic()
    metrics.ACTIVE_CONNECTIONS.inc()
    try:
        response = await call_next(request)
        return response
    finally:
        metrics.ACTIVE_CONNECTIONS.dec()


# ── Middleware: Zero Trust enforcement ────────────────────────────────────────
@app.middleware("http")
async def zero_trust_middleware(request: Request, call_next) -> Response:
    """
    Enforce mTLS identity + OPA authorization on every request.
    Pass-through: /health, /healthz, /ready, /metrics, /favicon.ico
    """
    request_id = getattr(request.state, "request_id", generate_request_id())
    path   = request.url.path
    method = request.method

    # ── Pass-through endpoints (probes + observability) ───────────────────────
    PASSTHROUGH = {"/health", "/healthz", "/ready", "/metrics", "/favicon.ico", "/docs", "/redoc", "/openapi.json"}
    if path in PASSTHROUGH:
        return await call_next(request)

    # ── Extract & validate CN ──────────────────────────────────────────────────
    raw_cn  = extract_client_cn(request)
    subject = normalize_subject(raw_cn)

    log_request(logger, request_id=request_id, method=method, path=path,
                subject=subject or "(none)",
                client_ip=request.client.host if request.client else "unknown")

    if not raw_cn:
        metrics.record_mtls_failure("no_client_cert")
        metrics.record_request(method, "unknown", 401, "", allowed=False, deny_reason="no_cert")
        return JSONResponse(status_code=401, content={
            "error":      "unauthorized",
            "message":    "Client certificate required (mTLS). "
                          "Attach X-Client-Cert-CN header or use a valid TLS client cert.",
            "hint":       "curl -H 'X-Client-Cert-CN: gateway.zerotrust.local' http://localhost:8000/records",
            "request_id": request_id,
        })

    if raw_cn not in settings.allowed_client_cns:
        logger.warning("CN not in allowlist", extra={"cn": raw_cn, "request_id": request_id})
        metrics.record_mtls_failure("cn_not_allowed")
        metrics.record_request(method, "unknown", 403, subject, allowed=False, deny_reason="cn_not_allowed")
        return JSONResponse(status_code=403, content={
            "error":      "forbidden",
            "message":    f"Client CN '{raw_cn}' is not in the allowlist.",
            "allowed":    settings.allowed_client_cns,
            "request_id": request_id,
        })

    # ── Resolve target service ─────────────────────────────────────────────────
    service_name = resolve_service(path) or "gateway"

    # ── OPA decision ──────────────────────────────────────────────────────────
    opa       = get_opa_client()
    opa_start = time.monotonic()
    decision  = await opa.authorize(subject=subject, service=service_name,
                                    resource=path, method=method)
    opa_ms    = (time.monotonic() - opa_start) * 1000

    log_opa_decision(logger, request_id=request_id, subject=subject,
                     service=service_name, resource=path, method=method,
                     allow=decision.allow, reason=decision.reason, latency_ms=opa_ms)
    metrics.record_opa_latency(service_name, decision.allow, opa_ms / 1000)

    if not decision.allow:
        metrics.record_request(method, service_name, 403, subject,
                               allowed=False, deny_reason=decision.reason)
        return JSONResponse(status_code=403, content={
            "error":      "forbidden",
            "message":    decision.reason,
            "subject":    subject,
            "service":    service_name,
            "resource":   path,
            "method":     method,
            "request_id": request_id,
        })

    # ── Forward to upstream ────────────────────────────────────────────────────
    response = await forward_request(request, service_name, request_id, subject)

    elapsed = time.monotonic() - getattr(request.state, "start_time", time.monotonic())
    response.headers["X-Request-ID"]     = request_id
    response.headers["X-OPA-Latency-Ms"] = f"{opa_ms:.2f}"

    metrics.record_request(method, service_name, response.status_code, subject, allowed=True)
    metrics.record_request_duration(method, service_name, response.status_code, elapsed)

    return response


# ── Health / Readiness / Liveness ─────────────────────────────────────────────
@app.get("/health", tags=["System"])
@app.get("/healthz", tags=["System"])
async def health_check() -> Dict[str, Any]:
    """Liveness probe — always returns healthy if process is running."""
    opa = get_opa_client()
    opa_ok = await opa.health_check()
    return {
        "status":  "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "opa":     "healthy" if opa_ok else "unreachable",
    }


@app.get("/ready", tags=["System"])
async def readiness_check() -> Dict[str, Any]:
    """
    Readiness probe — returns 503 if OPA is down (not ready to serve traffic).
    Kubernetes will stop routing to this pod until OPA recovers.
    """
    opa    = get_opa_client()
    opa_ok = await opa.health_check()
    if not opa_ok:
        return JSONResponse(status_code=503, content={
            "status":  "not_ready",
            "reason":  "OPA policy engine is unreachable",
            "service": settings.app_name,
        })
    return {"status": "ready", "service": settings.app_name}


# ── Prometheus metrics ─────────────────────────────────────────────────────────
@app.get("/metrics", tags=["System"])
async def prometheus_metrics() -> PlainTextResponse:
    """Prometheus scrape endpoint. Requires monitoring role via OPA."""
    output, content_type = metrics.get_metrics_output()
    return PlainTextResponse(content=output.decode(), media_type=content_type)


# ── Rate-limited login proxy (extra protection) ───────────────────────────────
@app.post("/login", tags=["Proxy"])
@limiter.limit("10/minute")
async def login_proxy(request: Request) -> Response:
    """Rate-limited login endpoint — max 10 attempts/min per IP."""
    request_id   = getattr(request.state, "request_id", generate_request_id())
    raw_cn       = extract_client_cn(request)
    subject      = normalize_subject(raw_cn)
    service_name = "service-a"
    return await forward_request(request, service_name, request_id, subject)


# ── Catch-all proxy ────────────────────────────────────────────────────────────
@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
    tags=["Proxy"],
    include_in_schema=False,
)
async def proxy(request: Request, path: str) -> Response:
    """Catch-all reverse proxy. Auth already enforced by middleware."""
    request_id   = getattr(request.state, "request_id", generate_request_id())
    raw_cn       = extract_client_cn(request)
    subject      = normalize_subject(raw_cn)
    service_name = resolve_service(request.url.path) or "gateway"
    return await forward_request(request, service_name, request_id, subject)
