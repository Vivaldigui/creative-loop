import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Creative Loop",
  description: "AI-powered creative cycle platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body style={{ margin: 0, fontFamily: "system-ui, sans-serif", background: "#f5f5f5", color: "#111" }}>
        {children}
      </body>
    </html>
  );
}
