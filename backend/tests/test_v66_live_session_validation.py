from app.live_session_validation import LiveSessionValidation, SessionThresholds


def test_live_session_becomes_ready(tmp_path):
    svc = LiveSessionValidation(str(tmp_path/'session.jsonl'), SessionThresholds(min_samples=3, min_ready_ratio=.66, max_feed_age_sec=10, max_error_ratio=.34))
    for _ in range(3):
        svc.record({"feed_age_sec":2,"websocket_connected":True,"authenticated":True,"market_open":True,"option_chain_ready":True,"tick_bridge_ready":True})
    result=svc.summary()
    assert result["status"] == "READY"
    assert result["samples"] == 3
    assert result["live_orders_enabled"] is False


def test_live_session_blocks_bad_samples(tmp_path):
    svc = LiveSessionValidation(str(tmp_path/'session.jsonl'), SessionThresholds(min_samples=2, min_ready_ratio=.9, max_feed_age_sec=5, max_error_ratio=.1))
    svc.record({"feed_age_sec":20,"authenticated":False,"market_open":True,"option_chain_ready":False,"tick_bridge_ready":False,"errors":["boom"]})
    svc.record({"feed_age_sec":1,"websocket_connected":False,"authenticated":True,"market_open":True,"option_chain_ready":True,"tick_bridge_ready":True})
    result=svc.summary()
    assert result["status"] == "BLOCKED"
    assert "LIVE_SESSION_READY_RATIO_BELOW_TARGET" in result["blockers"]


def test_history_survives_restart(tmp_path):
    path=str(tmp_path/'session.jsonl')
    LiveSessionValidation(path).record({"feed_age_sec":1,"authenticated":True,"market_open":True,"option_chain_ready":True,"tick_bridge_ready":True})
    assert len(LiveSessionValidation(path).history()) == 1
