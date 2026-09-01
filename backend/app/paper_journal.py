"""Paper-trading journal views and CSV export.

Read-only reporting over the existing restart-safe SQLite paper ledger.  This
module never submits broker orders and never mutates a trade.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any

from app import store


def journal_rows(trading_day: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    trades = store.list_paper_trades(trading_day=trading_day, limit=limit)
    rows: list[dict[str, Any]] = []
    for trade in trades:
        timeline = store.get_trade_timeline(int(trade["id"])) or {}
        setup = timeline.get("setup") or {}
        management = timeline.get("management") or {}
        events = timeline.get("events") or []
        rows.append({
            "trade_id": trade["id"],
            "trading_day": trade["trading_day"],
            "opened_at": trade["opened_at"],
            "closed_at": trade.get("closed_at"),
            "option_type": trade["option_type"],
            "strike": trade["strike"],
            "quantity": trade["quantity"],
            "entry_price": trade["entry_price"],
            "stop_loss": trade["stop_loss"],
            "target_1": trade.get("target_1"),
            "target_2": trade.get("target_2"),
            "close_price": trade.get("close_price"),
            "status": trade["status"],
            "gross_pnl": trade.get("gross_pnl"),
            "estimated_costs": trade.get("estimated_costs"),
            "net_pnl": trade.get("net_pnl"),
            "exit_reason": trade.get("exit_reason"),
            "decision": setup.get("decision"),
            "grade": setup.get("grade"),
            "alignment_score": setup.get("alignment_score"),
            "explanation": setup.get("explanation"),
            "remaining_quantity": management.get("remaining_quantity"),
            "highest_price": management.get("highest_price"),
            "active_stop_loss": management.get("active_stop_loss"),
            "monitor_events": len(events),
            "last_monitor_action": events[-1].get("action") if events else None,
        })
    return rows


def daily_summary(trading_day: str | None = None) -> dict[str, Any]:
    portfolio = store.paper_portfolio_summary(trading_day)
    rows = journal_rows(trading_day=trading_day, limit=200)
    open_rows = [r for r in rows if r["status"] == "OPEN"]
    return {
        "trading_day": trading_day or (rows[0]["trading_day"] if rows else None),
        "portfolio": portfolio,
        "open_positions": open_rows,
        "journal_entries": len(rows),
        "execution_mode": "PAPER_ONLY",
        "broker_orders_sent": False,
    }


def journal_csv(trading_day: str | None = None, limit: int = 200) -> str:
    rows = journal_rows(trading_day=trading_day, limit=limit)
    fields = list(rows[0].keys()) if rows else [
        "trade_id", "trading_day", "opened_at", "closed_at", "option_type", "strike",
        "quantity", "entry_price", "stop_loss", "target_1", "target_2", "close_price",
        "status", "gross_pnl", "estimated_costs", "net_pnl", "exit_reason", "decision",
        "grade", "alignment_score", "explanation", "remaining_quantity", "highest_price",
        "active_stop_loss", "monitor_events", "last_monitor_action",
    ]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()
