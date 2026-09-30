"""API settings (environment-driven, validated; unknown fields rejected)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(name)
    return [x.strip() for x in raw.split(",") if x.strip()] if raw else default


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_hosts: list[str] = Field(default_factory=lambda: ["127.0.0.1", "localhost"])
    extra_origins: list[str] = Field(default_factory=list)
    secure_cookies: bool = True
    session_ttl_minutes: int = Field(default=480, ge=5, le=7 * 24 * 60)
    session_cookie_path: str = "/"
    session_cookie_samesite: Literal["strict", "lax", "none"] = "strict"
    session_cookie_httponly: bool = True
    max_json_bytes: int = Field(default=1024 * 1024, gt=0)
    max_upload_bytes: int = Field(default=2 * 1024**3, gt=0)
    max_asset_storage_bytes: int = Field(default=10 * 1024**3, gt=0)
    login_attempts_per_minute: int = Field(default=6, ge=1)
    login_ip_rate_multiplier: int = Field(default=3, ge=1)
    mutations_per_minute: int = Field(default=240, ge=1)
    dashboard_dir: Path | None = None
    demo_mode: bool = False
    anonymous_read_only: bool = False
    scan_workers: int = Field(default=1, ge=1, le=4)
    default_profile: str = "baseline"

    @classmethod
    def from_env(cls, **overrides) -> "Settings":
        defaults = cls()
        values = {
            "allowed_hosts": _env_list("VISIONSENTINEL_ALLOWED_HOSTS", defaults.allowed_hosts),
            "extra_origins": _env_list("VISIONSENTINEL_ALLOWED_ORIGINS", defaults.extra_origins),
            "secure_cookies": os.environ.get("VISIONSENTINEL_INSECURE_COOKIES") != "1" if
            os.environ.get("VISIONSENTINEL_INSECURE_COOKIES") else defaults.secure_cookies,
            "demo_mode": os.environ.get("VISIONSENTINEL_DEMO") == "1",
            "anonymous_read_only": os.environ.get("VISIONX_ANONYMOUS_READ_ONLY", "0") == "1",
        }
        env_fields = {
            "session_ttl_minutes": "VISIONSENTINEL_SESSION_TTL_MINUTES",
            "session_cookie_path": "VISIONSENTINEL_SESSION_COOKIE_PATH",
            "session_cookie_samesite": "VISIONSENTINEL_SESSION_COOKIE_SAMESITE",
            "session_cookie_httponly": "VISIONSENTINEL_SESSION_COOKIE_HTTPONLY",
            "max_json_bytes": "VISIONSENTINEL_MAX_JSON_BYTES",
            "max_upload_bytes": "VISIONSENTINEL_MAX_UPLOAD_BYTES",
            "max_asset_storage_bytes": "VISIONSENTINEL_MAX_ASSET_STORAGE_BYTES",
            "login_attempts_per_minute": "VISIONSENTINEL_LOGIN_ATTEMPTS_PER_MINUTE",
            "login_ip_rate_multiplier": "VISIONSENTINEL_LOGIN_IP_RATE_MULTIPLIER",
            "mutations_per_minute": "VISIONSENTINEL_MUTATIONS_PER_MINUTE",
            "scan_workers": "VISIONSENTINEL_SCAN_WORKERS",
            "default_profile": "VISIONSENTINEL_DEFAULT_PROFILE",
        }
        for field, env_name in env_fields.items():
            if env_name in os.environ:
                values[field] = os.environ[env_name]
        dashboard = os.environ.get("VISIONSENTINEL_DASHBOARD")
        if dashboard:
            values["dashboard_dir"] = Path(dashboard)
        values.update({k: v for k, v in overrides.items() if v is not None})
        return cls(**values)
