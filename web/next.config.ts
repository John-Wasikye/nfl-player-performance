import type { NextConfig } from "next";

// A fully static site: every page is pre-built HTML, and the rankings data is fetched in the
// browser from the published JSON files, so the daily data refresh never needs a site rebuild.
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  // Normally left alone. The end-to-end suite sets NEXT_DIST_DIR so its build goes somewhere of
  // its own: `next dev` and `next build` otherwise share `.next`, and a build started while a dev
  // server is running makes them fight over the same files. With `output: "export"` this moves the
  // exported site as well as the build cache, which is why the suite serves from that same folder.
  ...(process.env.NEXT_DIST_DIR ? { distDir: process.env.NEXT_DIST_DIR } : {}),
};

export default nextConfig;
