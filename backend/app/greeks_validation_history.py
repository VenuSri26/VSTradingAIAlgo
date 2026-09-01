"""Restart-safe broker Greeks validation history and session summary."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any


class GreeksValidationHistory:
    def __init__(self, path: str):
        self.path = Path(path)
        self._lock = RLock()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
        return rows

    def record(self, result: dict[str, Any], source: str = "BROKER") -> dict[str, Any]:
        item = {
            "captured_at": self._now(),
            "source": source,
            "status": result.get("status"),
            "option_type": result.get("option_type"),
            "strike": result.get("strike"),
            "spot": result.get("spot"),
            "iv_pct": result.get("iv_pct"),
            "provided_metrics": int(result.get("provided_metrics") or 0),
            "failed_metrics": int(result.get("failed_metrics") or 0),
            "recommended_action": result.get("recommended_action"),
            "comparisons": result.get("comparisons") or [],
            "live_orders_enabled": False,
        }
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(item, separators=(",", ":")) + "\n")
        return item

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._read()
        return list(reversed(rows[-max(1, min(int(limit), 1000)):]))

    def summary(self, limit: int = 200) -> dict[str, Any]:
        rows = self._read()[-max(1, min(int(limit), 2000)):]
        total = len(rows)
        passed = sum(1 for row in rows if row.get("status") == "PASS")
        failed = sum(1 for row in rows if row.get("status") == "FAIL")
        warnings = sum(1 for row in rows if row.get("status") in {"WARNING", "BLOCKED"})
        provided = sum(int(row.get("provided_metrics") or 0) for row in rows)
        metric_failures = sum(int(row.get("failed_metrics") or 0) for row in rows)
        pass_rate = round((passed / total * 100.0), 2) if total else None
        metric_match_rate = round(((provided - metric_failures) / provided * 100.0), 2) if provided else None
        return {
            "status": "READY" if total >= 5 and failed == 0 else ("DEGRADED" if total else "NO_DATA"),
            "samples": total,
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
            "pass_rate_pct": pass_rate,
            "metric_match_rate_pct": metric_match_rate,
            "last_validation_at": rows[-1].get("captured_at") if rows else None,
            "recommended_action": "USE_FOR_DECISION_SUPPORT" if total >= 5 and failed == 0 else "COLLECT_AND_REVIEW_LIVE_SAMPLES",
            "live_orders_enabled": False,
        }
