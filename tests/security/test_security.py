"""
tests/security/test_security.py — Security tests for the Zero Trust Gateway.
Tests: no cert, wrong cert, expired cert, wrong CN, privilege escalation.
"""
from __future__ import annotations

import base64
import datetime
import ssl
import tempfile
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# ── Helpers ────────────────────────────────────────────────────────────────────

def make_client_with_cn(cn: Optional[str], app) -> httpx.AsyncClient:
    """Build an AsyncClient that presents a given CN header (simulates mTLS)."""
    headers = {}
    if cn:
        headers["X-Client-Cert-CN"] = cn
    return httpx.AsyncClient(app=app, base_url="http://testserver", headers=headers)


# ════════════════════════════════════════════════════════════════
# NO CERTIFICATE TESTS
# ════════════════════════════════════════════════════════════════

class TestNoCertificate:
    """Requests with no client certificate must be rejected at the gateway."""

    @pytest.mark.asyncio
    async def test_no_cert_get_records_rejected(self):
        """GET /records with no cert must return 401 Unauthorized."""
        from gateway.main import app
        async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
            response = await client.get("/records")
        assert response.status_code == 401, (
            f"Expected 401 but got {response.status_code}. "
            "Gateway must enforce mTLS for all non-health endpoints."
        )

    @pytest.mark.asyncio
    async def test_no_cert_post_login_rejected(self):
        """POST /login with no cert must return 401."""
        from gateway.main import app
        async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
            response = await client.post(
                "/login", json={"username": "admin", "password": "admin123"}
            )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_no_cert_delete_rejected(self):
        """DELETE with no cert must return 401."""
        from gateway.main import app
        async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
            response = await client.delete("/records/some-id")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_no_cert_health_still_accessible(self):
        """Health endpoint must remain accessible with no cert (monitoring/probes)."""
        from gateway.main import app
        async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
            response = await client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_no_cert_returns_error_json(self):
        """401 response for missing cert must be valid JSON with 'error' key."""
        from gateway.main import app
        async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
            response = await client.get("/users")
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert data["error"] == "unauthorized"


# ════════════════════════════════════════════════════════════════
# WRONG / UNKNOWN CN TESTS
# ════════════════════════════════════════════════════════════════

class TestWrongCertificate:
    """Requests presenting an unrecognized CN must be rejected."""

    @pytest.mark.asyncio
    async def test_unknown_cn_rejected(self):
        """CN not in the allowlist must return 403 Forbidden."""
        from gateway.main import app
        async with make_client_with_cn("rogue.attacker.io", app) as client:
            response = await client.get("/records")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_spoofed_cn_rejected(self):
        """Spoofed legitimate CN pattern that doesn't match must be rejected."""
        from gateway.main import app
        # CN looks legitimate but domain is wrong
        async with make_client_with_cn("gateway.evil-domain.local", app) as client:
            response = await client.get("/records")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_empty_cn_treated_as_no_cert(self):
        """Empty string CN header must be treated as no certificate."""
        from gateway.main import app
        async with httpx.AsyncClient(
            app=app,
            base_url="http://testserver",
            headers={"X-Client-Cert-CN": ""},
        ) as client:
            response = await client.get("/records")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_wildcard_cn_not_accepted(self):
        """Wildcard CN must not bypass allowlist check."""
        from gateway.main import app
        async with make_client_with_cn("*.zerotrust.local", app) as client:
            response = await client.get("/records")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_wrong_cn_error_message_not_leaking_details(self):
        """Error response for wrong CN must not leak internal config details."""
        from gateway.main import app
        async with make_client_with_cn("hacker.bad.com", app) as client:
            response = await client.get("/records")
        body = response.text
        # Must not expose allowlist contents or internal paths
        assert "ALLOWED_CLIENT_CNS" not in body
        assert "/etc/" not in body
        assert "traceback" not in body.lower()


# ════════════════════════════════════════════════════════════════
# PRIVILEGE ESCALATION TESTS
# ════════════════════════════════════════════════════════════════

