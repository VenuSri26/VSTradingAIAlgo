from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app import store
from app.config import settings, validate
from app.version import version_info


@dataclass(frozen=True)
class ResilienceCheck:
    code: str
    label: str
    status: str
    detail: str
    blocking: bool = False


def _age_seconds(path: Path) -> float | None:
    try:
        return max(0.0, datetime.now(timezone.utc).timestamp() - path.stat().st_mtime)
    except OSError:
        return None


def _database_check() -> ResilienceCheck:
    db_path = Path(store.DB_PATH)
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path, timeout=3.0) as conn:
            conn.execute("SELECT 1").fetchone()
        return ResilienceCheck("DATABASE", "SQLite availability", "PASS", f"Database reachable at {db_path}")
    except Exception as exc:
        return ResilienceCheck("DATABASE", "SQLite availability", "FAIL", str(exc), True)


def _path_writable_check(path_value: str, code: str, label: str) -> ResilienceCheck:
    path = Path(path_value)
    parent = path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
        writable = os.access(parent, os.W_OK)
        return ResilienceCheck(code, label, "PASS" if writable else "FAIL", f"Parent directory: {parent}", not writable)
    except Exception as exc:
        return ResilienceCheck(code, label, "FAIL", str(exc), True)


def _market_data_check() -> ResilienceCheck:
    state_path = Path(settings.market_data_state_path)
    if not state_path.exists():
        status = "WARN" if not settings.is_live() else "FAIL"
        return ResilienceCheck(
            "MARKET_DATA_STATE", "Market-data recovery state", status,
            f"State file not found: {state_path}", settings.is_live(),
        )
    age = _age_seconds(state_path)
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        keys = sorted(payload.keys())[:8] if isinstance(payload, dict) else []
        detail = f"State age {age:.0f}s; keys: {', '.join(keys) or 'none'}" if age is not None else "State file readable"
        stale = age is not None and age > max(60, settings.max_data_age_sec * 5)
        status = "WARN" if stale else "PASS"
        return ResilienceCheck("MARKET_DATA_STATE", "Market-data recovery state", status, detail, False)
    except Exception as exc:
        return ResilienceCheck("MARKET_DATA_STATE", "Market-data recovery state", "FAIL", f"Invalid state file: {exc}", settings.is_live())


def resilience_status() -> dict[str, Any]:
    config_problems = validate()
    checks: list[ResilienceCheck] = [
        ResilienceCheck(
            "CONFIG", "Configuration validation", "PASS" if not config_problems else "FAIL",
            "Configuration valid" if not config_problems else "; ".join(config_problems), bool(config_problems),
        ),
        _database_check(),
        _path_writable_check(settings.audit_log_path, "AUDIT_PATH", "Audit-log persistence"),
        _market_data_check(),
    ]

    try:
        position = store.get_open_position()
        detail = "No open paper position" if not position else f"Recoverable open position #{position.get('id')} {position.get('option_type')} {position.get('strike')}"
        checks.append(ResilienceCheck("POSITION_RECOVERY", "Position restart recovery", "PASS", detail))
    except Exception as exc:
        checks.append(ResilienceCheck("POSITION_RECOVERY", "Position restart recovery", "FAIL", str(exc), True))

    checks.extend([
        ResilienceCheck(
            "LIVE_ORDER_LOCK", "Automatic live-order safety lock",
            "PASS" if not settings.live_orders_enabled else "FAIL",
            "Live broker orders are disabled" if not settings.live_orders_enabled else "Live broker orders are enabled",
            settings.live_orders_enabled,
        ),
        ResilienceCheck(
            "TIMEZONE", "Trading timezone", "PASS" if settings.app_timezone == "Asia/Kolkata" else "WARN",
            f"Configured timezone: {settings.app_timezone}", False,
        ),
    ])

    blocking = [c for c in checks if c.blocking and c.status == "FAIL"]
    failed = [c for c in checks if c.status == "FAIL"]
    warnings = [c for c in checks if c.status == "WARN"]
    score = round(sum(1 for c in checks if c.status == "PASS") / len(checks) * 100.0, 2)
    overall = "READY" if not blocking and not failed else ("DEGRADED" if not blocking else "BLOCKED")

    return {
        "version": version_info(),
        "overall": overall,
        "resilience_score": score,
        "restart_safe": not blocking,
        "paper_only": not settings.live_orders_enabled,
        "checks": [asdict(c) for c in checks],
        "blocking_issues": [asdict(c) for c in blocking],
        "warning_count": len(warnings),
        "recommended_action": (
            "System can restart safely; continue paper validation."
            if not blocking else "Resolve blocking persistence or configuration issues before restart/deployment."
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
