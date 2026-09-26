from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.setup_service import refresh_kite_token, save_preferences, status


def test_save_preferences_is_allowlisted_persistent_and_immediate(tmp_path, monkeypatch):
    target = tmp_path / "backend.env"
    target.write_text("LIVE_ORDERS_ENABLED=false\nUNRELATED=keep-me\n", encoding="utf-8")
    monkeypatch.setattr(settings, "paper_auto_trader_enabled", True)
    result = save_preferences(
        minimum_confidence=88, capital=75000,
        profit_withdrawal_threshold=125000, default_stop_loss_pct=12.5,
        path=target,
    )
    content = target.read_text(encoding="utf-8")
    assert result["saved"] is True
    assert settings.paper_auto_trader_min_score == 88
    assert settings.paper_capital == 75000
    assert "PAPER_DEFAULT_STOP_LOSS_PCT=12.5" in content
    assert "LIVE_ORDERS_ENABLED=false" in content
    assert "UNRELATED=keep-me" in content
    assert Path(result["backup"]).exists()


@pytest.mark.parametrize("field,value", [
    ("minimum_confidence", 69), ("capital", 9000),
    ("profit_withdrawal_threshold", -1), ("default_stop_loss_pct", 51),
])
def test_setup_preferences_reject_unsafe_ranges(tmp_path, field, value):
    values = dict(minimum_confidence=85, capital=10000,
                  profit_withdrawal_threshold=100000, default_stop_loss_pct=20)
    values[field] = value
    with pytest.raises(ValueError):
        save_preferences(**values, path=tmp_path / "backend.env")


def test_setup_status_never_exposes_secrets():
    result = status({"connected": True, "user_id": "AB1234"})
    assert result["execution_mode"] == "PAPER_ONLY"
    assert result["live_mode_locked"] is True
    assert result["secrets_exposed"] is False
    assert "kite_api_secret" not in result
    assert "kite_access_token" not in result


def test_ui_token_exchange_requires_https(monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "admin-test")
    with TestClient(app) as client:
        response = client.post(
            "/api/setup/zerodha/refresh",
            headers={"X-Admin-Token": "admin-test"},
            json={"redirect_url": "http://example.test/?request_token=abc123"},
        )
    assert response.status_code == 426
    assert "HTTPS" in response.json()["detail"]


def test_refresh_token_saves_verified_token_without_returning_it(tmp_path, monkeypatch):
    class KiteStub:
        def __init__(self, api_key, timeout=15): self.api_key = api_key
        def generate_session(self, token, api_secret):
            assert token == "request-123" and api_secret == "secret"
            return {"access_token": "private-access-token"}
        def set_access_token(self, token): self.token = token
        def profile(self): return {"user_id": "AB1234"}

    import kiteconnect
    monkeypatch.setattr(kiteconnect, "KiteConnect", KiteStub)
    monkeypatch.setattr(settings, "kite_api_key", "key")
    monkeypatch.setattr(settings, "kite_api_secret", "secret")
    monkeypatch.setattr(settings, "live_orders_enabled", False)
    target = tmp_path / "backend.env"
    result = refresh_kite_token("https://example.test/?request_token=request-123", path=target)
    assert result["connected"] is True
    assert result["access_token_exposed"] is False
    assert "private-access-token" not in str(result)
    assert "KITE_ACCESS_TOKEN=private-access-token" in target.read_text(encoding="utf-8")
