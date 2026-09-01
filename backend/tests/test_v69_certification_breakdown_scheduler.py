from datetime import datetime
from zoneinfo import ZoneInfo
from app.live_session_validation import LiveSessionValidation, SessionThresholds
from app.live_session_certification import LiveSessionCertification, CertificationThresholds
from app.certification_eod_scheduler import CertificationEodScheduler

def test_breakdown_by_expiry_and_regime(tmp_path):
    service=LiveSessionValidation(str(tmp_path/'e.jsonl'),SessionThresholds(min_samples=1,min_ready_ratio=.5))
    service.record({"trading_day":"2026-08-05","feed_age_sec":1,"websocket_connected":True,"authenticated":True,"market_open":True,"option_chain_ready":True,"tick_bridge_ready":True,"expiry":"2026-08-06","market_regime":"TRENDING_BULLISH","errors":[]})
    result=LiveSessionCertification(service,CertificationThresholds(min_sessions=1)).breakdown()
    assert result["by_expiry"][0]["expiry"]=="2026-08-06"
    assert result["by_market_regime"][0]["market_regime"]=="TRENDING_BULLISH"
    assert result["live_orders_enabled"] is False

def test_eod_scheduler_generates_once_per_day():
    calls=[]; tz=ZoneInfo("Asia/Kolkata")
    s=CertificationEodScheduler(lambda d: calls.append(d) or {"ok":True},run_time="16:15")
    now=datetime(2026,8,5,16,30,tzinfo=tz)
    assert s.run_once(now)["generated"] is True
    assert s.run_once(now)["generated"] is False
    assert len(calls)==1

def test_eod_scheduler_skips_before_time():
    s=CertificationEodScheduler(lambda d:{"ok":True},run_time="16:15")
    assert s.run_once(datetime(2026,8,5,15,30,tzinfo=ZoneInfo("Asia/Kolkata")))["reason"]=="NOT_DUE"
