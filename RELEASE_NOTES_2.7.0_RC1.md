# V2.7.0 RC1 — Institutional Flow Intelligence

## Included
- Options-flow contribution using V2.6 option-chain intelligence.
- Index-futures positioning input and buildup classification.
- FII/DII cash-flow input interface.
- PCR trend classification.
- Evidence-weighted composite institutional-flow score.
- Explicit missing-feed warnings and zero-confidence components.
- New dashboard workspace and APIs.
- Live order submission remains disabled.

## Limits
The release does not fabricate live FII/DII or futures positioning. When those feeds are not configured, the API explicitly reports them unavailable and computes only from available option-chain evidence.
