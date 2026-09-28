"""Read-only pre/post-market reporting and broker reconciliation.

This module never places, modifies or cancels a broker order. Broker records
are observations used to expose manual/external activity alongside the local
recommendation and paper ledgers.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Callable
from zoneinfo import ZoneInfo

from app import store
from app.config import settings
from app.execution_ledger import list_orders as list_execution_orders
from app.market_clock import market_clock
from app.paper_loop_readiness import paper_loop_readiness
from app.risk_supervisor import status as risk_status
from app.version import version_info


def _safe(call: Callable[[], Any], fallback: Any) -> tuple[Any, str | None]:
    try:
        return call(), None
    except Exception as exc:
        return fallback, f"{type(exc).__name__}: {exc}"


def _nifty(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for item in records:
        symbol = str(item.get("tradingsymbol") or item.get("symbol") or "").upper()
        if symbol.startswith("NIFTY"):
            result.append(dict(item))
    return result


def _public_broker_record(item: dict[str, Any]) -> dict[str, Any]:
    """Allowlist useful trading fields and avoid persisting broker payloads wholesale."""
    fields = (
        "order_id", "exchange_order_id", "tradingsymbol", "exchange", "transaction_type",
        "quantity", "filled_quantity", "pending_quantity", "average_price", "price",
        "status", "order_timestamp", "exchange_timestamp", "trade_id", "fill_timestamp",
        "product", "order_type", "tag",
    )
    return {key: item.get(key) for key in fields if key in item}


class TradingReportService:
    def __init__(self, path: str, data_source_factory: Callable[[], Any]):
        self.path = Path(path)
        self.data_source_factory = data_source_factory
        self._lock = RLock()

    def _broker_snapshot(self) -> dict[str, Any]:
        source = self.data_source_factory()
        health, health_error = _safe(source.token_health, {"connected": False})
        kite = getattr(source, "_kite", None)
        if kite is None or not health.get("connected"):
            return {"connected": False, "health": health, "orders": [], "trades": [],
                    "positions": [], "errors": [x for x in [health_error, "BROKER_NOT_CONNECTED"] if x]}
        orders, orders_error = _safe(lambda: _nifty(list(kite.orders() or [])), [])
        trades, trades_error = _safe(lambda: _nifty(list(kite.trades() or [])), [])
        positions_payload, positions_error = _safe(lambda: dict(kite.positions() or {}), {})
        position_rows = []
        for group in ("net", "day"):
            position_rows.extend(_nifty(list(positions_payload.get(group) or [])))
        return {
            "connected": True,
            "health": health,
            "orders": [_public_broker_record(x) for x in orders],
            "trades": [_public_broker_record(x) for x in trades],
            "positions": [_public_broker_record(x) for x in position_rows],
            "errors": [x for x in (orders_error, trades_error, positions_error) if x],
            "read_only": True,
        }

    @staticmethod
    def _lineage(setups: list[dict[str, Any]], papers: list[dict[str, Any]], broker: dict[str, Any], executions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        paper_by_setup = {int(row["setup_id"]): row for row in papers if row.get("setup_id") is not None}
        broker_by_tag = {str(row.get("tag")): row for row in broker.get("orders", []) if row.get("tag")}
        execution_by_setup: dict[int, dict[str, Any]] = {}
        for execution in executions:
            setup_id = (execution.get("quality_snapshot") or {}).get("setup_id")
            if setup_id is not None:
                execution_by_setup[int(setup_id)] = execution
        rows = []
        for setup in setups:
            paper = paper_by_setup.get(int(setup["id"]))
            execution = execution_by_setup.get(int(setup["id"]))
            broker_order = broker_by_tag.get(str(execution.get("broker_tag"))) if execution else None
            if execution and not broker_order and execution.get("broker_order_id"):
                broker_order = next((row for row in broker.get("orders", [])
                                     if str(row.get("order_id")) == str(execution["broker_order_id"])), None)
            rows.append({
                "setup_id": setup["id"], "recommendation": setup.get("decision"),
                "grade": setup.get("grade"), "score": setup.get("alignment_score"),
                "contract": f"{setup.get('option_type') or ''} {setup.get('strike') or ''}".strip(),
                "setup_status": setup.get("status"),
                "paper_trade_id": paper.get("id") if paper else None,
                "paper_status": paper.get("status") if paper else None,
                "broker_order_id": broker_order.get("order_id") if broker_order else None,
                "broker_status": broker_order.get("status") if broker_order else None,
                "execution_id": execution.get("execution_id") if execution else None,
                "broker_match": "EXECUTION_LEDGER_MATCH" if broker_order else "NONE",
            })
        return rows

    def build(self, report_type: str, now: datetime | None = None) -> dict[str, Any]:
        if report_type not in {"PRE_MARKET", "POST_MARKET"}:
            raise ValueError("report_type must be PRE_MARKET or POST_MARKET")
        current = now or datetime.now(timezone.utc)
        clock = market_clock(current, settings.market_holidays, settings.market_open_time, settings.market_close_time)
        day = clock.trading_day
        broker = self._broker_snapshot()
        setups = store.list_trade_setups(trading_day=day, limit=200)
        papers = store.list_paper_trades(trading_day=day, limit=200)
        decisions = [x for x in store.list_paper_automation_runs(limit=200) if x.get("trading_day") == day]
        executions = [x for x in list_execution_orders(limit=500) if str(x.get("created_at") or "")[:10] == day]
        report = {
            "report_type": report_type,
            "generated_at": current.astimezone(timezone.utc).isoformat(),
            "trading_day": day,
            "market_clock": clock.to_dict(),
            "version": version_info(),
            "safety": {"execution_mode": "PAPER_ONLY", "live_orders_enabled": settings.live_orders_enabled,
                       "broker_access": "READ_ONLY_REPORTING"},
            "readiness": paper_loop_readiness(),
            "risk": risk_status(),
            "summary": {
                "recommendations": len(setups), "decision_cycles": len(decisions),
                "paper_trades": len(papers), "paper_open": sum(1 for x in papers if x.get("status") == "OPEN"),
                "paper_net_pnl": round(sum(float(x.get("net_pnl") or 0) for x in papers), 2),
                "zerodha_orders": len(broker.get("orders", [])), "zerodha_trades": len(broker.get("trades", [])),
                "unmatched_zerodha_orders": 0,
                "application_execution_orders": len(executions),
                "profit_withdrawal_threshold": settings.paper_profit_withdrawal_threshold,
                "withdrawal_alert": round(sum(float(x.get("net_pnl") or 0) for x in papers), 2)
                >= settings.paper_profit_withdrawal_threshold > 0,
            },
            "recommendations": setups,
            "decisions": decisions,
            "paper_trades": papers,
            "zerodha": broker,
            "application_execution_orders": executions,
        }
        report["lineage"] = self._lineage(setups, papers, broker, executions)
        matched = {str(x.get("broker_order_id")) for x in report["lineage"] if x.get("broker_order_id")}
        report["unmatched_zerodha_orders"] = [x for x in broker.get("orders", []) if str(x.get("order_id")) not in matched]
        report["summary"]["unmatched_zerodha_orders"] = len(report["unmatched_zerodha_orders"])
        if report_type == "PRE_MARKET":
            report["analysis"] = {
                "status": "READY" if broker.get("connected") and report["readiness"].get("offline_complete") else "BLOCKED",
                "message": "Token, safety controls and paper loop are ready; entries still require live A/A+ evidence."
                if broker.get("connected") else "Refresh the Zerodha token before the session.",
            }
        else:
            report["analysis"] = {
                "status": "COMPLETE" if not report["summary"]["paper_open"] else "OPEN_PAPER_POSITION",
                "message": "Daily recommendations, autonomous decisions, paper outcomes and read-only Zerodha observations reconciled.",
            }
        return report

    def generate(self, report_type: str, now: datetime | None = None) -> dict[str, Any]:
        report = self.build(report_type, now)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(report, default=str, separators=(",", ":")) + "\n")
        return report

    def history(self, limit: int = 20, report_type: str | None = None) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if report_type and item.get("report_type") != report_type:
                continue
            rows.append(item)
        return list(reversed(rows[-max(1, min(limit, 100)):]))

    def latest(self, report_type: str) -> dict[str, Any] | None:
        rows = self.history(1, report_type)
        return rows[0] if rows else None
