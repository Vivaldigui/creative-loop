"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Nav } from "@/components/Nav";
import { api, PublishedAdOut } from "@/lib/api";

// ── Status badge ─────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, { bg: string; text: string }> = {
    PAUSED: { bg: "#dbeafe", text: "#1e40af" },
    ACTIVE: { bg: "#dcfce7", text: "#166534" },
    DELETED: { bg: "#fee2e2", text: "#991b1b" },
    requires_manual_review: { bg: "#fef9c3", text: "#713f12" },
  };
  const c = colors[status] ?? { bg: "#f3f4f6", text: "#374151" };
  return (
    <span
      style={{
        background: c.bg,
        color: c.text,
        borderRadius: 4,
        padding: "2px 8px",
        fontSize: 11,
        fontWeight: 700,
        textTransform: "uppercase",
      }}
    >
      {status}
    </span>
  );
}

// ── Emergency pause button ────────────────────────────────────────────────────

function EmergencyPauseButton({ ad, onDone }: { ad: PublishedAdOut; onDone: () => void }) {
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  async function handle() {
    if (!confirm(`PAUSA DE EMERGÊNCIA para ${ad.id.slice(0, 8)}…\n\nIsso tentará pausar o anúncio imediatamente. Confirmar?`)) return;
    setLoading(true);
    setErr("");
    try {
      await api.publishedAds.emergencyPause(ad.id);
      onDone();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <button
        onClick={handle}
        disabled={loading}
        style={{
          padding: "5px 12px",
          background: loading ? "#9ca3af" : "#dc2626",
          color: "#fff",
          border: "none",
          borderRadius: 5,
          cursor: loading ? "not-allowed" : "pointer",
          fontWeight: 700,
          fontSize: 11,
        }}
      >
        {loading ? "Pausando…" : "PAUSA EMERGÊNCIA"}
      </button>
      {err && <p style={{ color: "#dc2626", fontSize: 10, marginTop: 2 }}>{err}</p>}
    </div>
  );
}

// ── Activate button (owner only) ──────────────────────────────────────────────

function ActivateButton({ ad, onDone }: { ad: PublishedAdOut; onDone: () => void }) {
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  async function handle() {
    const metaId = ad.meta_ad_id;
    if (!metaId) {
      setErr("meta_ad_id ausente — não é possível ativar");
      return;
    }
    const confirmed = confirm(
      `Ativar anúncio ${metaId}?\n\nIsso tornará o anúncio ATIVO na Meta. Apenas owners podem fazer isso.\n\nDigite o meta_ad_id para confirmar: ${metaId}`
    );
    if (!confirmed) return;
    setLoading(true);
    setErr("");
    try {
      await api.publishedAds.activate(ad.id, metaId);
      onDone();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <button
        onClick={handle}
        disabled={loading || ad.status === "ACTIVE"}
        style={{
          padding: "5px 12px",
          background: loading || ad.status === "ACTIVE" ? "#9ca3af" : "#059669",
          color: "#fff",
          border: "none",
          borderRadius: 5,
          cursor: loading || ad.status === "ACTIVE" ? "not-allowed" : "pointer",
          fontWeight: 700,
          fontSize: 11,
        }}
      >
        {loading ? "Ativando…" : "Ativar"}
      </button>
      {err && <p style={{ color: "#dc2626", fontSize: 10, marginTop: 2 }}>{err}</p>}
    </div>
  );
}

// ── Pause button ──────────────────────────────────────────────────────────────

function PauseButton({ ad, onDone }: { ad: PublishedAdOut; onDone: () => void }) {
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  async function handle() {
    if (!confirm(`Pausar anúncio ${ad.meta_ad_id ?? ad.id.slice(0, 8)}?`)) return;
    setLoading(true);
    setErr("");
    try {
      await api.publishedAds.pause(ad.id);
      onDone();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <button
        onClick={handle}
        disabled={loading || ad.status === "PAUSED"}
        style={{
          padding: "5px 12px",
          background: loading || ad.status === "PAUSED" ? "#9ca3af" : "#f59e0b",
          color: "#fff",
          border: "none",
          borderRadius: 5,
          cursor: loading || ad.status === "PAUSED" ? "not-allowed" : "pointer",
          fontWeight: 700,
          fontSize: 11,
        }}
      >
        {loading ? "Pausando…" : "Pausar"}
      </button>
      {err && <p style={{ color: "#dc2626", fontSize: 10, marginTop: 2 }}>{err}</p>}
    </div>
  );
}

// ── Refresh status button ─────────────────────────────────────────────────────

function RefreshButton({ ad, onDone }: { ad: PublishedAdOut; onDone: () => void }) {
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  async function handle() {
    setLoading(true);
    setErr("");
    try {
      await api.publishedAds.refreshStatus(ad.id);
      onDone();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <button
        onClick={handle}
        disabled={loading}
        style={{
          padding: "5px 10px",
          background: "#f3f4f6",
          border: "1px solid #d1d5db",
          borderRadius: 5,
          cursor: loading ? "not-allowed" : "pointer",
          fontSize: 11,
        }}
      >
        {loading ? "…" : "Atualizar status"}
      </button>
      {err && <p style={{ color: "#dc2626", fontSize: 10, marginTop: 2 }}>{err}</p>}
    </div>
  );
}

// ── Ad row ────────────────────────────────────────────────────────────────────

function AdRow({ ad, onRefresh }: { ad: PublishedAdOut; onRefresh: () => void }) {
  return (
    <tr style={{ borderBottom: "1px solid #f3f4f6", verticalAlign: "top" }}>
      <td style={tdStyle}>
        <code style={{ fontSize: 11 }}>{ad.id.slice(0, 12)}…</code>
        {ad.requires_manual_review && (
          <div style={{ fontSize: 10, color: "#b45309", marginTop: 2, fontWeight: 700 }}>
            REVISÃO MANUAL NECESSÁRIA
          </div>
        )}
      </td>
      <td style={tdStyle}>
        <StatusBadge status={ad.status} />
        <div style={{ fontSize: 10, color: "#6b7280", marginTop: 2 }}>{ad.workflow_state}</div>
      </td>
      <td style={{ ...tdStyle, fontFamily: "monospace", fontSize: 11 }}>
        {ad.meta_ad_id ?? <span style={{ color: "#9ca3af" }}>—</span>}
      </td>
      <td style={{ ...tdStyle, fontFamily: "monospace", fontSize: 11 }}>
        {ad.meta_campaign_id ? ad.meta_campaign_id.slice(0, 12) + "…" : <span style={{ color: "#9ca3af" }}>—</span>}
      </td>
      <td style={tdStyle}>
        <span
          style={{
            background: ad.dry_run ? "#fef9c3" : "#dcfce7",
            color: ad.dry_run ? "#713f12" : "#166534",
            borderRadius: 3,
            padding: "1px 6px",
            fontSize: 10,
            fontWeight: 700,
          }}
        >
          {ad.dry_run ? "DRY_RUN" : "REAL"}
        </span>
      </td>
      <td style={{ ...tdStyle, fontSize: 11, color: "#6b7280" }}>
        {new Date(ad.created_at).toLocaleDateString("pt-BR")}
      </td>
      <td style={tdStyle}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <RefreshButton ad={ad} onDone={onRefresh} />
          {!ad.dry_run && ad.status === "PAUSED" && <ActivateButton ad={ad} onDone={onRefresh} />}
          {!ad.dry_run && ad.status === "ACTIVE" && <PauseButton ad={ad} onDone={onRefresh} />}
          {!ad.dry_run && ad.status !== "DELETED" && (
            <EmergencyPauseButton ad={ad} onDone={onRefresh} />
          )}
        </div>
      </td>
    </tr>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function PublishedAdsPage() {
  const [ads, setAds] = useState<PublishedAdOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filterDryRun, setFilterDryRun] = useState<"all" | "real" | "dry">("all");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params: { dry_run?: boolean; limit?: number } = { limit: 50 };
      if (filterDryRun === "real") params.dry_run = false;
      if (filterDryRun === "dry") params.dry_run = true;
      const data = await api.publishedAds.list(params);
      setAds(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [filterDryRun]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div style={{ minHeight: "100vh", background: "#f5f5f5" }}>
      <Nav />
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "24px 16px" }}>
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 4 }}>
          <h1 style={{ fontSize: 22, fontWeight: 700 }}>Anúncios Publicados</h1>
          <Link href="/publish" style={{ fontSize: 13, color: "#3b82f6" }}>
            Nova publicação
          </Link>
        </div>
        <p style={{ color: "#6b7280", fontSize: 13, marginBottom: 20 }}>
          Fase 6 — Gerencie anúncios publicados na Meta. Ative, pause ou acione pausa de emergência.
        </p>

        <div
          style={{
            background: "#fff3cd",
            border: "1px solid #ffc107",
            borderRadius: 6,
            padding: "10px 14px",
            marginBottom: 16,
            fontSize: 12,
            color: "#664d03",
          }}
        >
          <strong>Atenção:</strong> Ativar um anúncio inicia gastos reais. Apenas usuários com papel{" "}
          <code>owner</code> podem ativar. Qualquer usuário autenticado pode acionar a pausa de
          emergência.
        </div>

        {/* Filters */}
        <div style={{ display: "flex", gap: 8, marginBottom: 16, alignItems: "center" }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: "#374151" }}>Filtrar:</span>
          {(["all", "real", "dry"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilterDryRun(f)}
              style={{
                padding: "4px 12px",
                border: "1px solid #d1d5db",
                borderRadius: 20,
                background: filterDryRun === f ? "#3b82f6" : "#fff",
                color: filterDryRun === f ? "#fff" : "#374151",
                fontSize: 12,
                cursor: "pointer",
                fontWeight: filterDryRun === f ? 700 : 400,
              }}
            >
              {f === "all" ? "Todos" : f === "real" ? "Real" : "DRY_RUN"}
            </button>
          ))}
          <button
            onClick={load}
            style={{
              marginLeft: "auto",
              padding: "4px 12px",
              border: "1px solid #d1d5db",
              borderRadius: 6,
              background: "#f3f4f6",
              fontSize: 12,
              cursor: "pointer",
            }}
          >
            Recarregar
          </button>
        </div>

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
            }}
          >
            {error}
          </div>
        )}

        {loading ? (
          <p style={{ color: "#9ca3af", fontSize: 13 }}>Carregando…</p>
        ) : ads.length === 0 ? (
          <div
            style={{
              background: "#fff",
              borderRadius: 8,
              padding: 40,
              textAlign: "center",
              border: "1px solid #e5e7eb",
              color: "#6b7280",
              fontSize: 14,
            }}
          >
            Nenhum anúncio encontrado.{" "}
            <Link href="/publish" style={{ color: "#3b82f6" }}>
              Publicar criativo
            </Link>
          </div>
        ) : (
          <div style={{ background: "#fff", borderRadius: 8, border: "1px solid #e5e7eb", overflow: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: "2px solid #e5e7eb", background: "#f9fafb" }}>
                  <th style={thStyle}>ID</th>
                  <th style={thStyle}>Status</th>
                  <th style={thStyle}>Meta Ad ID</th>
                  <th style={thStyle}>Campaign ID</th>
                  <th style={thStyle}>Modo</th>
                  <th style={thStyle}>Criado em</th>
                  <th style={thStyle}>Ações</th>
                </tr>
              </thead>
              <tbody>
                {ads.map((ad) => (
                  <AdRow key={ad.id} ad={ad} onRefresh={load} />
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p style={{ fontSize: 11, color: "#9ca3af", marginTop: 16 }}>
          {ads.length} anúncio(s) exibido(s). Em DRY_RUN, as ações de ativação/pausa retornam 400.
        </p>
      </div>
    </div>
  );
}

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "10px 12px",
  fontWeight: 700,
  fontSize: 12,
  color: "#6b7280",
};

const tdStyle: React.CSSProperties = {
  padding: "10px 12px",
};
