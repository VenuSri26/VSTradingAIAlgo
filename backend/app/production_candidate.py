from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app import store
from app.config import settings, validate
from app.release_health import release_certificate
from app.risk_supervisor import status as risk_status
from app.version import version_info


@dataclass(frozen=True)
class ReadinessRule:
    code: str
    label: str
    passed: bool
    weight: int
    detail: str


def _rule(code: str, label: str, passed: bool, weight: int, detail: str) -> ReadinessRule:
    return ReadinessRule(code=code, label=label, passed=bool(passed), weight=weight, detail=detail)


def production_candidate_status() -> dict[str, Any]:
    analytics = store.paper_analytics_summary()
    summary = analytics.get("summary", {})
    risk = risk_status()
    certificate = release_certificate()
    version = version_info()
    config_problems = validate()

    trades = int(summary.get("total_trades") or 0)
    win_rate = float(summary.get("win_rate") or 0.0)
    profit_factor_raw = summary.get("profit_factor")
    profit_factor = float(profit_factor_raw or 0.0)
    expectancy = float(summary.get("expectancy") or 0.0)
    max_drawdown = float(summary.get("max_drawdown") or 0.0)
    health_score = float(certificate.get("health_score") or 0.0)

    rules = [
        _rule("RELEASE_HEALTH", "Release health score", health_score >= 85, 15,
              f"Health score {health_score:.0f}/100; minimum 85"),
        _rule("CONFIG_VALID", "Configuration validation", not config_problems, 10,
              "Configuration valid" if not config_problems else "; ".join(config_problems)),
        _rule("PAPER_SAMPLE", "Paper-trade sample size", trades >= 30, 20,
              f"{trades} closed trades; minimum 30"),
        _rule("WIN_RATE", "Win-rate evidence", trades >= 30 and win_rate >= 50, 10,
              f"Win rate {win_rate:.2f}%; minimum 50% with 30 trades"),
        _rule("PROFIT_FACTOR", "Profit-factor evidence", trades >= 30 and profit_factor >= 1.20, 15,
              f"Profit factor {profit_factor:.2f}; minimum 1.20"),
        _rule("EXPECTANCY", "Positive expectancy", trades >= 30 and expectancy > 0, 10,
              f"Expectancy {expectancy:.2f}; must be positive"),
        _rule("DRAWDOWN", "Drawdown control", trades >= 30 and max_drawdown <= settings.paper_capital * 0.10, 10,
              f"Max drawdown {max_drawdown:.2f}; limit {settings.paper_capital * 0.10:.2f}"),
        _rule("RISK_READY", "Risk supervisor ready", not bool(risk.get("blocked")) and not bool(risk.get("kill_switch")), 5,
              "Risk supervisor ready" if not risk.get("blocked") else "Risk supervisor is blocking entries"),
        _rule("LIVE_DISABLED", "Live orders safety lock", not settings.live_orders_enabled, 5,
              "Live broker orders are disabled" if not settings.live_orders_enabled else "Live broker orders are enabled"),
    ]

    total_weight = sum(r.weight for r in rules)
    earned = sum(r.weight for r in rules if r.passed)
    score = round(earned / total_weight * 100.0, 2) if total_weight else 0.0
    blockers = [r for r in rules if not r.passed]

    if score >= 90 and not blockers:
        status = "CERTIFIED_FOR_CONTROLLED_PILOT"
    elif score >= 70:
        status = "PAPER_VALIDATION_REQUIRED"
    else:
        status = "NOT_READY"

    return {
        "version": version,
        "status": status,
        "readiness_score": score,
        "execution_mode": "PAPER_ONLY",
        "live_orders_enabled": settings.live_orders_enabled,
        "rules": [r.__dict__ for r in rules],
        "blockers": [r.__dict__ for r in blockers],
        "paper_performance": summary,
        "risk": risk,
        "release_health_score": health_score,
        "next_action": (
            "Continue paper trading until every evidence gate passes."
            if blockers else "Run a controlled manual-approval pilot; keep automatic execution disabled."
        ),
    }
