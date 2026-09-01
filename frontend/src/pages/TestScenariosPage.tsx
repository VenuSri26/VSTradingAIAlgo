import { useEffect, useState } from "react";

interface ScenarioResult {
  name: string;
  description: string;
  expected: "CE_BUY" | "PE_BUY" | "NO_TRADE";
  actual: "CE_BUY" | "PE_BUY" | "NO_TRADE";
  passed: boolean;
  grade: string;
  score: number;
  blockers: string[];
}

interface ScenarioSuite {
  suite: string;
  status: "PASS" | "FAIL";
  passed: number;
  failed: number;
  total: number;
  live_orders_enabled: boolean;
  results: ScenarioResult[];
}

export function TestScenariosPage() {
  const [data, setData] = useState<ScenarioSuite | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/test-scenarios");
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      setData(await response.json() as ScenarioSuite);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load test scenarios");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  if (loading) return <div className="page-card">Running deterministic release scenarios…</div>;
  if (error) return <div className="page-card"><b>Scenario API unavailable:</b> {error}</div>;
  if (!data) return null;

  return (
    <div className="page-stack">
      <section className="page-card">
        <div className="eyebrow">V4.0 RELEASE TESTING</div>
        <h2>{data.suite}</h2>
        <p>Deterministic tests verify trade acceptance, rejection and safety vetoes without sending broker orders.</p>
        <button type="button" className="primary-button" onClick={() => void load()}>Run scenarios again</button>
      </section>

      <section className="metric-grid">
        <div className="page-card"><div className="eyebrow">STATUS</div><h2>{data.status}</h2></div>
        <div className="page-card"><div className="eyebrow">PASSED</div><h2>{data.passed}/{data.total}</h2></div>
        <div className="page-card"><div className="eyebrow">FAILED</div><h2>{data.failed}</h2></div>
        <div className="page-card"><div className="eyebrow">LIVE ORDERS</div><h2>{data.live_orders_enabled ? "ENABLED" : "DISABLED"}</h2></div>
      </section>

      <section className="page-card">
        <div className="eyebrow">TEST SCENARIOS</div>
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>Scenario</th><th>Expected</th><th>Actual</th><th>Grade</th><th>Result</th><th>Reason</th></tr></thead>
            <tbody>
              {data.results.map((row) => (
                <tr key={row.name}>
                  <td><b>{row.name.split("_").join(" ")}</b><div className="muted-text">{row.description}</div></td>
                  <td>{row.expected}</td>
                  <td>{row.actual}</td>
                  <td>{row.grade}</td>
                  <td>{row.passed ? "PASS" : "FAIL"}</td>
                  <td>{row.blockers.length ? row.blockers.join(", ") : `Alignment ${row.score}/100; all gates passed`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
