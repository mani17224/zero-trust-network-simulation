"""
conftest.py — Shared pytest fixtures for Zero Trust test suite.
Provides: cert loading, mock OPA, async test clients, and test data.
"""
from __future__ import annotations

import json
import os
import ssl
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio

# ── Project root ───────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
CERTS_DIR    = PROJECT_ROOT / "certs"

# ── Cert file helpers ──────────────────────────────────────────────────────────

def cert_path(service: str, filename: str) -> str:
    """Return the path to a cert file for a given service."""
    return str(CERTS_DIR / service / filename)


def certs_exist(service: str) -> bool:
    """Check whether real cert files exist for a service."""
    required = ["cert.pem", "key.pem", "ca_chain.pem"]
    return all((CERTS_DIR / service / f).exists() for f in required)


# ── SSL context factory ────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def gateway_ssl_ctx() -> ssl.SSLContext | None:
    """
    Create an SSL context using the gateway client certificate for mTLS tests.
    Returns None if cert files are not present (unit tests run without certs).
    """
    if not certs_exist("gateway"):
        return None
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_cert_chain(
        certfile=cert_path("gateway", "cert.pem"),
        keyfile=cert_path("gateway", "key.pem"),
    )
    ctx.load_verify_locations(cafile=cert_path("gateway", "ca_chain.pem"))
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


@pytest.fixture(scope="session")
def monitoring_ssl_ctx() -> ssl.SSLContext | None:
    """SSL context for monitoring-agent client certificate."""
    if not certs_exist("monitoring-agent"):
        return None
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_cert_chain(
        certfile=cert_path("monitoring-agent", "cert.pem"),
        keyfile=cert_path("monitoring-agent", "key.pem"),
    )
    ctx.load_verify_locations(cafile=cert_path("monitoring-agent", "ca_chain.pem"))
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


# ── Mock OPA client ────────────────────────────────────────────────────────────

@pytest.fixture
def mock_opa_allow():
    """
    Mock OPA client that always returns allow=True.
    Patches the gateway's OPA client for unit tests.
    """
    mock_decision = MagicMock()
    mock_decision.allow = True
    mock_decision.reason = "test: always allow"
    mock_decision.audit = {}

    mock_client = AsyncMock()
    mock_client.authorize = AsyncMock(return_value=mock_decision)
    mock_client.health_check = AsyncMock(return_value=True)

    with patch("gateway.policy.get_opa_client", return_value=mock_client):
        yield mock_client


@pytest.fixture
def mock_opa_deny():
    """
    Mock OPA client that always returns allow=False.
    Used to test 403 denial paths.
    """
    mock_decision = MagicMock()
    mock_decision.allow = False
    mock_decision.reason = "test: always deny"
    mock_decision.audit = {}

    mock_client = AsyncMock()
    mock_client.authorize = AsyncMock(return_value=mock_decision)
    mock_client.health_check = AsyncMock(return_value=True)

    with patch("gateway.policy.get_opa_client", return_value=mock_client):
        yield mock_client


# ── Gateway test client ────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def gateway_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    Async httpx client pointed at the running gateway.
    Uses gateway client certificate for mTLS.
    """
    from gateway.main import app
    async with httpx.AsyncClient(
        app=app,
        base_url="http://testserver",
        headers={"X-Client-Cert-CN": "gateway.zerotrust.local"},
    ) as client:
        yield client


@pytest_asyncio.fixture
async def unauthed_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Async client with NO client certificate (for rejection tests)."""
    from gateway.main import app
    async with httpx.AsyncClient(
        app=app,
        base_url="http://testserver",
    ) as client:
        yield client


@pytest_asyncio.fixture
async def service_a_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Test client for Service A (Auth Service)."""
    import sys
    sys.path.insert(0, str(PROJECT_ROOT / "services" / "service-a"))
    from main import app
    async with httpx.AsyncClient(
        app=app,
        base_url="http://testserver",
        headers={"X-Client-Cert-CN": "gateway.zerotrust.local"},
    ) as client:
        yield client


@pytest_asyncio.fixture
async def service_b_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Test client for Service B (Data Service)."""
    import sys
    sys.path.insert(0, str(PROJECT_ROOT / "services" / "service-b"))
    from main import app
    async with httpx.AsyncClient(
        app=app,
        base_url="http://testserver",
        headers={"X-Client-Cert-CN": "gateway.zerotrust.local"},
    ) as client:
        yield client


@pytest_asyncio.fixture
async def service_c_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Test client for Service C (Admin Service)."""
    import sys
    sys.path.insert(0, str(PROJECT_ROOT / "services" / "service-c"))
    from main import app
    async with httpx.AsyncClient(
        app=app,
        base_url="http://testserver",
        headers={"X-Client-Cert-CN": "admin-service.zerotrust.local"},
    ) as client:
        yield client


# ── Test data fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def opa_input_gateway_records_get() -> dict:
    """Standard OPA input: gateway GET /records on service-b."""
    return {
        "subject": "gateway",
        "service": "service-b",
        "resource": "/records",
        "method": "GET",
    }


@pytest.fixture
def opa_input_unauthorized() -> dict:
    """OPA input for an unknown/unauthorized subject."""
    return {
        "subject": "evil-service",
        "service": "service-c",
        "resource": "/users",
        "method": "DELETE",
    }


@pytest.fixture
def valid_login_body() -> dict:
    """Valid login credentials for service-a tests."""
    return {"username": "alice", "password": "alice456"}


@pytest.fixture
def invalid_login_body() -> dict:
    """Invalid login credentials that should return 401."""
    return {"username": "alice", "password": "wrong-password"}
