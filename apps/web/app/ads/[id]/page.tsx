"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Nav } from "@/components/Nav";
import { FictitiousBanner } from "@/components/FictitiousBanner";
import {
  api,
  SourceAdOut,
  AnalysisOut,
  PromptVersionOut,
  GeneratedCreativeOut,
  CheckResult,
  SnapshotOut,
  PerformanceHypothesisItem,
  ObservationItem,
  MetricFactItem,
} from "@/lib/api";

type Step = "idle" | "analyzing" | "prompting" | "generating" | "checking" | "approving" | "publishing" | "revising" | "done";

const CATEGORY_LABELS: Record<string, string> = {
  composition: "Composição",
  color: "Cor",
  text: "Texto",
  product: "Produto",
  attention: "Atenção",
  style: "Estilo",
  other: "Outro",
};

export default function AdDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [ad, setAd] = useState<SourceAdOut | null>(null);
  const [insights, setInsights] = useState<SnapshotOut[]>([]);
  const [showRaw, setShowRaw] = useState(false);
  const [analysis, setAnalysis] = useState<AnalysisOut | null>(null);
  const [showAnalysisDetail, setShowAnalysisDetail] = useState(false);
  const [prompt, setPrompt] = useState<PromptVersionOut | null>(null);
  const [showReviseForm, setShowReviseForm] = useState(false);
  const [reviseFields, setReviseFields] = useState<Record<string, string>>({});
  const [reviseReason, setReviseReason] = useState("");
  const [creative, setCreative] = useState<GeneratedCreativeOut | null>(null);
  const [checks, setChecks] = useState<{ quality: CheckResult; policy: CheckResult } | null>(null);
  const [approved, setApproved] = useState(false);
  const [publishResult, setPublishResult] = useState<{ message: string; payload: unknown } | null>(null);
  const [step, setStep] = useState<Step>("idle");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.sourceAds.get(id).then((a) => {
      setAd(a);
    }).catch(() => router.push("/login"));
    api.sourceAds.insights(id, 90).then(setInsights).catch(() => {});
  }, [id, router]);

  async function run(stepName: Step, fn: () => Promise<void>) {
    setStep(stepName);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(String(e));
    } finally {
      setStep((s) => s === stepName ? "idle" : s);
    }
  }

  async function doAnalyze(force = false) {
    await run("analyzing", async () => {
      const a = await api.sourceAds.analyze(id, force);
      setAnalysis(a);
    });
  }

  async function doGeneratePrompt() {
    await run("prompting", async () => {
      if (!analysis) return;
      const p = await api.prompts.generate({
        source_ad_id: id,
        analysis_id: analysis.id,
        ad_format: ad?.ad_format ?? "feed",
        objective: ad?.objective ?? undefined,
        fields: { cta_text: ad?.cta ?? "Saiba mais" },
      });
      setPrompt(p);
      setReviseFields({ cta_text: ad?.cta ?? "Saiba mais" });
    });
  }

  async function doRevise() {
    if (!prompt) return;
    await run("revising", async () => {
      const p = await api.prompts.revise(prompt.template_id, {
        fields: reviseFields,
        change_reason: reviseReason || "Revisão manual",
      });
      setPrompt(p);
      setShowReviseForm(false);
      setReviseReason("");
    });
  }

  async function doGenerateCreative() {
    await run("generating", async () => {
      if (!prompt) return;
      const c = await api.creatives.generate({ prompt_version_id: prompt.id });
      setCreative(c);
    });
  }

  async function doQualityCheck() {
    await run("checking", async () => {
      if (!creative) return;
      const [q, p] = await Promise.all([
        api.creatives.qualityCheck(creative.id),
        api.creatives.policyCheck(creative.id),
      ]);
      setChecks({ quality: q as unknown as CheckResult, policy: p as unknown as CheckResult });
    });
  }

  async function doApprove() {
    await run("approving", async () => {
      if (!creative) return;
      await api.creatives.approve(creative.id, "Aprovado via interface");
      setApproved(true);
    });
  }

  async function doPublishDryRun() {
    await run("publishing", async () => {
      if (!creative) return;
      const r = await api.publish.dryRun({
        creative_id: creative.id,
        idempotency_key: `web-${creative.id}-${Date.now()}`,
        campaign_name: `[DRY_RUN] ${ad?.name}`,
        daily_budget_brl: 50,
        headline: ad?.headline ?? undefined,
        body_text: ad?.body_text ?? undefined,
        cta_type: ad?.cta ?? undefined,
      });
      setPublishResult({ message: r.message, payload: r.payload });
      setStep("done");
    });
  }

  if (!ad) return <p style={{ padding: 40 }}>Carregando...</p>;

  const isBlocked = checks
    ? checks.quality.result === "BLOCKED" || checks.policy.result === "BLOCKED"
    : false;

  return (
    <>
      <Nav />
      <main style={{ maxWidth: 860, margin: "0 auto", padding: "28px 20px" }}>
        <FictitiousBanner />

        <button onClick={() => router.back()} style={linkBtn}>← Voltar</button>
        <h1 style={{ marginTop: 8, marginBottom: 4 }}>{ad.name}</h1>

        {/* Source badges */}
        <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap", fontSize: 12 }}>
          {ad.is_fictitious && (
            <span style={badgeStyle("#d0ebff", "#1864ab")}>fictício</span>
          )}
          {ad.source && !ad.is_fictitious && (
            <span style={badgeStyle("#d3f9d8", "#1a6b35")}>{ad.source}</span>
          )}
          {ad.effective_status && (
            <span style={badgeStyle("#f1f3f5", "#444")}>{ad.effective_status}</span>
          )}
          {ad.last_synced_at && (
            <span style={{ fontSize: 11, color: "#999" }}>
              Último sync: {new Date(ad.last_synced_at).toLocaleString("pt-BR")}
            </span>
          )}
        </div>

        {/* Ad context from Meta */}
        {ad.source_adset && (
          <div style={{ background: "#f8f9fa", borderRadius: 6, padding: "10px 14px", marginBottom: 8, fontSize: 13 }}>
            <strong>Ad Set:</strong> {ad.source_adset.name}
            {ad.source_adset.optimization_goal && <span style={{ color: "#888" }}> · {ad.source_adset.optimization_goal}</span>}
            {ad.source_adset.effective_status && <span style={{ color: "#888" }}> · {ad.source_adset.effective_status}</span>}
          </div>
        )}

        {/* Creative from Meta */}
        {ad.source_creative && (
          <div style={{ background: "#f8f9fa", borderRadius: 6, padding: "10px 14px", marginBottom: 8, fontSize: 13 }}>
            <strong>Criativo Meta:</strong>
            {ad.source_creative.title && <div style={{ marginTop: 4 }}><strong>Título:</strong> {ad.source_creative.title}</div>}
            {ad.source_creative.body && <div><strong>Corpo:</strong> {ad.source_creative.body}</div>}
            {ad.source_creative.cta_type && <div><strong>CTA:</strong> {ad.source_creative.cta_type}</div>}
            {ad.source_creative.link_url && (
              <div><strong>URL:</strong> <span style={{ color: "#4c6ef5", wordBreak: "break-all" }}>{ad.source_creative.link_url}</span></div>
            )}
            {ad.source_creative.image_url && (
              <div style={{ marginTop: 6 }}>
                <img
                  src={ad.source_creative.image_url}
                  alt="preview"
                  style={{ maxWidth: 200, borderRadius: 4, border: "1px solid #eee" }}
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                />
              </div>
            )}
          </div>
        )}

        {ad.headline && <p style={{ color: "#555", margin: "4px 0 2px" }}><strong>Headline:</strong> {ad.headline}</p>}
        {ad.body_text && <p style={{ color: "#555", margin: "2px 0" }}><strong>Corpo:</strong> {ad.body_text}</p>}
        {ad.cta && <p style={{ color: "#555", margin: "2px 0 12px" }}><strong>CTA:</strong> {ad.cta}</p>}

        {/* Insights time series */}
        {insights.length > 0 && (
          <div style={{ background: "#fff", borderRadius: 8, padding: "14px 18px", boxShadow: "0 1px 4px rgba(0,0,0,.08)", marginBottom: 16 }}>
            <h3 style={{ margin: "0 0 10px", fontSize: 14 }}>Histórico de Métricas ({insights.length} períodos)</h3>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr style={{ background: "#f8f9fa" }}>
                    {["Período", "Gasto", "Impressões", "Cliques", "CTR", "ROAS", "Compras", "Leads"].map((h) => (
                      <th key={h} style={{ padding: "5px 8px", textAlign: "right", borderBottom: "1px solid #eee", fontWeight: 600, whiteSpace: "nowrap" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {insights.map((s) => (
                    <tr key={s.id} style={{ borderBottom: "1px solid #f0f0f0" }}>
                      <td style={{ padding: "5px 8px", whiteSpace: "nowrap", textAlign: "right" }}>
                        {s.date_start} {s.date_stop && s.date_stop !== s.date_start ? `→ ${s.date_stop}` : ""}
                      </td>
                      <td style={{ padding: "5px 8px", textAlign: "right" }}>R$ {(s.spend ?? 0).toFixed(2)}</td>
                      <td style={{ padding: "5px 8px", textAlign: "right" }}>{s.impressions?.toLocaleString("pt-BR") ?? "—"}</td>
                      <td style={{ padding: "5px 8px", textAlign: "right" }}>{s.clicks?.toLocaleString("pt-BR") ?? "—"}</td>
                      <td style={{ padding: "5px 8px", textAlign: "right" }}>{s.ctr?.toFixed(2) ?? "—"}%</td>
                      <td style={{ padding: "5px 8px", textAlign: "right", fontWeight: s.roas ? 600 : 400 }}>
                        {s.roas?.toFixed(2) ?? "—"}
                        {s.roas_source && <span style={{ color: "#aaa", fontWeight: 400 }}> ({s.roas_source[0]})</span>}
                      </td>
                      <td style={{ padding: "5px 8px", textAlign: "right" }}>{s.purchases ?? "—"}</td>
                      <td style={{ padding: "5px 8px", textAlign: "right" }}>{s.leads ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Raw response viewer */}
        {ad.snapshots[0] && (
          <div style={{ marginBottom: 12 }}>
            <button
              onClick={() => setShowRaw((p) => !p)}
              style={{ background: "none", border: "1px solid #ddd", borderRadius: 4, padding: "4px 10px", fontSize: 12, cursor: "pointer", color: "#666" }}
            >
              {showRaw ? "Ocultar" : "Ver"} resposta bruta (último snapshot)
            </button>
            {showRaw && (
              <pre style={{ ...preStyle, marginTop: 8, maxHeight: 300 }}>
                {JSON.stringify(ad.snapshots[0], null, 2)}
              </pre>
            )}
          </div>
        )}

        {error && <div style={errorBox}>{error}</div>}

        <div style={{ display: "flex", flexDirection: "column", gap: 14, marginTop: 24 }}>

          {/* ── Section 1: Analysis ──────────────────────────────── */}
          <Section title="1. Análise do criativo">
            {!analysis ? (
              <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                <ActionBtn onClick={() => doAnalyze(false)} loading={step === "analyzing"} label="Gerar análise" />
              </div>
            ) : (
              <div>
                {/* Header row */}
                <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 14, flexWrap: "wrap" }}>
                  <ProviderBadge provider={analysis.provider} />
                  <StatusBadge status={analysis.status} />
                  <span style={{ fontSize: 12, color: "#888" }}>v{analysis.analysis_version}</span>
                  {analysis.media_kind && (
                    <span style={{ fontSize: 12, color: "#888" }}>mídia: {analysis.media_kind}</span>
                  )}
                  {analysis.repaired && (
                    <span style={badgeStyle("#fff3cd", "#856404")}>JSON reparado</span>
                  )}
                  {analysis.latency_ms && (
                    <span style={{ fontSize: 11, color: "#aaa" }}>{analysis.latency_ms}ms</span>
                  )}
                  {analysis.estimated_cost_usd !== null && analysis.estimated_cost_usd !== undefined && (
                    <span style={{ fontSize: 11, color: "#aaa" }}>${analysis.estimated_cost_usd.toFixed(4)}</span>
                  )}
                  <button
                    onClick={() => doAnalyze(true)}
                    disabled={step === "analyzing"}
                    style={{ marginLeft: "auto", background: "none", border: "1px solid #ddd", borderRadius: 4, padding: "3px 10px", fontSize: 11, cursor: "pointer", color: "#666" }}
                  >
                    Re-analisar
                  </button>
                </div>

                {/* Confidence bar */}
                {analysis.confidence !== null && analysis.confidence !== undefined && (
                  <ConfidenceBar value={analysis.confidence} />
                )}

                {/* Visual summary */}
                {analysis.visual_summary && (
                  <div style={{ background: "#f8f9fa", borderRadius: 5, padding: "10px 14px", marginBottom: 12, fontSize: 13, lineHeight: 1.5 }}>
                    {analysis.visual_summary}
                  </div>
                )}

                {/* Observations */}
                {analysis.observations && analysis.observations.length > 0 && (
                  <CollapsibleSection title="Observações visuais" defaultOpen>
                    <ObservationList items={analysis.observations} />
                  </CollapsibleSection>
                )}

                {/* Metric facts */}
                {analysis.metric_facts && analysis.metric_facts.length > 0 && (
                  <CollapsibleSection title="Métricas utilizadas" defaultOpen>
                    <MetricFactList items={analysis.metric_facts} />
                  </CollapsibleSection>
                )}

                {/* Performance hypotheses */}
                {analysis.performance_hypotheses && analysis.performance_hypotheses.length > 0 && (
                  <CollapsibleSection title="Hipóteses de performance" defaultOpen>
                    <HypothesisList items={analysis.performance_hypotheses} />
                  </CollapsibleSection>
                )}

                {/* Strengths & weaknesses */}
                {((analysis.strengths && analysis.strengths.length > 0) || (analysis.weaknesses && analysis.weaknesses.length > 0)) && (
                  <CollapsibleSection title="Pontos fortes e fracos">
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 700, color: "#1a6b35", marginBottom: 6, textTransform: "uppercase" }}>Fortes</div>
                        <StringList items={analysis.strengths ?? []} color="#1a6b35" />
                      </div>
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 700, color: "#c00", marginBottom: 6, textTransform: "uppercase" }}>Fracos</div>
                        <StringList items={analysis.weaknesses ?? []} color="#c00" />
                      </div>
                    </div>
                  </CollapsibleSection>
                )}

                {/* Elements to test */}
                {analysis.elements_to_test && analysis.elements_to_test.length > 0 && (
                  <CollapsibleSection title="Elementos para testar">
                    <StringList items={analysis.elements_to_test} color="#1864ab" bullet="→" />
                  </CollapsibleSection>
                )}

                {/* Policy risks */}
                {analysis.policy_risks && analysis.policy_risks.length > 0 && (
                  <CollapsibleSection title="Riscos de política">
                    <StringList items={analysis.policy_risks} color="#856404" bullet="⚠" />
                  </CollapsibleSection>
                )}

                {/* Limitations */}
                {analysis.limitations && analysis.limitations.length > 0 && (
                  <CollapsibleSection title="Limitações">
                    <StringList items={analysis.limitations} color="#888" bullet="!" />
                  </CollapsibleSection>
                )}

                {/* Detail link */}
                <div style={{ marginTop: 10, display: "flex", gap: 10 }}>
                  <button
                    onClick={() => setShowAnalysisDetail((p) => !p)}
                    style={{ background: "none", border: "1px solid #ddd", borderRadius: 4, padding: "4px 10px", fontSize: 11, cursor: "pointer", color: "#666" }}
                  >
                    {showAnalysisDetail ? "Ocultar" : "Ver"} JSON completo
                  </button>
                </div>
                {showAnalysisDetail && (
                  <pre style={{ ...preStyle, marginTop: 8, maxHeight: 400 }}>
                    {JSON.stringify(analysis, null, 2)}
                  </pre>
                )}
              </div>
            )}
          </Section>

          {/* ── Section 2: Prompt ────────────────────────────────── */}
          <Section title="2. Prompt versionado">
            {!analysis ? (
              <p style={hintStyle}>Complete a análise primeiro.</p>
            ) : !prompt ? (
              <ActionBtn onClick={doGeneratePrompt} loading={step === "prompting"} label="Gerar prompt" />
            ) : (
              <div>
                <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 10, flexWrap: "wrap" }}>
                  <span style={badgeStyle("#e8f4fd", "#1864ab")}>v{prompt.version_number}</span>
                  <span style={{ fontSize: 12, color: "#888" }}>author: {prompt.author_type}</span>
                  {prompt.content_hash && (
                    <code style={{ fontSize: 10, color: "#aaa" }}>{prompt.content_hash.slice(0, 12)}…</code>
                  )}
                  <Link
                    href={`/prompts/${prompt.template_id}`}
                    style={{ marginLeft: "auto", fontSize: 12, color: "#4c6ef5", textDecoration: "none" }}
                  >
                    Ver template →
                  </Link>
                </div>
                {prompt.change_reason && (
                  <p style={{ fontSize: 12, color: "#777", margin: "0 0 8px", fontStyle: "italic" }}>&ldquo;{prompt.change_reason}&rdquo;</p>
                )}
                <pre style={preStyle}>{prompt.prompt_text}</pre>

                {/* Revise */}
                <div style={{ marginTop: 12 }}>
                  <button
                    onClick={() => setShowReviseForm((p) => !p)}
                    style={{ background: "none", border: "1px solid #7c83ff", borderRadius: 4, padding: "5px 14px", fontSize: 12, cursor: "pointer", color: "#7c83ff" }}
                  >
                    {showReviseForm ? "Cancelar revisão" : "Criar revisão"}
                  </button>
                </div>

                {showReviseForm && (
                  <div style={{ marginTop: 12, background: "#f8f9fa", borderRadius: 6, padding: "14px 16px" }}>
                    <p style={{ fontSize: 12, fontWeight: 700, margin: "0 0 10px" }}>Campos do prompt</p>
                    {Object.entries(reviseFields).map(([key, val]) => (
                      <div key={key} style={{ marginBottom: 8 }}>
                        <label style={{ fontSize: 11, color: "#888", display: "block", marginBottom: 2, textTransform: "uppercase" }}>{key}</label>
                        <input
                          value={val}
                          onChange={(e) => setReviseFields((p) => ({ ...p, [key]: e.target.value }))}
                          style={{ width: "100%", padding: "5px 8px", borderRadius: 4, border: "1px solid #ddd", fontSize: 13, boxSizing: "border-box" }}
                        />
                      </div>
                    ))}
                    <div style={{ marginBottom: 10 }}>
                      <label style={{ fontSize: 11, color: "#888", display: "block", marginBottom: 2, textTransform: "uppercase" }}>Motivo da revisão</label>
                      <input
                        value={reviseReason}
                        onChange={(e) => setReviseReason(e.target.value)}
                        placeholder="ex: Testando CTA diferente"
                        style={{ width: "100%", padding: "5px 8px", borderRadius: 4, border: "1px solid #ddd", fontSize: 13, boxSizing: "border-box" }}
                      />
                    </div>
                    <ActionBtn onClick={doRevise} loading={step === "revising"} label="Criar v" />
                  </div>
                )}
              </div>
            )}
          </Section>

          {/* ── Section 3: Creative ──────────────────────────────── */}
          <Section title="3. Gerar imagem (mock provider)">
            {!prompt ? (
              <p style={hintStyle}>Complete o prompt primeiro.</p>
            ) : !creative ? (
              <ActionBtn onClick={doGenerateCreative} loading={step === "generating"} label="Gerar criativo" />
            ) : (
              <div style={{ fontSize: 13 }}>
                <p>Provider: <strong>{creative.provider}</strong></p>
                <p>Hash: <code style={{ fontSize: 12 }}>{creative.file_hash}</code></p>
                <p>Dimensões: {creative.width}×{creative.height}</p>
                <p>Status: {creative.status}</p>
              </div>
            )}
          </Section>

          {/* ── Section 4: Quality checks ────────────────────────── */}
          <Section title="4. Quality + Policy checks">
            {!creative ? (
              <p style={hintStyle}>Gere o criativo primeiro.</p>
            ) : !checks ? (
              <ActionBtn onClick={doQualityCheck} loading={step === "checking"} label="Rodar checks" />
            ) : (
              <div style={{ fontSize: 13 }}>
                <ResultBadge label="Quality" result={checks.quality.result} />
                <ResultBadge label="Policy" result={checks.policy.result} />
                {isBlocked && (
                  <div style={{ background: "#f8d7da", color: "#721c24", padding: "8px 12px", borderRadius: 5, marginTop: 8 }}>
                    BLOQUEADO — não é possível aprovar. Override manual necessário.
                  </div>
                )}
              </div>
            )}
          </Section>

          {/* ── Section 5: Approval ──────────────────────────────── */}
          <Section title="5. Aprovação humana">
            {!checks ? (
              <p style={hintStyle}>Execute os checks primeiro.</p>
            ) : approved ? (
              <div style={{ color: "#155724", background: "#d4edda", padding: "8px 12px", borderRadius: 5, fontSize: 13 }}>
                Criativo aprovado.
              </div>
            ) : (
              <ActionBtn
                onClick={doApprove}
                loading={step === "approving"}
                label="Aprovar criativo"
                disabled={isBlocked}
              />
            )}
          </Section>

          {/* ── Section 6: Publish ───────────────────────────────── */}
          <Section title="6. Simular publicação (DRY_RUN)">
            {!approved ? (
              <p style={hintStyle}>Aprove o criativo primeiro.</p>
            ) : publishResult ? (
              <div>
                <p style={{ fontSize: 13, color: "#155724" }}>{publishResult.message}</p>
                <pre style={preStyle}>{JSON.stringify(publishResult.payload, null, 2)}</pre>
              </div>
            ) : (
              <ActionBtn onClick={doPublishDryRun} loading={step === "publishing"} label="Simular publicação (DRY_RUN)" />
            )}
          </Section>

        </div>
      </main>
    </>
  );
}

// ── Sub-components ────────────────────────────────────────────────

function ProviderBadge({ provider }: { provider: string }) {
  const isMock = provider === "mock";
  return (
    <span style={badgeStyle(isMock ? "#f1f3f5" : "#d3f9d8", isMock ? "#555" : "#1a6b35")}>
      {isMock ? "mock" : `real · ${provider}`}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, [string, string]> = {
    completed: ["#d4edda", "#155724"],
    partial: ["#fff3cd", "#856404"],
    failed: ["#f8d7da", "#721c24"],
  };
  const [bg, fg] = colors[status] ?? ["#e2e3e5", "#444"];
  return <span style={badgeStyle(bg, fg)}>{status}</span>;
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 70 ? "#1a6b35" : pct >= 40 ? "#856404" : "#c00";
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#888", marginBottom: 3 }}>
        <span>Confiança da análise</span>
        <span style={{ fontWeight: 700, color }}>{pct}%</span>
      </div>
      <div style={{ background: "#e9ecef", borderRadius: 3, height: 6, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, background: color, height: "100%", borderRadius: 3, transition: "width 0.4s" }} />
      </div>
    </div>
  );
}

function CollapsibleSection({ title, children, defaultOpen = false }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div style={{ marginBottom: 10, borderTop: "1px solid #f0f0f0", paddingTop: 8 }}>
      <button
        onClick={() => setOpen((p) => !p)}
        style={{ background: "none", border: "none", cursor: "pointer", padding: 0, display: "flex", alignItems: "center", gap: 6, fontSize: 13, fontWeight: 600, color: "#333" }}
      >
        <span style={{ fontSize: 10 }}>{open ? "▼" : "▶"}</span>
        {title}
      </button>
      {open && <div style={{ marginTop: 8 }}>{children}</div>}
    </div>
  );
}

