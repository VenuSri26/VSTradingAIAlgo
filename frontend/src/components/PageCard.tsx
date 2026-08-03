import type { ReactNode } from "react";

export function PageCard({ title, children, accent }: { title: string; children: ReactNode; accent?: string }) {
  return (
    <section className="page-card" style={accent ? { borderColor: accent } : undefined}>
      <h2>{title}</h2>
      {children}
    </section>
  );
}

export function StatTile({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="stat-tile">
      <span>{label}</span>
      <strong>{value}</strong>
      {hint ? <small>{hint}</small> : null}
    </div>
  );
}
