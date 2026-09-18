// A tiny static file server for the exported site (the `out` folder), with no dependencies.
//
//   node scripts/serve-static.mjs out                       # serve the site, with its own /data
//   node scripts/serve-static.mjs out --data e2e/fixtures   # serve /data/v1 from a fixture folder
//   options: --port 3210
//
// It mirrors what a static host does: /rankings/QB/ serves rankings/QB/index.html, and unknown
// paths get out/404.html with a 404 status. When serving fixtures, meta.json's generated_at is set
// to "now" so the "data is stale" banner does not appear on its own.
import { createReadStream, existsSync, readFileSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join, normalize, resolve, sep } from "node:path";

const args = process.argv.slice(2);
const flag = (name) => {
  const i = args.indexOf(name);
  return i === -1 ? undefined : args[i + 1];
};
const positional = args.filter((a, i) => !a.startsWith("--") && !args[i - 1]?.startsWith("--"));
const siteDir = resolve(positional[0] ?? "out");
const dataDir = flag("--data") ? resolve(flag("--data")) : null;
const port = Number(flag("--port") ?? 3210);

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
  ".txt": "text/plain; charset=utf-8",
};

function inside(base, target) {
  return target === base || target.startsWith(base + sep);
}

function resolveFile(urlPath) {
  const clean = normalize(decodeURIComponent(urlPath)).replace(/^([/\\])+/, "");
  if (dataDir && clean.replace(/\\/g, "/").startsWith("data/")) {
    const file = resolve(dataDir, clean.slice("data/".length));
    return inside(dataDir, file) ? file : null;
  }
  const file = resolve(siteDir, clean);
  return inside(siteDir, file) ? file : null;
}

const server = createServer((request, response) => {
  const url = new URL(request.url ?? "/", "http://localhost");
  let file = resolveFile(url.pathname);
  if (file && existsSync(file) && statSync(file).isDirectory()) file = join(file, "index.html");

  if (!file || !existsSync(file) || !statSync(file).isFile()) {
    const notFound = join(siteDir, "404.html");
    response.writeHead(404, { "content-type": TYPES[".html"] });
    response.end(existsSync(notFound) ? readFileSync(notFound) : "Not found");
    return;
  }

  const type = TYPES[extname(file)] ?? "application/octet-stream";
  if (dataDir && url.pathname === "/data/v1/meta.json") {
    const meta = JSON.parse(readFileSync(file, "utf8"));
    meta.generated_at = new Date().toISOString();
    response.writeHead(200, { "content-type": type, "cache-control": "no-store" });
    response.end(JSON.stringify(meta));
    return;
  }
  response.writeHead(200, { "content-type": type });
  createReadStream(file).pipe(response);
});

server.listen(port, () => console.log(`serving ${siteDir} on http://localhost:${port}`));
