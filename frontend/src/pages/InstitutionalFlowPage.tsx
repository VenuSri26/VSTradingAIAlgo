import { useEffect, useMemo, useState } from "react";
import { api } from "../services/api";
import type { DecisionIntelligence, InstitutionalFlowPoint, InstitutionalFlowSummary, InstitutionalFlowTrend } from "../types/operations";
import { PageCard } from "../components/PageCard";

function scoreWidth(value: number) { return `${Math.min(100, Math.max(0, (value + 100) / 2))}%`; }
function signed(value: number) { return `${value >= 0 ? "+" : ""}${value.toFixed(1)}`; }

export function InstitutionalFlowPage() {
  const [data,setData]=useState<InstitutionalFlowSummary|null>(null);
  const [trend,setTrend]=useState<InstitutionalFlowTrend|null>(null);
  const [anomalies,setAnomalies]=useState<InstitutionalFlowPoint[]>([]);
  const [decision,setDecision]=useState<DecisionIntelligence|null>(null);
  const [error,setError]=useState<string|null>(null);
  const load=()=>Promise.all([
    api.getInstitutionalFlow(), api.getInstitutionalFlowTrend(), api.getInstitutionalFlowAnomalies(), api.getDecisionIntelligence()
  ]).then(([summary,flowTrend,alerts,intelligence])=>{setData(summary);setTrend(flowTrend);setAnomalies(alerts.anomalies);setDecision(intelligence);setError(null);})
    .catch(e=>setError(e instanceof Error?e.message:"Unable to load institutional flow"));
  useEffect(()=>{ void load(); const id=window.setInterval(()=>void load(),30000); return()=>window.clearInterval(id); },[]);
  const latestPoints=useMemo(()=>trend?.points.slice(-18)??[],[trend]);
  if(error) return <PageCard title="Institutional Flow"><div className="error-banner">{error}</div><button onClick={()=>void load()}>Retry</button></PageCard>;
  if(!data) return <PageCard title="Institutional Flow"><div>Loading institutional evidence…</div></PageCard>;
  return <div className="page-stack">
    <PageCard title="Institutional Flow Intelligence">
      <p>Evidence-weighted view with persisted intraday history. Missing external feeds are shown explicitly.</p>
      <div className="metric-grid">
        <div className="metric-tile"><span>Bias</span><strong>{data.institutional_bias}</strong></div>
        <div className="metric-tile"><span>Flow score</span><strong>{data.institutional_flow_score.toFixed(1)}</strong></div>
        <div className="metric-tile"><span>Confidence</span><strong>{data.confidence.toFixed(1)}%</strong></div>
        <div className="metric-tile"><span>PCR trend</span><strong>{data.pcr_trend}</strong></div>
        <div className="metric-tile"><span>Session trend</span><strong>{trend?.trend?.split("_").join(" ")??"UNAVAILABLE"}</strong></div>
        <div className="metric-tile"><span>Flow change</span><strong>{signed(trend?.score_change??0)}</strong></div>
      </div>
    </PageCard>

    <PageCard title="Intraday Flow Trend">
      {latestPoints.length===0 ? <p>No persisted snapshots yet. The history begins as the endpoint refreshes.</p> :
      <div className="flow-bars" aria-label="Institutional flow history">
        {latestPoints.map(point=><div className="flow-bar-row" key={point.id} title={`${point.captured_at} · ${point.institutional_flow_score}`}>
          <span>{new Date(point.captured_at).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"})}</span>
          <div className="flow-bar-track"><div className="flow-bar-fill" style={{width:scoreWidth(point.institutional_flow_score)}} /></div>
          <strong>{signed(point.institutional_flow_score)}</strong>
        </div>)}
      </div>}
      <p>Samples: {trend?.samples??0} · PCR change: {signed(trend?.pcr_change??0)}</p>
    </PageCard>

    <PageCard title="Decision Intelligence">
      {decision ? <>
        <div className="metric-grid">
          <div className="metric-tile"><span>Decision</span><strong>{decision.decision}</strong></div>
          <div className="metric-tile"><span>Base confidence</span><strong>{decision.base_confidence.toFixed(1)}%</strong></div>
          <div className="metric-tile"><span>Flow-adjusted</span><strong>{decision.adjusted_confidence.toFixed(1)}%</strong></div>
          <div className="metric-tile"><span>Execution</span><strong>DISABLED</strong></div>
        </div>
        <ul>{decision.checks.map(check=><li key={check.name}>{check.passed?"✓":"✗"} {check.name}: {check.detail}</li>)}</ul>
      </>:<p>Decision intelligence unavailable.</p>}
    </PageCard>

    <PageCard title="Evidence Components">
      <div className="table-wrap"><table><thead><tr><th>Component</th><th>Direction</th><th>Score</th><th>Confidence</th><th>Evidence</th></tr></thead>
      <tbody>{data.components.map(c=><tr key={c.name}><td>{c.name.split("_").join(" ")}</td><td>{c.direction}</td><td>{c.score.toFixed(1)}</td><td>{c.confidence.toFixed(0)}%</td><td>{c.reason}</td></tr>)}</tbody></table></div>
    </PageCard>

    <PageCard title="Flow Anomalies">
      {anomalies.length===0?<p>No institutional-flow anomalies detected.</p>:<div className="table-wrap"><table><thead><tr><th>Time</th><th>Score</th><th>PCR</th><th>Anomaly</th></tr></thead><tbody>
        {anomalies.map(a=><tr key={a.id}><td>{new Date(a.captured_at).toLocaleString()}</td><td>{signed(a.institutional_flow_score)}</td><td>{a.pcr?.toFixed(2)??"—"}</td><td>{a.anomaly_codes.join(", ")}</td></tr>)}
      </tbody></table></div>}
    </PageCard>

    <PageCard title="Data-quality warnings"><ul>{data.warnings.map(w=><li key={w}>{w}</li>)}</ul><p>{data.note}</p></PageCard>
  </div>;
}
