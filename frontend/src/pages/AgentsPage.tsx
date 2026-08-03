import { useEffect, useState } from "react";
import { PageCard, StatTile } from "../components/PageCard";
import { api } from "../services/api";
import type { AgentRegistry } from "../types/operations";

export function AgentsPage() {
  const [data, setData] = useState<AgentRegistry | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api.getAgentRegistry().then(setData).catch((e) => setError(e instanceof Error ? e.message : String(e))); }, []);
  const available = data?.agents.filter((a) => a.availability === "OK").length ?? 0;
  const bullish = data?.agents.filter((a) => a.direction === "BULLISH").length ?? 0;
  const bearish = data?.agents.filter((a) => a.direction === "BEARISH").length ?? 0;
  return <div className="page-stack">
    {error ? <div className="error-box">{error}</div> : null}
    <div className="stat-grid">
      <StatTile label="Registered agents" value={data?.agents.length ?? "—"} />
      <StatTile label="Available" value={available} />
      <StatTile label="Bullish votes" value={bullish} />
      <StatTile label="Bearish votes" value={bearish} />
    </div>
    <PageCard title="Multi-Agent Decision Bus" accent="#7c6ff7">
      <div className="table-scroll"><table className="data-table"><thead><tr><th>Agent</th><th>Family</th><th>Direction</th><th>Score</th><th>Weight</th><th>Reason</th></tr></thead>
      <tbody>{data?.agents.map((a) => <tr key={a.name}><td><strong>{a.name}</strong><div className="muted-text">{a.purpose}</div></td><td>{a.family}</td><td className={a.direction === "BULLISH" ? "positive" : a.direction === "BEARISH" ? "negative" : ""}>{a.direction}</td><td>{a.score ?? "N/A"}</td><td>{(a.weight * 100).toFixed(0)}%</td><td>{a.reason}</td></tr>)}</tbody></table></div>
    </PageCard>
    <div className="two-column-grid">
      <PageCard title="Bull vs Bear Debate"><pre className="json-view">{JSON.stringify(data?.debate ?? {}, null, 2)}</pre></PageCard>
      <PageCard title="Supervisor Decision"><pre className="json-view">{JSON.stringify(data?.final_decision ?? {}, null, 2)}</pre></PageCard>
    </div>
  </div>;
}
