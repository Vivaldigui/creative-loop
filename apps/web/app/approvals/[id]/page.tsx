"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { Nav } from "@/components/Nav";
import { FictitiousBanner } from "@/components/FictitiousBanner";
import { api, ApprovalDetailOut, UserOut } from "@/lib/api";

const SEVERITY_COLOR: Record<string, string> = {
  blocked: "#ef4444",
  warning: "#f59e0b",
};

const RESULT_COLOR: Record<string, string> = {
  PASS: "#22c55e",
  WARNING: "#f59e0b",
  BLOCKED: "#ef4444",
};

function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span
      style={{
        background: color,
        color: "#fff",
        borderRadius: 4,
        padding: "2px 8px",
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: 0.5,
      }}
    >
      {label}
    </span>
  );
}

function FindingRow({ finding }: { finding: Record<string, unknown> }) {
  const severity = String(finding.severity ?? "");
  return (
    <div
      style={{
        padding: "8px 12px",
        borderRadius: 6,
        background: severity === "blocked" ? "#fff1f2" : "#fffbeb",
        borderLeft: `3px solid ${SEVERITY_COLOR[severity] ?? "#ccc"}`,
        marginBottom: 6,
        fontSize: 12,
      }}
    >
      <span style={{ fontWeight: 600, color: SEVERITY_COLOR[severity] ?? "#444" }}>
        [{String(finding.check ?? finding.rule ?? "?")}]
      </span>{" "}
      {String(finding.detail ?? "")}
      {Boolean(finding.matched_text) && (
        <span style={{ color: "#666", marginLeft: 8 }}>
          → <em>&quot;{String(finding.matched_text)}&quot;</em>
        </span>
      )}
    </div>
  );
}

