CREATE TABLE IF NOT EXISTS paper_trade_management (
    trade_id INTEGER PRIMARY KEY,
    original_quantity INTEGER NOT NULL,
    remaining_quantity INTEGER NOT NULL,
    realized_quantity INTEGER NOT NULL DEFAULT 0,
    realized_gross_pnl REAL NOT NULL DEFAULT 0,
    realized_costs REAL NOT NULL DEFAULT 0,
    highest_price REAL NOT NULL,
    active_stop_loss REAL NOT NULL,
    partial_target_done INTEGER NOT NULL DEFAULT 0,
    breakeven_armed INTEGER NOT NULL DEFAULT 0,
    trailing_enabled INTEGER NOT NULL DEFAULT 1,
    trail_distance_pct REAL NOT NULL DEFAULT 10,
    last_action TEXT NOT NULL DEFAULT 'INITIALIZED',
    updated_at TEXT NOT NULL,
    FOREIGN KEY(trade_id) REFERENCES paper_trades(id)
);
