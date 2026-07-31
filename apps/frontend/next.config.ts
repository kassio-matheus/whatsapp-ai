import { fileURLToPath } from "node:url"
import type { NextConfig } from "next"

const monorepoRoot = fileURLToPath(new URL("../../", import.meta.url))

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: monorepoRoot,
  transpilePackages: ["@workspace/ui"],
}

export default nextConfig
