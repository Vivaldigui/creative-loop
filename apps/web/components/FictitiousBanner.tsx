"use client";

export function FictitiousBanner() {
  return (
    <div
      role="alert"
      style={{
        background: "#fff3cd",
        border: "1px solid #ffc107",
        borderRadius: 6,
        padding: "10px 16px",
        marginBottom: 20,
        fontWeight: 600,
        color: "#664d03",
      }}
    >
      DADOS FICTÍCIOS — Esta tela exibe informações simuladas para fins de demonstração. Nenhuma publicação real foi
      realizada.
    </div>
  );
}
