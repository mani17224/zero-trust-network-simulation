"""
logger.py — Structured JSON logging for the Zero Trust Gateway.
Logs include request ID, timestamp, subject CN, resource, and OPA decision.
"""
from __future__ import annotations

import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from gateway.config import get_settings


class JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize log record to JSON string."""
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include extra fields attached to the record
        extra_fields = {
            k: v
            for k, v in record.__dict__.items()
            if k
            not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            }
        }
        log_entry.update(extra_fields)

        # Append exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def setup_logging() -> None:
    """Configure root logger with JSON formatter to stdout."""
    settings = get_settings()
    level = getattr(logging, settings.log_level, logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Suppress noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger with JSON formatting configured."""
    return logging.getLogger(name)


def generate_request_id() -> str:
    """Generate a unique request ID (UUIDv4)."""
    return str(uuid.uuid4())


def log_request(
    logger: logging.Logger,
    request_id: str,
    method: str,
    path: str,
    subject: str,
    client_ip: str,
) -> None:
    """Log an incoming request with structured fields."""
    logger.info(
        "Incoming request",
        extra={
            "request_id": request_id,
            "method": method,
            "path": path,
            "subject": subject,
            "client_ip": client_ip,
            "event": "request_received",
        },
    )


def log_opa_decision(
    logger: logging.Logger,
    request_id: str,
    subject: str,
    service: str,
    resource: str,
    method: str,
    allow: bool,
    reason: str,
    latency_ms: float,
) -> None:
    """Log an OPA authorization decision with full context."""
    logger.info(
        "OPA decision",
        extra={
            "request_id": request_id,
            "subject": subject,
            "service": service,
            "resource": resource,
            "method": method,
            "allow": allow,
            "reason": reason,
            "opa_latency_ms": round(latency_ms, 3),
            "event": "authz_decision",
        },
    )


def log_upstream_response(
    logger: logging.Logger,
    request_id: str,
    upstream_url: str,
    status_code: int,
    latency_ms: float,
) -> None:
    """Log the response received from an upstream microservice."""
    logger.info(
        "Upstream response",
        extra={
            "request_id": request_id,
            "upstream_url": upstream_url,
            "status_code": status_code,
            "upstream_latency_ms": round(latency_ms, 3),
            "event": "upstream_response",
        },
    )


def log_error(
    logger: logging.Logger,
    request_id: str,
    error: str,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Log an error with request context."""
    extra: Dict[str, Any] = {
        "request_id": request_id,
        "error": error,
        "event": "error",
    }
    if details:
        extra.update(details)
    logger.error("Request error", extra=extra)
