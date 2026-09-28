# V7.8 Research Adoption Record

VSTradingAI uses selected engineering patterns from the GitHub and article
research collected during development. External repositories were treated as
design references, not copied as unverified trading strategies.

## Adopted in the current code

| Research concept | VSTradingAI implementation |
| --- | --- |
| Refuse to trade without verifiable edge/data | Fail-closed data quality, freshness, alignment, grade and risk gates |
| Layered specialist agents | Trend, structure, options, institutional, gamma, liquidity and risk evidence feeding a supervisor |
| Adversarial risk review | Independent risk supervisor, kill switch, daily loss/trade limits and execution readiness gates |
| Evidence-based promotion | Production-candidate, resilience, consensus and live-session certification reports |
| Experiment/replay lineage | Deterministic replay, no-lookahead data source, strategy validation and Git commit/release lineage |
| Restart-safe autonomous systems | SQLite paper ledger, cycle deduplication, persistent monitor state and deployment rollback |
| Tool-rich financial analyst | Separate API tools for market state, agents, explanations, replay, analytics, operations and certification |
| Human-readable observability | Alerts, operational digest, journal, timeline and V7.8 Auto Paper dashboard |

## Selectively deferred

- **ATLAS-style Darwinian prompt/agent weighting:** the learning engine measures
  agent reliability, but it does not automatically promote weights into
  production. Automatic self-modification remains unsafe without larger,
  regime-balanced evidence.
- **Jev-style 24/7 orchestration:** useful for development/test automation, but
  the NIFTY execution loop remains market-calendar aware and intentionally
  sleeps outside the NSE session.
- **Reinforcement learning and autonomous strategy mutation:** retained as
  research-only until leakage-safe datasets, transaction costs and walk-forward
  thresholds are satisfied.
- **Automatic live broker execution:** explicitly out of scope for V7.8. Live
  orders remain disabled; the autonomous worker can only create paper trades.

## V7.8 completion boundary

The `/api/paper/readiness` certificate verifies everything that can be checked
without live market data. The remaining evidence must come from actual market
sessions: authenticated fresh quotes, full-session reliability, observed paper
entry/management/exit, and a multi-session performance sample.
