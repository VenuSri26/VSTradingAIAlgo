"""Persistent NSE holiday calendar managed through an admin-protected API."""
from __future__ import annotations
import csv
import io
import json
from datetime import date
from pathlib import Path
from typing import Any


class MarketCalendarService:
    def __init__(self, path: str):
        self.path = Path(path)

    def list_holidays(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        return sorted(data if isinstance(data, list) else [], key=lambda x: x.get("date", ""))

    def replace(self, holidays: list[dict[str, Any]]) -> dict[str, Any]:
        cleaned = []
        seen = set()
        for item in holidays:
            value = str(item.get("date") or "")
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError(f"Invalid holiday date: {value}") from exc
            if value in seen:
                continue
            seen.add(value)
            cleaned.append({"date": value, "name": str(item.get("name") or "NSE Holiday")[:120]})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(sorted(cleaned, key=lambda x: x["date"]), indent=2), encoding="utf-8")
        return self.status()

    def import_text(self, content: str, format: str = "auto", replace: bool = True) -> dict[str, Any]:
        """Import holidays from JSON or CSV without fetching untrusted URLs."""
        fmt = (format or "auto").lower()
        stripped = content.strip()
        if fmt == "auto":
            fmt = "json" if stripped.startswith("[") or stripped.startswith("{") else "csv"
        if fmt == "json":
            parsed = json.loads(stripped or "[]")
            holidays = parsed.get("holidays", []) if isinstance(parsed, dict) else parsed
        elif fmt == "csv":
            reader = csv.DictReader(io.StringIO(content))
            holidays = [{"date": row.get("date") or row.get("Date"), "name": row.get("name") or row.get("Name") or "NSE Holiday"} for row in reader]
        else:
            raise ValueError("format must be auto, json or csv")
        if not isinstance(holidays, list):
            raise ValueError("holiday import must contain a list")
        if not replace:
            holidays = self.list_holidays() + holidays
        status = self.replace(holidays)
        return {**status, "imported": len(holidays), "format": fmt}

    def status(self) -> dict[str, Any]:
        rows = self.list_holidays()
        today = date.today().isoformat()
        future = [x for x in rows if x["date"] >= today]
        return {"count": len(rows), "next_holiday": future[0] if future else None,
                "path": str(self.path), "source": "ADMIN_MANAGED", "live_orders_enabled": False}
