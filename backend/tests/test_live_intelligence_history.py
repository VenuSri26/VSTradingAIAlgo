from __future__ import annotations

import os
from datetime import datetime, timezone


def _sample(ce: float, pe: float, pcr: float):
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(), "spot": 25200, "atm_strike": 25200,
        "expiry": "2026-08-06", "contracts": 6, "completeness_pct": 100,
        "total_ce_oi": ce, "total_pe_oi": pe, "pcr_oi": pcr, "call_wall": 25300,
        "put_wall": 25100, "max_pain": 25200, "readiness_score": 100,
        "status": "READY", "recommended_action": "USE_FOR_DECISION_SUPPORT",
    }


def test_history_persists_and_trends(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "history.db"))
    import app.store as store
    import app.live_intelligence_history as history
    store.DB_PATH = os.environ["SQLITE_DB_PATH"]
    with store._conn() as conn:
        from app.migrations import apply_migrations
        apply_migrations(conn)
    history.record_snapshot(_sample(1000, 900, .9))
    history.record_snapshot(_sample(1050, 1200, 1.14))
    result = history.trend()
    assert result["samples"] == 2
    assert result["trend"] == "BULLISH_STRENGTHENING"
    assert result["pcr_change"] == .24


def test_history_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "empty.db"))
    import app.store as store
    import app.live_intelligence_history as history
    store.DB_PATH = os.environ["SQLITE_DB_PATH"]
    with store._conn() as conn:
        from app.migrations import apply_migrations
        apply_migrations(conn)
    assert history.trend()["trend"] == "NO_DATA"
