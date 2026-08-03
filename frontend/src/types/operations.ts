export type SetupStatus = "GENERATED" | "APPROVED" | "REJECTED" | "EXPIRED" | "CANCELLED" | "PAPER_OPEN" | "PAPER_CLOSED";

export interface TradeSetup {
  id: number; trading_day: string; generated_at: string; decision: string; grade: string;
  alignment_score: number | null; option_type: "CE" | "PE" | null; strike: number | null;
  entry_low: number | null; entry_high: number | null; stop_loss: number | null;
  target_1: number | null; target_2: number | null; risk_reward: number | null;
  explanation: string | null; status: SetupStatus; reviewed_at: string | null; review_note: string | null;
}
export interface PaperTrade {
  id: number; setup_id: number; trading_day: string; option_type: string; strike: number; quantity: number;
  entry_price: number; stop_loss: number; target_1: number | null; target_2: number | null;
  opened_at: string; closed_at: string | null; close_price: number | null; status: string;
  gross_pnl: number | null; estimated_costs: number; net_pnl: number | null; exit_reason: string | null;
}
export interface SystemMetrics {
  uptime_sec: number; pipeline_runs: number; pipeline_failures: number; pipeline_success_rate: number;
  pipeline_avg_duration_ms: number; pipeline_last_duration_ms: number; stale_data_events: number;
  decision_counts: Record<string, number>; active_alerts: number;
}
export interface OperationalAlert { timestamp: string; severity?: string; code: string; message: string; detail?: string; }
export interface VersionInfo { version: string; build_id?: string; build_time?: string; git_commit?: string; environment?: string; release_path?: string | null; reported_at?: string; }
export interface ZerodhaHealth { connected: boolean; source: string; mode: string; detail?: string; }

export interface PaperPortfolioSummary {
  total_trades: number; open_trades: number; closed_trades: number; wins: number; losses: number;
  win_rate: number; gross_pnl: number; estimated_costs: number; net_pnl: number; avg_win: number; avg_loss: number;
}
export interface RiskStatus {
  blocked: boolean; kill_switch: boolean; kill_switch_reason: string | null; trades_today: number; remaining_trades: number;
  daily_pnl: number; daily_loss_limit: number; remaining_loss_capacity: number; consecutive_losses: number;
  max_consecutive_losses: number; paper_capital: number; max_risk_per_trade_pct: number; max_capital_utilization_pct: number;
}
export interface TradeTimeline { trade: PaperTrade; setup: TradeSetup | null; events: Array<{id:number; trade_id:number; checked_at:string; current_price:number|null; action:string; detail:string|null}>; }

export interface AnalyticsSummary {
  total_trades: number; wins: number; losses: number; win_rate: number; net_pnl: number;
  gross_profit: number; gross_loss: number; avg_win: number; avg_loss: number;
  expectancy: number; profit_factor: number | null; max_drawdown: number;
}
export interface EquityPoint { trade_id: number; timestamp: string; net_pnl: number; equity: number; drawdown: number; }
export interface AnalyticsBucket { trades: number; wins: number; losses: number; net_pnl: number; win_rate: number; }
export interface PaperAnalytics {
  summary: AnalyticsSummary; equity_curve: EquityPoint[];
  daily: Array<AnalyticsBucket & { trading_day: string }>;
  by_option_type: Record<string, AnalyticsBucket>;
  by_grade: Record<string, AnalyticsBucket>;
  by_exit_reason: Record<string, AnalyticsBucket>;
}
export interface ReplayListItem {
  trade_id: number; setup_id: number; trading_day: string; option_type: string; strike: number;
  quantity: number; entry_price: number; close_price: number | null; status: string; net_pnl: number | null;
  exit_reason: string | null; opened_at: string; closed_at: string | null; decision: string | null;
  grade: string | null; alignment_score: number | null; explanation: string | null;
}
export interface DecisionReplay extends TradeTimeline {
  market_snapshot: Record<string, unknown> | null; replay_version: number; execution_mode: "PAPER_ONLY";
}

