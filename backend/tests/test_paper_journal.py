from app.paper_journal import journal_csv, journal_rows, daily_summary


def test_empty_journal_is_exportable(monkeypatch):
    monkeypatch.setattr("app.paper_journal.store.list_paper_trades", lambda **kwargs: [])
    text = journal_csv()
    assert text.startswith("trade_id,trading_day")
    assert journal_rows() == []


def test_daily_summary_is_paper_only(monkeypatch):
    monkeypatch.setattr("app.paper_journal.store.paper_portfolio_summary", lambda day: {"total_trades": 0})
    monkeypatch.setattr("app.paper_journal.journal_rows", lambda trading_day=None, limit=200: [])
    result = daily_summary()
    assert result["execution_mode"] == "PAPER_ONLY"
    assert result["broker_orders_sent"] is False
