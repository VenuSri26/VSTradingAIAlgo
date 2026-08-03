"""
Abstract data source contract.

Both MockDataSource (for local/dev/demo work) and ZerodhaDataSource (for real
live trading) implement this exact interface. The pipeline never knows or
cares which one it is talking to — this is what lets us build/test the whole
agent stack without a broker connection, then swap in Zerodha with zero
changes to pipeline/agents/routes.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional
import pandas as pd


class DataSource(ABC):
    """Every method must either return real/live-derived data, or raise
    DataUnavailable — NEVER fabricate a plausible-looking number."""

    @abstractmethod
    def is_connected(self) -> bool: ...

    @abstractmethod
    def get_ohlc(self, timeframe: str, lookback: int) -> pd.DataFrame:
        """Returns DataFrame[open, high, low, close, volume] indexed by time,
        oldest first, ending at the last COMPLETED candle only (no lookahead —
        see spec section 38: never include an in-progress/incomplete candle)."""
        ...

    @abstractmethod
    def get_spot(self) -> float: ...

    @abstractmethod
    def get_vix(self) -> float: ...

    @abstractmethod
    def get_option_chain(self, atm_range: int = 5) -> dict: ...

    @abstractmethod
    def get_last_tick_timestamp(self) -> str: ...

    @property
    @abstractmethod
    def source_name(self) -> str: ...


class DataUnavailable(Exception):
    """Raised by a DataSource when a value cannot be honestly produced.
    Callers must surface this as NOT_AVAILABLE / DATA_ERROR — never catch
    and substitute a guessed value."""
    pass
