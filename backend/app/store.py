"""
SQLite persistence layer for session counters and positions.

Replaces the in-memory SessionState stub — this is the actual data the
Risk Agent, Session Analytics card, and Position card need to survive a
backend restart (spec section 25/44 "existing functionality remains intact"
implies state shouldn't vanish every time uvicorn --reload kicks in).

Uses stdlib sqlite3 only — no extra dependency, works fully offline.
"""
from __future__ import annotations
import sqlite3
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from dataclasses import dataclass, asdict
from typing import Optional

from app.config import settings
from app.migrations import apply_migrations

DB_PATH = os.getenv("SQLITE_DB_PATH", os.path.join(os.path.dirname(settings.audit_log_path) or ".", "vstradingai.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    trading_day TEXT PRIMARY KEY,
    trades_today INTEGER NOT NULL DEFAULT 0,
    daily_pnl REAL NOT NULL DEFAULT 0,
    gross_pnl REAL NOT NULL DEFAULT 0,
    consecutive_losses INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    a_plus_trades INTEGER NOT NULL DEFAULT 0,
    a_trades INTEGER NOT NULL DEFAULT 0,
    skipped_setups INTEGER NOT NULL DEFAULT 0,
    risk_blocked_setups INTEGER NOT NULL DEFAULT 0,
    best_trade REAL,
    worst_trade REAL
);

CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trading_day TEXT NOT NULL,
    option_type TEXT NOT NULL,
    strike INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    stop_loss REAL,
    target_1 REAL,
    target_2 REAL,
    opened_at TEXT NOT NULL,
    closed_at TEXT,
    close_price REAL,
    status TEXT NOT NULL DEFAULT 'OPEN',  -- OPEN | CLOSED_TARGET | CLOSED_SL | CLOSED_MANUAL
    pnl REAL
);
CREATE UNIQUE INDEX IF NOT EXISTS one_open_position ON positions(status) WHERE status = 'OPEN';
CREATE INDEX IF NOT EXISTS idx_positions_trading_day ON positions(trading_day);

CREATE TABLE IF NOT EXISTS trade_setups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signature TEXT NOT NULL UNIQUE,
    trading_day TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    decision TEXT NOT NULL,
    grade TEXT NOT NULL,
    alignment_score INTEGER,
    option_type TEXT,
    strike INTEGER,
    entry_low REAL,
    entry_high REAL,
    stop_loss REAL,
    target_1 REAL,
    target_2 REAL,
    risk_reward REAL,
    explanation TEXT,
    snapshot_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'GENERATED',
    reviewed_at TEXT,
    review_note TEXT
);
CREATE INDEX IF NOT EXISTS idx_trade_setups_day_status ON trade_setups(trading_day, status);

CREATE TABLE IF NOT EXISTS paper_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    setup_id INTEGER NOT NULL UNIQUE,
    trading_day TEXT NOT NULL,
    option_type TEXT NOT NULL,
    strike INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    stop_loss REAL NOT NULL,
    target_1 REAL,
    target_2 REAL,
    opened_at TEXT NOT NULL,
    closed_at TEXT,
    close_price REAL,
    status TEXT NOT NULL DEFAULT 'OPEN',
    gross_pnl REAL,
    estimated_costs REAL NOT NULL DEFAULT 0,
    net_pnl REAL,
    exit_reason TEXT,
    FOREIGN KEY(setup_id) REFERENCES trade_setups(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_open_paper_trade ON paper_trades(status) WHERE status = 'OPEN';
CREATE INDEX IF NOT EXISTS idx_paper_trades_day_status ON paper_trades(trading_day, status);

CREATE TABLE IF NOT EXISTS paper_monitor_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER NOT NULL,
    checked_at TEXT NOT NULL,
    current_price REAL,
    action TEXT NOT NULL,
    detail TEXT,
    FOREIGN KEY(trade_id) REFERENCES paper_trades(id)
);
CREATE INDEX IF NOT EXISTS idx_paper_monitor_events_trade ON paper_monitor_events(trade_id, id DESC);

