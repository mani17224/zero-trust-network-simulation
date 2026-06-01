"""
models.py — Pydantic models for Service A (Auth Service).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    """Credentials for user login."""
    username: str = Field(..., min_length=1, max_length=100, description="Username")
    password: str = Field(..., min_length=1, description="Password (plaintext for demo)")


class LoginResponse(BaseModel):
    """Successful login response containing a signed JWT."""
    access_token: str = Field(..., description="Signed JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token lifetime in seconds")
    subject: str = Field(..., description="Authenticated username")


class VerifyResponse(BaseModel):
    """JWT verification response."""
    valid: bool = Field(..., description="Whether the token is valid")
    subject: str = Field(default="", description="Token subject (username)")
    expires_at: Optional[datetime] = Field(default=None, description="Token expiry timestamp")
    error: Optional[str] = Field(default=None, description="Validation error if invalid")


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    message: str
    request_id: Optional[str] = None


class HealthResponse(BaseModel):
    """Service health status."""
    status: str
    service: str
    version: str
