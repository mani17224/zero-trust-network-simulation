"""
main.py — Service A: Auth Service (port 8001).
Fixes:
  - Rate limiter on /login (10/min per IP)
  - Proper JSON logging
  - /ready + /healthz probes
"""
from __future__ import annotations

import json, logging, os, sys, uuid, time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from routes import router


class JSONFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname, "service": "service-a",
            "message": record.getMessage(),
        }
        skip = {"name","msg","args","levelname","levelno","pathname","filename","module",
                "exc_info","exc_text","stack_info","lineno","funcName","created","msecs",
                "relativeCreated","thread","threadName","processName","process","message","taskName"}
        entry.update({k: v for k, v in record.__dict__.items() if k not in skip})
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONFormatter())
logging.getLogger().setLevel(os.getenv("LOG_LEVEL", "INFO"))
logging.getLogger().handlers = [handler]
logger = logging.getLogger("service-a")

REQUEST_COUNT   = Counter("service_a_requests_total", "Total requests", ["method","endpoint","status"])
REQUEST_LATENCY = Histogram("service_a_request_duration_seconds", "Latency", ["endpoint"])

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Service A (Auth) starting", extra={"port": 8001})
    yield
    logger.info("Service A shutting down")


app = FastAPI(
    title="Zero Trust Auth Service", version=os.getenv("APP_VERSION", "1.0.0"),
    docs_url=None, redoc_url=None, lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    start = time.monotonic()
    response = await call_next(request)
    ms = (time.monotonic() - start) * 1000
    logger.info("handled", extra={
        "request_id": request_id, "method": request.method,
        "path": request.url.path, "status": response.status_code,
        "latency_ms": round(ms, 2),
        "subject": request.headers.get("X-Subject", "unknown"),
    })
    REQUEST_COUNT.labels(method=request.method, endpoint=request.url.path,
                         status=response.status_code).inc()
    REQUEST_LATENCY.labels(endpoint=request.url.path).observe(ms / 1000)
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(router, tags=["Auth"])


@app.get("/health")
@app.get("/healthz")
async def health():
    return {"status": "healthy", "service": "service-a", "version": os.getenv("APP_VERSION", "1.0.0")}


@app.get("/ready")
async def ready():
    return {"status": "ready", "service": "service-a"}


@app.get("/metrics")
async def metrics_endpoint():
    return PlainTextResponse(generate_latest().decode(), media_type=CONTENT_TYPE_LATEST)
