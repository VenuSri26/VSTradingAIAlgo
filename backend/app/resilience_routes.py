from fastapi import APIRouter

from app.resilience import resilience_status

router = APIRouter(prefix="/api/resilience", tags=["resilience"])


@router.get("/status")
def get_resilience_status():
    return resilience_status()


@router.get("/restart-check")
def get_restart_check():
    status = resilience_status()
    return {
        "version": status["version"],
        "overall": status["overall"],
        "restart_safe": status["restart_safe"],
        "blocking_issues": status["blocking_issues"],
        "recommended_action": status["recommended_action"],
    }
