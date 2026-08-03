from pathlib import Path
from app.version import version_info
from app.release_health import release_certificate
from app.routes import get_data_source
from app.pipeline import run_pipeline
from app.decision_explainability import explain_decision


def test_version_metadata_contains_release_fields():
    info = version_info()
    expected = (Path(__file__).resolve().parents[2] / "VERSION").read_text().strip()
    assert info["version"] == expected
    for key in ("build_id", "build_time", "git_commit", "environment", "reported_at"):
        assert key in info


def test_release_certificate_has_safety_checks():
    cert = release_certificate()
    assert cert["health_score"] >= 0
    assert "live_orders_safely_disabled" in cert["checks"]
    assert cert["checks"]["version_available"] is True


def test_decision_explanation_is_structured():
    response = run_pipeline(get_data_source())
    explanation = explain_decision(response)
    assert explanation["decision"] in {"CE_BUY", "PE_BUY", "NO_TRADE"}
    assert isinstance(explanation["checklist"]["passed"], list)
    assert isinstance(explanation["checklist"]["failed"], list)
    assert explanation["invalidation_conditions"]
