import { fileURLToPath } from "node:url"
import type { NextConfig } from "next"
import { loadEnvConfig } from "@next/env"

// Load environment variables from the root directory
loadEnvConfig(process.cwd())

const monorepoRoot = fileURLToPath(new URL("../../", import.meta.url))

const r2Endpoints: string[] = (() => {
  try {
    const parsed = JSON.parse(process.env.R2_API_ENDPOINT ?? "[]")
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
})()

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: monorepoRoot,
  transpilePackages: ["@workspace/ui"],
  images: {
    remotePatterns: r2Endpoints.map((hostname) => ({
      protocol: "https",
      hostname,
      port: "",
      pathname: "**",
    })),
  },
}

export default nextConfig
