from __future__ import annotations
from fastapi import APIRouter, Depends
from app.routes import get_data_source, require_admin_token
from app.kite_ticker_runtime import get_kite_ticker_runtime
from app.runtime_maintenance import get_runtime_maintenance
from app.market_safety_routes import get_market_safety_status

router = APIRouter()

@router.get('/api/runtime-maintenance/status')
def maintenance_status():
    return get_runtime_maintenance().status(runtime=get_kite_ticker_runtime().status())

@router.get('/api/runtime-maintenance/notifications')
def maintenance_notifications(limit: int = 50):
    return {'notifications': get_runtime_maintenance().notifications(limit)}

@router.post('/api/runtime-maintenance/run', dependencies=[Depends(require_admin_token)])
def maintenance_run():
    feed = get_market_safety_status()
    return get_runtime_maintenance().run_once(get_data_source(), get_kite_ticker_runtime(), feed)
