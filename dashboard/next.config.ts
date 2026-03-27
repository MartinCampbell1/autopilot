import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  outputFileTracingRoot: path.join(process.cwd(), ".."),
};

export default nextConfig;
