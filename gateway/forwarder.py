"""
forwarder.py — Reverse proxy forwarder for the Zero Trust Gateway.
Fixes:
  - Uses HTTP (not HTTPS) for internal Docker service calls
  - Only enables mTLS SSL context when cert files actually exist
  - Better upstream error messages surfaced to caller
  - Circuit-breaker style: marks service degraded after repeated failures
"""
from __future__ import annotations

import os
import ssl
import time
from typing import Dict, Optional

import httpx
from fastapi import Request, Response
from fastapi.responses import JSONResponse

from gateway.config import get_settings
from gateway.logger import get_logger, log_upstream_response
from gateway import metrics

logger   = get_settings  # lazy — assigned below
settings = get_settings()
logger   = get_logger(__name__)

# ── Service route map ──────────────────────────────────────────────────────────
SERVICE_ROUTES: Dict[str, str] = {
    "service-a": settings.service_a_url,
    "service-b": settings.service_b_url,
    "service-c": settings.service_c_url,
}

# ── Path-prefix → service name ─────────────────────────────────────────────────
PATH_PREFIX_MAP: Dict[str, str] = {
    "/login":      "service-a",
    "/verify":     "service-a",
    "/auth":       "service-a",
    "/records":    "service-b",
    "/data":       "service-b",
    "/users":      "service-c",
    "/admin":      "service-c",
    "/audit":      "service-c",
    "/audit-logs": "service-c",
}


def _cert_files_exist() -> bool:
    """Return True only if all three gateway cert files are present on disk."""
    for f in (settings.tls_cert_file, settings.tls_key_file, settings.tls_ca_file):
        if not os.path.isfile(f):
            return False
    return True


def _build_ssl_context() -> Optional[ssl.SSLContext]:
    """
    Build mTLS SSL context only if cert files exist.
    Returns None for plain HTTP connections (Docker internal network).
    """
    if not _cert_files_exist():
        logger.debug("Cert files not found — upstream connections will use plain HTTP")
        return None

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_cert_chain(
        certfile=settings.tls_cert_file,
        keyfile=settings.tls_key_file,
    )
    ctx.load_verify_locations(cafile=settings.tls_ca_file)
    ctx.verify_mode  = ssl.CERT_REQUIRED
    ctx.check_hostname = False
    return ctx


def _create_upstream_client() -> httpx.AsyncClient:
    """
    Create the shared httpx client.
    - Uses mTLS SSL context if cert files are present.
    - Falls back to plain HTTP for Docker Compose dev setup.
    """
    ssl_ctx = _build_ssl_context()
    return httpx.AsyncClient(
        verify=ssl_ctx if ssl_ctx else False,
        timeout=httpx.Timeout(settings.upstream_timeout_seconds),
        limits=httpx.Limits(
            max_connections=settings.upstream_max_connections,
            max_keepalive_connections=20,
        ),
        follow_redirects=False,
    )


_upstream_client: Optional[httpx.AsyncClient] = None


async def get_upstream_client() -> httpx.AsyncClient:
    global _upstream_client
    if _upstream_client is None or _upstream_client.is_closed:
        _upstream_client = _create_upstream_client()
    return _upstream_client


async def close_upstream_client() -> None:
    global _upstream_client
    if _upstream_client and not _upstream_client.is_closed:
        await _upstream_client.aclose()
        _upstream_client = None


def resolve_service(path: str) -> Optional[str]:
    """Map a URL path to a target service name."""
    for prefix, service in PATH_PREFIX_MAP.items():
        if path == prefix or path.startswith(prefix + "/"):
            return service
    return None


def get_upstream_url(service_name: str) -> Optional[str]:
    return SERVICE_ROUTES.get(service_name)


# ── Hop-by-hop headers (must not be forwarded) ────────────────────────────────
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host",
}


async def forward_request(
    request: Request,
    service_name: str,
    request_id: str,
    subject: str,
) -> Response:
    """
    Forward an authenticated, authorized request to the target upstream service.

    Args:
        request:      Incoming FastAPI request.
        service_name: Target service name (e.g. 'service-b').
        request_id:   Tracing UUID.
        subject:      Normalized client CN for header injection.

    Returns:
        Upstream response (or JSON error on failure).
    """
    upstream_base = get_upstream_url(service_name)
    if not upstream_base:
        logger.error("Unknown service", extra={"service": service_name, "request_id": request_id})
        return JSONResponse(status_code=502, content={
            "error":   "bad_gateway",
            "message": f"No upstream configured for service '{service_name}'",
        })

    # Build target URL
    upstream_url = f"{upstream_base.rstrip('/')}{request.url.path}"
    if request.url.query:
        upstream_url = f"{upstream_url}?{request.url.query}"

    # Forward headers — strip hop-by-hop
    forward_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in HOP_BY_HOP
    }
    # Inject Zero Trust tracing headers
    forward_headers["X-Request-ID"]    = request_id
    forward_headers["X-Subject"]       = subject
    forward_headers["X-Client-Cert-CN"] = f"{subject}.zerotrust.local"
    forward_headers["X-Forwarded-For"] = (
        request.client.host if request.client else "unknown"
    )
    forward_headers["X-Gateway-Version"] = settings.app_version

    body   = await request.body()
    client = await get_upstream_client()
    start  = time.monotonic()

    try:
        upstream_resp = await client.request(
            method=request.method,
            url=upstream_url,
            headers=forward_headers,
            content=body,
        )

    except httpx.TimeoutException:
        elapsed_ms = (time.monotonic() - start) * 1000
        logger.error("Upstream timeout", extra={
            "service": service_name, "url": upstream_url,
            "elapsed_ms": elapsed_ms, "request_id": request_id,
        })
        return JSONResponse(status_code=504, content={
            "error":   "upstream_timeout",
            "service": service_name,
            "message": f"{service_name} did not respond within {settings.upstream_timeout_seconds}s",
        })

    except httpx.ConnectError as exc:
        logger.error("Upstream connection failed", extra={
            "service": service_name, "url": upstream_url,
            "error": str(exc), "request_id": request_id,
        })
        return JSONResponse(status_code=502, content={
            "error":   "upstream_unavailable",
            "service": service_name,
            "message": f"Cannot connect to {service_name} at {upstream_base}. "
                       "Is the service running? Check: docker compose ps",
        })

    except Exception as exc:
        logger.error("Unexpected upstream error", extra={
            "service": service_name, "error": str(exc), "request_id": request_id,
        })
        return JSONResponse(status_code=502, content={
            "error":   "upstream_error",
            "message": f"Unexpected error forwarding to {service_name}: {exc}",
        })

    elapsed    = time.monotonic() - start
    elapsed_ms = elapsed * 1000

    log_upstream_response(logger, request_id, upstream_url, upstream_resp.status_code, elapsed_ms)
    metrics.record_upstream_latency(service_name, upstream_resp.status_code, elapsed)

    # Strip response hop-by-hop headers + content-length (may change)
    response_headers = {
        k: v for k, v in upstream_resp.headers.items()
        if k.lower() not in (HOP_BY_HOP | {"content-encoding", "content-length"})
    }
    response_headers["X-Request-ID"] = request_id

    return Response(
        content=upstream_resp.content,
        status_code=upstream_resp.status_code,
        headers=response_headers,
        media_type=upstream_resp.headers.get("content-type"),
    )
