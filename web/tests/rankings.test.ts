import { describe, expect, it } from "vitest";
import {
  filterPlayers,
  matchesQuery,
  nextSort,
  rankIn,
  sortPlayers,
  splitRanked,
  teamsIn,
} from "@/lib/rankings";
import type { RankedPlayer } from "@/lib/types";

function player(
  id: string,
  name: string,
  team: string,
  overrides: { rank?: number | null; score?: number | null; fantasy?: number; points?: number; games?: number } = {},
): RankedPlayer {
  const rank = overrides.rank === undefined ? 1 : overrides.rank;
  return {
    player_id: id,
    name,
    team,
    injury_status: null,
    games: overrides.games ?? 2,
    qualified: rank !== null,
    composite: {
      score: overrides.score === undefined ? (rank === null ? null : 80) : overrides.score,
      efficiency: 70,
      production: 60,
      rank,
      rank_prev: null,
      movement: null,
      is_new: false,
    },
    fantasy: {
      points: overrides.points ?? 20,
      per_game: 10,
      rank: overrides.fantasy ?? 1,
      rank_prev: null,
      movement: null,
      is_new: false,
    },
  };
}

const allen = player("A", "Josh Allen", "BUF", { rank: 1, score: 90, fantasy: 2, points: 40 });
const lawrence = player("L", "Trevor Lawrence", "JAX", { rank: 2, score: 85, fantasy: 1, points: 50 });
const dart = player("D", "Jaxson Dart", "NYG", { rank: 3, score: 70, fantasy: 3, points: 30 });
const backup = player("B", "Sam Backup", "BUF", { rank: null, fantasy: 4, points: 5, games: 1 });
const all = [dart, backup, allen, lawrence];

describe("splitting ranked and unranked players", () => {
  it("puts ranked players first, in rank order, and the rest after by fantasy rank", () => {
    const { ranked, unranked } = splitRanked(all, "composite");

    expect(ranked.map((p) => p.player_id)).toEqual(["A", "L", "D"]);
    expect(unranked.map((p) => p.player_id)).toEqual(["B"]);
  });

  it("ranks everyone in the fantasy view", () => {
    const { ranked, unranked } = splitRanked(all, "fantasy");

    expect(ranked.map((p) => p.player_id)).toEqual(["L", "A", "D", "B"]);
    expect(unranked).toEqual([]);
  });

  it("reads the rank for the chosen view", () => {
    expect(rankIn(allen, "composite")).toBe(1);
    expect(rankIn(allen, "fantasy")).toBe(2);
    expect(rankIn(backup, "composite")).toBeNull();
  });
});

describe("filtering", () => {
  it("matches a name fragment case-insensitively", () => {
    expect(matchesQuery(allen, "ALLEN")).toBe(true);
    expect(matchesQuery(allen, "osh al")).toBe(true);
    expect(matchesQuery(allen, "mahomes")).toBe(false);
  });

  it("matches a team code exactly, but not a fragment of it", () => {
    expect(matchesQuery(allen, "buf")).toBe(true);
    expect(matchesQuery(allen, "bu")).toBe(false);
  });

  it("treats an empty query as everyone", () => {
    expect(matchesQuery(allen, "   ")).toBe(true);
  });

  it("combines the name and team filters", () => {
    expect(filterPlayers(all, { team: "BUF" }).map((p) => p.player_id)).toEqual(["B", "A"]);
    expect(filterPlayers(all, { team: "BUF", query: "allen" }).map((p) => p.player_id)).toEqual(["A"]);
    expect(filterPlayers(all, { query: "zzz" })).toEqual([]);
  });

  it("lists the teams present, sorted", () => {
    expect(teamsIn(all)).toEqual(["BUF", "JAX", "NYG"]);
  });
});

describe("sorting", () => {
  const ids = (list: RankedPlayer[]) => list.map((p) => p.player_id);

  it("sorts by rank ascending", () => {
    const { ranked } = splitRanked(all, "composite");
    expect(ids(sortPlayers(ranked, { key: "rank", direction: "asc" }, "composite"))).toEqual(["A", "L", "D"]);
  });

  it("sorts numbers in either direction", () => {
    expect(ids(sortPlayers(all, { key: "points", direction: "desc" }, "fantasy"))).toEqual(["L", "A", "D", "B"]);
    expect(ids(sortPlayers(all, { key: "points", direction: "asc" }, "fantasy"))).toEqual(["B", "D", "A", "L"]);
  });

  it("sorts names alphabetically", () => {
    expect(ids(sortPlayers(all, { key: "name", direction: "asc" }, "fantasy"))).toEqual(["D", "A", "B", "L"]);
  });

  it("always puts players with a missing value last, whichever way it sorts", () => {
    expect(ids(sortPlayers(all, { key: "score", direction: "desc" }, "composite")).at(-1)).toBe("B");
    expect(ids(sortPlayers(all, { key: "score", direction: "asc" }, "composite")).at(-1)).toBe("B");
  });

  it("does not change the list it is given", () => {
    const before = ids(all);
    sortPlayers(all, { key: "points", direction: "asc" }, "fantasy");
    expect(ids(all)).toEqual(before);
  });

  it("breaks ties by fantasy rank so the order is stable", () => {
    const a = player("X", "Xavier", "KC", { rank: 1, score: 80, fantasy: 5 });
    const b = player("Y", "Yusuf", "KC", { rank: 2, score: 80, fantasy: 3 });
    expect(ids(sortPlayers([a, b], { key: "score", direction: "desc" }, "composite"))).toEqual(["Y", "X"]);
  });
});

describe("choosing the next sort when a header is clicked", () => {
  it("starts numbers high to low and text A to Z", () => {
    expect(nextSort({ key: "rank", direction: "asc" }, "points")).toEqual({ key: "points", direction: "desc" });
    expect(nextSort({ key: "rank", direction: "asc" }, "name")).toEqual({ key: "name", direction: "asc" });
  });

  it("flips the direction when the same header is clicked again", () => {
    expect(nextSort({ key: "points", direction: "desc" }, "points")).toEqual({ key: "points", direction: "asc" });
    expect(nextSort({ key: "points", direction: "asc" }, "points")).toEqual({ key: "points", direction: "desc" });
  });
});
