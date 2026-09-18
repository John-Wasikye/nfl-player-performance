import type { NextConfig } from "next";

// A fully static site: every page is pre-built HTML, and the rankings data is fetched in the
// browser from the published JSON files, so the daily data refresh never needs a site rebuild.
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
