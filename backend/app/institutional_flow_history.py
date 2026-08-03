from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from statistics import mean, pstdev
from typing import Any

from app import store


def _ensure_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS institutional_flow_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            captured_at TEXT NOT NULL,
            trading_day TEXT NOT NULL,
            spot REAL,
            pcr REAL,
            pcr_trend TEXT,
            institutional_flow_score REAL NOT NULL,
            institutional_bias TEXT NOT NULL,
            confidence REAL NOT NULL,
            options_score REAL,
            futures_score REAL,
            cash_score REAL,
            call_oi_change REAL,
            put_oi_change REAL,
            warning_count INTEGER NOT NULL DEFAULT 0,
            anomaly_score REAL NOT NULL DEFAULT 0,
            anomaly_codes_json TEXT NOT NULL DEFAULT '[]',
            snapshot_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_flow_snapshots_day_time ON institutional_flow_snapshots(trading_day, captured_at)"
    )


def _component_score(summary: dict[str, Any], name: str) -> float | None:
    for component in summary.get("components", []):
        if component.get("name") == name:
            value = component.get("score")
            return float(value) if value is not None else None
    return None


def _today(timestamp: str | None = None) -> str:
    if timestamp:
        try:
            return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            pass
    return datetime.now(timezone.utc).date().isoformat()


def _zscore(value: float, values: list[float]) -> float:
    if len(values) < 5:
        return 0.0
    deviation = pstdev(values)
    if deviation <= 1e-9:
        return 0.0
    return (value - mean(values)) / deviation


def detect_flow_anomalies(summary: dict[str, Any], recent: list[dict[str, Any]]) -> dict[str, Any]:
    codes: list[str] = []
    details: list[str] = []
    pcr = float(summary.get("pcr") or 1.0)
    score = float(summary.get("institutional_flow_score") or 0.0)
    confidence = float(summary.get("confidence") or 0.0)

    historical_pcr = [float(row["pcr"]) for row in recent if row.get("pcr") is not None]
    historical_scores = [float(row["institutional_flow_score"]) for row in recent]
    pcr_z = _zscore(pcr, historical_pcr)
    score_z = _zscore(score, historical_scores)

    if abs(pcr_z) >= 2.0:
        codes.append("PCR_OUTLIER")
        details.append(f"PCR deviates {abs(pcr_z):.1f} standard deviations from the session mean")
    if abs(score_z) >= 2.0:
        codes.append("FLOW_SCORE_OUTLIER")
        details.append(f"Flow score deviates {abs(score_z):.1f} standard deviations from the session mean")
    if confidence >= 55 and summary.get("institutional_bias") == "BULLISH" and pcr < 0.75:
        codes.append("BULLISH_PCR_DIVERGENCE")
        details.append("Bullish composite flow conflicts with a low PCR")
    if confidence >= 55 and summary.get("institutional_bias") == "BEARISH" and pcr > 1.30:
        codes.append("BEARISH_PCR_DIVERGENCE")
        details.append("Bearish composite flow conflicts with a high PCR")
    if recent:
        previous = recent[-1]
        previous_score = float(previous.get("institutional_flow_score") or 0.0)
        if abs(score - previous_score) >= 35:
            codes.append("RAPID_FLOW_REVERSAL")
            details.append(f"Composite flow changed {score - previous_score:+.1f} points since the previous snapshot")

    severity = min(100.0, abs(pcr_z) * 18 + abs(score_z) * 18 + len(codes) * 12)
    return {
        "anomaly": bool(codes),
        "anomaly_score": round(severity, 2),
        "codes": codes,
        "details": details,
        "pcr_zscore": round(pcr_z, 3),
        "flow_score_zscore": round(score_z, 3),
    }


