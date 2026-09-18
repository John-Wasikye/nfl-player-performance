// Pure functions for sorting and filtering a rankings table.
import type { RankedPlayer, RankView } from "./types";

export type SortKey = "rank" | "name" | "team" | "score" | "points" | "per_game" | "games";
export type SortDirection = "asc" | "desc";

export interface SortState {
  key: SortKey;
  direction: SortDirection;
}

export const DEFAULT_SORT: SortState = { key: "rank", direction: "asc" };

/** The rank a player holds in the chosen view (null when unranked in the composite view). */
export function rankIn(player: RankedPlayer, view: RankView): number | null {
  return view === "composite" ? player.composite.rank : player.fantasy.rank;
}

/** Ranked players first (they have a rank in this view), the rest after. */
export function splitRanked(players: RankedPlayer[], view: RankView) {
  const ranked = players.filter((p) => rankIn(p, view) !== null);
  const unranked = players.filter((p) => rankIn(p, view) === null);
  ranked.sort((a, b) => (rankIn(a, view) ?? 0) - (rankIn(b, view) ?? 0));
  unranked.sort((a, b) => a.fantasy.rank - b.fantasy.rank);
  return { ranked, unranked };
}

/** Case-insensitive match on a player's name or team. An empty query matches everyone. */
export function matchesQuery(player: RankedPlayer, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return player.name.toLowerCase().includes(q) || player.team.toLowerCase() === q;
}

export function filterPlayers(
  players: RankedPlayer[],
  { query = "", team = "" }: { query?: string; team?: string },
): RankedPlayer[] {
  return players.filter((p) => (!team || p.team === team) && matchesQuery(p, query));
}

function sortValue(player: RankedPlayer, key: SortKey, view: RankView): string | number | null {
  switch (key) {
    case "rank":
      return rankIn(player, view);
    case "name":
      return player.name.toLowerCase();
    case "team":
      return player.team;
    case "score":
      return player.composite.score;
    case "points":
      return player.fantasy.points;
    case "per_game":
      return player.fantasy.per_game;
    case "games":
      return player.games;
  }
}

/** Sort a copy of the list. Missing values always sort last, whichever direction is chosen. */
export function sortPlayers(
  players: RankedPlayer[],
  { key, direction }: SortState,
  view: RankView,
): RankedPlayer[] {
  const sign = direction === "asc" ? 1 : -1;
  return [...players].sort((a, b) => {
    const av = sortValue(a, key, view);
    const bv = sortValue(b, key, view);
    if (av === null && bv === null) return a.fantasy.rank - b.fantasy.rank;
    if (av === null) return 1;
    if (bv === null) return -1;
    if (av < bv) return -1 * sign;
    if (av > bv) return 1 * sign;
    return a.fantasy.rank - b.fantasy.rank;
  });
}

/** The teams present in a list, alphabetically, for a filter menu. */
export function teamsIn(players: RankedPlayer[]): string[] {
  return [...new Set(players.map((p) => p.team))].sort();
}

/** What to sort by first when a column header is clicked: numbers start high-to-low, text A-Z. */
export function nextSort(current: SortState, key: SortKey): SortState {
  if (current.key === key) {
    return { key, direction: current.direction === "asc" ? "desc" : "asc" };
  }
  const textual = key === "name" || key === "team" || key === "rank";
  return { key, direction: textual ? "asc" : "desc" };
}
