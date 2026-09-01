import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { ProductionCandidateStatus } from "../types/operations";

export function ProductionCandidatePage() {
  const [data, setData] = useState<ProductionCandidateStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getProductionCandidateStatus().then(setData).catch((e) => setError(String(e)));
  }, []);

  if (error) return <section className="page-stack"><div className="page-card danger">{error}</div></section>;
  if (!data) return <section className="page-stack"><div className="page-card">Loading production-candidate evidence…</div></section>;

  const ready = data.status === "CERTIFIED_FOR_CONTROLLED_PILOT";
  return (
    <section className="page-stack">
      <div className="page-card">
        <div className="eyebrow">V3.0 PRODUCTION CANDIDATE</div>
        <h2>{data.status.split("_").join(" ")}</h2>
        <p className="muted">Evidence-based release certification. Automatic live execution remains disabled.</p>
      </div>

      <div className="metric-grid">
        <div className="page-card"><div className="eyebrow">READINESS</div><h3>{data.readiness_score}%</h3></div>
        <div className="page-card"><div className="eyebrow">CLOSED TRADES</div><h3>{data.paper_performance.total_trades}</h3></div>
        <div className="page-card"><div className="eyebrow">PROFIT FACTOR</div><h3>{data.paper_performance.profit_factor ?? "—"}</h3></div>
        <div className="page-card"><div className="eyebrow">LIVE ORDERS</div><h3>{data.live_orders_enabled ? "ENABLED" : "DISABLED"}</h3></div>
      </div>

      <div className="page-card">
        <div className="eyebrow">CERTIFICATION GATES</div>
        <div className="check-list">
          {data.rules.map((rule) => (
            <div className="check-row" key={rule.code}>
              <span>{rule.passed ? "✓" : "✕"}</span>
              <span><strong>{rule.label}</strong><br /><span className="muted">{rule.detail}</span></span>
              <span>{rule.weight}%</span>
            </div>
          ))}
        </div>
      </div>

      <div className={`page-card ${ready ? "success" : "warning"}`}>
        <div className="eyebrow">NEXT ACTION</div>
        <h3>{data.next_action}</h3>
        {!ready && <p className="muted">Resolve every blocker before any controlled broker pilot.</p>}
      </div>
    </section>
  );
}
