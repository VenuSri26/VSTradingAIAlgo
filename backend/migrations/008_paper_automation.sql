CREATE TABLE IF NOT EXISTS paper_automation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checked_at TEXT NOT NULL,
    trading_day TEXT NOT NULL,
    cycle_key TEXT,
    action TEXT NOT NULL,
    reason TEXT,
    setup_id INTEGER,
    trade_id INTEGER,
    details_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_paper_automation_runs_day
    ON paper_automation_runs(trading_day, id DESC);
CREATE UNIQUE INDEX IF NOT EXISTS one_paper_automation_run_per_cycle
    ON paper_automation_runs(cycle_key) WHERE cycle_key IS NOT NULL;
