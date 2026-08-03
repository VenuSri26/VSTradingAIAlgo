import { useLiveDecision } from "./hooks/useLiveDecision";
import { useEffect, useState } from "react";
import { api } from "./services/api";
import type { AgentResult, Direction, TradeGrade } from "./types/decision";
import { LevelsGridCard, IndicatorsCard, SystemHealthCard } from "./cards/InfoCards";
import { OptionChainCard, GammaCard, LiquidityMapCard, TrapDetectionCard, MarketStructureCard } from "./cards/OptionAndStructureCards";
import { ExplainabilityCard, NarrativeCard, PositionCard, SessionAnalyticsCard, EntryChecklistCard } from "./cards/PanelCards";

// ---- design tokens (spec section 33) --------------------------------
const colors = {
  bg: "#0a0a0f",
  card: "#111118",
  border: "#22222c",
  purple: "#7c6ff7",
  green: "#4ade80",
  red: "#f87171",
  amber: "#fbbf24",
  textMuted: "#8a8a96",
};

function dirColor(dir: Direction) {
  if (dir === "BULLISH") return colors.green;
  if (dir === "BEARISH") return colors.red;
  if (dir === "NOT_AVAILABLE") return colors.textMuted;
  return colors.amber;
}

function gradeColor(grade: TradeGrade) {
  if (grade === "A+" || grade === "A") return colors.green;
  if (grade === "NO_TRADE") return colors.textMuted;
  return colors.amber;
}

const cardStyle: React.CSSProperties = {
  background: colors.card,
  border: `1px solid ${colors.border}`,
  borderRadius: 8,
  padding: 16,
};

const monoStyle: React.CSSProperties = { fontFamily: "ui-monospace, SFMono-Regular, monospace" };

