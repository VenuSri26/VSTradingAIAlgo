from app.resilience import resilience_status


def test_resilience_status_is_safe_by_default():
    status = resilience_status()
    assert status["overall"] in {"READY", "DEGRADED"}
    assert status["restart_safe"] is True
    assert status["paper_only"] is True
    assert len(status["checks"]) >= 6


def test_resilience_has_critical_checks():
    codes = {item["code"] for item in resilience_status()["checks"]}
    assert {"CONFIG", "DATABASE", "AUDIT_PATH", "POSITION_RECOVERY", "EXECUTION_SPINE"} <= codes
