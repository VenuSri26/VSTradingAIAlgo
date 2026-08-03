from pathlib import Path

from app import store
from app.institutional_flow_history import (
    detect_flow_anomalies, flow_trend, list_flow_history, record_flow_snapshot,
)


def _summary(score: float, pcr: float = 1.0):
    return {
        "institutional_flow_score": score,
        "institutional_bias": "BULLISH" if score > 12 else "BEARISH" if score < -12 else "NEUTRAL",
        "confidence": 70.0,
        "pcr": pcr,
        "pcr_trend": "FLAT",
        "components": [
            {"name":"OPTIONS_FLOW","score":score,"direction":"BULLISH","confidence":70,"reason":"test"}
        ],
        "warnings": [],
    }


def test_history_persists_and_builds_trend(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "flow.db"))
    record_flow_snapshot(_summary(10, 0.95), {"spot":25000})
    record_flow_snapshot(_summary(30, 1.10), {"spot":25020})
    rows = list_flow_history(limit=10)
    assert len(rows) == 2
    trend = flow_trend(limit=10, trading_day=rows[-1]["trading_day"])
    assert trend["samples"] == 2
    assert trend["score_change"] == 20.0
    assert trend["trend"] == "STRENGTHENING_BULLISH"


def test_anomaly_detects_rapid_reversal():
    recent = [{"pcr":1.0,"institutional_flow_score":35.0}]
    result = detect_flow_anomalies(_summary(-20, 1.0), recent)
    assert result["anomaly"] is True
    assert "RAPID_FLOW_REVERSAL" in result["codes"]


def test_missing_history_is_safe(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "empty.db"))
    result = flow_trend()
    assert result["samples"] == 0
    assert result["trend"] == "UNAVAILABLE"
