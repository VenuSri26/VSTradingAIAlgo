"""
Reads today's audit log entries to count SKIPPED / BLOCKED decision events.
Actual trade outcomes (wins/losses/pnl) live in app.store (SQLite), populated
only when a position is explicitly opened/closed — never inferred from polling.
"""
from __future__ import annotations
import json
import os
from datetime import date
from app.config import settings


def todays_skip_and_block_counts() -> tuple[int, int]:
    """Returns (skipped_setups, risk_blocked_setups) for today, counted from
    deduplicated audit log entries (routes.py only logs on decision change,
    so this reflects distinct setups, not poll ticks)."""
    if not os.path.exists(settings.audit_log_path):
        return 0, 0
    today = date.today().isoformat()
    skipped, blocked = 0, 0
    with open(settings.audit_log_path) as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not rec.get("timestamp", "").startswith(today):
                continue
            status = rec.get("outcome_status")
            if status == "SKIPPED":
                skipped += 1
            elif status == "BLOCKED":
                blocked += 1
    return skipped, blocked
