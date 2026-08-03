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
    try:
        yield
    finally:
        for task in (monitor_task, market_data_task):
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
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


@app.get("/healthz")
def healthz():
    return {"status": "ok", "trading_mode": settings.trading_mode, **version_info()}
