import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Every page is a client component that fetches from the API at runtime, so
  // the whole site can ship as static files (no Node server to host).
  output: "export",
  // Emits /archive/index.html rather than /archive.html, which every static
  // host serves correctly without custom rewrite rules.
  trailingSlash: true,
};

export default nextConfig;
