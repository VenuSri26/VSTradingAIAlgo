import { useEffect, useMemo, useState } from "react";
import { PageCard, StatTile } from "../components/PageCard";
import { api } from "../services/api";
import type { PaperTrade } from "../types/operations";

export function PortfolioPage() {
  const [trades, setTrades] = useState<PaperTrade[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getPaperTrades()
      .then((response) => setTrades(response.trades))
      .catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)));
  }, []);

  const summary = useMemo(() => {
    const closed = trades.filter((trade) => trade.status !== "OPEN");
    const net = closed.reduce((total, trade) => total + (trade.net_pnl ?? 0), 0);
    const wins = closed.filter((trade) => (trade.net_pnl ?? 0) > 0).length;
    return {
      open: trades.filter((trade) => trade.status === "OPEN").length,
      closed: closed.length,
      net,
      winRate: closed.length ? (wins / closed.length) * 100 : 0,
    };
  }, [trades]);

  return (
    <div className="page-stack">
      <div className="stat-grid">
        <StatTile label="Open paper trades" value={summary.open} />
        <StatTile label="Closed trades" value={summary.closed} />
        <StatTile label="Net paper P&L" value={`₹${summary.net.toFixed(2)}`} />
        <StatTile label="Win rate" value={`${summary.winRate.toFixed(1)}%`} />
      </div>

      <PageCard title="Paper Trade Journal" accent="#7c6ff7">
        {error ? <div className="error-box">{error}</div> : null}
        <div className="table-scroll">
          <table className="data-table">
            <thead><tr><th>ID</th><th>Contract</th><th>Qty</th><th>Entry</th><th>Status</th><th>Net P&L</th><th>Exit reason</th></tr></thead>
            <tbody>
              {trades.length === 0 ? (
                <tr><td colSpan={7} className="empty-cell">No paper trades recorded yet.</td></tr>
              ) : trades.map((trade) => (
                <tr key={trade.id}>
                  <td>#{trade.id}</td><td>{trade.option_type} {trade.strike}</td><td>{trade.quantity}</td>
                  <td>₹{trade.entry_price}</td><td>{trade.status}</td>
                  <td className={(trade.net_pnl ?? 0) >= 0 ? "positive" : "negative"}>{trade.net_pnl == null ? "—" : `₹${trade.net_pnl.toFixed(2)}`}</td>
                  <td>{trade.exit_reason ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </PageCard>
    </div>
  );
}
