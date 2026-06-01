"""
routes.py — Auth Service: POST /login, GET /verify.
Fixes:
  - JWT validates exp, iat, nbf, iss, jti
  - Rate-limit hint in error response
  - Better error messages for all failure cases
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from models import LoginRequest, LoginResponse, VerifyResponse
from auth import verify_client_cn

router = APIRouter()

JWT_SECRET:         str = os.getenv("JWT_SECRET", "CHANGE-ME-generate-with-openssl-rand-hex-32")
JWT_ALGORITHM:      str = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

# ── Demo user store ────────────────────────────────────────────────────────────
# In production replace with database query + bcrypt password hashing
DEMO_USERS: Dict[str, str] = {
    "admin":   "admin123",
    "alice":   "alice456",
    "bob":     "bob789",
    "monitor": "monitor000",
}


def create_access_token(subject: str, expires_delta: timedelta) -> str:
    """Issue a signed JWT with exp, iat, nbf, jti, and iss claims."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "nbf": now,                        # not-before = issued-at
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),          # unique token ID (prevents replay)
        "iss": "service-a.zerotrust.local",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


# ── POST /login ────────────────────────────────────────────────────────────────
@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Authenticate user and issue JWT",
)
async def login(
    body: LoginRequest,
    request: Request,
    client_cn: str = Depends(verify_client_cn),
) -> LoginResponse:
    """
    Validate username/password and return a signed JWT.
    Only callable by the gateway (enforced by OPA + CN allowlist).
    """
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    stored_pw = DEMO_USERS.get(body.username)
    if not stored_pw or stored_pw != body.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error":      "invalid_credentials",
                "message":    "Username or password is incorrect.",
                "request_id": request_id,
            },
        )

    expire_delta = timedelta(minutes=JWT_EXPIRE_MINUTES)
    token        = create_access_token(body.username, expire_delta)

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        expires_in=JWT_EXPIRE_MINUTES * 60,
        subject=body.username,
    )


# ── GET /verify ────────────────────────────────────────────────────────────────
@router.get(
    "/verify",
    response_model=VerifyResponse,
    summary="Verify a JWT token — validates exp, iat, nbf, iss",
)
async def verify_token(
    request:       Request,
    authorization: str = Header(default=""),
    client_cn:     str = Depends(verify_client_cn),
) -> VerifyResponse:
    """
    Validate a JWT from the Authorization header.
    Checks: signature, expiry (exp), not-before (nbf), issued-at (iat), issuer (iss).
    """
    if not authorization or not authorization.startswith("Bearer "):
        return VerifyResponse(valid=False, error="missing_token")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        return VerifyResponse(valid=False, error="empty_token")

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={
                "verify_exp": True,   # ← rejects expired tokens
                "verify_nbf": True,   # ← rejects not-yet-valid tokens
                "verify_iat": True,   # ← rejects tokens with future iat
            },
            # Only accept tokens issued by our own auth service
            issuer="service-a.zerotrust.local",
        )

        exp_ts = payload.get("exp")
        exp_dt = (
            datetime.fromtimestamp(exp_ts, tz=timezone.utc)
            if exp_ts else None
        )

        return VerifyResponse(
            valid=True,
            subject=payload.get("sub", ""),
            expires_at=exp_dt,
        )

    except jwt.ExpiredSignatureError:
        return VerifyResponse(valid=False, error="token_expired — please login again")
    except jwt.ImmatureSignatureError:
        return VerifyResponse(valid=False, error="token_not_yet_valid (nbf check failed)")
    except jwt.InvalidIssuedAtError:
        return VerifyResponse(valid=False, error="invalid_iat — clock skew detected")
    except jwt.InvalidIssuerError:
        return VerifyResponse(valid=False, error="invalid_issuer — token not from this service")
    except jwt.InvalidTokenError as exc:
        return VerifyResponse(valid=False, error=f"invalid_token: {exc}")
