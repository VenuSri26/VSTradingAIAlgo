import { useEffect, useState } from "react";
import type { AppPage } from "./AppLayout";
import { api } from "../services/api";
import type { VersionInfo } from "../types/operations";

const titles: Record<AppPage, { title: string; subtitle: string }> = {
  overview: { title: "Market Overview", subtitle: "Multi-agent Nifty50 decision support" },
  trading: { title: "Trading Workspace", subtitle: "Trade setups, execution and monitoring" },
  portfolio: { title: "Paper Portfolio", subtitle: "Open positions, journal and performance" },
  analytics: { title: "Analytics", subtitle: "Session metrics and decision quality" },
  operations: { title: "Operations Console", subtitle: "Health, alerts and protected paper controls" },
  settings: { title: "Settings", subtitle: "Runtime and safety configuration guidance" },
  risk: { title: "Risk Supervisor", subtitle: "Capital protection and execution controls" },
  replay: { title: "Decision Replay", subtitle: "Review historical AI decisions and outcomes" },
  agents: { title: "AI Agents", subtitle: "Multi-agent evidence, votes and explanations" },
  command: { title: "AI Command Center", subtitle: "Supervisor scoring, market regime and trade grading" },
  flow: { title: "Institutional Flow", subtitle: "Options, futures and FII/DII evidence quality" },
  strategy: { title: "Strategy Lab", subtitle: "Research, replay and validation workspace" },
  production: { title: "Production", subtitle: "Live-data, security and execution readiness" },
};

export function Header({ activePage }: { activePage: AppPage }) {
  const current = titles[activePage];
  const [version, setVersion] = useState<VersionInfo | null>(null);
  useEffect(() => {
    api.getVersion().then(setVersion).catch(() => undefined);
  }, []);
  return (
    <header className="top-header">
      <div><h1>{current.title}</h1><p>{current.subtitle}</p></div>
      <div className="header-badges">
        <span className="header-badge safe">HUMAN APPROVAL</span>
        <span className="header-badge">{version ? `v${version.version}` : "version loading"}</span>
        {version?.environment ? <span className="header-badge">{version.environment.toUpperCase()}</span> : null}
      </div>
    </header>
  );
}
