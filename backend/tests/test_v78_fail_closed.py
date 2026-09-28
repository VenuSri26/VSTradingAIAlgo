from app.routes import get_institutional_flow_summary


class BrokenSource:
    def get_option_chain(self, atm_range=8):
        raise RuntimeError("Zerodha session not authenticated")


def test_institutional_flow_summary_fails_closed(monkeypatch):
    monkeypatch.setattr("app.routes.get_data_source", lambda: BrokenSource())

    result = get_institutional_flow_summary()

    assert result["status"] == "BLOCKED"
    assert result["recommended_action"] == "NO_TRADE"
    assert result["error_code"] == "MARKET_DATA_UNAVAILABLE"
    assert result["live_orders_enabled"] is False
