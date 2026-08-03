import { useEffect, useState } from "react";
import { PageCard } from "../components/PageCard";
import { api } from "../services/api";
import type { DecisionReplay, ReplayListItem } from "../types/operations";

export function ReplayPage() {
  const [items, setItems] = useState<ReplayListItem[]>([]);
  const [selected, setSelected] = useState<DecisionReplay | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getReplays().then((result) => setItems(result.replays)).catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)));
  }, []);

  const loadReplay = (tradeId: number) => {
    setError(null);
    api.getReplay(tradeId).then(setSelected).catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)));
  };

  return <div className="page-stack">
    {error ? <div className="error-box">{error}</div> : null}
    <PageCard title="Decision Replay Index" accent="#f59e0b">
      <div className="table-scroll"><table className="data-table"><thead><tr><th>Trade</th><th>Contract</th><th>Grade</th><th>Alignment</th><th>Outcome</th><th>Net P&amp;L</th><th></th></tr></thead>
        <tbody>{items.length ? items.map((item) => <tr key={item.trade_id}><td>#{item.trade_id}</td><td>{item.option_type} {item.strike}</td><td>{item.grade ?? "—"}</td><td>{item.alignment_score ?? "—"}</td><td>{item.exit_reason ?? item.status}</td><td className={(item.net_pnl ?? 0) >= 0 ? "positive" : "negative"}>{item.net_pnl == null ? "—" : `₹${item.net_pnl.toFixed(2)}`}</td><td><button className="action-button" onClick={() => loadReplay(item.trade_id)}>Replay</button></td></tr>) : <tr><td colSpan={7} className="empty-cell">No paper trades available for replay.</td></tr>}</tbody>
      </table></div>
    </PageCard>
    {selected ? <>
      <div className="two-column-grid">
        <PageCard title={`Trade #${selected.trade.id}`}><div className="settings-list">
          <div><strong>Contract</strong><span>{selected.trade.option_type} {selected.trade.strike}</span></div>
          <div><strong>Entry / Exit</strong><span>₹{selected.trade.entry_price} / {selected.trade.close_price == null ? "OPEN" : `₹${selected.trade.close_price}`}</span></div>
          <div><strong>Status</strong><span>{selected.trade.status}</span></div>
          <div><strong>Net P&amp;L</strong><span className={(selected.trade.net_pnl ?? 0) >= 0 ? "positive" : "negative"}>{selected.trade.net_pnl == null ? "—" : `₹${selected.trade.net_pnl.toFixed(2)}`}</span></div>
        </div></PageCard>
        <PageCard title="AI Decision"><div className="settings-list">
          <div><strong>Decision</strong><span>{selected.setup?.decision ?? "—"}</span></div>
          <div><strong>Grade</strong><span>{selected.setup?.grade ?? "—"}</span></div>
          <div><strong>Alignment</strong><span>{selected.setup?.alignment_score ?? "—"}</span></div>
          <div><strong>Explanation</strong><span>{selected.setup?.explanation ?? "—"}</span></div>
        </div></PageCard>
      </div>
      <PageCard title="Monitoring Timeline"><div className="timeline-list">
        <div className="timeline-item"><strong>Setup generated</strong><span>{selected.setup?.generated_at ?? "—"}</span></div>
        <div className="timeline-item"><strong>Paper entry</strong><span>{selected.trade.opened_at} · ₹{selected.trade.entry_price}</span></div>
        {selected.events.map((event) => <div className="timeline-item" key={event.id}><strong>{event.action}</strong><span>{event.checked_at} · {event.current_price == null ? "No quote" : `₹${event.current_price}`} · {event.detail ?? ""}</span></div>)}
        {selected.trade.closed_at ? <div className="timeline-item"><strong>{selected.trade.exit_reason ?? "Closed"}</strong><span>{selected.trade.closed_at} · ₹{selected.trade.close_price}</span></div> : null}
      </div></PageCard>
      <PageCard title="Captured Market & Agent Snapshot"><pre className="json-view">{JSON.stringify(selected.market_snapshot, null, 2)}</pre></PageCard>
    </> : null}
  </div>;
}
