// Hand-drawn SVG charts. They are small, scale to any width, follow the theme, and have a text
// alternative, so no chart library is needed.
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import { formatMetricValue, formatPercent, metricLabel, ordinal } from "@/lib/format";
import type { BreakdownItem, Component, GradedWeek } from "@/lib/types";

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

export interface ValuePoint {
  week: number;
  value: number | null;
}

export interface ValueSeries {
  id: string;
  label: string;
  color: string;
  dashed?: boolean;
  /** Dots rather than dashes, so two comparison lines differ by more than colour. */
  dotted?: boolean;
  points: ValuePoint[];
}

/**
 * Share of projections within 5 points of the real score each week, for the model, the best simple
 * average and, once it exists, the frozen model, all on the same players. A week graded before a
 * figure existed is left as a gap.
 */
export function withinSeries(weeks: GradedWeek[]): ValueSeries[] {
  const series: ValueSeries[] = [
    {
      id: "model",
      label: "Model",
      color: "var(--accent)",
      points: weeks.map((w) => ({ week: w.week, value: w.within_5_points ?? null })),
    },
    {
      id: "baseline",
      label: "Best simple average",
      color: "var(--muted)",
      dashed: true,
      points: weeks.map((w) => {
        const values = Object.values(w.baseline_within_5_points ?? {});
        return { week: w.week, value: values.length ? Math.max(...values) : null };
      }),
    },
  ];
  // The model fixed before the season. It started partway through, so earlier weeks are gaps.
  if (weeks.some((w) => w.frozen_within_5_points != null)) {
    series.push({
      id: "frozen",
      label: "Frozen model",
      color: "var(--teal)",
      dotted: true,
      points: weeks.map((w) => ({ week: w.week, value: w.frozen_within_5_points ?? null })),
    });
  }
  return series;
}

const PERCENT_TICKS = [0, 0.2, 0.4, 0.6, 0.8, 1];
// Drawn at its on-screen width rather than scaled, so the axis labels stay readable on a phone.
const AW = 640;
const MIN_AW = 280;
const AH = 270;
const AM = { top: 16, right: 20, bottom: 46, left: 64 };

function valueSegments(points: ValuePoint[]) {
  const out: ValuePoint[][] = [];
  let current: ValuePoint[] = [];
  for (const p of points) {
    if (p.value === null) {
      if (current.length) out.push(current);
      current = [];
    } else current.push(p);
  }
  if (current.length) out.push(current);
  return out;
}

/** Projections within 5 points by week, on a fixed 0% to 100% scale. Higher is better. */
export function AccuracyHistoryChart({ series, title }: { series: ValueSeries[]; title: string }) {
  const ref = useRef<HTMLElement>(null);
  const [width, setWidth] = useState(AW);
  useEffect(() => {
    const element = ref.current;
    if (!element || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) =>
      setWidth(Math.max(MIN_AW, Math.round(entry.contentRect.width))),
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const weeks = [...new Set(series.flatMap((s) => s.points.map((p) => p.week)))].sort((a, b) => a - b);
  const hasValue = series.some((s) => s.points.some((p) => p.value !== null));
  if (weeks.length === 0 || !hasValue) return null;

  const innerW = width - AM.left - AM.right;
  const innerH = AH - AM.top - AM.bottom;
  const x = (week: number) =>
    weeks.length === 1 ? AM.left + innerW / 2 : AM.left + ((week - weeks[0]) / (weeks[weeks.length - 1] - weeks[0])) * innerW;
  const y = (share: number) => AM.top + (1 - share) * innerH;
  // On a narrow screen a full season of week numbers would overlap, so label every other one.
  const labelEvery = Math.max(1, Math.ceil(24 / (innerW / Math.max(1, weeks.length - 1))));
  const last = weeks.length - 1;
  const labelled = weeks.filter((_, i) => i === last || (i % labelEvery === 0 && last - i >= labelEvery));

  const description = series
    .map((s) => {
      const last = [...s.points].reverse().find((p) => p.value !== null);
      return last ? `${s.label}: ${formatPercent(last.value!)} within 5 points in week ${last.week}` : `${s.label}: not graded`;
    })
    .join(". ");

  return (
    <figure ref={ref}>
      <figcaption className="sr-only">{title}</figcaption>
      <svg viewBox={`0 0 ${width} ${AH}`} role="img" aria-label={`${title}. ${description}.`} className="h-auto w-full">
        {PERCENT_TICKS.map((tick) => (
          <g key={tick}>
            <line x1={AM.left} x2={width - AM.right} y1={y(tick)} y2={y(tick)} stroke="var(--line)" strokeWidth="1" />
            <text x={AM.left - 8} y={y(tick)} textAnchor="end" dominantBaseline="middle" fontSize="12" fill="var(--muted)">
              {formatPercent(tick)}
            </text>
          </g>
        ))}
        {labelled.map((week) => (
          <text key={week} x={x(week)} y={AM.top + innerH + 18} textAnchor="middle" fontSize="12" fill="var(--muted)">
            {week}
          </text>
        ))}
        <text x={AM.left + innerW / 2} y={AH - 6} textAnchor="middle" fontSize="12" fontWeight="600" fill="var(--fg)">
          Week
        </text>
        <text
          transform={`translate(14 ${AM.top + innerH / 2}) rotate(-90)`}
          textAnchor="middle"
          fontSize="12"
          fontWeight="600"
          fill="var(--fg)"
        >
          Projections within 5 points
        </text>
        {series.map((s) => (
          <g key={s.id}>
            {valueSegments(s.points).map((segment, i) => (
              <path
                key={i}
                data-series={s.id}
                d={segment.map((p, j) => `${j === 0 ? "M" : "L"}${x(p.week)},${y(p.value as number)}`).join(" ")}
                fill="none"
                stroke={s.color}
                strokeWidth="2.5"
                strokeLinejoin="round"
                strokeLinecap="round"
                strokeDasharray={s.dotted ? "1 5" : s.dashed ? "6 5" : undefined}
              />
            ))}
            {s.points.map(
              (p) =>
                p.value !== null && (
                  <circle key={p.week} cx={x(p.week)} cy={y(p.value)} r="4" fill="var(--surface)" stroke={s.color} strokeWidth="2.5">
                    <title>{`${s.label}, week ${p.week}: ${formatPercent(p.value)} within 5 points`}</title>
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
              <line x1="0" x2="24" y1="4" y2="4" stroke={s.color} strokeWidth="2.5" strokeDasharray={s.dotted ? "1 4" : s.dashed ? "5 4" : undefined} strokeLinecap={s.dotted ? "round" : undefined} />
            </svg>
            {s.label}
          </span>
        ))}
        <span className="ml-auto">Higher is better</span>
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
