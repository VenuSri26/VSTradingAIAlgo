"""Durable, duplicate-safe shadow evidence for source consensus."""
from __future__ import annotations

import hashlib
import json
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from app.market_data_consensus import MarketDataEnvelopeV2, SourceConsensusDecision


class ConsensusShadowRecorder:
    def __init__(self, path: str, max_history: int = 2000):
        self.path = Path(path)
        self.max_history = max(10, max_history)
        self._lock = RLock()
        self._recent: deque[dict[str, Any]] = deque(maxlen=self.max_history)
        self._last_event_id: str | None = None
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines()[-self.max_history:]:
                self._recent.append(json.loads(line))
            if self._recent:
                self._last_event_id = self._recent[-1].get("event_id")
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self._recent.clear()
            self._last_event_id = None

    @staticmethod
    def _event_id(primary: MarketDataEnvelopeV2, decision: SourceConsensusDecision) -> str:
        raw = json.dumps({
            "instrument": primary.instrument,
            "exchange_timestamp": primary.exchange_timestamp,
            "sources": decision.evidence.get("observed_sources", []),
            "prices": [q.get("last_price") for q in decision.evidence.get("quotes", [])],
        }, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def record(self, primary: MarketDataEnvelopeV2, decision: SourceConsensusDecision) -> dict[str, Any]:
        event_id = self._event_id(primary, decision)
        with self._lock:
            if event_id == self._last_event_id:
                return {"recorded": False, "event_id": event_id, "reason": "DUPLICATE_EVIDENCE"}
            row = {
                "event_id": event_id,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "instrument": primary.instrument,
                "primary_source": primary.source,
                "primary_exchange_timestamp": primary.exchange_timestamp,
                "status": decision.status.value,
                "approved": decision.approved,
                "sources": decision.evidence.get("observed_sources", []),
                "fresh_sources": decision.evidence.get("fresh_sources", []),
                "consensus_price": decision.evidence.get("consensus_price"),
                "deviation_pct": decision.evidence.get("observed_deviation_pct"),
                "blockers": decision.blockers,
                "warnings": decision.warnings,
            }
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
            self._recent.append(row)
            self._last_event_id = event_id
            return {"recorded": True, **row}

    def history(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._recent)[-max(1, min(limit, self.max_history)):][::-1]

    def summary(self) -> dict[str, Any]:
        with self._lock:
            rows = list(self._recent)
        counts = Counter(str(row.get("status") or "UNKNOWN") for row in rows)
        deviations = [float(row["deviation_pct"]) for row in rows if row.get("deviation_pct") is not None]
        return {
            "mode": "SHADOW_ONLY",
            "samples": len(rows),
            "status_counts": dict(sorted(counts.items())),
            "verified_ratio": round(counts.get("VERIFIED", 0) / len(rows), 6) if rows else None,
            "average_deviation_pct": round(sum(deviations) / len(deviations), 6) if deviations else None,
            "max_deviation_pct": round(max(deviations), 6) if deviations else None,
            "latest": rows[-1] if rows else None,
            "live_orders_enabled": False,
        }


_recorder: ConsensusShadowRecorder | None = None


def get_consensus_shadow_recorder(path: str) -> ConsensusShadowRecorder:
    global _recorder
    if _recorder is None or str(_recorder.path) != str(Path(path)):
        _recorder = ConsensusShadowRecorder(path)
    return _recorder
