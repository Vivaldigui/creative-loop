import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // standalone output required for Docker deployment (copies only production files)
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  },
  async rewrites() {
    const apiTarget = process.env.API_PROXY_TARGET;
    if (!apiTarget) return [];

    return [
      {
        source: "/api/:path*",
        destination: `${apiTarget.replace(/\/$/, "")}/:path*`,
      },
    ];
  },
};

export default nextConfig;
