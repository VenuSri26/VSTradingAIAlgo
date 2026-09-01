import type { LiveDecisionResponse } from "../types/decision";
import type { AgentRegistry, DecisionReplay, DeploymentSnapshot, LogEntry, OperationalAlert, OperationsSystem, PaperAnalytics, PaperPortfolioSummary, PaperTrade, ReplayListItem, RiskStatus, StrategyLabResult, SystemMetrics, TradeSetup, TradeTimeline, VersionInfo, ZerodhaHealth, ReleaseCertificate, DecisionExplanation, InstitutionalFlowSummary, InstitutionalFlowTrend, InstitutionalFlowPoint, DecisionIntelligence, AICommandCenter, ProductionCandidateStatus, ResilienceStatus, OpenPaperManagement } from "../types/operations";

const BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.trim() || window.location.origin;

async function requestJSON<T>(path: string, init?: RequestInit, timeoutMs = 8000): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${BASE_URL}${path}`, { ...init, signal: controller.signal });
    if (!res.ok) {
      let detail = `${res.status} ${res.statusText}`;
      try { const body = await res.json(); detail = body.detail ?? detail; } catch { /* ignore */ }
      throw new Error(detail);
    }
    return await res.json() as T;
  } finally { window.clearTimeout(timeout); }
}
function adminHeaders(token: string): HeadersInit { return { "Content-Type": "application/json", "X-Admin-Token": token }; }

export const api = {
  getLiveDecision: () => requestJSON<LiveDecisionResponse>("/api/decision/live"),
  getAnalyticsSession: () => requestJSON<Record<string, unknown>>("/api/analytics/session"),
  getPaperAnalytics: () => requestJSON<PaperAnalytics>("/api/analytics/paper"),
  getReplays: () => requestJSON<{replays: ReplayListItem[]}>("/api/replay?limit=50"),
  getReplay: (tradeId: number) => requestJSON<DecisionReplay>(`/api/replay/${tradeId}`),
  getMetrics: () => requestJSON<SystemMetrics>("/api/system/metrics"),
  getAlerts: () => requestJSON<{alerts: OperationalAlert[]}>("/api/system/alerts?limit=10"),
  getVersion: () => requestJSON<VersionInfo>("/api/system/version"),
  getReleaseCertificate: () => requestJSON<ReleaseCertificate>("/api/system/release-certificate"),
  getDecisionExplanation: () => requestJSON<DecisionExplanation>("/api/decision/explain"),
  getZerodhaHealth: () => requestJSON<ZerodhaHealth>("/api/system/zerodha-health"),
  getSetups: (status?: string) => requestJSON<{setups: TradeSetup[]}>(`/api/setups?limit=20${status ? `&status=${encodeURIComponent(status)}` : ""}`),
  reviewSetup: (id: number, status: "APPROVED"|"REJECTED"|"EXPIRED"|"CANCELLED", note: string, token: string) =>
    requestJSON<TradeSetup>(`/api/setups/${id}/review`, { method: "POST", headers: adminHeaders(token), body: JSON.stringify({status, note}) }),
  getPaperTrades: () => requestJSON<{trades: PaperTrade[]}>("/api/paper/trades?limit=20"),
  executePaper: (setup_id: number, entry_price: number, quantity: number | undefined, token: string) =>
    requestJSON<Record<string, unknown>>("/api/paper/execute", { method: "POST", headers: adminHeaders(token), body: JSON.stringify({setup_id, entry_price, ...(quantity ? {quantity} : {})}) }),
  monitorPaper: (current_price: number, force_eod: boolean, token: string) =>
    requestJSON<Record<string, unknown>>("/api/paper/monitor", { method: "POST", headers: adminHeaders(token), body: JSON.stringify({current_price, force_eod}) }),
  getPaperPortfolio: () => requestJSON<PaperPortfolioSummary>("/api/paper/portfolio"),
  getPaperManagement: () => requestJSON<OpenPaperManagement>("/api/paper/management/status"),
  configurePaperManagement: (trailing_enabled: boolean, trail_distance_pct: number, token: string) =>
    requestJSON<any>("/api/paper/management/config", {method:"POST", headers:adminHeaders(token), body:JSON.stringify({trailing_enabled, trail_distance_pct})}),
  getTradeTimeline: (tradeId: number) => requestJSON<TradeTimeline>(`/api/paper/trades/${tradeId}/timeline`),
  closePaper: (close_price: number, reason: string, token: string) =>
    requestJSON<PaperTrade>("/api/paper/close", { method: "POST", headers: adminHeaders(token), body: JSON.stringify({close_price, reason}) }),
  getRiskStatus: () => requestJSON<RiskStatus>("/api/risk/status"),
  setKillSwitch: (enabled: boolean, reason: string | null, token: string) =>
    requestJSON<Record<string, unknown>>("/api/risk/kill-switch", { method: "POST", headers: adminHeaders(token), body: JSON.stringify({enabled, reason}) }),
  getOperationsSystem: () => requestJSON<OperationsSystem>("/api/operations/system"),
  getOperationsLogs: () => requestJSON<{path:string; exists:boolean; entries:LogEntry[]}>("/api/operations/logs?limit=100"),
  getDeployments: () => requestJSON<DeploymentSnapshot>("/api/operations/deployments"),
  getAgentRegistry: () => requestJSON<AgentRegistry>("/api/agents/registry"),
  getStrategySample: () => requestJSON<Record<string, unknown>>("/api/strategy-lab/sample"),
  validateStrategy: (payload: Record<string, unknown>) => requestJSON<StrategyLabResult>("/api/strategy-lab/validate", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify(payload) }, 30000),
  getOptionChainSummary: () => requestJSON<any>("/api/option-chain/summary"),
  getOptionChainLive: () => requestJSON<any>("/api/option-chain/live"),
  getInstitutionalFlow: () => requestJSON<InstitutionalFlowSummary>("/api/institutional-flow/summary"),
  getInstitutionalFlowTrend: () => requestJSON<InstitutionalFlowTrend>("/api/institutional-flow/trend?limit=120"),
  getInstitutionalFlowAnomalies: () => requestJSON<{anomalies:InstitutionalFlowPoint[]}>("/api/institutional-flow/anomalies?limit=20"),
  getDecisionIntelligence: () => requestJSON<DecisionIntelligence>("/api/decision/intelligence"),
  getAICommandCenter: () => requestJSON<AICommandCenter>("/api/ai-command-center"),
  getProductionCandidateStatus: () => requestJSON<ProductionCandidateStatus>("/api/production-candidate/status"),
  getResilienceStatus: () => requestJSON<ResilienceStatus>("/api/resilience/status"),
  getLearningCapabilities: () => requestJSON<any>("/api/learning/capabilities"),
  evaluateLearning: (payload: Record<string, unknown>) => requestJSON<any>("/api/learning/evaluate", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)}, 30000),
  runWalkForward: (payload: Record<string, unknown>) => requestJSON<any>("/api/optimization/walk-forward", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)}, 30000),
  getMarketRegimeIntelligence: () => requestJSON<any>("/api/market-regime/intelligence"),
  getGammaIntelligence: () => requestJSON<any>("/api/gamma/intelligence"),
  getMarketSafety: () => requestJSON<any>("/api/market-safety/status"),
  getFeedAlerts: () => requestJSON<any>("/api/feed-alerts/status"),
  getTickBridgeStatus: () => requestJSON<any>("/api/tick-bridge/status"),
  getTickBridgeHistory: () => requestJSON<any>("/api/tick-bridge/history?limit=20"),
  getKiteStreamStatus: () => requestJSON<any>("/api/kite-stream/status"),
  getKiteStreamHistory: () => requestJSON<any>("/api/kite-stream/history?limit=20"),
  getKiteRuntimeStatus: () => requestJSON<any>("/api/kite-runtime/status"),
  syncKiteRuntimeSubscriptions: (token: string) => requestJSON<any>("/api/kite-runtime/sync-subscriptions", {method:"POST", headers:adminHeaders(token)}),
  getRuntimeMaintenance: () => requestJSON<any>("/api/runtime-maintenance/status"),
  getRuntimeNotifications: () => requestJSON<any>("/api/runtime-maintenance/notifications?limit=20"),
  getIntegrationReadiness: () => requestJSON<any>("/api/integration-readiness/status"),
  getLiveSessionValidation: () => requestJSON<any>("/api/live-session-validation/status"),
  getLiveSessionValidationHistory: () => requestJSON<any>("/api/live-session-validation/history?limit=100"),
  getLiveSessionSessions: () => requestJSON<any>("/api/live-session-validation/sessions?limit_days=10"),
  getLiveSessionRecorder: () => requestJSON<any>("/api/live-session-validation/recorder"),
  recordLiveSessionNow: (token: string) => requestJSON<any>("/api/live-session-validation/record-now", {method:"POST", headers:adminHeaders(token)}),
  getLiveSessionCertification: () => requestJSON<any>("/api/live-session-certification/status?limit_days=30"),
  notifyLiveSessionCertification: (token: string) => requestJSON<any>("/api/live-session-certification/notify?limit_days=30", {method:"POST", headers:adminHeaders(token)}),
  getLiveSessionCertificationBreakdown: () => requestJSON<any>("/api/live-session-certification/breakdown?limit_days=30"),
  getLiveSessionCertificationEodScheduler: () => requestJSON<any>("/api/live-session-certification/eod-scheduler"),
  runLiveSessionCertificationEodScheduler: (force: boolean, token: string) => requestJSON<any>(`/api/live-session-certification/eod-scheduler/run?force=${force ? "true" : "false"}`, {method:"POST", headers:adminHeaders(token)}),
  getNotificationOutbox: () => requestJSON<any>("/api/notifications/outbox?limit=20"),
  dispatchNotifications: (token: string) => requestJSON<any>("/api/notifications/dispatch", {method:"POST", headers:adminHeaders(token)}),
  getNotificationScheduler: () => requestJSON<any>("/api/notifications/scheduler"),
  runNotificationScheduler: (token: string) => requestJSON<any>("/api/notifications/scheduler/run", {method:"POST", headers:adminHeaders(token)}),
  acknowledgeNotification: (id: string, note: string, token: string) => requestJSON<any>(`/api/notifications/${encodeURIComponent(id)}/acknowledge`, {method:"POST", headers:adminHeaders(token), body:JSON.stringify({note})}),
  getOperationalDigest: () => requestJSON<any>("/api/operations/digest/status"),
  getOperationalDigestHistory: () => requestJSON<any>("/api/operations/digest/history?limit=10"),
  getOperationalDigestScheduler: () => requestJSON<any>("/api/operations/digest/scheduler"),
  runOperationalDigestScheduler: (force: boolean, token: string) => requestJSON<any>(`/api/operations/digest/scheduler/run?force=${force ? "true" : "false"}`, {method:"POST", headers:adminHeaders(token)}),
  generateOperationalDigest: (enqueue: boolean, token: string) => requestJSON<any>(`/api/operations/digest/generate?enqueue=${enqueue ? "true" : "false"}`, {method:"POST", headers:adminHeaders(token)}),
  getMarketHolidays: () => requestJSON<any>("/api/market-calendar/holidays"),
  importMarketHolidays: (content: string, format: string, replace: boolean, token: string) => requestJSON<any>("/api/market-calendar/import", {method:"POST", headers:adminHeaders(token), body:JSON.stringify({content, format, replace})}),
  syncMarketHolidays: (url: string | null, format: string | null, replace: boolean, token: string) => requestJSON<any>("/api/market-calendar/sync", {method:"POST", headers:adminHeaders(token), body:JSON.stringify({url, format, replace})}),
  compareBrokerGreeks: (payload: Record<string, unknown>) => requestJSON<any>("/api/broker-greeks/compare", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)}),
  getBrokerGreeksHistory: () => requestJSON<any>("/api/broker-greeks/history?limit=50"),
  getBrokerGreeksSessionSummary: () => requestJSON<any>("/api/broker-greeks/session-summary"),
  runRuntimeMaintenance: (token: string) => requestJSON<any>("/api/runtime-maintenance/run", {method:"POST", headers:adminHeaders(token)}),
  setKiteStreamSubscriptions: (instrument_tokens: number[], token: string) => requestJSON<any>("/api/kite-stream/subscriptions", {method:"POST", headers:adminHeaders(token), body:JSON.stringify({instrument_tokens})}),
  getFeedAlertHistory: () => requestJSON<any>("/api/feed-alerts/history?limit=20"),
  getMarketClock: () => requestJSON<any>("/api/market-safety/clock"),
  getLiveDataStatus: () => requestJSON<any>("/api/live-data/status"),
  getLiveMarketStatus: () => requestJSON<any>("/api/live-market/status"),
  getLiveMarketSources: () => requestJSON<any>("/api/live-market/sources"),
  getLiveMarketSnapshot: () => requestJSON<any>("/api/live-market/snapshot"),
  getLiveMarketFeed: () => requestJSON<any>("/api/live-market/feed"),
  getLiveMarketTicks: () => requestJSON<any>("/api/live-market/ticks?limit=50"),
  getLiveMarketCandles: () => requestJSON<any>("/api/live-market/candles?timeframe=3m&limit=120&include_current=true"),
  getLiveMarketIndicators: () => requestJSON<any>("/api/live-market/indicators?lookback=120"),
  getLiveIntelligence: () => requestJSON<any>("/api/live-intelligence/status"),
  getLiveIntelligenceHistory: () => requestJSON<any>("/api/live-intelligence/history?limit=60"),
  getLiveIntelligenceTrend: () => requestJSON<any>("/api/live-intelligence/trend?limit=60"),
  getLivePaperPreview: () => requestJSON<any>("/api/live-paper/preview"),
  prepareLivePaperSetup: (token: string) => requestJSON<any>("/api/live-paper/prepare", {method:"POST", headers:adminHeaders(token), body:JSON.stringify({confirmation_text:"PREPARE_PAPER_SETUP"})}),
  refreshLiveData: (token: string) => requestJSON<any>("/api/live-data/refresh", {method:"POST", headers:adminHeaders(token)}),
  pollLiveData: (token: string) => requestJSON<any>("/api/live-data/poll", {method:"POST", headers:adminHeaders(token)}),
  syncInstruments: (token: string) => requestJSON<any>("/api/live-data/instruments/sync", {method:"POST", headers:adminHeaders(token)}),
  getLiveCandles: () => requestJSON<any>("/api/live-data/candles"),
  getSecurityStatus: () => requestJSON<any>("/api/security/status"),
  getExecutionOrders: () => requestJSON<any>("/api/execution/orders"),
  previewOrder: (payload: Record<string, unknown>, token: string) => requestJSON<any>("/api/execution/preview", {method:"POST", headers:adminHeaders(token), body:JSON.stringify(payload)}),
  confirmOrder: (preview_id: string, confirmation_text: string, token: string) => requestJSON<any>("/api/execution/confirm", {method:"POST", headers:adminHeaders(token), body:JSON.stringify({preview_id, confirmation_text})}),
};
