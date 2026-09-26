"""Holiday-safe readiness certificate for the v7.8 autonomous paper loop."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app import store
from app.config import settings, validate
from app.paper_auto_trader import status_snapshot as automation_status
from app.paper_monitor import status_snapshot as monitor_status
from app.version import version_info


def _time_minutes(value: str) -> int | None:
    try:
        hour, minute = (int(part) for part in value.split(":", 1))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour * 60 + minute
    except (TypeError, ValueError):
        pass
    return None


def _check(code: str, label: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"code": code, "label": label, "passed": bool(passed), "detail": detail}


def paper_loop_readiness() -> dict[str, Any]:
    problems = validate()
    entry_cutoff = _time_minutes(settings.execution_entry_cutoff_time)
    eod_exit = _time_minutes(settings.paper_eod_exit_time)
    market_close = _time_minutes(settings.market_close_time)

    try:
        persistent = store.paper_automation_summary()
        persistence_ok, persistence_detail = True, f"SQLite audit ledger reachable; {persistent['recorded_cycles']} cycles today"
    except Exception as exc:
        persistence_ok, persistence_detail = False, f"SQLite audit ledger unavailable: {exc}"

    notification_parent = Path(settings.paper_notification_path).parent
    notification_ok = notification_parent.exists() and notification_parent.is_dir()
    reporting_parent = Path(settings.trading_report_path).parent
    reporting_ok = (settings.trading_report_scheduler_enabled and reporting_parent.exists()
                    and reporting_parent.is_dir())
    checks = [
        _check("CONFIG", "Configuration is valid", not problems,
               "No configuration problems" if not problems else "; ".join(problems)),
        _check("PAPER_ONLY", "Live-order safety lock", not settings.live_orders_enabled,
               "LIVE_ORDERS_ENABLED=false" if not settings.live_orders_enabled else "Unsafe: live orders are enabled"),
        _check("AUTO_ENTRY", "Autonomous entry worker configured", settings.paper_auto_trader_enabled,
               f"enabled={settings.paper_auto_trader_enabled}; interval={settings.paper_auto_trader_interval_sec}s"),
        _check("AUTO_MONITOR", "Restart-safe monitor configured", settings.paper_auto_monitor_enabled,
               f"enabled={settings.paper_auto_monitor_enabled}; interval={settings.paper_monitor_interval_sec}s"),
        _check("QUALITY_GATE", "A/A+ quality gate", 1 <= settings.paper_auto_trader_min_score <= 100,
               f"grades={settings.paper_auto_trader_grades}; minimum_score={settings.paper_auto_trader_min_score}"),
        _check("FRESHNESS_GATE", "Quote freshness gate", settings.paper_monitor_max_age_sec > 0,
               f"maximum quote age={settings.paper_monitor_max_age_sec}s"),
        _check("SESSION_TIMES", "Entry and EOD timing", None not in (entry_cutoff, eod_exit, market_close)
               and entry_cutoff <= eod_exit <= market_close,
               f"entry cutoff={settings.execution_entry_cutoff_time}; EOD exit={settings.paper_eod_exit_time}; market close={settings.market_close_time}"),
        _check("PERSISTENCE", "Persistent automation audit", persistence_ok, persistence_detail),
        _check("NOTIFICATION_PATH", "Paper event path", notification_ok,
               f"notification directory={notification_parent}"),
        _check("DAILY_REPORTING", "Pre/post-market reporting", reporting_ok,
               f"pre={settings.pre_market_report_time}; post={settings.post_market_report_time}; directory={reporting_parent}"),
    ]
    pending_live = [
        "Fresh authenticated Zerodha market data",
        "At least one complete market-session observation",
        "Observed autonomous paper entry, management, exit and journal lifecycle",
        "Multi-session performance sample for strategy certification",
    ]
    failed = [item for item in checks if not item["passed"]]
    auto = automation_status()
    monitor = monitor_status()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": version_info(),
        "status": "OFFLINE_COMPLETE_LIVE_PENDING" if not failed else "OFFLINE_BLOCKED",
        "offline_complete": not failed,
        "live_market_pending": True,
        "checks": checks,
        "failed_checks": failed,
        "pending_live_evidence": pending_live,
        "runtime": {
            "automation_running": auto.get("running", False),
            "monitor_running": monitor.get("running", False),
            "last_action": auto.get("last_action"),
            "last_reason": auto.get("last_reason"),
        },
        "execution_mode": "PAPER_ONLY",
        "live_orders_enabled": settings.live_orders_enabled,
        "recommended_action": (
            "Keep the service running and collect live-market evidence on the next trading session."
            if not failed else "Resolve failed offline checks before the next trading session."
        ),
    }
