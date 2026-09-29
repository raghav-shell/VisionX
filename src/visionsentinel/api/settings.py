"""API settings (environment-driven, validated; unknown fields rejected)."""

from __future__ import annotations

import os
from pathlib import Path

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
    max_json_bytes: int = Field(default=1024 * 1024, gt=0)
    max_upload_bytes: int = Field(default=2 * 1024**3, gt=0)
    login_attempts_per_minute: int = Field(default=6, ge=1)
    mutations_per_minute: int = Field(default=240, ge=1)
    dashboard_dir: Path | None = None
    demo_mode: bool = False
    scan_workers: int = Field(default=1, ge=1, le=4)
    default_profile: str = "baseline"

    @classmethod
    def from_env(cls, **overrides) -> "Settings":
        values = {
            "allowed_hosts": _env_list("VISIONSENTINEL_ALLOWED_HOSTS", ["127.0.0.1", "localhost"]),
            "extra_origins": _env_list("VISIONSENTINEL_ALLOWED_ORIGINS", []),
            "secure_cookies": os.environ.get("VISIONSENTINEL_INSECURE_COOKIES") != "1",
            "demo_mode": os.environ.get("VISIONSENTINEL_DEMO") == "1",
        }
        if os.environ.get("VISIONSENTINEL_DASHBOARD"):
            values["dashboard_dir"] = Path(os.environ["VISIONSENTINEL_DASHBOARD"])
        values.update({k: v for k, v in overrides.items() if v is not None})
        return cls(**values)
