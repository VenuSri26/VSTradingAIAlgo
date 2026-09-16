"""
ZerodhaDataSource — real broker integration via the official `kiteconnect` SDK.

This is the ONLY class permitted to run when TRADING_MODE=live (enforced in
config.py). It never fabricates data: every method either returns a genuine
value from Kite, or raises DataUnavailable, which the pipeline/agents must
propagate as NOT_AVAILABLE / STALE / DATA_ERROR (never a guessed number).

SETUP (do this on your machine, not here):
    pip install kiteconnect
    Set KITE_API_KEY, KITE_API_SECRET in your canonical .env (see .env.example)
    Generate KITE_ACCESS_TOKEN daily via the login flow (token expires daily —
    this is exactly the class of bug described in spec section 28; this class
    validates the token on init instead of failing silently mid-session).
"""
from __future__ import annotations
import time
import pandas as pd
from datetime import date, datetime, timezone
from .base import DataSource, DataUnavailable

NIFTY_INSTRUMENT_TOKEN = 256265  # NSE:NIFTY 50 index token (verify against your Kite instrument dump)
INDIA_VIX_TOKEN = 264969         # NSE:INDIA VIX


class ZerodhaDataSource(DataSource):
    def __init__(self, api_key: str, access_token: str, cache_ttl_sec: float = 1.5):
        try:
            from kiteconnect import KiteConnect
        except ImportError as e:
            raise RuntimeError(
                "kiteconnect SDK not installed. Run: pip install kiteconnect --break-system-packages"
            ) from e

        self._kite = KiteConnect(api_key=api_key)
        self._kite.set_access_token(access_token)
        self._cache_ttl = cache_ttl_sec
        self._cache: dict[str, tuple[float, object]] = {}
        self._connected = self._validate_token()
        self._last_market_timestamp: str | None = None
        self._instrument_cache_day: date | None = None
        self._instrument_cache: list[dict] | None = None

    # ---- connection / token validation -----------------------------------
    def _validate_token(self) -> bool:
        """Section 28 requirement: validate on startup, never assume the
        token is good and fail silently mid-session."""
        try:
            profile = self._kite.profile()
            return bool(profile.get("user_id"))
        except Exception:
            return False

    def is_connected(self) -> bool:
        return self._connected

    @property
    def source_name(self) -> str:
        return "ZERODHA"

    def _cached(self, key: str, fn):
        now = time.time()
        if key in self._cache:
            ts, val = self._cache[key]
            if now - ts < self._cache_ttl:
                return val
        val = fn()
        self._cache[key] = (now, val)
        return val


    def token_health(self) -> dict:
        """Return non-secret Zerodha session health for dashboards and AWS checks."""
        checked_at = datetime.now(timezone.utc).isoformat()
        if not self._connected:
            return {"connected": False, "checked_at": checked_at, "source": self.source_name}
        try:
            profile = self._kite.profile()
            return {
                "connected": bool(profile.get("user_id")),
                "checked_at": checked_at,
                "source": self.source_name,
                "user_id": profile.get("user_id"),
            }
        except Exception as exc:
            self._connected = False
            return {"connected": False, "checked_at": checked_at, "source": self.source_name, "error": str(exc)}

    def _get_nfo_instruments(self) -> list[dict]:
        """Cache the large NFO instrument dump once per UTC day.

        Zerodha's instrument master is not tick data and should not be fetched
        on every option-chain request. The cache refreshes automatically daily.
        """
        today = datetime.now(timezone.utc).date()
        if self._instrument_cache is not None and self._instrument_cache_day == today:
            return self._instrument_cache
        try:
            instruments = self._kite.instruments("NFO")
        except Exception as exc:
            if self._instrument_cache is not None:
                return self._instrument_cache
            raise DataUnavailable(f"Zerodha instrument dump failed: {exc}") from exc
        self._instrument_cache = instruments
        self._instrument_cache_day = today
        return instruments

    def instrument_sync_status(self, force: bool = False) -> dict:
        """Refresh and report the NFO instrument master without exposing secrets."""
        if force:
            self._instrument_cache = None
            self._instrument_cache_day = None
        instruments = self._get_nfo_instruments()
        nifty = [i for i in instruments if i.get("name") == "NIFTY" and i.get("segment") == "NFO-OPT"]
        today = datetime.now(timezone.utc).date()
        expiries = sorted({i.get("expiry") for i in nifty if i.get("expiry") and i.get("expiry") >= today})
        return {
            "count": len(nifty),
            "expiry": str(expiries[0]) if expiries else None,
            "available_expiries": [str(x) for x in expiries[:8]],
            "cache_day": str(self._instrument_cache_day) if self._instrument_cache_day else None,
            "source": self.source_name,
        }

    # ---- market data --------------------------------------------------
    def get_ohlc(self, timeframe: str, lookback: int) -> pd.DataFrame:
        if not self._connected:
            raise DataUnavailable("Zerodha session not authenticated")
        interval_map = {"1m": "minute", "3m": "3minute", "5m": "5minute",
                         "15m": "15minute", "1d": "day"}
        interval = interval_map.get(timeframe)
        if interval is None:
            raise DataUnavailable(f"Unsupported timeframe {timeframe}")
        try:
            now = datetime.now(timezone.utc)

            # Timeframe-aware historical warm-up.
            # Intraday indicators need enough recent minutes plus a prior session.
            # Daily candles need calendar-day history; using minutes here previously
            # fetched only ~1 day and left zero completed daily candles after
            # the no-lookahead filter removed today's forming candle.
            if timeframe == "1d":
                from_date = now - pd.Timedelta(days=max(lookback * 3, 15))
            else:
                from_date = now - pd.Timedelta(
                    minutes=lookback * 20 + 1440
                )

            candles = self._kite.historical_data(
                NIFTY_INSTRUMENT_TOKEN,
                from_date,
                now,
                interval,
            )
        except Exception as e:
            raise DataUnavailable(f"Zerodha historical_data failed: {e}") from e
        if not candles:
            raise DataUnavailable("Zerodha returned no candles")
        df = pd.DataFrame(candles).rename(columns=str.lower)
        df = df.set_index("date").tail(lookback)
        if len(df):
            self._last_market_timestamp = pd.Timestamp(df.index[-1]).to_pydatetime().isoformat()
        # NO LOOKAHEAD: drop the last candle if it is still forming
        if len(df) and df.index[-1] > datetime.now(timezone.utc) - pd.Timedelta(
            minutes={"1m": 1, "3m": 3, "5m": 5, "15m": 15, "1d": 1440}[timeframe]
        ):
            df = df.iloc[:-1]
        return df[["open", "high", "low", "close", "volume"]]

    def get_spot(self) -> float:
        if not self._connected:
            raise DataUnavailable("Zerodha session not authenticated")
        try:
            quote = self._cached("ltp_nifty", lambda: self._kite.ltp(["NSE:NIFTY 50"]))
            return float(quote["NSE:NIFTY 50"]["last_price"])
        except Exception as e:
            raise DataUnavailable(f"Zerodha LTP fetch failed: {e}") from e

    def get_vix(self) -> float:
        if not self._connected:
            raise DataUnavailable("Zerodha session not authenticated")
        try:
            quote = self._cached("ltp_vix", lambda: self._kite.ltp(["NSE:INDIA VIX"]))
            return float(quote["NSE:INDIA VIX"]["last_price"])
        except Exception as e:
            raise DataUnavailable(f"Zerodha VIX fetch failed: {e}") from e

    def get_option_chain(self, atm_range: int = 5) -> dict:
        if not self._connected:
            raise DataUnavailable("Zerodha session not authenticated")
        instruments = self._get_nfo_instruments()
        spot = self.get_spot()
        atm = round(spot / 50) * 50
        strikes = {atm + i * 50 for i in range(-atm_range, atm_range + 1)}
        nifty_opts = [
            i for i in instruments
            if i.get("name") == "NIFTY" and i.get("strike") in strikes and i.get("segment") == "NFO-OPT"
        ]
        # nearest expiry only
        if not nifty_opts:
            raise DataUnavailable("No matching NIFTY option instruments found")
        today = datetime.now(timezone.utc).date()
        valid_expiries = [i["expiry"] for i in nifty_opts if i.get("expiry") and i["expiry"] >= today]
        if not valid_expiries:
            raise DataUnavailable("No unexpired NIFTY option instruments found")
        nearest_expiry = min(valid_expiries)
        nifty_opts = [i for i in nifty_opts if i["expiry"] == nearest_expiry]
        symbols = [f"NFO:{i['tradingsymbol']}" for i in nifty_opts]
        try:
            quotes = self._kite.quote(symbols)
        except Exception as e:
            raise DataUnavailable(f"Zerodha option quote fetch failed: {e}") from e

        chain = {"CE": [], "PE": []}
        for inst in nifty_opts:
            q = quotes.get(f"NFO:{inst['tradingsymbol']}", {})
            side = "CE" if inst["instrument_type"] == "CE" else "PE"
            chain[side].append({
                "exchange": inst.get("exchange"),
                "segment": inst.get("segment"),
                "expiry": str(inst.get("expiry")) if inst.get("expiry") else None,
                "option_type": inst.get("instrument_type"),
                "strike": inst["strike"],
                "ltp": q.get("last_price"),
                "oi": q.get("oi"),
                # Kite quote does not provide previous-session OI. Do not
                # mislabel oi_day_high as OI change; persist a baseline later.
                "oi_change": None,
                "volume": q.get("volume"),
                "iv": None,  # requires separate IV calc / Kite does not provide directly
                "bid": (q.get("depth", {}).get("buy") or [{}])[0].get("price"),
                "ask": (q.get("depth", {}).get("sell") or [{}])[0].get("price"),
                "lot_size": inst.get("lot_size"),
                "tick_size": inst.get("tick_size"),
                "tradingsymbol": inst.get("tradingsymbol"),
                "instrument_token": inst.get("instrument_token"),
                "quote_timestamp": (q.get("timestamp") or q.get("last_trade_time")).isoformat()
                    if hasattr((q.get("timestamp") or q.get("last_trade_time")), "isoformat") else None,
            })
            qts = q.get("timestamp") or q.get("last_trade_time")
            if qts is not None and hasattr(qts, "isoformat"):
                self._last_market_timestamp = qts.isoformat()
        return {"atm": atm, "spot": spot, "chain": chain, "expiry": str(nearest_expiry)}

    # ---- order placement -------------------------------------------------
    # NOT called automatically anywhere in this project. Positions are
    # tracked via app/store.py's manual open/close endpoints — you place the
    # order yourself (here, or in the Kite app) and then record it. Wiring
    # these into an automatic "AI decides -> AI places order" flow is a
    # deliberate scope boundary, not an oversight: spec section 46 and the
    # project's whole design keep a human in the loop before real capital
    # moves. These methods exist so that loop is a button click, not a
    # manual Kite Connect API call, once you decide to close that gap.

    def place_order(self, tradingsymbol: str, transaction_type: str, quantity: int,
                     order_type: str = "MARKET", product: str = "MIS", price: float | None = None,
                     trigger_price: float | None = None, variety: str = "regular") -> str:
        """transaction_type: 'BUY' or 'SELL'. Returns the Kite order_id.
        Standard place_order — for large Nifty option quantities that may
        exceed the exchange freeze limit, use place_autoslice_order instead."""
        try:
            return self._kite.place_order(
                variety=variety, exchange="NFO", tradingsymbol=tradingsymbol,
                transaction_type=transaction_type, quantity=quantity, product=product,
                order_type=order_type, price=price, trigger_price=trigger_price,
            )
        except Exception as e:
            raise DataUnavailable(f"Zerodha place_order failed: {e}") from e

    def place_autoslice_order(self, tradingsymbol: str, transaction_type: str, quantity: int,
                               order_type: str = "MARKET", product: str = "MIS",
                               price: float | None = None) -> list[str]:
        """Uses pykiteconnect's place_autoslice_order, which automatically
        splits an order exceeding the exchange freeze limit into multiple
        orders instead of the whole order being rejected. Falls back to a
        single place_order if the installed kiteconnect version predates
        this method (added in a recent pykiteconnect release — verify
        `pip show kiteconnect` supports it; check the official repo's
        CHANGELOG if unsure). Returns a list of order_ids (one order_id if
        no slicing was needed)."""
        if hasattr(self._kite, "place_autoslice_order"):
            try:
                result = self._kite.place_autoslice_order(
                    variety="regular", exchange="NFO", tradingsymbol=tradingsymbol,
                    transaction_type=transaction_type, quantity=quantity, product=product,
                    order_type=order_type, price=price,
                )
                # SDK returns either a single order_id or a list depending
                # on whether slicing actually occurred — normalise to a list
                return result if isinstance(result, list) else [result]
            except Exception as e:
                raise DataUnavailable(f"Zerodha place_autoslice_order failed: {e}") from e
        # older SDK without autoslice support — single order, exchange will
        # reject it directly if it's over the freeze limit rather than silently failing
        order_id = self.place_order(tradingsymbol, transaction_type, quantity, order_type, product, price)
        return [order_id]

    def get_last_tick_timestamp(self) -> str:
        if not self._connected:
            raise DataUnavailable("Zerodha session not authenticated")
        if not self._last_market_timestamp:
            raise DataUnavailable("No verified Zerodha market timestamp available yet")
        return self._last_market_timestamp
