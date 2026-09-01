import { useEffect, useState } from "react";
import { api } from "../services/api";

type Capabilities={version:string;mode:string;features:string[];minimum_recommended_samples:number;automatic_weight_updates:boolean;live_orders_enabled:boolean};
export function LearningPage(){
 const [data,setData]=useState<Capabilities|null>(null); const [error,setError]=useState<string|null>(null);
 useEffect(()=>{api.getLearningCapabilities().then(setData).catch(e=>setError(String(e)))},[]);
 return <section className="page-stack">
  <div className="page-card"><div className="eyebrow">V2.9 AI LEARNING</div><h2>Learning & Optimization</h2>
  <p className="muted">Evaluate paper trades, calibrate confidence, rank agents and prepare walk-forward research. Production weights remain unchanged.</p></div>
  {error?<div className="page-card danger">{error}</div>:null}
  {!data?<div className="page-card">Loading learning capabilities…</div>:<>
   <div className="metric-grid">
    <div className="page-card"><div className="eyebrow">MODE</div><h3>{data.mode}</h3></div>
    <div className="page-card"><div className="eyebrow">MINIMUM SAMPLE</div><h3>{data.minimum_recommended_samples} trades</h3></div>
    <div className="page-card"><div className="eyebrow">AUTO WEIGHTS</div><h3>{data.automatic_weight_updates?"ENABLED":"DISABLED"}</h3></div>
    <div className="page-card"><div className="eyebrow">LIVE ORDERS</div><h3>{data.live_orders_enabled?"ENABLED":"DISABLED"}</h3></div>
   </div>
   <div className="page-card"><div className="eyebrow">AVAILABLE ENGINES</div><div className="check-list">{data.features.map(x=><div key={x} className="check-row"><span>✓</span><span>{x.replace(/_/g," ")}</span></div>)}</div></div>
  </>}
 </section>
}
