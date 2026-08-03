import { useEffect, useState } from "react";
import { PageCard, StatTile } from "../components/PageCard";
import { api } from "../services/api";
import type { StrategyLabResult } from "../types/operations";

export function StrategyLabPage() {
  const [payload, setPayload] = useState("");
  const [result, setResult] = useState<StrategyLabResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  useEffect(() => { api.getStrategySample().then((x) => setPayload(JSON.stringify(x, null, 2))).catch((e) => setError(String(e))); }, []);
  async function run() {
    setRunning(true); setError(null);
    try { setResult(await api.validateStrategy(JSON.parse(payload) as Record<string, unknown>)); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setRunning(false); }
  }
  const summary = result?.summary as Record<string, number | null> | undefined;
  return <div className="page-stack">
    {error ? <div className="error-box">{error}</div> : null}
    <div className="stat-grid"><StatTile label="Status" value={result?.promotion_status ?? "RESEARCH ONLY"} /><StatTile label="Trades" value={summary?.total ?? "—"} /><StatTile label="Win rate" value={summary?.win_rate == null ? "—" : `${summary.win_rate}%`} /><StatTile label="Net P&L" value={summary?.net_pnl == null ? "—" : `₹${summary.net_pnl}`} /></div>
    <PageCard title="Strategy Validation Input" accent="#38bdf8">
      <textarea className="strategy-editor" value={payload} onChange={(e) => setPayload(e.target.value)} spellCheck={false} />
      <button className="action-button safe-action" type="button" onClick={run} disabled={running}>{running ? "Running…" : "Run Conservative Validation"}</button>
      <p className="muted-text">Signals execute on the next candle. Same-candle stop/target ambiguity is treated as stop-loss. No production strategy is promoted automatically.</p>
    </PageCard>
    {result ? <><div className="two-column-grid"><PageCard title="Validation Summary"><pre className="json-view">{JSON.stringify(result.summary, null, 2)}</pre></PageCard><PageCard title="Walk-Forward Splits"><pre className="json-view">{JSON.stringify(result.walk_forward_splits, null, 2)}</pre></PageCard></div><PageCard title="Replay Trades"><pre className="json-view">{JSON.stringify(result.trades, null, 2)}</pre></PageCard></> : null}
  </div>;
}
