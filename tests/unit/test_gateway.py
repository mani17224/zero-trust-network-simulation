"""
tests/unit/test_gateway.py — Unit tests for the Zero Trust API Gateway.
Tests middleware, OPA client, forwarder logic, and route handlers.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio


# ── Gateway middleware tests ───────────────────────────────────────────────────

class TestHealthEndpoint:
    """Tests for the /health endpoint (no auth required)."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, gateway_client):
        """Health endpoint must return 200 without any client certificate."""
        response = await gateway_client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_response_schema(self, gateway_client):
        """Health response must contain status, service, and version fields."""
        response = await gateway_client.get("/health")
        data = response.json()
        assert "status" in data
        assert "service" in data
        assert "version" in data

    @pytest.mark.asyncio
    async def test_health_status_is_healthy(self, gateway_client, mock_opa_allow):
        """Health status field must be 'healthy'."""
        response = await gateway_client.get("/health")
        assert response.json()["status"] == "healthy"


class TestMTLSEnforcement:
    """Tests for mTLS certificate enforcement middleware."""

    @pytest.mark.asyncio
    async def test_request_without_cert_returns_401(self, unauthed_client):
        """Requests with no client certificate must be rejected with 401."""
        response = await unauthed_client.get("/records")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_request_with_unknown_cn_returns_403(self):
        """Requests with a CN not in the allowlist must be rejected with 403."""
        from gateway.main import app
        async with httpx.AsyncClient(
            app=app,
            base_url="http://testserver",
            headers={"X-Client-Cert-CN": "unknown-attacker.evil.com"},
        ) as client:
            response = await client.get("/records")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_valid_cert_cn_passes_mtls(self, gateway_client, mock_opa_allow):
        """Request with known CN must pass mTLS check and reach OPA."""
        response = await gateway_client.get("/records")
        # OPA mock allows, so this should not be 401/403 from mTLS
        assert response.status_code not in {401}

    @pytest.mark.asyncio
    async def test_401_response_contains_error_field(self, unauthed_client):
        """401 response body must contain an 'error' field."""
        response = await unauthed_client.get("/records")
        data = response.json()
        assert "error" in data

    @pytest.mark.asyncio
    async def test_403_response_contains_message(self):
        """403 response body must contain a 'message' field."""
        from gateway.main import app
        async with httpx.AsyncClient(
            app=app,
            base_url="http://testserver",
            headers={"X-Client-Cert-CN": "bad.actor.com"},
        ) as client:
            response = await client.get("/records")
        assert "message" in response.json()


class TestOPAMiddleware:
    """Tests for OPA authorization middleware."""

    @pytest.mark.asyncio
    async def test_opa_deny_returns_403(self, gateway_client, mock_opa_deny):
        """When OPA denies a request, gateway must return 403."""
        response = await gateway_client.get("/records")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_opa_deny_includes_reason(self, gateway_client, mock_opa_deny):
        """403 response from OPA denial must include the deny reason."""
        response = await gateway_client.get("/records")
        data = response.json()
        assert "message" in data
        assert data["message"] == "test: always deny"

    @pytest.mark.asyncio
    async def test_opa_deny_includes_request_id(self, gateway_client, mock_opa_deny):
        """403 response must include a request_id for tracing."""
        response = await gateway_client.get("/records")
        assert "request_id" in response.json()

    @pytest.mark.asyncio
    async def test_health_bypasses_opa(self, gateway_client, mock_opa_deny):
        """Health endpoint must succeed even when OPA would deny."""
        response = await gateway_client.get("/health")
        assert response.status_code == 200
        # OPA deny mock should NOT have been called for /health
        mock_opa_deny.authorize.assert_not_called()


class TestCNNormalization:
    """Tests for the normalize_subject helper function."""

    def test_normalize_full_cn(self):
        """Full CN 'gateway.zerotrust.local' should normalize to 'gateway'."""
        from gateway.main import normalize_subject
        assert normalize_subject("gateway.zerotrust.local") == "gateway"

    def test_normalize_short_name(self):
        """Short name 'gateway' should remain 'gateway'."""
        from gateway.main import normalize_subject
        assert normalize_subject("gateway") == "gateway"

    def test_normalize_none_returns_empty(self):
        """None input should return empty string."""
        from gateway.main import normalize_subject
        assert normalize_subject(None) == ""


class TestMetricsEndpoint:
    """Tests for the /metrics endpoint."""

    @pytest.mark.asyncio
    async def test_metrics_endpoint_accessible(self, gateway_client):
        """Metrics endpoint must be reachable."""
        response = await gateway_client.get("/metrics")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_metrics_content_type(self, gateway_client):
        """Metrics response must use Prometheus text format content type."""
        response = await gateway_client.get("/metrics")
        assert "text/plain" in response.headers.get("content-type", "")


class TestForwarderServiceResolution:
    """Tests for the service resolution logic in forwarder.py."""

    def test_records_resolves_to_service_b(self):
        """Path /records should resolve to service-b."""
        from gateway.forwarder import resolve_service
        assert resolve_service("/records") == "service-b"

    def test_login_resolves_to_service_a(self):
        """Path /login should resolve to service-a."""
        from gateway.forwarder import resolve_service
        assert resolve_service("/login") == "service-a"

    def test_users_resolves_to_service_c(self):
        """Path /users should resolve to service-c."""
        from gateway.forwarder import resolve_service
        assert resolve_service("/users") == "service-c"

    def test_unknown_path_returns_none(self):
        """Unrecognized path should return None."""
        from gateway.forwarder import resolve_service
        assert resolve_service("/unknown-path") is None

    def test_nested_records_path_resolves(self):
        """Path /records/123 should resolve to service-b."""
        from gateway.forwarder import resolve_service
        assert resolve_service("/records/abc-123") == "service-b"


class TestOPAClientCaching:
    """Tests for the OPA decision cache."""

    @pytest.mark.asyncio
    async def test_cache_returns_same_decision(self):
        """Second identical query must return cached decision without network call."""
        from gateway.policy import OPAClient

        client = OPAClient()
        mock_decision = MagicMock()
        mock_decision.allow = True
        mock_decision.reason = "cached"
        mock_decision.from_cache = False
        mock_decision.audit = {}

        with patch.object(client, "_get_client") as mock_http:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "result": {"allow": True, "reason": "cached", "audit": {}}
            }
            mock_response.raise_for_status = MagicMock()
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(return_value=mock_response)
            mock_http.return_value = mock_http_client

            # First call — hits network
            d1 = await client.authorize("gateway", "service-b", "/records", "GET")
            # Second call — should hit cache
            d2 = await client.authorize("gateway", "service-b", "/records", "GET")

        assert d1.allow is True
        assert d2.allow is True
        # Only one actual HTTP call made
        assert mock_http_client.post.call_count == 1
