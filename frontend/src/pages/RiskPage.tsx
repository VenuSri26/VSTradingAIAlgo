import { useEffect, useState } from "react";
import { PageCard, StatTile } from "../components/PageCard";
import { api } from "../services/api";
import type { RiskStatus } from "../types/operations";

export function RiskPage() {
  const [risk, setRisk] = useState<RiskStatus | null>(null);
  const [token, setToken] = useState(() => sessionStorage.getItem("vstradingai-admin-token") ?? "");
  const [reason, setReason] = useState("Manual safety stop");
  const [message, setMessage] = useState<string | null>(null);
  const refresh = () => api.getRiskStatus().then(setRisk).catch((e) => setMessage(e instanceof Error ? e.message : String(e)));
  useEffect(() => { void refresh(); }, []);
  const toggle = async () => {
    if (!risk) return;
    sessionStorage.setItem("vstradingai-admin-token", token);
    try { await api.setKillSwitch(!risk.kill_switch, !risk.kill_switch ? reason : null, token); setMessage(!risk.kill_switch ? "Kill switch enabled" : "Kill switch disabled"); await refresh(); }
    catch (e) { setMessage(e instanceof Error ? e.message : String(e)); }
  };
  return <div className="page-stack">
    <div className="stat-grid">
      <StatTile label="Risk state" value={risk?.blocked ? "BLOCKED" : "READY"} />
      <StatTile label="Trades remaining" value={risk?.remaining_trades ?? "—"} />
      <StatTile label="Loss capacity" value={risk ? `₹${risk.remaining_loss_capacity.toFixed(2)}` : "—"} />
      <StatTile label="Consecutive losses" value={risk ? `${risk.consecutive_losses}/${risk.max_consecutive_losses}` : "—"} />
    </div>
    <PageCard title="Emergency Kill Switch" accent={risk?.kill_switch ? "#f87171" : "#4ade80"}>
      {message ? <div className={message.includes("enabled") ? "error-box" : "muted-text"}>{message}</div> : null}
      <div className="form-grid">
        <label>Admin token<input type="password" value={token} onChange={(e) => setToken(e.target.value)} /></label>
        <label>Reason<input value={reason} onChange={(e) => setReason(e.target.value)} disabled={Boolean(risk?.kill_switch)} /></label>
      </div>
      <button className={`action-button ${risk?.kill_switch ? "safe-action" : "danger-action"}`} onClick={() => void toggle()}>
        {risk?.kill_switch ? "Disable kill switch" : "Enable kill switch"}
      </button>
      <p className="muted-text">When enabled, all new paper entries are blocked. It never places or cancels Zerodha orders.</p>
    </PageCard>
    <PageCard title="Risk Configuration">
      <div className="settings-list">
        <div><strong>Paper capital</strong><span>₹{risk?.paper_capital ?? "—"}</span></div>
        <div><strong>Max risk per trade</strong><span>{risk?.max_risk_per_trade_pct ?? "—"}%</span></div>
        <div><strong>Capital utilization cap</strong><span>{risk?.max_capital_utilization_pct ?? "—"}%</span></div>
        <div><strong>Daily loss limit</strong><span>₹{risk?.daily_loss_limit ?? "—"}</span></div>
        <div><strong>Kill-switch reason</strong><span>{risk?.kill_switch_reason ?? "—"}</span></div>
      </div>
    </PageCard>
  </div>;
}
