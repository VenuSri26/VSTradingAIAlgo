from email.message import EmailMessage

from app.notification_delivery import NotificationDelivery
from app.market_calendar_service import MarketCalendarService


def test_category_email_routing_overrides_severity(tmp_path, monkeypatch):
    sent: list[EmailMessage] = []

    class FakeSMTP:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def starttls(self): pass
        def login(self, username, password): pass
        def send_message(self, message): sent.append(message)

    monkeypatch.setattr("app.notification_delivery.smtplib.SMTP", FakeSMTP)
    svc = NotificationDelivery(
        str(tmp_path / "outbox.jsonl"),
        smtp_host="smtp.example.com",
        smtp_from="bot@example.com",
        smtp_to="default@example.com",
        smtp_to_critical="critical@example.com",
        smtp_to_broker="broker@example.com",
    )
    svc.enqueue("TOKEN_EXPIRED", "CRITICAL", "refresh token", "REFRESH", {"category": "BROKER"})
    result = svc.dispatch()
    assert result["delivered"] == 1
    assert sent[0]["To"] == "broker@example.com"


def test_whatsapp_adapter_delivers_with_bearer_token(tmp_path, monkeypatch):
    calls = []

    class FakeResponse:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): return False

    def fake_urlopen(req, timeout):
        calls.append((req, timeout))
        return FakeResponse()

    monkeypatch.setattr("app.notification_delivery.request.urlopen", fake_urlopen)
    svc = NotificationDelivery(
        str(tmp_path / "outbox.jsonl"),
        whatsapp_enabled=True,
        whatsapp_api_url="https://graph.example/messages",
        whatsapp_token="secret-token",
        whatsapp_to="919999999999",
    )
    svc.enqueue("FEED_DOWN", "CRITICAL", "feed disconnected", "CHECK_FEED", {"category": "INFRASTRUCTURE"})
    result = svc.dispatch()
    assert result["channels"]["whatsapp"] == 1
    assert calls
    assert calls[0][0].headers["Authorization"] == "Bearer secret-token"


def test_whatsapp_incomplete_configuration_remains_disabled(tmp_path):
    svc = NotificationDelivery(
        str(tmp_path / "outbox.jsonl"),
        whatsapp_enabled=True,
        whatsapp_api_url="https://graph.example/messages",
    )
    assert svc.whatsapp_enabled is False
    assert svc.delivery_enabled is False


def test_market_calendar_merge_deduplicates_synced_rows(tmp_path):
    svc = MarketCalendarService(str(tmp_path / "holidays.json"))
    svc.import_text("date,name\n2026-10-02,Gandhi Jayanti\n", "csv")
    result = svc.import_text(
        "date,name\n2026-10-02,Gandhi Jayanti\n2026-12-25,Christmas\n",
        "csv",
        replace=False,
    )
    assert result["count"] == 2
    assert [x["date"] for x in svc.list_holidays()] == ["2026-10-02", "2026-12-25"]
