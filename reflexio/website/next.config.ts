import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    // Use environment variable or default to localhost:8081 for local development
    const apiUrl = process.env.API_BACKEND_URL || "http://localhost:8081";
    return [
      {
        source: "/api/:path*",
        destination: `${apiUrl}/api/:path*`,
      },
      {
        source: "/token",
        destination: `${apiUrl}/token`,
      },
    ];
  },
};

export default nextConfig;
