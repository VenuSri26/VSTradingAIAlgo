from datetime import datetime, timedelta, timezone

from app.market_data_service import CandleAggregator, MarketDataSupervisor


class FakeSource:
    source_name = "FAKE"
    def token_health(self):
        return {"connected": True, "checked_at": datetime.now(timezone.utc).isoformat(), "user_id": "TEST"}
    def get_spot(self): return 25000.0
    def get_vix(self): return 14.5
    def get_option_chain(self, atm_range=8):
        return {"expiry": "2026-08-06", "chain": {"CE": [{"strike": 25000}], "PE": [{"strike": 25000}]}}
    def get_last_tick_timestamp(self): return datetime.now(timezone.utc).isoformat()
    def instrument_sync_status(self, force=False):
        return {"count": 1000, "expiry": "2026-08-06", "source": "FAKE"}


class BrokenSource:
    source_name = "BROKEN"
    def token_health(self): return {"connected": False}
    def get_spot(self): raise RuntimeError("feed unavailable")


def test_candle_aggregator_builds_3m_ohlc():
    agg = CandleAggregator(3)
    agg.add(100, datetime(2026, 8, 3, 9, 15, tzinfo=timezone.utc))
    agg.add(103, datetime(2026, 8, 3, 9, 16, tzinfo=timezone.utc))
    agg.add(99, datetime(2026, 8, 3, 9, 17, tzinfo=timezone.utc))
    candle = agg.snapshot()[0]
    assert candle["open"] == 100
    assert candle["high"] == 103
    assert candle["low"] == 99
    assert candle["close"] == 99
    assert candle["ticks"] == 3
    assert candle["finalized"] is False


def test_only_completed_candles_are_published_and_remain_immutable():
    agg = CandleAggregator(3)
    base = datetime(2026, 8, 3, 9, 15, tzinfo=timezone.utc)
    agg.add(100, base)
    agg.add(103, base + timedelta(minutes=1))
    assert agg.snapshot(include_current=False) == []

    agg.add(101, base + timedelta(minutes=3))
    completed = agg.snapshot(include_current=False)
    assert len(completed) == 1
    assert completed[0]["finalized"] is True
    assert completed[0]["close"] == 103

    assert agg.add(999, base + timedelta(minutes=2)) == "OUT_OF_ORDER"
    assert agg.snapshot(include_current=False) == completed


def test_duplicate_market_timestamp_cannot_mutate_forming_candle():
    agg = CandleAggregator(3)
    ts = datetime(2026, 8, 3, 9, 15, tzinfo=timezone.utc)
    assert agg.add(100, ts) == "ACCEPTED"
    assert agg.add(999, ts) == "DUPLICATE"
    candle = agg.snapshot()[0]
    assert candle["close"] == 100
    assert candle["ticks"] == 1


def test_market_data_poll_and_instrument_sync(tmp_path):
    supervisor = MarketDataSupervisor(str(tmp_path / "state.json"), 3, 30, False)
    state = supervisor.poll_once(FakeSource())
    assert state["connected"] is True
    assert state["authenticated"] is True
    assert state["fresh"] is True
    assert state["spot"] == 25000.0
    assert state["instruments_synced"] == 2
    sync = supervisor.sync_instruments(FakeSource())
    assert sync["count"] == 1000
    assert supervisor.snapshot()["instruments_synced"] == 1000


def test_market_data_failure_activates_safe_no_trade(tmp_path):
    supervisor = MarketDataSupervisor(str(tmp_path / "state.json"), 3, 30, False)
    state = supervisor.poll_once(BrokenSource())
    assert state["connected"] is False
    assert state["safe_no_trade"] is True
    assert state["consecutive_failures"] == 1
    assert "feed unavailable" in state["last_error"]


def test_market_data_missing_exchange_timestamp_fails_closed(tmp_path):
    class MissingTimestampSource(FakeSource):
        def get_last_tick_timestamp(self):
            return None

    supervisor = MarketDataSupervisor(str(tmp_path / "state.json"), 3, 30, False)
    state = supervisor.poll_once(MissingTimestampSource())
    assert state["connected"] is False
    assert state["safe_no_trade"] is True
    assert state["candles_3m"] == []
    assert "market timestamp unavailable" in state["last_error"]


def test_supervisor_publishes_only_finalized_three_minute_candles(tmp_path):
    class TimedSource(FakeSource):
        timestamp = datetime.now(timezone.utc) - timedelta(minutes=3)

        def get_last_tick_timestamp(self):
            return self.timestamp.isoformat()

    source = TimedSource()
    supervisor = MarketDataSupervisor(str(tmp_path / "state.json"), 3, 300, False)
    first = supervisor.poll_once(source)
    assert first["candles_3m"] == []

    source.timestamp += timedelta(minutes=3)
    second = supervisor.poll_once(source)
    assert len(second["candles_3m"]) == 1
    assert second["candles_3m"][0]["finalized"] is True
