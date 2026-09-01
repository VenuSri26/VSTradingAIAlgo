from app.notification_delivery import NotificationDelivery


def test_multi_category_recipients_are_combined(tmp_path):
    delivery=NotificationDelivery(str(tmp_path/'outbox.jsonl'), smtp_host='smtp.test', smtp_from='from@test', smtp_to_broker='broker@test', smtp_to_infrastructure='infra@test')
    row=delivery.enqueue('X','CRITICAL','m','a',{'categories':['BROKER','INFRASTRUCTURE','BROKER']})
    captured={}
    class Dummy:
        def __init__(self,*a,**k): pass
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def starttls(self): pass
        def login(self,*a): pass
        def send_message(self,msg): captured['to']=msg['To']
    import app.notification_delivery as mod
    old=mod.smtplib.SMTP; mod.smtplib.SMTP=Dummy
    try: delivery._send_email(row)
    finally: mod.smtplib.SMTP=old
    assert captured['to'] == 'broker@test, infra@test'
