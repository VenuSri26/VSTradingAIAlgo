from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any

@dataclass(frozen=True)
class FlowComponent:
    name: str
    score: float
    direction: str
    confidence: float
    reason: str


def _clamp(v: float, lo: float=-100.0, hi: float=100.0) -> float:
    return max(lo, min(hi, float(v)))


def _direction(score: float, neutral: float=12.0) -> str:
    if score > neutral: return 'BULLISH'
    if score < -neutral: return 'BEARISH'
    return 'NEUTRAL'


def classify_buildup(price_change_pct: float, oi_change_pct: float) -> str:
    if abs(price_change_pct) < 0.05 or abs(oi_change_pct) < 0.5:
        return 'NEUTRAL'
    if price_change_pct > 0 and oi_change_pct > 0: return 'LONG_BUILDUP'
    if price_change_pct < 0 and oi_change_pct > 0: return 'SHORT_BUILDUP'
    if price_change_pct > 0 and oi_change_pct < 0: return 'SHORT_COVERING'
    return 'LONG_UNWINDING'


def analyse_institutional_flow(option_summary: dict[str, Any], futures: dict[str, Any] | None=None,
                               cash: dict[str, Any] | None=None, pcr_history: list[float] | None=None) -> dict[str, Any]:
    futures=futures or {}; cash=cash or {}; pcr_history=pcr_history or []
    pcr=float(option_summary.get('pcr_oi') or option_summary.get('pcr') or 1.0)
    pcr_change=float(option_summary.get('pcr_change') or 0.0)
    if len(pcr_history)>=2:
        pcr_change=pcr_history[-1]-pcr_history[0]
    bias=float(option_summary.get('bias_score') or 50.0)
    option_score=_clamp((bias-50.0)*2.0 + (pcr-1.0)*35.0 + pcr_change*20.0)
    futures_net=float(futures.get('net_index_futures') or 0.0)
    futures_oi=float(futures.get('oi_change_pct') or 0.0)
    futures_price=float(futures.get('price_change_pct') or 0.0)
    fut_scale=max(abs(float(futures.get('normalization') or 100000.0)),1.0)
    futures_score=_clamp((futures_net/fut_scale)*65.0 + futures_price*12.0 + futures_oi*4.0)
    fii_cash=float(cash.get('fii_net') or 0.0); dii_cash=float(cash.get('dii_net') or 0.0)
    cash_scale=max(abs(float(cash.get('normalization') or 5000.0)),1.0)
    cash_score=_clamp(((fii_cash + 0.45*dii_cash)/cash_scale)*70.0)
    components=[
        FlowComponent('OPTIONS_FLOW',option_score,_direction(option_score),float(option_summary.get('confidence') or 40.0),f"PCR {pcr:.2f}; option bias {bias:.0f}/100"),
        FlowComponent('INDEX_FUTURES',futures_score,_direction(futures_score),75.0 if futures else 0.0,f"Net futures {futures_net:.0f}; {classify_buildup(futures_price,futures_oi)}" if futures else 'No live index-futures input configured'),
        FlowComponent('CASH_FLOW',cash_score,_direction(cash_score),70.0 if cash else 0.0,f"FII {fii_cash:.0f}; DII {dii_cash:.0f}" if cash else 'No live FII/DII cash input configured'),
    ]
    available=[c for c in components if c.confidence>0]
    weights={'OPTIONS_FLOW':0.5,'INDEX_FUTURES':0.3,'CASH_FLOW':0.2}
    denom=sum(weights[c.name] for c in available) or 1.0
    composite=sum(c.score*weights[c.name] for c in available)/denom
    confidence=sum(c.confidence*weights[c.name] for c in available)/denom
    warnings=[]
    if not futures: warnings.append('Index futures positioning is not connected; score uses available evidence only')
    if not cash: warnings.append('FII/DII cash flow is not connected; do not treat this as confirmed institutional activity')
    if len(pcr_history)<2: warnings.append('PCR trend history is unavailable; only the current snapshot is used')
    return {
        'institutional_flow_score': round(composite,2), 'institutional_bias': _direction(composite),
        'confidence': round(confidence,2), 'options_buildup': option_summary.get('institutional_bias','NEUTRAL'),
        'futures_buildup': classify_buildup(futures_price,futures_oi), 'pcr': round(pcr,4),
        'pcr_trend': 'RISING' if pcr_change>0.03 else 'FALLING' if pcr_change<-0.03 else 'FLAT',
        'components':[asdict(c) for c in components], 'warnings':warnings,
        'safe_for_live_execution': False,
        'note':'Decision-support only. Missing institutional feeds reduce confidence and cannot authorize orders.'
    }
