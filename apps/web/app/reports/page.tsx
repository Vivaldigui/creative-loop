"use client";

import { useEffect, useState } from "react";
import { Nav } from "@/components/Nav";
import { api, AlertItem, DailyReportOut, WeeklyReportOut } from "@/lib/api";

const ALERT_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  critical: { bg: "#fef2f2", text: "#991b1b", border: "#fca5a5" },
  warning: { bg: "#fffbeb", text: "#713f12", border: "#fcd34d" },
  info: { bg: "#eff6ff", text: "#1e40af", border: "#bfdbfe" },
};

function AlertCard({ alert }: { alert: AlertItem }) {
  const c = ALERT_COLORS[alert.level] ?? ALERT_COLORS.info;
  return (
    <div style={{ background: c.bg, border: `1px solid ${c.border}`, borderRadius: 6, padding: "10px 14px", marginBottom: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
        <span style={{ fontWeight: 700, fontSize: 11, color: c.text, textTransform: "uppercase" }}>{alert.level} — {alert.code}</span>
        {alert.entity_type && <span style={{ fontSize: 10, color: "#9ca3af" }}>{alert.entity_type}</span>}
      </div>
      <p style={{ margin: 0, fontSize: 13, color: c.text }}>{alert.message}</p>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number | null }) {
  return (
    <div style={{ background: "#fff", borderRadius: 8, border: "1px solid #e5e7eb", padding: "12px 16px" }}>
      <div style={{ fontSize: 11, color: "#6b7280", fontWeight: 600, textTransform: "uppercase", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: "#1f2937" }}>{value ?? "—"}</div>
    </div>
  );
}

export default function ReportsPage() {
  const [tab, setTab] = useState<"daily" | "weekly">("daily");
  const [daily, setDaily] = useState<DailyReportOut | null>(null);
  const [weekly, setWeekly] = useState<WeeklyReportOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadDaily() {
    setLoading(true); setError("");
    try { setDaily(await api.reports.daily()); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  }

  async function loadWeekly() {
    setLoading(true); setError("");
    try { setWeekly(await api.reports.weekly()); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  }

  useEffect(() => {
    if (tab === "daily" && !daily) loadDaily();
    if (tab === "weekly" && !weekly) loadWeekly();
  }, [tab]);

  return (
    <div style={{ minHeight: "100vh", background: "#f5f5f5" }}>
      <Nav />
      <div style={{ maxWidth: 1000, margin: "0 auto", padding: "24px 16px" }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Relatórios</h1>
        <p style={{ color: "#6b7280", fontSize: 13, marginBottom: 20 }}>
          Fase 7 — Relatórios operacionais diários e semanais. Inclui alertas de gasto anômalo, anúncios rejeitados e problemas em experimentos.
        </p>

        <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
          {(["daily", "weekly"] as const).map(t => (
            <button key={t} onClick={() => setTab(t)} style={{
              padding: "8px 20px", border: "1px solid #d1d5db", borderRadius: 6,
              background: tab === t ? "#1a1a2e" : "#fff",
              color: tab === t ? "#fff" : "#374151",
              fontSize: 14, cursor: "pointer", fontWeight: tab === t ? 700 : 400,
            }}>{t === "daily" ? "Diário" : "Semanal"}</button>
          ))}
          <button onClick={() => { if (tab === "daily") loadDaily(); else loadWeekly(); }} style={{ marginLeft: "auto", padding: "8px 14px", border: "1px solid #d1d5db", borderRadius: 6, background: "#f3f4f6", fontSize: 13, cursor: "pointer" }}>
            Atualizar
          </button>
        </div>

        {error && (
          <div style={{ background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: 6, padding: 12, marginBottom: 16, color: "#991b1b", fontSize: 12 }}>{error}</div>
        )}

        {loading && <p style={{ color: "#9ca3af", fontSize: 13 }}>Carregando…</p>}

        {/* Daily report */}
        {tab === "daily" && daily && !loading && (
          <div>
            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 8 }}>
                Período: {daily.period_start} → {daily.period_end} • Gerado em: {new Date(daily.generated_at).toLocaleString("pt-BR")}
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 12 }}>
                <Stat label="Gasto Total" value={daily.total_spend != null ? `${daily.currency} ${daily.total_spend.toFixed(2)}` : null} />
                <Stat label="Experimentos Ativos" value={daily.running_experiments} />
                <Stat label="Em Avaliação" value={daily.evaluating_experiments} />
                <Stat label="Alertas" value={daily.alerts.length} />
                <Stat label="Anúncios Rejeitados" value={daily.rejected_ads.length} />
                <Stat label="Sem Conversão" value={daily.ads_without_conversions.length} />
              </div>
            </div>

            {daily.alerts.length > 0 && (
              <div style={{ marginBottom: 20 }}>
                <h2 style={{ fontSize: 15, fontWeight: 700, marginBottom: 10, color: "#1f2937" }}>
                  Alertas ({daily.alerts.length})
                </h2>
                {daily.alerts.map((a, i) => <AlertCard key={i} alert={a} />)}
              </div>
            )}

            {daily.experiments_with_issues.length > 0 && (
              <div style={{ marginBottom: 20 }}>
                <h2 style={{ fontSize: 15, fontWeight: 700, marginBottom: 10, color: "#1f2937" }}>Experimentos com Problemas</h2>
                <div style={{ background: "#fff", borderRadius: 8, border: "1px solid #e5e7eb", overflow: "hidden" }}>
                  {daily.experiments_with_issues.map((e: Record<string, unknown>, i) => (
                    <div key={i} style={{ padding: "10px 14px", borderBottom: "1px solid #f3f4f6", fontSize: 13 }}>
                      <strong>{String(e.name ?? e.id)}</strong> — <span style={{ color: "#6b7280" }}>{String(e.state)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {daily.ads_without_conversions.length > 0 && (
              <div style={{ marginBottom: 20 }}>
                <h2 style={{ fontSize: 15, fontWeight: 700, marginBottom: 10, color: "#1f2937" }}>Variantes Sem Conversão</h2>
                <div style={{ background: "#fff", borderRadius: 8, border: "1px solid #e5e7eb", overflow: "hidden" }}>
                  {daily.ads_without_conversions.map((a: Record<string, unknown>, i) => (
                    <div key={i} style={{ padding: "10px 14px", borderBottom: "1px solid #f3f4f6", fontSize: 12, display: "flex", justifyContent: "space-between" }}>
                      <span style={{ fontFamily: "monospace" }}>{String(a.variant_id).slice(0, 12)}…</span>
                      <span>R$ {Number(a.spend).toFixed(2)} gasto</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {daily.alerts.length === 0 && daily.experiments_with_issues.length === 0 && (
              <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 8, padding: 24, textAlign: "center", color: "#166534", fontSize: 14 }}>
                ✓ Nenhum alerta crítico. Tudo dentro do esperado.
              </div>
            )}
          </div>
        )}

        {/* Weekly report */}
        {tab === "weekly" && weekly && !loading && (
          <div>
            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 8 }}>
                Semana: {weekly.report_week} • {weekly.period_start} → {weekly.period_end} • Gerado em: {new Date(weekly.generated_at).toLocaleString("pt-BR")}
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 12 }}>
                <Stat label="Gasto Semanal" value={weekly.total_spend != null ? `${weekly.currency} ${weekly.total_spend.toFixed(2)}` : null} />
                <Stat label="Experimentos Concluídos" value={weekly.completed_experiments.length} />
                <Stat label="Padrões Promissores" value={weekly.promising_patterns.length} />
                <Stat label="Padrões Rejeitados" value={weekly.rejected_patterns.length} />
                <Stat label="Novos Aprendizados" value={weekly.new_learnings.length} />
                <Stat label="Sugestões Geradas" value={weekly.suggestions.length} />
              </div>
            </div>

            {weekly.completed_experiments.length > 0 && (
              <div style={{ marginBottom: 20 }}>
                <h2 style={{ fontSize: 15, fontWeight: 700, marginBottom: 10, color: "#1f2937" }}>Experimentos Concluídos na Semana</h2>
                <div style={{ background: "#fff", borderRadius: 8, border: "1px solid #e5e7eb", overflow: "hidden" }}>
                  {weekly.completed_experiments.map((e: Record<string, unknown>, i) => (
                    <div key={i} style={{ padding: "12px 16px", borderBottom: "1px solid #f3f4f6", display: "flex", justifyContent: "space-between" }}>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 13 }}>{String(e.name ?? e.id)}</div>
                        <div style={{ fontSize: 11, color: "#6b7280" }}>Modo: {String(e.mode ?? "—")} · Avaliação: {String(e.evaluation_state ?? "—")}</div>
                      </div>
                      {e.confidence != null && (
                        <div style={{ fontSize: 12, color: "#374151" }}>Confiança: {(Number(e.confidence) * 100).toFixed(0)}%</div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {weekly.new_learnings.length > 0 && (
              <div style={{ marginBottom: 20 }}>
                <h2 style={{ fontSize: 15, fontWeight: 700, marginBottom: 10, color: "#1f2937" }}>Novos Aprendizados</h2>
                <div style={{ background: "#fff", borderRadius: 8, border: "1px solid #e5e7eb", overflow: "hidden" }}>
                  {weekly.new_learnings.map((l: Record<string, unknown>, i) => (
                    <div key={i} style={{ padding: "10px 16px", borderBottom: "1px solid #f3f4f6" }}>
                      <div style={{ fontSize: 13 }}>{String(l.pattern)}</div>
                      <div style={{ fontSize: 11, color: "#6b7280", marginTop: 2 }}>
                        Status: {String(l.status)} · Confiança: {l.confidence != null ? `${(Number(l.confidence) * 100).toFixed(0)}%` : "—"}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {weekly.completed_experiments.length === 0 && weekly.new_learnings.length === 0 && (
              <div style={{ background: "#f9fafb", border: "1px solid #e5e7eb", borderRadius: 8, padding: 24, textAlign: "center", color: "#6b7280", fontSize: 14 }}>
                Nenhuma atividade relevante na semana.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
