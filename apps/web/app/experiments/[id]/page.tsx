"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Nav } from "@/components/Nav";
import { api, DecisionOut, EvaluationOut, ExperimentOut, SuggestionOut, VariantSnapshotOut } from "@/lib/api";

// ── Helpers ────────────────────────────────────────────────────────────────────

function Badge({ label, bg, text }: { label: string; bg: string; text: string }) {
  return (
    <span style={{ background: bg, color: text, borderRadius: 4, padding: "2px 8px", fontSize: 11, fontWeight: 700, textTransform: "uppercase" }}>
      {label}
    </span>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 28 }}>
      <h2 style={{ fontSize: 15, fontWeight: 700, marginBottom: 12, color: "#1f2937", borderBottom: "1px solid #e5e7eb", paddingBottom: 6 }}>{title}</h2>
      {children}
    </div>
  );
}

// ── Actions panel ─────────────────────────────────────────────────────────────

function ActionPanel({ exp, onRefresh }: { exp: ExperimentOut; onRefresh: () => void }) {
  const [loading, setLoading] = useState<string | null>(null);
  const [err, setErr] = useState("");

  async function doAction(name: string, action: () => Promise<unknown>) {
    if (!confirm(`Confirma: ${name}?`)) return;
    setLoading(name);
    setErr("");
    try {
      await action();
      onRefresh();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(null);
    }
  }

  return (
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
      {exp.status === "draft" && (
        <button
          disabled={loading === "start"}
          onClick={() => doAction("Iniciar experimento", () => api.experiments.start(exp.id))}
          style={btnStyle("#059669", loading === "start")}
        >
          {loading === "start" ? "Iniciando…" : "▶ Iniciar"}
        </button>
      )}
      {exp.status === "running" && (
        <>
          <button
            disabled={loading === "evaluate"}
            onClick={() => doAction("Avaliar experimento", () => api.experiments.evaluate(exp.id, "Avaliação manual"))}
            style={btnStyle("#3b82f6", loading === "evaluate")}
          >
            {loading === "evaluate" ? "Avaliando…" : "Avaliar"}
          </button>
          <button
            disabled={loading === "stop"}
            onClick={() => {
              const reason = prompt("Motivo da parada:");
              if (!reason) return;
              setLoading("stop");
              setErr("");
              api.experiments.stop(exp.id, reason).then(onRefresh).catch(e => setErr(String(e))).finally(() => setLoading(null));
            }}
            style={btnStyle("#f59e0b", loading === "stop")}
          >
            {loading === "stop" ? "Parando…" : "Parar"}
          </button>
        </>
      )}
      {exp.status === "evaluating" && (
        <button
          disabled={loading === "complete"}
          onClick={() => doAction("Completar experimento", () => api.experiments.complete(exp.id))}
          style={btnStyle("#7c3aed", loading === "complete")}
        >
          {loading === "complete" ? "Completando…" : "Completar"}
        </button>
      )}
      {["completed", "stopped"].includes(exp.status) && (
        <button
          disabled={loading === "suggest"}
          onClick={() => doAction("Sugerir próxima rodada", () => api.experiments.suggestNextRound(exp.id))}
          style={btnStyle("#0891b2", loading === "suggest")}
        >
          {loading === "suggest" ? "Gerando…" : "Sugerir Próxima Rodada"}
        </button>
      )}
      {err && <span style={{ color: "#dc2626", fontSize: 11 }}>{err}</span>}
    </div>
  );
}

function btnStyle(color: string, disabled: boolean): React.CSSProperties {
  return { padding: "7px 14px", background: disabled ? "#9ca3af" : color, color: "#fff", border: "none", borderRadius: 6, cursor: disabled ? "not-allowed" : "pointer", fontWeight: 600, fontSize: 12 };
}

// ── Main ──────────────────────────────────────────────────────────────────────

