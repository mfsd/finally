import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";

const baseConfig: NextConfig = {
  output: "export",
  eslint: {
    ignoreDuringBuilds: false
  }
};

export default function nextConfig(phase: string): NextConfig {
  if (phase === PHASE_DEVELOPMENT_SERVER) {
    return {
      ...baseConfig,
      async rewrites() {
        return [
          {
            source: "/api/:path*",
            destination: "http://localhost:8000/api/:path*"
          }
        ];
      }
    };
  }

  return baseConfig;
}
