from datetime import datetime, timedelta, timezone

from app.notification_delivery import NotificationDelivery
from app.notification_scheduler import NotificationScheduler


def test_acknowledge_pending_notification(tmp_path):
    delivery = NotificationDelivery(str(tmp_path / "outbox.jsonl"))
    item = delivery.enqueue("TOKEN", "WARNING", "Refresh token", "REVIEW")
    ack = delivery.acknowledge(item["id"], "handled")
    assert ack["status"] == "ACKNOWLEDGED"
    assert ack["acknowledgement_note"] == "handled"


def test_critical_notification_escalates_once(tmp_path):
    delivery = NotificationDelivery(str(tmp_path / "outbox.jsonl"))
    item = delivery.enqueue("AUTH", "CRITICAL", "Authentication failed", "REFRESH")
    rows = delivery._read()
    rows[0]["created_at"] = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    delivery._write(rows)
    assert delivery.escalate_pending(60)["escalated"] == 1
    assert delivery.escalate_pending(60)["escalated"] == 0
    saved = delivery._read()[0]
    assert saved["escalation_level"] == 1
    assert saved["action"].startswith("ESCALATED:")


def test_retry_backoff_and_max_attempts(tmp_path):
    delivery = NotificationDelivery(
        str(tmp_path / "outbox.jsonl"), retry_base_sec=10, retry_max_sec=40, max_attempts=2
    )
    delivery.enqueue("FEED", "WARNING", "Feed stale", "WAIT")
    first = delivery.dispatch()
    assert first["processed"] == 1
    row = delivery._read()[0]
    assert row["attempts"] == 1
    assert row["next_attempt_at"] is not None
    row["next_attempt_at"] = datetime.now(timezone.utc).isoformat()
    delivery._write([row])
    delivery.dispatch()
    row = delivery._read()[0]
    row["next_attempt_at"] = datetime.now(timezone.utc).isoformat()
    delivery._write([row])
    delivery.dispatch()
    assert delivery._read()[0]["status"] == "FAILED"


def test_scheduler_runs_safely_when_delivery_disabled(tmp_path):
    delivery = NotificationDelivery(str(tmp_path / "outbox.jsonl"))
    delivery.enqueue("TEST", "INFO", "Test", "NONE")
    scheduler = NotificationScheduler(delivery, interval_sec=10, escalate_after_sec=60)
    result = scheduler.run_once()
    assert result["runs"] == 1
    assert result["outbox"]["pending"] == 1
    assert result["live_orders_enabled"] is False
