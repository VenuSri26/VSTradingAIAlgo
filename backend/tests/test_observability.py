from types import SimpleNamespace

from app.observability import metrics_snapshot, run_observed_pipeline


def test_observed_pipeline_records_success():
    response = SimpleNamespace(
        decision=SimpleNamespace(decision=SimpleNamespace(value="NO_TRADE")),
        system_health=SimpleNamespace(data_age_sec=0.0, overall=SimpleNamespace(value="GREEN")),
    )
    before = metrics_snapshot()["pipeline_runs"]
    result = run_observed_pipeline(lambda ds: response, object())
    after = metrics_snapshot()
    assert result is response
    assert after["pipeline_runs"] == before + 1
    assert after["pipeline_last_duration_ms"] is not None


def test_observed_pipeline_records_failure():
    before = metrics_snapshot()["pipeline_failures"]
    try:
        run_observed_pipeline(lambda ds: (_ for _ in ()).throw(RuntimeError("boom")), object())
    except RuntimeError:
        pass
    assert metrics_snapshot()["pipeline_failures"] == before + 1
