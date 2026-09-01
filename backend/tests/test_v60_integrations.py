from pathlib import Path
from app.notification_delivery import NotificationDelivery
from app.market_calendar_service import MarketCalendarService
from app.broker_greeks_validation import compare_broker_greeks


def test_notification_outbox_deduplicates_and_stays_pending_when_disabled(tmp_path):
    svc = NotificationDelivery(str(tmp_path / 'outbox.jsonl'))
    first = svc.enqueue('TOKEN', 'CRITICAL', 'refresh token', 'REFRESH')
    second = svc.enqueue('TOKEN', 'CRITICAL', 'refresh token', 'REFRESH')
    assert first['id'] == second['id']
    result = svc.dispatch()
    assert result['delivery_enabled'] is False
    assert svc.status()['pending'] == 1


def test_market_calendar_replace_validates_and_deduplicates(tmp_path):
    svc = MarketCalendarService(str(tmp_path / 'holidays.json'))
    status = svc.replace([{'date':'2026-10-02','name':'Gandhi Jayanti'}, {'date':'2026-10-02','name':'Duplicate'}])
    assert status['count'] == 1
    assert svc.list_holidays()[0]['name'] == 'Gandhi Jayanti'


def test_broker_greeks_comparison_pass_and_fail():
    base = {'option_type':'CE','spot':25000,'strike':25000,'ltp':250,'days_to_expiry':7,'broker_iv':20}
    model_only = compare_broker_greeks(base)
    assert model_only['status'] == 'WARNING'
    good = dict(base, broker_greeks=model_only['model_greeks'])
    assert compare_broker_greeks(good)['status'] == 'PASS'
    bad = dict(base, broker_greeks={'delta':-0.9,'gamma':0.1,'theta':99,'vega':99})
    assert compare_broker_greeks(bad)['status'] == 'FAIL'
