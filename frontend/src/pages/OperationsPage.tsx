import { useEffect, useState } from "react";
import { PageCard, StatTile } from "../components/PageCard";
import { api } from "../services/api";
import type { DeploymentSnapshot, LogEntry, OperationsSystem, SystemMetrics, ZerodhaHealth } from "../types/operations";

function gb(value: number | null) { return value == null ? "—" : `${(value / 1024 ** 3).toFixed(2)} GB`; }
export function OperationsPage() {
  const [system, setSystem] = useState<OperationsSystem | null>(null); const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [zerodha, setZerodha] = useState<ZerodhaHealth | null>(null); const [deploy, setDeploy] = useState<DeploymentSnapshot | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]); const [error, setError] = useState<string | null>(null);
  useEffect(() => { Promise.all([api.getOperationsSystem(), api.getMetrics(), api.getZerodhaHealth(), api.getDeployments(), api.getOperationsLogs()]).then(([s,m,z,d,l]) => {setSystem(s);setMetrics(m);setZerodha(z);setDeploy(d);setLogs(l.entries);}).catch((e)=>setError(e instanceof Error?e.message:String(e))); }, []);
  return <div className="page-stack">{error?<div className="error-box">{error}</div>:null}
    <div className="stat-grid"><StatTile label="Version" value={system?.version ?? "—"}/><StatTile label="API success" value={metrics?`${metrics.pipeline_success_rate}%`:"—"}/><StatTile label="Memory used" value={system?.memory.used_pct==null?"—":`${system.memory.used_pct}%`}/><StatTile label="Disk used" value={system?.disk.used_pct==null?"—":`${system.disk.used_pct}%`}/><StatTile label="Zerodha" value={zerodha?.connected?"CONNECTED":"NOT CONNECTED"}/></div>
    <div className="two-column-grid"><PageCard title="Server"><div className="settings-list"><div><strong>Host</strong><span>{system?.hostname??"—"}</span></div><div><strong>Uptime</strong><span>{system?`${Math.floor(system.uptime_sec/60)} min`:"—"}</span></div><div><strong>Memory available</strong><span>{gb(system?.memory.available_bytes??null)}</span></div><div><strong>Disk free</strong><span>{gb(system?.disk.free_bytes??null)}</span></div><div><strong>Load average</strong><span>{system?.load_average?.join(" / ")??"—"}</span></div></div></PageCard><PageCard title="Deployment"><div className="settings-list"><div><strong>Current release</strong><span>{deploy?.current_release??"Not detected outside AWS"}</span></div><div><strong>Backups</strong><span>{deploy?.backups.length??0}</span></div><div><strong>Trading mode</strong><span>{system?.trading_mode??"—"}</span></div><div><strong>Paper monitor</strong><span>{system?.paper_monitor_enabled?"ENABLED":"DISABLED"}</span></div></div></PageCard></div>
    <PageCard title="Deployment History"><pre className="command-view">{deploy?.history.join("\n") || "No deployment history found."}</pre></PageCard>
    <PageCard title="Recent Structured Logs"><pre className="json-view">{logs.length?logs.map((x)=>JSON.stringify(x)).join("\n"):"No log records found."}</pre></PageCard>
  </div>;
}
