import { useEffect, useState } from "react";
import { PageCard } from "../components/PageCard";
import { api } from "../services/api";
import type { AICommandCenter } from "../types/operations";

function tone(score:number){ return score>=78?"positive":score<=42?"negative":""; }
export function AICommandCenterPage(){
  const [data,setData]=useState<AICommandCenter|null>(null);
  const [error,setError]=useState<string|null>(null);
  const load=()=>api.getAICommandCenter().then(v=>{setData(v);setError(null)}).catch(e=>setError(e instanceof Error?e.message:"Unable to load AI Command Center"));
  useEffect(()=>{void load(); const id=window.setInterval(()=>void load(),15000); return()=>window.clearInterval(id)},[]);
  if(error) return <PageCard title="AI Command Center"><div className="error-box">{error}</div><button className="action-button" onClick={()=>void load()}>Retry</button></PageCard>;
  if(!data) return <PageCard title="AI Command Center"><p>Loading supervisor intelligence…</p></PageCard>;
  const scores=Object.entries(data.scores);
  return <div className="page-stack">
    <PageCard title="Supervisor Decision">
      <div className="command-hero">
        <div><span>Decision</span><strong className={data.decision==="NO_TRADE"?"negative":"positive"}>{data.decision}</strong></div>
        <div><span>Grade</span><strong>{data.grade}</strong></div>
        <div><span>Overall</span><strong className={tone(data.overall_score)}>{data.overall_score.toFixed(1)}</strong></div>
        <div><span>Votes</span><strong>{data.votes.bullish}B / {data.votes.bearish}S / {data.votes.neutral}N</strong></div>
      </div>
      <p className="muted-text">Only A and A+ recommendations are surfaced. Live broker execution remains disabled.</p>
    </PageCard>
    <PageCard title="Intelligence Scores">
      <div className="score-card-grid">{scores.map(([name,score])=><div className="score-card" key={name}><span>{name}</span><strong className={tone(score)}>{score.toFixed(1)}</strong><div className="score-track"><div style={{width:`${Math.max(0,Math.min(100,score))}%`}} /></div></div>)}</div>
    </PageCard>
    <div className="two-column-grid">
      <PageCard title="Why"><ul>{data.why.map(x=><li key={x}>✓ {x}</li>)}</ul></PageCard>
      <PageCard title="Why Not / Blockers">{data.why_not.length?<ul>{data.why_not.map(x=><li key={x}>✗ {x}</li>)}</ul>:<p>No material blockers.</p>}</PageCard>
    </div>
    <div className="two-column-grid">
      <PageCard title="Market Regime"><pre className="json-view">{JSON.stringify(data.market_regime,null,2)}</pre></PageCard>
      <PageCard title="Gamma Intelligence"><pre className="json-view">{JSON.stringify(data.gamma,null,2)}</pre></PageCard>
    </div>
    <PageCard title="Smart Money Structure"><pre className="json-view">{JSON.stringify(data.structure,null,2)}</pre></PageCard>
    <PageCard title="Invalidation Conditions"><ul>{data.invalidation_conditions.map(x=><li key={x}>{x}</li>)}</ul></PageCard>
  </div>;
}
