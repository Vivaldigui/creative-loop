"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Nav } from "@/components/Nav";
import { api, ExperimentOut } from "@/lib/api";

const STATE_COLORS: Record<string, { bg: string; text: string }> = {
  draft: { bg: "#f3f4f6", text: "#374151" },
  running: { bg: "#dcfce7", text: "#166534" },
  evaluating: { bg: "#dbeafe", text: "#1e40af" },
  completed: { bg: "#e0e7ff", text: "#3730a3" },
  stopped: { bg: "#fee2e2", text: "#991b1b" },
  paused: { bg: "#fef9c3", text: "#713f12" },
};

function StatusBadge({ status }: { status: string }) {
  const c = STATE_COLORS[status] ?? { bg: "#f3f4f6", text: "#374151" };
  return (
    <span style={{ background: c.bg, color: c.text, borderRadius: 4, padding: "2px 8px", fontSize: 11, fontWeight: 700, textTransform: "uppercase" }}>
      {status}
    </span>
  );
}

function EvalBadge({ state }: { state: string | null }) {
  if (!state) return <span style={{ color: "#9ca3af", fontSize: 11 }}>—</span>;
  const colors: Record<string, { bg: string; text: string }> = {
    winner_candidate: { bg: "#dcfce7", text: "#166534" },
    promising: { bg: "#d1fae5", text: "#065f46" },
    inconclusive: { bg: "#fef9c3", text: "#713f12" },
    underperforming: { bg: "#fee2e2", text: "#991b1b" },
    insufficient_data: { bg: "#f3f4f6", text: "#6b7280" },
    collecting: { bg: "#e0f2fe", text: "#0369a1" },
  };
  const c = colors[state] ?? { bg: "#f3f4f6", text: "#374151" };
  return (
    <span style={{ background: c.bg, color: c.text, borderRadius: 4, padding: "2px 8px", fontSize: 11, fontWeight: 600 }}>
      {state.replace(/_/g, " ")}
    </span>
  );
}