CREATE TABLE IF NOT EXISTS risk_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    kill_switch INTEGER NOT NULL DEFAULT 0,
    reason TEXT,
    updated_at TEXT NOT NULL
);
INSERT OR IGNORE INTO risk_state(id, kill_switch, reason, updated_at) VALUES (1, 0, NULL, CURRENT_TIMESTAMP);
"""


@contextmanager
def _conn():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        apply_migrations(conn)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _today() -> str:
    return datetime.now(ZoneInfo(settings.app_timezone)).date().isoformat()


def get_or_create_session_row(trading_day: str | None = None) -> sqlite3.Row:
    trading_day = trading_day or _today()
    with _conn() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE trading_day = ?", (trading_day,)).fetchone()
        if row is None:
            conn.execute("INSERT INTO sessions (trading_day) VALUES (?)", (trading_day,))
            row = conn.execute("SELECT * FROM sessions WHERE trading_day = ?", (trading_day,)).fetchone()
        return row


def get_session_dict(trading_day: str | None = None) -> dict:
    row = get_or_create_session_row(trading_day)
    return dict(row)


def record_trade_result(pnl: float, grade: str, trading_day: str | None = None) -> None:
    """Called when a position is closed. Updates daily counters atomically."""
    trading_day = trading_day or _today()
    get_or_create_session_row(trading_day)
    with _conn() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE trading_day = ?", (trading_day,)).fetchone()
        d = dict(row)
        win = pnl > 0
        consecutive_losses = 0 if win else d["consecutive_losses"] + 1
        best = pnl if d["best_trade"] is None else max(d["best_trade"], pnl)
        worst = pnl if d["worst_trade"] is None else min(d["worst_trade"], pnl)
        conn.execute(
            """UPDATE sessions SET
                 trades_today = trades_today + 1,
                 daily_pnl = daily_pnl + ?,
                 gross_pnl = gross_pnl + ?,
                 wins = wins + ?,
                 losses = losses + ?,
                 consecutive_losses = ?,
                 a_plus_trades = a_plus_trades + ?,
                 a_trades = a_trades + ?,
                 best_trade = ?,
                 worst_trade = ?
               WHERE trading_day = ?""",
            (pnl, abs(pnl), 1 if win else 0, 0 if win else 1, consecutive_losses,
             1 if grade == "A+" else 0, 1 if grade == "A" else 0, best, worst, trading_day),
        )


def record_skip(risk_blocked: bool, trading_day: str | None = None) -> None:
    trading_day = trading_day or _today()
    get_or_create_session_row(trading_day)
    col = "risk_blocked_setups" if risk_blocked else "skipped_setups"
    with _conn() as conn:
        conn.execute(f"UPDATE sessions SET {col} = {col} + 1 WHERE trading_day = ?", (trading_day,))


def open_position(option_type: str, strike: int, quantity: int, entry_price: float,
                   stop_loss: float | None, target_1: float | None, target_2: float | None) -> int:
    trading_day = _today()
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO positions (trading_day, option_type, strike, quantity, entry_price,
                 stop_loss, target_1, target_2, opened_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')""",
            (trading_day, option_type, strike, quantity, entry_price, stop_loss, target_1, target_2,
             datetime.now(timezone.utc).isoformat()),
        )
        return cur.lastrowid


def get_open_position() -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM positions WHERE status = 'OPEN' ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None


def close_position(position_id: int, close_price: float, status: str) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM positions WHERE id = ?", (position_id,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        pnl = (close_price - d["entry_price"]) * d["quantity"]
        conn.execute(
            "UPDATE positions SET closed_at = ?, close_price = ?, status = ?, pnl = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), close_price, status, pnl, position_id),
        )
        d.update(close_price=close_price, status=status, pnl=pnl)
        return d


