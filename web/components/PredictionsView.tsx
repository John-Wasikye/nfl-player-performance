"use client";

// The Predictions page.
//
// Two things here are deliberate and easy to get wrong if they are treated as styling choices.
//
// The range is shown next to every projection, never hidden behind a hover or a tooltip. A single
// number implies a precision that does not exist: one game of fantasy football is noisy enough that
// the honest 80% range is about 16 points wide, and a reader who sees only "12.4" will believe
// something the model is not claiming.
//
// A player who might not play shows his score *if he plays* as the main figure, with the chance of
// playing beside it. Leading with the availability-adjusted number would quietly mix two different
// questions — how good is he, and will he be there — into one figure that answers neither.
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

/** Where a projection sits inside its own range, as a percentage for the bar. */
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
            ? `Week ${index.data.week} of the ${index.data.season} season. Every projection shows the 80% range it sits in, because a single number would claim more certainty than one game allows.`
            : undefined
        }
      >
        {index.data && (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {index.data.status === "locked" ? (
              <Badge tone="accent">Locked before kickoff</Badge>
            ) : (
              <Badge tone="warn">Preliminary — may still change</Badge>
            )}
            <Link href="/report-card/" className="text-sm text-muted underline-offset-2 hover:underline">
              How accurate have these been?
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
          message={`No ${position} has enough recent playing time to project. Players with a very small role are left out on purpose: the model was measured doing worse than their own recent average, so a projection would be misleading.`}
        />
      ) : (
        <Card as="section">
          <ul>
            {file.data.players.map((player, i) => (
              <PlayerRow key={player.player_id} player={player} rank={i + 1} />
            ))}
          </ul>
        </Card>
      )}

      <p className="mt-4 text-sm text-muted">
        Players ruled Out or Doubtful are not shown at all, rather than shown at zero. Anyone listed
        Questionable keeps his projection for if he plays, with the chance he does beside it.
      </p>
    </>
  );
}
