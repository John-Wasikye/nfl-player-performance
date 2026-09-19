import { expect, test } from "@playwright/test";

// The fixtures are a fixed snapshot: 2026 week 2 projections (preliminary, not yet locked) and a
// hand-written accuracy file with three graded weeks, chosen to cover the states the Report card
// has to handle rather than the flattering ones.

test.describe("Projections", () => {
  test("shows a projection with the range it sits in, not a bare number", async ({ page }) => {
    await page.goto("/predictions/QB/");

    await expect(page.getByRole("heading", { level: 1 })).toContainText("Quarterbacks projections");
    const first = page.getByRole("listitem").first();
    await expect(first).toContainText("Josh Allen");
    // The low and high of the 80% range are on the row, always visible.
    await expect(first).toContainText("24.3");
    await expect(first).toContainText("10.7");
    await expect(first).toContainText("34.0");
  });

  test("says when the week is still preliminary rather than implying it is final", async ({ page }) => {
    await page.goto("/predictions/QB/");

    await expect(page.getByText("Preliminary — may still change")).toBeVisible();
  });

  test("explains that ruled-out players are left out rather than shown at zero", async ({ page }) => {
    await page.goto("/predictions/RB/");

    await expect(page.getByText(/ruled Out or Doubtful are not shown at all/)).toBeVisible();
  });

  test("each position has its own page", async ({ page }) => {
    await page.goto("/predictions/TE/");

    await expect(page.getByRole("heading", { level: 1 })).toContainText("Tight ends projections");
  });

  test("links to the accuracy record", async ({ page }) => {
    await page.goto("/predictions/QB/");
    await page.getByRole("link", { name: "How accurate have these been?" }).click();

    await expect(page.getByRole("heading", { level: 1 })).toContainText("Report card");
  });
});

test.describe("Report card", () => {
  test("shows the verdict the pipeline generated, unedited", async ({ page }) => {
    await page.goto("/report-card/");

    await expect(page.getByText(/inside the margin this project treats as noise/)).toBeVisible();
  });

  test("never shows an accuracy figure without the player count behind it", async ({ page }) => {
    await page.goto("/report-card/");

    await expect(page.getByText("Average error", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Player-games", { exact: true })).toBeVisible();
    // Every graded week's row carries its own count too.
    const row = page.getByRole("row").filter({ hasText: "331" });
    await expect(row).toBeVisible();
  });

  test("shows a week where the model lost to the baseline, rather than hiding it", async ({ page }) => {
    await page.goto("/report-card/");

    // Week 3 of the fixture is deliberately behind: 5.58 against a 5.44 baseline.
    const week3 = page.getByRole("row").filter({ hasText: "5.58" });
    await expect(week3).toBeVisible();
    await expect(week3).toContainText("-0.14");
  });

  test("publishes the experiments that failed, not only the ones that worked", async ({ page }) => {
    await page.goto("/report-card/");

    const rejected = page.getByRole("listitem").filter({ hasText: "Rejected" });
    await expect(rejected).toHaveCount(1);
    await expect(rejected).toContainText("training set as well");
  });

  test("says which metric judged an experiment that changed the population", async ({ page }) => {
    await page.goto("/report-card/");

    await expect(
      page.getByText(/not average error: this change altered which players are predicted/),
    ).toBeVisible();
  });

  test("explains that average error cannot be compared across populations", async ({ page }) => {
    await page.goto("/report-card/");

    await expect(page.getByText(/stricter selection raises this number/)).toBeVisible();
  });
});
