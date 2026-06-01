"""
tests/integration/test_mtls.py — Integration tests for mTLS handshake validation.
Requires running services and real certificates. Skipped if certs not present.
"""
from __future__ import annotations

import pytest
import httpx

GATEWAY_URL   = "https://localhost:8000"
SERVICE_A_URL = "https://localhost:8001"
SERVICE_B_URL = "https://localhost:8002"
SERVICE_C_URL = "https://localhost:8003"

pytestmark = pytest.mark.integration


def make_mtls_client(service: str, target_url: str, ca_file: str, timeout: float = 10.0):
    """
    Create an httpx client with mTLS configuration for integration tests.

    Args:
        service:    Name of the client service (e.g. 'gateway').
        target_url: Base URL of the target service.
        ca_file:    Path to CA chain PEM for server cert verification.
        timeout:    Request timeout in seconds.

    Returns:
        Configured httpx.Client.
    """
    return httpx.Client(
        base_url=target_url,
        cert=(f"certs/{service}/cert.pem", f"certs/{service}/key.pem"),
        verify=ca_file,
        timeout=timeout,
    )


@pytest.mark.skipif(
    not __import__("pathlib").Path("certs/gateway/cert.pem").exists(),
    reason="Real certificates not present — run certs/issue_certs.sh first",
)
class TestMTLSHandshake:
    """Full mTLS handshake tests between services."""

    def test_gateway_to_gateway_health(self, gateway_ssl_ctx):
        """Gateway can call its own /health with mTLS."""
        if gateway_ssl_ctx is None:
            pytest.skip("Gateway cert not present")
        with make_mtls_client("gateway", GATEWAY_URL, "certs/gateway/ca_chain.pem") as client:
            response = client.get("/health")
        assert response.status_code == 200

    def test_gateway_to_service_a(self, gateway_ssl_ctx):
        """Gateway can reach Service A /health with mTLS."""
        if gateway_ssl_ctx is None:
            pytest.skip("Gateway cert not present")
        with make_mtls_client("gateway", SERVICE_A_URL, "certs/gateway/ca_chain.pem") as client:
            response = client.get("/health")
        assert response.status_code == 200

    def test_gateway_to_service_b(self, gateway_ssl_ctx):
        """Gateway can reach Service B /health with mTLS."""
        if gateway_ssl_ctx is None:
            pytest.skip("Gateway cert not present")
        with make_mtls_client("gateway", SERVICE_B_URL, "certs/gateway/ca_chain.pem") as client:
            response = client.get("/health")
        assert response.status_code == 200

    def test_gateway_to_service_c(self, gateway_ssl_ctx):
        """Gateway can reach Service C /health with mTLS."""
        if gateway_ssl_ctx is None:
            pytest.skip("Gateway cert not present")
        with make_mtls_client("gateway", SERVICE_C_URL, "certs/gateway/ca_chain.pem") as client:
            response = client.get("/health")
        assert response.status_code == 200

    def test_no_cert_rejected(self):
        """Connection without client cert must be refused (SSL error or 401)."""
        try:
            with httpx.Client(base_url=GATEWAY_URL, verify=False, timeout=5.0) as client:
                response = client.get("/records")
            assert response.status_code in {400, 401, 403}
        except httpx.ConnectError:
            pass  # SSL handshake failure is also acceptable

    def test_monitoring_agent_cert_accepted(self, monitoring_ssl_ctx):
        """Monitoring agent cert must be accepted by the gateway."""
        if monitoring_ssl_ctx is None:
            pytest.skip("Monitoring agent cert not present")
        with make_mtls_client(
            "monitoring-agent", GATEWAY_URL, "certs/monitoring-agent/ca_chain.pem"
        ) as client:
            response = client.get("/health")
        assert response.status_code == 200
