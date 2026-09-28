"""Deterministic Indian equity-options paper transaction cost model.

Rates are configuration, not claims about a broker invoice.  The model keeps
every component visible and versioned so paper results can be reproduced.
"""
from __future__ import annotations

from typing import Any

from app.config import settings

COST_MODEL_VERSION = "INDIA_OPTIONS_V1"


def option_trade_costs(entry_price: float, exit_price: float, quantity: int) -> dict[str, Any]:
    if entry_price <= 0 or exit_price <= 0 or quantity <= 0:
        raise ValueError("prices and quantity must be positive")
    buy_turnover = float(entry_price) * int(quantity)
    sell_turnover = float(exit_price) * int(quantity)
    turnover = buy_turnover + sell_turnover
    brokerage = min(settings.paper_brokerage_per_order, buy_turnover * settings.paper_brokerage_rate) + min(
        settings.paper_brokerage_per_order, sell_turnover * settings.paper_brokerage_rate
    )
    stt = sell_turnover * settings.paper_stt_sell_rate
    exchange = turnover * settings.paper_exchange_charge_rate
    sebi = turnover * settings.paper_sebi_charge_rate
    stamp = buy_turnover * settings.paper_stamp_duty_buy_rate
    gst = (brokerage + exchange + sebi) * settings.paper_gst_rate
    total = brokerage + stt + exchange + sebi + stamp + gst
    return {
        "model_version": COST_MODEL_VERSION,
        "buy_turnover": round(buy_turnover, 2),
        "sell_turnover": round(sell_turnover, 2),
        "brokerage": round(brokerage, 2),
        "stt": round(stt, 2),
        "exchange_charges": round(exchange, 2),
        "sebi_charges": round(sebi, 2),
        "stamp_duty": round(stamp, 2),
        "gst": round(gst, 2),
        "total": round(total, 2),
    }
