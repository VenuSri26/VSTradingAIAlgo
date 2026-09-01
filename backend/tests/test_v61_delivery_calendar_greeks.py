import json
from app.notification_delivery import NotificationDelivery
from app.market_calendar_service import MarketCalendarService
from app.greeks_validation_history import GreeksValidationHistory


def test_notification_email_channel_can_deliver_without_webhook(tmp_path, monkeypatch):
    sent = []
    class FakeSMTP:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def starttls(self): pass
        def login(self, username, password): pass
        def send_message(self, message): sent.append(message)
    monkeypatch.setattr('app.notification_delivery.smtplib.SMTP', FakeSMTP)
    svc = NotificationDelivery(
        str(tmp_path / 'outbox.jsonl'), smtp_host='smtp.example.com',
        smtp_from='bot@example.com', smtp_to='user@example.com'
    )
    svc.enqueue('TOKEN', 'CRITICAL', 'refresh token', 'REFRESH')
    result = svc.dispatch()
    assert result['delivered'] == 1
    assert result['channels']['email'] == 1
    assert sent and 'refresh token' in sent[0].get_content()


def test_market_calendar_imports_csv_and_json(tmp_path):
    svc = MarketCalendarService(str(tmp_path / 'holidays.json'))
    csv_result = svc.import_text('date,name\n2026-10-02,Gandhi Jayanti\n', 'csv')
    assert csv_result['count'] == 1
    json_result = svc.import_text(json.dumps([{'date':'2026-12-25','name':'Christmas'}]), 'json', replace=False)
    assert json_result['count'] == 2


def test_greeks_history_persists_and_summarizes(tmp_path):
    svc = GreeksValidationHistory(str(tmp_path / 'greeks.jsonl'))
    for _ in range(5):
        svc.record({'status':'PASS','option_type':'CE','strike':25000,'spot':25010,'iv_pct':20,
                    'provided_metrics':4,'failed_metrics':0,'recommended_action':'USE_FOR_DECISION_SUPPORT'})
    summary = svc.summary()
    assert summary['status'] == 'READY'
    assert summary['samples'] == 5
    assert summary['pass_rate_pct'] == 100.0
    assert summary['metric_match_rate_pct'] == 100.0
