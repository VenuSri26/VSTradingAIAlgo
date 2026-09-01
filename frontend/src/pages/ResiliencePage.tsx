import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { ResilienceStatus } from "../types/operations";

export function ResiliencePage() {
  const [data, setData] = useState<ResilienceStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const pull = () => api.getResilienceStatus().then((value) => active && setData(value)).catch((e) => active && setError(String(e)));
    pull();
    const timer = window.setInterval(pull, 15000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);

  if (error) return <section className="page-stack"><div className="page-card danger">{error}</div></section>;
  if (!data) return <section className="page-stack"><div className="page-card">Checking restart and persistence safety…</div></section>;

  return (
    <section className="page-stack">
      <div className="page-card">
        <div className="eyebrow">V3.1 OPERATIONAL RESILIENCE</div>
        <h2>{data.overall}</h2>
        <p className="muted">Restart recovery, persistence, configuration and live-order safety checks.</p>
      </div>
      <div className="metric-grid">
        <div className="page-card"><div className="eyebrow">RESILIENCE SCORE</div><h3>{data.resilience_score}%</h3></div>
        <div className="page-card"><div className="eyebrow">RESTART SAFE</div><h3>{data.restart_safe ? "YES" : "NO"}</h3></div>
        <div className="page-card"><div className="eyebrow">EXECUTION</div><h3>{data.paper_only ? "PAPER ONLY" : "LIVE ENABLED"}</h3></div>
        <div className="page-card"><div className="eyebrow">WARNINGS</div><h3>{data.warning_count}</h3></div>
      </div>
      <div className="page-card">
        <div className="eyebrow">RECOVERY CHECKS</div>
        <div className="check-list">
          {data.checks.map((check) => (
            <div className="check-row" key={check.code}>
              <span>{check.status === "PASS" ? "✓" : check.status === "WARN" ? "!" : "✕"}</span>
              <span><strong>{check.label}</strong><br /><span className="muted">{check.detail}</span></span>
              <span>{check.status}</span>
            </div>
          ))}
        </div>
      </div>
      <div className={`page-card ${data.restart_safe ? "success" : "danger"}`}>
        <div className="eyebrow">RECOMMENDED ACTION</div><h3>{data.recommended_action}</h3>
      </div>
    </section>
  );
}
