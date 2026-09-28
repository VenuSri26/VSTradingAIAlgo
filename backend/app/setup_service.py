"""Validated, persistent UI setup operations.

Only an allowlist of paper-trading preferences can be changed. Live broker
orders cannot be enabled here. Zerodha token exchange is permitted only over
HTTPS and persists the resulting access token without returning it.
"""
from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from urllib.parse import parse_qs, urlparse

from dotenv import set_key

from app.config import settings, validate

_lock = RLock()


def env_path() -> Path:
    configured = os.getenv("BACKEND_ENV_PATH")
    if configured:
        return Path(configured)
    production = Path("/opt/vstradingai/shared/backend.env")
    return production if production.exists() else Path(".env")


def _backup(path: Path) -> Path:
    root = path.parent / "data" / "config_backups"
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ%f")
    target = root / f"backend.env.{stamp}.bak"
    if path.exists():
        shutil.copy2(path, target)
    return target


def _write(values: dict[str, str], path: Path | None = None) -> str:
    target = path or env_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.touch(mode=0o600)
    backup = _backup(target)
    try:
        for key, value in values.items():
            set_key(str(target), key, value, quote_mode="never")
        os.chmod(target, 0o600)
    except Exception:
        if backup.exists():
            shutil.copy2(backup, target)
        raise
    return str(backup)


def status(token_health: dict | None = None) -> dict:
    return {
        "execution_mode": "PAPER_ONLY",
        "paper_enabled": settings.paper_auto_trader_enabled,
        "live_mode_locked": True,
        "live_mode_unlock_requirement": "Complete multi-session paper certification and a separate production approval.",
        "live_orders_enabled": settings.live_orders_enabled,
        "minimum_confidence": settings.paper_auto_trader_min_score,
        "capital": settings.paper_capital,
        "capital_min": 10000,
        "capital_max": 200000,
        "profit_withdrawal_threshold": settings.paper_profit_withdrawal_threshold,
        "default_stop_loss_pct": settings.paper_default_stop_loss_pct,
        "zerodha": token_health or {"connected": False},
        "https_required_for_token_refresh": True,
        "https_configured": settings.require_https,
        "secrets_exposed": False,
    }


def save_preferences(*, minimum_confidence: int, capital: float,
                     profit_withdrawal_threshold: float, default_stop_loss_pct: float,
                     path: Path | None = None) -> dict:
    if not 70 <= minimum_confidence <= 90:
        raise ValueError("Minimum confidence must be between 70 and 90")
    if not 10000 <= capital <= 200000:
        raise ValueError("Capital must be between ₹10,000 and ₹2,00,000")
    if not 0 <= profit_withdrawal_threshold <= 10_000_000:
        raise ValueError("Profit withdrawal threshold must be between ₹0 and ₹1,00,00,000")
    if not 1 <= default_stop_loss_pct <= 50:
        raise ValueError("Default stop-loss must be between 1% and 50%")
    values = {
        "PAPER_AUTO_TRADER_MIN_SCORE": str(int(minimum_confidence)),
        "PAPER_CAPITAL": str(round(float(capital), 2)),
        "PAPER_PROFIT_WITHDRAWAL_THRESHOLD": str(round(float(profit_withdrawal_threshold), 2)),
        "PAPER_DEFAULT_STOP_LOSS_PCT": str(round(float(default_stop_loss_pct), 2)),
        "LIVE_ORDERS_ENABLED": "false",
    }
    with _lock:
        previous = {
            "paper_auto_trader_min_score": settings.paper_auto_trader_min_score,
            "paper_capital": settings.paper_capital,
            "paper_profit_withdrawal_threshold": settings.paper_profit_withdrawal_threshold,
            "paper_default_stop_loss_pct": settings.paper_default_stop_loss_pct,
            "live_orders_enabled": settings.live_orders_enabled,
        }
        settings.paper_auto_trader_min_score = int(minimum_confidence)
        settings.paper_capital = float(capital)
        settings.paper_profit_withdrawal_threshold = float(profit_withdrawal_threshold)
        settings.paper_default_stop_loss_pct = float(default_stop_loss_pct)
        settings.live_orders_enabled = False
        problems = validate()
        if problems:
            for key, value in previous.items():
                setattr(settings, key, value)
            raise ValueError("Configuration validation failed: " + "; ".join(problems))
        try:
            backup = _write(values, path)
        except Exception:
            for key, value in previous.items():
                setattr(settings, key, value)
            raise
    return {"saved": True, "applied_immediately": True, "backup": backup, **status()}


def kite_login_url() -> str:
    if not settings.kite_api_key:
        raise ValueError("KITE_API_KEY is not configured on the server")
    from kiteconnect import KiteConnect
    return KiteConnect(api_key=settings.kite_api_key, timeout=15).login_url()


def refresh_kite_token(redirect_url: str, *, path: Path | None = None) -> dict:
    if settings.live_orders_enabled:
        raise ValueError("LIVE_ORDERS_ENABLED must remain false")
    if not settings.kite_api_key or not settings.kite_api_secret:
        raise ValueError("Kite API key or secret is missing on the server")
    token = parse_qs(urlparse(redirect_url).query).get("request_token", [""])[0].strip()
    if not token:
        raise ValueError("request_token was not found in the redirect URL")
    from kiteconnect import KiteConnect
    kite = KiteConnect(api_key=settings.kite_api_key, timeout=15)
    session = kite.generate_session(token, api_secret=settings.kite_api_secret)
    access_token = str(session.get("access_token") or "").strip()
    if not access_token:
        raise ValueError("Zerodha did not return an access token")
    kite.set_access_token(access_token)
    profile = kite.profile()
    if not profile.get("user_id"):
        raise ValueError("Zerodha profile verification failed")
    with _lock:
        backup = _write({"KITE_ACCESS_TOKEN": access_token, "LIVE_ORDERS_ENABLED": "false"}, path)
        settings.kite_access_token = access_token
        settings.live_orders_enabled = False
        from app import routes
        from app.data_sources.zerodha_client import ZerodhaDataSource
        routes._data_source = ZerodhaDataSource(settings.kite_api_key, access_token)
    return {"connected": True, "user_id": profile.get("user_id"), "saved": True,
            "applied_immediately": True, "backup": backup,
            "live_orders_enabled": False, "access_token_exposed": False}
