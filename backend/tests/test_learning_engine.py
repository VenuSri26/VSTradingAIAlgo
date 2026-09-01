from app.learning_engine import TradeObservation, performance_metrics, confidence_calibration, agent_performance, grouped_performance, walk_forward_splits

def sample():
    return [
        TradeObservation(100,80,"TREND","AI",{"Trend":90,"Risk":80}),
        TradeObservation(-50,70,"RANGE","AI",{"Trend":40,"Risk":70}),
        TradeObservation(150,85,"TREND","VWAP",{"Trend":85,"Risk":90}),
    ]

def test_performance_metrics():
    m=performance_metrics(sample(),1000)
    assert m["trade_count"]==3 and m["net_pnl"]==200 and m["profit_factor"]==5

def test_calibration_and_agents():
    assert confidence_calibration(sample())["sample_count"]==3
    assert agent_performance(sample())[0]["samples"]==3

def test_grouping_and_walk_forward():
    assert grouped_performance(sample(),"regime")[0]["regime"]=="TREND"
    assert len(walk_forward_splits(list(range(10)),4,2,2))==3
