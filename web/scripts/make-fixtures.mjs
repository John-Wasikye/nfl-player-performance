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
console.log(`fixtures: ${meta.weeks.length} weeks, ${players} players -> ${target}`);
