import type { NextConfig } from "next";

const publicApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
if (!publicApiBaseUrl) {
  throw new Error("NEXT_PUBLIC_API_BASE_URL must be set when building the frontend.");
}

const nextConfig: NextConfig = {
  // Emits a minimal self-contained server bundle for the Docker runtime stage.
  output: "standalone",
  env: { NEXT_PUBLIC_API_BASE_URL: publicApiBaseUrl },
};

export default nextConfig;
