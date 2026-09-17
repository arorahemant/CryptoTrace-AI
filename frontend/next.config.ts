import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";

const nextConfig = (phase: string): NextConfig => {
  const devApiTarget = phase === PHASE_DEVELOPMENT_SERVER
    ? process.env.DEV_API_PROXY_TARGET?.trim().replace(/\/+$/, "")
    : undefined;

  // DEV_API_PROXY_TARGET opts into a local proxy; production keeps static export.
  if (devApiTarget) {
    return {
      async rewrites() {
        return [{ source: "/api/v1/:path*", destination: `${devApiTarget}/api/v1/:path*` }];
      },
    };
  }

  return { output: "export" };
};

export default nextConfig;
