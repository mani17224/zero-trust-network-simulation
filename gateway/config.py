"""
config.py — Gateway configuration via environment variables.
All settings validated with Pydantic BaseSettings.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Gateway application settings loaded from environment variables."""

    # ── Application ────────────────────────────────────────────────────────────
    app_name:    str  = Field(default="Zero Trust Gateway", env="APP_NAME")
    app_version: str  = Field(default="1.0.0",             env="APP_VERSION")
    debug:       bool = Field(default=False,                env="DEBUG")
    log_level:   str  = Field(default="INFO",               env="LOG_LEVEL")
    host:        str  = Field(default="0.0.0.0",            env="HOST")
    port:        int  = Field(default=8000,                 env="PORT")

    # ── Dev-mode CN override (ONLY used when DEBUG=true) ──────────────────────
    # Allows testing without real TLS certs.
    # Set: DEV_CLIENT_CN=gateway.zerotrust.local
    dev_client_cn: Optional[str] = Field(default=None, env="DEV_CLIENT_CN")

    # ── mTLS Certificate Paths ─────────────────────────────────────────────────
    tls_cert_file: str = Field(default="/certs/gateway/cert.pem",      env="TLS_CERT_FILE")
    tls_key_file:  str = Field(default="/certs/gateway/key.pem",       env="TLS_KEY_FILE")
    tls_ca_file:   str = Field(default="/certs/gateway/ca_chain.pem",  env="TLS_CA_FILE")

    # ── OPA Policy Engine ──────────────────────────────────────────────────────
    opa_url:             str   = Field(default="http://opa:8181",              env="OPA_URL")
    opa_policy_path:     str   = Field(default="/v1/data/zerotrust/authz",     env="OPA_POLICY_PATH")
    opa_timeout_seconds: float = Field(default=5.0,                            env="OPA_TIMEOUT_SECONDS")
    opa_cache_ttl_seconds: int = Field(default=10,                             env="OPA_CACHE_TTL_SECONDS")

    # ── Upstream Services (HTTP inside Docker, HTTPS with real certs) ─────────
    # Use http:// inside Docker Compose (services talk on internal network).
    # Use https:// only when certs are mounted and mTLS is fully configured.
    service_a_url: str = Field(default="http://service-a:8001", env="SERVICE_A_URL")
    service_b_url: str = Field(default="http://service-b:8002", env="SERVICE_B_URL")
    service_c_url: str = Field(default="http://service-c:8003", env="SERVICE_C_URL")

    # ── Upstream Request Settings ──────────────────────────────────────────────
    upstream_timeout_seconds: float = Field(default=30.0, env="UPSTREAM_TIMEOUT_SECONDS")
    upstream_max_connections: int   = Field(default=100,  env="UPSTREAM_MAX_CONNECTIONS")

    # ── JWT ────────────────────────────────────────────────────────────────────
    jwt_secret:         str = Field(default="CHANGE-ME-generate-with-openssl-rand-hex-32", env="JWT_SECRET")
    jwt_algorithm:      str = Field(default="HS256",                                        env="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=60,                                             env="JWT_EXPIRE_MINUTES")

    # ── Allowed Client CNs ────────────────────────────────────────────────────
    allowed_client_cns: List[str] = Field(
        default=[
            "gateway.zerotrust.local",
            "service-a.zerotrust.local",
            "service-b.zerotrust.local",
            "service-c.zerotrust.local",
            "monitoring.zerotrust.local",
            "admin-service.zerotrust.local",
        ],
        env="ALLOWED_CLIENT_CNS",
    )

    # ── Prometheus ─────────────────────────────────────────────────────────────
    metrics_enabled: bool = Field(default=True,       env="METRICS_ENABLED")
    metrics_path:    str  = Field(default="/metrics", env="METRICS_PATH")

    # ── CORS ───────────────────────────────────────────────────────────────────
    cors_origins: List[str] = Field(
        default=["*"],
        env="CORS_ORIGINS",
    )

    # ── Rate Limiting ──────────────────────────────────────────────────────────
    rate_limit_default:  str = Field(default="200/minute",  env="RATE_LIMIT_DEFAULT")
    rate_limit_login:    str = Field(default="10/minute",   env="RATE_LIMIT_LOGIN")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            raise ValueError(f"log_level must be one of {valid}")
        return upper

    @field_validator("allowed_client_cns", mode="before")
    @classmethod
    def parse_cn_list(cls, v):
        if isinstance(v, str):
            return [cn.strip() for cn in v.split(",") if cn.strip()]
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    model_config = {
        "env_file":          ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive":    False,
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings singleton."""
    return Settings()
