# V7.6.0 — Overfitting-Resistant Research Certification

V7.6.0 strengthens the offline Strategy Lab. It does not change signals,
execution settings, broker access, or production strategy weights.

## Added

- Purged and embargoed expanding walk-forward splits.
- Probabilistic Sharpe Ratio for a selected return series.
- Deflated Sharpe Ratio (DSR) adjusted for repeated strategy trials and
  non-normal returns.
- A fail-closed research-trial report with `CERTIFIED_RESEARCH_CANDIDATE`,
  `REJECTED`, or `INSUFFICIENT_EVIDENCE` status.
- Strategy Lab request/response fields for advanced validation evidence.

## Improvement over the previous code

The prior walk-forward helper only returned adjacent chronological train/test
ranges. It could not exclude observations near a fold boundary, remember an
embargo after a test period, or distinguish a genuine result from the best of
many attempted configurations.

The new controls:

- make leakage gaps visible and machine-verifiable;
- require all attempted trials, including failures, to be represented;
- penalize the selected Sharpe for multiple testing, skew, kurtosis, and sample
  length;
- refuse certification when the trial count or observation history is
  insufficient; and
- keep every result research-only, with no automatic production promotion.

## Required interpretation

- Returns for all trials must use the same frequency and cost assumptions.
- `purge_size` must cover the maximum label/feature overlap before the test
  fold.
- `embargo_size` must cover the chosen post-test contamination horizon.
- A passing DSR is evidence for further shadow/paper evaluation, not evidence
  that a live strategy will be profitable.

## Research and implementation references

- Bailey, Borwein, López de Prado, and Zhu, *The Probability of Backtest
  Overfitting* (CSCV/PBO and full trial accounting):
  `https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253`
- Bailey and López de Prado, *The Deflated Sharpe Ratio* (selection bias,
  non-normality, and multiple testing):
  `https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf`
- Arnott, Harvey, and Markowitz, *A Backtesting Protocol in the Era of Machine
  Learning* (research governance and holdout discipline):
  `https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3275654`
- skfolio `CombinatorialPurgedCV` documentation, reviewed as a current
  open-source implementation reference:
  `https://skfolio.org/generated/skfolio.model_selection.CombinatorialPurgedCV.html`

## Safety boundary

The certification code is offline and deterministic. It never calls a broker,
changes environment variables, updates live strategy parameters, or enables
orders. Live orders remain disabled by default and AWS is unchanged.
