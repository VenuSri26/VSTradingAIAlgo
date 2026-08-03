from __future__ import annotations
from app.models import RiskResult, AgentResult, Direction, utcnow


def risk_agent(
    trades_today: int,
    max_trades: int,
    daily_pnl: float,
    daily_loss_limit: float,
    consecutive_losses: int,
    max_consecutive_losses: int,
    data_age_sec: float,
    max_data_age_sec: float,
    vix: float,
    vix_spike_threshold: float,
    proposed_rr: float | None,
    min_rr: float,
    minutes_to_close: float | None,
    weight: float,
) -> tuple[AgentResult, RiskResult]:
    reasons = []
    approved = True

    if trades_today >= max_trades:
        approved = False
        reasons.append(f"Daily trade limit reached ({trades_today}/{max_trades})")

    if daily_pnl <= -abs(daily_loss_limit):
        approved = False
        reasons.append(f"Daily loss limit hit (P&L {daily_pnl:.0f} <= -{daily_loss_limit:.0f})")

    if consecutive_losses >= max_consecutive_losses:
        approved = False
        reasons.append(f"Consecutive loss limit reached ({consecutive_losses})")

    if data_age_sec > max_data_age_sec:
        approved = False
        reasons.append(f"Market data stale ({data_age_sec:.1f}s > {max_data_age_sec:.0f}s limit)")

    if vix >= vix_spike_threshold:
        approved = False
        reasons.append(f"Volatility spike (VIX {vix:.1f} >= {vix_spike_threshold:.1f})")

    if proposed_rr is not None and proposed_rr < min_rr:
        approved = False
        reasons.append(f"Risk/reward below minimum ({proposed_rr:.2f} < {min_rr:.2f})")

    if minutes_to_close is not None and minutes_to_close < 15:
        approved = False
        reasons.append(f"Too close to market close ({minutes_to_close:.0f} min remaining)")

    risk_result = RiskResult(
        approved=approved, reasons=reasons, trades_today=trades_today, max_trades=max_trades,
        daily_pnl=daily_pnl, daily_loss_limit=daily_loss_limit, consecutive_losses=consecutive_losses,
    )

    agent_result = AgentResult(
        name="Risk Agent",
        score=100 if approved else 0,
        direction=Direction.BULLISH if approved else Direction.BEARISH,
        confidence=1.0,
        reason="RISK APPROVED — no veto conditions triggered." if approved else "TRADE BLOCKED: " + "; ".join(reasons),
        evidence=reasons if reasons else ["All risk checks passed"],
        weight=weight, timestamp=utcnow(),
    )
    return agent_result, risk_result
