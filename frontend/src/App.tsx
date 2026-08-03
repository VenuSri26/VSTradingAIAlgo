import { useMemo, useState } from "react";
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

export default function App() {
  const [page, setPage] = useState<AppPage>("overview");

  const content = useMemo(() => {
    switch (page) {
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
    <AppLayout activePage={page} onNavigate={setPage}>
      {content}
    </AppLayout>
  );
}
