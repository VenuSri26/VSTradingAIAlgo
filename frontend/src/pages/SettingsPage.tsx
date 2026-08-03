import { PageCard } from "../components/PageCard";

export function SettingsPage() {
  return (
    <div className="page-stack">
      <PageCard title="Safety Configuration" accent="#fbbf24">
        <div className="settings-list">
          <div><strong>Execution mode</strong><span>Decision support / paper only</span></div>
          <div><strong>Live Zerodha orders</strong><span className="negative">Disabled</span></div>
          <div><strong>Protected actions</strong><span>Require X-Admin-Token</span></div>
          <div><strong>Runtime configuration</strong><span>/opt/vstradingai/shared/backend.env</span></div>
        </div>
      </PageCard>
      <PageCard title="Deployment Guidance">
        <p className="muted-text">Change server-side values only through the shared environment file, then restart the API service and run the AWS validation script.</p>
        <pre className="command-view">sudo nano /opt/vstradingai/shared/backend.env{"\n"}sudo systemctl restart vstradingai-api{"\n"}sudo /opt/vstradingai/current/test_aws_lightsail.sh</pre>
      </PageCard>
    </div>
  );
}
