import type { NextConfig } from "next";

/**
 * The FastAPI backend runs separately (default http://127.0.0.1:8000).
 * Everything under /api is proxied to it, so the browser only ever talks to
 * one origin and no CORS configuration is needed on the Python side.
 */
const API_ORIGIN = process.env.BATRIS_API_ORIGIN ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_ORIGIN}/api/:path*` }];
  },
};

export default nextConfig;
