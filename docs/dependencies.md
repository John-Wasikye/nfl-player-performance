# Dependencies held back, and why

Dependabot proposes updates weekly. These are the ones that are not applied, each with the condition
for removing it. Nothing here is ignored without a reason written down.

| Item | State | Why | Remove when |
|---|---|---|---|
| TypeScript 7 | **split**: 6.0.x for the tools, 7.0.x for the type-check | The npm package for TS 7 has no programmatic API yet (only the `tsc` command), and `typescript-eslint` and Next both need that API. `typescript-eslint` supports `>=4.8.4 <6.1.0`, so `typescript` is held at `~6.0.3`. The `typecheck` script runs the native TS 7 compiler, installed as the `typescript-native` alias, which checks the project in about 6 seconds. A planted type error was seen to fail it | typescript-eslint supports TS 7 (tracked at typescript-eslint#10940); then drop the alias and move `typescript` to 7 |
| `@types/node` 26 | held at 24 (Dependabot ignores majors) | The types should match the Node the site builds with (22 in CI, 24 locally), not run ahead of it | the build moves to a newer Node |
| ESLint 10 | **applied**, with a wrapper | `eslint-plugin-react` 7.37.5, bundled by `eslint-config-next`, calls `context.getFilename()`, which ESLint 10 removed. `web/eslint.config.mjs` wraps the Next configs in `fixupConfigRules` from `@eslint/compat`, which restores it. Checked by planting a conditional hook, a missing `key` and an unused variable: all still reported | `eslint-config-next` ships a plugin that supports ESLint 10; then delete the wrapper |
| `braces` advisory GHSA-vfj7-8cjw-p6xm | **accepted**, no fix exists; GitHub auto-dismissed its alert as dev-only | Stack overflow from deeply nested brace patterns (a crash, not code execution). The advisory lists no patched version and 3.0.3 is the latest release. It is reached only through the lint toolchain (`eslint-config-next` > `@next/eslint-plugin-next` > `fast-glob` > `micromatch` > `braces`), which runs on this repository's own files and is not part of the shipped site. `npm audit --omit=dev` reports 0 vulnerabilities | `braces` publishes a patched release. Do not run `npm audit fix --force`: it "fixes" this by downgrading `eslint-config-next` two major versions |

CI runs `npm audit --omit=dev --audit-level=high` on every change, so a high-severity advisory in anything the
site ships fails the build. That is the check that would have caught the `next/og` advisory (fixed in Next
16.3.6) before it reached a deploy.

Pinned GitHub Actions are updated by Dependabot as full commit SHAs with the version in a comment.
