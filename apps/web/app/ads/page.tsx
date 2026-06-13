"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Nav } from "@/components/Nav";
import { FictitiousBanner } from "@/components/FictitiousBanner";
import { api, SourceAdOut } from "@/lib/api";

const LABELS = ["", "winner", "loser", "neutral"];
const OBJECTIVES = ["", "OUTCOME_SALES", "OUTCOME_LEADS", "OUTCOME_AWARENESS", "OUTCOME_ENGAGEMENT"];
const STATUSES = ["", "ACTIVE", "PAUSED", "ARCHIVED", "DELETED"];
const PAGE_SIZE = 20;

export default function AdsLibraryPage() {
  const router = useRouter();
  const [ads, setAds] = useState<SourceAdOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);

  const [filters, setFilters] = useState({
    performance_label: "",
    source: "",
    objective: "",
    effective_status: "",
    is_fictitious: "" as "" | "true" | "false",
  });

  const loadAds = useCallback(async (reset = false) => {
    setLoading(true);
    const currentOffset = reset ? 0 : offset;
    try {
      const params: Record<string, string | boolean | number> = {
        limit: PAGE_SIZE,
        offset: currentOffset,
      };
      if (filters.performance_label) params.performance_label = filters.performance_label;
      if (filters.source) params.source = filters.source;
      if (filters.objective) params.objective = filters.objective;
      if (filters.effective_status) params.effective_status = filters.effective_status;
      if (filters.is_fictitious !== "") params.is_fictitious = filters.is_fictitious === "true";

      const result = await api.sourceAds.list(params as Parameters<typeof api.sourceAds.list>[0]);
      if (reset) {
        setAds(result);
        setOffset(PAGE_SIZE);
      } else {
        setAds((prev) => [...prev, ...result]);
        setOffset((prev) => prev + PAGE_SIZE);
      }
      setHasMore(result.length === PAGE_SIZE);
    } catch {
      router.push("/login");
    } finally {
      setLoading(false);
    }
  }, [filters, offset, router]);

  useEffect(() => {
    loadAds(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  const handleFilter = (key: string, value: string) => {
    setFilters((p) => ({ ...p, [key]: value }));
  };

  return (
    <>
      <Nav />
      <main style={{ maxWidth: 1000, margin: "0 auto", padding: "28px 20px" }}>
        <FictitiousBanner />
        <h1 style={{ marginTop: 0 }}>Biblioteca de Anúncios Históricos</h1>

        {/* Filter bar */}
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 20, fontSize: 13 }}>
          <FilterSelect
            label="Label"
            value={filters.performance_label}
            options={LABELS}
            onChange={(v) => handleFilter("performance_label", v)}
          />
          <FilterSelect
            label="Objetivo"
            value={filters.objective}
            options={OBJECTIVES}
            onChange={(v) => handleFilter("objective", v)}
          />
          <FilterSelect
            label="Status"
            value={filters.effective_status}
            options={STATUSES}
            onChange={(v) => handleFilter("effective_status", v)}
          />
          <FilterSelect
            label="Dados"
            value={filters.is_fictitious}
            options={["", "true", "false"]}
            labels={["Todos", "Fictícios", "Reais"]}
            onChange={(v) => handleFilter("is_fictitious", v)}
          />
          <div>
            <label style={labelStyle}>Fonte</label>
            <input
              value={filters.source}
              onChange={(e) => handleFilter("source", e.target.value)}
              placeholder="ex: real, mock"
              style={{ padding: "5px 8px", borderRadius: 4, border: "1px solid #ddd", fontSize: 13, width: 100 }}
            />
          </div>
          <button
            onClick={() => setFilters({ performance_label: "", source: "", objective: "", effective_status: "", is_fictitious: "" })}
            style={{ alignSelf: "flex-end", background: "#eee", border: "none", borderRadius: 4, padding: "6px 12px", cursor: "pointer", fontSize: 12 }}
          >
            Limpar
          </button>
        </div>

        {/* Results count */}
        <p style={{ fontSize: 12, color: "#888", marginBottom: 12 }}>
          {ads.length} anúncio{ads.length !== 1 ? "s" : ""} carregado{ads.length !== 1 ? "s" : ""}
        </p>

        {ads.length === 0 && !loading ? (
          <p style={{ color: "#888" }}>
            Nenhum anúncio encontrado. Acesse <Link href="/integrations" style={{ color: "#4c6ef5" }}>Integrações</Link> e execute uma importação.
          </p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {ads.map((ad) => (
              <Link
                key={ad.id}
                href={`/ads/${ad.id}`}
                style={{ textDecoration: "none", color: "inherit" }}
              >
                <div
                  style={{
                    background: "#fff",
                    borderRadius: 8,
                    padding: "16px 20px",
                    boxShadow: "0 1px 4px rgba(0,0,0,.08)",
                    display: "grid",
                    gridTemplateColumns: "1fr auto",
                    gap: 12,
                    cursor: "pointer",
                  }}
                >
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                      <span style={{ fontWeight: 600 }}>{ad.name}</span>
                      <SourceBadge source={ad.source} isFictitious={ad.is_fictitious} />
                      {ad.effective_status && (
                        <span style={{ fontSize: 11, color: "#888" }}>{ad.effective_status}</span>
                      )}
                    </div>
                    {ad.headline && <div style={{ fontSize: 13, color: "#555", marginBottom: 4 }}>{ad.headline}</div>}
                    <div style={{ display: "flex", gap: 10, flexWrap: "wrap", fontSize: 12, color: "#888" }}>
                      {ad.ad_format && <span>Formato: {ad.ad_format}</span>}
                      {ad.objective && <span>Objetivo: {ad.objective}</span>}
                      {ad.source_adset && <span>Ad Set: {ad.source_adset.name}</span>}
                    </div>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
                    <LabelBadge label={ad.performance_label} />
                    {ad.snapshots[0] && (
                      <div style={{ fontSize: 12, color: "#888", textAlign: "right" }}>
                        <div>Gasto: R$ {(ad.snapshots[0].spend ?? 0).toFixed(2)}</div>
                        <div>ROAS: {ad.snapshots[0].roas?.toFixed(2) ?? "—"}</div>
                        <div>CTR: {ad.snapshots[0].ctr?.toFixed(1) ?? "—"}%</div>
                      </div>
                    )}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}

        {loading && <p style={{ textAlign: "center", color: "#888", marginTop: 20 }}>Carregando...</p>}

        {!loading && hasMore && (
          <div style={{ textAlign: "center", marginTop: 20 }}>
            <button
              onClick={() => loadAds(false)}
              style={{ background: "#4c6ef5", color: "#fff", border: "none", borderRadius: 6, padding: "10px 24px", cursor: "pointer", fontSize: 14 }}
            >
              Carregar mais
            </button>
          </div>
        )}
      </main>
    </>
  );
}

function FilterSelect({
  label,
  value,
  options,
  labels,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  labels?: string[];
  onChange: (v: string) => void;
}) {
  return (
    <div>
      <label style={labelStyle}>{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{ padding: "5px 8px", borderRadius: 4, border: "1px solid #ddd", fontSize: 13 }}
      >
        {options.map((o, i) => (
          <option key={o} value={o}>{labels ? labels[i] : o || "Todos"}</option>
        ))}
      </select>
    </div>
  );
}

function SourceBadge({ source, isFictitious }: { source: string | null; isFictitious: boolean }) {
  if (isFictitious) {
    return (
      <span style={{ background: "#d0ebff", borderRadius: 3, padding: "1px 6px", fontSize: 10, fontWeight: 600, color: "#1864ab" }}>
        fictício
      </span>
    );
  }
  if (source === "real") {
    return (
      <span style={{ background: "#d3f9d8", borderRadius: 3, padding: "1px 6px", fontSize: 10, fontWeight: 600, color: "#1a6b35" }}>
        real
      </span>
    );
  }
  return null;
}

function LabelBadge({ label }: { label: string | null }) {
  const colors: Record<string, string> = { winner: "#d4edda", loser: "#f8d7da", neutral: "#e2e3e5" };
  return (
    <span
      style={{
        background: colors[label ?? ""] ?? "#e2e3e5",
        borderRadius: 4,
        padding: "3px 10px",
        fontSize: 12,
        fontWeight: 600,
      }}
    >
      {label ?? "sem label"}
    </span>
  );
}

const labelStyle: React.CSSProperties = {
  display: "block", fontSize: 10, color: "#999", marginBottom: 3, fontWeight: 600, textTransform: "uppercase",
};
