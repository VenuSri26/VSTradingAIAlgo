from __future__ import annotations
import secrets
from fastapi import HTTPException, Header
from app.config import settings


def require_app_access(x_app_token: str | None = Header(default=None)) -> None:
    if not settings.app_access_token:
        return
    if not x_app_token or not secrets.compare_digest(x_app_token, settings.app_access_token):
        raise HTTPException(status_code=401, detail="Invalid application access token")


def security_status() -> dict:
    return {
        "app_access_token_configured": bool(settings.app_access_token),
        "admin_token_configured": bool(settings.admin_token),
        "https_required": settings.require_https,
        "live_orders_enabled": settings.live_orders_enabled,
        "manual_confirmation_required": True,
        "secrets_exposed": False,
    }
