"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Nav } from "@/components/Nav";
import { FictitiousBanner } from "@/components/FictitiousBanner";
import { api, ApprovalQueueItem } from "@/lib/api";

const STATUS_COLOR: Record<string, string> = {
  awaiting_approval: "#f59e0b",
  blocked: "#ef4444",
};

const CHECK_COLOR: Record<string, string> = {
  PASS: "#22c55e",
  WARNING: "#f59e0b",
  BLOCKED: "#ef4444",
};

function CheckBadge({ result }: { result: string | null }) {
  if (!result) return <span style={{ color: "#aaa", fontSize: 11 }}>—</span>;
  return (
    <span
      style={{
        background: CHECK_COLOR[result] ?? "#ccc",
        color: "#fff",
        borderRadius: 4,
        padding: "2px 7px",
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: 0.5,
      }}
    >
      {result}
    </span>
  );
}

export default function ApprovalsPage() {
  const router = useRouter();
  const [items, setItems] = useState<ApprovalQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.approvals
      .list({ include_blocked: true, limit: 50 })
      .then(setItems)
      .catch((e: Error) => {
        if (e.message.startsWith("401")) router.push("/login");
        else setError(e.message);
      })
      .finally(() => setLoading(false));
  }, [router]);

  if (loading) return <p style={{ padding: 40 }}>Carregando fila de aprovações…</p>;

  return (
    <>
      <Nav />
      <main style={{ maxWidth: 900, margin: "0 auto", padding: "28px 20px" }}>
        <FictitiousBanner />
        <h1 style={{ marginTop: 0 }}>Fila de Aprovações</h1>
        <p style={{ color: "#666", fontSize: 13, marginBottom: 20 }}>
          Criativos aguardando revisão humana. A aprovação aqui é verificação interna —{" "}
          <strong>não garante aprovação pela Meta Ads</strong>.
        </p>

        {error && (
          <div style={{ background: "#fee", border: "1px solid #fcc", borderRadius: 6, padding: 12, marginBottom: 16, color: "#c00", fontSize: 13 }}>
            Erro ao carregar: {error}
          </div>
        )}

        {items.length === 0 && !error ? (
          <p style={{ color: "#888" }}>Nenhum criativo aguardando revisão.</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {items.map((item) => (
              <Link
                key={item.id}
                href={`/approvals/${item.id}`}
                style={{ textDecoration: "none", color: "inherit" }}
              >
                <div
                  style={{
                    background: "#fff",
                    borderRadius: 10,
                    padding: "14px 18px",
                    boxShadow: "0 1px 4px rgba(0,0,0,.08)",
                    display: "flex",
                    alignItems: "center",
                    gap: 16,
                    cursor: "pointer",
                    borderLeft: `4px solid ${STATUS_COLOR[item.status] ?? "#ccc"}`,
                  }}
                >
                  {/* Thumbnail */}
                  <div
                    style={{
                      width: 72,
                      height: 72,
                      borderRadius: 6,
                      background: "#f0f0f0",
                      flexShrink: 0,
                      overflow: "hidden",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    {item.thumbnail_url ? (
                      <img
                        src={item.thumbnail_url}
                        alt="Thumbnail"
                        style={{ width: "100%", height: "100%", objectFit: "cover" }}
                      />
                    ) : (
                      <span style={{ fontSize: 22 }}>🖼</span>
                    )}
                  </div>

                  {/* Info */}
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                      <span
                        style={{
                          background: STATUS_COLOR[item.status] ?? "#ccc",
                          color: "#fff",
                          borderRadius: 4,
                          padding: "2px 8px",
                          fontSize: 11,
                          fontWeight: 700,
                        }}
                      >
                        {item.status.replace("_", " ").toUpperCase()}
                      </span>
                      {item.is_fictitious && (
                        <span style={{ background: "#e0e7ff", color: "#4338ca", borderRadius: 4, padding: "2px 7px", fontSize: 11 }}>
                          FICTÍCIO
                        </span>
                      )}
                      {item.variation_of_id && (
                        <span style={{ background: "#fef3c7", color: "#92400e", borderRadius: 4, padding: "2px 7px", fontSize: 11 }}>
                          VARIAÇÃO
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: 12, color: "#555", display: "flex", gap: 12, flexWrap: "wrap" }}>
                      <span>Provider: <strong>{item.provider}</strong></span>
                      {item.width && item.height && (
                        <span>Dimensão: <strong>{item.width}×{item.height}</strong></span>
                      )}
                      {item.estimated_cost_usd !== null && (
                        <span>Custo: <strong>US$ {item.estimated_cost_usd?.toFixed(3)}</strong></span>
                      )}
                    </div>
                    <div style={{ fontSize: 12, color: "#555", display: "flex", gap: 10, marginTop: 6 }}>
                      <span>Quality: <CheckBadge result={item.quality_check?.result ?? null} /></span>
                      <span>Policy: <CheckBadge result={item.policy_check?.result ?? null} /></span>
                    </div>
                  </div>

                  <span style={{ fontSize: 13, color: "#7c83ff", flexShrink: 0 }}>Revisar →</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </main>
    </>
  );
}
