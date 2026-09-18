import { describe, expect, it } from "vitest";
import {
  formatMetricValue,
  formatPercent,
  formatPoints,
  formatScore,
  formatSigned,
  initials,
  isStale,
  metricLabel,
  ordinal,
  timeAgo,
} from "@/lib/format";

describe("formatting numbers", () => {
  it("shows scores and points with one decimal and a dash when missing", () => {
    expect(formatScore(80.44)).toBe("80.4");
    expect(formatScore(null)).toBe("—");
    expect(formatPoints(76.5)).toBe("76.5");
    expect(formatPoints(undefined)).toBe("—");
  });

  it("signs positive numbers", () => {
    expect(formatSigned(3)).toBe("+3");
    expect(formatSigned(-2)).toBe("-2");
    expect(formatSigned(0)).toBe("0");
  });

  it("formats fractions as percentages", () => {
    expect(formatPercent(0.923)).toBe("92%");
    expect(formatPercent(0.5, 1)).toBe("50.0%");
  });

  it("writes ordinals, including the teens", () => {
    expect(ordinal(1)).toBe("1st");
    expect(ordinal(2)).toBe("2nd");
    expect(ordinal(3)).toBe("3rd");
    expect(ordinal(4)).toBe("4th");
    expect(ordinal(11)).toBe("11th");
    expect(ordinal(12)).toBe("12th");
    expect(ordinal(13)).toBe("13th");
    expect(ordinal(21)).toBe("21st");
    expect(ordinal(22)).toBe("22nd");
    expect(ordinal(100)).toBe("100th");
    expect(ordinal(0)).toBe("0th");
  });
});

describe("time", () => {
  const now = new Date("2026-09-18T20:00:00Z");

  it("describes how long ago something was", () => {
    expect(timeAgo("2026-09-18T19:59:30Z", now)).toBe("just now");
    expect(timeAgo("2026-09-18T19:15:00Z", now)).toBe("45 minutes ago");
    expect(timeAgo("2026-09-18T19:00:00Z", now)).toBe("1 hour ago");
    expect(timeAgo("2026-09-18T15:00:00Z", now)).toBe("5 hours ago");
    expect(timeAgo("2026-09-15T20:00:00Z", now)).toBe("3 days ago");
  });

  it("does not crash on a bad timestamp", () => {
    expect(timeAgo("not a date", now)).toBe("unknown");
  });

  it("flags data older than 36 hours as stale", () => {
    expect(isStale("2026-09-17T09:00:00Z", now)).toBe(false); // 35 hours
    expect(isStale("2026-09-17T07:00:00Z", now)).toBe(true); // 37 hours
    expect(isStale("garbage", now)).toBe(true);
  });
});

describe("names and labels", () => {
  it("builds initials from first and last name, ignoring suffixes", () => {
    expect(initials("Josh Allen")).toBe("JA");
    expect(initials("Patrick Mahomes II")).toBe("PM");
    expect(initials("Kenneth Walker III")).toBe("KW");
    expect(initials("Amon-Ra St. Brown")).toBe("AB");
    expect(initials("Cher")).toBe("CH");
    expect(initials("")).toBe("?");
  });

  it("turns metric ids into readable labels", () => {
    expect(metricLabel("epa_per_dropback")).toBe("EPA per dropback");
    expect(metricLabel("cpoe")).toBe("CPOE");
    expect(metricLabel("sack_rate")).toBe("Sack rate");
    expect(metricLabel("receiving_tds")).toBe("Receiving TDs");
    expect(metricLabel("fg_pct_40_plus")).toBe("FG % from 40+ yards");
    expect(metricLabel("wopr_avg")).toBe("WOPR (per-game average)");
  });

  it("formats rates as percentages and totals as numbers", () => {
    expect(formatMetricValue("catch_rate", 0.7123)).toBe("71.2%");
    expect(formatMetricValue("target_share_avg", 0.253)).toBe("25.3%");
    expect(formatMetricValue("fg_pct", 1)).toBe("100.0%");
    expect(formatMetricValue("passing_yards", 582)).toBe("582");
    expect(formatMetricValue("epa_per_dropback", 0.4621)).toBe("0.462");
    expect(formatMetricValue("passing_epa", 29.61)).toBe("29.6");
  });
});
