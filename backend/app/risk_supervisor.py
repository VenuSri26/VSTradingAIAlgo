from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app.config import settings
from app import store

@dataclass
class RiskDecision:
    approved: bool
    reasons: list[str]
    warnings: list[str]
    max_quantity: int
    requested_quantity: int
    risk_rupees: float
    capital_required: float

    def to_dict(self) -> dict:
        return asdict(self)

def evaluate_paper_entry(setup: dict, entry_price: float, quantity: int | None = None) -> RiskDecision:
    reasons: list[str] = []
    warnings: list[str] = []
    state = store.get_risk_state()
    session = store.get_session_dict()
    if state.get("kill_switch"):
        reasons.append(f"Emergency kill switch is active: {state.get('reason') or 'No reason supplied'}")
    if store.get_open_paper_trade():
        reasons.append("A paper trade is already open")
    if setup.get("status") != "APPROVED":
        reasons.append("Only APPROVED setups may be executed")
    if session["trades_today"] >= settings.max_trades_per_day:
        reasons.append("Maximum trades per day reached")
    if session["daily_pnl"] <= -abs(settings.daily_loss_limit):
        reasons.append("Daily loss limit reached")
    if session["consecutive_losses"] >= settings.max_consecutive_losses:
        reasons.append("Consecutive-loss lockout is active")
    stop = float(setup.get("stop_loss") or 0)
    effective_entry = entry_price + settings.paper_slippage_rupees
    if stop <= 0 or effective_entry <= stop:
        reasons.append("Invalid entry/stop-loss relationship")
        return RiskDecision(False, reasons, warnings, 0, quantity or 0, 0.0, 0.0)
    risk_per_unit = effective_entry - stop
    risk_budget = settings.paper_capital * settings.max_risk_per_trade_pct / 100
    raw_max = int(risk_budget // risk_per_unit)
    max_qty_risk = (raw_max // settings.nifty_lot_size) * settings.nifty_lot_size
    capital_limit = settings.paper_capital * settings.max_capital_utilization_pct / 100
    raw_capital_qty = int(capital_limit // effective_entry)
    max_qty_capital = (raw_capital_qty // settings.nifty_lot_size) * settings.nifty_lot_size
    max_qty = min(max_qty_risk, max_qty_capital)
    requested = quantity or max_qty
    if requested <= 0 or max_qty <= 0:
        reasons.append("Risk or capital settings do not permit one lot")
    if requested % settings.nifty_lot_size != 0:
        reasons.append(f"Quantity must be a multiple of {settings.nifty_lot_size}")
    if requested > max_qty:
        reasons.append(f"Requested quantity exceeds safe maximum of {max_qty}")
    risk_rupees = round(risk_per_unit * max(requested, 0), 2)
    capital_required = round(effective_entry * max(requested, 0), 2)
    if setup.get("risk_reward") is not None and float(setup["risk_reward"]) < settings.min_risk_reward:
        reasons.append("Setup risk/reward is below the configured minimum")
    now = datetime.now(ZoneInfo(settings.app_timezone))
    if now.weekday() >= 5:
        warnings.append("Market is closed for the weekend")
    return RiskDecision(not reasons, reasons, warnings, max_qty, requested, risk_rupees, capital_required)

def status() -> dict:
    session = store.get_session_dict()
    state = store.get_risk_state()
    remaining_loss = max(0.0, settings.daily_loss_limit + session["daily_pnl"])
    remaining_trades = max(0, settings.max_trades_per_day - session["trades_today"])
    blocked = bool(state.get("kill_switch")) or remaining_loss <= 0 or remaining_trades <= 0 or session["consecutive_losses"] >= settings.max_consecutive_losses
    return {
        "blocked": blocked, "kill_switch": bool(state.get("kill_switch")), "kill_switch_reason": state.get("reason"),
        "trades_today": session["trades_today"], "remaining_trades": remaining_trades,
        "daily_pnl": session["daily_pnl"], "daily_loss_limit": settings.daily_loss_limit,
        "remaining_loss_capacity": round(remaining_loss, 2),
        "consecutive_losses": session["consecutive_losses"], "max_consecutive_losses": settings.max_consecutive_losses,
        "paper_capital": settings.paper_capital, "max_risk_per_trade_pct": settings.max_risk_per_trade_pct,
        "max_capital_utilization_pct": settings.max_capital_utilization_pct,
    }
