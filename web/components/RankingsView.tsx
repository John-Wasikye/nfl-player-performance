"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { useJson } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatPoints, formatScore } from "@/lib/format";
import {
  DEFAULT_SORT,
  filterPlayers,
  nextSort,
  rankIn,
  sortPlayers,
  splitRanked,
  teamsIn,
  type SortKey,
  type SortState,
} from "@/lib/rankings";
import {
  POSITION_NAMES,
  type Position,
  type RankedPlayer,
  type RankingsFile,
  type RankView,
} from "@/lib/types";
import { SortIcon } from "./icons";
import { useMeta } from "./MetaContext";
import {
  Avatar,
  Badge,
  EmptyState,
  ErrorState,
  InjuryBadge,
  MovementChip,
  PageHeader,
  PositionTabs,
  Segmented,
  Skeleton,
} from "./ui";

interface Column {
  key: string;
  label: string;
  sortKey: SortKey;
  className?: string; // responsive visibility
  numeric?: boolean;
}

function columnsFor(view: RankView): Column[] {
  if (view === "composite") {
    return [
      { key: "rank", label: "#", sortKey: "rank" },
      { key: "player", label: "Player", sortKey: "name" },
      { key: "team", label: "Team", sortKey: "team", className: "hidden sm:table-cell" },
      { key: "score", label: "Score", sortKey: "score", numeric: true },
      { key: "eff", label: "Efficiency", sortKey: "score", className: "hidden lg:table-cell", numeric: true },
      { key: "prod", label: "Production", sortKey: "score", className: "hidden lg:table-cell", numeric: true },
      { key: "games", label: "GP", sortKey: "games", className: "hidden md:table-cell", numeric: true },
      { key: "points", label: "PPR pts", sortKey: "points", className: "hidden md:table-cell", numeric: true },
    ];
  }
  return [
    { key: "rank", label: "#", sortKey: "rank" },
    { key: "player", label: "Player", sortKey: "name" },
    { key: "team", label: "Team", sortKey: "team", className: "hidden sm:table-cell" },
    { key: "points", label: "PPR pts", sortKey: "points", numeric: true },
    { key: "per_game", label: "Per game", sortKey: "per_game", className: "hidden md:table-cell", numeric: true },
    { key: "games", label: "GP", sortKey: "games", className: "hidden md:table-cell", numeric: true },
    { key: "composite", label: "Composite", sortKey: "score", className: "hidden sm:table-cell", numeric: true },
  ];
}

function ScoreBar({ value }: { value: number | null }) {
  return (
    <div className="mt-1 h-1.5 w-full max-w-[5.5rem] rounded-full bg-surface-2" aria-hidden="true">
      <div
        className="h-full rounded-full bg-accent"
        style={{ width: `${Math.max(0, Math.min(100, value ?? 0))}%` }}
      />
    </div>
  );
}

function Cell({ column, player, view }: { column: Column; player: RankedPlayer; view: RankView }) {
  const rank = rankIn(player, view);
  const cls = cn(column.className, column.numeric && "text-right tnum");
  const view_ = view === "composite" ? player.composite : player.fantasy;
  switch (column.key) {
    case "rank":
      return (
        <td className="w-16 py-3 pl-4 pr-2">
          <div className="flex flex-col items-start gap-0.5">
            <span className="text-base font-semibold tnum">{rank ?? "—"}</span>
            <MovementChip movement={view_.movement} isNew={view_.is_new} />
          </div>
        </td>
      );
    case "player":
      return (
        <td className="py-3 pr-2">
          <Link
            href={`/player/?id=${encodeURIComponent(player.player_id)}`}
            className="group flex items-center gap-3"
          >
            <Avatar name={player.name} team={player.team} />
            <span className="min-w-0">
              <span className="block truncate font-medium group-hover:text-accent">{player.name}</span>
              <span className="flex items-center gap-2 text-xs text-muted sm:hidden">
                {player.team}
                <InjuryBadge status={player.injury_status} />
              </span>
            </span>
            <span className="hidden sm:inline">
              <InjuryBadge status={player.injury_status} />
            </span>
          </Link>
        </td>
      );
    case "team":
      return <td className={cn("py-3 pr-2 text-muted", cls)}>{player.team}</td>;
    case "score":
      return (
        <td className={cn("py-3 pr-4", cls)}>
          <div className="flex flex-col items-end">
            <span className="font-semibold">{formatScore(player.composite.score)}</span>
            <ScoreBar value={player.composite.score} />
          </div>
        </td>
      );
    case "eff":
      return <td className={cn("py-3 pr-4 text-muted", cls)}>{formatScore(player.composite.efficiency)}</td>;
    case "prod":
      return <td className={cn("py-3 pr-4 text-muted", cls)}>{formatScore(player.composite.production)}</td>;
    case "games":
      return <td className={cn("py-3 pr-4 text-muted", cls)}>{player.games}</td>;
    case "points":
      return (
        <td className={cn("py-3 pr-4", view === "fantasy" ? "font-semibold" : "text-muted", cls)}>
          {formatPoints(player.fantasy.points)}
        </td>
      );
    case "per_game":
      return <td className={cn("py-3 pr-4 text-muted", cls)}>{formatPoints(player.fantasy.per_game)}</td>;
    case "composite":
      return (
        <td className={cn("py-3 pr-4 text-muted", cls)}>
          {player.composite.rank ? `#${player.composite.rank}` : "—"}
        </td>
      );
    default:
      return null;
  }
}

