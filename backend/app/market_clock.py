from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo
from typing import Iterable

IST = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class MarketClockStatus:
    timestamp_utc: str
    timestamp_local: str
    trading_day: str
    weekday: int
    market_open: bool
    session: str
    reason: str
    seconds_to_open: int | None
    seconds_to_close: int | None

    def to_dict(self) -> dict:
        return asdict(self)


def parse_timestamp(value: str | datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        # Exchange timestamps without an offset are interpreted as India time.
        dt = dt.replace(tzinfo=IST)
    return dt.astimezone(timezone.utc)


def normalize_exchange_timestamp(value: str | datetime | None) -> str:
    return parse_timestamp(value).isoformat()


def parse_holidays(values: str | Iterable[str] | None) -> set[date]:
    if values is None:
        return set()
    items = values.split(",") if isinstance(values, str) else values
    result: set[date] = set()
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        result.add(date.fromisoformat(text))
    return result


def market_clock(
    now: str | datetime | None = None,
    holidays: str | Iterable[str] | None = None,
    open_time: str = "09:15",
    close_time: str = "15:30",
) -> MarketClockStatus:
    utc_now = parse_timestamp(now)
    local = utc_now.astimezone(IST)
    holiday_set = parse_holidays(holidays)
    open_h, open_m = (int(x) for x in open_time.split(":", 1))
    close_h, close_m = (int(x) for x in close_time.split(":", 1))
    open_dt = datetime.combine(local.date(), time(open_h, open_m), tzinfo=IST)
    close_dt = datetime.combine(local.date(), time(close_h, close_m), tzinfo=IST)

    if local.weekday() >= 5:
        session, reason, is_open = "CLOSED", "WEEKEND", False
    elif local.date() in holiday_set:
        session, reason, is_open = "CLOSED", "MARKET_HOLIDAY", False
    elif local < open_dt:
        session, reason, is_open = "PRE_OPEN", "BEFORE_MARKET_OPEN", False
    elif local > close_dt:
        session, reason, is_open = "POST_CLOSE", "AFTER_MARKET_CLOSE", False
    else:
        session, reason, is_open = "OPEN", "REGULAR_MARKET_SESSION", True

    return MarketClockStatus(
        timestamp_utc=utc_now.isoformat(),
        timestamp_local=local.isoformat(),
        trading_day=local.date().isoformat(),
        weekday=local.weekday(),
        market_open=is_open,
        session=session,
        reason=reason,
        seconds_to_open=max(0, int((open_dt - local).total_seconds())) if local < open_dt else None,
        seconds_to_close=max(0, int((close_dt - local).total_seconds())) if local <= close_dt else None,
    )
