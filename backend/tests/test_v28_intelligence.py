from types import SimpleNamespace
from app.market_regime_engine import classify_market_regime
from app.smart_money_engine import analyse_market_structure
from app.gamma_intelligence import analyse_gamma
from app.ai_supervisor_v2 import build_supervisor_decision
from app.data_sources.mock_source import MockDataSource


def test_regime_engine_detects_bullish_trend():
    out = classify_market_regime({"nifty_spot": 25200}, {"vwap":25100,"ema20":25150,"ema50":25000,"atr":80,"adx":30,"rsi":65}, {})
    assert out["regime"] == "TRENDING_BULLISH"
    assert out["trend_score"] > 50


def test_smart_money_detects_bullish_bos():
    candles=[]
    for i in range(6):
        candles.append({"open":100+i,"high":102+i,"low":99+i,"close":101+i})
    candles[-1] = {"open":106,"high":112,"low":105,"close":111}
    out=analyse_market_structure(candles)
    assert out["bos"] == "BULLISH"
    assert out["structure_bias"] == "BULLISH"


def test_gamma_engine_returns_chain_intelligence():
    snap=MockDataSource(seed=9).get_option_chain(atm_range=4)
    out=analyse_gamma(snap)
    assert out["dealer_regime"] in {"LONG_GAMMA","SHORT_GAMMA","UNKNOWN"}
    assert "strikes" in out or out["dealer_regime"] == "UNKNOWN"


def test_supervisor_only_recommends_high_grade():
    base=SimpleNamespace(risk=SimpleNamespace(approved=True))
    regime={"trend_score":90,"range":{"low":100,"high":120}}
    structure={"structure_score":90,"range":{"low":100,"high":120}}
    gamma={"dealer_regime":"LONG_GAMMA","gamma_flip":110}
    flow={"institutional_flow_score":80}
    out=build_supervisor_decision(base,regime,structure,gamma,flow)
    assert out["grade"] in {"A+","A"}
    assert out["decision"] == "CE_BUY"
