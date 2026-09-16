from __future__ import annotations
import asyncio
import logging
import time
import uuid
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings, validate
from app.version import APP_VERSION, version_info
from app.observability import configure_logging

configure_logging()
logger = logging.getLogger("vstradingai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    problems = validate()
    if problems:
        logger.error("CONFIG VALIDATION FAILED on startup:")
        for p in problems:
            logger.error("  - %s", p)
        # Fail loud but don't crash the process outright in mock mode (dev
        # convenience); in live mode this should be a hard stop — enforce
        # via start_nifty.sh calling `python -m app.config` before boot.
        if settings.is_live():
            raise RuntimeError("Refusing to start in LIVE mode with invalid config: " + "; ".join(problems))
    else:
        logger.info("Config validated OK. TRADING_MODE=%s", settings.trading_mode)

    monitor_task = None
    market_data_task = None
    kite_runtime_task = None
    runtime_maintenance_task = None
    notification_scheduler_task = None
    daily_digest_scheduler_task = None
    live_session_recorder_task = None
    certification_eod_task = None
    from app.routes import get_data_source
    if settings.paper_auto_monitor_enabled:
        from app.paper_monitor import run_monitor_loop
        monitor_task = asyncio.create_task(run_monitor_loop(get_data_source))
    if settings.market_data_supervisor_enabled:
        from app.market_data_service import get_supervisor
        supervisor = get_supervisor(
            settings.market_data_state_path,
            settings.market_data_poll_interval_sec,
            settings.max_data_age_sec,
            settings.kite_websocket_requested,
        )
        market_data_task = asyncio.create_task(supervisor.run(get_data_source))
    if settings.is_live() and settings.kite_websocket_requested:
        from app.kite_ticker_runtime import get_kite_ticker_runtime
        runtime = get_kite_ticker_runtime()
        runtime.start()
        kite_runtime_task = asyncio.create_task(runtime.monitor_loop())
        from app.runtime_maintenance import get_runtime_maintenance
        from app.market_safety_routes import get_market_safety_status
        runtime_maintenance_task = asyncio.create_task(get_runtime_maintenance().run_loop(get_data_source, runtime, get_market_safety_status))
    if settings.notification_dispatch_enabled:
        from app.integration_readiness_routes import _scheduler
        notification_scheduler_task = asyncio.create_task(_scheduler.run_loop())
    if settings.daily_digest_enabled:
        from app.integration_readiness_routes import _daily_digest_scheduler
        daily_digest_scheduler_task = asyncio.create_task(_daily_digest_scheduler.run_loop())
    if settings.live_session_auto_record_enabled:
        from app.live_session_recorder import get_live_session_recorder
        from app.kite_ticker_runtime import get_kite_ticker_runtime
        from app.market_safety_routes import get_market_safety_status
        from app.tick_bridge_routes import tick_bridge_status
        live_session_recorder_task = asyncio.create_task(get_live_session_recorder().run_loop(
            lambda: get_kite_ticker_runtime().status(), get_market_safety_status, tick_bridge_status
        ))
    if settings.live_session_cert_eod_enabled:
        from app.live_session_certification_routes import get_certification_eod_scheduler
        certification_eod_task = asyncio.create_task(get_certification_eod_scheduler().run_loop())
    try:
        yield
    finally:
        for task in (monitor_task, market_data_task, kite_runtime_task, runtime_maintenance_task, notification_scheduler_task, daily_digest_scheduler_task, live_session_recorder_task, certification_eod_task):
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        if settings.is_live() and settings.kite_websocket_requested:
            from app.kite_ticker_runtime import get_kite_ticker_runtime
            get_kite_ticker_runtime().stop("application shutdown")
        logger.info("Shutting down VSTradingAI backend")


app = FastAPI(title="VSTradingAI - Nifty50 AI Trading Dashboard API", version=APP_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.middleware("http")
async def security_headers(request: Request, call_next):
    if settings.require_https and request.headers.get("x-forwarded-proto", request.url.scheme) != "https":
        return JSONResponse(status_code=426, content={"detail": "HTTPS is required"})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; connect-src 'self' ws: wss:; style-src 'self' 'unsafe-inline'; script-src 'self'"
    return response


@app.middleware("http")
async def request_observability(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_failed", extra={"request_id": request_id, "path": request.url.path, "method": request.method})
        raise
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    logger.info("request_completed", extra={"request_id": request_id, "path": request.url.path, "method": request.method, "status_code": response.status_code, "duration_ms": duration_ms})
    return response

from app.routes import router  # noqa: E402
app.include_router(router)
from app.market_safety_routes import router as market_safety_router  # noqa: E402
app.include_router(market_safety_router)
from app.feed_alert_routes import router as feed_alert_router  # noqa: E402
app.include_router(feed_alert_router)
from app.learning_routes import router as learning_router  # noqa: E402
app.include_router(learning_router)
from app.production_candidate_routes import router as production_candidate_router  # noqa: E402
app.include_router(production_candidate_router)
from app.resilience_routes import router as resilience_router  # noqa: E402
app.include_router(resilience_router)
from app.test_scenario_routes import router as test_scenario_router  # noqa: E402
app.include_router(test_scenario_router)
from app.live_intelligence_routes import router as live_intelligence_router  # noqa: E402
app.include_router(live_intelligence_router)
from app.live_paper_bridge_routes import router as live_paper_bridge_router  # noqa: E402
app.include_router(live_paper_bridge_router)
from app.tick_bridge_routes import router as tick_bridge_router  # noqa: E402
app.include_router(tick_bridge_router)
from app.kite_stream_routes import router as kite_stream_router  # noqa: E402
app.include_router(kite_stream_router)
from app.kite_ticker_runtime_routes import router as kite_ticker_runtime_router  # noqa: E402
app.include_router(kite_ticker_runtime_router)
from app.runtime_maintenance_routes import router as runtime_maintenance_router  # noqa: E402
app.include_router(runtime_maintenance_router)
from app.integration_readiness_routes import router as integration_readiness_router  # noqa: E402
app.include_router(integration_readiness_router)
from app.live_session_validation_routes import router as live_session_validation_router  # noqa: E402
app.include_router(live_session_validation_router)
from app.live_session_certification_routes import router as live_session_certification_router  # noqa: E402
app.include_router(live_session_certification_router)
from app.live_market_routes import router as live_market_router  # noqa: E402
app.include_router(live_market_router)
from app.market_data_consensus_routes import router as market_data_consensus_router  # noqa: E402
app.include_router(market_data_consensus_router)


@app.get("/healthz")
def healthz():
    return {"status": "ok", "trading_mode": settings.trading_mode, **version_info()}