export default function ExperimentsPage() {
  const [experiments, setExperiments] = useState<ExperimentOut[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [modeFilter, setModeFilter] = useState("all");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params: Record<string, string> = {};
      if (statusFilter !== "all") params.status = statusFilter;
      if (modeFilter !== "all") params.mode = modeFilter;
      const data = await api.experiments.list(params);
      setExperiments(data.items);
      setTotal(data.total);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [statusFilter, modeFilter]);

  useEffect(() => { load(); }, [load]);

  return (
    <div style={{ minHeight: "100vh", background: "#f5f5f5" }}>
      <Nav />
      <div style={{ maxWidth: 1200, margin: "0 auto", padding: "24px 16px" }}>
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 4 }}>
          <h1 style={{ fontSize: 22, fontWeight: 700 }}>Experimentos</h1>
          <Link href="/experiments/new" style={{ padding: "8px 16px", background: "#3b82f6", color: "#fff", borderRadius: 6, textDecoration: "none", fontSize: 13, fontWeight: 600 }}>
            + Novo Experimento
          </Link>
        </div>
        <p style={{ color: "#6b7280", fontSize: 13, marginBottom: 20 }}>
          Fase 7 — Gerencie experimentos EXPLORATORY e CONTROLLED. Avalie variantes com rigor estatístico.
        </p>

        {/* Filters */}
        <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: "#374151" }}>Status:</span>
            {["all", "draft", "running", "evaluating", "completed", "stopped"].map(s => (
              <button key={s} onClick={() => setStatusFilter(s)} style={{
                padding: "3px 10px", border: "1px solid #d1d5db", borderRadius: 20,
                background: statusFilter === s ? "#3b82f6" : "#fff",
                color: statusFilter === s ? "#fff" : "#374151",
                fontSize: 12, cursor: "pointer", fontWeight: statusFilter === s ? 700 : 400,
              }}>{s === "all" ? "Todos" : s}</button>
            ))}
          </div>
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: "#374151" }}>Modo:</span>
            {["all", "EXPLORATORY", "CONTROLLED"].map(m => (
              <button key={m} onClick={() => setModeFilter(m)} style={{
                padding: "3px 10px", border: "1px solid #d1d5db", borderRadius: 20,
                background: modeFilter === m ? "#7c3aed" : "#fff",
                color: modeFilter === m ? "#fff" : "#374151",
                fontSize: 12, cursor: "pointer", fontWeight: modeFilter === m ? 700 : 400,
              }}>{m === "all" ? "Todos" : m}</button>
            ))}
          </div>
          <button onClick={load} style={{ marginLeft: "auto", padding: "4px 12px", border: "1px solid #d1d5db", borderRadius: 6, background: "#f3f4f6", fontSize: 12, cursor: "pointer" }}>
            Recarregar
          </button>
        </div>

        {error && (
          <div style={{ background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: 6, padding: 12, marginBottom: 16, color: "#991b1b", fontSize: 12 }}>
            {error}
          </div>
        )}

        {loading ? (
          <p style={{ color: "#9ca3af", fontSize: 13 }}>Carregando…</p>
        ) : experiments.length === 0 ? (
          <div style={{ background: "#fff", borderRadius: 8, padding: 40, textAlign: "center", border: "1px solid #e5e7eb", color: "#6b7280", fontSize: 14 }}>
            Nenhum experimento encontrado.{" "}
            <Link href="/experiments/new" style={{ color: "#3b82f6" }}>Criar experimento</Link>
          </div>
        ) : (
          <div style={{ background: "#fff", borderRadius: 8, border: "1px solid #e5e7eb", overflow: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: "2px solid #e5e7eb", background: "#f9fafb" }}>
                  <th style={thStyle}>Nome</th>
                  <th style={thStyle}>Modo</th>
                  <th style={thStyle}>Status</th>
                  <th style={thStyle}>Avaliação</th>
                  <th style={thStyle}>Métrica Principal</th>
                  <th style={thStyle}>Variantes</th>
                  <th style={thStyle}>Criado em</th>
                  <th style={thStyle}>Ações</th>
                </tr>
              </thead>
              <tbody>
                {experiments.map(exp => (
                  <tr key={exp.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                    <td style={tdStyle}>
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{exp.name}</div>
                      {exp.hypothesis && <div style={{ fontSize: 11, color: "#6b7280", maxWidth: 280 }}>{exp.hypothesis.slice(0, 80)}{exp.hypothesis.length > 80 ? "…" : ""}</div>}
                    </td>
                    <td style={tdStyle}>
                      <span style={{ background: exp.mode === "CONTROLLED" ? "#ede9fe" : "#fef3c7", color: exp.mode === "CONTROLLED" ? "#5b21b6" : "#92400e", borderRadius: 4, padding: "2px 8px", fontSize: 11, fontWeight: 700 }}>
                        {exp.mode}
                      </span>
                    </td>
                    <td style={tdStyle}><StatusBadge status={exp.status} /></td>
                    <td style={tdStyle}><EvalBadge state={exp.evaluation_state} /></td>
                    <td style={{ ...tdStyle, fontSize: 12, color: "#6b7280" }}>{exp.primary_metric ?? "—"}</td>
                    <td style={{ ...tdStyle, fontSize: 12, textAlign: "center" }}>{exp.variants?.length ?? 0}</td>
                    <td style={{ ...tdStyle, fontSize: 12, color: "#6b7280" }}>
                      {exp.created_at ? new Date(exp.created_at).toLocaleDateString("pt-BR") : "—"}
                    </td>
                    <td style={tdStyle}>
                      <Link href={`/experiments/${exp.id}`} style={{ color: "#3b82f6", fontSize: 12, textDecoration: "none", fontWeight: 600 }}>
                        Ver detalhes →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p style={{ fontSize: 11, color: "#9ca3af", marginTop: 12 }}>{total} experimento(s) total.</p>
      </div>
    </div>
  );
}

const thStyle: React.CSSProperties = { textAlign: "left", padding: "10px 12px", fontWeight: 700, fontSize: 12, color: "#6b7280" };
const tdStyle: React.CSSProperties = { padding: "10px 12px", verticalAlign: "top" };
