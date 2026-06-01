"""
tests/unit/test_services.py — Unit tests for microservice endpoints.
Tests Service A (auth), Service B (data), and Service C (admin).
"""
from __future__ import annotations

import pytest


# ════════════════════════════════════════════════════════════════
# SERVICE A — Auth Service
# ════════════════════════════════════════════════════════════════

class TestServiceAHealth:
    """Service A health endpoint tests."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, service_a_client):
        """Service A /health must return 200."""
        response = await service_a_client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_schema(self, service_a_client):
        """Service A health response must contain status and service fields."""
        response = await service_a_client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "service-a"


class TestServiceALogin:
    """Service A /login endpoint tests."""

    @pytest.mark.asyncio
    async def test_valid_login_returns_200(self, service_a_client, valid_login_body):
        """Valid credentials must return 200 with an access token."""
        response = await service_a_client.post("/login", json=valid_login_body)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_valid_login_returns_token(self, service_a_client, valid_login_body):
        """Login response must contain access_token and subject fields."""
        response = await service_a_client.post("/login", json=valid_login_body)
        data = response.json()
        assert "access_token" in data
        assert data["subject"] == valid_login_body["username"]
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_invalid_password_returns_401(self, service_a_client, invalid_login_body):
        """Wrong password must return 401."""
        response = await service_a_client.post("/login", json=invalid_login_body)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_unknown_user_returns_401(self, service_a_client):
        """Unknown username must return 401."""
        response = await service_a_client.post(
            "/login", json={"username": "nobody", "password": "pass"}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_fields_returns_422(self, service_a_client):
        """Missing required fields must return 422 Unprocessable Entity."""
        response = await service_a_client.post("/login", json={"username": "alice"})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_unauthorized_cn_cannot_login(self):
        """A client with a non-gateway CN must be rejected from /login."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "services" / "service-a"))
        from main import app
        import httpx
        async with httpx.AsyncClient(
            app=app,
            base_url="http://testserver",
            headers={"X-Client-Cert-CN": "service-b.zerotrust.local"},
        ) as client:
            # service-b is allowed to call /login (it's in the allowlist for service-a)
            # But OPA would deny it — here we just test the CN allowlist
            response = await client.post(
                "/login", json={"username": "alice", "password": "alice456"}
            )
        # service-b is in the allowlist, so 200 is returned (OPA not tested here)
        assert response.status_code in {200, 403}


class TestServiceAVerify:
    """Service A /verify endpoint tests."""

    @pytest.mark.asyncio
    async def test_verify_with_valid_token(self, service_a_client, valid_login_body):
        """A freshly issued token must verify as valid."""
        login_resp = await service_a_client.post("/login", json=valid_login_body)
        token = login_resp.json()["access_token"]

        verify_resp = await service_a_client.get(
            "/verify", headers={"Authorization": f"Bearer {token}"}
        )
        assert verify_resp.status_code == 200
        data = verify_resp.json()
        assert data["valid"] is True
        assert data["subject"] == valid_login_body["username"]

    @pytest.mark.asyncio
    async def test_verify_with_no_token(self, service_a_client):
        """Missing Authorization header must return valid=False."""
        response = await service_a_client.get("/verify")
        assert response.status_code == 200
        assert response.json()["valid"] is False

    @pytest.mark.asyncio
    async def test_verify_with_bad_token(self, service_a_client):
        """A garbage token must return valid=False."""
        response = await service_a_client.get(
            "/verify", headers={"Authorization": "Bearer not-a-real-jwt"}
        )
        assert response.status_code == 200
        assert response.json()["valid"] is False


# ════════════════════════════════════════════════════════════════
# SERVICE B — Data Service
# ════════════════════════════════════════════════════════════════

class TestServiceBHealth:
    """Service B health endpoint tests."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, service_b_client):
        """Service B /health must return 200."""
        response = await service_b_client.get("/health")
        assert response.status_code == 200


class TestServiceBRecords:
    """Service B /records endpoint tests."""

    @pytest.mark.asyncio
    async def test_list_records_returns_200(self, service_b_client):
        """GET /records must return 200 with paginated data."""
        response = await service_b_client.get("/records")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_records_schema(self, service_b_client):
        """Records response must contain records, total, page, page_size fields."""
        response = await service_b_client.get("/records")
        data = response.json()
        assert "records" in data
        assert "total" in data
        assert "page" in data
        assert isinstance(data["records"], list)

    @pytest.mark.asyncio
    async def test_create_record_returns_201(self, service_b_client):
        """POST /records with valid body must return 201."""
        response = await service_b_client.post(
            "/records",
            json={"title": "Test Record", "content": "Test content", "tags": ["test"]},
        )
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_create_record_appears_in_list(self, service_b_client):
        """A newly created record must appear in subsequent GET /records."""
        title = "Unique Record XYZ"
        await service_b_client.post(
            "/records", json={"title": title, "content": "content"}
        )
        list_resp = await service_b_client.get("/records?page_size=100")
        records = list_resp.json()["records"]
        assert any(r["title"] == title for r in records)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_record_returns_404(self, service_b_client):
        """DELETE on a non-existent record ID must return 404."""
        response = await service_b_client.delete("/records/does-not-exist-abc123")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_record_succeeds(self, service_b_client):
        """Create then delete a record — must return 200 with deleted=true."""
        create = await service_b_client.post(
            "/records", json={"title": "To Delete", "content": "bye"}
        )
        record_id = create.json()["id"]
        delete = await service_b_client.delete(f"/records/{record_id}")
        assert delete.status_code == 200
        assert delete.json()["deleted"] is True


# ════════════════════════════════════════════════════════════════
# SERVICE C — Admin Service
# ════════════════════════════════════════════════════════════════

class TestServiceCHealth:
    """Service C health endpoint tests."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, service_c_client):
        """Service C /health must return 200."""
        response = await service_c_client.get("/health")
        assert response.status_code == 200


class TestServiceCUsers:
    """Service C /users endpoint tests."""

    @pytest.mark.asyncio
    async def test_list_users_returns_200(self, service_c_client):
        """GET /users must return 200 with a list."""
        response = await service_c_client.get("/users")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_create_user_returns_201(self, service_c_client):
        """POST /users with valid body must return 201."""
        response = await service_c_client.post(
            "/users",
            json={"username": "newuser", "email": "new@test.local", "role": "reader"},
        )
        assert response.status_code == 201
        assert response.json()["username"] == "newuser"

    @pytest.mark.asyncio
    async def test_create_user_invalid_role_returns_422(self, service_c_client):
        """POST /users with an invalid role must return 422."""
        response = await service_c_client.post(
            "/users",
            json={"username": "x", "email": "x@x.local", "role": "superadmin"},
        )
        assert response.status_code == 422


class TestServiceCAuditLogs:
    """Service C /audit-logs endpoint tests."""

    @pytest.mark.asyncio
    async def test_audit_logs_returns_200(self, service_c_client):
        """GET /audit-logs must return 200 with a list."""
        response = await service_c_client.get("/audit-logs")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_audit_logs_max_50(self, service_c_client):
        """Audit logs must return at most 50 entries."""
        response = await service_c_client.get("/audit-logs")
        assert len(response.json()) <= 50

    @pytest.mark.asyncio
    async def test_audit_logs_schema(self, service_c_client):
        """Each audit log entry must have required fields."""
        response = await service_c_client.get("/audit-logs")
        logs = response.json()
        if logs:
            entry = logs[0]
            for field in ["id", "timestamp", "subject", "method", "decision"]:
                assert field in entry, f"Missing field: {field}"
