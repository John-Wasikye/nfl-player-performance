"use client";

import Link from "next/link";
import { useJson } from "@/lib/api";
import { formatPercent, formatPoints } from "@/lib/format";
import {
  POSITION_NAMES,
  type PredictedPlayer,
  type PredictionsFile,
  type PredictionsIndex,
  type Position,
} from "@/lib/types";
import {
  Avatar,
  Badge,
  Card,
  EmptyState,
  ErrorState,
  InjuryBadge,
  PageHeader,
  Skeleton,
} from "./ui";

function positionInRange(player: PredictedPlayer): number {
  const span = player.high - player.low;
  if (span <= 0) return 50;
  return ((player.points - player.low) / span) * 100;
}

function RangeBar({ player }: { player: PredictedPlayer }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-9 text-right text-xs text-muted tnum">{formatPoints(player.low)}</span>
      <span className="relative h-1.5 w-full min-w-16 rounded-full bg-surface-2">
        <span
          className="absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent ring-2 ring-surface"
          style={{ left: `${positionInRange(player)}%` }}
        />
      </span>
      <span className="w-9 text-xs text-muted tnum">{formatPoints(player.high)}</span>
    </div>
  );
}

function PlayerRow({ player, rank }: { player: PredictedPlayer; rank: number }) {
  const doubtful = player.probability_of_playing < 1;
  return (
    <li className="flex items-center gap-3 border-b border-line px-4 py-3 last:border-b-0">
      <span className="w-6 shrink-0 text-sm font-medium text-muted tnum">{rank}</span>
      <Avatar name={player.name} team={player.team} size={32} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <Link
            href={`/player/?id=${encodeURIComponent(player.player_id)}`}
            className="truncate font-medium hover:underline"
          >
            {player.name}
          </Link>
          <InjuryBadge status={player.injury_status} />
        </div>
        <p className="mt-0.5 text-xs text-muted">
          {player.team} {player.is_home ? "vs" : "at"} {player.opponent}
        </p>
      </div>
      <div className="hidden w-44 shrink-0 sm:block">
        <RangeBar player={player} />
      </div>
      <div className="w-20 shrink-0 text-right">
        <p className="font-semibold tnum">{formatPoints(player.points)}</p>
        {doubtful ? (
          <p className="text-xs text-warn tnum">
            {formatPercent(player.probability_of_playing)} to play
          </p>
        ) : (
          <p className="text-xs text-muted tnum sm:hidden">
            {formatPoints(player.low)}–{formatPoints(player.high)}
          </p>
        )}
      </div>
    </li>
  );
}


function ColumnHeadings() {
  return (
    <div
      aria-hidden="true"
      className="flex items-center gap-3 border-b border-line px-4 py-2 text-xs font-medium text-muted"
    >
      <span className="w-6 shrink-0">#</span>
      <span className="w-8 shrink-0" aria-hidden="true" />
      <span className="min-w-0 flex-1">Player and matchup</span>
      <span className="hidden w-44 shrink-0 text-center sm:block">
        Range it could land in (80%)
      </span>
      <span className="w-20 shrink-0 text-right">Projected</span>
    </div>
  );
}

function Key() {
  return (
    <Card as="section" className="mb-4 p-4">
      <h2 className="text-sm font-semibold">What the numbers mean</h2>
      <dl className="mt-2 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
        <div className="flex gap-2">
          <dt className="shrink-0 font-medium">Projected</dt>
          <dd className="text-muted">
            The most likely PPR fantasy score for this game.
          </dd>
        </div>
        <div className="flex gap-2">
          <dt className="shrink-0 font-medium">Range</dt>
          <dd className="text-muted">
            Four games in five should land between these two numbers. The dot marks the projection
            inside it.
          </dd>
        </div>
        <div className="flex gap-2">
          <dt className="shrink-0 font-medium">% to play</dt>
          <dd className="text-muted">
            Shown only for players on the injury report. The projection above it assumes he plays.
          </dd>
        </div>
        <div className="flex gap-2">
          <dt className="shrink-0 font-medium">Order</dt>
          <dd className="text-muted">
            Highest projected first, after discounting anyone who might not play.
          </dd>
        </div>
      </dl>
      <p className="mt-3 text-xs text-muted">
        PPR means one point per reception.{" "}
        <Link href="/methodology/predictions/" className="text-accent underline underline-offset-2">
          How these are produced
        </Link>
        .
      </p>
    </Card>
  );
}

export function PredictionsView({ position }: { position: Position }) {
  const index = useJson<PredictionsIndex>("predictions/latest.json");
  const path = index.data
    ? `predictions/${index.data.season}/${index.data.week}/${position}.json`
    : null;
  const file = useJson<PredictionsFile>(path);

  const error = index.error ?? file.error;
  const loading = index.loading || file.loading;

  return (
    <>
      <PageHeader
        title={`${POSITION_NAMES[position]} projections`}
        subtitle={
          index.data
            ? `Week ${index.data.week} of the ${index.data.season} season. Each projection comes with the range it could land in.`
            : undefined
        }
      >
        {index.data && (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {index.data.status === "locked" ? (
              <Badge tone="accent">Locked before kickoff</Badge>
            ) : (
              <Badge tone="warn">Preliminary, may still change</Badge>
            )}
            <Link href="/report-card/" className="text-sm text-muted underline-offset-2 hover:underline">
              How accurate have these been?
            </Link>
            <Link
              href="/methodology/predictions/"
              className="text-sm text-muted underline-offset-2 hover:underline"
            >
              How these are made
            </Link>
          </div>
        )}
      </PageHeader>

      {error ? (
        <ErrorState message={error.message} />
      ) : loading ? (
        <Skeleton className="h-96 w-full rounded-2xl" />
      ) : !file.data || file.data.players.length === 0 ? (
        <EmptyState
          title="No projections this week"
          message={`No ${position} qualifies this week. Players with a small role are left out because the model did worse than their own recent average on them.`}
        />
      ) : (
        <>
          <Key />
          <Card as="section">
            <ColumnHeadings />
            <ul>
              {file.data.players.map((player, i) => (
                <PlayerRow key={player.player_id} player={player} rank={i + 1} />
              ))}
            </ul>
          </Card>
        </>
      )}

      <p className="mt-4 text-sm text-muted">
        Players ruled Out or Doubtful are left off instead of shown at zero. A Questionable player keeps his projection for if he plays, with the chance he does next to it.
      </p>
    </>
  );
}
