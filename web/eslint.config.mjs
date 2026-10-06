import { fixupConfigRules } from "@eslint/compat";
import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  // eslint-plugin-react (bundled by eslint-config-next) still calls context.getFilename(), which
  // ESLint 10 removed. fixupConfigRules puts the old context methods back. Drop this wrapper once
  // eslint-config-next ships a plugin that supports ESLint 10.
  ...fixupConfigRules(nextVitals),
  ...fixupConfigRules(nextTs),
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    // Where the end-to-end suite builds, so linting never walks the generated site.
    "out-e2e/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