function ObservationList({ items }: { items: ObservationItem[] }) {
  const grouped: Record<string, ObservationItem[]> = {};
  for (const item of items) {
    const cat = item.category ?? "other";
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(item);
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {Object.entries(grouped).map(([cat, obs]) => (
        <div key={cat}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#888", textTransform: "uppercase", marginBottom: 4 }}>
            {CATEGORY_LABELS[cat] ?? cat}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {obs.map((o, i) => (
              <div key={i} style={{ fontSize: 12, color: "#444", paddingLeft: 10, borderLeft: "2px solid #e0e0e0" }}>
                {o.text}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function MetricFactList({ items }: { items: MetricFactItem[] }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {items.map((f, i) => (
        <div key={i} style={{ display: "flex", gap: 8, alignItems: "baseline", fontSize: 12 }}>
          <span style={badgeStyle("#e8f4fd", "#1864ab")}>{f.metric}</span>
          {f.value !== null && f.value !== undefined && (
            <strong style={{ color: "#1864ab" }}>{f.value}</strong>
          )}
          <span style={{ color: "#555" }}>{f.text}</span>
        </div>
      ))}
    </div>
  );
}

function HypothesisList({ items }: { items: PerformanceHypothesisItem[] }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {items.map((h, i) => (
        <div key={i} style={{ background: "#f8f9fa", borderRadius: 5, padding: "10px 12px" }}>
          <div style={{ fontSize: 12, color: "#333", lineHeight: 1.4, marginBottom: 6 }}>
            {h.statement}
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span style={{ fontSize: 10, color: "#888" }}>variável: <strong>{h.primary_variable}</strong></span>
            <ConfidenceBar value={h.confidence} />
          </div>
        </div>
      ))}
    </div>
  );
}

function StringList({ items, color = "#444", bullet = "•" }: { items: string[]; color?: string; bullet?: string }) {
  return (
    <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 4 }}>
      {items.map((item, i) => (
        <li key={i} style={{ display: "flex", gap: 6, fontSize: 12, color, alignItems: "flex-start" }}>
          <span style={{ flexShrink: 0 }}>{bullet}</span>
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ background: "#fff", borderRadius: 8, padding: "16px 20px", boxShadow: "0 1px 4px rgba(0,0,0,.08)" }}>
      <h3 style={{ margin: "0 0 12px", fontSize: 15 }}>{title}</h3>
      {children}
    </div>
  );
}

function ActionBtn({ onClick, loading, label, disabled }: { onClick: () => void; loading: boolean; label: string; disabled?: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={loading || disabled}
      style={{
        background: disabled ? "#ccc" : "#7c83ff",
        color: "#fff",
        border: "none",
        borderRadius: 6,
        padding: "9px 18px",
        fontSize: 14,
        cursor: loading || disabled ? "not-allowed" : "pointer",
        opacity: loading ? 0.7 : 1,
      }}
    >
      {loading ? "Processando..." : label}
    </button>
  );
}

function ResultBadge({ label, result }: { label: string; result: string }) {
  const colors: Record<string, string> = { PASS: "#d4edda", WARNING: "#fff3cd", BLOCKED: "#f8d7da" };
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 8, marginRight: 12 }}>
      <span style={{ fontSize: 13 }}>{label}:</span>
      <span style={{ background: colors[result] ?? "#e2e3e5", padding: "2px 10px", borderRadius: 4, fontSize: 12, fontWeight: 700 }}>
        {result}
      </span>
    </div>
  );
}

function badgeStyle(bg: string, color: string): React.CSSProperties {
  return { background: bg, color, borderRadius: 3, padding: "2px 8px", fontWeight: 600, fontSize: 11, whiteSpace: "nowrap" as const };
}

const preStyle: React.CSSProperties = {
  background: "#f8f9fa",
  borderRadius: 5,
  padding: 12,
  fontSize: 11,
  overflow: "auto",
  maxHeight: 200,
  margin: 0,
};
const hintStyle: React.CSSProperties = { color: "#999", fontSize: 13, margin: 0 };
const errorBox: React.CSSProperties = {
  background: "#ffe0e0", color: "#c00", padding: "10px 14px", borderRadius: 6, fontSize: 13, marginTop: 12,
};
const linkBtn: React.CSSProperties = {
  background: "none", border: "none", cursor: "pointer", color: "#7c83ff", fontSize: 14, padding: 0,
};
