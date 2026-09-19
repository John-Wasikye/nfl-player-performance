// Builds a small, fixed copy of the published data for the end-to-end tests, so the tests do not
// depend on whatever the latest pipeline run produced. Re-run it only to refresh the snapshot:
//
//   node scripts/make-fixtures.mjs            (reads ../data/published/v1)
import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = resolve(root, process.env.DATA_SRC ?? "../data/published/v1");
const target = resolve(root, "e2e/fixtures/v1");
const RANKED_KEPT = 12;
const UNRANKED_KEPT = 3;
const POSITIONS = ["QB", "RB", "WR", "TE", "K"];

if (!existsSync(source)) {
  console.error(`No published data at ${source}. Run \`nfl-pipeline run\` first.`);
  process.exit(1);
}

const read = (path) => JSON.parse(readFileSync(path, "utf8"));
const write = (path, value) => {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, JSON.stringify(value));
};

rmSync(target, { recursive: true, force: true });
const meta = read(join(source, "meta.json"));
write(join(target, "meta.json"), meta);
cpSync(join(source, "methodology.json"), join(target, "methodology.json"));

const kept = new Set();
for (const week of meta.weeks) {
  for (const position of POSITIONS) {
    const file = read(join(source, "rankings", String(meta.season), String(week), `${position}.json`));
    const ranked = file.players.filter((p) => p.composite.rank !== null).slice(0, RANKED_KEPT);
    const unranked = file.players.filter((p) => p.composite.rank === null).slice(0, UNRANKED_KEPT);
    file.players = [...ranked, ...unranked];
    for (const p of file.players) kept.add(p.player_id);
    write(join(target, "rankings", String(meta.season), String(week), `${position}.json`), file);
  }
}

const movers = read(join(source, "movers", String(meta.season), `${meta.latest_week}.json`));
for (const side of ["risers", "fallers"]) {
  for (const position of POSITIONS) {
    movers[side][position] = movers[side][position].filter((m) => kept.has(m.player_id));
  }
}
write(join(target, "movers", String(meta.season), `${meta.latest_week}.json`), movers);

let players = 0;
for (const name of readdirSync(join(source, "players"))) {
  if (kept.has(name.replace(/\.json$/, ""))) {
    cpSync(join(source, "players", name), join(target, "players", name));
    players += 1;
  }
}
const PREDICTED_KEPT = 8;
const index = read(join(source, "predictions", "latest.json"));
write(join(target, "predictions", "latest.json"), index);
for (const position of index.positions) {
  const file = read(
    join(source, "predictions", String(index.season), String(index.week), `${position}.json`),
  );
  file.players = file.players.slice(0, PREDICTED_KEPT);
  write(
    join(target, "predictions", String(index.season), String(index.week), `${position}.json`),
    file,
  );
}
cpSync(join(source, "ledger.json"), join(target, "ledger.json"));

// Written by hand because no week has been graded yet and the real file is empty. The numbers are
// made up, to cover the states the Report card has to show, including a losing week.
const gradedWeek = (week, mae, baseline, coverage, frozen, players) => ({
  season: meta.season,
  week,
  player_games: players,
  mae,
  rmse: Number((mae * 1.4).toFixed(4)),
  interval_coverage: coverage,
  baseline_mae: { recent_average: baseline, season_average: baseline + 0.2, last_ten: baseline + 0.1 },
  frozen_model_mae: frozen,
});
const weeks = [
  // Comfortably ahead.
  gradedWeek(1, 5.12, 5.41, 0.801, 5.33, 331),
  // Ahead by less than 0.15, which must not render as a win.
  gradedWeek(2, 5.33, 5.4, 0.792, 5.36, 338),
  // Behind the baseline.
  gradedWeek(3, 5.58, 5.44, 0.774, 5.41, 344),
];
const pooled = (pick) =>
  Number(
    (
      weeks.reduce((sum, w) => sum + pick(w) * w.player_games, 0) /
      weeks.reduce((sum, w) => sum + w.player_games, 0)
    ).toFixed(4),
  );
write(join(target, "accuracy", `${meta.season}.json`), {
  schema_version: meta.schema_version,
  season: meta.season,
  generated_at: meta.generated_at,
  weeks,
  season_to_date: {
    season: meta.season,
    week: 3,
    player_games: weeks.reduce((sum, w) => sum + w.player_games, 0),
    mae: pooled((w) => w.mae),
    rmse: pooled((w) => w.rmse),
    interval_coverage: pooled((w) => w.interval_coverage),
    baseline_mae: {
      recent_average: pooled((w) => w.baseline_mae.recent_average),
      season_average: pooled((w) => w.baseline_mae.season_average),
      last_ten: pooled((w) => w.baseline_mae.last_ten),
    },
    frozen_model_mae: pooled((w) => w.frozen_model_mae),
  },
  verdict:
    "Across 3 graded weeks and 1,013 player-games, projections were off by 5.34 fantasy points on " +
    "average. A player's recent average would have been off by 5.42, so the model is ahead by only " +
    "0.08 points, which is inside the margin I treat as noise. The 80% ranges contained " +
    "the real result 79% of the time. It is level with a model frozen before the season, so nothing " +
    "added this year has made a measurable difference yet.",
});

console.log(
  `fixtures: ${meta.weeks.length} weeks, ${players} players, ` +
    `${index.positions.length} projected positions -> ${target}`,
);
