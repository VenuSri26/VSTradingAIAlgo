from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from app.store import _conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trading_day(captured_at: str | None = None) -> str:
    value = captured_at or _now_iso()
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        dt = datetime.now(timezone.utc)
    return dt.date().isoformat()


def _latest(conn: sqlite3.Connection, trading_day: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM live_intelligence_snapshots WHERE trading_day=? ORDER BY id DESC LIMIT 1",
        (trading_day,),
    ).fetchone()


def record_snapshot(analysis: dict[str, Any]) -> dict[str, Any]:
    captured_at = _now_iso()
    day = _trading_day(captured_at)
    with _conn() as conn:
        previous = _latest(conn, day)
        ce_change = None if previous is None else round(float(analysis.get("total_ce_oi") or 0) - float(previous["total_ce_oi"] or 0), 2)
        pe_change = None if previous is None else round(float(analysis.get("total_pe_oi") or 0) - float(previous["total_pe_oi"] or 0), 2)
        pcr = analysis.get("pcr_oi")
        pcr_change = None
        if previous is not None and pcr is not None and previous["pcr_oi"] is not None:
            pcr_change = round(float(pcr) - float(previous["pcr_oi"]), 4)
        cur = conn.execute(
            """
            INSERT INTO live_intelligence_snapshots(
              captured_at,trading_day,source_timestamp,spot,atm_strike,expiry,contracts,
              completeness_pct,total_ce_oi,total_pe_oi,pcr_oi,call_wall,put_wall,max_pain,
              readiness_score,status,recommended_action,ce_oi_change,pe_oi_change,pcr_change,snapshot_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                captured_at, day, analysis.get("captured_at"), analysis.get("spot"), analysis.get("atm_strike"),
                analysis.get("expiry"), int(analysis.get("contracts") or 0), int(analysis.get("completeness_pct") or 0),
                float(analysis.get("total_ce_oi") or 0), float(analysis.get("total_pe_oi") or 0), pcr,
                analysis.get("call_wall"), analysis.get("put_wall"), analysis.get("max_pain"),
                int(analysis.get("readiness_score") or 0), analysis.get("status") or "UNKNOWN",
                analysis.get("recommended_action") or "NO_TRADE", ce_change, pe_change, pcr_change,
                json.dumps(analysis, separators=(",", ":"), default=str),
            ),
        )
        snapshot_id = int(cur.lastrowid)
    return {"id": snapshot_id, "recorded_at": captured_at, "trading_day": day,
            "ce_oi_change": ce_change, "pe_oi_change": pe_change, "pcr_change": pcr_change}


def list_history(limit: int = 120, trading_day: str | None = None) -> list[dict[str, Any]]:
    limit = max(1, min(500, int(limit)))
    day = trading_day or _trading_day()
    with _conn() as conn:
        rows = conn.execute(
            """SELECT id,captured_at,trading_day,source_timestamp,spot,atm_strike,expiry,contracts,
                      completeness_pct,total_ce_oi,total_pe_oi,pcr_oi,call_wall,put_wall,max_pain,
                      readiness_score,status,recommended_action,ce_oi_change,pe_oi_change,pcr_change
               FROM live_intelligence_snapshots WHERE trading_day=? ORDER BY id DESC LIMIT ?""",
            (day, limit),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


def trend(limit: int = 120, trading_day: str | None = None) -> dict[str, Any]:
    history = list_history(limit=limit, trading_day=trading_day)
    if not history:
        return {"trading_day": trading_day or _trading_day(), "samples": 0, "trend": "NO_DATA",
                "pcr_change": None, "ce_oi_change": None, "pe_oi_change": None, "history": []}
    first, last = history[0], history[-1]
    pcr_change = None
    if first.get("pcr_oi") is not None and last.get("pcr_oi") is not None:
        pcr_change = round(float(last["pcr_oi"]) - float(first["pcr_oi"]), 4)
    ce_change = round(float(last.get("total_ce_oi") or 0) - float(first.get("total_ce_oi") or 0), 2)
    pe_change = round(float(last.get("total_pe_oi") or 0) - float(first.get("total_pe_oi") or 0), 2)
    if pcr_change is None:
        label = "INSUFFICIENT_DATA"
    elif pcr_change >= 0.08 and pe_change > ce_change:
        label = "BULLISH_STRENGTHENING"
    elif pcr_change <= -0.08 and ce_change > pe_change:
        label = "BEARISH_STRENGTHENING"
    else:
        label = "STABLE"
    return {"trading_day": last["trading_day"], "samples": len(history), "trend": label,
            "pcr_change": pcr_change, "ce_oi_change": ce_change, "pe_oi_change": pe_change,
            "latest": last, "history": history}