function MetricCard({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: string }) {
  return (
    <div style={cardStyle}>
      <div style={{ color: colors.textMuted, fontSize: 12, letterSpacing: 0.5, textTransform: "uppercase" }}>{label}</div>
      <div style={{ ...monoStyle, fontSize: 28, fontWeight: 600, color: accent ?? "#fff", marginTop: 4 }}>{value}</div>
      {sub && <div style={{ color: colors.textMuted, fontSize: 13, marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function AgentBar({ agent }: { agent: AgentResult }) {
  const color = dirColor(agent.direction);
  const pct = agent.score ?? 0;
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 4 }}>
        <span>{agent.name}</span>
        <span style={{ ...monoStyle, color }}>
          {agent.score === null ? "NOT AVAILABLE" : `${agent.score}/100`} · {agent.direction}
        </span>
      </div>
      <div style={{ background: "#1a1a22", borderRadius: 4, height: 6, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, background: color, height: "100%" }} />
      </div>
      <div style={{ color: colors.textMuted, fontSize: 12, marginTop: 2 }}>{agent.reason}</div>
    </div>
  );
}

const gridStyle = (cols: string): React.CSSProperties => ({ display: "grid", gridTemplateColumns: cols, gap: 12, marginBottom: 16 });

export default function Dashboard() {
  const { data, error, loading, lastUpdated, transport } = useLiveDecision();
  const [analytics, setAnalytics] = useState<Record<string, unknown> | null>(null);

  // session analytics is a separate lightweight endpoint (spec section 30) —
  // polled independently since it changes far less often than the live decision
  useEffect(() => {
    let cancelled = false;
    async function pull() {
      try {
        const a = await api.getAnalyticsSession();
        if (!cancelled) setAnalytics(a);
      } catch {
        /* non-critical panel; fail silently and keep last-known value */
      }
    }
    pull();
    const id = setInterval(pull, 15000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  if (loading && !data) {
    return <div style={{ background: colors.bg, color: "#fff", padding: 24, minHeight: "100vh" }}>Loading live decision…</div>;
  }
  if (error && !data) {
    return (
      <div style={{ background: colors.bg, color: colors.red, padding: 24, minHeight: "100vh" }}>
        Failed to reach backend: {error}. Is the API running on the configured VITE_API_BASE_URL?
      </div>
    );
  }
  if (!data) return null;

  const { market, decision, alignment, agents, flags, risk, system_health, levels, indicators, options, gamma, liquidity, market_structure, narrative, position } = data;
  const trapAgent = agents.find((a) => a.name === "Trap Detection Agent");

  return (
    <div style={{ background: colors.bg, minHeight: "100vh", color: "#e6e6ea", padding: 20, fontFamily: "Inter, system-ui, sans-serif" }}>
      {/* ROW 1 — header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 16 }}>
        <div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>NIFTY 50</div>
          <div style={{ color: colors.textMuted, fontSize: 13 }}>
            {String(market.phase ?? "—")} · regime {String((data.regime as any)?.label ?? "—")} · last updated{" "}
            {lastUpdated ? new Date(lastUpdated).toLocaleTimeString() : "—"}
            {transport && (
              <span style={{ marginLeft: 8, color: transport === "websocket" ? colors.green : colors.amber }}>
                ● {transport === "websocket" ? "LIVE" : "POLLING"}
              </span>
            )}
          </div>
        </div>
        <div
          style={{
            padding: "6px 14px", borderRadius: 6, fontWeight: 700, fontSize: 13,
            background: "#1a1a22", color: gradeColor(decision.grade), border: `1px solid ${colors.border}`,
          }}
        >
          {system_health.overall}
        </div>
      </div>

      {/* ROW 2 — top metric cards */}
      <div style={gridStyle("repeat(4, 1fr)")}>
        <MetricCard label="Nifty Spot" value={String(market.spot ?? "—")} sub={`${market.day_change ?? "—"} (${market.day_change_pct ?? "—"}%)`} />
        <MetricCard label="VWAP" value={String(levels.vwap ?? "—")} />
        <MetricCard label="India VIX" value={String(market.vix ?? "—")} />
        <MetricCard label="Options Sentiment (PCR)" value={String((options as any)?.metrics?.pcr ?? "—")} />
      </div>

      {/* ROW 3 — AI decision + alignment + risk */}
      <div style={gridStyle("2fr 1fr 1fr")}>
        <div style={{ ...cardStyle, borderColor: colors.purple }}>
          <div style={{ color: colors.textMuted, fontSize: 12, marginBottom: 6 }}>AI DECISION</div>
          <div style={{ fontSize: 26, fontWeight: 800, color: gradeColor(decision.grade) }}>
            {decision.decision.replace("_", " ")}
          </div>
          <div style={{ fontSize: 13, marginTop: 4 }}>
            Grade: <b style={{ color: gradeColor(decision.grade) }}>{decision.grade}</b>
            {"  ·  "}Confidence: {decision.confidence !== null ? `${Math.round(decision.confidence * 100)}%` : "—"}
          </div>
          {decision.plan && (
            <div style={{ ...monoStyle, fontSize: 13, marginTop: 10, lineHeight: 1.7 }}>
              {decision.plan.option_type} {decision.plan.strike} · LTP ₹{decision.plan.ltp}
              <br />Entry: ₹{decision.plan.entry_low}–₹{decision.plan.entry_high}
              <br />SL: ₹{decision.plan.stop_loss} · T1: ₹{decision.plan.target_1} · T2: ₹{decision.plan.target_2}
              <br />RR: 1:{decision.plan.risk_reward}
              {(decision.plan.delta !== null || decision.plan.iv !== null) && (
                <>
                  <br />
                  <span style={{ color: colors.textMuted }}>
                    {decision.plan.delta !== null && `Δ ${decision.plan.delta}`}
                    {decision.plan.theta !== null && `  ·  Θ ${decision.plan.theta}/day`}
                    {decision.plan.iv !== null && `  ·  IV ${decision.plan.iv}%`}
                  </span>
                </>
              )}
            </div>
          )}
          <div style={{ color: colors.textMuted, fontSize: 13, marginTop: 10 }}>{decision.explanation}</div>
        </div>
        <MetricCard label="Alignment Score" value={alignment.score !== null ? `${alignment.score}/100` : "N/A"} accent={colors.purple} />
        <div style={cardStyle}>
          <div style={{ color: colors.textMuted, fontSize: 12 }}>RISK STATUS</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: risk.approved ? colors.green : colors.red, marginTop: 4 }}>
            {risk.approved ? "RISK APPROVED" : "TRADE BLOCKED"}
          </div>
          {risk.reasons.map((r, i) => (
            <div key={i} style={{ color: colors.textMuted, fontSize: 12, marginTop: 4 }}>{r}</div>
          ))}
        </div>
      </div>

      {/* ROW 4 — agent scores */}
      <div style={{ ...cardStyle, marginBottom: 16 }}>
        <div style={{ color: colors.textMuted, fontSize: 12, marginBottom: 10 }}>MULTI-AGENT SCORES</div>
        {agents.map((a) => <AgentBar key={a.name} agent={a} />)}
      </div>

      {/* ROW 5 — levels / indicators / structure */}
      <div style={gridStyle("1fr 1fr 1fr")}>
        <LevelsGridCard levels={levels} spot={typeof market.spot === "number" ? market.spot : undefined} />
        <IndicatorsCard indicators={indicators} />
        <MarketStructureCard structure={market_structure} />
      </div>

      {/* ROW 6 — option chain + intelligence */}
      <div style={gridStyle("1fr")}>
        <OptionChainCard options={options as any} />
      </div>

      {/* ROW 7 — liquidity / gamma / trap */}
      <div style={gridStyle("1fr 1fr 1fr")}>
        <LiquidityMapCard liquidity={liquidity} />
        <GammaCard gamma={gamma} />
        <TrapDetectionCard agent={trapAgent} />
      </div>

      {/* ROW 8 — flags */}
      <div style={{ ...cardStyle, marginBottom: 16 }}>
        <div style={{ color: colors.textMuted, fontSize: 12, marginBottom: 10 }}>BULL / BEAR / WATCH FLAGS</div>
        {flags.map((f, i) => (
          <div key={i} style={{ fontSize: 13, marginBottom: 6, color: f.category === "BULL" ? colors.green : f.category === "BEAR" ? colors.red : colors.amber }}>
            ● {f.category} — <span style={{ color: "#e6e6ea" }}>{f.text}</span>
          </div>
        ))}
      </div>

      {/* ROW 9 — explainability + narrative + checklist */}
      <div style={gridStyle("2fr 1fr")}>
        <ExplainabilityCard agents={agents} />
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <NarrativeCard narrative={narrative} />
          <EntryChecklistCard checklist={decision.checklist} />
        </div>
      </div>

      {/* ROW 10 — position / session analytics / system health */}
      <div style={gridStyle("1fr 1fr 1fr")}>
        <PositionCard position={position} />
        <SessionAnalyticsCard analytics={analytics ?? {}} />
        <SystemHealthCard health={system_health} />
      </div>

    </div>
  );
}