export default function ApprovalDetailPage() {
  const router = useRouter();
  const params = useParams();
  const id = params?.id as string;

  const [detail, setDetail] = useState<ApprovalDetailOut | null>(null);
  const [user, setUser] = useState<UserOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState(false);
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.approvals.get(id), api.auth.me()])
      .then(([d, u]) => {
        setDetail(d);
        setUser(u);
      })
      .catch((e: Error) => {
        if (e.message.startsWith("401")) router.push("/login");
        else setError(e.message);
      })
      .finally(() => setLoading(false));
  }, [id, router]);

  if (loading) return <p style={{ padding: 40 }}>Carregando…</p>;
  if (!detail) return <p style={{ padding: 40 }}>Criativo não encontrado.</p>;

  const isOwnerOrAdmin = user?.role === "owner" || user?.role === "admin";
  const isOwner = user?.role === "owner";
  const hasBlocked =
    detail.quality_checks.some((c) => c.result === "BLOCKED") ||
    detail.policy_checks.some((c) => c.result === "BLOCKED");
  const allFindings = [
    ...(detail.quality_checks.flatMap((c) => (c as Record<string, unknown[]>).findings ?? [])),
    ...(detail.policy_checks.flatMap((c) => (c as Record<string, unknown[]>).findings ?? [])),
  ] as Record<string, unknown>[];

  const originalAsset = detail.assets.find((a) => (a as Record<string, unknown>).role === "original");
  const derivativeAssets = detail.assets.filter((a) => (a as Record<string, unknown>).role === "derivative");

  async function handleApprove() {
    if (!comment && hasBlocked) {
      setError("Informe um comentário ao sobrescrever itens BLOCKED.");
      return;
    }
    setActing(true);
    setError(null);
    try {
      await api.creatives.approve(id, comment || undefined, hasBlocked && isOwner);
      setSuccess("Criativo aprovado com sucesso.");
      setTimeout(() => router.push("/approvals"), 1500);
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setActing(false);
    }
  }

  async function handleReject() {
    if (!comment) { setError("Comentário obrigatório para rejeitar."); return; }
    setActing(true);
    setError(null);
    try {
      await api.creatives.reject(id, comment);
      setSuccess("Criativo rejeitado.");
      setTimeout(() => router.push("/approvals"), 1500);
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setActing(false);
    }
  }

  async function handleVariation() {
    if (!comment) { setError("Explique por que deseja uma nova variação."); return; }
    setActing(true);
    setError(null);
    try {
      const res = await api.creatives.requestVariation(id, comment);
      setSuccess(`Nova variação enfileirada (ID: ${res.new_creative_id}).`);
      setTimeout(() => router.push("/approvals"), 2000);
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setActing(false);
    }
  }

  const alreadyActed = detail.status === "approved" || detail.status === "rejected";

  return (
    <>
      <Nav />
      <main style={{ maxWidth: 960, margin: "0 auto", padding: "28px 20px" }}>
        <FictitiousBanner />

        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
          <Link href="/approvals" style={{ color: "#7c83ff", fontSize: 13 }}>← Voltar à fila</Link>
          <Badge
            label={detail.status.replace("_", " ").toUpperCase()}
            color={RESULT_COLOR[detail.status === "awaiting_approval" ? "WARNING" : detail.status === "blocked" ? "BLOCKED" : "PASS"] ?? "#888"}
          />
          {detail.is_fictitious && <Badge label="FICTÍCIO" color="#6366f1" />}
          {detail.variation_of_id && <Badge label="VARIAÇÃO" color="#92400e" />}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, marginBottom: 24 }}>
          {/* Left: Image preview */}
          <div>
            <h3 style={{ marginTop: 0, fontSize: 14, marginBottom: 10 }}>Imagem original</h3>
            <div
              style={{
                background: "#f0f0f0",
                borderRadius: 8,
                overflow: "hidden",
                minHeight: 200,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              {originalAsset && (originalAsset as Record<string, unknown>).signed_url ? (
                <img
                  src={String((originalAsset as Record<string, unknown>).signed_url)}
                  alt="Creative original"
                  style={{ maxWidth: "100%", display: "block" }}
                />
              ) : (
                <span style={{ color: "#aaa", fontSize: 13 }}>Imagem indisponível</span>
              )}
            </div>

            {derivativeAssets.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <div style={{ fontSize: 12, color: "#666", marginBottom: 6 }}>Derivados:</div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {derivativeAssets.map((a, i) => {
                    const asset = a as Record<string, unknown>;
                    return (
                      <div key={i} style={{ textAlign: "center" }}>
                        <div style={{ background: "#e5e7eb", borderRadius: 4, width: 60, height: 60, overflow: "hidden", display: "flex", alignItems: "center", justifyContent: "center" }}>
                          {asset.signed_url ? (
                            <img src={String(asset.signed_url)} alt={String(asset.format_label)} style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }} />
                          ) : <span style={{ fontSize: 18 }}>🖼</span>}
                        </div>
                        <div style={{ fontSize: 10, color: "#666", marginTop: 2 }}>{String(asset.format_label ?? "—")}</div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Right: Metadata */}
          <div>
            <h3 style={{ marginTop: 0, fontSize: 14, marginBottom: 10 }}>Detalhes</h3>
            <table style={{ fontSize: 12, width: "100%", borderCollapse: "collapse" }}>
              <tbody>
                {[
                  ["Provider", detail.provider],
                  ["Modelo", detail.model_used],
                  ["Dimensões", detail.width && detail.height ? `${detail.width}×${detail.height}` : "—"],
                  ["Custo estimado", detail.estimated_cost_usd != null ? `US$ ${detail.estimated_cost_usd.toFixed(4)}` : "—"],
                  ["Hash", detail.file_hash ? detail.file_hash.slice(0, 16) + "…" : "—"],
                  ["Prompt v.", detail.prompt_version_number],
                  ["Motivo da revisão", detail.prompt_change_reason],
                  ["Aprendizado", detail.prompt_learning_used],
                ].map(([k, v]) => v ? (
                  <tr key={String(k)}>
                    <td style={{ color: "#888", paddingRight: 12, paddingBottom: 5, verticalAlign: "top" }}>{k}:</td>
                    <td style={{ paddingBottom: 5 }}>{String(v)}</td>
                  </tr>
                ) : null)}
              </tbody>
            </table>

            {detail.prompt_text && (
              <div style={{ marginTop: 12 }}>
                <div style={{ fontSize: 12, color: "#666", marginBottom: 4 }}>Prompt:</div>
                <pre
                  style={{
                    background: "#f5f5f5",
                    borderRadius: 6,
                    padding: 10,
                    fontSize: 11,
                    whiteSpace: "pre-wrap",
                    maxHeight: 140,
                    overflow: "auto",
                    margin: 0,
                  }}
                >
                  {detail.prompt_text}
                </pre>
              </div>
            )}
          </div>
        </div>

        {/* Quality & Policy findings */}
        {allFindings.length > 0 && (
          <div style={{ marginBottom: 20 }}>
            <h3 style={{ fontSize: 14, marginBottom: 10 }}>Verificações ({allFindings.length} achados)</h3>
            {allFindings.map((f, i) => <FindingRow key={i} finding={f} />)}
          </div>
        )}

        {/* Internal notice */}
        <div
          style={{
            background: "#fef3c7",
            border: "1px solid #fcd34d",
            borderRadius: 6,
            padding: "10px 14px",
            fontSize: 12,
            color: "#92400e",
            marginBottom: 20,
          }}
        >
          ⚠️ {detail.internal_notice}
        </div>

        {/* Action area */}
        {!alreadyActed && isOwnerOrAdmin && (
          <div
            style={{
              background: "#fff",
              borderRadius: 10,
              padding: 20,
              boxShadow: "0 1px 4px rgba(0,0,0,.08)",
            }}
          >
            <h3 style={{ marginTop: 0, fontSize: 14 }}>Decisão</h3>

            {hasBlocked && !isOwner && (
              <div style={{ background: "#fee", borderRadius: 6, padding: 10, fontSize: 12, color: "#c00", marginBottom: 12 }}>
                Este criativo possui verificações BLOCKED. Apenas o <strong>owner</strong> pode sobrescrever.
              </div>
            )}
            {hasBlocked && isOwner && (
              <div style={{ background: "#fff1f2", borderRadius: 6, padding: 10, fontSize: 12, color: "#991b1b", marginBottom: 12 }}>
                ⛔ Existem verificações BLOCKED. Para aprovar, você precisará sobrescrever — informe um comentário justificando.
              </div>
            )}

            <div style={{ marginBottom: 12 }}>
              <label style={{ fontSize: 12, color: "#555", display: "block", marginBottom: 4 }}>
                Comentário {hasBlocked ? <strong>(obrigatório para override BLOCKED)</strong> : "(opcional para aprovação, obrigatório para rejeição)"}:
              </label>
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Descreva sua decisão…"
                style={{
                  width: "100%",
                  height: 80,
                  borderRadius: 6,
                  border: "1px solid #d1d5db",
                  padding: 8,
                  fontSize: 13,
                  resize: "vertical",
                  boxSizing: "border-box",
                }}
              />
            </div>

            {error && <p style={{ color: "#ef4444", fontSize: 12, marginBottom: 10 }}>{error}</p>}
            {success && <p style={{ color: "#22c55e", fontSize: 12, marginBottom: 10 }}>{success}</p>}

            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              {(!hasBlocked || isOwner) && (
                <button
                  onClick={handleApprove}
                  disabled={acting}
                  style={{
                    background: "#22c55e",
                    color: "#fff",
                    border: "none",
                    borderRadius: 6,
                    padding: "9px 20px",
                    fontSize: 13,
                    cursor: acting ? "wait" : "pointer",
                    fontWeight: 600,
                  }}
                >
                  {acting ? "Processando…" : hasBlocked ? "Aprovar (sobrescrever BLOCKED)" : "Aprovar"}
                </button>
              )}
              <button
                onClick={handleReject}
                disabled={acting}
                style={{
                  background: "#ef4444",
                  color: "#fff",
                  border: "none",
                  borderRadius: 6,
                  padding: "9px 20px",
                  fontSize: 13,
                  cursor: acting ? "wait" : "pointer",
                  fontWeight: 600,
                }}
              >
                Rejeitar
              </button>
              <button
                onClick={handleVariation}
                disabled={acting}
                style={{
                  background: "#6366f1",
                  color: "#fff",
                  border: "none",
                  borderRadius: 6,
                  padding: "9px 20px",
                  fontSize: 13,
                  cursor: acting ? "wait" : "pointer",
                  fontWeight: 600,
                }}
              >
                Solicitar nova variação
              </button>
            </div>
          </div>
        )}

        {alreadyActed && (
          <div
            style={{
              background: "#f0fdf4",
              border: "1px solid #bbf7d0",
              borderRadius: 8,
              padding: "14px 18px",
              fontSize: 13,
              color: "#166534",
            }}
          >
            Este criativo já foi {detail.status === "approved" ? "aprovado" : "rejeitado"}.
          </div>
        )}
      </main>
    </>
  );
}
