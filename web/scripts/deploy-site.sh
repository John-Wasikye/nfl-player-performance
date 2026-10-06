#!/usr/bin/env bash
# Uploads the built site (web/out) to the site bucket and refreshes CloudFront.
#
#   AWS_PROFILE=nfl_player_stats bash scripts/deploy-site.sh
#
# Never touches data/v1/: the daily pipeline owns that prefix, and --delete would otherwise remove it.
# Run `npm run build` first.
set -euo pipefail

BUCKET="${SITE_BUCKET:-jw-nfl-player-stats-site}"
DISTRIBUTION="${SITE_DISTRIBUTION_ID:-E1OZ5WDKRFMJ25}"
OUT="$(cd "$(dirname "$0")/.." && pwd)/out"

[ -f "$OUT/index.html" ] || { echo "no build in $OUT; run npm run build first" >&2; exit 1; }

# Hashed assets never change under the same name, so they cache for a year.
aws s3 sync "$OUT/_next/static" "s3://$BUCKET/_next/static" \
  --cache-control "public, max-age=31536000, immutable" --no-progress

# Everything else is re-checked after five minutes.
aws s3 sync "$OUT" "s3://$BUCKET" --delete \
  --exclude "data/*" --exclude "_next/static/*" \
  --cache-control "public, max-age=300" --no-progress

aws cloudfront create-invalidation --distribution-id "$DISTRIBUTION" --paths "/*" \
  --query "Invalidation.Id" --output text
