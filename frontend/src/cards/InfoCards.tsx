import type { SystemHealth } from "../types/decision";

const colors = {
  card: "#111118",
  border: "#22222c",
  green: "#4ade80",
  red: "#f87171",
  amber: "#fbbf24",
  textMuted: "#8a8a96",
};

const cardStyle: React.CSSProperties = {
  background: colors.card,
  border: `1px solid ${colors.border}`,
  borderRadius: 8,
  padding: 16,
};
const monoStyle: React.CSSProperties = { fontFamily: "ui-monospace, SFMono-Regular, monospace" };
const sectionLabel: React.CSSProperties = { color: colors.textMuted, fontSize: 12, marginBottom: 10, textTransform: "uppercase", letterSpacing: 0.5 };

function fmt(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return v.toFixed(1);
  return String(v);
}

// ---- Levels Grid (spec section 7) --------------------------------------
export function LevelsGridCard({ levels, spot }: { levels: Record<string, unknown>; spot: number | undefined }) {
  const entries: [string, unknown][] = [
    ["PDH", levels.pdh], ["PDL", levels.pdl], ["PDC", levels.pdc],
    ["Today Open", levels.today_open], ["VWAP", levels.vwap],
    ["EMA 20", levels.ema20], ["EMA 50", levels.ema50],
    ["Session High", levels.session_high], ["Session Low", levels.session_low],
    ["Call Wall", levels.call_wall], ["Put Wall", levels.put_wall],
  ];
  return (
    <div style={cardStyle}>
      <div style={sectionLabel}>KEY MARKET LEVELS</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px 16px" }}>
        {entries.map(([label, val]) => {
          const num = typeof val === "number" ? val : null;
          const near = num !== null && spot !== undefined && Math.abs(num - spot) / spot < 0.003;
          return (
            <div key={label} style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
              <span style={{ color: colors.textMuted }}>{label}</span>
              <span style={{ ...monoStyle, color: near ? colors.amber : "#e6e6ea", fontWeight: near ? 700 : 400 }}>
                {fmt(val)}{near ? " •" : ""}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---- Technical Indicators (spec section 8) -----------------------------
export function IndicatorsCard({ indicators }: { indicators: Record<string, unknown> }) {
  const rows: [string, unknown][] = [
    ["RSI(14)", indicators.rsi14], ["MACD Hist", indicators.macd_hist],
    ["ADX(14)", indicators.adx14], ["ATR(14)", indicators.atr14],
    ["Volume", indicators.volume], ["Rel. Volume", indicators.relative_volume],
  ];
  return (
    <div style={cardStyle}>
      <div style={sectionLabel}>TECHNICAL INDICATORS</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "10px 12px" }}>
        {rows.map(([label, val]) => (
          <div key={label}>
            <div style={{ color: colors.textMuted, fontSize: 11 }}>{label}</div>
            <div style={{ ...monoStyle, fontSize: 16 }}>{fmt(val)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---- System Health (spec section 26) -----------------------------------
export function SystemHealthCard({ health }: { health: SystemHealth }) {
  const statusColor = (s: string) => (s === "GREEN" ? colors.green : s === "AMBER" ? colors.amber : colors.red);
  return (
    <div style={cardStyle}>
      <div style={sectionLabel}>SYSTEM HEALTH</div>
      {health.components.map((c) => (
        <div key={c.name} style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 6 }}>
          <span>{c.name}</span>
          <span style={{ color: statusColor(c.status), fontWeight: 700 }}>{c.status}</span>
        </div>
      ))}
      <div style={{ borderTop: `1px solid ${colors.border}`, marginTop: 8, paddingTop: 8, fontSize: 12, color: colors.textMuted }}>
        Last tick: {health.last_tick_timestamp ? new Date(health.last_tick_timestamp).toLocaleTimeString() : "—"}
        {"  ·  "}Data age: {health.data_age_sec !== null ? `${health.data_age_sec.toFixed(1)}s` : "—"}
      </div>
    </div>
  );
}
