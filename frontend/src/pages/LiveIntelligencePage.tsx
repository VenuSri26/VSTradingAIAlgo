import { useEffect, useState } from "react";
import { api } from "../services/api";

type Status = {
  status: string; readiness_score: number; spot?: number; atm_strike?: number;
  expiry?: string; contracts: number; completeness_pct: number; pcr_oi?: number;
  call_wall?: number; put_wall?: number; max_pain?: number; age_sec?: number;
  warnings: string[]; blockers: string[]; recommended_action: string;
};
type Point = { captured_at:string; pcr_oi?:number; total_ce_oi:number; total_pe_oi:number; readiness_score:number; status:string };
type Trend = { samples:number; trend:string; pcr_change?:number; ce_oi_change?:number; pe_oi_change?:number; history:Point[] };

export function LiveIntelligencePage() {
  const [maintenance, setMaintenance] = useState<any>(null);
  const [integration, setIntegration] = useState<any>(null);
  const [liveSession, setLiveSession] = useState<any>(null);
  const [liveSessionSessions, setLiveSessionSessions] = useState<any>(null);
  const [liveSessionRecorder, setLiveSessionRecorder] = useState<any>(null);
  const [liveSessionCertification, setLiveSessionCertification] = useState<any>(null);
  const [certificationBreakdown, setCertificationBreakdown] = useState<any>(null);
  const [certificationEod, setCertificationEod] = useState<any>(null);
  const [outbox, setOutbox] = useState<any>(null);
  const [greeksSession, setGreeksSession] = useState<any>(null);
  const [notificationScheduler, setNotificationScheduler] = useState<any>(null);
  const [operationalDigest, setOperationalDigest] = useState<any>(null);
  const [digestHistory, setDigestHistory] = useState<any[]>([]);
  const [digestScheduler, setDigestScheduler] = useState<any>(null);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [data, setData] = useState<Status | null>(null);
  const [trend, setTrend] = useState<Trend | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<any>(null);
  const [prepareMessage, setPrepareMessage] = useState<string | null>(null);
  const [safety, setSafety] = useState<any>(null);
  const [feedAlerts, setFeedAlerts] = useState<any>(null);
  const [tickBridge, setTickBridge] = useState<any>(null);
  const [kiteStream, setKiteStream] = useState<any>(null);
  const [kiteRuntime, setKiteRuntime] = useState<any>(null);
  const [liveMarket, setLiveMarket] = useState<any>(null);
  const [liveSources, setLiveSources] = useState<any>(null);
  const [realtimeFeed, setRealtimeFeed] = useState<any>(null);
  const [realtimeIndicators, setRealtimeIndicators] = useState<any>(null);
  useEffect(() => {
    let active = true;
    const pullRealtime = async () => {
      try {
        const [feed, indicators] = await Promise.all([api.getLiveMarketFeed(), api.getLiveMarketIndicators()]);
        if (active) { setRealtimeFeed(feed); setRealtimeIndicators(indicators); }
      } catch { /* gateway panel already surfaces connection errors */ }
    };
    pullRealtime();
    const timer = window.setInterval(pullRealtime, 3000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);
  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const [status, series, paperPreview, feedSafety, alerts, ticks, stream, runtime, maintenanceStatus, notificationStatus, integrationStatus, outboxStatus, greeksStatus, schedulerStatus, digestStatus, digestRows, digestSchedulerStatus, liveSessionStatus, sessionReports, recorderStatus, certificationStatus, certificationBreakdownStatus, certificationEodStatus, liveMarketStatus, liveMarketSources] = await Promise.all([api.getLiveIntelligence(), api.getLiveIntelligenceTrend(), api.getLivePaperPreview(), api.getMarketSafety(), api.getFeedAlerts(), api.getTickBridgeStatus(), api.getKiteStreamStatus(), api.getKiteRuntimeStatus(), api.getRuntimeMaintenance(), api.getRuntimeNotifications(), api.getIntegrationReadiness(), api.getNotificationOutbox(), api.getBrokerGreeksSessionSummary(), api.getNotificationScheduler(), api.getOperationalDigest(), api.getOperationalDigestHistory(), api.getOperationalDigestScheduler(), api.getLiveSessionValidation(), api.getLiveSessionSessions(), api.getLiveSessionRecorder(), api.getLiveSessionCertification(), api.getLiveSessionCertificationBreakdown(), api.getLiveSessionCertificationEodScheduler(), api.getLiveMarketStatus(), api.getLiveMarketSources()]);
        if (active) { setData(status); setTrend(series); setPreview(paperPreview); setSafety(feedSafety); setFeedAlerts(alerts); setTickBridge(ticks); setKiteStream(stream); setKiteRuntime(runtime); setMaintenance(maintenanceStatus); setNotifications(notificationStatus.notifications ?? []); setIntegration(integrationStatus); setOutbox(outboxStatus); setGreeksSession(greeksStatus); setNotificationScheduler(schedulerStatus); setOperationalDigest(digestStatus); setDigestHistory(digestRows.items ?? []); setDigestScheduler(digestSchedulerStatus); setLiveSession(liveSessionStatus); setLiveSessionSessions(sessionReports); setLiveSessionRecorder(recorderStatus); setLiveSessionCertification(certificationStatus); setCertificationBreakdown(certificationBreakdownStatus); setCertificationEod(certificationEodStatus); setLiveMarket(liveMarketStatus); setLiveSources(liveMarketSources); setError(null); }
      } catch (e) { if (active) setError(String(e)); }
    };
    load(); const timer = window.setInterval(load, 15000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);
  if (error) return <section className="panel"><h2>Live Intelligence</h2><p>{error}</p></section>;
  if (!data) return <section className="panel"><h2>Live Intelligence</h2><p>Loading…</p></section>;
  const metrics = [
    ["Readiness", `${data.readiness_score}/100`], ["Spot", data.spot ?? "—"], ["ATM", data.atm_strike ?? "—"],
    ["PCR", data.pcr_oi ?? "—"], ["Call Wall", data.call_wall ?? "—"], ["Put Wall", data.put_wall ?? "—"],
    ["Max Pain", data.max_pain ?? "—"], ["Contracts", data.contracts], ["Completeness", `${data.completeness_pct}%`],
  ];
  const points = trend?.history ?? [];
  const maxOi = Math.max(1, ...points.flatMap(p => [p.total_ce_oi || 0, p.total_pe_oi || 0]));
  return <div className="page-stack">
    <section className="panel"><div className="panel-heading"><div><h2>V7 Live Market Gateway</h2><p>Strict source validation: live Zerodha data or unavailable. No synthetic fallback in live mode.</p></div><span className={`status-chip ${liveMarket?.status === "READY" ? "positive" : "negative"}`}>{liveMarket?.status ?? "LOADING"}</span></div>
      <div className="metric-grid">
        <div className="metric-card"><span>Source</span><strong>{liveMarket?.source ?? "—"}</strong></div>
        <div className="metric-card"><span>Transport</span><strong>{liveMarket?.transport ?? "—"}</strong></div>
        <div className="metric-card"><span>Authenticated</span><strong>{liveMarket?.authenticated ? "YES" : "NO"}</strong></div>
        <div className="metric-card"><span>Subscriptions</span><strong>{liveMarket?.subscription_count ?? 0}</strong></div>
        <div className="metric-card"><span>Feed Age</span><strong>{liveMarket?.feed_age_sec ?? "—"} sec</strong></div>
        <div className="metric-card"><span>Orders</span><strong>DISABLED</strong></div>
      </div>
      {(liveMarket?.blockers ?? []).map((x:string)=><p key={x}>⛔ {x}</p>)}
      {(liveMarket?.warnings ?? []).map((x:string)=><p key={x}>⚠ {x}</p>)}
      <p style={{fontSize:12,opacity:.7}}>Spot source: {liveSources?.market_fields?.nifty_spot ?? "—"} · PCR source: {liveSources?.market_fields?.pcr ?? "—"}</p>
    </section>
    <section className="panel"><div className="panel-heading"><div><h3>V7 Real-Time Feed</h3><p>KiteTicker ticks, streamed NIFTY candles and completed-candle technical indicators.</p></div><span className={`status-chip ${realtimeFeed?.connected ? "positive" : "negative"}`}>{realtimeFeed?.connected ? "WEBSOCKET LIVE" : (realtimeFeed?.transport ?? "WAITING")}</span></div>
      <div className="metric-grid">
        <div className="metric-card"><span>NIFTY Tick</span><strong>{realtimeFeed?.nifty_spot ?? "UNAVAILABLE"}</strong></div>
        <div className="metric-card"><span>India VIX Tick</span><strong>{realtimeFeed?.india_vix ?? "UNAVAILABLE"}</strong></div>
        <div className="metric-card"><span>Feed Age</span><strong>{realtimeFeed?.feed_age_sec ?? "—"} sec</strong></div>
        <div className="metric-card"><span>Accepted Ticks</span><strong>{realtimeFeed?.accepted_ticks ?? 0}</strong></div>
        <div className="metric-card"><span>3m Candles</span><strong>{realtimeFeed?.candle_counts?.["3m"] ?? 0}</strong></div>
        <div className="metric-card"><span>Indicator Source</span><strong>{realtimeIndicators?.source ?? "—"}</strong></div>
      </div>
      <p style={{fontSize:12,opacity:.7}}>EMA20 {realtimeIndicators?.indicators?.ema20 ?? "—"} · EMA50 {realtimeIndicators?.indicators?.ema50 ?? "—"} · RSI {realtimeIndicators?.indicators?.rsi14 ?? "—"} · ATR {realtimeIndicators?.indicators?.atr14 ?? "—"} · ADX {realtimeIndicators?.indicators?.adx14 ?? "—"}</p>
      <p style={{fontSize:12,opacity:.7}}>Live broker orders remain disabled. During stream warm-up, indicators explicitly use completed Zerodha OHLC rather than synthetic candles.</p>
    </section>
    <section className="panel"><div className="panel-heading"><div><h2>Live Market Intelligence</h2><p>Broker snapshot quality, OI structure and execution-safety gate.</p></div><span className={`status-chip ${data.status === "READY" ? "positive" : "negative"}`}>{data.status}</span></div>
      <div className="metric-grid">{metrics.map(([k,v]) => <div className="metric-card" key={String(k)}><span>{k}</span><strong>{String(v)}</strong></div>)}</div>
    </section>
    <section className="panel"><div className="panel-heading"><div><h3>Feed & Market Safety</h3><p>Exchange timestamp, trading-session, authentication and fallback checks.</p></div><span className={`status-chip ${safety?.status === "READY" ? "positive" : "negative"}`}>{safety?.status ?? "LOADING"}</span></div>
      <div className="metric-grid">
        <div className="metric-card"><span>Safety Score</span><strong>{safety?.score ?? "—"}/100</strong></div>
        <div className="metric-card"><span>Market Session</span><strong>{safety?.market_clock?.session ?? "—"}</strong></div>
        <div className="metric-card"><span>Feed Age</span><strong>{safety?.market_age_sec ?? "—"} sec</strong></div>
        <div className="metric-card"><span>Feed Mode</span><strong>{safety?.websocket_active ? "WEBSOCKET" : "REST FALLBACK"}</strong></div>
      </div>
      {(safety?.blockers ?? []).map((x:string) => <p key={x}>⛔ {x}</p>)}
      {(safety?.warnings ?? []).map((x:string) => <p key={x}>⚠ {x}</p>)}
      {safety?.status === "READY" ? <p>✓ Feed is safe for decision support. Live broker orders remain disabled.</p> : null}
    </section>
    <section className="panel"><div className="panel-heading"><div><h3>Feed Alert Center</h3><p>Token health, stale data, disconnections and fallback alerts.</p></div><span className={`status-chip ${feedAlerts?.status === "READY" ? "positive" : "negative"}`}>{feedAlerts?.status ?? "LOADING"}</span></div>
      <div className="metric-grid">
        <div className="metric-card"><span>Critical</span><strong>{feedAlerts?.critical_count ?? "—"}</strong></div>
        <div className="metric-card"><span>Warnings</span><strong>{feedAlerts?.warning_count ?? "—"}</strong></div>
        <div className="metric-card"><span>Token Check Age</span><strong>{feedAlerts?.token_check_age_sec ?? "—"} sec</strong></div>
        <div className="metric-card"><span>Action</span><strong>{feedAlerts?.recommended_action ?? "—"}</strong></div>
      </div>
      {(feedAlerts?.alerts ?? []).map((x:any) => <p key={x.code}>{x.severity === "CRITICAL" ? "⛔" : "⚠"} <strong>{x.code}</strong> — {x.message} · {x.action}</p>)}
      {feedAlerts?.status === "READY" ? <p>✓ No active feed alerts.</p> : null}
    </section>

    <section className="panel"><div className="panel-heading"><div><h3>Live Session Validation</h3><p>Persistent market-hours evidence for feed quality, WebSocket reliability and paper-readiness.</p></div><span className={`status-chip ${liveSession?.status === "READY" ? "positive" : "negative"}`}>{liveSession?.status ?? "LOADING"}</span></div>
      <div className="metric-grid">
        <div className="metric-card"><span>Samples</span><strong>{liveSession?.samples ?? 0}</strong></div>
        <div className="metric-card"><span>Ready Ratio</span><strong>{liveSession ? `${Math.round((liveSession.ready_ratio ?? 0)*100)}%` : "—"}</strong></div>
        <div className="metric-card"><span>WebSocket Ratio</span><strong>{liveSession ? `${Math.round((liveSession.websocket_ratio ?? 0)*100)}%` : "—"}</strong></div>
        <div className="metric-card"><span>Average Feed Age</span><strong>{liveSession?.average_feed_age_sec ?? "—"} sec</strong></div>
      </div>
      {(liveSession?.blockers ?? []).map((x:string)=><p key={x}>⛔ {x}</p>)}
      {(liveSession?.warnings ?? []).map((x:string)=><p key={x}>⚠ {x}</p>)}
      <div className="metric-grid">
        <div className="metric-card"><span>Auto Recorder</span><strong>{liveSessionRecorder?.enabled ? "ENABLED" : "DISABLED"}</strong></div>
        <div className="metric-card"><span>Recorded</span><strong>{liveSessionRecorder?.recorded ?? 0}</strong></div>
        <div className="metric-card"><span>Sessions</span><strong>{liveSessionSessions?.session_count ?? 0}</strong></div>
        <div className="metric-card"><span>Ready Sessions</span><strong>{liveSessionSessions?.ready_session_count ?? 0}</strong></div>
      </div>
      <button type="button" onClick={async()=>{try{const token=sessionStorage.getItem("admin_token")||"";await api.recordLiveSessionNow(token);setLiveSession(await api.getLiveSessionValidation());setLiveSessionSessions(await api.getLiveSessionSessions());setLiveSessionRecorder(await api.getLiveSessionRecorder());}catch(e){setPrepareMessage(String(e));}}}>Record Validation Sample Now</button>
      {(liveSessionSessions?.sessions ?? []).slice(-3).map((x:any)=><p key={x.trading_day}>• {x.trading_day} — {x.status} · ready {(Number(x.ready_ratio||0)*100).toFixed(1)}% · WS {(Number(x.websocket_ratio||0)*100).toFixed(1)}%</p>)}
      <p style={{fontSize:12,opacity:.7}}>Automatic evidence collection runs in the background and produces restart-safe multi-session reports. Live broker orders remain disabled.</p>
    </section>
    <section className="panel"><div className="panel-heading"><div><h3>Multi-Session Certification</h3><p>Configurable cross-session evidence gate before any controlled execution pilot is considered.</p></div><span className={`status-chip ${liveSessionCertification?.status === "CERTIFIED" ? "positive" : "negative"}`}>{liveSessionCertification?.status ?? "LOADING"}</span></div>
      <div className="metric-grid">
        <div className="metric-card"><span>Sessions</span><strong>{liveSessionCertification?.session_count ?? 0}</strong></div>
        <div className="metric-card"><span>Ready Sessions</span><strong>{liveSessionCertification?.ready_session_count ?? 0}</strong></div>
        <div className="metric-card"><span>Ready Ratio</span><strong>{liveSessionCertification ? `${Math.round((liveSessionCertification.ready_session_ratio ?? 0)*100)}%` : "—"}</strong></div>
        <div className="metric-card"><span>Average WS Ratio</span><strong>{liveSessionCertification ? `${Math.round((liveSessionCertification.average_websocket_ratio ?? 0)*100)}%` : "—"}</strong></div>
      </div>
      {(liveSessionCertification?.blockers ?? []).map((x:string)=><p key={x}>⛔ {x}</p>)}
      {(liveSessionCertification?.warnings ?? []).map((x:string)=><p key={x}>⚠ {x}</p>)}
      <button type="button" onClick={async()=>{try{const token=sessionStorage.getItem("admin_token")||"";await api.notifyLiveSessionCertification(token);setPrepareMessage("Certification report queued in notification outbox");}catch(e){setPrepareMessage(String(e));}}}>Queue Certification Report</button>
      <div className="metric-grid">
        <div className="metric-card"><span>Expiry Groups</span><strong>{certificationBreakdown?.by_expiry?.length ?? 0}</strong></div>
        <div className="metric-card"><span>Regime Groups</span><strong>{certificationBreakdown?.by_market_regime?.length ?? 0}</strong></div>
        <div className="metric-card"><span>EOD Scheduler</span><strong>{certificationEod?.enabled ? certificationEod.configured_time : "DISABLED"}</strong></div>
        <div className="metric-card"><span>EOD Reports</span><strong>{certificationEod?.generated ?? 0}</strong></div>
      </div>
      <button type="button" onClick={async()=>{try{const token=sessionStorage.getItem("admin_token")||"";const r=await api.runLiveSessionCertificationEodScheduler(true,token);setCertificationEod(r);setPrepareMessage("End-of-day certification report queued");}catch(e){setPrepareMessage(String(e));}}}>Run EOD Certification Now</button>
      {(certificationBreakdown?.by_expiry ?? []).slice(0,3).map((x:any)=><p key={x.expiry}>• Expiry {x.expiry} — {x.status} · ready {(Number(x.ready_ratio||0)*100).toFixed(1)}%</p>)}
      {(certificationBreakdown?.by_market_regime ?? []).slice(0,3).map((x:any)=><p key={x.market_regime}>• Regime {x.market_regime} — {x.status} · ready {(Number(x.ready_ratio||0)*100).toFixed(1)}%</p>)}
      <p style={{fontSize:12,opacity:.7}}>Certification covers market-data reliability only. Live broker orders remain disabled.</p>
    </section>
    <section className="panel"><div className="panel-heading"><div><h3>Integration Readiness</h3><p>Notification delivery, NSE holiday calendar and broker Greeks validation foundation.</p></div><span className={`status-chip ${integration?.status === "READY" ? "positive" : "negative"}`}>{integration?.status ?? "LOADING"}</span></div>
      <div className="metric-grid">
        <div className="metric-card"><span>Outbox Pending</span><strong>{outbox?.status?.pending ?? 0}</strong></div>
        <div className="metric-card"><span>Delivery</span><strong>{integration?.notification_delivery?.delivery_enabled ? "ENABLED" : "DISABLED"}</strong></div>
        <div className="metric-card"><span>WhatsApp</span><strong>{integration?.notification_delivery?.whatsapp_enabled ? "ENABLED" : "DISABLED"}</strong></div>
        <div className="metric-card"><span>Category Routes</span><strong>{Object.values(
  (integration?.notification_delivery?.category_routing ?? {}) as Record<string, number>
).reduce( (a, b) => Number(a) + Number(b), 0)}</strong></div>
        <div className="metric-card"><span>Holiday Count</span><strong>{integration?.market_calendar?.count ?? 0}</strong></div>
        <div className="metric-card"><span>Next Holiday</span><strong>{integration?.market_calendar?.next_holiday?.date ?? "—"}</strong></div>
        <div className="metric-card"><span>Greeks Samples</span><strong>{greeksSession?.samples ?? 0}</strong></div>
        <div className="metric-card"><span>Greeks Match</span><strong>{greeksSession?.metric_match_rate_pct ?? "—"}%</strong></div>
      </div>
      <div className="metric-grid">
        <div className="metric-card"><span>Scheduler Runs</span><strong>{notificationScheduler?.runs ?? 0}</strong></div>
        <div className="metric-card"><span>Delivered</span><strong>{notificationScheduler?.delivered ?? 0}</strong></div>
        <div className="metric-card"><span>Escalated</span><strong>{notificationScheduler?.escalated ?? 0}</strong></div>
        <div className="metric-card"><span>Last Run</span><strong>{notificationScheduler?.last_run_at ? new Date(notificationScheduler.last_run_at).toLocaleTimeString() : "—"}</strong></div>
      </div>
      <button type="button" onClick={async()=>{try{const token=sessionStorage.getItem("admin_token")||"";const r=await api.runNotificationScheduler(token);setNotificationScheduler(r);setOutbox(await api.getNotificationOutbox());}catch(e){setPrepareMessage(String(e));}}}>Run Notification Scheduler</button>
      <button type="button" onClick={async()=>{try{const token=sessionStorage.getItem("admin_token")||"";const r=await api.syncMarketHolidays(null,null,true,token);setPrepareMessage(`Holiday sync completed: ${r.count ?? 0} dates`);setIntegration(await api.getIntegrationReadiness());}catch(e){setPrepareMessage(String(e));}}}>Sync Holiday Calendar</button>
      {(integration?.blockers ?? []).map((x:string)=><p key={x}>⛔ {x}</p>)}
      <p style={{fontSize:12,opacity:.7}}>Category-specific email and optional WhatsApp delivery are disabled until configured by an admin. Live broker orders remain disabled.</p>
    </section>

    <section className="panel"><div className="panel-heading"><div><h3>Daily Operational Digest</h3><p>Consolidated notification, calendar, scheduler and Greeks-readiness report.</p></div><span className={`status-chip ${operationalDigest?.latest?.status === "READY" ? "positive" : "negative"}`}>{operationalDigest?.latest?.status ?? "NOT GENERATED"}</span></div>
      <div className="metric-grid">
        <div className="metric-card"><span>Digest History</span><strong>{operationalDigest?.history_count ?? 0}</strong></div>
        <div className="metric-card"><span>Pending</span><strong>{operationalDigest?.latest?.notification_counts?.PENDING ?? 0}</strong></div>
        <div className="metric-card"><span>Failed</span><strong>{operationalDigest?.latest?.notification_counts?.FAILED ?? 0}</strong></div>
        <div className="metric-card"><span>Greeks Samples</span><strong>{operationalDigest?.latest?.greeks_validation?.samples ?? 0}</strong></div>
        <div className="metric-card"><span>Auto Schedule</span><strong>{digestScheduler?.enabled ? `${digestScheduler.configured_time} ${digestScheduler.timezone}` : "DISABLED"}</strong></div>
        <div className="metric-card"><span>Next Digest</span><strong>{digestScheduler?.next_run_at ? new Date(digestScheduler.next_run_at).toLocaleString() : "—"}</strong></div>
      </div>
      <button type="button" onClick={async()=>{try{const token=sessionStorage.getItem("admin_token")||"";const r=await api.generateOperationalDigest(true,token);setOperationalDigest({history_count:(operationalDigest?.history_count ?? 0)+1,latest:r});setDigestHistory((await api.getOperationalDigestHistory()).items ?? []);}catch(e){setPrepareMessage(String(e));}}}>Generate & Queue Digest</button>
      <button type="button" onClick={async()=>{try{const token=sessionStorage.getItem("admin_token")||"";const r=await api.runOperationalDigestScheduler(true,token);setDigestScheduler(r);setOperationalDigest(await api.getOperationalDigest());setDigestHistory((await api.getOperationalDigestHistory()).items ?? []);}catch(e){setPrepareMessage(String(e));}}}>Run Scheduled Digest Now</button>
      {(operationalDigest?.latest?.blockers ?? []).map((x:string)=><p key={x}>⛔ {x}</p>)}
      {(operationalDigest?.latest?.warnings ?? []).map((x:string)=><p key={x}>⚠ {x}</p>)}
      {digestHistory.slice(0,3).map((x:any)=><p key={x.generated_at}>• {new Date(x.generated_at).toLocaleString()} — {x.status} · {x.recommended_action}</p>)}
      <p style={{fontSize:12,opacity:.7}}>The automatic scheduler creates at most one digest per local trading day and catches up after a restart. Live broker orders remain disabled.</p>
    </section>
    <section className="panel"><div className="panel-heading"><div><h3>Runtime Maintenance</h3><p>Periodic subscription refresh, expiry rollover, market-aware heartbeat and token notifications.</p></div><span className={`status-chip ${maintenance?.last_error ? "negative" : "positive"}`}>{maintenance?.last_error ? "DEGRADED" : "READY"}</span></div>
      <div className="metric-grid">
        <div className="metric-card"><span>Subscription Syncs</span><strong>{maintenance?.sync_count ?? 0}</strong></div>
        <div className="metric-card"><span>Expiry Rollovers</span><strong>{maintenance?.rollover_count ?? 0}</strong></div>
        <div className="metric-card"><span>Active Expiry</span><strong>{maintenance?.last_expiry ?? "—"}</strong></div>
        <div className="metric-card"><span>Notifications</span><strong>{maintenance?.notification_count ?? 0}</strong></div>
        <div className="metric-card"><span>Market Session</span><strong>{maintenance?.market_clock?.session ?? "—"}</strong></div>
        <div className="metric-card"><span>Last Error</span><strong>{maintenance?.last_error ?? "NONE"}</strong></div>
      </div>
      <button type="button" onClick={async()=>{try{const token=sessionStorage.getItem("admin_token")||"";const r=await api.runRuntimeMaintenance(token);setMaintenance(r);}catch(e){setPrepareMessage(String(e));}}}>Run Maintenance Now</button>
      {(notifications ?? []).slice(0,5).map((n:any)=><p key={`${n.timestamp}-${n.code}`}>{n.severity === "CRITICAL" ? "⛔" : n.severity === "WARNING" ? "⚠" : "✓"} <strong>{n.code}</strong> — {n.message}</p>)}
      <p style={{fontSize:12,opacity:.7}}>Outside market hours, an idle socket does not trigger false heartbeat failures. Live broker orders remain disabled.</p>
    </section>
    <section className="panel"><div className="panel-heading"><div><h3>Actual KiteTicker Runtime</h3><p>Network transport, heartbeat monitoring, exponential reconnect and dynamic option subscriptions.</p></div><span className={`status-chip ${kiteRuntime?.connected ? "positive" : "negative"}`}>{kiteRuntime?.transport ?? "LOADING"}</span></div>
      <div className="metric-grid">
        <div className="metric-card"><span>Running</span><strong>{kiteRuntime?.running ? "YES" : "NO"}</strong></div>
        <div className="metric-card"><span>Contracts</span><strong>{kiteRuntime?.subscription_count ?? 0}</strong></div>
        <div className="metric-card"><span>Heartbeat Age</span><strong>{kiteRuntime?.heartbeat_age_sec ?? "—"} sec</strong></div>
        <div className="metric-card"><span>Reconnect Delay</span><strong>{kiteRuntime?.reconnect_delay_sec ?? 0} sec</strong></div>
        <div className="metric-card"><span>Reconnect Attempts</span><strong>{kiteRuntime?.reconnect_attempts ?? 0}</strong></div>
        <div className="metric-card"><span>Last Error</span><strong>{kiteRuntime?.last_error ?? "NONE"}</strong></div>
      </div>
      <button type="button" onClick={async()=>{try{const token=sessionStorage.getItem("admin_token")||"";const r=await api.syncKiteRuntimeSubscriptions(token);setKiteRuntime(r);}catch(e){setPrepareMessage(String(e));}}}>Sync Active Expiry Subscriptions</button>
      <p style={{fontSize:12,opacity:.7}}>This runtime automatically falls back to REST when disconnected. It transports market data only; live broker orders remain disabled.</p>
    </section>
    <section className="panel"><div className="panel-heading"><div><h3>Kite Stream Manager</h3><p>Subscription state, reconnect tracking, batching and backpressure protection for KiteTicker integration.</p></div><span className={`status-chip ${kiteStream?.connected ? "positive" : "negative"}`}>{kiteStream?.mode ?? "LOADING"}</span></div>
      <div className="metric-grid">
        <div className="metric-card"><span>Subscriptions</span><strong>{kiteStream?.subscription_count ?? 0}</strong></div>
        <div className="metric-card"><span>Reconnects</span><strong>{kiteStream?.reconnect_attempts ?? 0}</strong></div>
        <div className="metric-card"><span>Batches</span><strong>{kiteStream?.received_batches ?? 0}</strong></div>
        <div className="metric-card"><span>Accepted</span><strong>{kiteStream?.accepted_ticks ?? 0}</strong></div>
        <div className="metric-card"><span>Ignored</span><strong>{kiteStream?.ignored_ticks ?? 0}</strong></div>
        <div className="metric-card"><span>Dropped</span><strong>{kiteStream?.dropped_ticks ?? 0}</strong></div>
      </div>
      <p style={{fontSize:12,opacity:.7}}>This layer manages market-data transport only. REST fallback remains active when WebSocket is disconnected. Live broker orders remain disabled.</p>
    </section>
    <section className="panel"><div className="panel-heading"><div><h3>Tick-to-Paper Bridge</h3><p>Deduplicates exchange ticks and routes only the matching option contract to the restart-safe paper monitor.</p></div><span className={`status-chip ${tickBridge?.last_error ? "negative" : "positive"}`}>{tickBridge?.last_error ? "DEGRADED" : "READY"}</span></div>
      <div className="metric-grid">
        <div className="metric-card"><span>Accepted Ticks</span><strong>{tickBridge?.accepted ?? 0}</strong></div>
        <div className="metric-card"><span>Duplicates</span><strong>{tickBridge?.duplicates ?? 0}</strong></div>
        <div className="metric-card"><span>Out of Order</span><strong>{tickBridge?.out_of_order ?? 0}</strong></div>
        <div className="metric-card"><span>Paper Routes</span><strong>{tickBridge?.routed_to_paper ?? 0}</strong></div>
        <div className="metric-card"><span>Last Price</span><strong>{tickBridge?.last_price ?? "—"}</strong></div>
        <div className="metric-card"><span>Last Action</span><strong>{tickBridge?.last_action ?? "—"}</strong></div>
      </div>
      <p style={{fontSize:12,opacity:.7}}>Execution mode: PAPER_TICK_MONITOR_ONLY. Duplicate and out-of-order ticks are ignored. Live broker orders remain disabled.</p>
    </section>
    <section className="panel"><div className="panel-heading"><div><h3>Intraday OI & PCR Trend</h3><p>{trend?.samples ?? 0} persisted samples · {trend?.trend ?? "NO_DATA"}</p></div></div>
      <div className="metric-grid">
        <div className="metric-card"><span>PCR Change</span><strong>{trend?.pcr_change ?? "—"}</strong></div>
        <div className="metric-card"><span>CE OI Change</span><strong>{trend?.ce_oi_change ?? "—"}</strong></div>
        <div className="metric-card"><span>PE OI Change</span><strong>{trend?.pe_oi_change ?? "—"}</strong></div>
      </div>
      <div style={{display:"flex",alignItems:"end",gap:4,height:150,marginTop:16,overflowX:"auto"}}>
        {points.map((p,i) => <div key={`${p.captured_at}-${i}`} title={`${p.captured_at} PCR ${p.pcr_oi ?? "—"}`} style={{display:"flex",gap:1,alignItems:"end",minWidth:8,height:"100%"}}>
          <div style={{width:3,height:`${Math.max(2,(p.total_ce_oi/maxOi)*100)}%`,background:"#f87171"}} />
          <div style={{width:3,height:`${Math.max(2,(p.total_pe_oi/maxOi)*100)}%`,background:"#4ade80"}} />
        </div>)}
      </div>
      <p style={{fontSize:12,opacity:.7}}>Red = CE OI · Green = PE OI. History is stored in SQLite and survives restarts.</p>
    </section>
    <section className="panel"><div className="panel-heading"><div><h3>Paper Setup Bridge</h3><p>Creates a draft setup only after live-data and OI/PCR trend validation. It never executes a trade.</p></div><span className={`status-chip ${preview?.status === "READY_FOR_HUMAN_REVIEW" ? "positive" : "negative"}`}>{preview?.status ?? "LOADING"}</span></div>
      {preview?.candidate ? <div className="metric-grid">
        <div className="metric-card"><span>Direction</span><strong>{preview.candidate.decision}</strong></div>
        <div className="metric-card"><span>Contract</span><strong>{preview.candidate.strike} {preview.candidate.option_type}</strong></div>
        <div className="metric-card"><span>Entry</span><strong>₹{preview.candidate.entry_low}–₹{preview.candidate.entry_high}</strong></div>
        <div className="metric-card"><span>SL / T1 / T2</span><strong>₹{preview.candidate.stop_loss} / ₹{preview.candidate.target_1} / ₹{preview.candidate.target_2}</strong></div>
      </div> : <>{(preview?.blockers ?? []).map((x:string) => <p key={x}>⛔ {x}</p>)}</>}
      <button type="button" disabled={preview?.status !== "READY_FOR_HUMAN_REVIEW"} onClick={async()=>{try{const token=sessionStorage.getItem("admin_token")||"";const r=await api.prepareLivePaperSetup(token);setPrepareMessage(r.created?`Draft setup #${r.setup?.id} created for human review`:`${r.reason}: existing setup retained`);}catch(e){setPrepareMessage(String(e));}}}>Prepare Draft Paper Setup</button>
      {prepareMessage ? <p>{prepareMessage}</p> : null}
      <p style={{fontSize:12,opacity:.7}}>Human approval is still required in Trading Workspace before paper execution. Live broker orders are disabled.</p>
    </section>
    <section className="panel"><h3>Decision Gate</h3><p><strong>{data.recommended_action}</strong> · feed age {data.age_sec ?? "—"} sec · expiry {data.expiry ?? "—"}</p>
      {data.blockers.map(x => <p key={x}>⛔ {x}</p>)}{data.warnings.map(x => <p key={x}>⚠ {x}</p>)}
      {!data.blockers.length && !data.warnings.length ? <p>✓ Snapshot passed all quality checks.</p> : null}
    </section>
  </div>;
}
