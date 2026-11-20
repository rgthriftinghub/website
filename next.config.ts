import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emits a minimal self-contained server bundle for the Docker runtime stage.
  output: "standalone"
};

export default nextConfig;
