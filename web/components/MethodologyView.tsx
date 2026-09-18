"use client";

import { useJson } from "@/lib/api";
import { formatPercent, metricLabel } from "@/lib/format";
import { POSITION_NAMES, type BacktestHeadline, type Methodology, type Position } from "@/lib/types";
import { Badge, Card, ErrorState, PageHeader, SectionTitle, Skeleton } from "./ui";

const fmt = (value: number | null) => (value === null ? "n/a" : value.toFixed(3));

/** Plain-language reading of the backtest, built only from the numbers in the file. */
export function backtestVerdict(b: BacktestHeadline): string[] {
  const positions = Object.keys(b.held_out_spearman) as Position[];
  const usable = positions.filter(
    (p) => b.held_out_spearman[p].current !== null && b.held_out_spearman[p].points_per_game_baseline !== null,
  );
  const worse = usable.filter(
    (p) => (b.held_out_spearman[p].current as number) < (b.held_out_spearman[p].points_per_game_baseline as number) - 0.02,
  );
  const lines: string[] = [];
  if (worse.length === usable.length && usable.length > 0) {
    lines.push(
      `The current setting (${formatPercent(b.current_efficiency_weight)} efficiency) ranked next week's fantasy points less accurately than simply ranking by fantasy points per game at every position, on seasons it was not tuned on.`,
    );
  } else if (worse.length > 0) {
    lines.push(
      `The current setting (${formatPercent(b.current_efficiency_weight)} efficiency) ranked next week's fantasy points less accurately than fantasy points per game at ${worse.join(", ")}.`,
    );
  } else {
    lines.push(
      `The current setting (${formatPercent(b.current_efficiency_weight)} efficiency) ranked next week's fantasy points about as well as ranking by fantasy points per game.`,
    );
  }
  if (b.selected_efficiency_weight !== b.current_efficiency_weight) {
    lines.push(
      `The backtest's preferred setting was ${formatPercent(b.selected_efficiency_weight)} efficiency.`,
    );
  }
  return lines;
}

