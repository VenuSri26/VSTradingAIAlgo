"""Canonical application version and build metadata."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_VERSION = "0.0.0"


def _read_version() -> str:
    version_file = Path(__file__).resolve().parents[2] / "VERSION"
    try:
        value = version_file.read_text(encoding="utf-8").strip()
        if value:
            return value
    except OSError:
        pass
    return os.getenv("APP_VERSION", "").strip() or _DEFAULT_VERSION


def _release_path() -> str | None:
    current = Path("/opt/vstradingai/current")
    try:
        return str(current.resolve()) if current.exists() else None
    except OSError:
        return None


APP_VERSION = _read_version()
BUILD_ID = os.getenv("BUILD_ID", "local")
BUILD_TIME = os.getenv("BUILD_TIME", "unknown")
GIT_COMMIT = os.getenv("GIT_COMMIT", "unknown")
APP_ENVIRONMENT = os.getenv("APP_ENVIRONMENT", "production" if Path("/opt/vstradingai").exists() else "development")


def version_info() -> dict[str, str | None]:
    return {
        "version": APP_VERSION,
        "build_id": BUILD_ID,
        "build_time": BUILD_TIME,
        "git_commit": GIT_COMMIT,
        "environment": APP_ENVIRONMENT,
        "release_path": _release_path(),
        "reported_at": datetime.now(timezone.utc).isoformat(),
    }
