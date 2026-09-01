from datetime import datetime, timezone
import inspect

from app.pipeline import _pipeline_now, run_pipeline


def test_pipeline_clock_accepts_historical_override():
    historical = datetime(
        2026, 8, 11, 4, 30, 0,
        tzinfo=timezone.utc,
    )

    resolved = _pipeline_now(historical)

    assert resolved == historical
    assert resolved.tzinfo == timezone.utc


def test_pipeline_clock_normalizes_naive_datetime():
    historical = datetime(2026, 8, 11, 4, 30, 0)

    resolved = _pipeline_now(historical)

    assert resolved.tzinfo == timezone.utc
    assert resolved.year == 2026
    assert resolved.month == 8
    assert resolved.day == 11
    assert resolved.hour == 4
    assert resolved.minute == 30


def test_run_pipeline_exposes_replay_clock():
    params = inspect.signature(run_pipeline).parameters

    assert "as_of" in params
    assert params["as_of"].default is None
