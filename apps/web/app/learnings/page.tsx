"use client";

import { useCallback, useEffect, useState } from "react";
import { Nav } from "@/components/Nav";
import { api, LearningOut } from "@/lib/api";

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  provisional: { bg: "#fef9c3", text: "#713f12" },
  confirmed: { bg: "#dcfce7", text: "#166534" },
  rejected: { bg: "#fee2e2", text: "#991b1b" },
};

function ConfirmRejectButtons({ learning, onRefresh }: { learning: LearningOut; onRefresh: () => void }) {
  const [loading, setLoading] = useState<"confirm" | "reject" | null>(null);
  const [err, setErr] = useState("");

  if (learning.status !== "provisional") return null;

  async function doConfirm() {
    setLoading("confirm");
    setErr("");
    try {
      await api.learnings.confirm(learning.id, "Confirmado via UI");
      onRefresh();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(null);
    }
  }

  async function doReject() {
    const comment = prompt("Motivo da rejeição (obrigatório):");
    if (!comment?.trim()) return;
    setLoading("reject");
    setErr("");
    try {
      await api.learnings.reject(learning.id, comment);
      onRefresh();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(null);
    }
  }

  return (
    <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
      <button
        disabled={loading !== null}
        onClick={doConfirm}
        style={{ padding: "4px 10px", background: loading === "confirm" ? "#9ca3af" : "#059669", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 11, fontWeight: 600 }}
      >
        {loading === "confirm" ? "…" : "Confirmar"}
      </button>
      <button
        disabled={loading !== null}
        onClick={doReject}
        style={{ padding: "4px 10px", background: loading === "reject" ? "#9ca3af" : "#dc2626", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 11, fontWeight: 600 }}
      >
        {loading === "reject" ? "…" : "Rejeitar"}
      </button>
      {err && <span style={{ fontSize: 10, color: "#dc2626" }}>{err}</span>}
    </div>
  );
}

export default function LearningsPage() {
  const [learnings, setLearnings] = useState<LearningOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params: Record<string, string> = {};
      if (statusFilter !== "all") params.status = statusFilter;
      const data = await api.learnings.list(params);
      setLearnings(data);
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
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "24px 16px" }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Aprendizados</h1>
        <p style={{ color: "#6b7280", fontSize: 13, marginBottom: 20 }}>
          Fase 7 — Padrões aprendidos de experimentos. Novos aprendizados começam como <strong>provisional</strong>. Confirme ou rejeite com análise humana obrigatória.
        </p>

        <div style={{ display: "flex", gap: 8, marginBottom: 16, alignItems: "center" }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: "#374151" }}>Status:</span>
          {["all", "provisional", "confirmed", "rejected"].map(s => (
            <button key={s} onClick={() => setStatusFilter(s)} style={{
              padding: "3px 10px", border: "1px solid #d1d5db", borderRadius: 20,
              background: statusFilter === s ? "#3b82f6" : "#fff",
              color: statusFilter === s ? "#fff" : "#374151",
              fontSize: 12, cursor: "pointer", fontWeight: statusFilter === s ? 700 : 400,
            }}>{s === "all" ? "Todos" : s}</button>
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
        ) : learnings.length === 0 ? (
          <div style={{ background: "#fff", borderRadius: 8, padding: 40, textAlign: "center", border: "1px solid #e5e7eb", color: "#6b7280", fontSize: 14 }}>
            Nenhum aprendizado encontrado.
          </div>
        ) : (
          <div style={{ display: "grid", gap: 12 }}>
            {learnings.map(l => {
              const sc = STATUS_COLORS[l.status] ?? { bg: "#f3f4f6", text: "#374151" };
              return (
                <div key={l.id} style={{ background: "#fff", borderRadius: 8, border: "1px solid #e5e7eb", padding: "16px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                    <div style={{ flex: 1, marginRight: 12 }}>
                      <p style={{ margin: 0, fontWeight: 600, fontSize: 14, color: "#1f2937" }}>{l.observed_pattern}</p>
                    </div>
                    <span style={{ background: sc.bg, color: sc.text, borderRadius: 4, padding: "2px 8px", fontSize: 11, fontWeight: 700, textTransform: "uppercase", whiteSpace: "nowrap" }}>
                      {l.status}
                    </span>
                  </div>

                  <div style={{ display: "flex", gap: 12, fontSize: 12, color: "#6b7280", flexWrap: "wrap", marginBottom: 6 }}>
                    {l.context && <span>Contexto: <strong>{l.context}</strong></span>}
                    {l.segment && <span>Segmento: <strong>{l.segment}</strong></span>}
                    {l.objective && <span>Objetivo: <strong>{l.objective}</strong></span>}
                    {l.placement && <span>Placement: <strong>{l.placement}</strong></span>}
                    {l.confidence != null && <span>Confiança: <strong>{(l.confidence * 100).toFixed(0)}%</strong></span>}
                    {l.sample_size != null && <span>N={l.sample_size}</span>}
                    {l.responsible_type && <span>Tipo: <strong>{l.responsible_type}</strong></span>}
                  </div>

                  {l.review_comment && (
                    <div style={{ background: "#f9fafb", borderRadius: 4, padding: "6px 10px", fontSize: 12, color: "#374151", marginBottom: 6 }}>
                      <strong>Comentário:</strong> {l.review_comment}
                    </div>
                  )}

                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
                    <ConfirmRejectButtons learning={l} onRefresh={load} />
                    <span style={{ fontSize: 11, color: "#9ca3af" }}>
                      {l.created_at ? new Date(l.created_at).toLocaleDateString("pt-BR") : ""}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        <p style={{ fontSize: 11, color: "#9ca3af", marginTop: 12 }}>
          {learnings.length} aprendizado(s). Aprendizados confirmed podem ser usados na geração de sugestões.
        </p>
      </div>
    </div>
  );
}
