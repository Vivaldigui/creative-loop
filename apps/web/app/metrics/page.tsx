"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Nav } from "@/components/Nav";
import { FictitiousBanner } from "@/components/FictitiousBanner";
import { api, MetricsOut } from "@/lib/api";

type TopAd = {
  id: string;
  name: string;
  performance_label: string | null;
  source: string | null;
  is_fictitious: boolean;
  [key: string]: unknown;
};

export default function MetricsPage() {
  const router = useRouter();
  const [metrics, setMetrics] = useState<MetricsOut | null>(null);
  const [topAds, setTopAds] = useState<TopAd[]>([]);
  const [metric, setMetric] = useState("roas");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.auth.me().catch(() => router.push("/login"));
    Promise.all([
      api.metrics.summary(),
      api.metrics.topAds(metric, 10),
    ])
      .then(([m, t]) => {
        setMetrics(m);
        setTopAds(t as TopAd[]);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [router, metric]);

  const refreshTopAds = (m: string) => {
    setMetric(m);
    api.metrics.topAds(m, 10).then((t) => setTopAds(t as TopAd[])).catch(() => {});
  };

  if (loading) return <p style={{ padding: 40 }}>Carregando...</p>;

  return (
    <>
      <Nav />
      <main style={{ maxWidth: 900, margin: "0 auto", padding: "28px 20px" }}>
        <FictitiousBanner />
        <h1 style={{ marginTop: 0 }}>Métricas Consolidadas</h1>

        {/* KPI cards */}
        {metrics && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 12, marginBottom: 32 }}>
            <KpiCard label="Gasto Total" value={`R$ ${metrics.total_spend.toFixed(2)}`} />
            <KpiCard label="Impressões" value={metrics.total_impressions.toLocaleString("pt-BR")} />
            <KpiCard label="Cliques" value={metrics.total_clicks.toLocaleString("pt-BR")} />
            <KpiCard label="Compras" value={metrics.total_purchases.toLocaleString("pt-BR")} />
            <KpiCard label="Leads" value={metrics.total_leads.toLocaleString("pt-BR")} />
            <KpiCard label="Valor de Compras" value={`R$ ${metrics.total_purchase_value.toFixed(2)}`} />
            <KpiCard label="ROAS Médio" value={metrics.avg_roas.toFixed(2)} sub="reportado" />
            {metrics.derived_roas !== null && (
              <KpiCard label="ROAS Derivado" value={metrics.derived_roas.toFixed(2)} sub="calculado" />
            )}
            <KpiCard label="CTR Médio" value={`${metrics.avg_ctr.toFixed(2)}%`} />
            <KpiCard label="CPC Médio" value={`R$ ${metrics.avg_cpc.toFixed(2)}`} />
            <KpiCard label="CPM Médio" value={`R$ ${metrics.avg_cpm.toFixed(2)}`} />
          </div>
        )}

        {/* Top ads table */}
        <section>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
            <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>Top Anúncios por:</h2>
            <select
              value={metric}
              onChange={(e) => refreshTopAds(e.target.value)}
              style={{ fontSize: 13, padding: "4px 8px", borderRadius: 4 }}
            >
              {["roas", "ctr", "purchases", "leads", "spend"].map((m) => (
                <option key={m} value={m}>{m.toUpperCase()}</option>
              ))}
            </select>
          </div>
          {topAds.length === 0 ? (
            <p style={{ color: "#888" }}>Nenhum anúncio com métricas disponíveis.</p>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ background: "#f0f0f0" }}>
                  {["Nome", "Label", "Fonte", metric.toUpperCase()].map((h) => (
                    <th key={h} style={{ padding: "7px 10px", textAlign: "left", borderBottom: "1px solid #ddd" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {topAds.map((ad) => (
                  <tr key={ad.id} style={{ borderBottom: "1px solid #eee" }}>
                    <td style={{ padding: "7px 10px" }}>
                      <a href={`/ads/${ad.id}`} style={{ color: "#4c6ef5", textDecoration: "none" }}>
                        {ad.name.length > 50 ? ad.name.slice(0, 50) + "…" : ad.name}
                      </a>
                    </td>
                    <td style={{ padding: "7px 10px" }}>
                      {ad.performance_label && <LabelBadge label={ad.performance_label} />}
                    </td>
                    <td style={{ padding: "7px 10px", color: "#888" }}>
                      {ad.is_fictitious ? "🔵 fictício" : ad.source ?? "—"}
                    </td>
                    <td style={{ padding: "7px 10px", fontWeight: 600 }}>
                      {ad[metric] !== null && ad[metric] !== undefined
                        ? Number(ad[metric]).toFixed(2)
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </main>
    </>
  );
}

function KpiCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div
      style={{
        background: "#fff",
        border: "1px solid #eee",
        borderRadius: 8,
        padding: "14px 16px",
        boxShadow: "0 1px 3px rgba(0,0,0,.05)",
      }}
    >
      <div style={{ fontSize: 11, color: "#888", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: "#1a1a2e" }}>{value}</div>
      {sub && <div style={{ fontSize: 10, color: "#aaa", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function LabelBadge({ label }: { label: string }) {
  const colors: Record<string, string> = { winner: "#d4edda", loser: "#f8d7da", neutral: "#e2e3e5" };
  return (
    <span
      style={{
        background: colors[label] ?? "#e2e3e5",
        borderRadius: 4,
        padding: "2px 8px",
        fontSize: 11,
        fontWeight: 600,
      }}
    >
      {label}
    </span>
  );
}
