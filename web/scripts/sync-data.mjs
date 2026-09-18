// Copies the pipeline's published JSON into public/data/v1 so the dev server (and a local build)
// can serve it. In production the same files are served from the data bucket, so this is dev-only.
//
//   node scripts/sync-data.mjs                 # from ../data/published/v1
//   DATA_SRC=some/dir/v1 node scripts/sync-data.mjs
import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = resolve(root, process.env.DATA_SRC ?? "../data/published/v1");
const target = resolve(root, "public/data/v1");

if (!existsSync(source)) {
  console.warn(
    `sync-data: no published data at ${source}. Run \`nfl-pipeline run\` in the repo root first.`,
  );
  process.exit(0);
}

rmSync(target, { recursive: true, force: true });
mkdirSync(dirname(target), { recursive: true });
cpSync(source, target, { recursive: true });
console.log(`sync-data: copied ${source} -> ${target}`);
