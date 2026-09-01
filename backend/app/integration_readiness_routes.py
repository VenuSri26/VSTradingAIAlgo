from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from urllib import request
from app.config import settings
from app.routes import require_admin_token
from app.notification_delivery import NotificationDelivery
from app.market_calendar_service import MarketCalendarService
from app.broker_greeks_validation import compare_broker_greeks
from app.greeks_validation_history import GreeksValidationHistory
from app.notification_scheduler import NotificationScheduler
from app.operational_digest import OperationalDigestService
from app.daily_digest_scheduler import DailyDigestScheduler

router = APIRouter()
_delivery = NotificationDelivery(
    settings.notification_outbox_path,
    settings.notification_webhook_url,
    settings.notification_timeout_sec,
    smtp_host=settings.notification_smtp_host,
    smtp_port=settings.notification_smtp_port,
    smtp_username=settings.notification_smtp_username,
    smtp_password=settings.notification_smtp_password,
    smtp_from=settings.notification_smtp_from,
    smtp_to=settings.notification_smtp_to,
    smtp_to_info=settings.notification_smtp_to_info,
    smtp_to_warning=settings.notification_smtp_to_warning,
    smtp_to_critical=settings.notification_smtp_to_critical,
    smtp_to_broker=settings.notification_smtp_to_broker,
    smtp_to_infrastructure=settings.notification_smtp_to_infrastructure,
    smtp_to_trading=settings.notification_smtp_to_trading,
    whatsapp_enabled=settings.notification_whatsapp_enabled,
    whatsapp_api_url=settings.notification_whatsapp_api_url,
    whatsapp_token=settings.notification_whatsapp_token,
    whatsapp_to=settings.notification_whatsapp_to,
    smtp_use_tls=settings.notification_smtp_use_tls,
    retry_base_sec=settings.notification_retry_base_sec,
    retry_max_sec=settings.notification_retry_max_sec,
    max_attempts=settings.notification_max_attempts,
)
_calendar = MarketCalendarService(settings.market_calendar_path)
_greeks_history = GreeksValidationHistory(settings.greeks_validation_history_path)
_scheduler = NotificationScheduler(_delivery, settings.notification_dispatch_interval_sec, settings.notification_escalate_after_sec)
_digest = OperationalDigestService(settings.operational_digest_path, _delivery, _calendar, _greeks_history, _scheduler)
_daily_digest_scheduler = DailyDigestScheduler(_digest, enabled=settings.daily_digest_enabled, run_time=settings.daily_digest_time, timezone_name=settings.app_timezone, poll_interval_sec=settings.daily_digest_poll_interval_sec, enqueue=settings.daily_digest_enqueue)


class NotifyBody(BaseModel):
    code: str = Field(min_length=2, max_length=80)
    severity: str = Field(default="INFO", max_length=20)
    message: str = Field(min_length=2, max_length=500)
    action: str = Field(default="REVIEW", max_length=120)
    metadata: dict = {}


class AcknowledgeBody(BaseModel):
    note: str = Field(default="", max_length=300)


class HolidaysBody(BaseModel):
    holidays: list[dict]


class HolidayImportBody(BaseModel):
    content: str = Field(min_length=2)
    format: str = "auto"
    replace: bool = True


@router.get("/api/integration-readiness/status")
def integration_status():
    delivery = _delivery.status()
    calendar = _calendar.status()
    greeks = _greeks_history.summary()
    blockers = []
    warnings = []
    if calendar["count"] == 0:
        blockers.append("MARKET_CALENDAR_EMPTY")
    if not delivery["delivery_enabled"]:
        warnings.append("NOTIFICATION_DELIVERY_DISABLED")
    if greeks["samples"] < 5:
        warnings.append("INSUFFICIENT_LIVE_GREEKS_SAMPLES")
    status = "BLOCKED" if blockers else ("DEGRADED" if warnings else "READY")
    return {
        "status": status,
        "notification_delivery": delivery,
        "market_calendar": calendar,
        "greeks_validation": greeks,
        "greeks_validation_available": True,
        "blockers": blockers,
        "warnings": warnings,
        "live_orders_enabled": False,
    }