function Backtest({ backtest }: { backtest: BacktestHeadline }) {
  const positions = Object.keys(backtest.held_out_spearman) as Position[];
  return (
    <section aria-label="Backtest">
      <SectionTitle
        title="How well do the rankings predict next week?"
        description={`We tested every week's ranking against the following week's fantasy points. The efficiency weight was chosen on ${backtest.tuning_seasons.join(", ")} and checked on ${backtest.held_out_seasons.join(", ")}, which it had not seen.`}
      />
      <Card className="overflow-x-auto p-0">
        <table className="w-full text-sm">
          <caption className="sr-only">Held-out rank correlation with next week&apos;s fantasy points, by position</caption>
          <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
            <tr>
              <th scope="col" className="px-4 py-3 font-medium">Position</th>
              <th scope="col" className="px-4 py-3 text-right font-medium">Composite, current setting</th>
              <th scope="col" className="px-4 py-3 text-right font-medium">Composite, tested best</th>
              <th scope="col" className="px-4 py-3 text-right font-medium">Fantasy points per game</th>
            </tr>
          </thead>
          <tbody className="tnum">
            {positions.map((p) => {
              const row = backtest.held_out_spearman[p];
              return (
                <tr key={p} className="border-b border-line/70 last:border-0">
                  <th scope="row" className="px-4 py-3 text-left font-medium">{p}</th>
                  <td className="px-4 py-3 text-right">{fmt(row.current)}</td>
                  <td className="px-4 py-3 text-right">{fmt(row.selected)}</td>
                  <td className="px-4 py-3 text-right">{fmt(row.points_per_game_baseline)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>
      <div className="mt-4 space-y-2 text-sm text-muted">
        <p>
          Numbers are the rank correlation (Spearman) between a player&apos;s ranking and their next-week
          fantasy points. 0 means no relationship and 1 would be perfect. Single-game results are noisy,
          so modest values are normal.
        </p>
        {backtestVerdict(backtest).map((line) => (
          <p key={line} className="font-medium text-fg">
            {line}
          </p>
        ))}
      </div>
    </section>
  );
}

function MetricList({ items }: { items: Methodology["positions"][number]["metrics"] }) {
  return (
    <ul className="mt-1 space-y-0.5 text-sm text-muted">
      {items.map((m) => (
        <li key={m.metric}>
          {metricLabel(m.metric)}
          {m.direction === "lower" && <span className="text-xs"> (lower is better)</span>}
        </li>
      ))}
    </ul>
  );
}

function PositionCard({ position }: { position: Methodology["positions"][number] }) {
  const efficiency = position.metrics.filter((m) => m.component === "efficiency");
  const production = position.metrics.filter((m) => m.component === "production");
  return (
    <Card as="article" className="p-5">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="font-semibold">{POSITION_NAMES[position.position]}</h3>
        <Badge>
          {formatPercent(position.efficiency_weight)} / {formatPercent(position.production_weight)}
        </Badge>
      </div>
      <p className="mt-3 text-xs font-medium uppercase tracking-wide text-muted">Efficiency</p>
      <MetricList items={efficiency} />
      <p className="mt-3 text-xs font-medium uppercase tracking-wide text-muted">Production</p>
      <MetricList items={production} />
      <p className="mt-4 border-t border-line pt-3 text-xs text-muted">
        Ranked once they reach {position.min_role_per_week}{" "}
        {position.position === "QB"
          ? "pass attempts"
          : position.position === "RB"
            ? "carries plus targets"
            : position.position === "K"
              ? "kicks (field goals plus extra points)"
              : "targets"}{" "}
        per game their team has played.
      </p>
    </Card>
  );
}

export function MethodologyView() {
  const { data, error, loading } = useJson<Methodology>("methodology.json");
  return (
    <div className="rise space-y-12">
      <PageHeader
        title="Methodology"
        subtitle="How the composite score and the fantasy ranking are built, and how well they work."
      />

      <section aria-label="Overview" className="grid gap-4 md:grid-cols-2">
        <Card className="p-6">
          <h2 className="font-semibold">Composite score</h2>
          <p className="mt-2 text-sm text-muted">
            Every player is measured on several statistics. Each one becomes a <strong className="text-fg">percentile</strong>{" "}
            among ranked players at the same position that week, so a 90 means better than 90% of them.
            The percentiles are averaged into two scores from 0 to 100, then blended:
          </p>
          <ul className="mt-3 space-y-1.5 text-sm text-muted">
            <li>
              <strong className="text-fg">Efficiency</strong>: rates per opportunity, such as EPA per dropback
              or yards per target.
            </li>
            <li>
              <strong className="text-fg">Production</strong>: totals and shares, such as yards, touchdowns,
              and target share.
            </li>
          </ul>
        </Card>
        <Card className="p-6">
          <h2 className="font-semibold">Fantasy points</h2>
          <p className="mt-2 text-sm text-muted">
            The second ranking is simply season-to-date PPR fantasy points (one point per reception). The
            data source does not score kickers, so we use common standard scoring for them.
          </p>
          {data && <p className="mt-3 text-sm text-muted">{data.kicker_scoring}</p>}
        </Card>
      </section>

      {error && <ErrorState message={error.message} />}
      {loading && <Skeleton className="h-64 w-full" />}
      {data && (
        <>
          <section aria-label="Settings by position">
            <SectionTitle
              title="What counts at each position"
              description="The exact settings currently in use. The badge shows the efficiency / production blend."
            />
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {data.positions.map((p) => (
                <PositionCard key={p.position} position={p} />
              ))}
            </div>
          </section>

          {data.backtest ? (
            <Backtest backtest={data.backtest} />
          ) : (
            <p className="text-sm text-muted">The backtest hasn&apos;t been run yet.</p>
          )}
        </>
      )}

      <section aria-label="Limitations">
        <SectionTitle title="Things to keep in mind" />
        <ul className="list-disc space-y-2 pl-5 text-sm text-muted">
          <li>
            <strong className="text-fg">Early-season rankings are noisy.</strong> In the first few weeks
            every player has only a handful of plays behind them.
          </li>
          <li>
            <strong className="text-fg">Only players with enough volume are ranked.</strong> The minimum
            grows with each game the team plays, so a few good plays never rank a player high late in the
            season. Everyone else is listed separately.
          </li>
          <li>
            <strong className="text-fg">Rankings only use games already played.</strong> Each week&apos;s
            ranking uses data through that week and nothing later.
          </li>
          <li>
            <strong className="text-fg">These are statistical rankings, not predictions or betting advice.</strong>
          </li>
        </ul>
      </section>
    </div>
  );
}
