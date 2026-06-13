"use client";

import { useEffect, useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Nav } from "@/components/Nav";
import { FictitiousBanner } from "@/components/FictitiousBanner";
import { api, ProductOut } from "@/lib/api";

export default function ProductsPage() {
  const router = useRouter();
  const [products, setProducts] = useState<ProductOut[]>([]);
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.products.list().catch(() => router.push("/login")).then((p) => p && setProducts(p));
  }, [router]);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      const created = await api.products.create({ name, description: description || undefined, category: category || undefined });
      setProducts((prev) => [created, ...prev]);
      setName("");
      setCategory("");
      setDescription("");
    } catch (err) {
      setError(String(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <Nav />
      <main style={{ maxWidth: 800, margin: "0 auto", padding: "28px 20px" }}>
        <FictitiousBanner />
        <h1 style={{ marginTop: 0 }}>Produtos / Identidade de Marca</h1>

        <section style={{ background: "#fff", borderRadius: 8, padding: 24, marginBottom: 28, boxShadow: "0 1px 4px rgba(0,0,0,.08)" }}>
          <h2 style={{ marginTop: 0, fontSize: 16 }}>Novo produto</h2>
          {error && (
            <div style={{ background: "#ffe0e0", color: "#c00", padding: "8px 12px", borderRadius: 5, fontSize: 13, marginBottom: 12 }}>
              {error}
            </div>
          )}
          <form onSubmit={handleCreate} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <label style={labelStyle}>
              Nome *
              <input required value={name} onChange={(e) => setName(e.target.value)} style={inputStyle} />
            </label>
            <label style={labelStyle}>
              Categoria
              <input value={category} onChange={(e) => setCategory(e.target.value)} style={inputStyle} />
            </label>
            <label style={labelStyle}>
              Descrição
              <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} style={{ ...inputStyle, resize: "vertical" }} />
            </label>
            <button type="submit" disabled={saving} style={btnStyle}>
              {saving ? "Salvando..." : "Criar produto"}
            </button>
          </form>
        </section>

        <h2>Produtos cadastrados</h2>
        {products.length === 0 ? (
          <p style={{ color: "#888" }}>Nenhum produto ainda.</p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0, display: "flex", flexDirection: "column", gap: 10 }}>
            {products.map((p) => (
              <li
                key={p.id}
                style={{ background: "#fff", borderRadius: 8, padding: "14px 20px", boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}
              >
                <strong>{p.name}</strong>
                {p.category && <span style={{ marginLeft: 10, fontSize: 12, color: "#888" }}>{p.category}</span>}
                {p.is_fictitious && (
                  <span style={{ marginLeft: 10, fontSize: 11, color: "#b08800", background: "#fff3cd", padding: "1px 6px", borderRadius: 4 }}>
                    fictício
                  </span>
                )}
                {p.description && <p style={{ margin: "6px 0 0", fontSize: 13, color: "#555" }}>{p.description}</p>}
              </li>
            ))}
          </ul>
        )}
      </main>
    </>
  );
}

const labelStyle: React.CSSProperties = { fontSize: 13, color: "#444", display: "flex", flexDirection: "column", gap: 4 };
const inputStyle: React.CSSProperties = { padding: "8px 10px", borderRadius: 5, border: "1px solid #ccc", fontSize: 14 };
const btnStyle: React.CSSProperties = {
  background: "#7c83ff", color: "#fff", border: "none", borderRadius: 6,
  padding: "10px 20px", fontSize: 14, cursor: "pointer", alignSelf: "flex-start",
};
