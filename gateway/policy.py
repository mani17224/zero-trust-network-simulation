"""
policy.py — Async OPA client for Zero Trust Gateway.
Queries OPA for authorization decisions with TTL-based caching.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import Any, Dict, Optional, Tuple

import httpx

from gateway.config import get_settings
from gateway.logger import get_logger
from gateway import metrics

logger = get_logger(__name__)
settings = get_settings()


class OPADecision:
    """Represents an OPA authorization decision."""

    def __init__(self, allow: bool, reason: str, audit: Dict[str, Any]) -> None:
        self.allow = allow
        self.reason = reason
        self.audit = audit
        self.from_cache = False

    def __repr__(self) -> str:
        return f"OPADecision(allow={self.allow}, reason={self.reason!r})"


class OPACache:
    """Thread-safe TTL cache for OPA decisions."""

    def __init__(self, ttl_seconds: int = 10) -> None:
        self._cache: Dict[str, Tuple[OPADecision, float]] = {}
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()

    def _make_key(
        self, subject: str, service: str, resource: str, method: str
    ) -> str:
        """Generate a deterministic cache key from request parameters."""
        raw = f"{subject}:{service}:{resource}:{method}"
        return hashlib.sha256(raw.encode()).hexdigest()

    async def get(
        self, subject: str, service: str, resource: str, method: str
    ) -> Optional[OPADecision]:
        """Return cached decision if present and not expired."""
        key = self._make_key(subject, service, resource, method)
        async with self._lock:
            if key in self._cache:
                decision, cached_at = self._cache[key]
                if time.monotonic() - cached_at < self._ttl:
                    metrics.OPA_CACHE_HITS.inc()
                    decision.from_cache = True
                    return decision
                # Expired — remove entry
                del self._cache[key]
        metrics.OPA_CACHE_MISSES.inc()
        return None

    async def set(
        self,
        subject: str,
        service: str,
        resource: str,
        method: str,
        decision: OPADecision,
    ) -> None:
        """Store a decision in the cache."""
        key = self._make_key(subject, service, resource, method)
        async with self._lock:
            self._cache[key] = (decision, time.monotonic())

    async def invalidate(self) -> None:
        """Clear all cached decisions (called on policy reload)."""
        async with self._lock:
            self._cache.clear()
        logger.info("OPA decision cache cleared")


class OPAClient:
    """Async client for querying the OPA policy engine."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._cache = OPACache(ttl_seconds=self._settings.opa_cache_ttl_seconds)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Return or create the shared httpx async client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._settings.opa_url,
                timeout=httpx.Timeout(self._settings.opa_timeout_seconds),
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def authorize(
        self,
        subject: str,
        service: str,
        resource: str,
        method: str,
    ) -> OPADecision:
        """
        Query OPA for an authorization decision.

        Args:
            subject:  Client identity (CN from mTLS certificate).
            service:  Target microservice name.
            resource: Request path (e.g. "/records").
            method:   HTTP method (e.g. "GET").

        Returns:
            OPADecision with allow, reason, and audit fields.

        Raises:
            OPAError: If the OPA query fails after retries.
        """
        # Check cache first
        cached = await self._cache.get(subject, service, resource, method)
        if cached is not None:
            logger.debug(
                "OPA cache hit",
                extra={"subject": subject, "service": service, "resource": resource},
            )
            return cached

        # Build OPA input document
        opa_input = {
            "input": {
                "subject": subject,
                "service": service,
                "resource": resource,
                "method": method,
            }
        }

        start_time = time.monotonic()
        client = await self._get_client()

        try:
            response = await client.post(
                self._settings.opa_policy_path,
                content=json.dumps(opa_input),
            )
            response.raise_for_status()

        except httpx.TimeoutException as exc:
            elapsed = time.monotonic() - start_time
            logger.error(
                "OPA query timed out",
                extra={
                    "opa_url": self._settings.opa_url,
                    "elapsed_seconds": elapsed,
                    "subject": subject,
                },
            )
            # Fail-closed: deny on timeout
            return OPADecision(
                allow=False,
                reason="access denied: OPA query timeout — fail-closed",
                audit={},
            )

        except httpx.HTTPStatusError as exc:
            logger.error(
                "OPA returned error status",
                extra={
                    "status_code": exc.response.status_code,
                    "body": exc.response.text[:500],
                    "subject": subject,
                },
            )
            return OPADecision(
                allow=False,
                reason=f"access denied: OPA error {exc.response.status_code}",
                audit={},
            )

        except httpx.RequestError as exc:
            logger.error(
                "OPA connection error",
                extra={"error": str(exc), "subject": subject},
            )
            return OPADecision(
                allow=False,
                reason="access denied: OPA unreachable — fail-closed",
                audit={},
            )

        elapsed = time.monotonic() - start_time
        metrics.record_opa_latency(service, allow=True, duration_seconds=elapsed)

        # Parse OPA response
        try:
            body = response.json()
            result = body.get("result", {})
            allow: bool = result.get("allow", False)
            reason: str = result.get("reason", "no reason provided")
            audit: Dict[str, Any] = result.get("audit", {})
        except (json.JSONDecodeError, KeyError) as exc:
            logger.error("Failed to parse OPA response", extra={"error": str(exc)})
            return OPADecision(
                allow=False,
                reason="access denied: invalid OPA response",
                audit={},
            )

        decision = OPADecision(allow=allow, reason=reason, audit=audit)

        # Cache positive and negative decisions
        await self._cache.set(subject, service, resource, method, decision)

        logger.debug(
            "OPA decision",
            extra={
                "allow": allow,
                "reason": reason,
                "subject": subject,
                "service": service,
                "opa_latency_ms": round(elapsed * 1000, 3),
            },
        )

        return decision

    async def health_check(self) -> bool:
        """Check if OPA is reachable and responsive."""
        try:
            client = await self._get_client()
            response = await client.get("/health")
            return response.status_code == 200
        except Exception:
            return False

    async def invalidate_cache(self) -> None:
        """Invalidate the OPA decision cache (e.g., after policy reload)."""
        await self._cache.invalidate()


# ── Module-level singleton ─────────────────────────────────────────────────────
_opa_client: Optional[OPAClient] = None


def get_opa_client() -> OPAClient:
    """Return the module-level OPA client singleton."""
    global _opa_client
    if _opa_client is None:
        _opa_client = OPAClient()
    return _opa_client
