// Hand-drawn SVG charts. They are small, scale to any width, follow the theme, and have a text
// alternative, so no chart library is needed.
import { cn } from "@/lib/cn";
import { formatMetricValue, formatPercent, metricLabel, ordinal } from "@/lib/format";
import type { BreakdownItem, Component } from "@/lib/types";

export interface SeriesPoint {
  week: number;
  rank: number | null;
}

export interface Series {
  id: string;
  label: string;
  color: string; // a CSS color, usually a theme variable
  dashed?: boolean;
  points: SeriesPoint[];
}

const W = 640;
const H = 240;
const M = { top: 16, right: 20, bottom: 30, left: 40 };

/** Round a maximum rank up to a tidy axis end. */
export function niceMax(maxRank: number): number {
  if (maxRank <= 5) return 5;
  if (maxRank <= 10) return 10;
  const step = maxRank <= 30 ? 5 : maxRank <= 80 ? 10 : 25;
  return Math.ceil(maxRank / step) * step;
}

export function rankTicks(max: number): number[] {
  if (max <= 5) return [1, 2, 3, 4, 5].filter((n) => n <= max);
  const step = max <= 10 ? 3 : max <= 30 ? 5 : max <= 80 ? 10 : 25;
  const ticks = [1];
  for (let n = step; n < max; n += step) ticks.push(n);
  ticks.push(max);
  return [...new Set(ticks)];
}

/** A rank-over-time line chart. Rank 1 is at the top, so a rising line means improving. */
export function RankHistoryChart({ series, title }: { series: Series[]; title: string }) {
  const weeks = [...new Set(series.flatMap((s) => s.points.map((p) => p.week)))].sort((a, b) => a - b);
  const ranks = series.flatMap((s) => s.points.map((p) => p.rank).filter((r): r is number => r !== null));
  if (weeks.length === 0 || ranks.length === 0) return null;

  const max = niceMax(Math.max(...ranks));
  const innerW = W - M.left - M.right;
  const innerH = H - M.top - M.bottom;
  const x = (week: number) =>
    weeks.length === 1 ? M.left + innerW / 2 : M.left + ((week - weeks[0]) / (weeks[weeks.length - 1] - weeks[0])) * innerW;
  const y = (rank: number) => M.top + ((rank - 1) / Math.max(1, max - 1)) * innerH;

  // Break the line where a week has no rank instead of drawing across the gap.
  function segments(points: SeriesPoint[]) {
    const out: SeriesPoint[][] = [];
    let current: SeriesPoint[] = [];
    for (const p of points) {
      if (p.rank === null) {
        if (current.length) out.push(current);
        current = [];
      } else current.push(p);
    }
    if (current.length) out.push(current);
    return out;
  }

  const description = series
    .map((s) => {
      const last = [...s.points].reverse().find((p) => p.rank !== null);
      return last ? `${s.label}: rank ${last.rank} in week ${last.week}` : `${s.label}: not ranked`;
    })
    .join(". ");

  return (
    <figure>
      <figcaption className="sr-only">{title}</figcaption>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`${title}. ${description}.`}
        className="h-auto w-full"
      >
        {rankTicks(max).map((tick) => (
          <g key={tick}>
            <line x1={M.left} x2={W - M.right} y1={y(tick)} y2={y(tick)} stroke="var(--line)" strokeWidth="1" />
            <text x={M.left - 8} y={y(tick)} textAnchor="end" dominantBaseline="middle" fontSize="11" fill="var(--muted)">
              {tick}
            </text>
          </g>
        ))}
        {weeks.map((week) => (
          <text key={week} x={x(week)} y={H - 8} textAnchor="middle" fontSize="11" fill="var(--muted)">
            {week}
          </text>
        ))}
        <text x={M.left} y={H - 8} textAnchor="end" fontSize="10" fill="var(--muted)" dx="-18">
          Wk
        </text>
        {series.map((s) => (
          <g key={s.id}>
            {segments(s.points).map((segment, i) => (
              <path
                key={i}
                d={segment.map((p, j) => `${j === 0 ? "M" : "L"}${x(p.week)},${y(p.rank as number)}`).join(" ")}
                fill="none"
                stroke={s.color}
                strokeWidth="2.5"
                strokeLinejoin="round"
                strokeLinecap="round"
                strokeDasharray={s.dashed ? "6 5" : undefined}
              />
            ))}
            {s.points.map(
              (p) =>
                p.rank !== null && (
                  <circle key={p.week} cx={x(p.week)} cy={y(p.rank)} r="4" fill="var(--surface)" stroke={s.color} strokeWidth="2.5">
                    <title>{`${s.label}, week ${p.week}: rank ${p.rank}`}</title>
                  </circle>
                ),
            )}
          </g>
        ))}
      </svg>
      <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-muted">
        {series.map((s) => (
          <span key={s.id} className="inline-flex items-center gap-2">
            <svg width="24" height="8" aria-hidden="true">
              <line x1="0" x2="24" y1="4" y2="4" stroke={s.color} strokeWidth="2.5" strokeDasharray={s.dashed ? "5 4" : undefined} />
            </svg>
            {s.label}
          </span>
        ))}
        <span className="ml-auto">Higher on the chart is a better rank</span>
      </div>
    </figure>
  );
}

const COMPONENT_COLOR: Record<Component, string> = {
  efficiency: "bg-accent",
  production: "bg-teal",
};

/** Horizontal percentile bars: how a player compares with others at the position, metric by metric. */
export function BreakdownBars({ items, component }: { items: BreakdownItem[]; component: Component }) {
  const rows = items
    .filter((item) => item.component === component)
    .sort((a, b) => b.contribution_points - a.contribution_points);
  if (rows.length === 0) return null;
  return (
    <ul className="space-y-3">
      {rows.map((item) => {
        const percent = Math.round(item.percentile * 100);
        return (
          <li key={item.metric}>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="font-medium">{metricLabel(item.metric)}</span>
              <span className="tnum text-muted">
                {formatMetricValue(item.metric, item.value)}
                <span className="mx-1.5 opacity-40" aria-hidden="true">
                  ·
                </span>
                <span className="text-fg">{ordinal(percent)} pct</span>
              </span>
            </div>
            <div
              className="mt-1.5 h-2 w-full rounded-full bg-surface-2"
              role="meter"
              aria-label={`${metricLabel(item.metric)} percentile`}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={percent}
              aria-valuetext={`${formatPercent(item.percentile)} percentile`}
            >
              <div
                className={cn("h-full rounded-full", COMPONENT_COLOR[component])}
                style={{ width: `${Math.max(2, percent)}%` }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
