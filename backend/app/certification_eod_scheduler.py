"""Once-daily post-market certification notification scheduler."""
from __future__ import annotations
import asyncio
from datetime import datetime, time
from zoneinfo import ZoneInfo
from typing import Callable, Any

class CertificationEodScheduler:
    def __init__(self, notify_fn: Callable[[int], dict[str, Any]], *, enabled: bool=True, run_time: str="16:15", timezone_name: str="Asia/Kolkata", poll_interval_sec: float=60, limit_days: int=30):
        self.notify_fn=notify_fn; self.enabled=enabled; self.run_time=run_time; self.tz=ZoneInfo(timezone_name)
        self.poll_interval_sec=max(10,float(poll_interval_sec)); self.limit_days=limit_days
        self.last_run_day=None; self.runs=0; self.generated=0; self.failures=0; self.last_error=None; self.last_run_at=None
    def _due(self, now: datetime) -> bool:
        if not self.enabled: return False
        hh,mm=[int(x) for x in self.run_time.split(':',1)]
        local=now.astimezone(self.tz)
        return local.time() >= time(hh,mm) and self.last_run_day != local.date().isoformat() and local.weekday()<5
    def run_once(self, now: datetime|None=None, force: bool=False) -> dict[str,Any]:
        now=now or datetime.now(self.tz); self.runs+=1; self.last_run_at=now.isoformat()
        if not force and not self._due(now): return {**self.status(now),"generated":False,"reason":"NOT_DUE"}
        try:
            result=self.notify_fn(self.limit_days); self.generated+=1; self.last_run_day=now.astimezone(self.tz).date().isoformat(); self.last_error=None
            return {**self.status(now),"generated":True,"result":result}
        except Exception as exc:
            self.failures+=1; self.last_error=str(exc)[:500]; raise
    async def run_loop(self):
        while True:
            try: self.run_once()
            except Exception: pass
            await asyncio.sleep(self.poll_interval_sec)
    def status(self, now: datetime|None=None):
        now=now or datetime.now(self.tz)
        return {"enabled":self.enabled,"configured_time":self.run_time,"timezone":str(self.tz),"last_run_day":self.last_run_day,"runs":self.runs,"generated":self.generated,"failures":self.failures,"last_error":self.last_error,"last_run_at":self.last_run_at,"live_orders_enabled":False}
