from app.live_session_validation import LiveSessionValidation, SessionThresholds
from app.live_session_certification import LiveSessionCertification, CertificationThresholds


def _record_day(service, day, ready=True, count=2):
    for _ in range(count):
        service.record({
            "trading_day": day,
            "feed_age_sec": 2 if ready else 20,
            "websocket_connected": ready,
            "authenticated": True,
            "market_open": True,
            "option_chain_ready": True,
            "tick_bridge_ready": True,
            "errors": [],
        })


def test_certification_passes_multiple_ready_sessions(tmp_path):
    service = LiveSessionValidation(str(tmp_path / "evidence.jsonl"), SessionThresholds(min_samples=2, min_ready_ratio=.9))
    for day in ("2026-08-03", "2026-08-04", "2026-08-05"):
        _record_day(service, day, True)
    cert = LiveSessionCertification(service, CertificationThresholds(min_sessions=3, min_ready_session_ratio=1, min_average_ready_ratio=.9, min_average_websocket_ratio=.8))
    result = cert.evaluate()
    assert result["status"] == "CERTIFIED"
    assert result["live_orders_enabled"] is False


def test_certification_blocks_insufficient_sessions(tmp_path):
    service = LiveSessionValidation(str(tmp_path / "evidence.jsonl"), SessionThresholds(min_samples=2, min_ready_ratio=.9))
    _record_day(service, "2026-08-05", True)
    result = LiveSessionCertification(service, CertificationThresholds(min_sessions=3)).evaluate()
    assert result["status"] == "BLOCKED"
    assert "INSUFFICIENT_VALIDATED_SESSIONS" in result["blockers"]


def test_certification_blocks_bad_session_ratio(tmp_path):
    service = LiveSessionValidation(str(tmp_path / "evidence.jsonl"), SessionThresholds(min_samples=2, min_ready_ratio=.9))
    _record_day(service, "2026-08-04", True)
    _record_day(service, "2026-08-05", False)
    result = LiveSessionCertification(service, CertificationThresholds(min_sessions=2, min_ready_session_ratio=.75)).evaluate()
    assert result["status"] == "BLOCKED"
    assert "READY_SESSION_RATIO_BELOW_TARGET" in result["blockers"]


def test_certification_notification_is_enqueued(tmp_path):
    service = LiveSessionValidation(str(tmp_path / "evidence.jsonl"), SessionThresholds(min_samples=1, min_ready_ratio=.9))
    _record_day(service, "2026-08-05", True, 1)
    calls=[]
    cert = LiveSessionCertification(service, CertificationThresholds(min_sessions=1), lambda *args: calls.append(args) or {"id":"n1"})
    result=cert.enqueue_report()
    assert result["enqueued"] is True
    assert calls[0][0] == "LIVE_SESSION_CERTIFICATION"