class TestPrivilegeEscalation:
    """Services must not be able to exceed their assigned roles."""

    @pytest.mark.asyncio
    async def test_reader_cannot_post(self, mock_opa_deny):
        """Service-a (reader role) must be denied POST on service-b."""
        from gateway.main import app
        # Override mock to simulate real OPA deny for role violation
        mock_opa_deny.authorize.return_value.allow = False
        mock_opa_deny.authorize.return_value.reason = (
            "access denied: subject lacks required role for this resource"
        )
        async with make_client_with_cn("service-a.zerotrust.local", app) as client:
            response = await client.post(
                "/records", json={"title": "Escalation Attempt", "content": "x"}
            )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_writer_cannot_delete(self, mock_opa_deny):
        """Gateway (writer+reader, not admin) must be denied DELETE on service-b."""
        from gateway.main import app
        mock_opa_deny.authorize.return_value.allow = False
        mock_opa_deny.authorize.return_value.reason = "access denied: subject lacks required role"
        async with make_client_with_cn("gateway.zerotrust.local", app) as client:
            response = await client.delete("/records/abc")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_non_admin_cannot_access_service_c(self, mock_opa_deny):
        """Non-admin service must be denied all service-c endpoints."""
        from gateway.main import app
        mock_opa_deny.authorize.return_value.allow = False
        mock_opa_deny.authorize.return_value.reason = (
            "access denied: service-c requires admin role"
        )
        async with make_client_with_cn("gateway.zerotrust.local", app) as client:
            response = await client.get("/users")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_non_gateway_cannot_post_login(self, mock_opa_deny):
        """Only the gateway may call POST /login on service-a."""
        from gateway.main import app
        mock_opa_deny.authorize.return_value.allow = False
        mock_opa_deny.authorize.return_value.reason = (
            "access denied: POST /login restricted to gateway service"
        )
        async with make_client_with_cn("service-b.zerotrust.local", app) as client:
            response = await client.post(
                "/login", json={"username": "admin", "password": "admin123"}
            )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_monitoring_cannot_access_data(self, mock_opa_deny):
        """Monitoring agent (monitoring role only) must be denied data endpoints."""
        from gateway.main import app
        mock_opa_deny.authorize.return_value.allow = False
        mock_opa_deny.authorize.return_value.reason = (
            "access denied: subject lacks required role for this resource"
        )
        async with make_client_with_cn("monitoring.zerotrust.local", app) as client:
            response = await client.get("/records")
        assert response.status_code == 403


# ════════════════════════════════════════════════════════════════
# INJECTION / BYPASS ATTEMPTS
# ════════════════════════════════════════════════════════════════

class TestInjectionAttempts:
    """Test that malformed inputs do not bypass security controls."""

    @pytest.mark.asyncio
    async def test_null_bytes_in_cn_rejected(self):
        """CN with null bytes must not bypass allowlist check."""
        from gateway.main import app
        async with httpx.AsyncClient(
            app=app,
            base_url="http://testserver",
            headers={"X-Client-Cert-CN": "gateway.zerotrust.local\x00evil"},
        ) as client:
            response = await client.get("/records")
        # Null byte makes CN not match allowlist
        assert response.status_code in {401, 403}

    @pytest.mark.asyncio
    async def test_header_injection_in_cn_rejected(self):
        """CN with newline characters must not inject headers."""
        from gateway.main import app
        async with httpx.AsyncClient(
            app=app,
            base_url="http://testserver",
            headers={"X-Client-Cert-CN": "gateway.zerotrust.local\r\nX-Admin: true"},
        ) as client:
            response = await client.get("/records")
        assert response.status_code in {401, 403}

    @pytest.mark.asyncio
    async def test_oversized_cn_rejected(self):
        """CN that is absurdly long must not crash or bypass allowlist."""
        from gateway.main import app
        long_cn = "a" * 5000 + ".zerotrust.local"
        async with make_client_with_cn(long_cn, app) as client:
            response = await client.get("/records")
        assert response.status_code in {401, 403}

    @pytest.mark.asyncio
    async def test_sql_injection_in_path_sanitized(self, mock_opa_allow):
        """SQL injection patterns in path must be handled gracefully."""
        from gateway.main import app
        async with make_client_with_cn("gateway.zerotrust.local", app) as client:
            # This should hit the forwarder, which will return 502 (service not running)
            # but must NOT return 500 or expose stack traces
            response = await client.get("/records/'; DROP TABLE records; --")
        assert response.status_code not in {500}

    @pytest.mark.asyncio
    async def test_path_traversal_rejected(self, mock_opa_allow):
        """Path traversal attempts must not expose internal files."""
        from gateway.main import app
        async with make_client_with_cn("gateway.zerotrust.local", app) as client:
            response = await client.get("/records/../../etc/passwd")
        assert response.status_code not in {500}
        if response.status_code == 200:
            assert "root:" not in response.text


# ════════════════════════════════════════════════════════════════
# OPA FAIL-CLOSED TESTS
# ════════════════════════════════════════════════════════════════

class TestOPAFailClosed:
    """When OPA is unreachable, the gateway must deny all requests (fail-closed)."""

    @pytest.mark.asyncio
    async def test_opa_timeout_denies_request(self):
        """OPA timeout must result in 403 (fail-closed, not 500)."""
        from gateway.main import app
        from gateway.policy import OPADecision

        timeout_decision = OPADecision(
            allow=False,
            reason="access denied: OPA query timeout — fail-closed",
            audit={},
        )

        with patch("gateway.policy.get_opa_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.authorize = AsyncMock(return_value=timeout_decision)
            mock_get.return_value = mock_client

            async with make_client_with_cn("gateway.zerotrust.local", app) as client:
                response = await client.get("/records")

        assert response.status_code == 403
        assert "timeout" in response.json().get("message", "").lower()

    @pytest.mark.asyncio
    async def test_opa_unreachable_denies_request(self):
        """OPA connection error must result in 403 (not 500 or 200)."""
        from gateway.main import app
        from gateway.policy import OPADecision

        unreachable_decision = OPADecision(
            allow=False,
            reason="access denied: OPA unreachable — fail-closed",
            audit={},
        )

        with patch("gateway.policy.get_opa_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.authorize = AsyncMock(return_value=unreachable_decision)
            mock_get.return_value = mock_client

            async with make_client_with_cn("gateway.zerotrust.local", app) as client:
                response = await client.get("/records")

        assert response.status_code == 403
