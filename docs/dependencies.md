# Dependencies held back, and why

Dependabot proposes updates weekly. These are the ones that are not applied, each with the condition
for removing it. Nothing here is ignored without a reason written down.

| Item | State | Why | Remove when |
|---|---|---|---|
| TypeScript 7 | held at 5.9 (Dependabot ignores majors) | `typescript-eslint`, which `eslint-config-next` bundles, throws "does not support TS 7.0", so `npm run lint` fails | typescript-eslint supports TS 7 (tracked at typescript-eslint#10940) |
| `@types/node` 26 | held at 24 (Dependabot ignores majors) | The types should match the Node the site builds with (22 in CI, 24 locally), not run ahead of it | the build moves to a newer Node |
| ESLint 10 | **applied**, with a wrapper | `eslint-plugin-react` 7.37.5, bundled by `eslint-config-next`, calls `context.getFilename()`, which ESLint 10 removed. `web/eslint.config.mjs` wraps the Next configs in `fixupConfigRules` from `@eslint/compat`, which restores it. Checked by planting a conditional hook, a missing `key` and an unused variable: all still reported | `eslint-config-next` ships a plugin that supports ESLint 10; then delete the wrapper |
| `braces` advisory GHSA-vfj7-8cjw-p6xm | **accepted**, no fix exists | Stack overflow from deeply nested brace patterns (a crash, not code execution). The advisory lists no patched version and 3.0.3 is the latest release. It is reached only through the lint toolchain (`eslint-config-next` > `@next/eslint-plugin-next` > `fast-glob` > `micromatch` > `braces`), which runs on this repository's own files and is not part of the shipped site. `npm audit --omit=dev` reports 0 vulnerabilities | `braces` publishes a patched release. Do not run `npm audit fix --force`: it "fixes" this by downgrading `eslint-config-next` two major versions |

Pinned GitHub Actions are updated by Dependabot as full commit SHAs with the version in a comment.
