"use client";

import Link from "next/link";
import { useState } from "react";
import { useJson } from "@/lib/api";
import { formatScore, timeAgo } from "@/lib/format";
import {
  POSITIONS,
  POSITION_NAMES,
  type Meta,
  type MoversFile,
  type Mover,
  type Position,
  type PredictionsFile,
  type PredictionsIndex,
  type RankingsFile,
} from "@/lib/types";
import { cn } from "@/lib/cn";
import { ChevronRightIcon } from "./icons";
import { useMeta } from "./MetaContext";
import { Avatar, Badge, Card, EmptyState, ErrorState, MovementChip, SectionTitle, Skeleton } from "./ui";

function StatusPills({ meta }: { meta: Meta }) {
  return (
    <div className="mt-5 flex flex-wrap items-center gap-2">
      <Badge tone="accent">
        {meta.season} season · Week {meta.latest_week}
        {meta.week_complete ? "" : " in progress"}
      </Badge>
      <span className="text-sm text-muted" suppressHydrationWarning>
        Updated {timeAgo(meta.generated_at)}
      </span>
    </div>
  );
}

function MoverRow({ mover, position }: { mover: Mover; position: Position }) {
  return (
    <li>
      <Link
        href={`/player/?id=${encodeURIComponent(mover.player_id)}`}
        className="flex items-center gap-3 rounded-xl px-2 py-2 hover:bg-surface-2"
      >
        <Avatar name={mover.name} team={mover.team} size={32} />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium">{mover.name}</span>
          <span className="text-xs text-muted">
            {position} · {mover.team} · #{mover.rank_prev} to #{mover.rank}
          </span>
        </span>
        <MovementChip movement={mover.movement} />
      </Link>
    </li>
  );
}

function Movers({ meta }: { meta: Meta }) {
  const [position, setPosition] = useState<Position>("QB");
  const { data, error, loading } = useJson<MoversFile>(`movers/${meta.season}/${meta.latest_week}.json`);
  const risers = data?.risers[position] ?? [];
  const fallers = data?.fallers[position] ?? [];

  return (
    <section aria-label="Biggest movers">
      <SectionTitle
        title="Biggest movers"
        description={`Composite rank changes since week ${Math.max(1, meta.latest_week - 1)}.`}
        action={
          <div role="tablist" aria-label="Position" className="flex gap-1">
            {POSITIONS.map((p) => (
              <button
                key={p}
                role="tab"
                type="button"
                aria-selected={p === position}
                onClick={() => setPosition(p)}
                className={cn(
                  "rounded-full px-3 py-1 text-sm font-medium",
                  p === position ? "bg-fg text-bg" : "bg-surface-2 text-muted hover:text-fg",
                )}
              >
                {p}
              </button>
            ))}
          </div>
        }
      />
      {error && <ErrorState message={error.message} />}
      {loading && <Skeleton className="h-48 w-full" />}
      {data && (
        <div className="grid gap-4 md:grid-cols-2">
          <Card className="p-4">
            <h3 className="mb-2 px-2 text-sm font-semibold text-up">Risers</h3>
            {risers.length ? (
              <ul>{risers.map((m) => <MoverRow key={m.player_id} mover={m} position={position} />)}</ul>
            ) : (
              <p className="px-2 py-6 text-sm text-muted">Nobody has moved up yet this week.</p>
            )}
          </Card>
          <Card className="p-4">
            <h3 className="mb-2 px-2 text-sm font-semibold text-down">Fallers</h3>
            {fallers.length ? (
              <ul>{fallers.map((m) => <MoverRow key={m.player_id} mover={m} position={position} />)}</ul>
            ) : (
              <p className="px-2 py-6 text-sm text-muted">Nobody has moved down yet this week.</p>
            )}
          </Card>
        </div>
      )}
    </section>
  );
}

function TopFive({ meta, position }: { meta: Meta; position: Position }) {
  const { data, error, loading } = useJson<RankingsFile>(
    `rankings/${meta.season}/${meta.latest_week}/${position}.json`,
  );
  const top = (data?.players ?? []).filter((p) => p.composite.rank !== null).slice(0, 5);
  return (
    <Card as="article" className="flex flex-col p-4">
      <div className="mb-2 flex items-center justify-between px-2">
        <h3 className="font-semibold">{POSITION_NAMES[position]}</h3>
        <Link
          href={`/rankings/${position}/`}
          className="inline-flex items-center gap-0.5 text-sm text-accent hover:underline"
          aria-label={`See all ${POSITION_NAMES[position].toLowerCase()}`}
        >
          All <ChevronRightIcon width={14} height={14} />
        </Link>
      </div>
      {error && <p className="px-2 py-6 text-sm text-muted">Couldn&apos;t load this list.</p>}
      {loading && <Skeleton className="h-40 w-full" />}
      {data && top.length === 0 && <p className="px-2 py-6 text-sm text-muted">No one is ranked yet.</p>}
      <ol>
        {top.map((p) => (
          <li key={p.player_id}>
            <Link
              href={`/player/?id=${encodeURIComponent(p.player_id)}`}
              className="flex items-center gap-3 rounded-xl px-2 py-2 hover:bg-surface-2"
            >
              <span className="w-5 text-sm font-semibold text-muted tnum">{p.composite.rank}</span>
              <Avatar name={p.name} team={p.team} size={32} />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium">{p.name}</span>
                <span className="text-xs text-muted">{p.team}</span>
              </span>
              <span className="text-sm font-semibold tnum">{formatScore(p.composite.score)}</span>
            </Link>
          </li>
        ))}
      </ol>
    </Card>
  );
}


