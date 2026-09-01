import type { ReactNode } from "react";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";

export type AppPage = "overview" | "trading" | "portfolio" | "risk" | "analytics" | "replay" | "agents" | "command" | "flow" | "strategy" | "operations" | "production" | "learning" | "certification" | "resilience" | "scenarios" | "live-intelligence" | "settings";

interface AppLayoutProps {
  activePage: AppPage;
  onNavigate: (page: AppPage) => void;
  children: ReactNode;
}

export function AppLayout({ activePage, onNavigate, children }: AppLayoutProps) {
  return (
    <div className="app-shell">
      <Sidebar activePage={activePage} onNavigate={onNavigate} />
      <div className="app-main">
        <Header activePage={activePage} />
        <main className="app-content">{children}</main>
      </div>
    </div>
  );
}
