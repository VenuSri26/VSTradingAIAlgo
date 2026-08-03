// Mirrors backend/app/schemas.py::LiveDecisionResponseSchema exactly.
// Keep these two files in sync manually until a codegen step is added
// (e.g. openapi-typescript against /openapi.json).

export type Direction = "BULLISH" | "BEARISH" | "NEUTRAL" | "NOT_AVAILABLE";
export type Availability = "OK" | "NOT_AVAILABLE" | "STALE" | "DATA_ERROR";
export type TradeGrade = "A+" | "A" | "B" | "C" | "NO_TRADE";
export type DecisionType = "CE_BUY" | "PE_BUY" | "NO_TRADE";
export type HealthStatus = "GREEN" | "AMBER" | "RED";
export type FlagCategory = "BULL" | "BEAR" | "WATCH";

export interface AgentResult {
  name: string;
  score: number | null;
  direction: Direction;
  confidence: number | null;
  reason: string;
  evidence: string[];
  weight: number;
  timestamp: string;
  availability: Availability;
}

export interface Alignment {
  score: number | null;
  bullish_contribution: number;
  bearish_contribution: number;
  neutral_contribution: number;
  weights_used: Record<string, number>;
  timestamp: string;
}

export interface Flag {
  category: FlagCategory;
  text: string;
  agent_source: string;
}

export interface EntryChecklistItem {
  label: string;
  passed: boolean;
  detail: string;
}

export interface TradePlan {
  option_type: "CE" | "PE" | null;
  strike: number | null;
  ltp: number | null;
  entry_low: number | null;
  entry_high: number | null;
  trigger: string | null;
  confirmation: string | null;
  stop_loss: number | null;
  target_1: number | null;
  target_2: number | null;
  risk_reward: number | null;
  max_risk_rupees: number | null;
  invalidation: string | null;
  delta: number | null;
  theta: number | null;
  iv: number | null;
}

export interface Decision {
  decision: DecisionType;
  grade: TradeGrade;
  confidence: number | null;
  alignment_score: number | null;
  plan: TradePlan | null;
  checklist: EntryChecklistItem[];
  explanation: string;
  timestamp: string;
}

export interface RiskResult {
  approved: boolean;
  reasons: string[];
  trades_today: number;
  max_trades: number;
  daily_pnl: number;
  daily_loss_limit: number;
  consecutive_losses: number;
}

export interface PositionInfo {
  has_position: boolean;
  option_type?: "CE" | "PE" | null;
  strike?: number | null;
  quantity?: number | null;
  entry_price?: number | null;
  current_price?: number | null;
  pnl?: number | null;
  pnl_pct?: number | null;
  stop_loss?: number | null;
  target_1?: number | null;
  target_2?: number | null;
  status?: string | null;
  time_in_trade_sec?: number | null;
}

export interface ComponentHealth {
  name: string;
  status: HealthStatus;
  detail: string;
}

export interface SystemHealth {
  components: ComponentHealth[];
  last_tick_timestamp: string | null;
  data_age_sec: number | null;
  overall: HealthStatus;
}

export interface LiveDecisionResponse {
  timestamp: string;
  market: Record<string, unknown>;
  regime: Record<string, unknown>;
  levels: Record<string, unknown>;
  indicators: Record<string, unknown>;
  options: Record<string, unknown>;
  gamma: Record<string, unknown>;
  liquidity: Record<string, unknown>;
  agents: AgentResult[];
  alignment: Alignment;
  flags: Flag[];
  decision: Decision;
  risk: RiskResult;
  position: PositionInfo;
  system_health: SystemHealth;
  market_structure: Record<string, unknown>;
  narrative: string;
}
