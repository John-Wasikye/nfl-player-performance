// Small, pure formatting helpers. Kept free of React so they are easy to test.

const DASH = "—";

/** A 0-100 score with one decimal, or a dash when the player has none. */
export function formatScore(score: number | null | undefined): string {
  return score == null ? DASH : score.toFixed(1);
}

/** Fantasy points with one decimal. */
export function formatPoints(points: number | null | undefined): string {
  return points == null ? DASH : points.toFixed(1);
}

/** "+3", "-2", or "0" (a plain hyphen-minus keeps it copy-paste friendly). */
export function formatSigned(value: number): string {
  if (value > 0) return `+${value}`;
  return String(value);
}

/** A 0-1 fraction as a percentage, e.g. 0.923 -> "92%". */
export function formatPercent(fraction: number, digits = 0): string {
  return `${(fraction * 100).toFixed(digits)}%`;
}

/** "1st", "2nd", "3rd", "11th"... */
export function ordinal(n: number): string {
  const rem100 = n % 100;
  if (rem100 >= 11 && rem100 <= 13) return `${n}th`;
  switch (n % 10) {
    case 1:
      return `${n}st`;
    case 2:
      return `${n}nd`;
    case 3:
      return `${n}rd`;
    default:
      return `${n}th`;
  }
}

/** How long ago an ISO timestamp was, in plain words: "just now", "3 hours ago", "2 days ago". */
export function timeAgo(iso: string, now: Date = new Date()): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "unknown";
  const seconds = Math.max(0, Math.round((now.getTime() - then) / 1000));
  if (seconds < 90) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} minutes ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 36) return hours === 1 ? "1 hour ago" : `${hours} hours ago`;
  const days = Math.round(hours / 24);
  return `${days} days ago`;
}

/** True when the published data is older than the threshold (default 36 hours). */
export function isStale(iso: string, now: Date = new Date(), maxHours = 36): boolean {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return true;
  return now.getTime() - then > maxHours * 3600 * 1000;
}

/** Initials for an avatar: "Patrick Mahomes II" -> "PM", "Amon-Ra St. Brown" -> "AS". */
export function initials(name: string): string {
  const suffixes = new Set(["jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v"]);
  const parts = name
    .split(/\s+/)
    .filter((part) => part && !suffixes.has(part.toLowerCase()));
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/** "epa_per_dropback" -> "EPA per dropback", with known acronyms kept in capitals. */
const ACRONYMS: Record<string, string> = {
  epa: "EPA",
  cpoe: "CPOE",
  racr: "RACR",
  wopr: "WOPR",
  tds: "TDs",
  td: "TD",
  fg: "FG",
  pat: "PAT",
  int: "INT",
  ppr: "PPR",
  avg: "average",
};

const LABEL_OVERRIDES: Record<string, string> = {
  fg_pct: "FG %",
  fg_pct_40_plus: "FG % from 40+ yards",
  pat_pct: "PAT %",
  fg_made: "FG made",
  fg_made_50_plus: "FG made from 50+ yards",
  kicker_points: "Kicker points",
  target_share_avg: "Target share (per-game average)",
  air_yards_share_avg: "Air yards share (per-game average)",
  wopr_avg: "WOPR (per-game average)",
  total_tds: "Total TDs",
  first_downs: "First downs",
};

export function metricLabel(metric: string): string {
  if (LABEL_OVERRIDES[metric]) return LABEL_OVERRIDES[metric];
  const words = metric.split("_").map((word) => ACRONYMS[word] ?? word);
  const text = words.join(" ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** A metric value formatted for display: rates and shares get more precision than totals. */
export function formatMetricValue(metric: string, value: number): string {
  if (/(_pct|rate|share|catch_rate)/.test(metric) || metric === "fg_pct_40_plus") {
    return `${(value * 100).toFixed(1)}%`;
  }
  if (Number.isInteger(value)) return String(value);
  if (Math.abs(value) < 1) return value.toFixed(3);
  return value.toFixed(1);
}
