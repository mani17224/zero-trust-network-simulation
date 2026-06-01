"""
routes.py — Admin Service routes: /users and /audit-logs.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List
import random

from fastapi import APIRouter, Depends, HTTPException, Request, status

from models import AuditLogEntry, CreateUserRequest, User
from auth import verify_client_cn

router = APIRouter()

# In-memory stores
_USERS: Dict[str, User] = {}
_AUDIT_LOGS: List[AuditLogEntry] = []


def _seed_data() -> None:
    """Seed demo users and audit log entries."""
    demo_users = [
        ("alice", "alice@zerotrust.local", "admin"),
        ("bob", "bob@zerotrust.local", "writer"),
        ("carol", "carol@zerotrust.local", "reader"),
        ("monitor", "monitor@zerotrust.local", "monitoring"),
    ]
    for username, email, role in demo_users:
        uid = str(uuid.uuid4())
        _USERS[uid] = User(
            id=uid, username=username, email=email, role=role,
            created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30)),
        )

    services = ["gateway", "service-a", "service-b", "service-c", "monitoring-agent"]
    resources = ["/records", "/users", "/login", "/verify", "/metrics", "/audit-logs"]
    methods = ["GET", "POST", "DELETE"]
    decisions = ["allow", "allow", "allow", "deny"]  # 75% allow rate

    for i in range(50):
        entry_id = str(uuid.uuid4())
        decision = random.choice(decisions)
        _AUDIT_LOGS.append(AuditLogEntry(
            id=entry_id,
            timestamp=datetime.now(timezone.utc) - timedelta(minutes=random.randint(0, 1440)),
            subject=random.choice(services),
            target_service=random.choice(["service-a", "service-b", "service-c"]),
            resource=random.choice(resources),
            method=random.choice(methods),
            decision=decision,
            reason="allowed by policy" if decision == "allow" else "insufficient role",
            latency_ms=round(random.uniform(0.5, 45.0), 2),
            request_id=str(uuid.uuid4()),
        ))

    _AUDIT_LOGS.sort(key=lambda e: e.timestamp, reverse=True)


_seed_data()


@router.get("/users", response_model=List[User], summary="List all users")
async def list_users(
    request: Request,
    client_cn: str = Depends(verify_client_cn),
) -> List[User]:
    """
    Return all users. Requires admin role.

    Args:
        request:    Incoming request.
        client_cn:  Verified admin CN.

    Returns:
        List of all User objects.
    """
    return list(_USERS.values())


@router.post(
    "/users",
    response_model=User,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
)
async def create_user(
    body: CreateUserRequest,
    request: Request,
    client_cn: str = Depends(verify_client_cn),
) -> User:
    """
    Create a new user. Requires admin role.

    Args:
        body:       New user data.
        client_cn:  Verified admin CN.

    Returns:
        Created User object.
    """
    valid_roles = {"reader", "writer", "admin", "monitoring"}
    if body.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid_role", "message": f"Role must be one of {valid_roles}"},
        )

    uid = str(uuid.uuid4())
    user = User(
        id=uid,
        username=body.username,
        email=body.email,
        role=body.role,
        created_at=datetime.now(timezone.utc),
    )
    _USERS[uid] = user

    # Record audit log entry for this admin action
    _AUDIT_LOGS.insert(0, AuditLogEntry(
        id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc),
        subject=client_cn.split(".")[0],
        target_service="service-c",
        resource="/users",
        method="POST",
        decision="allow",
        reason="admin action: user created",
        latency_ms=0.0,
        request_id=request.headers.get("X-Request-ID", str(uuid.uuid4())),
    ))

    return user


@router.get(
    "/audit-logs",
    response_model=List[AuditLogEntry],
    summary="Return last 50 audit log entries",
)
async def get_audit_logs(
    request: Request,
    client_cn: str = Depends(verify_client_cn),
) -> List[AuditLogEntry]:
    """
    Return the 50 most recent audit log entries. Requires admin role.

    Args:
        request:    Incoming request.
        client_cn:  Verified admin CN.

    Returns:
        List of AuditLogEntry objects, newest first.
    """
    return _AUDIT_LOGS[:50]
