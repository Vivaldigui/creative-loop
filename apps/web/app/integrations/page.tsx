"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Nav } from "@/components/Nav";
import { api, SyncRunOut } from "@/lib/api";

type ProviderStatus = { provider: string; status: string; message?: string };

export default function IntegrationsPage() {
  const router = useRouter();
  const [testResults, setTestResults] = useState<Record<string, ProviderStatus>>({});
  const [accounts, setAccounts] = useState<unknown[]>([]);
  const [runs, setRuns] = useState<SyncRunOut[]>([]);
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadRuns = useCallback(async () => {
    try {
      const r = await api.sync.runs(10);
      setRuns(r);
    } catch {
      // not critical
    }
  }, []);

  useEffect(() => {
    api.auth.me()
      .then(() => loadRuns())
      .catch(() => router.push("/login"))
      .finally(() => setLoading(false));
  }, [router, loadRuns]);

  const testProvider = async (provider: "meta" | "openai" | "anthropic") => {
    try {
      const result = await api.integrations.test(provider);
      setTestResults((p) => ({ ...p, [provider]: result }));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setTestResults((p) => ({ ...p, [provider]: { provider, status: "error", message } }));
    }
  };

  const loadAccounts = async () => {
    try {
      const r = await api.integrations.metaAccounts();
      setAccounts(r.accounts);
    } catch {
      setAccounts([]);
    }
  };

  const runSync = async (kind: "history" | "incremental") => {
    setSyncing(true);
    setSyncMsg(null);
    try {
      const r = kind === "history"
        ? await api.sync.history()
        : await api.sync.incremental();
      setSyncMsg(`✓ ${r.message}`);
      await loadRuns();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setSyncMsg(`✗ Erro: ${message}`);
    } finally {
      setSyncing(false);
    }
  };

  if (loading) return <p style={{ padding: 40 }}>Carregando...</p>;

  return (
    <>
      <Nav />
      <main style={{ maxWidth: 900, margin: "0 auto", padding: "28px 20px" }}>
        <h1 style={{ marginTop: 0 }}>Integrações</h1>

        {/* Provider tests */}
        <Section title="Testar Conexões">
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            {(["meta", "anthropic", "openai"] as const).map((p) => (
              <div key={p} style={{ flex: "1 1 220px" }}>
                <div style={cardStyle}>
                  <strong style={{ textTransform: "capitalize" }}>{p}</strong>
                  <button onClick={() => testProvider(p)} style={btnStyle}>Testar</button>
                  {testResults[p] && (
                    <StatusBadge status={testResults[p].status} />
                  )}
                  {testResults[p]?.message && (
                    <p style={{ fontSize: 11, color: "#888", marginTop: 4 }}>{testResults[p].message}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Section>

        {/* Meta accounts */}
        <Section title="Contas Meta Autorizadas">
          <button onClick={loadAccounts} style={btnStyle}>Listar contas</button>
          {accounts.length > 0 && (
            <ul style={{ marginTop: 8, paddingLeft: 20 }}>
              {accounts.map((a: unknown, i) => {
                const acc = a as Record<string, unknown>;
                return (
                  <li key={i} style={{ fontSize: 13, marginBottom: 4 }}>
                    <strong>{String(acc.name ?? acc.id)}</strong> — ID: {String(acc.id)} — Moeda: {String(acc.currency ?? "—")}
                  </li>
                );
              })}
            </ul>
          )}
        </Section>

        {/* Sync triggers */}
        <Section title="Importação de Dados (Somente Leitura)">
          <div
            style={{
              background: "#fff3cd",
              border: "1px solid #ffc107",
              borderRadius: 6,
              padding: "10px 14px",
              marginBottom: 14,
              fontSize: 13,
            }}
          >
            <strong>Nota:</strong> Toda importação é somente leitura. Nenhum dado é alterado ou criado na Meta.
            Com <code>META_PROVIDER=mock</code> (padrão), os dados importados são simulados e marcados como fictícios.
          </div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <button
              onClick={() => runSync("history")}
              disabled={syncing}
              style={{ ...btnStyle, background: "#4c6ef5" }}
            >
              {syncing ? "Importando..." : "Importar Histórico Completo"}
            </button>
            <button
              onClick={() => runSync("incremental")}
              disabled={syncing}
              style={{ ...btnStyle, background: "#2e9e44" }}
            >
              {syncing ? "Importando..." : "Sync Incremental (30 dias)"}
            </button>
          </div>
          {syncMsg && (
            <p
              style={{
                marginTop: 10,
                padding: "8px 12px",
                borderRadius: 4,
                background: syncMsg.startsWith("✓") ? "#d3f9d8" : "#ffe3e3",
                fontSize: 13,
              }}
            >
              {syncMsg}
            </p>
          )}
        </Section>

        {/* Sync runs history */}
        <Section title="Histórico de Sincronizações">
          <button onClick={loadRuns} style={{ ...btnStyle, background: "#666", marginBottom: 10 }}>
            Atualizar
          </button>
          {runs.length === 0 ? (
            <p style={{ color: "#888", fontSize: 13 }}>Nenhuma sincronização executada ainda.</p>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ background: "#f0f0f0" }}>
                  {["Tipo", "Status", "Período", "Ads", "Snapshots", "Erros", "Finalizado em"].map((h) => (
                    <th key={h} style={{ padding: "6px 10px", textAlign: "left", borderBottom: "1px solid #ddd" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.id} style={{ borderBottom: "1px solid #eee" }}>
                    <td style={{ padding: "6px 10px" }}>{r.kind}</td>
                    <td style={{ padding: "6px 10px" }}>
                      <StatusBadge status={r.status} />
                    </td>
                    <td style={{ padding: "6px 10px", fontSize: 11, color: "#666" }}>
                      {r.date_start} – {r.date_stop}
                    </td>
                    <td style={{ padding: "6px 10px" }}>
                      {r.ads_created}c / {r.ads_updated}u
                    </td>
                    <td style={{ padding: "6px 10px" }}>
                      {r.snapshots_created}c / {r.snapshots_updated}u
                    </td>
                    <td style={{ padding: "6px 10px", color: r.error_detail ? "#e03131" : "#888", fontSize: 11 }}>
                      {r.error_detail ? r.error_detail.slice(0, 60) + "..." : "—"}
                    </td>
                    <td style={{ padding: "6px 10px", fontSize: 11, color: "#666" }}>
                      {r.finished_at ? new Date(r.finished_at).toLocaleString("pt-BR") : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Section>

        {/* Setup instructions */}
        <Section title="Configuração para Dados Reais">
          <div style={{ fontSize: 13, lineHeight: 1.7 }}>
            <p>Para importar dados reais da Meta, preencha no <code>.env</code>:</p>
            <pre style={{ background: "#f5f5f5", padding: 12, borderRadius: 4, overflowX: "auto" }}>
{`META_PROVIDER=real
META_APP_ID=<seu_app_id>
META_APP_SECRET=<seu_app_secret>
META_ACCESS_TOKEN=<token_long_lived>   # escopo mínimo: ads_read
META_AD_ACCOUNT_ID=act_<id_da_conta>`}
            </pre>
            <p>
              <strong>Atenção:</strong> O token precisa ter escopo <code>ads_read</code>. Não use tokens com
              <code>ads_management</code> — esse escopo permite escrita e viola o princípio do menor privilégio.
              Consulte <code>docs/META_SETUP.md</code> para o guia completo.
            </p>
          </div>
        </Section>
      </main>
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{ marginBottom: 32 }}>
      <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 12, borderBottom: "1px solid #eee", paddingBottom: 6 }}>
        {title}
      </h2>
      {children}
    </section>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    ok: "#d3f9d8",
    mock_ok: "#d0ebff",
    success: "#d3f9d8",
    running: "#fff3cd",
    error: "#ffe3e3",
    failed: "#ffe3e3",
    not_configured: "#f1f3f5",
    partial: "#fff3cd",
  };
  return (
    <span
      style={{
        background: colors[status] ?? "#f1f3f5",
        borderRadius: 4,
        padding: "2px 8px",
        fontSize: 11,
        fontWeight: 600,
        marginLeft: 6,
      }}
    >
      {status}
    </span>
  );
}

const cardStyle: React.CSSProperties = {
  background: "#fff",
  border: "1px solid #eee",
  borderRadius: 8,
  padding: "14px 16px",
  boxShadow: "0 1px 3px rgba(0,0,0,.06)",
};

const btnStyle: React.CSSProperties = {
  background: "#1a1a2e",
  color: "#fff",
  border: "none",
  borderRadius: 4,
  padding: "7px 14px",
  fontSize: 12,
  fontWeight: 600,
  cursor: "pointer",
  marginTop: 8,
};
