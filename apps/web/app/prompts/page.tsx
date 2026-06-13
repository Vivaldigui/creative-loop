"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Nav } from "@/components/Nav";
import { FictitiousBanner } from "@/components/FictitiousBanner";
import { api, PromptTemplateOut } from "@/lib/api";

const FORMATS = ["", "feed", "stories", "reels", "carousel", "banner"];
const OBJECTIVES = ["", "OUTCOME_SALES", "OUTCOME_LEADS", "OUTCOME_AWARENESS", "OUTCOME_ENGAGEMENT"];
const PAGE_SIZE = 20;

export default function PromptsPage() {
  const router = useRouter();
  const [templates, setTemplates] = useState<PromptTemplateOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [filters, setFilters] = useState({ ad_format: "", objective: "" });

  const loadTemplates = useCallback(async (reset = false) => {
    setLoading(true);
    const currentOffset = reset ? 0 : offset;
    try {
      const params: Record<string, string | number> = { limit: PAGE_SIZE, offset: currentOffset };
      if (filters.ad_format) params.ad_format = filters.ad_format;
      if (filters.objective) params.objective = filters.objective;
      const result = await api.prompts.list(params as Parameters<typeof api.prompts.list>[0]);
      if (reset) {
        setTemplates(result);
        setOffset(PAGE_SIZE);
      } else {
        setTemplates((prev) => [...prev, ...result]);
        setOffset((prev) => prev + PAGE_SIZE);
      }
      setHasMore(result.length === PAGE_SIZE);
    } catch {
      router.push("/login");
    } finally {
      setLoading(false);
    }
  }, [filters, offset, router]);

  useEffect(() => {
    loadTemplates(true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  return (
    <>
      <Nav />
      <main style={{ maxWidth: 900, margin: "0 auto", padding: "28px 20px" }}>
        <FictitiousBanner />
        <h1 style={{ marginTop: 0 }}>Templates de Prompt</h1>

        {/* Filter bar */}
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 20, fontSize: 13 }}>
          <div>
            <label style={labelStyle}>Formato</label>
            <select
              value={filters.ad_format}
              onChange={(e) => setFilters((p) => ({ ...p, ad_format: e.target.value }))}
              style={selectStyle}
            >
              {FORMATS.map((f) => (
                <option key={f} value={f}>{f || "Todos"}</option>
              ))}
            </select>
          </div>
          <div>
            <label style={labelStyle}>Objetivo</label>
            <select
              value={filters.objective}
              onChange={(e) => setFilters((p) => ({ ...p, objective: e.target.value }))}
              style={selectStyle}
            >
              {OBJECTIVES.map((o) => (
                <option key={o} value={o}>{o || "Todos"}</option>
              ))}
            </select>
          </div>
          <button
            onClick={() => setFilters({ ad_format: "", objective: "" })}
            style={{ alignSelf: "flex-end", background: "#eee", border: "none", borderRadius: 4, padding: "6px 12px", cursor: "pointer", fontSize: 12 }}
          >
            Limpar
          </button>
        </div>

        <p style={{ fontSize: 12, color: "#888", marginBottom: 12 }}>
          {templates.length} template{templates.length !== 1 ? "s" : ""} carregado{templates.length !== 1 ? "s" : ""}
        </p>

        {templates.length === 0 && !loading ? (
          <p style={{ color: "#888" }}>
            Nenhum template encontrado. Acesse um <Link href="/ads" style={{ color: "#4c6ef5" }}>anúncio</Link> e gere um prompt primeiro.
          </p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {templates.map((t) => (
              <Link key={t.id} href={`/prompts/${t.id}`} style={{ textDecoration: "none", color: "inherit" }}>
                <div style={cardStyle}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4, flexWrap: "wrap" }}>
                      <span style={{ fontWeight: 600, fontSize: 14 }}>{t.name}</span>
                      <StatusBadge status={t.status} />
                      {t.ad_format && <Badge bg="#e8f4fd" fg="#1864ab">{t.ad_format}</Badge>}
                      {t.objective && <Badge bg="#f3f0ff" fg="#5f3dc4">{t.objective}</Badge>}
                    </div>
                    <div style={{ fontSize: 12, color: "#888" }}>
                      Criado: {t.created_at ? new Date(t.created_at).toLocaleString("pt-BR") : "—"}
                    </div>
                  </div>
                  <div style={{ textAlign: "right", flexShrink: 0 }}>
                    <div style={{ fontSize: 22, fontWeight: 700, color: "#4c6ef5" }}>—</div>
                    <div style={{ fontSize: 11, color: "#888" }}>versões</div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}

        {loading && <p style={{ textAlign: "center", color: "#888", marginTop: 20 }}>Carregando...</p>}

        {!loading && hasMore && (
          <div style={{ textAlign: "center", marginTop: 20 }}>
            <button
              onClick={() => loadTemplates(false)}
              style={{ background: "#4c6ef5", color: "#fff", border: "none", borderRadius: 6, padding: "10px 24px", cursor: "pointer", fontSize: 14 }}
            >
              Carregar mais
            </button>
          </div>
        )}
      </main>
    </>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, [string, string]> = {
    active: ["#d4edda", "#155724"],
    draft: ["#e2e3e5", "#444"],
    archived: ["#f8d7da", "#721c24"],
  };
  const [bg, fg] = map[status] ?? ["#e2e3e5", "#444"];
  return <Badge bg={bg} fg={fg}>{status}</Badge>;
}

function Badge({ bg, fg, children }: { bg: string; fg: string; children: React.ReactNode }) {
  return (
    <span style={{ background: bg, color: fg, borderRadius: 3, padding: "2px 8px", fontSize: 11, fontWeight: 600 }}>
      {children}
    </span>
  );
}

const cardStyle: React.CSSProperties = {
  background: "#fff",
  borderRadius: 8,
  padding: "14px 18px",
  boxShadow: "0 1px 4px rgba(0,0,0,.08)",
  display: "flex",
  alignItems: "flex-start",
  gap: 16,
  cursor: "pointer",
  transition: "box-shadow 0.15s",
};

const labelStyle: React.CSSProperties = {
  display: "block", fontSize: 10, color: "#999", marginBottom: 3, fontWeight: 600, textTransform: "uppercase",
};

const selectStyle: React.CSSProperties = {
  padding: "5px 8px", borderRadius: 4, border: "1px solid #ddd", fontSize: 13,
};
