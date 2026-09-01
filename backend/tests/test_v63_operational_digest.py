from app.notification_delivery import NotificationDelivery
from app.notification_scheduler import NotificationScheduler
from app.operational_digest import OperationalDigestService


class CalendarStub:
    def __init__(self, count=2): self.count = count
    def status(self): return {"count": self.count, "next_holiday": {"date": "2026-10-02"} if self.count else None}


class GreeksStub:
    def __init__(self, samples=5): self.samples = samples
    def summary(self): return {"samples": self.samples, "status": "READY" if self.samples >= 5 else "COLLECTING"}


def make_digest(tmp_path, *, calendar_count=2, greek_samples=5):
    delivery = NotificationDelivery(str(tmp_path / "outbox.jsonl"))
    scheduler = NotificationScheduler(delivery, interval_sec=10, escalate_after_sec=60)
    digest = OperationalDigestService(str(tmp_path / "digest.jsonl"), delivery, CalendarStub(calendar_count), GreeksStub(greek_samples), scheduler)
    return delivery, digest


def test_ready_digest_persists_history(tmp_path):
    _, digest = make_digest(tmp_path)
    result = digest.generate()
    assert result["status"] == "DEGRADED"  # delivery channel intentionally disabled
    assert result["live_orders_enabled"] is False
    assert digest.status()["history_count"] == 1
    assert len(digest.history()) == 1


def test_digest_reports_failed_notifications_as_blocker(tmp_path):
    delivery, digest = make_digest(tmp_path)
    row = delivery.enqueue("FEED", "CRITICAL", "Feed failed", "REVIEW")
    rows = delivery._read(); rows[0]["status"] = "FAILED"; delivery._write(rows)
    result = digest.generate()
    assert result["status"] == "BLOCKED"
    assert "FAILED_NOTIFICATIONS_PRESENT" in result["blockers"]


def test_digest_can_enqueue_summary_without_enabling_orders(tmp_path):
    delivery, digest = make_digest(tmp_path)
    result = digest.generate(enqueue=True)
    assert result["live_orders_enabled"] is False
    items = delivery.list()
    assert items[0]["code"] == "DAILY_OPERATIONAL_DIGEST"
    assert items[0]["status"] == "PENDING"


def test_severity_routing_selects_configured_recipients(tmp_path, monkeypatch):
    delivery = NotificationDelivery(
        str(tmp_path / "outbox.jsonl"),
        smtp_host="smtp.test", smtp_from="from@test",
        smtp_to="default@test", smtp_to_critical="ops@test,owner@test",
    )
    captured = {}
    class FakeSMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def starttls(self): pass
        def login(self, *a): pass
        def send_message(self, message): captured["to"] = message["To"]
    monkeypatch.setattr("app.notification_delivery.smtplib.SMTP", FakeSMTP)
    row = delivery.enqueue("AUTH", "CRITICAL", "Authentication failed", "REFRESH")
    delivery._send_email(row)
    assert captured["to"] == "ops@test, owner@test"
    assert delivery.status()["severity_routing"]["CRITICAL"] == 2
