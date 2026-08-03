from app.institutional_flow import classify_buildup, analyse_institutional_flow

def test_buildup_quadrants():
    assert classify_buildup(1,2)=='LONG_BUILDUP'
    assert classify_buildup(-1,2)=='SHORT_BUILDUP'
    assert classify_buildup(1,-2)=='SHORT_COVERING'
    assert classify_buildup(-1,-2)=='LONG_UNWINDING'

def test_missing_feeds_are_explicit_and_safe():
    result=analyse_institutional_flow({'pcr_oi':1.2,'bias_score':65,'confidence':80,'institutional_bias':'BULLISH'})
    assert result['institutional_bias']=='BULLISH'
    assert result['safe_for_live_execution'] is False
    assert len(result['warnings'])>=2

def test_full_flow_combination():
    result=analyse_institutional_flow(
      {'pcr_oi':1.15,'bias_score':62,'confidence':85,'institutional_bias':'BULLISH'},
      {'net_index_futures':60000,'normalization':100000,'price_change_pct':0.7,'oi_change_pct':3.2},
      {'fii_net':2200,'dii_net':800,'normalization':5000}, [0.95,1.02,1.15])
    assert result['institutional_flow_score']>20
    assert result['futures_buildup']=='LONG_BUILDUP'
    assert result['pcr_trend']=='RISING'
