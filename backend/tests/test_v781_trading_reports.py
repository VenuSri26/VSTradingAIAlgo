from datetime import datetime
from zoneinfo import ZoneInfo

from app import store
from app.trading_report import TradingReportService
from app.trading_report_scheduler import TradingReportScheduler

IST = ZoneInfo("Asia/Kolkata")


class KiteStub:
    def orders(self):
        return [
            {"order_id": "z-1", "tradingsymbol": "NIFTY26SEP23000CE", "transaction_type": "BUY", "quantity": 75, "status": "COMPLETE", "tag": "manual"},
            {"order_id": "other", "tradingsymbol": "BANKNIFTY26SEP50000CE", "status": "COMPLETE"},
        ]

    def trades(self):
        return [{"trade_id": "t-1", "order_id": "z-1", "tradingsymbol": "NIFTY26SEP23000CE", "quantity": 75, "average_price": 100}]

    def positions(self):
        return {"net": [{"tradingsymbol": "NIFTY26SEP23000CE", "quantity": 75}], "day": []}


class SourceStub:
    _kite = KiteStub()

    def token_health(self):
        return {"connected": True, "user_id": "test-user"}


def test_post_market_report_reconciles_read_only_broker_data(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "report.db"))
    monkeypatch.setattr("app.trading_report.paper_loop_readiness", lambda: {"offline_complete": True})
    monkeypatch.setattr("app.trading_report.risk_status", lambda: {"kill_switch": False})
    service = TradingReportService(str(tmp_path / "reports.jsonl"), lambda: SourceStub())
    report = service.generate("POST_MARKET", datetime(2026, 9, 28, 16, 0, tzinfo=IST))
    assert report["summary"]["zerodha_orders"] == 1
    assert report["summary"]["zerodha_trades"] == 1
    assert report["summary"]["unmatched_zerodha_orders"] == 1
    assert report["safety"]["broker_access"] == "READ_ONLY_REPORTING"
    assert report["safety"]["live_orders_enabled"] is False
    assert service.latest("POST_MARKET")["trading_day"] == "2026-09-28"


def test_pre_market_report_blocks_when_token_is_not_connected(tmp_path, monkeypatch):
    class OfflineSource:
        _kite = None
        def token_health(self):
            return {"connected": False}

    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "offline.db"))
    monkeypatch.setattr("app.trading_report.paper_loop_readiness", lambda: {"offline_complete": True})
    monkeypatch.setattr("app.trading_report.risk_status", lambda: {"kill_switch": False})
    service = TradingReportService(str(tmp_path / "reports.jsonl"), lambda: OfflineSource())
    report = service.build("PRE_MARKET", datetime(2026, 9, 28, 9, 1, tzinfo=IST))
    assert report["analysis"]["status"] == "BLOCKED"
    assert "Refresh" in report["analysis"]["message"]


def test_report_scheduler_skips_weekend_and_runs_once_on_trading_day(tmp_path, monkeypatch):
    class ServiceStub:
        def __init__(self): self.calls = 0
        def latest(self, _): return None
        def generate(self, report_type, now):
            self.calls += 1
            return {"report_type": report_type, "trading_day": now.date().isoformat(), "generated_at": now.isoformat()}

    monkeypatch.setattr("app.trading_report_scheduler.settings.market_holidays", "")
    service = ServiceStub()
    scheduler = TradingReportScheduler(service, "PRE_MARKET", "09:00")
    saturday = datetime(2026, 9, 26, 10, 0, tzinfo=IST)
    monday = datetime(2026, 9, 28, 9, 1, tzinfo=IST)
    assert scheduler.run_once(saturday)["generated"] is False
    assert scheduler.run_once(monday)["generated"] is True
    assert scheduler.run_once(monday)["generated"] is False
    assert service.calls == 1