@router.get("/api/notifications/outbox")
def notification_outbox(limit: int = 50):
    return {"status": _delivery.status(), "items": _delivery.list(limit)}


@router.post("/api/notifications/enqueue", dependencies=[Depends(require_admin_token)])
def notification_enqueue(body: NotifyBody):
    return _delivery.enqueue(body.code, body.severity, body.message, body.action, body.metadata)


@router.post("/api/notifications/dispatch", dependencies=[Depends(require_admin_token)])
def notification_dispatch(limit: int = 20):
    return _delivery.dispatch(limit)


@router.get("/api/notifications/scheduler")
def notification_scheduler_status():
    return _scheduler.status()


@router.post("/api/notifications/scheduler/run", dependencies=[Depends(require_admin_token)])
def notification_scheduler_run():
    return _scheduler.run_once()


@router.post("/api/notifications/{item_id}/acknowledge", dependencies=[Depends(require_admin_token)])
def notification_acknowledge(item_id: str, body: AcknowledgeBody):
    try:
        return _delivery.acknowledge(item_id, body.note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Notification not found") from exc


@router.get("/api/operations/digest/status")
def operational_digest_status():
    return _digest.status()

@router.get("/api/operations/digest/scheduler")
def operational_digest_scheduler_status():
    return _daily_digest_scheduler.status()


@router.post("/api/operations/digest/scheduler/run", dependencies=[Depends(require_admin_token)])
def operational_digest_scheduler_run(force: bool = False):
    return _daily_digest_scheduler.run_once(force=force)



@router.get("/api/operations/digest/history")
def operational_digest_history(limit: int = 30):
    return {"items": _digest.history(limit), "status": _digest.status()}


@router.post("/api/operations/digest/generate", dependencies=[Depends(require_admin_token)])
def operational_digest_generate(enqueue: bool = False):
    return _digest.generate(enqueue=enqueue)


@router.get("/api/market-calendar/holidays")
def holidays():
    return {"status": _calendar.status(), "holidays": _calendar.list_holidays()}


@router.post("/api/market-calendar/holidays", dependencies=[Depends(require_admin_token)])
def replace_holidays(body: HolidaysBody):
    try:
        return _calendar.replace(body.holidays)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/api/market-calendar/import", dependencies=[Depends(require_admin_token)])
def import_holidays(body: HolidayImportBody):
    try:
        return _calendar.import_text(body.content, body.format, body.replace)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc




class HolidaySyncBody(BaseModel):
    url: str | None = None
    format: str | None = None
    replace: bool = True


@router.post("/api/market-calendar/sync", dependencies=[Depends(require_admin_token)])
def sync_holidays(body: HolidaySyncBody):
    url = (body.url or settings.market_calendar_source_url or "").strip()
    if not url:
        raise HTTPException(status_code=422, detail="MARKET_CALENDAR_SOURCE_URL is not configured")
    fmt = (body.format or settings.market_calendar_source_format or "auto").lower()
    try:
        req = request.Request(url, headers={"User-Agent": "VSTradingAI/6.5"})
        with request.urlopen(req, timeout=max(2.0, settings.notification_timeout_sec)) as response:  # noqa: S310 - admin configured source
            content = response.read().decode("utf-8")
        result = _calendar.import_text(content, fmt, body.replace)
        return {**result, "source_url": url, "source_format": fmt, "live_orders_enabled": False}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Holiday source synchronization failed: {exc}") from exc

@router.post("/api/broker-greeks/compare")
def broker_greeks_compare(payload: dict):
    try:
        result = compare_broker_greeks(payload)
        recorded = _greeks_history.record(result, source=str(payload.get("source") or "BROKER"))
        return {**result, "recorded_at": recorded["captured_at"]}
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid Greeks payload: {exc}") from exc


@router.get("/api/broker-greeks/history")
def broker_greeks_history(limit: int = 100):
    return {"summary": _greeks_history.summary(limit), "items": _greeks_history.list(limit)}


@router.get("/api/broker-greeks/session-summary")
def broker_greeks_session_summary(limit: int = 200):
    return _greeks_history.summary(limit)
