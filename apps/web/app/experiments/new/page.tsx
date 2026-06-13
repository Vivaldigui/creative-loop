"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Nav } from "@/components/Nav";
import { api } from "@/lib/api";

export default function NewExperimentPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    name: "",
    mode: "EXPLORATORY",
    hypothesis: "",
    primary_variable: "",
    primary_metric: "ctr",
    objective: "",
    placement: "",
    planned_budget: "",
    currency: "BRL",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function set(field: string, value: string) {
    setForm(prev => ({ ...prev, [field]: value }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) { setError("Nome é obrigatório."); return; }
    if (form.mode === "CONTROLLED" && !form.primary_variable.trim()) {
      setError("Experimentos CONTROLLED exigem primary_variable."); return;
    }

    setLoading(true);
    setError("");
    try {
      const payload: Record<string, unknown> = {
        name: form.name.trim(),
        mode: form.mode,
        hypothesis: form.hypothesis.trim() || null,
        primary_variable: form.primary_variable.trim() || null,
        primary_metric: form.primary_metric || null,
        objective: form.objective.trim() || null,
        placement: form.placement.trim() || null,
        currency: form.currency,
        planned_budget: form.planned_budget ? Number(form.planned_budget) : null,
        variants: [],
      };
      const exp = await api.experiments.create(payload);
      router.push(`/experiments/${exp.id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", background: "#f5f5f5" }}>
      <Nav />
      <div style={{ maxWidth: 680, margin: "0 auto", padding: "24px 16px" }}>
        <div style={{ marginBottom: 8 }}>
          <Link href="/experiments" style={{ color: "#6b7280", fontSize: 12, textDecoration: "none" }}>← Experimentos</Link>
        </div>
        <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Novo Experimento</h1>
        <p style={{ color: "#6b7280", fontSize: 13, marginBottom: 20 }}>
          EXPLORATORY: causalidade não é atribuída, estado máximo = promising.<br />
          CONTROLLED: variável única obrigatória, permite winner_candidate.
        </p>

        <div style={{ background: "#fff", borderRadius: 8, border: "1px solid #e5e7eb", padding: "24px" }}>
          <form onSubmit={submit}>
            <Field label="Nome *">
              <input value={form.name} onChange={e => set("name", e.target.value)} style={inputStyle} placeholder="Ex: Teste de headline Produto X" required />
            </Field>

            <Field label="Modo *">
              <div style={{ display: "flex", gap: 10 }}>
                {["EXPLORATORY", "CONTROLLED"].map(m => (
                  <label key={m} style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer", fontSize: 13 }}>
                    <input type="radio" name="mode" value={m} checked={form.mode === m} onChange={() => set("mode", m)} />
                    <span style={{ fontWeight: form.mode === m ? 700 : 400 }}>{m}</span>
                  </label>
                ))}
              </div>
              {form.mode === "CONTROLLED" && (
                <div style={{ marginTop: 6, fontSize: 11, color: "#713f12", background: "#fef9c3", padding: "4px 8px", borderRadius: 4 }}>
                  CONTROLLED: só uma variável pode ser alterada entre variantes.
                </div>
              )}
            </Field>

            <Field label="Hipótese">
              <textarea value={form.hypothesis} onChange={e => set("hypothesis", e.target.value)} style={{ ...inputStyle, height: 80, resize: "vertical" }} placeholder="Se alterarmos X, esperamos Y porque Z..." />
            </Field>

            <Field label={`Variável Principal${form.mode === "CONTROLLED" ? " *" : ""}`}>
              <input value={form.primary_variable} onChange={e => set("primary_variable", e.target.value)} style={inputStyle} placeholder="Ex: headline, imagem, CTA" required={form.mode === "CONTROLLED"} />
            </Field>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <Field label="Métrica Principal">
                <select value={form.primary_metric} onChange={e => set("primary_metric", e.target.value)} style={inputStyle}>
                  {["ctr", "cvr", "roas", "cpc", "cpm", "purchases", "leads"].map(m => (
                    <option key={m} value={m}>{m.toUpperCase()}</option>
                  ))}
                </select>
              </Field>
              <Field label="Objetivo">
                <input value={form.objective} onChange={e => set("objective", e.target.value)} style={inputStyle} placeholder="Ex: CONVERSIONS, REACH" />
              </Field>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
              <Field label="Placement">
                <input value={form.placement} onChange={e => set("placement", e.target.value)} style={inputStyle} placeholder="Ex: FEED, STORY" />
              </Field>
              <Field label="Orçamento Planejado">
                <input type="number" value={form.planned_budget} onChange={e => set("planned_budget", e.target.value)} style={inputStyle} placeholder="Ex: 500.00" step="0.01" min="0" />
              </Field>
              <Field label="Moeda">
                <select value={form.currency} onChange={e => set("currency", e.target.value)} style={inputStyle}>
                  {["BRL", "USD", "EUR"].map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </Field>
            </div>

            {error && (
              <div style={{ background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: 6, padding: "10px 12px", marginBottom: 12, color: "#991b1b", fontSize: 12 }}>
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              style={{ width: "100%", padding: "10px", background: loading ? "#9ca3af" : "#3b82f6", color: "#fff", border: "none", borderRadius: 6, cursor: loading ? "not-allowed" : "pointer", fontWeight: 700, fontSize: 14, marginTop: 8 }}
            >
              {loading ? "Criando…" : "Criar Experimento (Draft)"}
            </button>
          </form>
        </div>

        <p style={{ fontSize: 11, color: "#9ca3af", marginTop: 12 }}>
          O experimento é criado como draft. Adicione variantes e inicie quando estiver pronto.
        </p>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#374151", marginBottom: 4 }}>{label}</label>
      {children}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%", padding: "8px 10px", border: "1px solid #d1d5db", borderRadius: 6,
  fontSize: 13, outline: "none", boxSizing: "border-box", background: "#fff",
};
