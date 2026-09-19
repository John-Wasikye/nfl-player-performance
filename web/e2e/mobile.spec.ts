import { expect, test, type Page } from "@playwright/test";

// Runs on a phone-sized viewport (see the "mobile" project in playwright.config.ts).

async function hasHorizontalOverflow(page: Page) {
  return page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
}

test.describe("on a phone", () => {
  for (const path of [
    "/",
    "/rankings/QB/",
    "/rankings/QB/?view=fantasy",
    "/predictions/QB/",
    "/report-card/",
    "/methodology/predictions/",
    "/methodology/predictions/research/",
    "/methodology/",
    "/about/",
  ]) {
    test(`${path} fits the screen without sideways scrolling`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState("networkidle");

      expect(await hasHorizontalOverflow(page)).toBe(false);
    });
  }

  test("the player page fits the screen", async ({ page }) => {
    await page.goto("/rankings/QB/");
    await page.getByRole("table").first().locator("tbody tr").first().getByRole("link").click();
    await page.getByRole("heading", { name: "Why this rank" }).waitFor();

    expect(await hasHorizontalOverflow(page)).toBe(false);
  });

  test("every header control is visible and reachable", async ({ page }) => {
    await page.goto("/");
    const nav = page.getByRole("navigation", { name: "Primary" });

    for (const name of [
      "Home",
      "Rankings",
      "Projections",
      "Report card",
      "Methodology",
      "About",
    ]) {
      await expect(nav.getByRole("link", { name })).toBeInViewport();
    }
    await expect(page.getByRole("button", { name: "Search players" })).toBeInViewport();
    await expect(page.getByRole("button", { name: /Switch to (dark|light) theme/ })).toBeInViewport();
  });

  test("the rankings table shows the essentials and hides the rest", async ({ page }) => {
    await page.goto("/rankings/QB/");
    const table = page.getByRole("table").first();
    await table.waitFor();

    await expect(table.getByRole("columnheader", { name: /Score/ })).toBeVisible();
    await expect(table.getByRole("columnheader", { name: /Efficiency/ })).toBeHidden();
    await expect(table.getByRole("columnheader", { name: /PPR pts/ })).toBeHidden();
  });

  test("touch targets in the header are large enough", async ({ page }) => {
    await page.goto("/");
    for (const name of [/Search players/, /Switch to (dark|light) theme/]) {
      const box = await page.getByRole("button", { name }).boundingBox();
      expect(box!.height).toBeGreaterThanOrEqual(36);
      expect(box!.width).toBeGreaterThanOrEqual(36);
    }
  });
});