def create_trade_setup(signature: str, payload: dict) -> int | None:
    """Persist an actionable generated setup once. Returns None for duplicates."""
    import json
    decision = payload.get("decision", {})
    plan = decision.get("plan") or {}
    try:
        with _conn() as conn:
            cur = conn.execute(
                """INSERT INTO trade_setups (signature, trading_day, generated_at, decision, grade,
                   alignment_score, option_type, strike, entry_low, entry_high, stop_loss, target_1,
                   target_2, risk_reward, explanation, snapshot_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (signature, _today(), payload.get("timestamp") or datetime.now(timezone.utc).isoformat(),
                 decision.get("decision"), decision.get("grade"), decision.get("alignment_score"),
                 plan.get("option_type"), plan.get("strike"), plan.get("entry_low"), plan.get("entry_high"),
                 plan.get("stop_loss"), plan.get("target_1"), plan.get("target_2"), plan.get("risk_reward"),
                 decision.get("explanation"), json.dumps(payload, default=str, separators=(",", ":"))),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def list_trade_setups(trading_day: str | None = None, status: str | None = None, limit: int = 50) -> list[dict]:
    clauses, values = [], []
    if trading_day:
        clauses.append("trading_day = ?")
        values.append(trading_day)
    if status:
        clauses.append("status = ?")
        values.append(status)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    values.append(max(1, min(limit, 200)))
    with _conn() as conn:
        rows = conn.execute(
            f"SELECT id, signature, trading_day, generated_at, decision, grade, alignment_score, option_type, "
            f"strike, entry_low, entry_high, stop_loss, target_1, target_2, risk_reward, explanation, status, "
            f"reviewed_at, review_note FROM trade_setups{where} ORDER BY id DESC LIMIT ?", values
        ).fetchall()
        return [dict(r) for r in rows]


def review_trade_setup(setup_id: int, status: str, note: str | None = None) -> dict | None:
    if status not in {"APPROVED", "REJECTED", "EXPIRED", "CANCELLED"}:
        raise ValueError("Unsupported setup review status")
    with _conn() as conn:
        row = conn.execute("SELECT * FROM trade_setups WHERE id = ?", (setup_id,)).fetchone()
        if row is None:
            return None
        if row["status"] != "GENERATED":
            raise ValueError(f"Setup is already {row['status']}")
        reviewed_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE trade_setups SET status = ?, reviewed_at = ?, review_note = ? WHERE id = ?",
            (status, reviewed_at, note, setup_id),
        )
        result = dict(row)
        result.update(status=status, reviewed_at=reviewed_at, review_note=note)
        return result


def get_trade_setup(setup_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM trade_setups WHERE id = ?", (setup_id,)).fetchone()
        return dict(row) if row else None


def open_paper_trade(setup_id: int, quantity: int, entry_price: float, slippage_rupees: float = 0.0) -> int:
    setup = get_trade_setup(setup_id)
    if setup is None:
        raise ValueError("Trade setup not found")
    if setup["status"] != "APPROVED":
        raise ValueError("Only APPROVED setups can be paper executed")
    if not setup.get("option_type") or not setup.get("strike") or not setup.get("stop_loss"):
        raise ValueError("Setup has incomplete option plan")
    effective_entry = round(entry_price + max(0.0, slippage_rupees), 2)
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO paper_trades (setup_id, trading_day, option_type, strike, quantity,
               entry_price, stop_loss, target_1, target_2, opened_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')""",
            (setup_id, _today(), setup["option_type"], setup["strike"], quantity, effective_entry,
             setup["stop_loss"], setup["target_1"], setup["target_2"], datetime.now(timezone.utc).isoformat()),
        )
        conn.execute("UPDATE trade_setups SET status = 'PAPER_OPEN' WHERE id = ?", (setup_id,))
        return cur.lastrowid


def get_open_paper_trade() -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM paper_trades WHERE status = 'OPEN' ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None


def list_paper_trades(trading_day: str | None = None, status: str | None = None, limit: int = 50) -> list[dict]:
    clauses, values = [], []
    if trading_day:
        clauses.append("trading_day = ?"); values.append(trading_day)
    if status:
        clauses.append("status = ?"); values.append(status)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    values.append(max(1, min(limit, 200)))
    with _conn() as conn:
        rows = conn.execute(f"SELECT * FROM paper_trades{where} ORDER BY id DESC LIMIT ?", values).fetchall()
        return [dict(r) for r in rows]


def close_paper_trade(trade_id: int, close_price: float, status: str, estimated_costs: float, exit_reason: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM paper_trades WHERE id = ?", (trade_id,)).fetchone()
        if row is None or row["status"] != "OPEN":
            return None
        gross = round((close_price - row["entry_price"]) * row["quantity"], 2)
        costs = round(max(0.0, estimated_costs), 2)
        net = round(gross - costs, 2)
        closed_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """UPDATE paper_trades SET closed_at=?, close_price=?, status=?, gross_pnl=?,
               estimated_costs=?, net_pnl=?, exit_reason=? WHERE id=?""",
            (closed_at, close_price, status, gross, costs, net, exit_reason, trade_id),
        )
        conn.execute("UPDATE trade_setups SET status = 'PAPER_CLOSED' WHERE id = ?", (row["setup_id"],))
        result = dict(row)
        result.update(closed_at=closed_at, close_price=close_price, status=status, gross_pnl=gross,
                      estimated_costs=costs, net_pnl=net, exit_reason=exit_reason)
        return result


