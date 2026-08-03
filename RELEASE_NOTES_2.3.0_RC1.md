# VSTradingAI 2.3.0 RC1

## Included
- Package 5: read-only operations console with server resources, structured logs, deployment history, backups, pipeline metrics and Zerodha health.
- Package 6: multi-agent registry, evidence-family visibility, live agent votes, debate and supervisor decision workspace.
- Package 7: conservative Strategy Lab JSON validation, next-bar replay, costs/slippage, metrics and walk-forward split visibility.

## Safety
- Live broker order placement remains disabled.
- Operations endpoints are read-only.
- Strategy Lab never changes production configuration or agent weights.

## Pending
- Real historical-data import from Zerodha into Strategy Lab.
- Persistent strategy experiment catalogue and certification workflow.
- Notification delivery adapters.
- Zerodha live WebSocket and manual order-preview workflow.
