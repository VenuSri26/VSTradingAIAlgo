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

export interface ProductionCandidateRule { code:string; label:string; passed:boolean; weight:number; detail:string; }
export interface ProductionCandidateStatus {
  version:VersionInfo; status:string; readiness_score:number; execution_mode:string; live_orders_enabled:boolean;
  rules:ProductionCandidateRule[]; blockers:ProductionCandidateRule[]; paper_performance:AnalyticsSummary;
  risk:RiskStatus; release_health_score:number; next_action:string;
}

export interface ResilienceCheck { code:string; label:string; status:"PASS"|"WARN"|"FAIL"; detail:string; blocking:boolean; }
export interface ResilienceStatus {
  version:VersionInfo; overall:"READY"|"DEGRADED"|"BLOCKED"; resilience_score:number; restart_safe:boolean;
  paper_only:boolean; checks:ResilienceCheck[]; blocking_issues:ResilienceCheck[]; warning_count:number;
  recommended_action:string; generated_at:string;
}

export interface PaperManagementState {
  trade_id:number; original_quantity:number; remaining_quantity:number; realized_quantity:number;
  realized_gross_pnl:number; realized_costs:number; highest_price:number; active_stop_loss:number;
  partial_target_done:number; breakeven_armed:number; trailing_enabled:number;
  trail_distance_pct:number; last_action:string; updated_at:string;
}
export interface OpenPaperManagement { trade:PaperTrade|null; management:PaperManagementState|null; execution_mode?:string; }

export interface PaperAutomationRun {
  id:number; checked_at:string; trading_day:string; cycle_key:string|null; action:string;
  reason:string|null; setup_id:number|null; trade_id:number|null; details?:Record<string,unknown>;
}
export interface PaperAutomationSummary {
  trading_day:string; recorded_cycles:number; paper_trades_opened:number; blocked:number;
  no_trade:number; actions:Record<string,number>;
}
export interface PaperAutomationStatus {
  running:boolean; iterations:number; paper_trades_opened:number; blocked:number;
  last_checked_at:string|null; last_action:string; last_reason:string|null;
  last_setup_id:number|null; last_trade_id:number|null; enabled:boolean; interval_sec:number;
  minimum_score:number; allowed_grades:string; execution_mode:"PAPER_ONLY";
  full_pipeline_required:boolean; cost_model_version:string;
  live_orders_enabled:false; persistent_today:PaperAutomationSummary; recent_runs:PaperAutomationRun[];
}
export interface PaperMonitorStatus {
  running:boolean; iterations:number; successful_quotes:number; quote_failures:number;
  last_checked_at:string|null; last_price:number|null; last_action:string;
  last_error:string|null; active_trade_id:number|null; enabled:boolean; interval_sec:number;
  max_quote_age_sec:number; eod_exit_time:string; execution_mode:"PAPER_ONLY";
}
export interface PaperDailySummary {
  trading_day:string|null; portfolio:PaperPortfolioSummary; open_positions:Array<Record<string,unknown>>;
  journal_entries:number; execution_mode:"PAPER_ONLY"; broker_orders_sent:false;
}
export interface PaperLoopReadiness {
  generated_at:string; status:"OFFLINE_COMPLETE_LIVE_PENDING"|"OFFLINE_BLOCKED";
  offline_complete:boolean; live_market_pending:boolean;
  checks:Array<{code:string;label:string;passed:boolean;detail:string}>;
  failed_checks:Array<{code:string;label:string;passed:boolean;detail:string}>;
  pending_live_evidence:string[];
  runtime:{automation_running:boolean;monitor_running:boolean;last_action:string|null;last_reason:string|null};
  execution_mode:"PAPER_ONLY"; live_orders_enabled:boolean; recommended_action:string;
}
export interface TradingReport {
  report_type:"PRE_MARKET"|"POST_MARKET"; generated_at:string; trading_day:string;
  analysis:{status:string;message:string};
  summary:{recommendations:number;decision_cycles:number;paper_trades:number;paper_open:number;
    paper_net_pnl:number;zerodha_orders:number;zerodha_trades:number;unmatched_zerodha_orders:number;
    application_execution_orders:number};
  lineage:Array<{setup_id:number;recommendation:string;grade:string;score:number;contract:string;
    setup_status:string;paper_trade_id:number|null;paper_status:string|null;
    broker_order_id:string|null;broker_status:string|null;broker_match:string;execution_id:string|null}>;
  unmatched_zerodha_orders:Array<Record<string,unknown>>;
  safety:{execution_mode:string;live_orders_enabled:boolean;broker_access:string};
}
export interface TradingReportStatus {
  pre_market:TradingReport|null; post_market:TradingReport|null;
  schedulers:{pre_market:{configured_time:string;last_run_at:string|null;last_error:string|null};
    post_market:{configured_time:string;last_run_at:string|null;last_error:string|null}};
  execution_mode:"PAPER_ONLY"; live_orders_enabled:false;
}
export interface SetupConfiguration {
  execution_mode:"PAPER_ONLY"; paper_enabled:boolean; live_mode_locked:true;
  live_mode_unlock_requirement:string; live_orders_enabled:false;
  minimum_confidence:number; capital:number; capital_min:number; capital_max:number;
  profit_withdrawal_threshold:number; default_stop_loss_pct:number;
  zerodha:{connected:boolean;checked_at?:string;source?:string;user_id?:string;error?:string};
  https_required_for_token_refresh:boolean; https_configured:boolean; secrets_exposed:false;
}
