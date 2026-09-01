CREATE TABLE IF NOT EXISTS live_intelligence_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at TEXT NOT NULL,
    trading_day TEXT NOT NULL,
    source_timestamp TEXT,
    spot REAL,
    atm_strike INTEGER,
    expiry TEXT,
    contracts INTEGER NOT NULL DEFAULT 0,
    completeness_pct INTEGER NOT NULL DEFAULT 0,
    total_ce_oi REAL NOT NULL DEFAULT 0,
    total_pe_oi REAL NOT NULL DEFAULT 0,
    pcr_oi REAL,
    call_wall INTEGER,
    put_wall INTEGER,
    max_pain INTEGER,
    readiness_score INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    ce_oi_change REAL,
    pe_oi_change REAL,
    pcr_change REAL,
    snapshot_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_live_intelligence_day_time
ON live_intelligence_snapshots(trading_day, captured_at);