export default function ExperimentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [exp, setExp] = useState<ExperimentOut | null>(null);
  const [evaluations, setEvaluations] = useState<EvaluationOut[]>([]);
  const [snapshots, setSnapshots] = useState<VariantSnapshotOut[]>([]);
  const [decisions, setDecisions] = useState<DecisionOut[]>([]);
  const [suggestions, setSuggestions] = useState<SuggestionOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError("");
    try {
      const [expData, evalsData, snapsData, decsData, sugsData] = await Promise.all([
        api.experiments.get(id),
        api.experiments.evaluations(id).catch(() => []),
        api.experiments.metrics(id).catch(() => []),
        api.experiments.decisions(id).catch(() => []),
        api.experiments.suggestions(id).catch(() => []),
      ]);
      setExp(expData);
      setEvaluations(evalsData);
      setSnapshots(snapsData);
      setDecisions(decsData);
      setSuggestions(sugsData);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div style={{ minHeight: "100vh", background: "#f5f5f5" }}><Nav /><p style={{ padding: 32, color: "#9ca3af" }}>Carregando…</p></div>;
  if (error || !exp) return <div style={{ minHeight: "100vh", background: "#f5f5f5" }}><Nav /><p style={{ padding: 32, color: "#dc2626" }}>{error || "Experimento não encontrado."}</p></div>;

  const latestEval = evaluations[0] ?? null;

  return (
    <div style={{ minHeight: "100vh", background: "#f5f5f5" }}>
      <Nav />
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "24px 16px" }}>
        <div style={{ marginBottom: 4 }}>
          <Link href="/experiments" style={{ color: "#6b7280", fontSize: 12, textDecoration: "none" }}>← Experimentos</Link>
        </div>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 20, flexWrap: "wrap", gap: 12 }}>
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 6 }}>{exp.name}</h1>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <Badge label={exp.status} bg={exp.status === "running" ? "#dcfce7" : "#f3f4f6"} text={exp.status === "running" ? "#166534" : "#374151"} />
              <Badge label={exp.mode} bg={exp.mode === "CONTROLLED" ? "#ede9fe" : "#fef3c7"} text={exp.mode === "CONTROLLED" ? "#5b21b6" : "#92400e"} />
              {latestEval && <Badge label={latestEval.evaluation_state.replace(/_/g, " ")} bg="#dbeafe" text="#1e40af" />}
              {exp.is_fictitious && <Badge label="FICTÍCIO" bg="#fef9c3" text="#713f12" />}
            </div>
          </div>
          <ActionPanel exp={exp} onRefresh={load} />
        </div>

        {/* Info grid */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 12, marginBottom: 24 }}>
          {[
            ["Objetivo", exp.objective ?? "—"],
            ["Métrica Principal", exp.primary_metric ?? "—"],
            ["Placement", exp.placement ?? "—"],
            ["Orçamento Planejado", exp.planned_budget != null ? `${exp.currency ?? ""} ${exp.planned_budget.toFixed(2)}` : "—"],
            ["Início da janela", exp.window_start ? new Date(exp.window_start).toLocaleDateString("pt-BR") : "—"],
            ["Fim da janela", exp.window_end ? new Date(exp.window_end).toLocaleDateString("pt-BR") : "—"],
            ["Iniciado em", exp.started_at ? new Date(exp.started_at).toLocaleDateString("pt-BR") : "—"],
            ["Encerrado em", exp.ended_at ? new Date(exp.ended_at).toLocaleDateString("pt-BR") : "—"],
          ].map(([k, v]) => (
            <div key={k} style={{ background: "#fff", borderRadius: 8, border: "1px solid #e5e7eb", padding: "12px 14px" }}>
              <div style={{ fontSize: 11, color: "#6b7280", fontWeight: 600, textTransform: "uppercase", marginBottom: 4 }}>{k}</div>
              <div style={{ fontSize: 13, fontWeight: 600, color: "#1f2937" }}>{v}</div>
            </div>
          ))}
        </div>

        {exp.hypothesis && (
          <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 8, padding: "12px 16px", marginBottom: 20, fontSize: 13, color: "#166534" }}>
            <strong>Hipótese:</strong> {exp.hypothesis}
          </div>
        )}

        {/* Variants */}
        <Section title={`Variantes (${exp.variants?.length ?? 0})`}>
          {(exp.variants ?? []).length === 0 ? (
            <p style={{ color: "#9ca3af", fontSize: 13 }}>Nenhuma variante.</p>
          ) : (
            <div style={{ display: "grid", gap: 10 }}>
              {exp.variants.map(v => (
                <div key={v.id} style={{ background: "#fff", borderRadius: 8, border: "1px solid #e5e7eb", padding: "12px 16px", display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 13 }}>{v.name}</div>
                    <div style={{ fontSize: 11, color: "#6b7280", marginTop: 2 }}>
                      {v.variant_role && <span style={{ marginRight: 8 }}>Papel: {v.variant_role}</span>}
                      {v.hypothesis && <span>{v.hypothesis.slice(0, 80)}</span>}
                    </div>
                  </div>
                  <div style={{ fontSize: 11, color: "#6b7280", textAlign: "right" }}>
                    {v.allocated_budget != null && <div>Budget: {exp.currency} {v.allocated_budget.toFixed(2)}</div>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Section>

        {/* Latest evaluation */}
        {latestEval && (
          <Section title="Última Avaliação">
            <div style={{ background: "#fff", borderRadius: 8, border: "1px solid #e5e7eb", padding: "16px" }}>
              <div style={{ display: "flex", gap: 16, marginBottom: 12, flexWrap: "wrap" }}>
                <div><span style={{ fontSize: 11, color: "#6b7280" }}>Estado</span><div style={{ fontWeight: 700 }}>{latestEval.evaluation_state.replace(/_/g, " ")}</div></div>
                <div><span style={{ fontSize: 11, color: "#6b7280" }}>Confiança</span><div style={{ fontWeight: 700 }}>{latestEval.confidence != null ? `${(latestEval.confidence * 100).toFixed(1)}%` : "—"}</div></div>
                <div><span style={{ fontSize: 11, color: "#6b7280" }}>Causalidade</span><div style={{ fontWeight: 700, color: latestEval.causal_attribution ? "#166534" : "#9ca3af" }}>{latestEval.causal_attribution ? "Sim" : "Não (correlação)"}</div></div>
                <div><span style={{ fontSize: 11, color: "#6b7280" }}>Engine v</span><div style={{ fontWeight: 700 }}>{latestEval.engine_version ?? "—"}</div></div>
                <div><span style={{ fontSize: 11, color: "#6b7280" }}>Avaliado em</span><div style={{ fontWeight: 700 }}>{latestEval.evaluated_at ? new Date(latestEval.evaluated_at).toLocaleDateString("pt-BR") : "—"}</div></div>
              </div>
              {(latestEval.limitations ?? []).length > 0 && (
                <div style={{ background: "#fffbeb", borderRadius: 6, padding: "8px 12px", fontSize: 12, color: "#713f12" }}>
                  <strong>Limitações:</strong>
                  <ul style={{ margin: "4px 0 0 16px", padding: 0 }}>
                    {latestEval.limitations!.map((l, i) => <li key={i}>{l}</li>)}
                  </ul>
                </div>
              )}
            </div>
          </Section>
        )}

        {/* Snapshots */}
        {snapshots.length > 0 && (
          <Section title={`Métricas de Variantes (${snapshots.length} snapshots)`}>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, background: "#fff", borderRadius: 8, border: "1px solid #e5e7eb" }}>
                <thead>
                  <tr style={{ background: "#f9fafb", borderBottom: "2px solid #e5e7eb" }}>
                    {["Variante", "Data Início", "Data Fim", "Impressões", "Cliques", "Gasto", "CTR", "CVR", "ROAS", "Conversões", "Matured"].map(h => (
                      <th key={h} style={{ padding: "8px 10px", textAlign: "left", fontWeight: 700, fontSize: 11, color: "#6b7280" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {snapshots.slice(0, 20).map(s => (
                    <tr key={s.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                      <td style={{ padding: "8px 10px", fontFamily: "monospace", fontSize: 11 }}>{s.variant_id.slice(0, 8)}…</td>
                      <td style={{ padding: "8px 10px" }}>{s.date_start}</td>
                      <td style={{ padding: "8px 10px" }}>{s.date_stop}</td>
                      <td style={{ padding: "8px 10px" }}>{s.impressions?.toLocaleString("pt-BR") ?? "—"}</td>
                      <td style={{ padding: "8px 10px" }}>{s.clicks?.toLocaleString("pt-BR") ?? "—"}</td>
                      <td style={{ padding: "8px 10px" }}>{s.spend != null ? `R$ ${s.spend.toFixed(2)}` : "—"}</td>
                      <td style={{ padding: "8px 10px" }}>{s.ctr != null ? `${s.ctr.toFixed(2)}%` : "—"}</td>
                      <td style={{ padding: "8px 10px" }}>{s.cvr != null ? `${(s.cvr * 100).toFixed(2)}%` : "—"}</td>
                      <td style={{ padding: "8px 10px" }}>{s.roas != null ? s.roas.toFixed(2) : "—"}</td>
                      <td style={{ padding: "8px 10px" }}>{s.purchases ?? s.leads ?? "—"}</td>
                      <td style={{ padding: "8px 10px" }}>
                        <span style={{ color: s.is_matured ? "#166534" : "#9ca3af", fontWeight: 600 }}>{s.is_matured ? "✓" : "—"}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {snapshots.length > 20 && <p style={{ fontSize: 11, color: "#9ca3af", marginTop: 4 }}>Exibindo 20 de {snapshots.length} snapshots.</p>}
            </div>
          </Section>
        )}

        {/* Decisions */}
        {decisions.length > 0 && (
          <Section title={`Decisões (${decisions.length})`}>
            <div style={{ display: "grid", gap: 10 }}>
              {decisions.map(d => (
                <div key={d.id} style={{ background: "#fff", borderRadius: 8, border: "1px solid #e5e7eb", padding: "12px 16px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                    <span style={{ fontWeight: 600, fontSize: 13 }}>{d.suggested_action ?? "—"}</span>
                    <span style={{ fontSize: 11, color: "#6b7280" }}>{d.decided_at ? new Date(d.decided_at).toLocaleDateString("pt-BR") : "—"}</span>
                  </div>
                  {d.recommendation && <p style={{ fontSize: 12, color: "#374151", margin: 0 }}>{d.recommendation}</p>}
                  {d.executed_action && <p style={{ fontSize: 11, color: "#6b7280", margin: "4px 0 0" }}>Executado: {d.executed_action}</p>}
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* Suggestions */}
        {suggestions.length > 0 && (
          <Section title={`Sugestões de Próxima Rodada (${suggestions.length})`}>
            <div style={{ display: "grid", gap: 10 }}>
              {suggestions.map(s => (
                <div key={s.id} style={{ background: "#fff", borderRadius: 8, border: "1px solid #e5e7eb", padding: "12px 16px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                    <span style={{ background: s.status === "pending_approval" ? "#fef9c3" : s.status === "approved" ? "#dcfce7" : "#fee2e2", color: s.status === "pending_approval" ? "#713f12" : s.status === "approved" ? "#166534" : "#991b1b", borderRadius: 4, padding: "2px 8px", fontSize: 11, fontWeight: 700 }}>{s.status}</span>
                    <span style={{ fontSize: 11, color: "#6b7280" }}>{s.diversity_score != null ? `Diversidade: ${(s.diversity_score * 100).toFixed(0)}%` : ""}</span>
                  </div>
                  {s.hypothesis && <p style={{ fontSize: 12, color: "#374151", margin: "0 0 6px" }}><strong>Hipótese:</strong> {s.hypothesis}</p>}
                  <Link href={`/suggestions/${s.id}`} style={{ fontSize: 12, color: "#3b82f6", textDecoration: "none" }}>Ver sugestão →</Link>
                </div>
              ))}
            </div>
          </Section>
        )}

        <p style={{ fontSize: 11, color: "#9ca3af" }}>ID: {exp.id}</p>
      </div>
    </div>
  );
}