export interface OperationsSystem {
  timestamp: string; hostname: string; uptime_sec: number; process_id: number;
  load_average: number[] | null; trading_mode: string; paper_monitor_enabled: boolean; version: string;
  memory: { total_bytes: number | null; available_bytes: number | null; used_pct: number | null };
  disk: { total_bytes: number; free_bytes: number; used_bytes: number; used_pct: number | null };
}
export interface DeploymentSnapshot { current_release: string | null; history: string[]; backups: string[]; }
export interface LogEntry { timestamp?: string; level?: string; logger?: string; message?: string; [key: string]: unknown; }
export interface AgentRegistryItem {
  name: string; score: number | null; direction: string; confidence: number | null; reason: string;
  evidence: string[]; weight: number; availability: string; family: string; purpose: string;
}
export interface AgentRegistry {
  agents: AgentRegistryItem[]; alignment: Record<string, unknown>; debate: Record<string, unknown>;
  final_decision: Record<string, unknown>; execution_mode: string;
}
export interface StrategyLabResult {
  run_at: string; name: string; summary: Record<string, unknown>; trades: Array<Record<string, unknown>>;
  walk_forward_splits: Array<Record<string, number>>; config: Record<string, unknown>;
  promotion_status: string; note: string;
}

export interface ReleaseCertificate { generated_at:string; status:string; health_score:number; checks:Record<string,boolean>; version:VersionInfo; system:OperationsSystem; database:Record<string,unknown>; deployment:DeploymentSnapshot; last_smoke_test:Record<string,unknown>; configuration_problems:string[]; }
export interface DecisionExplanation { decision:string; grade:string; confidence:number; alignment_score:number; risk_approved:boolean; checklist:{passed:string[];failed:string[]}; why:string[]; why_not:string[]; invalidation_conditions:string[]; agent_votes:{bullish:number;bearish:number;neutral:number}; option_chain:Record<string,unknown>|null; summary:string; }

export interface InstitutionalFlowComponent { name:string; score:number; direction:string; confidence:number; reason:string; }
export interface FlowAnomaly { anomaly:boolean; anomaly_score:number; codes:string[]; details:string[]; pcr_zscore:number; flow_score_zscore:number; }
export interface InstitutionalFlowSummary {
  institutional_flow_score:number; institutional_bias:string; confidence:number; options_buildup:string;
  futures_buildup:string; pcr:number; pcr_trend:string; components:InstitutionalFlowComponent[];
  warnings:string[]; safe_for_live_execution:boolean; note:string; snapshot_id?:number; captured_at?:string; anomaly?:FlowAnomaly;
}
export interface InstitutionalFlowPoint { id:number; captured_at:string; trading_day:string; spot:number|null; pcr:number|null; pcr_trend:string|null; institutional_flow_score:number; institutional_bias:string; confidence:number; options_score:number|null; futures_score:number|null; cash_score:number|null; warning_count:number; anomaly_score:number; anomaly_codes:string[]; }
export interface InstitutionalFlowTrend { trading_day:string; samples:number; trend:string; score_change:number; pcr_change:number; latest:InstitutionalFlowPoint|null; points:InstitutionalFlowPoint[]; }
export interface DecisionIntelligence { decision:string; base_confidence:number; adjusted_confidence:number; institutional_flow:InstitutionalFlowSummary|null; option_chain:Record<string,unknown>|null; checks:Array<{name:string;passed:boolean;detail:string}>; execution_mode:string; live_orders_enabled:boolean; }

export interface AICommandCenter {
  decision:string; grade:string; overall_score:number; confidence:number;
  scores:{trend:number;institutional:number;structure:number;gamma:number;risk:number};
  weights:Record<string,number>; votes:{bullish:number;bearish:number;neutral:number};
  market_regime:Record<string,unknown>; structure:Record<string,unknown>; gamma:Record<string,unknown>;
  institutional_flow:InstitutionalFlowSummary|null; why:string[]; why_not:string[];
  invalidation_conditions:string[]; execution_mode:string; live_orders_enabled:boolean;
}
