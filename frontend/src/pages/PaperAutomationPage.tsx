import { useCallback, useEffect, useState } from "react";
import { PageCard, StatTile } from "../components/PageCard";
import { api } from "../services/api";
import type {
  PaperAutomationStatus,
  PaperDailySummary,
  PaperLoopReadiness,
  PaperMonitorStatus,
  PaperTrade,
  TradingReportStatus,
  ZerodhaHealth,
} from "../types/operations";

const when = (value: string | null) => value
  ? new Date(value).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })
  : "—";

function stateTone(action?: string) {
  if (["PAPER_TRADE_OPENED", "MANAGED", "CLOSED"].includes(action ?? "")) return "positive";
  if (["BLOCKED", "ERROR"].includes(action ?? "")) return "negative";
  return "";
}

export function PaperAutomationPage() {
  const [automation, setAutomation] = useState<PaperAutomationStatus | null>(null);
  const [monitor, setMonitor] = useState<PaperMonitorStatus | null>(null);
  const [health, setHealth] = useState<ZerodhaHealth | null>(null);
  const [summary, setSummary] = useState<PaperDailySummary | null>(null);
  const [trades, setTrades] = useState<PaperTrade[]>([]);
  const [readiness, setReadiness] = useState<PaperLoopReadiness | null>(null);
  const [reports, setReports] = useState<TradingReportStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [auto, mon, broker, day, journal, certificate, reportStatus] = await Promise.all([
        api.getPaperAutomationStatus(), api.getPaperMonitorStatus(), api.getZerodhaHealth(),
        api.getPaperDailySummary(), api.getPaperTrades(), api.getPaperLoopReadiness(), api.getTradingReportStatus(),
      ]);
      setAutomation(auto); setMonitor(mon); setHealth(broker); setSummary(day);
      setTrades(journal.trades); setReadiness(certificate); setReports(reportStatus);
      setUpdatedAt(new Date().toISOString()); setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 10_000);
    return () => window.clearInterval(timer);
  }, [load]);

  const persistent = automation?.persistent_today;
  const portfolio = summary?.portfolio;
  const ready = automation?.running && automation.enabled && monitor?.running;

  return <div className="page-stack">
    {error ? <div className="error-box">Dashboard refresh failed: {error}</div> : null}

    <section className={`automation-banner ${ready ? "ready" : "blocked"}`}>
      <div>
        <span className="eyebrow">V7.8 AUTONOMOUS PAPER LOOP</span>
        <h2>{ready ? "System is monitoring automatically" : "Automation needs attention"}</h2>
        <p className={stateTone(automation?.last_action)}>
          {automation?.last_action ?? "LOADING"}{automation?.last_reason ? ` — ${automation.last_reason}` : ""}
        </p>
      </div>
      <div className="automation-safety">
        <strong>{automation?.execution_mode ?? "PAPER_ONLY"}</strong>
        <span>Live orders: {automation?.live_orders_enabled ? "ENABLED" : "DISABLED"}</span>
      </div>
    </section>

    <div className="stat-grid">
      <StatTile label="Loop" value={automation?.running ? "RUNNING" : "STOPPED"} />
      <StatTile label="Current action" value={automation?.last_action ?? "—"} />
      <StatTile label="Zerodha" value={health?.connected ? "CONNECTED" : "NOT CONNECTED"} />
      <StatTile label="Paper trades today" value={persistent?.paper_trades_opened ?? 0} />
      <StatTile label="No-trade decisions" value={persistent?.no_trade ?? 0} />
      <StatTile label="Blocked decisions" value={persistent?.blocked ?? 0} />
    </div>

    <PageCard title="Holiday Completion Certificate" accent="#a78bfa">
      <div className="certificate-heading">
        <div><strong className={readiness?.offline_complete ? "positive" : "negative"}>{readiness?.status ?? "LOADING"}</strong>
          <p className="muted-text">{readiness?.recommended_action ?? "Checking offline readiness…"}</p></div>
        <span className={`safety-pill ${readiness?.offline_complete ? "certificate-pass" : ""}`}>
          {readiness?.offline_complete ? "OFFLINE COMPLETE" : "ACTION REQUIRED"}
        </span>
      </div>
      <div className="readiness-grid">
        {readiness?.checks.map(check => <div className="readiness-check" key={check.code}>
          <span className={check.passed ? "positive" : "negative"}>{check.passed ? "✓" : "✕"}</span>
          <div><strong>{check.label}</strong><small>{check.detail}</small></div>
        </div>)}
      </div>
      <h3 className="subheading">Only live evidence remaining</h3>
      <ul className="pending-list">{readiness?.pending_live_evidence.map(item => <li key={item}>{item}</li>)}</ul>
    </PageCard>

    <div className="two-column-grid">
      <PageCard title="How to read this screen" accent="#7c6ff7">
        <div className="settings-list">
          <div><strong>WAITING</strong><span>Market closed, weekend, cutoff, cooldown or an open trade exists.</span></div>
          <div><strong>NO_TRADE</strong><span>Market was evaluated but did not pass the A/A+ quality gate.</span></div>
          <div><strong>BLOCKED</strong><span>Missing/stale data or a risk control prevented entry.</span></div>
          <div><strong>PAPER_TRADE_OPENED</strong><span>A simulated position was opened; no Zerodha order was sent.</span></div>
        </div>
      </PageCard>
      <PageCard title="Loop configuration" accent="#4ade80">
        <div className="settings-list">
          <div><strong>Entry interval</strong><span>{automation?.interval_sec ?? "—"} seconds</span></div>
          <div><strong>Minimum score</strong><span>{automation?.minimum_score ?? "—"}</span></div>
          <div><strong>Allowed grades</strong><span>{automation?.allowed_grades ?? "—"}</span></div>
          <div><strong>Monitor interval</strong><span>{monitor?.interval_sec ?? "—"} seconds</span></div>
          <div><strong>Maximum quote age</strong><span>{monitor?.max_quote_age_sec ?? "—"} seconds</span></div>
          <div><strong>EOD exit</strong><span>{monitor?.eod_exit_time ?? "—"} IST</span></div>
        </div>
      </PageCard>
    </div>

    <PageCard title="Paper Position Monitor" accent="#22c55e">
      <div className="metric-grid">
        <div className="metric-card"><span>State</span><strong className={stateTone(monitor?.last_action)}>{monitor?.last_action ?? "—"}</strong></div>
        <div className="metric-card"><span>Active trade</span><strong>{monitor?.active_trade_id ? `#${monitor.active_trade_id}` : "NONE"}</strong></div>
        <div className="metric-card"><span>Last price</span><strong>{monitor?.last_price == null ? "—" : `₹${monitor.last_price}`}</strong></div>
        <div className="metric-card"><span>Good quotes</span><strong>{monitor?.successful_quotes ?? 0}</strong></div>
        <div className="metric-card"><span>Quote failures</span><strong>{monitor?.quote_failures ?? 0}</strong></div>
        <div className="metric-card"><span>Last checked</span><strong className="compact-value">{when(monitor?.last_checked_at ?? null)}</strong></div>
      </div>
      {monitor?.last_error ? <div className="error-box">{monitor.last_error}</div> : null}
    </PageCard>

    <PageCard title="Recent Autonomous Decisions" accent="#f59e0b">
      <div className="table-scroll"><table className="data-table">
        <thead><tr><th>Time (IST)</th><th>Action</th><th>Reason</th><th>Setup</th><th>Trade</th></tr></thead>
        <tbody>{!automation?.recent_runs.length
          ? <tr><td colSpan={5} className="empty-cell">No autonomous decisions recorded yet.</td></tr>
          : automation.recent_runs.map(run => <tr key={run.id}>
            <td>{when(run.checked_at)}</td><td className={stateTone(run.action)}>{run.action}</td>
            <td className="reason-cell">{run.reason ?? "—"}</td><td>{run.setup_id ? `#${run.setup_id}` : "—"}</td>
            <td>{run.trade_id ? `#${run.trade_id}` : "—"}</td>
          </tr>)}</tbody>
      </table></div>
    </PageCard>

    <PageCard title="Paper Journal" accent="#38bdf8">
      <div className="metric-grid journal-summary">
        <div className="metric-card"><span>Total</span><strong>{portfolio?.total_trades ?? 0}</strong></div>
        <div className="metric-card"><span>Open</span><strong>{portfolio?.open_trades ?? 0}</strong></div>
        <div className="metric-card"><span>Closed</span><strong>{portfolio?.closed_trades ?? 0}</strong></div>
        <div className="metric-card"><span>Net P&amp;L</span><strong>₹{(portfolio?.net_pnl ?? 0).toFixed(2)}</strong></div>
      </div>
      <div className="table-scroll"><table className="data-table">
        <thead><tr><th>ID</th><th>Contract</th><th>Qty</th><th>Entry</th><th>Status</th><th>Net P&amp;L</th><th>Exit</th></tr></thead>
        <tbody>{trades.length === 0
          ? <tr><td colSpan={7} className="empty-cell">No paper trades yet. The loop will populate this automatically on a qualifying market setup.</td></tr>
          : trades.map(trade => <tr key={trade.id}><td>#{trade.id}</td><td>{trade.option_type} {trade.strike}</td>
            <td>{trade.quantity}</td><td>₹{trade.entry_price}</td><td>{trade.status}</td>
            <td className={(trade.net_pnl ?? 0) >= 0 ? "positive" : "negative"}>{trade.net_pnl == null ? "—" : `₹${trade.net_pnl.toFixed(2)}`}</td>
            <td>{trade.exit_reason ?? "—"}</td></tr>)}</tbody>
      </table></div>
    </PageCard>

    <PageCard title="Pre/Post-Market Reports & Zerodha Reconciliation" accent="#c084fc">
      <div className="metric-grid journal-summary">
        <div className="metric-card"><span>Pre-market schedule</span><strong>{reports?.schedulers.pre_market.configured_time ?? "09:00"} IST</strong></div>
        <div className="metric-card"><span>Post-market schedule</span><strong>{reports?.schedulers.post_market.configured_time ?? "15:40"} IST</strong></div>
        <div className="metric-card"><span>Latest paper P&amp;L</span><strong>₹{(reports?.post_market?.summary.paper_net_pnl ?? 0).toFixed(2)}</strong></div>
        <div className="metric-card"><span>Zerodha orders observed</span><strong>{reports?.post_market?.summary.zerodha_orders ?? 0}</strong></div>
      </div>
      <div className="two-column-grid">
        <div className="readiness-check"><span className={reports?.pre_market ? "positive" : ""}>{reports?.pre_market ? "✓" : "○"}</span><div>
          <strong>Pre-market analysis</strong><small>{reports?.pre_market?.analysis.message ?? "Will be generated automatically on the next trading day."}</small>
        </div></div>
        <div className="readiness-check"><span className={reports?.post_market ? "positive" : ""}>{reports?.post_market ? "✓" : "○"}</span><div>
          <strong>Post-market analysis</strong><small>{reports?.post_market?.analysis.message ?? "Will reconcile recommendations, paper results and read-only broker observations."}</small>
        </div></div>
      </div>
      <p className="muted-text">Zerodha access on this page is read-only. Manual broker orders are shown as unmatched observations; they are never copied into paper trading and this page cannot place an order.</p>
      <div className="table-scroll"><table className="data-table">
        <thead><tr><th>Setup</th><th>Recommendation</th><th>Grade / score</th><th>Paper trade</th><th>Zerodha match</th></tr></thead>
        <tbody>{!reports?.post_market?.lineage.length
          ? <tr><td colSpan={5} className="empty-cell">No completed post-market lineage report yet.</td></tr>
          : reports.post_market.lineage.map(row => <tr key={row.setup_id}><td>#{row.setup_id} {row.contract}</td>
            <td>{row.recommendation}</td><td>{row.grade} / {row.score}</td>
            <td>{row.paper_trade_id ? `#${row.paper_trade_id} ${row.paper_status}` : "Not opened"}</td>
            <td>{row.broker_order_id ? `${row.broker_order_id} ${row.broker_status ?? ""}` : "No match"}</td></tr>)}</tbody>
      </table></div>
    </PageCard>

    <div className="dashboard-footer-note">
      Auto-refreshes every 10 seconds · Last refreshed {when(updatedAt)} · This page cannot submit live broker orders.
      <button type="button" className="action-button" onClick={() => void load()}>Refresh now</button>
    </div>
  </div>;
}
