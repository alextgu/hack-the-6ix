import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  // Silence multi-lockfile warning; keep resolution rooted on this app.
  // Shared CSS is imported via ../design-system from landing/.
  turbopack: {
    root: path.join(__dirname),
  },
};

export default nextConfig;
