import type { AppPage } from "./AppLayout";

const items: Array<{ id: AppPage; label: string; icon: string }> = [
  { id: "overview", label: "Overview", icon: "◫" },
  { id: "trading", label: "Trading", icon: "↗" },
  { id: "portfolio", label: "Portfolio", icon: "₹" },
  { id: "risk", label: "Risk", icon: "!" },
  { id: "analytics", label: "Analytics", icon: "▥" },
  { id: "replay", label: "Replay", icon: "↺" },
  { id: "agents", label: "Agents", icon: "AI" },
  { id: "command", label: "AI Command", icon: "★" },
  { id: "flow", label: "Institutional Flow", icon: "⇅" },
  { id: "strategy", label: "Strategy Lab", icon: "⌁" },
  { id: "operations", label: "Operations", icon: "⚙" },
  { id: "production", label: "Production", icon: "✓" },
  { id: "settings", label: "Settings", icon: "☰" },
];

interface SidebarProps {
  activePage: AppPage;
  onNavigate: (page: AppPage) => void;
}

export function Sidebar({ activePage, onNavigate }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="brand-block">
        <div className="brand-mark">VS</div>
        <div>
          <div className="brand-title">VSTradingAI</div>
          <div className="brand-subtitle">NIFTY OPTIONS DESK</div>
        </div>
      </div>

      <nav className="sidebar-nav" aria-label="Primary navigation">
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`nav-button ${activePage === item.id ? "active" : ""}`}
            onClick={() => onNavigate(item.id)}
          >
            <span className="nav-icon" aria-hidden="true">{item.icon}</span>
            <span>{item.label}</span>
          </button>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="safety-pill">PAPER ONLY</div>
        <div className="sidebar-note">Live broker submission remains disabled by default.</div>
      </div>
    </aside>
  );
}
