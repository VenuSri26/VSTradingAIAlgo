import { useEffect, useMemo, useState } from "react";
import { PageCard, StatTile } from "../components/PageCard";
import { api } from "../services/api";
import type { OpenPaperManagement, PaperTrade } from "../types/operations";

export function PortfolioPage() {
  const [trades, setTrades] = useState<PaperTrade[]>([]);
  const [management, setManagement] = useState<OpenPaperManagement | null>(null);
  const [trailPct, setTrailPct] = useState(10);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const [tradeResponse, managementResponse] = await Promise.all([api.getPaperTrades(), api.getPaperManagement()]);
      setTrades(tradeResponse.trades); setManagement(managementResponse); setError(null);
      if (managementResponse.management) setTrailPct(managementResponse.management.trail_distance_pct);
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
  };
  useEffect(() => { load(); const id=window.setInterval(load,10000); return()=>window.clearInterval(id); }, []);

  const summary = useMemo(() => {
    const closed = trades.filter((trade) => trade.status !== "OPEN");
    const net = closed.reduce((total, trade) => total + (trade.net_pnl ?? 0), 0);
    const wins = closed.filter((trade) => (trade.net_pnl ?? 0) > 0).length;
    return { open: trades.filter((trade) => trade.status === "OPEN").length, closed: closed.length, net,
      winRate: closed.length ? (wins / closed.length) * 100 : 0 };
  }, [trades]);

  const m = management?.management;
  const active = management?.trade;
  return <div className="page-stack">
    <div className="stat-grid">
      <StatTile label="Open paper trades" value={summary.open} />
      <StatTile label="Closed trades" value={summary.closed} />
      <StatTile label="Net paper P&L" value={`₹${summary.net.toFixed(2)}`} />
      <StatTile label="Win rate" value={`${summary.winRate.toFixed(1)}%`} />
    </div>

    <PageCard title="Active Trade Management" accent="#4ade80">
      {!m || !active ? <p>No open paper trade. Trailing and partial-exit state will appear after execution.</p> : <>
        <div className="metric-grid">
          <div className="metric-card"><span>Contract</span><strong>{active.option_type} {active.strike}</strong></div>
          <div className="metric-card"><span>Remaining Qty</span><strong>{m.remaining_quantity}/{m.original_quantity}</strong></div>
          <div className="metric-card"><span>Active Stop</span><strong>₹{m.active_stop_loss}</strong></div>
          <div className="metric-card"><span>Highest Price</span><strong>₹{m.highest_price}</strong></div>
          <div className="metric-card"><span>Realized Qty</span><strong>{m.realized_quantity}</strong></div>
          <div className="metric-card"><span>Last Action</span><strong>{m.last_action}</strong></div>
        </div>
        <p>{m.partial_target_done ? "✓ Target-1 management completed" : "Target-1 partial exit pending"} · {m.breakeven_armed ? "✓ Break-even armed" : "Break-even not armed"}</p>
        <div style={{display:"flex",gap:8,alignItems:"center",flexWrap:"wrap"}}>
          <label>Trailing distance % <input type="number" min={2} max={30} value={trailPct} onChange={e=>setTrailPct(Number(e.target.value))}/></label>
          <button type="button" onClick={async()=>{try{const token=sessionStorage.getItem("admin_token")||"";await api.configurePaperManagement(true,trailPct,token);await load();}catch(e){setError(String(e));}}}>Enable / Update Trailing</button>
          <button type="button" onClick={async()=>{try{const token=sessionStorage.getItem("admin_token")||"";await api.configurePaperManagement(false,trailPct,token);await load();}catch(e){setError(String(e));}}}>Disable Trailing</button>
        </div>
        <p style={{fontSize:12,opacity:.7}}>Paper-only: T1 books half the lots when at least two lots are open, moves stop to break-even, then trails the remaining quantity. One-lot trades move to break-even without partial exit.</p>
      </>}
    </PageCard>

    <PageCard title="Paper Trade Journal" accent="#7c6ff7">
      {error ? <div className="error-box">{error}</div> : null}
      <div className="table-scroll"><table className="data-table">
        <thead><tr><th>ID</th><th>Contract</th><th>Qty</th><th>Entry</th><th>Status</th><th>Net P&L</th><th>Exit reason</th></tr></thead>
        <tbody>{trades.length === 0 ? <tr><td colSpan={7} className="empty-cell">No paper trades recorded yet.</td></tr> : trades.map((trade)=><tr key={trade.id}>
          <td>#{trade.id}</td><td>{trade.option_type} {trade.strike}</td><td>{trade.quantity}</td><td>₹{trade.entry_price}</td><td>{trade.status}</td>
          <td className={(trade.net_pnl ?? 0)>=0?"positive":"negative"}>{trade.net_pnl==null?"—":`₹${trade.net_pnl.toFixed(2)}`}</td><td>{trade.exit_reason??"—"}</td>
        </tr>)}</tbody>
      </table></div>
    </PageCard>
  </div>;
}
