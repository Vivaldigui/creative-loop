"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Nav } from "@/components/Nav";
import {
  api,
  GeneratedCreativeOut,
  GuardCheckResult,
  DryRunResponse,
  ValidateResponse,
} from "@/lib/api";

// ── Helpers ────────────────────────────────────────────────────────────────

function severityColor(severity: string) {
  if (severity === "blocked") return "#ef4444";
  if (severity === "warning") return "#f59e0b";
  return "#22c55e";
}

function CheckRow({ check }: { check: GuardCheckResult }) {
  return (
    <div
      style={{
        display: "flex",
        gap: 8,
        alignItems: "flex-start",
        padding: "6px 0",
        borderBottom: "1px solid #f0f0f0",
      }}
    >
      <span
        style={{
          display: "inline-block",
          width: 10,
          height: 10,
          borderRadius: "50%",
          background: severityColor(check.severity),
          marginTop: 4,
          flexShrink: 0,
        }}
      />
      <div style={{ flex: 1 }}>
        <span style={{ fontWeight: 600, fontSize: 12, fontFamily: "monospace" }}>{check.code}</span>
        {check.detail && (
          <p style={{ margin: "2px 0 0", fontSize: 12, color: "#555" }}>{check.detail}</p>
        )}
      </div>
      <span
        style={{
          fontSize: 10,
          fontWeight: 700,
          color: severityColor(check.severity),
          textTransform: "uppercase",
        }}
      >
        {check.severity}
      </span>
    </div>
  );
}

function JsonViewer({ data, label }: { data: unknown; label: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ marginBottom: 8 }}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          background: "#f3f4f6",
          border: "1px solid #d1d5db",
          borderRadius: 4,
          padding: "4px 10px",
          cursor: "pointer",
          fontSize: 12,
          fontWeight: 600,
        }}
      >
        {open ? "▼" : "▶"} {label}
      </button>
      {open && (
        <pre
          style={{
            marginTop: 4,
            background: "#1e1e2e",
            color: "#cdd6f4",
            borderRadius: 6,
            padding: 12,
            fontSize: 11,
            overflow: "auto",
            maxHeight: 400,
          }}
        >
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  );
}

// ── DRY_RUN Banner ─────────────────────────────────────────────────────────

function DryRunBanner() {
  return (
    <div
      style={{
        background: "#fef3c7",
        border: "2px solid #f59e0b",
        borderRadius: 8,
        padding: "12px 16px",
        marginBottom: 24,
        display: "flex",
        alignItems: "center",
        gap: 10,
      }}
    >
      <span style={{ fontSize: 20 }}>⚠️</span>
      <div>
        <strong style={{ color: "#92400e" }}>MODO DRY_RUN ATIVO</strong>
        <p style={{ margin: "2px 0 0", fontSize: 12, color: "#78350f" }}>
          Nenhuma operação real será realizada. Nenhuma campanha, conjunto ou anúncio será criado na
          Meta. Nenhum gasto ocorrerá. Os IDs exibidos são simulados e não existem na plataforma Meta.
        </p>
      </div>
    </div>
  );
}

// ── Placeholder Warning ─────────────────────────────────────────────────────

function PlaceholderWarning({ placeholders }: { placeholders: string[] }) {
  if (placeholders.length === 0) return null;
  return (
    <div
      style={{
        background: "#fef9c3",
        border: "1px solid #fde047",
        borderRadius: 6,
        padding: "8px 12px",
        marginTop: 12,
        fontSize: 12,
      }}
    >
      <strong>Configurações pendentes (bloqueiam publicação real na Fase 6):</strong>
      <ul style={{ margin: "4px 0 0 16px", padding: 0 }}>
        {placeholders.map((p) => (
          <li key={p} style={{ fontFamily: "monospace" }}>
            {p}
          </li>
        ))}
      </ul>
    </div>
  );
}

// ── Simulated IDs Panel ─────────────────────────────────────────────────────

