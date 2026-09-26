from app import store
from app.config import settings, validate
from app.paper_loop_readiness import paper_loop_readiness


def _valid(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "readiness.db"))
    monkeypatch.setattr(settings, "paper_notification_path", str(tmp_path / "paper.jsonl"))
    monkeypatch.setattr(settings, "paper_auto_trader_enabled", True)
    monkeypatch.setattr(settings, "paper_auto_monitor_enabled", True)
    monkeypatch.setattr(settings, "live_orders_enabled", False)
    monkeypatch.setattr(settings, "paper_auto_trader_interval_sec", 15)
    monkeypatch.setattr(settings, "paper_monitor_interval_sec", 5)
    monkeypatch.setattr(settings, "paper_auto_trader_min_score", 85)
    monkeypatch.setattr(settings, "paper_auto_trader_grades", "A,A+")
    monkeypatch.setattr(settings, "paper_monitor_max_age_sec", 30)
    monkeypatch.setattr(settings, "execution_entry_cutoff_time", "15:15")
    monkeypatch.setattr(settings, "paper_eod_exit_time", "15:20")
    monkeypatch.setattr(settings, "market_close_time", "15:30")


def test_readiness_reports_only_live_evidence_pending(tmp_path, monkeypatch):
    _valid(monkeypatch, tmp_path)
    result = paper_loop_readiness()
    assert result["status"] == "OFFLINE_COMPLETE_LIVE_PENDING"
    assert result["offline_complete"] is True
    assert result["live_market_pending"] is True
    assert result["failed_checks"] == []
    assert result["live_orders_enabled"] is False


def test_config_rejects_autonomous_paper_with_live_orders(tmp_path, monkeypatch):
    _valid(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "live_orders_enabled", True)
    problems = validate()
    assert "PAPER_AUTO_TRADER_ENABLED requires LIVE_ORDERS_ENABLED=false" in problems
    result = paper_loop_readiness()
    assert result["status"] == "OFFLINE_BLOCKED"
    assert any(check["code"] == "PAPER_ONLY" for check in result["failed_checks"])
