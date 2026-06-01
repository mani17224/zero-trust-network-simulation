"""
auth.py — mTLS CN verification for service-c.
Fixes:
  - Accepts both 'gateway' (short) and 'gateway.zerotrust.local' (full)
  - Reads allowlist from env var so Docker Compose can configure it
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import HTTPException, Request, status

_RAW_ALLOW = os.getenv(
    "ALLOWED_CLIENT_CNS",
    "gateway.zerotrust.local,service-a.zerotrust.local,"
    "service-b.zerotrust.local,service-c.zerotrust.local,"
    "monitoring.zerotrust.local,admin-service.zerotrust.local",
)

# Build a set that includes BOTH the short name and full domain
_FULL_CNS = {cn.strip() for cn in _RAW_ALLOW.split(",") if cn.strip()}
_SHORT_CNS = {cn.split(".")[0] for cn in _FULL_CNS}
ALLOWED_CNS = _FULL_CNS | _SHORT_CNS


def extract_client_cn(request: Request) -> Optional[str]:
    """
    Extract CN from:
      1. X-Client-Cert-CN header  (set by gateway when forwarding)
      2. X-Subject header         (short name set by gateway)
      3. Direct SSL object        (for direct TLS connections)
    """
    for header in ("X-Client-Cert-CN", "X-Subject"):
        val = request.headers.get(header, "").strip()
        if val:
            return val

    ssl_object = request.scope.get("ssl_object")
    if ssl_object:
        try:
            cert = ssl_object.getpeercert()
            if cert:
                for field in cert.get("subject", []):
                    for k, v in field:
                        if k == "commonName":
                            return v
        except Exception:
            pass

    return None


def verify_client_cn(request: Request) -> str:
    """
    Verify client CN against allowlist.
    Raises 401 if no cert present, 403 if CN not allowed.
    """
    cn = extract_client_cn(request)

    if not cn:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error":   "unauthorized",
                "message": "Client certificate required — missing X-Client-Cert-CN header",
            },
        )

    # Check both full and short forms
    short = cn.split(".")[0]
    if cn not in ALLOWED_CNS and short not in ALLOWED_CNS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error":   "forbidden",
                "message": f"Client CN '{cn}' is not authorized to call service-c",
                "service": "service-c",
            },
        )

    return cn
