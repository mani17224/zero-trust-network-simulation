"""
models.py — Pydantic models for Service C (Admin Service).
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class User(BaseModel):
    """A user managed by the Admin Service."""
    id: str
    username: str
    email: str
    role: str
    created_at: datetime
    active: bool = True


class CreateUserRequest(BaseModel):
    """Request body for creating a new user."""
    username: str = Field(..., min_length=3, max_length=64)
    email: str = Field(..., description="User email address")
    role: str = Field(..., description="Assigned role: reader, writer, admin, monitoring")


class AuditLogEntry(BaseModel):
    """A single audit log entry."""
    id: str
    timestamp: datetime
    subject: str = Field(..., description="Caller service/user CN")
    target_service: str
    resource: str
    method: str
    decision: str = Field(..., description="allow or deny")
    reason: str
    latency_ms: float
    request_id: str