def record_paper_monitor_event(trade_id: int, current_price: float | None, action: str, detail: str | None) -> int:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO paper_monitor_events (trade_id, checked_at, current_price, action, detail) VALUES (?, ?, ?, ?, ?)",
            (trade_id, datetime.now(timezone.utc).isoformat(), current_price, action, detail),
        )
        return cur.lastrowid


def list_paper_monitor_events(trade_id: int | None = None, limit: int = 100) -> list[dict]:
    limit = max(1, min(limit, 500))
    with _conn() as conn:
        if trade_id is None:
            rows = conn.execute("SELECT * FROM paper_monitor_events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM paper_monitor_events WHERE trade_id=? ORDER BY id DESC LIMIT ?", (trade_id, limit)).fetchall()
        return [dict(r) for r in rows]


def get_risk_state() -> dict:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM risk_state WHERE id = 1").fetchone()
        return dict(row)


def set_kill_switch(enabled: bool, reason: str | None = None) -> dict:
    updated_at = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute(
            "UPDATE risk_state SET kill_switch=?, reason=?, updated_at=? WHERE id=1",
            (1 if enabled else 0, reason, updated_at),
        )
    return {"kill_switch": enabled, "reason": reason, "updated_at": updated_at}


def paper_portfolio_summary(trading_day: str | None = None) -> dict:
    with _conn() as conn:
        params: tuple = ()
        where = ""
        if trading_day:
            where = " WHERE trading_day = ?"
            params = (trading_day,)
        rows = [dict(r) for r in conn.execute(f"SELECT * FROM paper_trades{where} ORDER BY id", params).fetchall()]
    closed = [r for r in rows if r["status"] != "OPEN"]
    wins = [r for r in closed if (r.get("net_pnl") or 0) > 0]
    losses = [r for r in closed if (r.get("net_pnl") or 0) <= 0]
    net = round(sum((r.get("net_pnl") or 0) for r in closed), 2)
    gross = round(sum((r.get("gross_pnl") or 0) for r in closed), 2)
    costs = round(sum((r.get("estimated_costs") or 0) for r in closed), 2)
    avg_win = round(sum((r.get("net_pnl") or 0) for r in wins) / len(wins), 2) if wins else 0.0
    avg_loss = round(sum((r.get("net_pnl") or 0) for r in losses) / len(losses), 2) if losses else 0.0
    return {
        "total_trades": len(rows), "open_trades": len(rows) - len(closed), "closed_trades": len(closed),
        "wins": len(wins), "losses": len(losses),
        "win_rate": round(len(wins) / len(closed) * 100, 2) if closed else 0.0,
        "gross_pnl": gross, "estimated_costs": costs, "net_pnl": net,
        "avg_win": avg_win, "avg_loss": avg_loss,
    }


def get_trade_timeline(trade_id: int) -> dict | None:
    with _conn() as conn:
        trade = conn.execute("SELECT * FROM paper_trades WHERE id=?", (trade_id,)).fetchone()
        if trade is None:
            return None
        setup = conn.execute("SELECT * FROM trade_setups WHERE id=?", (trade["setup_id"],)).fetchone()
        events = conn.execute("SELECT * FROM paper_monitor_events WHERE trade_id=? ORDER BY id", (trade_id,)).fetchall()
    return {"trade": dict(trade), "setup": dict(setup) if setup else None, "events": [dict(e) for e in events]}


