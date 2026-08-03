import type { AgentResult, EntryChecklistItem, PositionInfo } from "../types/decision";

const colors = {
  card: "#111118",
  border: "#22222c",
  purple: "#7c6ff7",
  green: "#4ade80",
  red: "#f87171",
  amber: "#fbbf24",
  textMuted: "#8a8a96",
};
const cardStyle: React.CSSProperties = { background: colors.card, border: `1px solid ${colors.border}`, borderRadius: 8, padding: 16 };
const monoStyle: React.CSSProperties = { fontFamily: "ui-monospace, SFMono-Regular, monospace" };
const sectionLabel: React.CSSProperties = { color: colors.textMuted, fontSize: 12, marginBottom: 10, textTransform: "uppercase", letterSpacing: 0.5 };

function dirColor(dir: string) {
  if (dir === "BULLISH") return colors.green;
  if (dir === "BEARISH") return colors.red;
  if (dir === "NOT_AVAILABLE") return colors.textMuted;
  return colors.amber;
}

// ---- Agent Explainability Panel (spec section 22) -----------------------
export function ExplainabilityCard({ agents }: { agents: AgentResult[] }) {
  return (
    <div style={cardStyle}>
      <div style={sectionLabel}>AGENT EXPLAINABILITY</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        {agents.map((a) => (
          <div key={a.name} style={{ borderLeft: `3px solid ${dirColor(a.direction)}`, paddingLeft: 10 }}>
            <div style={{ fontSize: 12, fontWeight: 700, textTransform: "uppercase" }}>{a.name}</div>
            <div style={{ ...monoStyle, fontSize: 13, color: dirColor(a.direction) }}>
              {a.direction} {a.score !== null ? `${a.score}/100` : ""}
            </div>
            <ul style={{ margin: "4px 0 0 16px", padding: 0, fontSize: 11, color: colors.textMuted }}>
              {a.evidence.slice(0, 3).map((e, i) => <li key={i}>{e}</li>)}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---- Institutional Narrative (spec section 23) ---------------------------
export function NarrativeCard({ narrative }: { narrative: string }) {
  return (
    <div style={{ ...cardStyle, borderColor: colors.purple }}>
      <div style={sectionLabel}>INSTITUTIONAL NARRATIVE</div>
      <div style={{ fontSize: 14, lineHeight: 1.6, color: "#e6e6ea" }}>{narrative || "NOT AVAILABLE"}</div>
    </div>
  );
}

// ---- Current Position (spec section 24) ----------------------------------
export function PositionCard({ position }: { position: PositionInfo }) {
  if (!position.has_position) {
    return (
      <div style={cardStyle}>
        <div style={sectionLabel}>CURRENT POSITION</div>
        <div style={{ color: colors.textMuted, fontSize: 14 }}>NO OPEN POSITION</div>
      </div>
    );
  }
  const pnlColor = (position.pnl ?? 0) >= 0 ? colors.green : colors.red;
  return (
    <div style={cardStyle}>
      <div style={sectionLabel}>CURRENT POSITION</div>
      <div style={{ fontSize: 16, fontWeight: 700 }}>{position.option_type} {position.strike}</div>
      <div style={{ ...monoStyle, fontSize: 13, marginTop: 6, lineHeight: 1.8 }}>
        Qty: {position.quantity} · Entry: ₹{position.entry_price} · LTP: ₹{position.current_price}
        <br />
        P&amp;L: <span style={{ color: pnlColor }}>₹{position.pnl} ({position.pnl_pct}%)</span>
        <br />
        SL: ₹{position.stop_loss} · T1: ₹{position.target_1} · T2: ₹{position.target_2}
      </div>
      <div style={{ fontSize: 12, color: colors.textMuted, marginTop: 6 }}>Status: {position.status}</div>
    </div>
  );
}

// ---- Session Analytics (spec section 25) ---------------------------------
export function SessionAnalyticsCard({ analytics }: { analytics: Record<string, unknown> }) {
  const rows: [string, unknown][] = [
    ["Trades Today", analytics.trades_today], ["Wins", analytics.wins], ["Losses", analytics.losses],
    ["Win Rate", analytics.win_rate !== null && analytics.win_rate !== undefined ? `${analytics.win_rate}%` : "—"],
    ["Net P&L", analytics.net_pnl], ["A+ Trades", analytics.a_plus_trades], ["A Trades", analytics.a_trades],
    ["Risk Blocked", analytics.risk_blocked_setups],
  ];
  return (
    <div style={cardStyle}>
      <div style={sectionLabel}>SESSION ANALYTICS</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px 16px" }}>
        {rows.map(([label, val]) => (
          <div key={label} style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
            <span style={{ color: colors.textMuted }}>{label}</span>
            <span style={monoStyle}>{String(val ?? "—")}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---- Entry Checklist (spec section 19) -----------------------------------
export function EntryChecklistCard({ checklist }: { checklist: EntryChecklistItem[] }) {
  if (!checklist || checklist.length === 0) return null;
  return (
    <div style={cardStyle}>
      <div style={sectionLabel}>ENTRY CHECKLIST</div>
      {checklist.map((c, i) => (
        <div key={i} style={{ display: "flex", gap: 8, fontSize: 13, marginBottom: 6 }}>
          <span style={{ color: c.passed ? colors.green : colors.red, fontWeight: 700 }}>{c.passed ? "✓" : "✕"}</span>
          <div>
            <div>{c.label}</div>
            <div style={{ fontSize: 11, color: colors.textMuted }}>{c.detail}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