function RankingsTable({
  players,
  view,
  sort,
  onSort,
  caption,
}: {
  players: RankedPlayer[];
  view: RankView;
  sort: SortState;
  onSort: (key: SortKey) => void;
  caption: string;
}) {
  const columns = columnsFor(view);
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
            {columns.map((column, index) => {
              const active = sort.key === column.sortKey && (column.key !== "eff" && column.key !== "prod");
              const sortable = column.key !== "eff" && column.key !== "prod";
              return (
                <th
                  key={column.key}
                  scope="col"
                  aria-sort={active ? (sort.direction === "asc" ? "ascending" : "descending") : undefined}
                  className={cn(
                    "py-2.5 font-medium",
                    index === 0 ? "pl-4 pr-2" : "pr-4",
                    column.className,
                    column.numeric && "text-right",
                  )}
                >
                  {sortable ? (
                    <button
                      type="button"
                      onClick={() => onSort(column.sortKey)}
                      aria-label={`Sort by ${column.label}`}
                      className={cn(
                        "inline-flex items-center gap-1 uppercase tracking-wide hover:text-fg",
                        active && "text-fg",
                      )}
                    >
                      {column.label}
                      <SortIcon direction={active ? sort.direction : undefined} />
                    </button>
                  ) : (
                    column.label
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {players.map((player) => (
            <tr key={player.player_id} className="border-b border-line/70 last:border-0 hover:bg-surface-2/60">
              {columns.map((column) => (
                <Cell key={column.key} column={column} player={player} view={view} />
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TableSkeleton() {
  return (
    <div className="space-y-3 p-4" role="status" aria-label="Loading rankings">
      {Array.from({ length: 10 }, (_, i) => (
        <div key={i} className="flex items-center gap-4">
          <Skeleton className="h-9 w-9 rounded-full" />
          <Skeleton className="h-4 flex-1" />
          <Skeleton className="h-4 w-16" />
        </div>
      ))}
    </div>
  );
}

export function RankingsView({ position }: { position: Position }) {
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams();
  const { data: meta, error: metaError } = useMeta();

  const view: RankView = search.get("view") === "fantasy" ? "fantasy" : "composite";
  const requestedWeek = Number(search.get("week"));
  const week =
    meta && meta.weeks.includes(requestedWeek) ? requestedWeek : (meta?.latest_week ?? null);

  const [sort, setSort] = useState<SortState>(DEFAULT_SORT);
  const [query, setQuery] = useState("");
  const [team, setTeam] = useState("");

  const path = meta && week !== null ? `rankings/${meta.season}/${week}/${position}.json` : null;
  const { data, error, loading } = useJson<RankingsFile>(path);

  function setParam(name: string, value: string | null) {
    const params = new URLSearchParams(search.toString());
    if (value === null) params.delete(name);
    else params.set(name, value);
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }

  const { ranked, unranked, visible, teams } = useMemo(() => {
    const players = data?.players ?? [];
    const filtered = filterPlayers(players, { query, team });
    const split = splitRanked(filtered, view);
    return {
      ranked: sortPlayers(split.ranked, sort, view),
      unranked: split.unranked,
      visible: filtered.length,
      teams: teamsIn(players),
    };
  }, [data, query, team, view, sort]);

  const weekLabel =
    week === null ? "" : `Week ${week}${data && !data.week_complete ? " (in progress)" : ""}`;

  return (
    <div className="rise">
      <PageHeader
        title={POSITION_NAMES[position]}
        subtitle={
          view === "composite" ? (
            <>
              Ranked by a composite score that blends how efficiently each player performs with how
              much they have produced.{" "}
              <Link href="/methodology/" className="text-accent underline underline-offset-2">
                How it works
              </Link>
            </>
          ) : (
            "Ranked by season-to-date PPR fantasy points (standard scoring for kickers)."
          )
        }
      />
      <div className="mb-5 space-y-4">
        <PositionTabs active={position} />
        <div className="flex flex-wrap items-center gap-3">
          <Segmented<RankView>
            label="Ranking view"
            value={view}
            options={[
              { value: "composite", label: "Composite" },
              { value: "fantasy", label: "Fantasy PPR" },
            ]}
            onChange={(next) => setParam("view", next === "composite" ? null : next)}
          />
          {meta && (
            <label className="flex items-center gap-2 text-sm text-muted">
              <span className="sr-only sm:not-sr-only">Week</span>
              <select
                value={week ?? ""}
                onChange={(event) => setParam("week", event.target.value)}
                aria-label="Week"
                className="rounded-lg border border-line bg-surface px-3 py-1.5 text-sm text-fg"
              >
                {[...meta.weeks].reverse().map((w) => (
                  <option key={w} value={w}>
                    Week {w}
                    {w === meta.latest_week && !meta.week_complete ? " (in progress)" : ""}
                  </option>
                ))}
              </select>
            </label>
          )}
          <select
            value={team}
            onChange={(event) => setTeam(event.target.value)}
            aria-label="Team"
            className="rounded-lg border border-line bg-surface px-3 py-1.5 text-sm text-fg"
          >
            <option value="">All teams</option>
            {teams.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Filter players"
            aria-label="Filter players by name"
            className="w-full min-w-0 rounded-lg border border-line bg-surface px-3 py-1.5 text-sm placeholder:text-muted sm:w-auto sm:max-w-xs sm:flex-1"
          />
        </div>
      </div>

      <section aria-label={`${POSITION_NAMES[position]} rankings`} className="rounded-2xl border border-line bg-surface shadow-card">
        {(metaError || error) && (
          <div className="p-4">
            <ErrorState
              title="Couldn't load the rankings"
              message={(metaError ?? error)?.message ?? "Please try again."}
            />
          </div>
        )}
        {!metaError && !error && (loading || !meta) && <TableSkeleton />}
        {data && (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3 text-sm">
              <span className="font-medium">
                {weekLabel} <span className="font-normal text-muted">· {data.season} season</span>
              </span>
              <span className="text-muted">
                {visible} {visible === 1 ? "player" : "players"}
              </span>
            </div>
            {ranked.length > 0 ? (
              <RankingsTable
                players={ranked}
                view={view}
                sort={sort}
                onSort={(key) => setSort((current) => nextSort(current, key))}
                caption={`${POSITION_NAMES[position]} ranked by ${view === "composite" ? "composite score" : "PPR fantasy points"}, ${weekLabel}`}
              />
            ) : (
              <div className="p-4">
                <EmptyState
                  title="No players match"
                  message={
                    query || team
                      ? "Try a different name or team."
                      : "Nobody is ranked here yet this week."
                  }
                />
              </div>
            )}
            {unranked.length > 0 && (
              <details className="border-t border-line">
                <summary className="flex cursor-pointer items-center justify-between gap-2 px-4 py-3 text-sm font-medium hover:bg-surface-2/60">
                  <span>
                    Not ranked yet <Badge>{unranked.length}</Badge>
                  </span>
                  <span className="text-xs font-normal text-muted">Not enough volume so far</span>
                </summary>
                <p className="px-4 pb-2 text-sm text-muted">
                  These players haven&apos;t had enough attempts, carries, targets, or kicks for the
                  games their team has played, so they don&apos;t get a composite score. Listed by
                  fantasy points.
                </p>
                <RankingsTable
                  players={unranked}
                  view="fantasy"
                  sort={{ key: "rank", direction: "asc" }}
                  onSort={() => {}}
                  caption={`${POSITION_NAMES[position]} not yet ranked`}
                />
              </details>
            )}
          </>
        )}
      </section>
    </div>
  );
}
