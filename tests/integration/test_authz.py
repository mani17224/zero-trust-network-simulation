"""
tests/integration/test_authz.py — Integration tests for OPA authorization scenarios.
Tests allow and deny paths through the gateway with real OPA evaluation.
"""
from __future__ import annotations

import pytest
import httpx

pytestmark = pytest.mark.integration

GATEWAY_URL = "http://localhost:8000"


def gateway_client_with_cn(cn: str) -> httpx.Client:
    """Create an httpx client that identifies itself with the given CN header."""
    return httpx.Client(
        base_url=GATEWAY_URL,
        headers={"X-Client-Cert-CN": cn},
        timeout=10.0,
    )


@pytest.mark.skipif(
    True,  # Set to False when running against live stack
    reason="Integration tests require running Docker stack — run with: make test-integration",
)
class TestAuthorizationAllowScenarios:
    """Allow path tests: valid subject + correct role → request reaches service."""

    def test_gateway_get_records_allowed(self):
        """Gateway (writer+reader) must be allowed to GET /records on service-b."""
        with gateway_client_with_cn("gateway.zerotrust.local") as client:
            response = client.get("/records")
        assert response.status_code == 200

    def test_gateway_post_records_allowed(self):
        """Gateway (writer) must be allowed to POST /records on service-b."""
        with gateway_client_with_cn("gateway.zerotrust.local") as client:
            response = client.post(
                "/records", json={"title": "Auth Test", "content": "content"}
            )
        assert response.status_code == 201

    def test_service_a_get_records_allowed(self):
        """Service-a (reader) must be allowed to GET /records."""
        with gateway_client_with_cn("service-a.zerotrust.local") as client:
            response = client.get("/records")
        assert response.status_code == 200

    def test_monitoring_agent_get_metrics_allowed(self):
        """Monitoring agent (monitoring role) must be allowed to GET /metrics."""
        with gateway_client_with_cn("monitoring.zerotrust.local") as client:
            response = client.get("/metrics")
        assert response.status_code == 200


@pytest.mark.skipif(
    True,
    reason="Integration tests require running Docker stack",
)
class TestAuthorizationDenyScenarios:
    """Deny path tests: wrong role/subject → 403 response."""

    def test_service_a_cannot_post_records(self):
        """Service-a (reader only) must be denied POST /records."""
        with gateway_client_with_cn("service-a.zerotrust.local") as client:
            response = client.post(
                "/records", json={"title": "Illegal Write", "content": "x"}
            )
        assert response.status_code == 403

    def test_gateway_cannot_delete_records(self):
        """Gateway (writer+reader, not admin) must be denied DELETE /records."""
        with gateway_client_with_cn("gateway.zerotrust.local") as client:
            response = client.delete("/records/some-id")
        assert response.status_code == 403

    def test_non_admin_cannot_access_service_c(self):
        """Non-admin service must be denied access to service-c /users."""
        with gateway_client_with_cn("service-b.zerotrust.local") as client:
            response = client.get("/users")
        assert response.status_code == 403

    def test_unknown_subject_denied(self):
        """An unregistered service CN must be denied all requests."""
        with gateway_client_with_cn("rogue.service.local") as client:
            response = client.get("/records")
        assert response.status_code == 403

    def test_non_gateway_cannot_post_login(self):
        """Only gateway may POST /login — service-b must be denied."""
        with gateway_client_with_cn("service-b.zerotrust.local") as client:
            response = client.post(
                "/login", json={"username": "alice", "password": "alice456"}
            )
        assert response.status_code == 403

    def test_deny_response_includes_reason(self):
        """403 response must include a human-readable reason from OPA."""
        with gateway_client_with_cn("service-a.zerotrust.local") as client:
            response = client.post(
                "/records", json={"title": "x", "content": "x"}
            )
        data = response.json()
        assert "message" in data
        assert len(data["message"]) > 0
