"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Nav } from "@/components/Nav";
import { api, SuggestionOut } from "@/lib/api";

export default function SuggestionsPage() {
  const [suggestions, setSuggestions] = useState<SuggestionOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = statusFilter !== "all" ? { status: statusFilter } : undefined;
      const data = await api.suggestions.list(params);
      setSuggestions(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { load(); }, [load]);

  return (
    <div style={{ minHeight: "100vh", background: "#f5f5f5" }}>
      <Nav />
      <div style={{ maxWidth: 1000, margin: "0 auto", padding: "24px 16px" }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Sugestões de Próxima Rodada</h1>
        <p style={{ color: "#6b7280", fontSize: 13, marginBottom: 20 }}>
          Fase 7 — Sugestões de experimentos geradas com base em aprendizados. Requere aprovação humana antes de qualquer ação.
          <strong> Nenhuma imagem é gerada automaticamente.</strong>
        </p>

        <div style={{ display: "flex", gap: 8, marginBottom: 16, alignItems: "center" }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: "#374151" }}>Status:</span>
          {["all", "pending_approval", "approved", "rejected"].map(s => (
            <button key={s} onClick={() => setStatusFilter(s)} style={{
              padding: "3px 10px", border: "1px solid #d1d5db", borderRadius: 20,
              background: statusFilter === s ? "#3b82f6" : "#fff",
              color: statusFilter === s ? "#fff" : "#374151",
              fontSize: 12, cursor: "pointer", fontWeight: statusFilter === s ? 700 : 400,
            }}>{s === "all" ? "Todos" : s.replace(/_/g, " ")}</button>
          ))}
          <button onClick={load} style={{ marginLeft: "auto", padding: "4px 12px", border: "1px solid #d1d5db", borderRadius: 6, background: "#f3f4f6", fontSize: 12, cursor: "pointer" }}>
            Recarregar
          </button>
        </div>

        {error && (
          <div style={{ background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: 6, padding: 12, marginBottom: 16, color: "#991b1b", fontSize: 12 }}>{error}</div>
        )}

        {loading ? (
          <p style={{ color: "#9ca3af", fontSize: 13 }}>Carregando…</p>
        ) : suggestions.length === 0 ? (
          <div style={{ background: "#fff", borderRadius: 8, padding: 40, textAlign: "center", border: "1px solid #e5e7eb", color: "#6b7280", fontSize: 14 }}>
            Nenhuma sugestão encontrada.
          </div>
        ) : (
          <div style={{ display: "grid", gap: 12 }}>
            {suggestions.map(s => (
              <SuggestionCard key={s.id} suggestion={s} onRefresh={load} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function SuggestionCard({ suggestion: s, onRefresh }: { suggestion: SuggestionOut; onRefresh: () => void }) {
  const [loading, setLoading] = useState<"approve" | "reject" | null>(null);
  const [err, setErr] = useState("");

  const statusColors: Record<string, { bg: string; text: string }> = {
    pending_approval: { bg: "#fef9c3", text: "#713f12" },
    approved: { bg: "#dcfce7", text: "#166534" },
    rejected: { bg: "#fee2e2", text: "#991b1b" },
  };
  const sc = statusColors[s.status] ?? { bg: "#f3f4f6", text: "#374151" };

  async function doApprove() {
    const comment = prompt("Comentário (opcional):") ?? undefined;
    setLoading("approve");
    setErr("");
    try {
      await api.suggestions.approve(s.id, comment);
      onRefresh();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(null);
    }
  }

  async function doReject() {
    const comment = prompt("Motivo da rejeição (opcional):") ?? undefined;
    setLoading("reject");
    setErr("");
    try {
      await api.suggestions.reject(s.id, comment);
      onRefresh();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(null);
    }
  }

  return (
    <div style={{ background: "#fff", borderRadius: 8, border: "1px solid #e5e7eb", padding: "16px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
        <div>
          <span style={{ background: sc.bg, color: sc.text, borderRadius: 4, padding: "2px 8px", fontSize: 11, fontWeight: 700, textTransform: "uppercase" }}>
            {s.status.replace(/_/g, " ")}
          </span>
          {s.diversity_score != null && (
            <span style={{ marginLeft: 8, fontSize: 11, color: "#6b7280" }}>
              Diversidade: {(s.diversity_score * 100).toFixed(0)}%
            </span>
          )}
        </div>
        <span style={{ fontSize: 11, color: "#9ca3af" }}>
          {s.created_at ? new Date(s.created_at).toLocaleDateString("pt-BR") : ""}
        </span>
      </div>

      {s.hypothesis && (
        <p style={{ margin: "0 0 8px", fontWeight: 600, fontSize: 13, color: "#1f2937" }}>
          <strong>Hipótese:</strong> {s.hypothesis}
        </p>
      )}
      {s.primary_variable && (
        <p style={{ margin: "0 0 8px", fontSize: 12, color: "#374151" }}>
          <strong>Variável principal:</strong> {s.primary_variable}
        </p>
      )}
      {s.rationale && (
        <p style={{ margin: "0 0 8px", fontSize: 12, color: "#6b7280" }}>
          {s.rationale.slice(0, 200)}{s.rationale.length > 200 ? "…" : ""}
        </p>
      )}

      {s.context_snapshot && (
        <div style={{ background: "#f9fafb", borderRadius: 6, padding: "8px 12px", fontSize: 11, color: "#374151", marginBottom: 10 }}>
          {Object.entries(s.context_snapshot).map(([k, v]) => (
            <span key={k} style={{ marginRight: 12 }}><strong>{k}:</strong> {String(v)}</span>
          ))}
        </div>
      )}

      {s.selected_learning_ids && s.selected_learning_ids.length > 0 && (
        <p style={{ fontSize: 11, color: "#6b7280", margin: "0 0 10px" }}>
          Aprendizados usados: {s.selected_learning_ids.length}
        </p>
      )}

      <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 6 }}>
        {s.status === "pending_approval" && (
          <>
            <button
              disabled={loading !== null}
              onClick={doApprove}
              style={{ padding: "5px 12px", background: loading === "approve" ? "#9ca3af" : "#059669", color: "#fff", border: "none", borderRadius: 5, cursor: "pointer", fontWeight: 600, fontSize: 12 }}
            >
              {loading === "approve" ? "…" : "Aprovar"}
            </button>
            <button
              disabled={loading !== null}
              onClick={doReject}
              style={{ padding: "5px 12px", background: loading === "reject" ? "#9ca3af" : "#dc2626", color: "#fff", border: "none", borderRadius: 5, cursor: "pointer", fontWeight: 600, fontSize: 12 }}
            >
              {loading === "reject" ? "…" : "Rejeitar"}
            </button>
          </>
        )}
        {s.source_experiment_id && (
          <Link href={`/experiments/${s.source_experiment_id}`} style={{ fontSize: 12, color: "#3b82f6", textDecoration: "none", marginLeft: "auto" }}>
            Ver experimento fonte →
          </Link>
        )}
        {err && <span style={{ fontSize: 10, color: "#dc2626" }}>{err}</span>}
      </div>
    </div>
  );
}
