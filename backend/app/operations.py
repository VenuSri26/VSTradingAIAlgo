from __future__ import annotations

import json
import os
import shutil
import socket
import time
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.version import version_info

STARTED_AT = time.time()


def _memory() -> dict:
    values: dict[str, int] = {}
    try:
        for line in Path('/proc/meminfo').read_text().splitlines():
            key, value = line.split(':', 1)
            values[key] = int(value.strip().split()[0]) * 1024
    except (OSError, ValueError):
        return {"total_bytes": None, "available_bytes": None, "used_pct": None}
    total = values.get('MemTotal', 0)
    available = values.get('MemAvailable', 0)
    used_pct = round((total - available) / total * 100, 2) if total else None
    return {"total_bytes": total, "available_bytes": available, "used_pct": used_pct}


def _disk() -> dict:
    usage = shutil.disk_usage('/')
    return {
        "total_bytes": usage.total,
        "free_bytes": usage.free,
        "used_bytes": usage.used,
        "used_pct": round(usage.used / usage.total * 100, 2) if usage.total else None,
    }


def _load_average() -> list[float] | None:
    try:
        return [round(x, 2) for x in os.getloadavg()]
    except (AttributeError, OSError):
        return None


def system_snapshot() -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hostname": socket.gethostname(),
        "uptime_sec": round(time.time() - STARTED_AT, 1),
        "process_id": os.getpid(),
        "load_average": _load_average(),
        "memory": _memory(),
        "disk": _disk(),
        "trading_mode": settings.trading_mode,
        "paper_monitor_enabled": settings.paper_auto_monitor_enabled,
        "version": version_info()["version"],
    }


def recent_logs(limit: int = 100) -> dict:
    limit = max(1, min(limit, 500))
    path = Path(settings.log_file_path or '')
    if not path.exists() or not path.is_file():
        return {"path": str(path), "exists": False, "entries": []}
    lines = path.read_text(errors='replace').splitlines()[-limit:]
    entries = []
    for line in lines:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            entries.append({"message": line})
    return {"path": str(path), "exists": True, "entries": entries}


def deployment_snapshot() -> dict:
    candidates = [
        Path('/opt/vstradingai/shared/deployment/deployment_history.log'),
        Path('/opt/vstradingai/deployment/deployment_history.log'),
        Path('deployment/deployment_history.log'),
    ]
    history_path = next((p for p in candidates if p.exists()), None)
    history = history_path.read_text(errors='replace').splitlines()[-50:] if history_path else []
    current = None
    current_link = Path('/opt/vstradingai/current')
    try:
        if current_link.exists():
            current = str(current_link.resolve())
    except OSError:
        current = None
    backup_dirs = []
    for root in (Path('/opt/vstradingai/shared/deployment/backups'), Path('/opt/vstradingai/deployment/backups')):
        if root.exists():
            backup_dirs.extend(sorted((str(p) for p in root.iterdir() if p.is_dir()), reverse=True)[:20])
    return {"current_release": current, "history": history, "backups": backup_dirs[:20]}
