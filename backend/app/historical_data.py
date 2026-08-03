"""
Historical NSE data fetcher for the backtest scaffold (app/backtest.py).

Unblocks the gap flagged in the project review: our backtest evaluator was
fully tested against synthetic data but had no real Nifty price history to
run against. This wires in `nsepython` for that — optional dependency,
never required for the core dashboard to run.

    pip install nsepython --break-system-packages

Falls back with a clear error (not a fabricated price series) if nsepython
isn't installed or the network call fails — the same "never fabricate"
principle as every other data source in this project.
"""
from __future__ import annotations
from datetime import datetime, timedelta
import pandas as pd

try:
    import nsepython  # noqa: F401
    _NSEPYTHON_AVAILABLE = True
except ImportError:
    _NSEPYTHON_AVAILABLE = False


class HistoricalDataUnavailable(Exception):
    pass


def nsepython_available() -> bool:
    return _NSEPYTHON_AVAILABLE


def fetch_nifty_history(start_date: str, end_date: str) -> pd.DataFrame:
    """start_date/end_date: 'DD-MM-YYYY' (nsepython's expected format).
    Returns a DataFrame[open, high, low, close, volume] indexed by date.
    Raises HistoricalDataUnavailable rather than returning a guessed series
    if nsepython isn't installed or the fetch fails — same contract as
    DataSource.get_ohlc in app/data_sources/base.py."""
    if not _NSEPYTHON_AVAILABLE:
        raise HistoricalDataUnavailable(
            "nsepython not installed. Run: pip install nsepython --break-system-packages"
        )
    try:
        from nsepython import nsefetch  # index history endpoint
        # NSE's index historical data API; nsepython's helper functions
        # change occasionally with NSE API updates — verify against
        # nsepython's current README before relying on this in production.
        url = (
            "https://www.nseindia.com/api/historical/indicesHistory"
            f"?indexType=NIFTY%2050&from={start_date}&to={end_date}"
        )
        data = nsefetch(url)
        records = data.get("data", {}).get("indexCloseOnlineRecords", [])
        if not records:
            raise HistoricalDataUnavailable(f"No data returned for {start_date} to {end_date}")
        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["EOD_TIMESTAMP"])
        df = df.rename(columns={
            "EOD_OPEN_INDEX_VAL": "open", "EOD_HIGH_INDEX_VAL": "high",
            "EOD_LOW_INDEX_VAL": "low", "EOD_CLOSE_INDEX_VAL": "close",
        })
        df["volume"] = 0  # index-level data has no volume field
        return df.set_index("date")[["open", "high", "low", "close", "volume"]].sort_index()
    except HistoricalDataUnavailable:
        raise
    except Exception as e:
        raise HistoricalDataUnavailable(f"nsepython fetch failed: {e}") from e


def make_price_lookup_for_backtest(option_side: str = "CE"):
    """Builds a price_lookup(timestamp, plan) callable matching the
    signature app.backtest.evaluate_audit_log expects. This is a REFERENCE
    implementation using Nifty spot history as a rough proxy for option
    premium movement (real option premium history would need NSE's F&O
    historical API or your own recorded ticks — spot-as-proxy is directionally
    useful for a first pass, not a precise premium simulation).

    Usage:
        from app.backtest import load_audit_log, evaluate_audit_log, summarize
        from app.historical_data import make_price_lookup_for_backtest
        records = load_audit_log(settings.audit_log_path)
        lookup = make_price_lookup_for_backtest()
        evals = evaluate_audit_log(records, lookup)
        print(summarize(evals))
    """
    def _lookup(timestamp: str, plan: dict):
        try:
            decision_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            return None
        start = decision_time.strftime("%d-%m-%Y")
        end = (decision_time + timedelta(days=3)).strftime("%d-%m-%Y")
        try:
            df = fetch_nifty_history(start, end)
        except HistoricalDataUnavailable:
            return None
        if df.empty:
            return None
        # crude proxy: scale spot moves into premium-equivalent moves using
        # the plan's own entry price as a base — replace with real option
        # tick history for production-grade backtesting
        spot_start = df["close"].iloc[0]
        entry = plan.get("ltp") or 0
        if spot_start == 0 or entry == 0:
            return None
        scale = entry / spot_start
        return df["close"] * scale

    return _lookup
