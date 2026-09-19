import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

// axe checks (WCAG 2.2 A and AA) on each kind of page, in both themes. They don't replace testing
// with a screen reader.

const fixture = (path: string) => JSON.parse(readFileSync(join(__dirname, "fixtures/v1", path), "utf8"));
const topQuarterback: string = fixture("rankings/2026/2/QB.json").players[0].player_id;

const PAGES: Array<{ name: string; path: string; ready: (page: Page) => Promise<void> }> = [
  {
    name: "home",
    path: "/",
    // Both the projections and the rankings sections list every position, so this says which.
    ready: (page) =>
      page
        .getByRole("region", { name: "Top players by position" })
        .getByRole("heading", { level: 3, name: "Kickers" })
        .waitFor(),
  },
  {
    name: "rankings (composite)",
    path: "/rankings/QB/",
    ready: (page) => page.getByRole("table").first().waitFor(),
  },
  {
    name: "rankings (fantasy)",
    path: "/rankings/RB/?view=fantasy",
    ready: (page) => page.getByRole("table").first().waitFor(),
  },
  {
    name: "player",
    path: `/player/?id=${topQuarterback}`,
    ready: (page) => page.getByRole("heading", { name: "Why this rank" }).waitFor(),
  },
  {
    name: "projections",
    path: "/predictions/QB/",
    ready: (page) => page.getByRole("listitem").first().waitFor(),
  },
  {
    name: "report card",
    path: "/report-card/",
    ready: (page) => page.getByRole("table").first().waitFor(),
  },
  {
    name: "research paper",
    path: "/methodology/predictions/research/",
    ready: (page) => page.getByRole("navigation", { name: "Paper contents" }).waitFor(),
  },
  {
    name: "methodology",
    path: "/methodology/",
    ready: (page) => page.getByRole("region", { name: "Backtest" }).waitFor(),
  },
  {
    name: "about",
    path: "/about/",
    ready: (page) => page.getByRole("heading", { name: "Glossary" }).waitFor(),
  },
];

for (const theme of ["light", "dark"] as const) {
  test.describe(`accessibility (${theme})`, () => {
    for (const { name, path, ready } of PAGES) {
      test(`${name} has no detectable violations`, async ({ page }) => {
        await page.addInitScript((value) => localStorage.setItem("theme", value), theme);
        await page.goto(path);
        await ready(page);

        const results = await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
          .analyze();

        const summary = results.violations.map((v) => ({
          rule: v.id,
          impact: v.impact,
          nodes: v.nodes.slice(0, 3).map((n) => n.html.slice(0, 140)),
        }));
        expect(summary, JSON.stringify(summary, null, 2)).toEqual([]);
      });
    }
  });
}

test("the search dialog is accessible when open", async ({ page }) => {
  await page.goto("/");
  await page
    .getByRole("region", { name: "Top players by position" })
    .getByRole("heading", { level: 3, name: "Kickers" })
    .waitFor();
  await page.keyboard.press("/");
  await page.getByRole("dialog").getByRole("textbox").fill("allen");
  await page.getByRole("dialog").getByRole("link", { name: /Josh Allen/ }).waitFor();

  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();

  expect(results.violations.map((v) => v.id)).toEqual([]);
});

test("everything can be reached and used with the keyboard alone", async ({ page }) => {
  await page.goto("/rankings/QB/");
  await page.getByRole("table").first().waitFor();

  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();

  // Tab until the first player link is focused, then follow it with Enter.
  for (let i = 0; i < 40; i++) {
    await page.keyboard.press("Tab");
    const focused = await page.evaluate(() => document.activeElement?.textContent ?? "");
    if (focused.includes("Josh Allen")) break;
  }
  await page.keyboard.press("Enter");

  await expect(page).toHaveURL(/\/player\/\?id=/);
});
