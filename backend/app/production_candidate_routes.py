from fastapi import APIRouter

from app.production_candidate import production_candidate_status

router = APIRouter(prefix="/api/production-candidate", tags=["production-candidate"])


@router.get("/status")
def get_status():
    return production_candidate_status()


@router.get("/checklist")
def get_checklist():
    status = production_candidate_status()
    return {
        "version": status["version"],
        "status": status["status"],
        "readiness_score": status["readiness_score"],
        "rules": status["rules"],
        "blockers": status["blockers"],
        "next_action": status["next_action"],
    }
