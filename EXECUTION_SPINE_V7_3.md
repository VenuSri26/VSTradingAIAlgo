# VSTradingAI V7.3 — Deterministic Execution Spine

## What this patch changes

This hardens the existing V7.2 manual execution preview without handing broker-write authority to AI/LLM agents.

- SQLite-WAL durable previews, signal IDs, execution IDs, broker tags, order states, and audit events.
- Restart-safe idempotency: duplicate confirmation remains blocked after process restart.
- Fixes preview expiry (V7.2 accidentally set `expires_at` to the creation second).
- Enforces **NIFTY CE/PE BUY-only** at the deterministic backend layer.
- Requires an approved **A/A+ `setup_id`** before a live confirmation is eligible.
- Introduces first-class `UNKNOWN` order state.
- Persists `SUBMITTING` before the broker call.
- Never blindly retries a broker order POST.
- Reconciles UNKNOWN/partial/open orders by a deterministic Kite correlation tag.
- Latches the persistent kill switch if broker reconciliation finds multiple economic orders for one correlation tag.
- Blocks new live entries while any execution is SUBMITTING/ACKNOWLEDGED/OPEN/PARTIAL/UNKNOWN.
- Adds deterministic runtime data-quality and option bid/ask/spread/liquidity gates.
- Adds Prometheus-compatible execution/risk/data-quality metrics helper.

## Required route additions

The current `/api/execution/preview`, `/api/execution/confirm`, and `/api/execution/orders` routes continue to work because `execution_readiness.py` preserves those function names.

Add admin-only routes for explicit live submission and reconciliation as shown in `routes_v73.patch`.

## Safety contract

`Decision/Setup -> A/A+ -> manual preview -> CONFIRM -> AWAITING_BROKER_SUBMISSION -> EXECUTE LIVE -> SUBMITTING -> ACKNOWLEDGED/UNKNOWN -> reconciliation -> broker truth`

`UNKNOWN` is not a retry signal. It means the broker may already have accepted the order.

## Migration

No destructive migration is required. The execution ledger creates three additive tables in the existing SQLite database:

- `execution_previews`
- `execution_orders`
- `execution_events`

The design is intentionally portable to PostgreSQL + transactional outbox + NATS JetStream later.