function TopProjected({ index, position }: { index: PredictionsIndex; position: Position }) {
  const { data, error, loading } = useJson<PredictionsFile>(
    `predictions/${index.season}/${index.week}/${position}.json`,
  );
  const top = (data?.players ?? []).slice(0, 5);
  return (
    <Card as="article" className="p-4">
      <div className="mb-2 flex items-center justify-between px-2">
        <h3 className="font-semibold">{POSITION_NAMES[position]}</h3>
        <Link
          href={`/predictions/${position}/`}
          className="inline-flex items-center gap-0.5 text-sm text-accent hover:underline"
          aria-label={`See all ${POSITION_NAMES[position].toLowerCase()} projections`}
        >
          All <ChevronRightIcon width={14} height={14} />
        </Link>
      </div>
      {error && <p className="px-2 py-6 text-sm text-muted">Couldn&apos;t load these projections.</p>}
      {loading && <Skeleton className="h-40 w-full" />}
      <ol>
        {top.map((player, i) => (
          <li
            key={player.player_id}
            className="flex items-center gap-3 rounded-xl px-2 py-2"
          >
            <span className="w-5 text-sm font-semibold text-muted tnum">{i + 1}</span>
            <Avatar name={player.name} team={player.team} size={32} />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">{player.name}</span>
              <span className="text-xs text-muted">
                {player.team} {player.is_home ? "vs" : "at"} {player.opponent}
              </span>
            </span>
            <span className="text-right">
              <span className="block text-sm font-semibold tnum">
                {player.points.toFixed(1)}
              </span>
              <span className="block text-xs text-muted tnum">
                {player.low.toFixed(1)}&ndash;{player.high.toFixed(1)}
              </span>
            </span>
          </li>
        ))}
      </ol>
    </Card>
  );
}

function Projections() {
  const { data: index } = useJson<PredictionsIndex>("predictions/latest.json");
  if (!index) return null;
  return (
    <section aria-label="Next week's projections">
      <SectionTitle
        title={`Projected for week ${index.week}`}
        description="The highest projected scores at each position, with the range each one could land in."
        action={
          <Badge tone={index.status === "locked" ? "accent" : "warn"}>
            {index.status === "locked" ? "Locked before kickoff" : "Preliminary"}
          </Badge>
        }
      />
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {POSITIONS.map((position) => (
          <TopProjected key={position} index={index} position={position} />
        ))}
        <Card as="article" className="flex flex-col justify-center gap-2 bg-accent-soft p-6">
          <h3 className="font-semibold">How accurate are these?</h3>
          <p className="text-sm text-muted">
            Projections are locked before kickoff and graded afterwards. The record is public, including the changes that didn&apos;t work.
          </p>
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            <Link href="/report-card/" className="text-sm font-medium text-accent hover:underline">
              See the record
            </Link>
            <Link
              href="/methodology/predictions/"
              className="text-sm font-medium text-accent hover:underline"
            >
              How it works
            </Link>
          </div>
        </Card>
      </div>
    </section>
  );
}

export function HomeView() {
  const { data: meta, error, loading } = useMeta();

  return (
    <div className="rise space-y-12">
      <section className="pt-4 sm:pt-8">
        <h1 className="max-w-3xl text-balance text-4xl font-semibold tracking-tight sm:text-5xl">
          NFL player rankings and predictions
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-muted">
          The <strong className="font-semibold text-fg">rankings</strong> score what players have done so far this season. The <strong className="font-semibold text-fg">projections</strong> estimate what each one will do next, with a range and a public record of how they have done.
        </p>
        {meta && <StatusPills meta={meta} />}
        {loading && <Skeleton className="mt-5 h-7 w-64" />}
        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/rankings/QB/"
            className="rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-accent-fg hover:opacity-90"
          >
            Browse rankings
          </Link>
          <Link
            href="/predictions/QB/"
            className="rounded-xl border border-line bg-surface px-5 py-2.5 text-sm font-semibold hover:bg-surface-2"
          >
            See next week&apos;s projections
          </Link>
        </div>
      </section>

      {error && (
        <ErrorState
          title="Couldn't load the latest rankings"
          message={error.message}
        />
      )}
      {loading && (
        <div className="space-y-6" role="status" aria-label="Loading">
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      )}
      {meta && (
        <>
          <Projections />
          <Movers meta={meta} />
          <section aria-label="Top players by position">
            <SectionTitle
              title="Top of each position"
              description="The five highest composite scores at each position."
            />
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {POSITIONS.map((position) => (
                <TopFive key={position} meta={meta} position={position} />
              ))}
              <Card as="article" className="flex flex-col justify-center gap-2 bg-accent-soft p-6">
                <h3 className="font-semibold">What is the composite score?</h3>
                <p className="text-sm text-muted">
                  It blends how efficiently a player performs (rates per play) with how much they have
                  produced (totals), each measured against other players at the same position.
                </p>
                <Link href="/methodology/" className="text-sm font-medium text-accent hover:underline">
                  Read the methodology
                </Link>
              </Card>
            </div>
          </section>
        </>
      )}
      {!meta && !loading && !error && <EmptyState title="Nothing to show yet" />}
    </div>
  );
}
