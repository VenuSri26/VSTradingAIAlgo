import { useEffect, useState } from "react";
import { PageCard } from "../components/PageCard";
import { api } from "../services/api";
import type { SetupConfiguration } from "../types/operations";

type FormState = { minimum_confidence:number; capital:number; profit_withdrawal_threshold:number; default_stop_loss_pct:number };

export function SettingsPage() {
  const [status,setStatus]=useState<SetupConfiguration|null>(null);
  const [form,setForm]=useState<FormState>({minimum_confidence:85,capital:10000,profit_withdrawal_threshold:100000,default_stop_loss_pct:20});
  const [adminToken,setAdminToken]=useState(()=>sessionStorage.getItem("admin_token")||"");
  const [redirectUrl,setRedirectUrl]=useState("");
  const [message,setMessage]=useState("");
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);

  async function load(){
    try{
      const value=await api.getSetupStatus(); setStatus(value);
      setForm({minimum_confidence:value.minimum_confidence,capital:value.capital,
        profit_withdrawal_threshold:value.profit_withdrawal_threshold,default_stop_loss_pct:value.default_stop_loss_pct});
      setError("");
    }catch(reason){setError(reason instanceof Error?reason.message:String(reason));}
  }
  useEffect(()=>{void load();},[]);
  function update<K extends keyof FormState>(key:K,value:number){setForm(previous=>({...previous,[key]:value}));}

  async function save(){
    setBusy(true);setMessage("");setError("");
    try{const value=await api.saveSetupPreferences(form,adminToken);setStatus(value);setMessage("Paper-trading setup saved and applied immediately.");}
    catch(reason){setError(reason instanceof Error?reason.message:String(reason));}finally{setBusy(false);}
  }
  async function openLogin(){
    setBusy(true);setMessage("");setError("");
    try{const value=await api.getZerodhaLoginUrl(adminToken);window.open(value.login_url,"_blank","noopener,noreferrer");setMessage("Complete Zerodha login, then copy the full redirect URL back here.");}
    catch(reason){setError(reason instanceof Error?reason.message:String(reason));}finally{setBusy(false);}
  }
  async function refreshToken(){
    setBusy(true);setMessage("");setError("");
    try{const value=await api.refreshZerodhaFromRedirect(redirectUrl,adminToken);setMessage(`Zerodha connected for ${value.user_id}. Live orders remain disabled.`);setRedirectUrl("");await load();}
    catch(reason){setError(reason instanceof Error?reason.message:String(reason));}finally{setBusy(false);}
  }

  return <div className="page-stack">
    {error?<div className="error-box">{error}</div>:null}{message?<div className="success-box">{message}</div>:null}
    <section className="automation-banner ready"><div><span className="eyebrow">SAFE SETUP</span><h2>Paper trading configuration</h2><p>Configure the autonomous paper environment without editing server files.</p></div><div className="automation-safety"><strong>PAPER ONLY</strong><span>Live orders locked</span></div></section>

    <PageCard title="1. Administrator Access" accent="#fbbf24">
      <div className="form-grid"><label>Admin token<input type="password" autoComplete="off" value={adminToken} onChange={event=>{setAdminToken(event.target.value);sessionStorage.setItem("admin_token",event.target.value)}} placeholder="Existing ADMIN_TOKEN" /></label></div>
      <p className="muted-text">Kept only in this browser session and never displayed by the server.</p>
    </PageCard>

    <PageCard title="2. Zerodha Daily Connection" accent="#38bdf8">
      <div className="setup-mode-grid">
        <div className={`mode-card ${status?.zerodha.connected?"selected":""}`}><span>Connection</span><strong>{status?.zerodha.connected?"CONNECTED":"NOT CONNECTED"}</strong><small>{status?.zerodha.user_id??status?.zerodha.error??"Daily login required"}</small></div>
        <div className={`mode-card ${status?.https_configured?"selected":"locked"}`}><span>Credential transport</span><strong>{status?.https_configured?"HTTPS READY":"HTTPS REQUIRED"}</strong><small>Zerodha redirect URLs are rejected over plain HTTP.</small></div>
      </div>
      <div className="setup-actions"><button className="action-button" disabled={busy||!adminToken} onClick={()=>void openLogin()}>1. Open Zerodha Login</button></div>
      <div className="form-grid"><label>Full Zerodha redirect URL<input type="password" autoComplete="off" value={redirectUrl} onChange={event=>setRedirectUrl(event.target.value)} placeholder="https://your-redirect...?request_token=..." disabled={!status?.https_configured}/></label></div>
      <button className="action-button safe-action" disabled={busy||!adminToken||!redirectUrl||!status?.https_configured} onClick={()=>void refreshToken()}>2. Verify and connect</button>
      {!status?.https_configured?<p className="setup-warning">UI token entry is locked because this server currently uses HTTP. Until HTTPS is installed, continue using:<br/><code>sudo /opt/vstradingai/current/scripts/ops/vstradingai-refresh-kite-token</code></p>:null}
    </PageCard>

    <PageCard title="3. Trading Mode" accent="#a78bfa"><div className="setup-mode-grid">
      <div className="mode-card selected"><span>Selected</span><strong>PAPER TRADING</strong><small>Simulated entries, management, exits and journal.</small></div>
      <div className="mode-card locked"><span>Locked</span><strong>LIVE TRADING</strong><small>{status?.live_mode_unlock_requirement??"Requires paper certification and separate approval."}</small></div>
    </div></PageCard>

    <PageCard title="4. Paper Capital & Risk Preferences" accent="#4ade80">
      <div className="form-grid">
        <label>Minimum setup confidence (70–90%)<input type="number" min="70" max="90" value={form.minimum_confidence} onChange={event=>update("minimum_confidence",Number(event.target.value))}/><small>Only setups meeting this score can progress.</small></label>
        <label>Paper capital (₹10,000–₹2,00,000)<input type="number" min="10000" max="200000" step="1000" value={form.capital} onChange={event=>update("capital",Number(event.target.value))}/><small>Position size remains constrained by lot size and risk limits.</small></label>
        <label>Profit withdrawal alert (₹)<input type="number" min="0" max="10000000" step="1000" value={form.profit_withdrawal_threshold} onChange={event=>update("profit_withdrawal_threshold",Number(event.target.value))}/><small>Reporting alert only—no automatic fund withdrawal.</small></label>
        <label>Default stop-loss (% of option premium)<input type="number" min="1" max="50" step="0.5" value={form.default_stop_loss_pct} onChange={event=>update("default_stop_loss_pct",Number(event.target.value))}/><small>Applied to newly generated paper setups.</small></label>
      </div>
      <button className="action-button safe-action" disabled={busy||!adminToken} onClick={()=>void save()}>Save paper setup</button>
    </PageCard>

    <PageCard title="Safety Summary"><div className="settings-list">
      <div><strong>Execution mode</strong><span>PAPER_ONLY</span></div><div><strong>Live Zerodha orders</strong><span className="positive">DISABLED</span></div><div><strong>Secrets returned by API</strong><span>Never</span></div><div><strong>Preference changes</strong><span>Validated, backed up and immediately applied</span></div>
    </div></PageCard>
  </div>;
}
