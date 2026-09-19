import type { NextConfig } from "next";

// A fully static site: every page is pre-built HTML, and the rankings data is fetched in the
// browser from the published JSON files, so the daily data refresh never needs a site rebuild.
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  // Set by the e2e suite so its build doesn't collide with `next dev`. With `output: "export"` this also
  // moves the exported site.
  ...(process.env.NEXT_DIST_DIR ? { distDir: process.env.NEXT_DIST_DIR } : {}),
};

export default nextConfig;
