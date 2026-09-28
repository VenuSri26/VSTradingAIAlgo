from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.config import settings
from app.live_paper_bridge_routes import require_admin_token
from app.routes import get_data_source
from app.trading_report import TradingReportService
from app.trading_report_scheduler import TradingReportScheduler

router = APIRouter()
service = TradingReportService(settings.trading_report_path, get_data_source)
pre_market_scheduler = TradingReportScheduler(
    service, "PRE_MARKET", settings.pre_market_report_time,
    enabled=settings.trading_report_scheduler_enabled,
    timezone_name=settings.app_timezone, poll_interval_sec=settings.trading_report_poll_interval_sec,
)
post_market_scheduler = TradingReportScheduler(
    service, "POST_MARKET", settings.post_market_report_time,
    enabled=settings.trading_report_scheduler_enabled,
    timezone_name=settings.app_timezone, poll_interval_sec=settings.trading_report_poll_interval_sec,
)


@router.get("/api/trading-reports/status")
def report_status():
    return {"pre_market": service.latest("PRE_MARKET"), "post_market": service.latest("POST_MARKET"),
            "schedulers": {"pre_market": pre_market_scheduler.status(), "post_market": post_market_scheduler.status()},
            "execution_mode": "PAPER_ONLY", "live_orders_enabled": False}


@router.get("/api/trading-reports/history")
def report_history(limit: int = 20, report_type: str | None = None):
    normalized = report_type.upper() if report_type else None
    if normalized and normalized not in {"PRE_MARKET", "POST_MARKET"}:
        raise HTTPException(status_code=422, detail="report_type must be PRE_MARKET or POST_MARKET")
    return {"reports": service.history(limit, normalized)}


@router.post("/api/trading-reports/generate", dependencies=[Depends(require_admin_token)])
def generate_report(report_type: str):
    normalized = report_type.upper()
    if normalized not in {"PRE_MARKET", "POST_MARKET"}:
        raise HTTPException(status_code=422, detail="report_type must be PRE_MARKET or POST_MARKET")
    return service.generate(normalized)


@router.post("/api/trading-reports/scheduler/run", dependencies=[Depends(require_admin_token)])
def run_report_scheduler(report_type: str, force: bool = False):
    normalized = report_type.upper()
    scheduler = pre_market_scheduler if normalized == "PRE_MARKET" else post_market_scheduler if normalized == "POST_MARKET" else None
    if scheduler is None:
        raise HTTPException(status_code=422, detail="report_type must be PRE_MARKET or POST_MARKET")
    return scheduler.run_once(force=force)
