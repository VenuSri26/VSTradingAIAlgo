CREATE TABLE IF NOT EXISTS risk_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    kill_switch INTEGER NOT NULL DEFAULT 0,
    reason TEXT,
    updated_at TEXT NOT NULL
);
INSERT OR IGNORE INTO risk_state(id, kill_switch, reason, updated_at) VALUES (1, 0, NULL, CURRENT_TIMESTAMP);
