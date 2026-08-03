from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.config import settings


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("request_id", "pipeline_id", "path", "method", "status_code", "duration_ms", "event"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, separators=(",", ":"))


def configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    stream = logging.StreamHandler()
    stream.setFormatter(JsonFormatter() if settings.log_json else logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
    ))
    root.addHandler(stream)

    if settings.log_file_path:
        path = Path(settings.log_file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(path)
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)


@dataclass
class Alert:
    timestamp: str
    severity: str
    code: str
    message: str
    pipeline_id: str | None = None


_lock = threading.RLock()
_started = time.monotonic()
_pipeline_runs = 0
_pipeline_failures = 0
_pipeline_total_ms = 0.0
_pipeline_last_ms: float | None = None
_pipeline_last_success: str | None = None
_pipeline_last_failure: str | None = None
_stale_data_events = 0
_decisions: dict[str, int] = {}
_alerts: deque[Alert] = deque(maxlen=200)


def record_alert(severity: str, code: str, message: str, pipeline_id: str | None = None) -> None:
    alert = Alert(datetime.now(timezone.utc).isoformat(), severity, code, message, pipeline_id)
    with _lock:
        previous = _alerts[-1] if _alerts else None
        if previous and previous.code == code and previous.message == message:
            return
        _alerts.append(alert)
    logging.getLogger("vstradingai.alerts").warning(
        message, extra={"event": code, "pipeline_id": pipeline_id}
    )


def run_observed_pipeline(run_fn: Callable[..., Any], data_source: Any, **kwargs: Any) -> Any:
    global _pipeline_runs, _pipeline_failures, _pipeline_total_ms, _pipeline_last_ms
    global _pipeline_last_success, _pipeline_last_failure, _stale_data_events
    pipeline_id = str(uuid.uuid4())
    started = time.perf_counter()
    logger = logging.getLogger("vstradingai.pipeline")
    try:
        response = run_fn(data_source, **kwargs)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        now = datetime.now(timezone.utc).isoformat()
        decision = response.decision.decision.value
        with _lock:
            _pipeline_runs += 1
            _pipeline_total_ms += duration_ms
            _pipeline_last_ms = duration_ms
            _pipeline_last_success = now
            _decisions[decision] = _decisions.get(decision, 0) + 1
            health = response.system_health
            if getattr(health, "data_age_sec", None) is not None and health.data_age_sec > settings.max_data_age_sec:
                _stale_data_events += 1
                record_alert("AMBER", "STALE_DATA", f"Market data age is {health.data_age_sec:.1f}s", pipeline_id)
            if getattr(health, "overall", None) and getattr(health.overall, "value", str(health.overall)) == "RED":
                record_alert("RED", "SYSTEM_HEALTH_RED", "Pipeline reported RED system health", pipeline_id)
        logger.info(
            "pipeline_completed",
            extra={"event": "pipeline_completed", "pipeline_id": pipeline_id, "duration_ms": duration_ms},
        )
        return response
    except Exception as exc:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        with _lock:
            _pipeline_runs += 1
            _pipeline_failures += 1
            _pipeline_total_ms += duration_ms
            _pipeline_last_ms = duration_ms
            _pipeline_last_failure = datetime.now(timezone.utc).isoformat()
        record_alert("RED", "PIPELINE_FAILURE", str(exc), pipeline_id)
        logger.exception(
            "pipeline_failed",
            extra={"event": "pipeline_failed", "pipeline_id": pipeline_id, "duration_ms": duration_ms},
        )
        raise


def metrics_snapshot() -> dict[str, Any]:
    with _lock:
        avg = round(_pipeline_total_ms / _pipeline_runs, 2) if _pipeline_runs else None
        return {
            "uptime_sec": round(time.monotonic() - _started, 1),
            "pipeline_runs": _pipeline_runs,
            "pipeline_failures": _pipeline_failures,
            "pipeline_success_rate": round((_pipeline_runs - _pipeline_failures) / _pipeline_runs * 100, 2) if _pipeline_runs else None,
            "pipeline_avg_duration_ms": avg,
            "pipeline_last_duration_ms": _pipeline_last_ms,
            "pipeline_last_success": _pipeline_last_success,
            "pipeline_last_failure": _pipeline_last_failure,
            "stale_data_events": _stale_data_events,
            "decision_counts": dict(_decisions),
            "active_alerts": len(_alerts),
        }


def list_alerts(limit: int = 50) -> list[dict[str, Any]]:
    with _lock:
        return [asdict(a) for a in list(_alerts)[-max(1, min(limit, 200)):]][::-1]