def record_flow_snapshot(summary: dict[str, Any], option_summary: dict[str, Any] | None = None,
                         captured_at: str | None = None) -> dict[str, Any]:
    captured_at = captured_at or datetime.now(timezone.utc).isoformat()
    trading_day = _today(captured_at)
    recent = list_flow_history(limit=60, trading_day=trading_day)
    anomaly = detect_flow_anomalies(summary, recent)
    option_summary = option_summary or {}
    payload = {
        **summary,
        "captured_at": captured_at,
        "option_summary": option_summary,
        "anomaly": anomaly,
    }
    with store._conn() as conn:
        _ensure_schema(conn)
        cur = conn.execute(
            """
            INSERT INTO institutional_flow_snapshots (
                captured_at, trading_day, spot, pcr, pcr_trend, institutional_flow_score,
                institutional_bias, confidence, options_score, futures_score, cash_score,
                call_oi_change, put_oi_change, warning_count, anomaly_score,
                anomaly_codes_json, snapshot_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                captured_at, trading_day, option_summary.get("spot"), summary.get("pcr"),
                summary.get("pcr_trend"), summary.get("institutional_flow_score"),
                summary.get("institutional_bias"), summary.get("confidence"),
                _component_score(summary, "OPTIONS_FLOW"), _component_score(summary, "INDEX_FUTURES"),
                _component_score(summary, "CASH_FLOW"), option_summary.get("total_ce_oi_change"),
                option_summary.get("total_pe_oi_change"), len(summary.get("warnings", [])),
                anomaly["anomaly_score"], json.dumps(anomaly["codes"]),
                json.dumps(payload, default=str, separators=(",", ":")),
            ),
        )
        snapshot_id = int(cur.lastrowid)
    return {"id": snapshot_id, **payload}


def list_flow_history(limit: int = 120, trading_day: str | None = None) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 1000))
    with store._conn() as conn:
        _ensure_schema(conn)
        if trading_day:
            rows = conn.execute(
                "SELECT * FROM institutional_flow_snapshots WHERE trading_day = ? ORDER BY captured_at ASC LIMIT ?",
                (trading_day, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM institutional_flow_snapshots ORDER BY captured_at DESC LIMIT ?", (limit,)
            ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        try:
            item["anomaly_codes"] = json.loads(item.pop("anomaly_codes_json"))
        except (TypeError, json.JSONDecodeError):
            item["anomaly_codes"] = []
        item.pop("snapshot_json", None)
        result.append(item)
    if not trading_day:
        result.reverse()
    return result


def flow_trend(limit: int = 120, trading_day: str | None = None) -> dict[str, Any]:
    rows = list_flow_history(limit=limit, trading_day=trading_day or _today())
    if not rows:
        return {
            "trading_day": trading_day or _today(), "samples": 0, "trend": "UNAVAILABLE",
            "score_change": 0.0, "pcr_change": 0.0, "latest": None, "points": [],
        }
    first, latest = rows[0], rows[-1]
    score_change = float(latest["institutional_flow_score"]) - float(first["institutional_flow_score"])
    first_pcr = float(first.get("pcr") or 0.0)
    last_pcr = float(latest.get("pcr") or 0.0)
    trend = "STRENGTHENING_BULLISH" if score_change >= 12 else "STRENGTHENING_BEARISH" if score_change <= -12 else "STABLE"
    return {
        "trading_day": latest["trading_day"], "samples": len(rows), "trend": trend,
        "score_change": round(score_change, 2), "pcr_change": round(last_pcr - first_pcr, 4),
        "latest": latest, "points": rows,
    }


def recent_anomalies(limit: int = 20) -> list[dict[str, Any]]:
    rows = list_flow_history(limit=500)
    anomalies = [row for row in rows if row.get("anomaly_codes")]
    return anomalies[-max(1, min(limit, 100)):][::-1]


def nearest_flow_snapshot(timestamp: str | None) -> dict[str, Any] | None:
    if not timestamp:
        return None
    with store._conn() as conn:
        _ensure_schema(conn)
        row = conn.execute(
            """
            SELECT snapshot_json FROM institutional_flow_snapshots
            ORDER BY ABS(strftime('%s', captured_at) - strftime('%s', ?)) ASC LIMIT 1
            """,
            (timestamp,),
        ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row["snapshot_json"])
    except (TypeError, json.JSONDecodeError):
        return None
