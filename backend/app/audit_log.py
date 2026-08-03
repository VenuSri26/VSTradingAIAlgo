from __future__ import annotations
import json
import os
from dataclasses import asdict
from app.config import settings
from app.models import LiveDecisionResponse


def _serialize(obj):
    if hasattr(obj, "__dict__") or hasattr(obj, "__dataclass_fields__"):
        try:
            return asdict(obj)
        except TypeError:
            pass
    return str(obj)


def log_decision(response: LiveDecisionResponse, outcome_status: str = "GENERATED") -> None:
    """outcome_status: GENERATED | TAKEN | SKIPPED | BLOCKED | EXPIRED"""
    os.makedirs(os.path.dirname(settings.audit_log_path) or ".", exist_ok=True)
    record = {
        "timestamp": response.timestamp,
        "decision": response.decision.decision.value,
        "grade": response.decision.grade.value,
        "alignment_score": response.alignment.score,
        "outcome_status": outcome_status,
        "plan": asdict(response.decision.plan) if response.decision.plan else None,
        "risk_approved": response.risk.approved,
        "risk_reasons": response.risk.reasons,
        "agent_scores": {a.name: a.score for a in response.agents},
    }
    with open(settings.audit_log_path, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")
