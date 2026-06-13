"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.auth.login(email, password);
      router.push("/dashboard");
    } catch {
      setError("Credenciais inválidas ou servidor indisponível.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#1a1a2e",
      }}
    >
      <form
        onSubmit={handleSubmit}
        style={{
          background: "#fff",
          padding: 36,
          borderRadius: 10,
          width: 360,
          display: "flex",
          flexDirection: "column",
          gap: 16,
        }}
      >
        <h1 style={{ margin: 0, fontSize: 22, color: "#1a1a2e" }}>Creative Loop</h1>
        <p style={{ margin: 0, color: "#666", fontSize: 14 }}>Faça login para continuar</p>

        {error && (
          <div style={{ background: "#ffe0e0", color: "#c00", padding: "8px 12px", borderRadius: 5, fontSize: 13 }}>
            {error}
          </div>
        )}

        <label style={{ fontSize: 13, color: "#444" }}>
          E-mail
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={{ display: "block", width: "100%", marginTop: 4, padding: "8px 10px", borderRadius: 5, border: "1px solid #ccc", boxSizing: "border-box" }}
          />
        </label>

        <label style={{ fontSize: 13, color: "#444" }}>
          Senha
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={{ display: "block", width: "100%", marginTop: 4, padding: "8px 10px", borderRadius: 5, border: "1px solid #ccc", boxSizing: "border-box" }}
          />
        </label>

        <button
          type="submit"
          disabled={loading}
          style={{
            background: "#7c83ff",
            color: "#fff",
            border: "none",
            borderRadius: 6,
            padding: "10px 0",
            fontSize: 15,
            cursor: loading ? "not-allowed" : "pointer",
            opacity: loading ? 0.7 : 1,
          }}
        >
          {loading ? "Entrando..." : "Entrar"}
        </button>
      </form>
    </main>
  );
}
