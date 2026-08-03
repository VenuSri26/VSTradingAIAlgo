import { useEffect, useMemo, useState } from "react";
import { api } from "../services/api";
import type { OperationalAlert, PaperTrade, SystemMetrics, TradeSetup, ZerodhaHealth } from "../types/operations";

const card: React.CSSProperties = {background:"#111118",border:"1px solid #22222c",borderRadius:8,padding:16};
const btn: React.CSSProperties = {border:0,borderRadius:6,padding:"8px 11px",cursor:"pointer",fontWeight:700};
const input: React.CSSProperties = {background:"#0a0a0f",color:"#fff",border:"1px solid #33333e",borderRadius:6,padding:8,width:"100%",boxSizing:"border-box"};
const muted="#8a8a96", green="#4ade80", red="#f87171", amber="#fbbf24", purple="#7c6ff7";

export function OperationsPanel() {
  const [metrics,setMetrics]=useState<SystemMetrics|null>(null), [alerts,setAlerts]=useState<OperationalAlert[]>([]);
  const [setups,setSetups]=useState<TradeSetup[]>([]), [trades,setTrades]=useState<PaperTrade[]>([]);
  const [health,setHealth]=useState<ZerodhaHealth|null>(null), [version,setVersion]=useState("—");
  const [token,setToken]=useState(()=>sessionStorage.getItem("vst_admin_token")??"");
  const [entry,setEntry]=useState(""), [qty,setQty]=useState(""), [monitor,setMonitor]=useState("");
  const [message,setMessage]=useState(""), [busy,setBusy]=useState(false);
  const openTrade=useMemo(()=>trades.find(t=>t.status==="OPEN"),[trades]);
  async function refresh(){
    const results=await Promise.allSettled([api.getMetrics(),api.getAlerts(),api.getSetups(),api.getPaperTrades(),api.getZerodhaHealth(),api.getVersion()]);
    if(results[0].status==="fulfilled")setMetrics(results[0].value);
    if(results[1].status==="fulfilled")setAlerts(results[1].value.alerts);
    if(results[2].status==="fulfilled")setSetups(results[2].value.setups);
    if(results[3].status==="fulfilled")setTrades(results[3].value.trades);
    if(results[4].status==="fulfilled")setHealth(results[4].value);
    if(results[5].status==="fulfilled")setVersion(results[5].value.version);
  }
  useEffect(()=>{refresh();const id=setInterval(refresh,10000);return()=>clearInterval(id)},[]);
  function saveToken(v:string){setToken(v);sessionStorage.setItem("vst_admin_token",v)}
  async function act(run:()=>Promise<unknown>){if(!token){setMessage("Enter ADMIN_TOKEN for protected paper actions.");return;}setBusy(true);try{await run();setMessage("Action completed successfully.");await refresh();}catch(e){setMessage(e instanceof Error?e.message:String(e));}finally{setBusy(false)}}
  return <div style={{display:"grid",gap:12}}>
    <div style={{...card,borderColor:purple}}>
      <div style={{display:"flex",justifyContent:"space-between",gap:10,flexWrap:"wrap"}}><b>OPERATIONS CONTROL</b><span style={{color:muted}}>v{version} · Zerodha {health?.connected?"CONNECTED":"CHECK"} · {health?.mode??"—"}</span></div>
      <div style={{marginTop:10,display:"grid",gridTemplateColumns:"minmax(220px,1fr) auto",gap:8}}><input type="password" placeholder="ADMIN_TOKEN (stored only in this browser session)" value={token} onChange={e=>saveToken(e.target.value)} style={input}/><button style={{...btn,background:"#252533",color:"#fff"}} onClick={refresh}>Refresh</button></div>
      {message&&<div style={{marginTop:8,color:message.includes("success")?green:amber,fontSize:13}}>{message}</div>}
    </div>
    <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(180px,1fr))",gap:12}}>
      {[['Pipeline runs',metrics?.pipeline_runs],['Success',metrics?`${metrics.pipeline_success_rate}%`:null],['Avg latency',metrics?`${metrics.pipeline_avg_duration_ms} ms`:null],['Stale events',metrics?.stale_data_events],['Active alerts',metrics?.active_alerts]].map(([l,v])=><div style={card} key={String(l)}><div style={{fontSize:11,color:muted}}>{l}</div><div style={{fontSize:24,fontWeight:700,marginTop:4}}>{v??'—'}</div></div>)}
    </div>
    <div style={{display:"grid",gridTemplateColumns:"minmax(0,2fr) minmax(280px,1fr)",gap:12}}>
      <div style={card}><b>TRADE SETUPS</b><div style={{marginTop:10,overflowX:"auto"}}><table style={{width:"100%",borderCollapse:"collapse",fontSize:12}}><thead><tr>{['ID','Decision','Grade','Strike','Entry','Status','Actions'].map(x=><th key={x} style={{textAlign:'left',padding:7,color:muted}}>{x}</th>)}</tr></thead><tbody>{setups.slice(0,10).map(s=><tr key={s.id} style={{borderTop:"1px solid #22222c"}}><td style={{padding:7}}>{s.id}</td><td>{s.decision}</td><td>{s.grade}</td><td>{s.option_type} {s.strike}</td><td>{s.entry_low}–{s.entry_high}</td><td style={{color:s.status==='APPROVED'?green:s.status==='REJECTED'?red:amber}}>{s.status}</td><td style={{padding:7,whiteSpace:'nowrap'}}>{s.status==='GENERATED'&&<><button disabled={busy} style={{...btn,background:green,marginRight:5}} onClick={()=>act(()=>api.reviewSetup(s.id,'APPROVED','Approved from operations dashboard',token))}>Approve</button><button disabled={busy} style={{...btn,background:red}} onClick={()=>act(()=>api.reviewSetup(s.id,'REJECTED','Rejected from operations dashboard',token))}>Reject</button></>}{s.status==='APPROVED'&&<button disabled={busy} style={{...btn,background:purple,color:'#fff'}} onClick={()=>{setEntry(String(s.entry_low??''));setMessage(`Setup ${s.id} selected. Enter execution price below.`)}}>Select</button>}</td></tr>)}</tbody></table></div></div>
      <div style={card}><b>RECENT ALERTS</b>{alerts.length===0?<div style={{color:green,marginTop:10}}>No operational alerts.</div>:alerts.map((a,i)=><div key={i} style={{borderTop:i?'1px solid #22222c':'none',padding:'9px 0'}}><div style={{color:a.severity==='ERROR'?red:amber,fontWeight:700,fontSize:12}}>{a.code}</div><div style={{fontSize:12}}>{a.message}</div></div>)}</div>
    </div>
    <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(280px,1fr))",gap:12}}>
      <div style={card}><b>PAPER EXECUTION</b><div style={{color:muted,fontSize:12,margin:'6px 0 10px'}}>Approved setups only. This never sends a Zerodha order.</div><select id="setup-select" style={input}><option value="">Select approved setup</option>{setups.filter(s=>s.status==='APPROVED').map(s=><option key={s.id} value={s.id}>#{s.id} {s.option_type} {s.strike}</option>)}</select><div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8,marginTop:8}}><input style={input} value={entry} onChange={e=>setEntry(e.target.value)} placeholder="Entry price"/><input style={input} value={qty} onChange={e=>setQty(e.target.value)} placeholder="Quantity (optional)"/></div><button disabled={busy} style={{...btn,background:purple,color:'#fff',marginTop:8,width:'100%'}} onClick={()=>{const el=document.getElementById('setup-select') as HTMLSelectElement;act(()=>api.executePaper(Number(el.value),Number(entry),qty?Number(qty):undefined,token))}}>Execute paper trade</button></div>
      <div style={card}><b>OPEN PAPER TRADE</b>{!openTrade?<div style={{color:muted,marginTop:10}}>No open paper trade.</div>:<><div style={{marginTop:8,fontSize:13,lineHeight:1.7}}>#{openTrade.id} · {openTrade.option_type} {openTrade.strike}<br/>Qty {openTrade.quantity} · Entry ₹{openTrade.entry_price}<br/>SL ₹{openTrade.stop_loss} · T1 ₹{openTrade.target_1} · T2 ₹{openTrade.target_2}</div><input style={{...input,marginTop:8}} value={monitor} onChange={e=>setMonitor(e.target.value)} placeholder="Current option price"/><div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8,marginTop:8}}><button disabled={busy} style={{...btn,background:green}} onClick={()=>act(()=>api.monitorPaper(Number(monitor),false,token))}>Update / monitor</button><button disabled={busy} style={{...btn,background:red,color:'#fff'}} onClick={()=>act(()=>api.monitorPaper(Number(monitor),true,token))}>Force EOD close</button></div></>}</div>
    </div>
  </div>
}
