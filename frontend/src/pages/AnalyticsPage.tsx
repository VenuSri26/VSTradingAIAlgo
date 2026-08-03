import { useEffect, useMemo, useState } from "react";
import { PageCard, StatTile } from "../components/PageCard";
import { api } from "../services/api";
import type { AnalyticsBucket, PaperAnalytics, SystemMetrics } from "../types/operations";

function money(value: number) { return `₹${value.toFixed(2)}`; }

function EquityChart({ analytics }: { analytics: PaperAnalytics }) {
  const points = analytics.equity_curve;
  const polyline = useMemo(() => {
    if (!points.length) return "";
    const values = points.map((point) => point.equity);
    const min = Math.min(0, ...values);
    const max = Math.max(0, ...values);
    const range = max - min || 1;
    return points.map((point, index) => {
      const x = points.length === 1 ? 50 : (index / (points.length - 1)) * 100;
      const y = 92 - ((point.equity - min) / range) * 82;
      return `${x},${y}`;
    }).join(" ");
  }, [points]);

  if (!points.length) return <div className="empty-chart">Close paper trades to build the equity curve.</div>;
  return (
    <div className="chart-wrap">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="equity-chart" role="img" aria-label="Paper trading equity curve">
        <line x1="0" x2="100" y1="92" y2="92" className="chart-axis" />
        <polyline points={polyline} className="chart-line" vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="chart-caption"><span>First trade</span><strong>{money(points.length ? points[points.length - 1].equity : 0)}</strong><span>Latest trade</span></div>
    </div>
  );
}

function Breakdown({ data }: { data: Record<string, AnalyticsBucket> }) {
  const entries = Object.entries(data);
  if (!entries.length) return <div className="muted-text">No closed trades available.</div>;
  return (
    <div className="table-scroll"><table className="data-table"><thead><tr><th>Group</th><th>Trades</th><th>Win rate</th><th>Net P&amp;L</th></tr></thead>
      <tbody>{entries.map(([name, bucket]) => <tr key={name}><td>{name}</td><td>{bucket.trades}</td><td>{bucket.win_rate.toFixed(1)}%</td><td className={bucket.net_pnl >= 0 ? "positive" : "negative"}>{money(bucket.net_pnl)}</td></tr>)}</tbody>
    </table></div>
  );
}

export function AnalyticsPage() {
  const [analytics, setAnalytics] = useState<PaperAnalytics | null>(null);
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.getPaperAnalytics(), api.getMetrics()])
      .then(([paper, system]) => { setAnalytics(paper); setMetrics(system); })
      .catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)));
  }, []);

  const summary = analytics?.summary;
  return (
    <div className="page-stack">
      {error ? <div className="error-box">{error}</div> : null}
      <div className="stat-grid">
        <StatTile label="Closed trades" value={summary?.total_trades ?? "—"} />
        <StatTile label="Win rate" value={summary ? `${summary.win_rate.toFixed(1)}%` : "—"} />
        <StatTile label="Net paper P&L" value={summary ? money(summary.net_pnl) : "—"} />
        <StatTile label="Profit factor" value={summary?.profit_factor == null ? "—" : summary.profit_factor.toFixed(2)} />
        <StatTile label="Expectancy" value={summary ? money(summary.expectancy) : "—"} />
        <StatTile label="Max drawdown" value={summary ? money(summary.max_drawdown) : "—"} />
      </div>
      <PageCard title="Paper Equity Curve" accent="#4ade80"><EquityChart analytics={analytics ?? {summary: {} as never, equity_curve: [], daily: [], by_option_type: {}, by_grade: {}, by_exit_reason: {}}} /></PageCard>
      <div className="two-column-grid">
        <PageCard title="CE vs PE Performance"><Breakdown data={analytics?.by_option_type ?? {}} /></PageCard>
        <PageCard title="Grade Performance"><Breakdown data={analytics?.by_grade ?? {}} /></PageCard>
      </div>
      <div className="two-column-grid">
        <PageCard title="Exit Reason Performance"><Breakdown data={analytics?.by_exit_reason ?? {}} /></PageCard>
        <PageCard title="Pipeline Quality">
          <div className="settings-list">
            <div><strong>Pipeline runs</strong><span>{metrics?.pipeline_runs ?? "—"}</span></div>
            <div><strong>Success rate</strong><span>{metrics ? `${metrics.pipeline_success_rate}%` : "—"}</span></div>
            <div><strong>Average latency</strong><span>{metrics ? `${metrics.pipeline_avg_duration_ms} ms` : "—"}</span></div>
            <div><strong>Stale-data events</strong><span>{metrics?.stale_data_events ?? "—"}</span></div>
          </div>
        </PageCard>
      </div>
    </div>
  );
}
