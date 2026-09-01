from datetime import datetime
from zoneinfo import ZoneInfo

from app.daily_digest_scheduler import DailyDigestScheduler


class DigestStub:
    def __init__(self, rows=None): self.rows = list(rows or []); self.generated = 0
    def history(self, limit=1): return list(reversed(self.rows[-limit:]))
    def generate(self, enqueue=False):
        self.generated += 1
        row = {"generated_at": "2026-08-06T10:30:00+00:00", "status": "READY", "enqueue": enqueue}
        self.rows.append(row)
        return row


def ist(hour, minute=0, day=6):
    return datetime(2026, 8, day, hour, minute, tzinfo=ZoneInfo("Asia/Kolkata"))


def test_scheduler_generates_once_after_configured_time():
    digest = DigestStub()
    scheduler = DailyDigestScheduler(digest, run_time="16:00", timezone_name="Asia/Kolkata", enqueue=True)
    first = scheduler.run_once(ist(16, 1))
    second = scheduler.run_once(ist(17, 0))
    assert first["generated"] is True
    assert first["digest"]["enqueue"] is True
    assert second["generated"] is False
    assert digest.generated == 1


def test_scheduler_does_not_run_before_time():
    scheduler = DailyDigestScheduler(DigestStub(), run_time="16:00", timezone_name="Asia/Kolkata")
    result = scheduler.run_once(ist(15, 59))
    assert result["generated"] is False
    assert result["reason"] == "NOT_DUE"


def test_scheduler_catches_up_after_restart():
    scheduler = DailyDigestScheduler(DigestStub(), run_time="16:00", timezone_name="Asia/Kolkata")
    assert scheduler.status(ist(18, 0))["due_now"] is True
    assert scheduler.run_once(ist(18, 0))["generated"] is True


def test_existing_digest_prevents_duplicate_same_day():
    existing = [{"generated_at": "2026-08-06T10:30:00+00:00", "status": "READY"}]
    scheduler = DailyDigestScheduler(DigestStub(existing), run_time="16:00", timezone_name="Asia/Kolkata")
    result = scheduler.run_once(ist(18, 0))
    assert result["generated"] is False
    assert result["last_run_day"] == "2026-08-06"
