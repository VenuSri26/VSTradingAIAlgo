from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app import eod_session_seal, execution_spine

IST = ZoneInfo("Asia/Kolkata")


def test_entry_cutoff_blocks_new_submission(monkeypatch):
    monkeypatch.setattr(execution_spine.settings, "execution_entry_cutoff_time", "15:15")
    result = execution_spine.entry_window_status(datetime(2026, 9, 16, 15, 15, tzinfo=IST))
    assert result["approved"] is False
    assert result["blocker"] == "ENTRY_CUTOFF_REACHED"


def test_eod_seal_is_not_available_before_cutoff(monkeypatch):
    monkeypatch.setattr(eod_session_seal.settings, "execution_eod_seal_time", "15:25")
    with pytest.raises(ValueError, match="EOD_SEAL_NOT_DUE"):
        eod_session_seal.seal_session(now=datetime(2026, 9, 16, 15, 24, tzinfo=IST))


def _safe_local_state(monkeypatch):
    monkeypatch.setattr(eod_session_seal.settings, "execution_eod_seal_time", "15:25")
    monkeypatch.setattr(eod_session_seal.settings, "trading_mode", "mock")
    monkeypatch.setattr(eod_session_seal, "blocking_exposure", lambda: [])
    monkeypatch.setattr(eod_session_seal.store, "get_open_position", lambda: None)
    monkeypatch.setattr(eod_session_seal.store, "get_open_paper_trade", lambda: None)


def test_flat_mock_session_seals_with_durable_event(monkeypatch):
    _safe_local_state(monkeypatch)
    events = []
    monkeypatch.setattr(eod_session_seal, "record_event", lambda execution_id, event, detail: events.append(event))
    monkeypatch.setattr(eod_session_seal.store, "set_kill_switch", lambda *args: (_ for _ in ()).throw(AssertionError("must not latch")))
    result = eod_session_seal.seal_session(now=datetime(2026, 9, 16, 15, 25, tzinfo=IST))
    assert result["sealed"] is True
    assert events == ["EOD_SESSION_SEALED"]


def test_nonflat_session_latches_kill_switch(monkeypatch):
    _safe_local_state(monkeypatch)
    monkeypatch.setattr(eod_session_seal.store, "get_open_position", lambda: {"id": 7})
    latched = []
    monkeypatch.setattr(eod_session_seal.store, "set_kill_switch", lambda enabled, reason: latched.append((enabled, reason)))
    monkeypatch.setattr(eod_session_seal, "record_event", lambda *args: None)
    result = eod_session_seal.seal_session(now=datetime(2026, 9, 16, 15, 30, tzinfo=IST))
    assert result["sealed"] is False
    assert "POSITION_NOT_FLAT" in result["blockers"]
    assert latched[0][0] is True


def test_unresolved_execution_prevents_seal(monkeypatch):
    _safe_local_state(monkeypatch)
    monkeypatch.setattr(eod_session_seal, "blocking_exposure", lambda: [{"execution_id": "exec-1"}])
    monkeypatch.setattr(eod_session_seal.store, "set_kill_switch", lambda *args: None)
    monkeypatch.setattr(eod_session_seal, "record_event", lambda *args: None)
    result = eod_session_seal.seal_session(now=datetime(2026, 9, 16, 15, 30, tzinfo=IST))
    assert result["sealed"] is False
    assert result["unresolved_execution_ids"] == ["exec-1"]
