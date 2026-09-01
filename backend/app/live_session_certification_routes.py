from __future__ import annotations
from fastapi import APIRouter, Depends
from app.config import settings
from app.routes import require_admin_token
from app.live_session_recorder import get_live_session_service
from app.live_session_certification import LiveSessionCertification, CertificationThresholds
from app.certification_eod_scheduler import CertificationEodScheduler

router = APIRouter()


def _service() -> LiveSessionCertification:
    try:
        from app.integration_readiness_routes import _delivery
        enqueue = _delivery.enqueue
    except Exception:
        enqueue = None
    return LiveSessionCertification(
        get_live_session_service(),
        CertificationThresholds(
            min_sessions=settings.live_session_cert_min_sessions,
            min_ready_session_ratio=settings.live_session_cert_min_ready_session_ratio,
            min_average_ready_ratio=settings.live_session_cert_min_average_ready_ratio,
            min_average_websocket_ratio=settings.live_session_cert_min_average_websocket_ratio,
            max_average_error_ratio=settings.live_session_cert_max_average_error_ratio,
            max_average_feed_age_sec=settings.live_session_cert_max_average_feed_age_sec,
        ),
        enqueue,
    )


@router.get("/api/live-session-certification/status")
def certification_status(limit_days: int = 30):
    return _service().evaluate(limit_days)


@router.post("/api/live-session-certification/notify", dependencies=[Depends(require_admin_token)])
def certification_notify(limit_days: int = 30):
    return _service().enqueue_report(limit_days)


_eod_scheduler: CertificationEodScheduler | None = None

def get_certification_eod_scheduler() -> CertificationEodScheduler:
    global _eod_scheduler
    if _eod_scheduler is None:
        _eod_scheduler = CertificationEodScheduler(
            lambda days: _service().enqueue_report(days),
            enabled=settings.live_session_cert_eod_enabled,
            run_time=settings.live_session_cert_eod_time,
            timezone_name=settings.app_timezone,
            poll_interval_sec=settings.live_session_cert_eod_poll_interval_sec,
        )
    return _eod_scheduler

@router.get("/api/live-session-certification/breakdown")
def certification_breakdown(limit_days: int = 30):
    return _service().breakdown(limit_days)

@router.get("/api/live-session-certification/eod-scheduler")
def certification_eod_scheduler_status():
    return get_certification_eod_scheduler().status()

@router.post("/api/live-session-certification/eod-scheduler/run", dependencies=[Depends(require_admin_token)])
def certification_eod_scheduler_run(force: bool = False):
    return get_certification_eod_scheduler().run_once(force=force)
