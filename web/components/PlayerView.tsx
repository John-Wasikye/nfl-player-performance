"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useJson } from "@/lib/api";
import { formatPoints, formatScore, ordinal } from "@/lib/format";
import { POSITION_NAMES, type PlayerFile } from "@/lib/types";
import { BreakdownBars, RankHistoryChart } from "./charts";
import { ChevronRightIcon } from "./icons";
import { Avatar, Card, EmptyState, ErrorState, MovementChip, SectionTitle, Skeleton } from "./ui";

function Stat({
  label,
  value,
  detail,
}: {
  label: string;
  value: React.ReactNode;
  detail?: React.ReactNode;
}) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-3xl font-semibold tracking-tight tnum">{value}</p>
      {detail && <div className="mt-1 text-sm text-muted">{detail}</div>}
    </div>
  );
}

function PlayerSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading player">
      <div className="flex items-center gap-4">
        <Skeleton className="h-16 w-16 rounded-full" />
        <div className="space-y-2">
          <Skeleton className="h-7 w-56" />
          <Skeleton className="h-4 w-32" />
        </div>
      </div>
      <Skeleton className="h-40 w-full" />
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

export function PlayerView() {
  const id = useSearchParams().get("id");
  const { data: player, error, loading } = useJson<PlayerFile>(id ? `players/${encodeURIComponent(id)}.json` : null);

  if (!id) {
    return (
      <EmptyState
        title="No player selected"
        message="Pick a player from the rankings, or press / to search."
      />
    );
  }
  if (error) {
    return (
      <ErrorState
        title={error.kind === "not-found" ? "Couldn't find that player" : "Couldn't load the player"}
        message={
          error.kind === "not-found"
            ? "They may not be ranked this season. Try searching for another player."
            : error.message
        }
      />
    );
  }
  if (loading || !player) return <PlayerSkeleton />;

  const history = player.history;
  const latest = history[history.length - 1];
  const previous = history.length > 1 ? history[history.length - 2] : null;
  const compositeMove =
    latest.composite_rank !== null && previous?.composite_rank != null
      ? previous.composite_rank - latest.composite_rank
      : null;
  const fantasyMove = previous ? previous.fantasy_rank - latest.fantasy_rank : null;

  return (
    <div className="rise space-y-8">
      <nav aria-label="Breadcrumb" className="flex items-center gap-1 text-sm text-muted">
        <Link href="/rankings/QB/" className="hover:text-fg">
          Rankings
        </Link>
        <ChevronRightIcon width={14} height={14} />
        <Link href={`/rankings/${player.position}/`} className="hover:text-fg">
          {POSITION_NAMES[player.position]}
        </Link>
      </nav>

      <header className="flex flex-wrap items-center gap-4">
        <Avatar name={player.name} team={player.team} size={64} />
        <div>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{player.name}</h1>
          <p className="mt-1 text-muted">
            {player.position} · {player.team} · {player.season} season, through week {player.latest_week}
          </p>
        </div>
      </header>

      <Card className="grid grid-cols-2 gap-6 p-5 sm:grid-cols-4 sm:p-6">
        <Stat
          label="Composite rank"
          value={latest.composite_rank ? `#${latest.composite_rank}` : "—"}
          detail={
            latest.composite_rank ? (
              <span className="inline-flex items-center gap-2">
                Score {formatScore(latest.composite_score)} <MovementChip movement={compositeMove} />
              </span>
            ) : (
              "Not ranked yet"
            )
          }
        />
        <Stat
          label="Fantasy rank"
          value={`#${latest.fantasy_rank}`}
          detail={
            <span className="inline-flex items-center gap-2">
              {formatPoints(latest.ppr_points)} pts <MovementChip movement={fantasyMove} />
            </span>
          }
        />
        <Stat label="Efficiency" value={formatScore(latest.efficiency_score)} detail="Per-play performance" />
        <Stat label="Production" value={formatScore(latest.production_score)} detail="Volume and output" />
      </Card>

      {!latest.qualified && (
        <div className="rounded-2xl border border-line bg-warn-soft px-5 py-4 text-sm text-warn">
          {player.name} isn&apos;t ranked in the composite yet: not enough{" "}
          {player.position === "QB"
            ? "pass attempts"
            : player.position === "K"
              ? "kicks"
              : player.position === "RB"
                ? "carries and targets"
                : "targets"}{" "}
          so far for the games {player.team} has played. Fantasy points are still ranked.
        </div>
      )}

      <section aria-label="Rank history">
        <SectionTitle
          title="Rank by week"
          description="Season-to-date rank after each week. The composite line has gaps where the player wasn't ranked."
        />
        <Card className="p-4 sm:p-6">
          <RankHistoryChart
            title={`${player.name}: rank by week`}
            series={[
              {
                id: "composite",
                label: "Composite rank",
                color: "var(--accent)",
                points: history.map((h) => ({ week: h.week, rank: h.composite_rank })),
              },
              {
                id: "fantasy",
                label: "Fantasy rank",
                color: "var(--series-2)",
                dashed: true,
                points: history.map((h) => ({ week: h.week, rank: h.fantasy_rank })),
              },
            ]}
          />
          <details className="mt-4 text-sm">
            <summary className="cursor-pointer text-muted hover:text-fg">View as a table</summary>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">{player.name} weekly ranks</caption>
                <thead className="text-xs uppercase tracking-wide text-muted">
                  <tr>
                    <th scope="col" className="py-2 pr-4 font-medium">Week</th>
                    <th scope="col" className="py-2 pr-4 font-medium">Composite rank</th>
                    <th scope="col" className="py-2 pr-4 font-medium">Score</th>
                    <th scope="col" className="py-2 pr-4 font-medium">Fantasy rank</th>
                    <th scope="col" className="py-2 pr-4 font-medium">PPR pts</th>
                    <th scope="col" className="py-2 font-medium">Games</th>
                  </tr>
                </thead>
                <tbody className="tnum">
                  {[...history].reverse().map((h) => (
                    <tr key={h.week} className="border-t border-line/70">
                      <td className="py-2 pr-4">{h.week}</td>
                      <td className="py-2 pr-4">{h.composite_rank ?? "—"}</td>
                      <td className="py-2 pr-4">{formatScore(h.composite_score)}</td>
                      <td className="py-2 pr-4">{h.fantasy_rank}</td>
                      <td className="py-2 pr-4">{formatPoints(h.ppr_points)}</td>
                      <td className="py-2">{h.games}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </Card>
      </section>

      {player.breakdown.length > 0 && (
        <section aria-label="Score breakdown">
          <SectionTitle
            title="Why this rank"
            description={`How ${player.name} compares with other ranked ${POSITION_NAMES[player.position].toLowerCase()} on each measure. A ${ordinal(90)} percentile means better than 90% of them.`}
          />
          <div className="grid gap-4 lg:grid-cols-2">
            <Card className="p-5 sm:p-6">
              <h3 className="mb-1 font-semibold">Efficiency</h3>
              <p className="mb-4 text-sm text-muted">How well he performs per opportunity.</p>
              <BreakdownBars items={player.breakdown} component="efficiency" />
            </Card>
            <Card className="p-5 sm:p-6">
              <h3 className="mb-1 font-semibold">Production</h3>
              <p className="mb-4 text-sm text-muted">How much he has done so far this season.</p>
              <BreakdownBars items={player.breakdown} component="production" />
            </Card>
          </div>
        </section>
      )}
    </div>
  );
}
