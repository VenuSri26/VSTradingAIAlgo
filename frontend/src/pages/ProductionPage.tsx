import { useEffect, useState } from "react";
import { PageCard } from "../components/PageCard";
import { api } from "../services/api";
import type { DecisionExplanation, ReleaseCertificate } from "../types/operations";

type LiveStatus = {
  connected:boolean; authenticated:boolean; fresh:boolean; safe_no_trade:boolean;
  age_sec:number|null; reconnects:number; consecutive_failures:number; polls:number;
  successful_polls:number; success_rate:number|null; instruments_synced:number;
  expiry:string|null; mode:string; websocket_requested:boolean; websocket_active:boolean;
  message:string; spot:number|null; vix:number|null; last_success_at:string|null;
  last_market_timestamp:string|null; last_error:string|null; token_user_id:string|null;
  candles_3m:Array<{start:string;end:string;open:number;high:number;low:number;close:number;ticks:number}>;
};
type SecurityStatus = { app_access_token_configured:boolean; admin_token_configured:boolean; https_required:boolean; live_orders_enabled:boolean; manual_confirmation_required:boolean };
type Preview = { preview_id:string; approved:boolean; status:string; checks:Array<{name:string;passed:boolean;detail:string}>; execution_mode:string };

export function ProductionPage() {
  const [live, setLive] = useState<LiveStatus | null>(null);
  const [security, setSecurity] = useState<SecurityStatus | null>(null);
  const [optionIntel, setOptionIntel] = useState<any | null>(null);
  const [orders, setOrders] = useState<any[]>([]);
  const [token, setToken] = useState(sessionStorage.getItem("admin_token") || "");
  const [symbol, setSymbol] = useState("NIFTY26AUG25300CE");
  const [quantity, setQuantity] = useState(75);
  const [price, setPrice] = useState(100);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [message, setMessage] = useState("");
  const [certificate, setCertificate] = useState<ReleaseCertificate | null>(null);
  const [explanation, setExplanation] = useState<DecisionExplanation | null>(null);

  const load = async () => {
    const [l, s, o, oi, cert, explain] = await Promise.all([api.getLiveDataStatus(), api.getSecurityStatus(), api.getExecutionOrders(), api.getOptionChainSummary(), api.getReleaseCertificate(), api.getDecisionExplanation()]);
    setLive(l); setSecurity(s); setOrders(o.orders || []); setOptionIntel(oi); setCertificate(cert); setExplanation(explain);
  };
  useEffect(() => {
    load().catch(e => setMessage(String(e)));
    const timer = window.setInterval(() => load().catch(()=>undefined), 5000);
    return () => window.clearInterval(timer);
  }, []);

  const runAction = async (action: "poll" | "sync") => {
    try {
      if (!token) throw new Error("Admin token is required.");
      const result = action === "poll" ? await api.pollLiveData(token) : await api.syncInstruments(token);
      setMessage(action === "poll" ? "Market snapshot refreshed." : `Instrument sync completed: ${result.count ?? 0} instruments.`);
      await load();
    } catch (e) { setMessage(String(e)); }
  };
  const createPreview = async () => {
    try {
      const result = await api.previewOrder({tradingsymbol:symbol, transaction_type:"BUY", quantity, order_type:"MARKET", product:"MIS", estimated_price:price}, token);
      setPreview(result); setMessage(result.approved ? "Preview ready for manual confirmation." : "Preview blocked by safety checks.");
    } catch (e) { setMessage(String(e)); }
  };
  const confirm = async () => {
    if (!preview) return;
    try { await api.confirmOrder(preview.preview_id, "CONFIRM", token); setMessage("Readiness record created. No broker order was sent."); await load(); }
    catch (e) { setMessage(String(e)); }
  };

  return <div className="page-stack">
    {message && <div className="error-box">{message}</div>}
    <div className="two-column-grid">
      <PageCard title="Release Certificate" accent="#22c55e">
        <div className="stat-grid">
          <div className="stat-tile"><span>Release</span><strong>{certificate?.version.version || "-"}</strong><small>{certificate?.version.environment || "-"}</small></div>
          <div className="stat-tile"><span>Health Score</span><strong>{certificate?.health_score ?? "-"}%</strong><small>{certificate?.status || "-"}</small></div>
          <div className="stat-tile"><span>Build</span><strong>{certificate?.version.build_id || "-"}</strong><small>{certificate?.version.build_time || "-"}</small></div>
        </div>
        <pre className="json-view">{JSON.stringify(certificate?.checks || {}, null, 2)}</pre>
      </PageCard>
      <PageCard title="Decision Explainability" accent="#a78bfa">
        <p><strong>{explanation?.decision || "-"}</strong> · {explanation?.grade || "-"} · alignment {explanation?.alignment_score ?? "-"}/100</p>
        <h4>Why</h4><ul>{(explanation?.why || []).map((item) => <li key={item}>{item}</li>)}</ul>
        <h4>Why not / blockers</h4><ul>{(explanation?.why_not || []).map((item) => <li key={item}>{item}</li>)}</ul>
        <h4>Invalidation</h4><ul>{(explanation?.invalidation_conditions || []).map((item) => <li key={item}>{item}</li>)}</ul>
      </PageCard>
    </div>

    <div className="stat-grid">
      <div className="stat-tile"><span>Live Data</span><strong className={live?.fresh ? "positive":"negative"}>{live?.fresh ? "FRESH":"SAFE NO-TRADE"}</strong><small>{live?.mode || "-"}</small></div>
      <div className="stat-tile"><span>Feed Age</span><strong>{live?.age_sec ?? "-"}s</strong><small>Last success {live?.last_success_at ? new Date(live.last_success_at).toLocaleTimeString() : "-"}</small></div>
      <div className="stat-tile"><span>Spot / VIX</span><strong>{live?.spot?.toFixed(2) ?? "-"}</strong><small>VIX {live?.vix?.toFixed(2) ?? "-"}</small></div>
      <div className="stat-tile"><span>Feed Success</span><strong>{live?.success_rate ?? "-"}%</strong><small>{live?.successful_polls ?? 0}/{live?.polls ?? 0} polls</small></div>
      <div className="stat-tile"><span>Instruments</span><strong>{live?.instruments_synced ?? 0}</strong><small>Expiry {live?.expiry || "-"}</small></div>
      <div className="stat-tile"><span>Live Orders</span><strong className={security?.live_orders_enabled ? "negative":"positive"}>{security?.live_orders_enabled ? "ENABLED":"DISABLED"}</strong><small>Manual confirmation required</small></div>
    </div>

    <PageCard title="V2.6 option-chain intelligence">
      <div className="stat-grid">
        <div className="stat-tile"><span>Institutional Bias</span><strong className={optionIntel?.institutional_bias === "BULLISH" ? "positive" : optionIntel?.institutional_bias === "BEARISH" ? "negative" : ""}>{optionIntel?.institutional_bias || "-"}</strong><small>Score {optionIntel?.bias_score ?? "-"}/100 · confidence {optionIntel?.confidence ?? "-"}%</small></div>
        <div className="stat-tile"><span>PCR (OI)</span><strong>{optionIntel?.pcr_oi ?? "-"}</strong><small>CE {optionIntel?.total_ce_oi?.toLocaleString?.() ?? "-"} · PE {optionIntel?.total_pe_oi?.toLocaleString?.() ?? "-"}</small></div>
        <div className="stat-tile"><span>Call Wall</span><strong>{optionIntel?.call_wall ?? "-"}</strong><small>Strongest resistance</small></div>
        <div className="stat-tile"><span>Put Wall</span><strong>{optionIntel?.put_wall ?? "-"}</strong><small>Strongest support</small></div>
        <div className="stat-tile"><span>Max Pain</span><strong>{optionIntel?.max_pain ?? "-"}</strong><small>ATM {optionIntel?.atm_strike ?? "-"}</small></div>
      </div>
      <div className="settings-list">
        {(optionIntel?.reasons || []).map((reason:string, index:number)=><div key={`${index}-${reason}`}><b>Evidence {index+1}</b><span>{reason}</span></div>)}
        {(optionIntel?.warnings || []).map((warning:string)=><div key={warning}><b className="negative">Warning</b><span>{warning}</span></div>)}
      </div>
    </PageCard>

    <PageCard title="V2.5 market-data supervisor">
      <div className="settings-list">
        <div><b>Connection</b><span>{live?.connected ? "Connected":"Not connected"}</span></div>
        <div><b>Authentication</b><span>{live?.authenticated ? `Valid${live.token_user_id ? ` · ${live.token_user_id}` : ""}`:"Not authenticated"}</span></div>
        <div><b>Safety state</b><span className={live?.safe_no_trade ? "negative":"positive"}>{live?.safe_no_trade ? "NO_TRADE enforced":"Feed healthy"}</span></div>
        <div><b>Polling failures</b><span>{live?.consecutive_failures ?? 0} consecutive · {live?.reconnects ?? 0} recoveries</span></div>
        <div><b>WebSocket readiness</b><span>{live?.websocket_active ? "Active" : live?.websocket_requested ? "Requested; safe polling active" : "Disabled; safe polling active"}</span></div>
        <div><b>Message</b><span>{live?.message || "No status"}</span></div>
        {live?.last_error && <div><b className="negative">Last error</b><span>{live.last_error}</span></div>}
      </div>
      <div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
        <button className="action-button" onClick={()=>runAction("poll")}>Poll live snapshot</button>
        <button className="action-button" onClick={()=>runAction("sync")}>Sync instruments</button>
      </div>
    </PageCard>

    <PageCard title="3-minute candle aggregation">
      <div className="table-scroll"><table className="data-table"><thead><tr><th>Start</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>Samples</th></tr></thead><tbody>
        {(live?.candles_3m || []).slice(-10).reverse().map(c=><tr key={c.start}><td>{new Date(c.start).toLocaleTimeString()}</td><td>{c.open.toFixed(2)}</td><td>{c.high.toFixed(2)}</td><td>{c.low.toFixed(2)}</td><td>{c.close.toFixed(2)}</td><td>{c.ticks}</td></tr>)}
        {!live?.candles_3m?.length && <tr><td colSpan={6} className="empty-cell">Candles appear after market snapshots are received.</td></tr>}
      </tbody></table></div>
    </PageCard>

    <PageCard title="Manual execution readiness">
      <div className="form-grid">
        <label>Admin token<input type="password" value={token} onChange={e=>{setToken(e.target.value);sessionStorage.setItem("admin_token",e.target.value)}} /></label>
        <label>Trading symbol<input value={symbol} onChange={e=>setSymbol(e.target.value)} /></label>
        <label>Quantity<input type="number" value={quantity} onChange={e=>setQuantity(Number(e.target.value))} /></label>
        <label>Estimated price<input type="number" value={price} onChange={e=>setPrice(Number(e.target.value))} /></label>
      </div>
      <button className="action-button" onClick={createPreview}>Run order preview</button>
      {preview && <div className="page-card" style={{marginTop:12}}><b>{preview.status}</b> · {preview.execution_mode}<div className="settings-list">{preview.checks.map(c=><div key={c.name}><b className={c.passed?"positive":"negative"}>{c.name}</b><span>{c.detail}</span></div>)}</div><button className="action-button safe-action" disabled={!preview.approved} onClick={confirm}>Confirm readiness record</button></div>}
    </PageCard>

    <PageCard title="Production security"><div className="settings-list">
      <div><b>Application token</b><span>{security?.app_access_token_configured ? "Configured":"Not configured"}</span></div>
      <div><b>Admin token</b><span>{security?.admin_token_configured ? "Configured":"Not configured"}</span></div>
      <div><b>HTTPS required</b><span>{security?.https_required ? "Yes":"No"}</span></div>
      <div><b>Browser security headers</b><span>Enabled</span></div>
    </div></PageCard>

    <PageCard title="Execution reconciliation queue"><div className="table-scroll"><table className="data-table"><thead><tr><th>ID</th><th>Status</th><th>Symbol</th><th>Quantity</th><th>Broker sent</th></tr></thead><tbody>
      {orders.length ? orders.map(o=><tr key={o.order_id}><td>{o.order_id}</td><td>{o.status}</td><td>{o.order.tradingsymbol}</td><td>{o.order.quantity}</td><td>{String(o.submitted_to_broker)}</td></tr>) : <tr><td colSpan={5} className="empty-cell">No readiness records.</td></tr>}
    </tbody></table></div></PageCard>
  </div>;
}
