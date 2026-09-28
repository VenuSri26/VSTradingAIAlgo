ALTER TABLE paper_trades ADD COLUMN entry_reference REAL;
ALTER TABLE paper_trades ADD COLUMN entry_slippage REAL NOT NULL DEFAULT 0;
ALTER TABLE paper_trade_management ADD COLUMN lowest_price REAL;

UPDATE paper_trades
SET entry_reference = entry_price
WHERE entry_reference IS NULL;

UPDATE paper_trade_management
SET lowest_price = highest_price
WHERE lowest_price IS NULL;
