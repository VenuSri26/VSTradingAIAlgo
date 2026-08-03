# VSTradingAI 2.8.0 RC1

Cumulative release built from V2.7.0 RC2.

## Added
- AI Supervisor v2 with weighted scores, votes, grade and A/A+ filter.
- Market regime intelligence.
- Smart-money structure analysis: BOS, CHOCH, liquidity sweep, FVG and order-block foundation.
- Greeks-based gamma exposure, gamma flip, gamma walls and pinning zone foundation.
- AI Command Center API and dashboard page.
- Regression tests for all V2.8 intelligence modules.

## Safety
- Decision support and paper trading only.
- Live Zerodha order submission remains disabled.
- Missing live candles/option data reduces confidence rather than fabricating evidence.
