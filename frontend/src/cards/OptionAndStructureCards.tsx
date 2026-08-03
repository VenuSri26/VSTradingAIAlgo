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

interface ChainLeg { strike: number; ltp: number; oi: number; oi_change: number; volume: number; iv: number; bid: number; ask: number; delta?: number | null; gamma?: number | null }
interface OptionsData { snapshot?: { atm?: number; spot?: number; chain?: { CE: ChainLeg[]; PE: ChainLeg[] } }; metrics?: Record<string, unknown> }

// ---- Option Chain Panel (spec section 11) -------------------------------
export function OptionChainCard({ options }: { options: OptionsData }) {
  const chain = options.snapshot?.chain;
  const atm = options.snapshot?.atm;
  if (!chain) return <div style={cardStyle}><div style={sectionLabel}>OPTION CHAIN</div><div style={{ color: colors.textMuted }}>NOT AVAILABLE</div></div>;

  const strikes = Array.from(new Set([...chain.CE.map((c) => c.strike), ...chain.PE.map((p) => p.strike)])).sort((a, b) => a - b);
  const callWall = options.metrics?.call_wall as { strike: number } | undefined;
  const putWall = options.metrics?.put_wall as { strike: number } | undefined;

  const leg = (side: "CE" | "PE", strike: number) => chain[side].find((l) => l.strike === strike);

  return (
    <div style={cardStyle}>
      <div style={sectionLabel}>OPTION CHAIN (ATM ± 5)</div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse", ...monoStyle }}>
          <thead>
            <tr style={{ color: colors.textMuted, textAlign: "right" }}>
              <th style={{ textAlign: "right", padding: 4 }}>CE Δ</th>
              <th style={{ textAlign: "right", padding: 4 }}>CE OI</th>
              <th style={{ textAlign: "right", padding: 4 }}>CE LTP</th>
              <th style={{ textAlign: "center", padding: 4 }}>STRIKE</th>
              <th style={{ textAlign: "left", padding: 4 }}>PE LTP</th>
              <th style={{ textAlign: "left", padding: 4 }}>PE OI</th>
              <th style={{ textAlign: "left", padding: 4 }}>PE Δ</th>
            </tr>
          </thead>
          <tbody>
            {strikes.map((strike) => {
              const ce = leg("CE", strike);
              const pe = leg("PE", strike);
              const isAtm = strike === atm;
              const isCallWall = callWall?.strike === strike;
              const isPutWall = putWall?.strike === strike;
              return (
                <tr key={strike} style={{ background: isAtm ? "#1a1a26" : "transparent" }}>
                  <td style={{ textAlign: "right", padding: 4, color: colors.textMuted }}>{ce?.delta ?? "—"}</td>
                  <td style={{ textAlign: "right", padding: 4, color: isCallWall ? colors.purple : "#e6e6ea" }}>
                    {ce?.oi.toLocaleString() ?? "—"}{isCallWall ? " (wall)" : ""}
                  </td>
                  <td style={{ textAlign: "right", padding: 4, color: colors.green }}>{ce?.ltp ?? "—"}</td>
                  <td style={{ textAlign: "center", padding: 4, fontWeight: isAtm ? 700 : 400, color: isAtm ? colors.purple : "#e6e6ea" }}>
                    {strike}{isAtm ? " ★" : ""}
                  </td>
                  <td style={{ textAlign: "left", padding: 4, color: colors.red }}>{pe?.ltp ?? "—"}</td>
                  <td style={{ textAlign: "left", padding: 4, color: isPutWall ? colors.purple : "#e6e6ea" }}>
                    {pe?.oi.toLocaleString() ?? "—"}{isPutWall ? " (wall)" : ""}
                  </td>
                  <td style={{ textAlign: "left", padding: 4, color: colors.textMuted }}>{pe?.delta ?? "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {options.metrics && (
        <div style={{ marginTop: 10, fontSize: 12, color: colors.textMuted }}>
          PCR: <b style={{ color: "#e6e6ea" }}>{String(options.metrics.pcr ?? "—")}</b>
        </div>
      )}
    </div>
  );
}

// ---- Gamma Analysis (spec section 13) -----------------------------------
export function GammaCard({ gamma }: { gamma: Record<string, unknown> }) {
  if (!gamma || Object.keys(gamma).length === 0 || gamma.call_wall === undefined) {
    return <div style={cardStyle}><div style={sectionLabel}>GAMMA ANALYSIS</div><div style={{ color: colors.textMuted }}>DATA NOT AVAILABLE</div></div>;
  }
  return (
    <div style={cardStyle}>
      <div style={sectionLabel}>GAMMA ANALYSIS</div>
      <div style={{ fontSize: 13, lineHeight: 1.9 }}>
        <div>Call Wall: <span style={monoStyle}>{String(gamma.call_wall)}</span></div>
        <div>Put Wall: <span style={monoStyle}>{String(gamma.put_wall)}</span></div>
        <div>Gamma Flip (est.): <span style={monoStyle}>{String(gamma.gamma_flip)}</span></div>
        {gamma.net_gex !== null && gamma.net_gex !== undefined && (
          <div>
            Net GEX: <span style={{ ...monoStyle, color: Number(gamma.net_gex) > 0 ? colors.green : colors.red }}>
              {Number(gamma.net_gex).toLocaleString()}
            </span>
            <span style={{ color: colors.textMuted, fontSize: 11 }}>
              {" "}({Number(gamma.net_gex) > 0 ? "dampening" : "accelerating"})
            </span>
          </div>
        )}
        <div>Pinning Zone: <span style={{ color: gamma.pinning_zone ? colors.amber : colors.textMuted }}>{gamma.pinning_zone ? "YES" : "No"}</span></div>
        <div style={{ color: colors.textMuted, marginTop: 6 }}>{String(gamma.expected_volatility ?? "")}</div>
      </div>
    </div>
  );
}

// ---- Liquidity Map (spec section 10) ------------------------------------
export function LiquidityMapCard({ liquidity }: { liquidity: Record<string, unknown> }) {
  if (!liquidity || liquidity.buy_side_liquidity === undefined) {
    return <div style={cardStyle}><div style={sectionLabel}>LIQUIDITY MAP</div><div style={{ color: colors.textMuted }}>NOT AVAILABLE</div></div>;
  }
  return (
    <div style={cardStyle}>
      <div style={sectionLabel}>LIQUIDITY MAP</div>
      <div style={{ fontSize: 13, lineHeight: 1.9 }}>
        <div>Buy-side liquidity: <span style={{ ...monoStyle, color: colors.green }}>{String(liquidity.buy_side_liquidity)}</span></div>
        <div>Sell-side liquidity: <span style={{ ...monoStyle, color: colors.red }}>{String(liquidity.sell_side_liquidity)}</span></div>
        <div style={{ color: colors.textMuted, marginTop: 6 }}>
          Current position: {String(liquidity.sweep_status).replace(/_/g, " ").toLowerCase()}
        </div>
      </div>
    </div>
  );
}

// ---- Trap Detection (spec section 14) -----------------------------------
export function TrapDetectionCard({ agent }: { agent: { reason: string; evidence: string[]; direction: string } | undefined }) {
  if (!agent) return null;
  const isTrap = !agent.reason.includes("NO TRAP") && !agent.reason.toLowerCase().includes("no_trap");
  return (
    <div style={cardStyle}>
      <div style={sectionLabel}>TRAP DETECTION</div>
      <div style={{ fontSize: 15, fontWeight: 700, color: isTrap ? colors.amber : colors.green, marginBottom: 6 }}>
        {agent.reason}
      </div>
      {agent.evidence.map((e, i) => (
        <div key={i} style={{ fontSize: 12, color: colors.textMuted }}>• {e}</div>
      ))}
    </div>
  );
}

// ---- Market Structure (spec section 9) ----------------------------------
export function MarketStructureCard({ structure }: { structure: Record<string, unknown> }) {
  if (!structure || Object.keys(structure).length === 0) {
    return <div style={cardStyle}><div style={sectionLabel}>MARKET STRUCTURE</div><div style={{ color: colors.textMuted }}>NOT AVAILABLE</div></div>;
  }
  const fvgs = (structure.fvgs as any[]) ?? [];
  const obs = (structure.order_blocks as any[]) ?? [];
  const candles = (structure.candlestick_patterns as any[]) ?? [];
  return (
    <div style={cardStyle}>
      <div style={sectionLabel}>MARKET STRUCTURE</div>
      <div style={{ fontSize: 14, marginBottom: 6 }}>
        Trend: <b style={{ color: structure.trend === "UPTREND" ? colors.green : structure.trend === "DOWNTREND" ? colors.red : colors.amber }}>
          {String(structure.trend)}
        </b>
      </div>
      <div style={{ fontSize: 12, color: colors.textMuted, marginBottom: 6 }}>
        Sequence: {(structure.sequence_labels as string[])?.join(" → ") || "—"}
      </div>
      <div style={{ fontSize: 13, marginBottom: 8 }}>
        {String(structure.last_event)}: <span style={{ color: colors.textMuted }}>{String(structure.last_event_detail)}</span>
      </div>
      {fvgs.length > 0 && (
        <div style={{ fontSize: 12, marginBottom: 4 }}>
          <span style={{ color: colors.textMuted }}>FVGs: </span>
          {fvgs.map((g, i) => (
            <span key={i} style={{ color: g.type === "BULLISH" ? colors.green : colors.red, marginRight: 8 }}>
              {g.type[0]}{g.gap_low.toFixed(0)}-{g.gap_high.toFixed(0)}
            </span>
          ))}
        </div>
      )}
      {obs.length > 0 && (
        <div style={{ fontSize: 12 }}>
          <span style={{ color: colors.textMuted }}>Order blocks: </span>
          {obs.map((o, i) => (
            <span key={i} style={{ color: o.type.includes("BULLISH") ? colors.green : colors.red, marginRight: 8 }}>
              {o.low.toFixed(0)}-{o.high.toFixed(0)}
            </span>
          ))}
        </div>
      )}
      {candles.length > 0 && (
        <div style={{ fontSize: 12, marginTop: 4 }}>
          <span style={{ color: colors.textMuted }}>Candlestick patterns: </span>
          {candles.map((p, i) => (
            <span key={i} style={{ color: p.bias === "BULLISH" ? colors.green : p.bias === "BEARISH" ? colors.red : colors.amber, marginRight: 8 }}>
              {p.type.replace(/_/g, " ")}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
