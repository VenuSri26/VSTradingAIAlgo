from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import app.runtime_maintenance as module
from app.runtime_maintenance import RuntimeMaintenance

IST=ZoneInfo('Asia/Kolkata')

class Runtime:
    def __init__(self): self.contracts=[]; self.market=None
    def status(self): return {'metadata_count':len(self.contracts),'connected':True}
    def configure_contracts(self, contracts): self.contracts=contracts; return self.status()
    def set_market_session(self, market_open, session): self.market=(market_open,session)

class DS:
    def __init__(self, expiry='2026-08-06'): self.expiry=expiry
    def get_option_chain(self, atm_range=8):
        return {'expiry':self.expiry,'chain':{'CE':[{'instrument_token':1,'strike':25000,'tradingsymbol':'CE'}],'PE':[{'instrument_token':2,'strike':25000,'tradingsymbol':'PE'}]}}

def configure(monkeypatch):
    monkeypatch.setattr(module.settings,'market_holidays','')
    monkeypatch.setattr(module.settings,'market_open_time','09:15')
    monkeypatch.setattr(module.settings,'market_close_time','15:30')
    monkeypatch.setattr(module.settings,'instrument_sync_interval_hours',12)
    monkeypatch.setattr(module.settings,'websocket_atm_range',8)
    monkeypatch.setattr(module.settings,'token_warn_age_sec',100)
    monkeypatch.setattr(module.settings,'token_block_age_sec',200)

def test_syncs_contracts_during_market(monkeypatch,tmp_path):
    configure(monkeypatch); r=Runtime(); s=RuntimeMaintenance(interval_sec=30,notification_path=str(tmp_path/'n.jsonl'))
    out=s.run_once(DS(),r,{'authenticated':True,'token_check_age_sec':1},datetime(2026,8,6,10,0,tzinfo=IST))
    assert len(r.contracts)==2 and out['sync_count']==1 and r.market==(True,'OPEN')

def test_does_not_sync_after_market(monkeypatch,tmp_path):
    configure(monkeypatch); r=Runtime(); s=RuntimeMaintenance(interval_sec=30,notification_path=str(tmp_path/'n.jsonl'))
    out=s.run_once(DS(),r,{'authenticated':True},datetime(2026,8,6,18,0,tzinfo=IST))
    assert len(r.contracts)==0 and out['sync_count']==0 and r.market==(False,'POST_CLOSE')

def test_token_alert_deduplicates(monkeypatch,tmp_path):
    configure(monkeypatch); r=Runtime(); p=tmp_path/'n.jsonl'; s=RuntimeMaintenance(interval_sec=30,notification_path=str(p))
    now=datetime(2026,8,6,10,0,tzinfo=IST)
    s.run_once(DS(),r,{'authenticated':False},now); s.run_once(DS(),r,{'authenticated':False},now)
    assert len(p.read_text().splitlines())==1 and s.status()['notification_count']==1

def test_expiry_rollover_is_recorded(monkeypatch,tmp_path):
    configure(monkeypatch); r=Runtime(); s=RuntimeMaintenance(interval_sec=30,notification_path=str(tmp_path/'n.jsonl'))
    now=datetime(2026,8,6,10,0,tzinfo=IST)
    s.run_once(DS('2026-08-06'),r,{'authenticated':True},now)
    s._state.last_sync_at=None
    s.run_once(DS('2026-08-13'),r,{'authenticated':True},now)
    assert s.status()['rollover_count']==1
