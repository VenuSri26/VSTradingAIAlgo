import { useEffect, useMemo, useState } from "react";
import { AppLayout, type AppPage } from "./layout/AppLayout";
import Dashboard from "./Dashboard";
import { TradingWorkspace } from "./pages/TradingWorkspace";
import { PortfolioPage } from "./pages/PortfolioPage";
import { RiskPage } from "./pages/RiskPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { OperationsPage } from "./pages/OperationsPage";
import { ReplayPage } from "./pages/ReplayPage";
import { SettingsPage } from "./pages/SettingsPage";
import { AgentsPage } from "./pages/AgentsPage";
import { StrategyLabPage } from "./pages/StrategyLabPage";
import { ProductionPage } from "./pages/ProductionPage";
import { InstitutionalFlowPage } from "./pages/InstitutionalFlowPage";
import { AICommandCenterPage } from "./pages/AICommandCenterPage";
import { LearningPage } from "./pages/LearningPage";
import { ProductionCandidatePage } from "./pages/ProductionCandidatePage";
import { ResiliencePage } from "./pages/ResiliencePage";
import { TestScenariosPage } from "./pages/TestScenariosPage";
import { LiveIntelligencePage } from "./pages/LiveIntelligencePage";
import { PaperAutomationPage } from "./pages/PaperAutomationPage";

export default function App() {
  const validPages = useMemo(() => new Set<AppPage>([
    "overview", "auto-paper", "trading", "portfolio", "risk", "analytics",
    "replay", "agents", "command", "flow", "strategy", "operations",
    "production", "learning", "certification", "resilience", "scenarios",
    "live-intelligence", "settings",
  ]), []);
  const pageFromPath = () => {
    const candidate = window.location.pathname.replace(/^\/+|\/+$/g, "") || "overview";
    return validPages.has(candidate as AppPage) ? candidate as AppPage : "overview";
  };
  const [page, setPage] = useState<AppPage>(pageFromPath);

  useEffect(() => {
    const onPopState = () => setPage(pageFromPath());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [validPages]);

  function navigate(nextPage: AppPage) {
    setPage(nextPage);
    const nextPath = nextPage === "overview" ? "/" : `/${nextPage}`;
    if (window.location.pathname !== nextPath) window.history.pushState({}, "", nextPath);
  }

  const content = useMemo(() => {
    switch (page) {
      case "auto-paper":
        return <PaperAutomationPage />;
      case "trading":
        return <TradingWorkspace />;
      case "portfolio":
        return <PortfolioPage />;
      case "risk":
        return <RiskPage />;
      case "analytics":
        return <AnalyticsPage />;
      case "replay":
        return <ReplayPage />;
      case "agents":
        return <AgentsPage />;
      case "command":
        return <AICommandCenterPage />;
      case "flow":
        return <InstitutionalFlowPage />;
      case "strategy":
        return <StrategyLabPage />;
      case "learning":
        return <LearningPage />;
      case "certification":
        return <ProductionCandidatePage />;
      case "resilience":
        return <ResiliencePage />;
      case "scenarios":
        return <TestScenariosPage />;
      case "live-intelligence":
        return <LiveIntelligencePage />;
      case "operations":
        return <OperationsPage />;
      case "production":
        return <ProductionPage />;
      case "settings":
        return <SettingsPage />;
      default:
        return <Dashboard />;
    }
  }, [page]);

  return (
    <AppLayout activePage={page} onNavigate={navigate}>
      {content}
    </AppLayout>
  );
}
