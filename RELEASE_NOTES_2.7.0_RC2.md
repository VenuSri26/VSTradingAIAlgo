# VSTradingAI 2.7.0 RC2

## Added
- Persistent intraday institutional-flow snapshots in SQLite.
- PCR and composite-flow session trend APIs.
- Institutional-flow anomaly detection and rapid-reversal alerts.
- Flow-adjusted decision-confidence endpoint.
- Institutional-flow evidence in paper-trade decision replay.
- Dashboard trend, anomaly and decision-intelligence panels.

## Safety
- Missing FII/DII and futures feeds remain explicit and receive zero confidence.
- Institutional flow cannot authorize live orders.
- Automatic Zerodha order placement remains disabled.
