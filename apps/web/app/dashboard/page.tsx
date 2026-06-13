"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Nav } from "@/components/Nav";
import { FictitiousBanner } from "@/components/FictitiousBanner";
import { api, ProductOut, SourceAdOut } from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [products, setProducts] = useState<ProductOut[]>([]);
  const [ads, setAds] = useState<SourceAdOut[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.products.list(), api.sourceAds.list()])
      .then(([p, a]) => {
        setProducts(p);
        setAds(a);
      })
      .catch(() => router.push("/login"))
      .finally(() => setLoading(false));
  }, [router]);

  const totalSpend = ads
    .flatMap((a) => a.snapshots)
    .reduce((s, snap) => s + (snap.spend ?? 0), 0);

  const totalImpressions = ads
    .flatMap((a) => a.snapshots)
    .reduce((s, snap) => s + (snap.impressions ?? 0), 0);

  if (loading) return <p style={{ padding: 40 }}>Carregando...</p>;

  return (
    <>
      <Nav />
      <main style={{ maxWidth: 1000, margin: "0 auto", padding: "28px 20px" }}>
        <FictitiousBanner />

        <h1 style={{ marginTop: 0 }}>Dashboard</h1>

        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 32 }}>
          <Card label="Produtos" value={products.length} />
          <Card label="Anúncios históricos" value={ads.length} />
          <Card label="Gasto total (fictício)" value={`R$ ${totalSpend.toFixed(2)}`} />
          <Card label="Impressões (fictício)" value={totalImpressions.toLocaleString()} />
        </div>

        <h2>Anúncios recentes</h2>
        {ads.length === 0 ? (
          <p style={{ color: "#888" }}>Nenhum anúncio encontrado.</p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", background: "#fff", borderRadius: 8, overflow: "hidden" }}>
            <thead>
              <tr style={{ background: "#f0f0f0", fontSize: 13 }}>
                <th style={th}>Nome</th>
                <th style={th}>Formato</th>
                <th style={th}>Label</th>
                <th style={th}>Status</th>
              </tr>
            </thead>
            <tbody>
              {ads.map((ad) => (
                <tr
                  key={ad.id}
                  style={{ cursor: "pointer", fontSize: 14 }}
                  onClick={() => router.push(`/ads/${ad.id}`)}
                >
                  <td style={td}>{ad.name}</td>
                  <td style={td}>{ad.ad_format ?? "—"}</td>
                  <td style={td}>
                    <LabelBadge label={ad.performance_label} />
                  </td>
                  <td style={td}>{ad.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </main>
    </>
  );
}

function Card({ label, value }: { label: string; value: string | number }) {
  return (
    <div
      style={{
        background: "#fff",
        borderRadius: 8,
        padding: "16px 24px",
        minWidth: 160,
        boxShadow: "0 1px 4px rgba(0,0,0,.08)",
      }}
    >
      <div style={{ fontSize: 12, color: "#888", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700 }}>{value}</div>
    </div>
  );
}

function LabelBadge({ label }: { label: string | null }) {
  const colors: Record<string, string> = { winner: "#d4edda", loser: "#f8d7da", neutral: "#e2e3e5" };
  return (
    <span
      style={{
        background: colors[label ?? ""] ?? "#e2e3e5",
        borderRadius: 4,
        padding: "2px 8px",
        fontSize: 12,
        fontWeight: 600,
      }}
    >
      {label ?? "—"}
    </span>
  );
}

const th: React.CSSProperties = { textAlign: "left", padding: "10px 14px" };
const td: React.CSSProperties = { padding: "10px 14px", borderTop: "1px solid #f0f0f0" };
