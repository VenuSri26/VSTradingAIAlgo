# VSTradingAI 4.0.0 RC1

## Release focus
Deterministic test-scenario framework for validating core trading and safety decisions before paper/live market use.

## Added
- Ten built-in trading decision scenarios.
- Bullish CE and bearish PE acceptance scenarios.
- Low-alignment, stale-data, risk-veto, trap, poor RR, market-closed, neutral and option-conflict rejection scenarios.
- `GET /api/test-scenarios` release suite endpoint.
- `POST /api/test-scenarios/evaluate` custom scenario endpoint.
- Test Scenarios dashboard page.
- Automated regression tests ensuring risk vetoes and safety gates fail closed.

## Safety
- Scenario execution never places Zerodha orders.
- Live orders remain disabled.
- Production agent weights are not modified.
