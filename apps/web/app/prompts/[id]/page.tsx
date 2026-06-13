"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Nav } from "@/components/Nav";
import { FictitiousBanner } from "@/components/FictitiousBanner";
import { api, PromptTemplateDetailOut, PromptVersionOut, DiffOut } from "@/lib/api";

const KNOWN_FIELDS = [
  "product_name", "cta_text", "objective", "ad_format", "channel",
  "positioning", "exact_text", "margins", "mandatory_elements",
  "authorized_references", "originality_note", "do_not_copy",
  "policy_risks", "learnings_used", "known_limitations",
];

export default function PromptDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [template, setTemplate] = useState<PromptTemplateDetailOut | null>(null);
  const [versions, setVersions] = useState<PromptVersionOut[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<PromptVersionOut | null>(null);
  const [compareVersion, setCompareVersion] = useState<PromptVersionOut | null>(null);
  const [diff, setDiff] = useState<DiffOut | null>(null);
  const [loadingDiff, setLoadingDiff] = useState(false);
  const [showReviseForm, setShowReviseForm] = useState(false);
  const [reviseFields, setReviseFields] = useState<Record<string, string>>({});
  const [reviseReason, setReviseReason] = useState("");
  const [revising, setRevising] = useState(false);
  const [reviseError, setReviseError] = useState<string | null>(null);

  useEffect(() => {
    api.prompts.get(id)
      .then((t) => {
        setTemplate(t);
        if (t.latest_version) {
          const fields: Record<string, string> = {};
          if (t.latest_version.structured_fields) {
            for (const [k, v] of Object.entries(t.latest_version.structured_fields)) {
              fields[k] = String(v ?? "");
            }
          }
          setReviseFields(fields);
        }
      })
      .catch(() => router.push("/login"));

    api.prompts.versions(id)
      .then((vs) => {
        setVersions(vs);
        if (vs.length > 0) setSelectedVersion(vs[vs.length - 1]);
      })
      .catch(() => {});
  }, [id, router]);

  async function loadDiff(vA: PromptVersionOut, vB: PromptVersionOut) {
    setLoadingDiff(true);
    setDiff(null);
    try {
      const d = await api.promptVersions.diff(vA.id, vB.id);
      setDiff(d);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingDiff(false);
    }
  }

  async function doRevise() {
    setRevising(true);
    setReviseError(null);
    try {
      const pv = await api.prompts.revise(id, {
        fields: reviseFields,
        change_reason: reviseReason || "Revisão manual",
      });
      setVersions((prev) => [...prev, pv]);
      setSelectedVersion(pv);
      setTemplate((t) => t ? { ...t, latest_version: pv, version_count: t.version_count + 1 } : t);
      setShowReviseForm(false);
      setReviseReason("");
    } catch (e) {
      setReviseError(String(e));
    } finally {
      setRevising(false);
    }
  }

  function handleSelectVersion(v: PromptVersionOut) {
    setSelectedVersion(v);
    setCompareVersion(null);
    setDiff(null);
  }

  function handleCompare(v: PromptVersionOut) {
    if (!selectedVersion || v.id === selectedVersion.id) return;
    setCompareVersion(v);
    loadDiff(selectedVersion, v);
  }

  if (!template) return <p style={{ padding: 40 }}>Carregando...</p>;

  return (
    <>
      <Nav />
      <main style={{ maxWidth: 1000, margin: "0 auto", padding: "28px 20px" }}>
        <FictitiousBanner />

        <button onClick={() => router.back()} style={linkBtn}>← Voltar</button>
        <div style={{ display: "flex", gap: 10, alignItems: "baseline", marginTop: 8, marginBottom: 4, flexWrap: "wrap" }}>
          <h1 style={{ margin: 0 }}>{template.name}</h1>
          <Badge bg={template.status === "active" ? "#d4edda" : "#e2e3e5"} fg={template.status === "active" ? "#155724" : "#444"}>
            {template.status}
          </Badge>
          {template.ad_format && <Badge bg="#e8f4fd" fg="#1864ab">{template.ad_format}</Badge>}
          {template.objective && <Badge bg="#f3f0ff" fg="#5f3dc4">{template.objective}</Badge>}
        </div>
        <p style={{ fontSize: 12, color: "#888", margin: "0 0 20px" }}>
          {template.version_count} versão{template.version_count !== 1 ? "ões" : ""} · criado: {template.created_at ? new Date(template.created_at).toLocaleString("pt-BR") : "—"}
        </p>

        <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", gap: 20, alignItems: "start" }}>

          {/* ── Version timeline (left column) ────────────────── */}
          <div style={{ background: "#fff", borderRadius: 8, padding: "14px 16px", boxShadow: "0 1px 4px rgba(0,0,0,.08)" }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: "#888", marginBottom: 10, textTransform: "uppercase" }}>
              Histórico ({versions.length})
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {versions.map((v) => {
                const isSelected = selectedVersion?.id === v.id;
                const isCompare = compareVersion?.id === v.id;
                return (
                  <div
                    key={v.id}
                    style={{
                      borderRadius: 5,
                      padding: "8px 10px",
                      background: isSelected ? "#e8f4fd" : isCompare ? "#f3f0ff" : "#f8f9fa",
                      border: isSelected ? "1px solid #74c0fc" : isCompare ? "1px solid #b197fc" : "1px solid transparent",
                      cursor: "pointer",
                      fontSize: 12,
                    }}
                    onClick={() => handleSelectVersion(v)}
                  >
                    <div style={{ fontWeight: 700, color: isSelected ? "#1864ab" : isCompare ? "#5f3dc4" : "#333" }}>
                      v{v.version_number}
                      {isSelected && <span style={{ marginLeft: 6, fontSize: 10, fontWeight: 400, color: "#1864ab" }}>atual</span>}
                      {isCompare && <span style={{ marginLeft: 6, fontSize: 10, fontWeight: 400, color: "#5f3dc4" }}>comparando</span>}
                    </div>
                    {v.change_reason && (
                      <div style={{ color: "#666", marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {v.change_reason}
                      </div>
                    )}
                    <div style={{ color: "#aaa", marginTop: 2, fontSize: 10 }}>
                      {v.created_at ? new Date(v.created_at).toLocaleString("pt-BR") : ""}
                    </div>
                    {selectedVersion && v.id !== selectedVersion.id && (
                      <button
                        onClick={(e) => { e.stopPropagation(); handleCompare(v); }}
                        style={{ marginTop: 4, background: "none", border: "1px solid #b197fc", borderRadius: 3, padding: "2px 6px", fontSize: 10, color: "#5f3dc4", cursor: "pointer" }}
                      >
                        Comparar
                      </button>
                    )}
                  </div>
                );
              })}
            </div>

            {/* New revision button */}
            <button
              onClick={() => setShowReviseForm((p) => !p)}
              style={{ marginTop: 14, width: "100%", background: "#7c83ff", color: "#fff", border: "none", borderRadius: 5, padding: "8px 0", fontSize: 12, cursor: "pointer" }}
            >
              + Criar revisão
            </button>
          </div>

          {/* ── Right column ──────────────────────────────────── */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

            {/* Revise form */}
            {showReviseForm && (
              <div style={{ background: "#fff", borderRadius: 8, padding: "16px 20px", boxShadow: "0 1px 4px rgba(0,0,0,.08)" }}>
                <h3 style={{ margin: "0 0 14px", fontSize: 15 }}>Nova revisão</h3>
                {reviseError && <div style={errorBox}>{reviseError}</div>}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 12 }}>
                  {KNOWN_FIELDS.map((key) => (
                    <div key={key}>
                      <label style={labelStyle}>{key}</label>
                      <input
                        value={reviseFields[key] ?? ""}
                        onChange={(e) => setReviseFields((p) => ({ ...p, [key]: e.target.value }))}
                        placeholder={`ex: ${key}`}
                        style={inputStyle}
                      />
                    </div>
                  ))}
                </div>
                <div style={{ marginBottom: 12 }}>
                  <label style={labelStyle}>Motivo da revisão</label>
                  <input
                    value={reviseReason}
                    onChange={(e) => setReviseReason(e.target.value)}
                    placeholder="ex: Testando CTA diferente"
                    style={{ ...inputStyle, width: "100%", boxSizing: "border-box" }}
                  />
                </div>
                <div style={{ display: "flex", gap: 10 }}>
                  <button
                    onClick={doRevise}
                    disabled={revising}
                    style={{ background: "#7c83ff", color: "#fff", border: "none", borderRadius: 5, padding: "8px 18px", fontSize: 13, cursor: revising ? "not-allowed" : "pointer", opacity: revising ? 0.7 : 1 }}
                  >
                    {revising ? "Criando..." : "Criar versão"}
                  </button>
                  <button
                    onClick={() => setShowReviseForm(false)}
                    style={{ background: "none", border: "1px solid #ddd", borderRadius: 5, padding: "8px 18px", fontSize: 13, cursor: "pointer", color: "#666" }}
                  >
                    Cancelar
                  </button>
                </div>
              </div>
            )}

            {/* Selected version detail */}
            {selectedVersion && (
              <div style={{ background: "#fff", borderRadius: 8, padding: "16px 20px", boxShadow: "0 1px 4px rgba(0,0,0,.08)" }}>
                <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
                  <h3 style={{ margin: 0, fontSize: 15 }}>Versão {selectedVersion.version_number}</h3>
                  <Badge bg="#e8f4fd" fg="#1864ab">{selectedVersion.author_type}</Badge>
                  {selectedVersion.target_model && (
                    <Badge bg="#f3f0ff" fg="#5f3dc4">{selectedVersion.target_model}</Badge>
                  )}
                  {selectedVersion.content_hash && (
                    <code style={{ fontSize: 10, color: "#aaa" }}>{selectedVersion.content_hash.slice(0, 16)}…</code>
                  )}
                </div>
                {selectedVersion.change_reason && (
                  <p style={{ fontSize: 12, color: "#777", margin: "0 0 10px", fontStyle: "italic" }}>
                    &ldquo;{selectedVersion.change_reason}&rdquo;
                  </p>
                )}
                <pre style={preStyle}>{selectedVersion.prompt_text}</pre>

                {/* Structured fields */}
                {selectedVersion.structured_fields && Object.keys(selectedVersion.structured_fields).length > 0 && (
                  <div style={{ marginTop: 12 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: "#888", textTransform: "uppercase", marginBottom: 8 }}>Campos estruturados</div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, fontSize: 12 }}>
                      {Object.entries(selectedVersion.structured_fields).map(([k, v]) => (
                        v ? (
                          <div key={k} style={{ background: "#f8f9fa", borderRadius: 4, padding: "5px 8px" }}>
                            <span style={{ color: "#888", fontSize: 10, textTransform: "uppercase" }}>{k}</span>
                            <div style={{ color: "#333", marginTop: 2, wordBreak: "break-word" }}>{String(v)}</div>
                          </div>
                        ) : null
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Diff viewer */}
            {compareVersion && (
              <div style={{ background: "#fff", borderRadius: 8, padding: "16px 20px", boxShadow: "0 1px 4px rgba(0,0,0,.08)" }}>
                <h3 style={{ margin: "0 0 12px", fontSize: 15 }}>
                  Diff: v{selectedVersion?.version_number} → v{compareVersion.version_number}
                </h3>

                {loadingDiff && <p style={{ color: "#888", fontSize: 13 }}>Carregando diff...</p>}

                {diff && (
                  <div>
                    {/* Field changes summary */}
                    {diff.changed_field_count > 0 && (
                      <div style={{ marginBottom: 14 }}>
                        <div style={{ fontSize: 11, fontWeight: 700, color: "#888", textTransform: "uppercase", marginBottom: 8 }}>
                          Campos alterados ({diff.changed_field_count})
                        </div>
                        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                          {Object.entries(diff.field_changes).map(([field, change]) => (
                            <div key={field} style={{ background: "#f8f9fa", borderRadius: 4, padding: "8px 10px", fontSize: 12 }}>
                              <div style={{ fontWeight: 700, color: "#333", marginBottom: 4, textTransform: "uppercase", fontSize: 10 }}>{field}</div>
                              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                                <div>
                                  <span style={{ fontSize: 10, color: "#888" }}>antes</span>
                                  <div style={{ background: "#ffeef0", borderRadius: 3, padding: "3px 6px", color: "#c00", marginTop: 2, wordBreak: "break-word" }}>
                                    {String(change.before ?? "")}
                                  </div>
                                </div>
                                <div>
                                  <span style={{ fontSize: 10, color: "#888" }}>depois</span>
                                  <div style={{ background: "#e6ffed", borderRadius: 3, padding: "3px 6px", color: "#1a6b35", marginTop: 2, wordBreak: "break-word" }}>
                                    {String(change.after ?? "")}
                                  </div>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Unified diff */}
                    {diff.unified_diff && (
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 700, color: "#888", textTransform: "uppercase", marginBottom: 6 }}>
                          Diff unificado
                        </div>
                        <pre style={{ ...preStyle, maxHeight: 400 }}>
                          {diff.unified_diff.split("\n").map((line, i) => (
                            <span
                              key={i}
                              style={{
                                display: "block",
                                background: line.startsWith("+") ? "#e6ffed" : line.startsWith("-") ? "#ffeef0" : "transparent",
                                color: line.startsWith("+") ? "#1a6b35" : line.startsWith("-") ? "#c00" : "#555",
                              }}
                            >
                              {line || " "}
                            </span>
                          ))}
                        </pre>
                      </div>
                    )}

                    <button
                      onClick={() => { setCompareVersion(null); setDiff(null); }}
                      style={{ marginTop: 10, background: "none", border: "1px solid #ddd", borderRadius: 4, padding: "4px 12px", fontSize: 11, cursor: "pointer", color: "#666" }}
                    >
                      Fechar diff
                    </button>
                  </div>
                )}
              </div>
            )}

          </div>
        </div>
      </main>
    </>
  );
}

function Badge({ bg, fg, children }: { bg: string; fg: string; children: React.ReactNode }) {
  return (
    <span style={{ background: bg, color: fg, borderRadius: 3, padding: "2px 8px", fontSize: 11, fontWeight: 600, whiteSpace: "nowrap" as const }}>
      {children}
    </span>
  );
}

const preStyle: React.CSSProperties = {
  background: "#f8f9fa",
  borderRadius: 5,
  padding: 12,
  fontSize: 11,
  overflow: "auto",
  maxHeight: 300,
  margin: 0,
  whiteSpace: "pre-wrap",
  wordBreak: "break-word",
};
const labelStyle: React.CSSProperties = {
  display: "block", fontSize: 10, color: "#999", marginBottom: 3, fontWeight: 600, textTransform: "uppercase",
};
const inputStyle: React.CSSProperties = {
  padding: "5px 8px", borderRadius: 4, border: "1px solid #ddd", fontSize: 12, width: "100%", boxSizing: "border-box",
};
const errorBox: React.CSSProperties = {
  background: "#ffe0e0", color: "#c00", padding: "8px 12px", borderRadius: 5, fontSize: 12, marginBottom: 10,
};
const linkBtn: React.CSSProperties = {
  background: "none", border: "none", cursor: "pointer", color: "#7c83ff", fontSize: 14, padding: 0,
};
