from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings, validate
from app.operations import deployment_snapshot, system_snapshot
from app.version import version_info


def _database_health() -> dict:
    path = Path("data/vstradingai.db")
    candidates = [path, Path("/opt/vstradingai/shared/data/vstradingai.db")]
    db_path = next((p for p in candidates if p.exists()), candidates[0])
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("select 1").fetchone()
            migrations = conn.execute("select count(*) from schema_migrations").fetchone()[0]
        return {"ok": True, "path": str(db_path), "migrations": migrations}
    except Exception as exc:
        return {"ok": False, "path": str(db_path), "error": str(exc)}


def _last_smoke_test() -> dict:
    paths = [
        Path("/opt/vstradingai/shared/deployment/last_smoke_test.json"),
        Path("deployment/last_smoke_test.json"),
    ]
    for path in paths:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return {"ok": False, "path": str(path), "error": "invalid smoke-test record"}
    return {"ok": None, "message": "No persisted smoke-test record yet"}


def release_certificate() -> dict:
    version = version_info()
    system = system_snapshot()
    deployment = deployment_snapshot()
    database = _database_health()
    config_problems = validate()
    checks = {
        "version_available": version["version"] != "0.0.0",
        "release_path_available": bool(version.get("release_path")) or version["environment"] == "development",
        "database": bool(database.get("ok")),
        "configuration": len(config_problems) == 0,
        "live_orders_safely_disabled": not settings.live_orders_enabled,
    }
    score = round(sum(1 for passed in checks.values() if passed) / len(checks) * 100)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if all(checks.values()) else "ATTENTION",
        "health_score": score,
        "checks": checks,
        "version": version,
        "system": system,
        "database": database,
        "deployment": deployment,
        "last_smoke_test": _last_smoke_test(),
        "configuration_problems": config_problems,
    }
