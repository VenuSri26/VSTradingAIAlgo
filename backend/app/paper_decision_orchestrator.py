"""V7.9 gate joining the full agent pipeline to PAPER-only automation."""
from __future__ import annotations

from typing import Any

from app.pipeline import run_pipeline
from app.decision_evidence import verify_decision_evidence


def corroborate(preview: dict[str, Any], decision: Any) -> dict[str, Any]:
    result = preview.copy()
    candidate = dict(result.get("candidate") or {})
    blockers = list(result.get("blockers") or [])
    pipeline_decision = decision.decision
    decision_name = getattr(pipeline_decision.decision, "value", str(pipeline_decision.decision))
    grade = getattr(pipeline_decision.grade, "value", str(pipeline_decision.grade))
    expected = f"{candidate.get('option_type')}_BUY"
    if getattr(decision.system_health.overall, "value", str(decision.system_health.overall)) != "GREEN":
        blockers.append("FULL_PIPELINE_HEALTH_NOT_GREEN")
    if not decision.risk.approved:
        blockers.append("FULL_PIPELINE_RISK_VETO")
    if decision_name != expected:
        blockers.append(f"FULL_PIPELINE_DIRECTION_MISMATCH:{decision_name}:{expected}")
    if grade not in {"A", "A+"}:
        blockers.append(f"FULL_PIPELINE_GRADE_NOT_ALLOWED:{grade}")
    evidence = decision.decision_evidence or {}
    if not evidence or not verify_decision_evidence(evidence) or (evidence.get("bar") or {}).get("finalized") is not True:
        blockers.append("FULL_PIPELINE_EVIDENCE_UNVERIFIED")
    result["full_pipeline"] = {
        "decision": decision_name,
        "grade": grade,
        "alignment_score": pipeline_decision.alignment_score,
        "confidence": pipeline_decision.confidence,
        "risk_approved": decision.risk.approved,
        "system_health": getattr(decision.system_health.overall, "value", str(decision.system_health.overall)),
        "decision_evidence": evidence,
        "explanation": pipeline_decision.explanation,
    }
    if blockers:
        result.update(status="BLOCKED", action="NO_TRADE", blockers=list(dict.fromkeys(blockers)), candidate=None)
        return result
    candidate["grade"] = grade
    candidate["alignment_score"] = min(
        int(candidate.get("alignment_score") or 0), int(pipeline_decision.alignment_score or 0)
    )
    candidate["rationale"] = list(candidate.get("rationale") or []) + [
        f"Full multi-agent pipeline corroborated {decision_name} grade {grade}"
    ]
    result["candidate"] = candidate
    return result


def evaluate(preview: dict[str, Any], data_source: Any, *, as_of: Any) -> dict[str, Any]:
    return corroborate(preview, run_pipeline(data_source, as_of=as_of))
