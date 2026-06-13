"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/integrations", label: "Integrações" },
  { href: "/products", label: "Produtos / Marca" },
  { href: "/ads", label: "Biblioteca de Anúncios" },
  { href: "/metrics", label: "Métricas" },
  { href: "/approvals", label: "Aprovações" },
  { href: "/prompts", label: "Prompts" },
  { href: "/publish", label: "Publicação (DRY_RUN)" },
  { href: "/published-ads", label: "Anúncios Publicados" },
  { href: "/experiments", label: "Experimentos" },
  { href: "/learnings", label: "Aprendizados" },
  { href: "/suggestions", label: "Sugestões" },
  { href: "/reports", label: "Relatórios" },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <nav
      style={{
        background: "#1a1a2e",
        padding: "0 24px",
        display: "flex",
        alignItems: "center",
        gap: 24,
        height: 52,
        flexWrap: "wrap",
      }}
    >
      <span style={{ color: "#7c83ff", fontWeight: 700, fontSize: 16, marginRight: 16 }}>
        Creative Loop
      </span>
      {links.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          style={{
            color: pathname.startsWith(l.href) ? "#fff" : "#aaa",
            textDecoration: "none",
            fontSize: 14,
            fontWeight: pathname.startsWith(l.href) ? 600 : 400,
          }}
        >
          {l.label}
        </Link>
      ))}
    </nav>
  );
}
