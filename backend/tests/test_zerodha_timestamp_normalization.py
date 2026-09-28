from datetime import datetime, timezone

from app.data_sources.zerodha_client import _exchange_timestamp_iso


def test_naive_kite_timestamp_is_treated_as_ist_and_converted_to_utc():
    result = _exchange_timestamp_iso(datetime(2026, 9, 21, 12, 30))
    assert result == "2026-09-21T07:00:00+00:00"


def test_aware_kite_timestamp_is_converted_to_utc():
    value = datetime(2026, 9, 21, 7, 0, tzinfo=timezone.utc)
    assert _exchange_timestamp_iso(value) == "2026-09-21T07:00:00+00:00"


def test_missing_timestamp_remains_missing():
    assert _exchange_timestamp_iso(None) is None