def paper_analytics_summary() -> dict:
    """Return evidence-based analytics from closed paper trades only.

    Open trades are excluded from realized performance. Equity is cumulative
    net P&L ordered by close time, so the response can be graphed directly.
    """
    with _conn() as conn:
        rows = [dict(r) for r in conn.execute(
            """SELECT p.*, s.grade, s.decision, s.alignment_score
               FROM paper_trades p
               LEFT JOIN trade_setups s ON s.id = p.setup_id
               WHERE p.status != 'OPEN'
               ORDER BY COALESCE(p.closed_at, p.opened_at), p.id"""
        ).fetchall()]

    wins = [r for r in rows if float(r.get("net_pnl") or 0) > 0]
    losses = [r for r in rows if float(r.get("net_pnl") or 0) <= 0]
    gross_profit = sum(float(r.get("net_pnl") or 0) for r in wins)
    gross_loss = abs(sum(float(r.get("net_pnl") or 0) for r in losses))
    net_pnl = sum(float(r.get("net_pnl") or 0) for r in rows)
    avg_win = gross_profit / len(wins) if wins else 0.0
    avg_loss = -gross_loss / len(losses) if losses else 0.0
    expectancy = net_pnl / len(rows) if rows else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (None if not wins else 999.0)

    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0
    equity_curve = []
    daily: dict[str, dict] = {}
    by_option: dict[str, dict] = {}
    by_grade: dict[str, dict] = {}
    by_exit: dict[str, dict] = {}

    def add_bucket(target: dict[str, dict], key: str, pnl: float) -> None:
        bucket = target.setdefault(key, {"trades": 0, "wins": 0, "losses": 0, "net_pnl": 0.0})
        bucket["trades"] += 1
        bucket["wins" if pnl > 0 else "losses"] += 1
        bucket["net_pnl"] = round(float(bucket["net_pnl"]) + pnl, 2)

    for row in rows:
        pnl = float(row.get("net_pnl") or 0)
        cumulative += pnl
        peak = max(peak, cumulative)
        drawdown = peak - cumulative
        max_drawdown = max(max_drawdown, drawdown)
        equity_curve.append({
            "trade_id": row["id"],
            "timestamp": row.get("closed_at") or row.get("opened_at"),
            "net_pnl": round(pnl, 2),
            "equity": round(cumulative, 2),
            "drawdown": round(drawdown, 2),
        })
        day = row.get("trading_day") or "UNKNOWN"
        add_bucket(daily, day, pnl)
        add_bucket(by_option, row.get("option_type") or "UNKNOWN", pnl)
        add_bucket(by_grade, row.get("grade") or "UNKNOWN", pnl)
        add_bucket(by_exit, row.get("exit_reason") or row.get("status") or "UNKNOWN", pnl)

    for groups in (daily, by_option, by_grade, by_exit):
        for bucket in groups.values():
            bucket["win_rate"] = round(bucket["wins"] / bucket["trades"] * 100, 2) if bucket["trades"] else 0.0

    return {
        "summary": {
            "total_trades": len(rows),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(rows) * 100, 2) if rows else 0.0,
            "net_pnl": round(net_pnl, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "expectancy": round(expectancy, 2),
            "profit_factor": None if profit_factor is None else round(profit_factor, 2),
            "max_drawdown": round(max_drawdown, 2),
        },
        "equity_curve": equity_curve,
        "daily": [{"trading_day": day, **values} for day, values in sorted(daily.items())],
        "by_option_type": by_option,
        "by_grade": by_grade,
        "by_exit_reason": by_exit,
    }


def list_decision_replays(limit: int = 50) -> list[dict]:
    limit = max(1, min(limit, 200))
    with _conn() as conn:
        rows = conn.execute(
            """SELECT p.id AS trade_id, p.setup_id, p.trading_day, p.option_type, p.strike,
                      p.quantity, p.entry_price, p.close_price, p.status, p.net_pnl,
                      p.exit_reason, p.opened_at, p.closed_at,
                      s.decision, s.grade, s.alignment_score, s.explanation
               FROM paper_trades p
               LEFT JOIN trade_setups s ON s.id = p.setup_id
               ORDER BY p.id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_decision_replay(trade_id: int) -> dict | None:
    timeline = get_trade_timeline(trade_id)
    if timeline is None:
        return None
    setup = timeline.get("setup")
    snapshot = None
    if setup and setup.get("snapshot_json"):
        try:
            snapshot = json.loads(setup["snapshot_json"])
        except (TypeError, json.JSONDecodeError):
            snapshot = None
    institutional_flow_evidence = None
    try:
        from app.institutional_flow_history import nearest_flow_snapshot
        institutional_flow_evidence = nearest_flow_snapshot(timeline.get("trade", {}).get("opened_at"))
    except Exception:
        institutional_flow_evidence = None
    return {
        **timeline,
        "market_snapshot": snapshot,
        "institutional_flow_evidence": institutional_flow_evidence,
        "replay_version": 2,
        "execution_mode": "PAPER_ONLY",
    }