function SimulatedIds({ response }: { response: DryRunResponse["simulated_response"] }) {
  if (!response) return null;
  const ids = [
    { label: "Campaign ID", value: response.simulated_campaign_id },
    { label: "Ad Set ID", value: response.simulated_adset_id },
    { label: "Image Hash", value: response.simulated_image_hash },
    { label: "Ad Creative ID", value: response.simulated_ad_creative_id },
    { label: "Ad ID", value: response.simulated_ad_id },
  ];
  return (
    <div
      style={{
        background: "#f0fdf4",
        border: "1px solid #86efac",
        borderRadius: 8,
        padding: 16,
        marginTop: 16,
      }}
    >
      <h4 style={{ margin: "0 0 8px", color: "#166534" }}>
        IDs Simulados{" "}
        <span
          style={{
            background: "#bbf7d0",
            color: "#166534",
            fontSize: 10,
            fontWeight: 700,
            borderRadius: 3,
            padding: "1px 5px",
            marginLeft: 4,
          }}
        >
          FICTÍCIOS — NÃO EXISTEM NA META
        </span>
      </h4>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        {ids.map(({ label, value }) => (
          <div key={label} style={{ background: "#fff", borderRadius: 4, padding: "6px 10px" }}>
            <div style={{ fontSize: 10, color: "#6b7280", fontWeight: 600 }}>{label}</div>
            <div style={{ fontFamily: "monospace", fontSize: 11, color: "#111", wordBreak: "break-all" }}>
              {value}
            </div>
          </div>
        ))}
      </div>
      {response.placeholders_present.length > 0 && (
        <PlaceholderWarning placeholders={response.placeholders_present} />
      )}
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────

export default function PublishPage() {
  const [creatives, setCreatives] = useState<GeneratedCreativeOut[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [loadingCreatives, setLoadingCreatives] = useState(true);

  // Form state
  const [campaignName, setCampaignName] = useState("");
  const [adsetName, setAdsetName] = useState("");
  const [adName, setAdName] = useState("");
  const [objective, setObjective] = useState("OUTCOME_TRAFFIC");
  const [budgetBrl, setBudgetBrl] = useState("");
  const [headline, setHeadline] = useState("");
  const [bodyText, setBodyText] = useState("");
  const [ctaType, setCtaType] = useState("SHOP_NOW");
  const [landingUrl, setLandingUrl] = useState("");
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID());

  // Results
  const [validateResult, setValidateResult] = useState<ValidateResponse | null>(null);
  const [dryRunResult, setDryRunResult] = useState<DryRunResponse | null>(null);
  const [history, setHistory] = useState<DryRunResponse[]>([]);

  const [validating, setValidating] = useState(false);
  const [simulating, setSimulating] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.creatives
      .list({ status: "approved", limit: 50 })
      .then((data) => setCreatives(data))
      .catch(() => {})
      .finally(() => setLoadingCreatives(false));
  }, []);

  async function handleValidate() {
    if (!selectedId || !budgetBrl) return;
    setValidating(true);
    setError("");
    setValidateResult(null);
    try {
      const result = await api.publish.validate({
        creative_id: selectedId,
        daily_budget_brl: parseFloat(budgetBrl),
        objective,
        landing_url: landingUrl || undefined,
        campaign_name: campaignName || undefined,
        adset_name: adsetName || undefined,
        ad_name: adName || undefined,
      });
      setValidateResult(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setValidating(false);
    }
  }

  async function handleSimulate() {
    if (!selectedId || !budgetBrl) return;
    setSimulating(true);
    setError("");
    setDryRunResult(null);
    try {
      const result = await api.publish.dryRun({
        creative_id: selectedId,
        idempotency_key: idempotencyKey,
        campaign_name: campaignName || undefined,
        adset_name: adsetName || undefined,
        ad_name: adName || undefined,
        objective,
        daily_budget_brl: parseFloat(budgetBrl),
        headline: headline || undefined,
        body_text: bodyText || undefined,
        cta_type: ctaType,
        landing_url: landingUrl || undefined,
      });
      setDryRunResult(result);
      setHistory((h) => [result, ...h].slice(0, 10));
      // New key for next attempt
      setIdempotencyKey(crypto.randomUUID());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSimulating(false);
    }
  }

  const canValidate = !!selectedId && !!budgetBrl && parseFloat(budgetBrl) > 0;
  const canSimulate = canValidate && validateResult?.passed === true;

  const selected = creatives.find((c) => c.id === selectedId);

  return (
    <div style={{ minHeight: "100vh", background: "#f5f5f5" }}>
      <Nav />
      <div style={{ maxWidth: 900, margin: "0 auto", padding: "24px 16px" }}>
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 4 }}>
          <h1 style={{ fontSize: 22, fontWeight: 700 }}>Publicação Simulada</h1>
          <Link href="/published-ads" style={{ fontSize: 13, color: "#3b82f6" }}>
            Ver anúncios publicados →
          </Link>
        </div>
        <p style={{ color: "#6b7280", fontSize: 13, marginBottom: 20 }}>
          Fase 5 — Simule a publicação de um criativo aprovado sem realizar chamadas reais à Meta.
          Para publicação real (Fase 6), configure <code>DRY_RUN=false</code> e{" "}
          <code>META_WRITE_ENABLED=true</code>.
        </p>

        <DryRunBanner />

        {/* Creative selection */}
        <section
          style={{
            background: "#fff",
            borderRadius: 8,
            padding: 20,
            marginBottom: 16,
            border: "1px solid #e5e7eb",
          }}
        >
          <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 700 }}>
            1. Selecionar criativo aprovado
          </h3>
          {loadingCreatives ? (
            <p style={{ color: "#aaa", fontSize: 13 }}>Carregando criativos…</p>
          ) : creatives.length === 0 ? (
            <p style={{ color: "#ef4444", fontSize: 13 }}>
              Nenhum criativo aprovado encontrado.{" "}
              <Link href="/approvals" style={{ color: "#3b82f6" }}>
                Aprovar criativo
              </Link>
            </p>
          ) : (
            <select
              value={selectedId}
              onChange={(e) => {
                setSelectedId(e.target.value);
                setValidateResult(null);
                setDryRunResult(null);
              }}
              style={{
                width: "100%",
                padding: "8px 10px",
                border: "1px solid #d1d5db",
                borderRadius: 6,
                fontSize: 13,
              }}
            >
              <option value="">— selecione —</option>
              {creatives.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.id.slice(0, 8)}… — {c.status} — {c.provider} —{" "}
                  {c.width}×{c.height}
                </option>
              ))}
            </select>
          )}
          {selected && (
            <p style={{ fontSize: 11, color: "#6b7280", marginTop: 6 }}>
              Status: <strong>{selected.status}</strong> | Provider: {selected.provider} | Hash:{" "}
              {selected.file_hash?.slice(0, 12)}…
            </p>
          )}
        </section>

        {/* Campaign form */}
        <section
          style={{
            background: "#fff",
            borderRadius: 8,
            padding: 20,
            marginBottom: 16,
            border: "1px solid #e5e7eb",
          }}
        >
          <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 700 }}>2. Campanha</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <label style={{ fontSize: 12, fontWeight: 600 }}>
              Nome da campanha
              <input
                value={campaignName}
                onChange={(e) => setCampaignName(e.target.value)}
                placeholder="[DRY_RUN] Campanha teste"
                style={inputStyle}
              />
            </label>
            <label style={{ fontSize: 12, fontWeight: 600 }}>
              Objetivo
              <select value={objective} onChange={(e) => setObjective(e.target.value)} style={inputStyle}>
                {[
                  "OUTCOME_TRAFFIC",
                  "OUTCOME_AWARENESS",
                  "OUTCOME_ENGAGEMENT",
                  "OUTCOME_LEADS",
                  "OUTCOME_SALES",
                ].map((o) => (
                  <option key={o}>{o}</option>
                ))}
              </select>
            </label>
          </div>
        </section>

        {/* Ad set form */}
        <section
          style={{
            background: "#fff",
            borderRadius: 8,
            padding: 20,
            marginBottom: 16,
            border: "1px solid #e5e7eb",
          }}
        >
          <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 700 }}>3. Conjunto de anúncios</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <label style={{ fontSize: 12, fontWeight: 600 }}>
              Nome do conjunto
              <input
                value={adsetName}
                onChange={(e) => setAdsetName(e.target.value)}
                placeholder="[DRY_RUN] Conjunto teste"
                style={inputStyle}
              />
            </label>
            <label style={{ fontSize: 12, fontWeight: 600 }}>
              Orçamento diário (R$) *
              <input
                type="number"
                min={1}
                step={0.01}
                value={budgetBrl}
                onChange={(e) => setBudgetBrl(e.target.value)}
                placeholder="50.00"
                style={inputStyle}
              />
            </label>
          </div>
          <p style={{ fontSize: 11, color: "#6b7280", marginTop: 6 }}>
            Limite configurado: MAX_DAILY_SPEND (verificado na validação)
          </p>
        </section>

        {/* Ad form */}
        <section
          style={{
            background: "#fff",
            borderRadius: 8,
            padding: 20,
            marginBottom: 16,
            border: "1px solid #e5e7eb",
          }}
        >
          <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 700 }}>4. Anúncio</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <label style={{ fontSize: 12, fontWeight: 600 }}>
              Nome do anúncio
              <input
                value={adName}
                onChange={(e) => setAdName(e.target.value)}
                placeholder="[DRY_RUN] Anúncio teste"
                style={inputStyle}
              />
            </label>
            <label style={{ fontSize: 12, fontWeight: 600 }}>
              CTA
              <select value={ctaType} onChange={(e) => setCtaType(e.target.value)} style={inputStyle}>
                {["SHOP_NOW", "LEARN_MORE", "SIGN_UP", "CONTACT_US", "GET_OFFER", "APPLY_NOW"].map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </label>
            <label style={{ fontSize: 12, fontWeight: 600 }}>
              Headline
              <input
                value={headline}
                onChange={(e) => setHeadline(e.target.value)}
                placeholder="Sua oferta aqui"
                style={inputStyle}
              />
            </label>
            <label style={{ fontSize: 12, fontWeight: 600 }}>
              Texto (body)
              <input
                value={bodyText}
                onChange={(e) => setBodyText(e.target.value)}
                placeholder="Descrição do anúncio"
                style={inputStyle}
              />
            </label>
            <label style={{ fontSize: 12, fontWeight: 600, gridColumn: "1 / -1" }}>
              Landing page URL
              <input
                value={landingUrl}
                onChange={(e) => setLandingUrl(e.target.value)}
                placeholder="https://seu-site.com/oferta"
                style={inputStyle}
              />
            </label>
          </div>
        </section>

        {/* Idempotency key */}
        <section
          style={{
            background: "#fff",
            borderRadius: 8,
            padding: 16,
            marginBottom: 16,
            border: "1px solid #e5e7eb",
          }}
        >
          <h3 style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 700 }}>Chave de idempotência</h3>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input
              value={idempotencyKey}
              onChange={(e) => setIdempotencyKey(e.target.value)}
              style={{ ...inputStyle, fontFamily: "monospace", fontSize: 11, flex: 1 }}
            />
            <button
              onClick={() => setIdempotencyKey(crypto.randomUUID())}
              style={{
                padding: "7px 12px",
                background: "#f3f4f6",
                border: "1px solid #d1d5db",
                borderRadius: 5,
                cursor: "pointer",
                fontSize: 11,
                fontWeight: 600,
              }}
            >
              Gerar nova
            </button>
          </div>
          <p style={{ fontSize: 10, color: "#9ca3af", marginTop: 4 }}>
            Mesma chave + mesmo payload = retry seguro (sem duplicata). Mesma chave + payload diferente
            = 409 Conflict.
          </p>
        </section>

        {error && (
          <div
            style={{
              background: "#fef2f2",
              border: "1px solid #fca5a5",
              borderRadius: 6,
              padding: 12,
              marginBottom: 16,
              color: "#991b1b",
              fontSize: 12,
              fontFamily: "monospace",
              whiteSpace: "pre-wrap",
              wordBreak: "break-all",
            }}
          >
            {error}
          </div>
        )}

        {/* Action buttons */}
        <div style={{ display: "flex", gap: 12, marginBottom: 24 }}>
          <button
            onClick={handleValidate}
            disabled={!canValidate || validating}
            style={{
              ...btnStyle,
              background: canValidate ? "#3b82f6" : "#9ca3af",
              cursor: canValidate ? "pointer" : "not-allowed",
            }}
          >
            {validating ? "Validando…" : "Validar"}
          </button>
          <button
            onClick={handleSimulate}
            disabled={!canSimulate || simulating}
            style={{
              ...btnStyle,
              background: canSimulate ? "#10b981" : "#9ca3af",
              cursor: canSimulate ? "pointer" : "not-allowed",
            }}
          >
            {simulating ? "Simulando…" : "Simular publicação (DRY_RUN)"}
          </button>
        </div>

        {/* Validation results */}
        {validateResult && (
          <section
            style={{
              background: "#fff",
              borderRadius: 8,
              padding: 20,
              marginBottom: 16,
              border: `2px solid ${validateResult.passed ? "#86efac" : "#fca5a5"}`,
            }}
          >
            <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 700 }}>
              Resultado da validação{" "}
              <span
                style={{
                  background: validateResult.passed ? "#dcfce7" : "#fee2e2",
                  color: validateResult.passed ? "#166534" : "#991b1b",
                  borderRadius: 4,
                  padding: "2px 8px",
                  fontSize: 11,
                  fontWeight: 700,
                }}
              >
                {validateResult.passed ? "APROVADO" : "BLOQUEADO"}
              </span>
            </h3>
            <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 12 }}>
              {validateResult.blocked_count} bloqueio(s) · {validateResult.warning_count} aviso(s)
            </div>
            {validateResult.checks.map((c) => (
              <CheckRow key={c.code} check={c} />
            ))}
            {validateResult.payload_preview && (
              <div style={{ marginTop: 16 }}>
                <JsonViewer data={validateResult.payload_preview} label="Preview dos payloads" />
              </div>
            )}
          </section>
        )}

        {/* Dry run result */}
        {dryRunResult && (
          <section
            style={{
              background: "#fff",
              borderRadius: 8,
              padding: 20,
              marginBottom: 24,
              border: `2px solid ${dryRunResult.result === "simulated" ? "#86efac" : "#fca5a5"}`,
            }}
          >
            <h3 style={{ margin: "0 0 6px", fontSize: 14, fontWeight: 700 }}>
              Resultado da simulação{" "}
              <span
                style={{
                  background:
                    dryRunResult.result === "simulated"
                      ? "#dcfce7"
                      : dryRunResult.result === "rejected"
                      ? "#fee2e2"
                      : "#fef9c3",
                  color:
                    dryRunResult.result === "simulated"
                      ? "#166534"
                      : dryRunResult.result === "rejected"
                      ? "#991b1b"
                      : "#713f12",
                  borderRadius: 4,
                  padding: "2px 8px",
                  fontSize: 11,
                  fontWeight: 700,
                }}
              >
                {dryRunResult.result.toUpperCase()}
              </span>
              {dryRunResult.idempotent && (
                <span
                  style={{
                    background: "#dbeafe",
                    color: "#1e40af",
                    borderRadius: 4,
                    padding: "2px 8px",
                    fontSize: 10,
                    fontWeight: 700,
                    marginLeft: 8,
                  }}
                >
                  RETRY IDEMPOTENTE
                </span>
              )}
            </h3>
            <p style={{ fontSize: 12, color: "#6b7280", margin: "0 0 8px" }}>{dryRunResult.message}</p>
            <p style={{ fontSize: 11, color: "#9ca3af", margin: "0 0 12px", fontFamily: "monospace" }}>
              correlation_id: {dryRunResult.correlation_id} · attempt_id:{" "}
              {dryRunResult.attempt_id.slice(0, 8)}…
            </p>

            {dryRunResult.simulated_response && (
              <SimulatedIds response={dryRunResult.simulated_response} />
            )}

            {dryRunResult.payload && (
              <div style={{ marginTop: 16 }}>
                <JsonViewer data={dryRunResult.payload} label="Payloads completos (5 etapas)" />
              </div>
            )}

            <div style={{ marginTop: 12 }}>
              <h4 style={{ fontSize: 12, fontWeight: 700, margin: "0 0 8px" }}>Verificações</h4>
              {dryRunResult.checks?.map((c) => <CheckRow key={c.code} check={c} />)}
            </div>
          </section>
        )}

        {/* Simulation history */}
        {history.length > 0 && (
          <section
            style={{
              background: "#fff",
              borderRadius: 8,
              padding: 20,
              border: "1px solid #e5e7eb",
            }}
          >
            <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 700 }}>
              Histórico de simulações (sessão)
            </h3>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: "2px solid #e5e7eb" }}>
                  <th style={thStyle}>Attempt ID</th>
                  <th style={thStyle}>Resultado</th>
                  <th style={thStyle}>Idempotente</th>
                  <th style={thStyle}>Correlation ID</th>
                </tr>
              </thead>
              <tbody>
                {history.map((h) => (
                  <tr key={h.attempt_id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                    <td style={tdStyle}>{h.attempt_id.slice(0, 12)}…</td>
                    <td style={tdStyle}>
                      <span
                        style={{
                          color:
                            h.result === "simulated"
                              ? "#22c55e"
                              : h.result === "rejected"
                              ? "#ef4444"
                              : "#f59e0b",
                          fontWeight: 700,
                        }}
                      >
                        {h.result}
                      </span>
                    </td>
                    <td style={tdStyle}>{h.idempotent ? "sim" : "não"}</td>
                    <td style={{ ...tdStyle, fontFamily: "monospace", fontSize: 10 }}>
                      {h.correlation_id.slice(0, 16)}…
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}
      </div>
    </div>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────────

const inputStyle: React.CSSProperties = {
  display: "block",
  width: "100%",
  marginTop: 4,
  padding: "7px 10px",
  border: "1px solid #d1d5db",
  borderRadius: 5,
  fontSize: 13,
  boxSizing: "border-box",
};

const btnStyle: React.CSSProperties = {
  padding: "10px 20px",
  color: "#fff",
  border: "none",
  borderRadius: 6,
  fontSize: 14,
  fontWeight: 700,
};

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "6px 8px",
  fontWeight: 700,
  fontSize: 12,
  color: "#6b7280",
};

const tdStyle: React.CSSProperties = {
  padding: "6px 8px",
};
