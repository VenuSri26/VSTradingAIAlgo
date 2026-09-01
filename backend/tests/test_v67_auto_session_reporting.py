from app.live_session_recorder import LiveSessionRecorder
from app.live_session_validation import LiveSessionValidation, SessionThresholds


def test_recorder_builds_and_persists_sample(tmp_path):
    svc = LiveSessionValidation(str(tmp_path / "session.jsonl"), SessionThresholds(min_samples=1))
    rec = LiveSessionRecorder(svc, interval_sec=5)
    row = rec.record_once(
        {"connected": True, "heartbeat_age_sec": 2, "last_error": None, "market_open": True},
        {"age_sec": 2, "authenticated": True, "market_open": True, "option_chain_ready": True, "blockers": [], "warnings": []},
        {"last_error": None},
    )
    assert row["ready"] is True
    assert rec.status()["recorded"] == 1
    assert len(svc.history()) == 1


def test_recorder_marks_runtime_error(tmp_path):
    svc = LiveSessionValidation(str(tmp_path / "session.jsonl"), SessionThresholds(min_samples=1))
    rec = LiveSessionRecorder(svc)
    row = rec.record_once(
        {"connected": False, "heartbeat_age_sec": 20, "last_error": "socket failed"},
        {"age_sec": 20, "authenticated": False, "market_open": True, "option_chain_ready": False, "blockers": ["AUTH"], "warnings": []},
        {"last_error": "bridge failed"},
    )
    assert row["ready"] is False
    assert "BROKER_AUTHENTICATION_INVALID" in row["blockers"]


def test_multi_session_report(tmp_path):
    svc = LiveSessionValidation(str(tmp_path / "session.jsonl"), SessionThresholds(min_samples=2, min_ready_ratio=.5, max_error_ratio=.5))
    for day in ("2026-08-04", "2026-08-05"):
        svc.record({"trading_day": day, "feed_age_sec": 1, "websocket_connected": True, "authenticated": True, "market_open": True, "option_chain_ready": True, "tick_bridge_ready": True})
        svc.record({"trading_day": day, "feed_age_sec": 2, "websocket_connected": True, "authenticated": True, "market_open": True, "option_chain_ready": True, "tick_bridge_ready": True})
    report = svc.multi_session_report()
    assert report["session_count"] == 2
    assert report["ready_session_count"] == 2
    assert report["recommended_action"] == "MULTI_SESSION_EVIDENCE_READY_FOR_REVIEW"
