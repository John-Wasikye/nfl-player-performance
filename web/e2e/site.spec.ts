import { expect, test, type Page } from "@playwright/test";

// The fixtures are a fixed snapshot: 2026 season, weeks 1-2, week 2 in progress. Josh Allen is the
// top-ranked quarterback in both views.

const rows = (page: Page) => page.getByRole("table").first().locator("tbody tr");

test.describe("Home", () => {
  test("shows the season status, the movers, and the top of every position", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByRole("heading", { level: 1 })).toContainText("NFL player rankings");
    await expect(page.getByText(/2026 season · Week 2 in progress/)).toBeVisible();
    await expect(page.getByRole("region", { name: "Biggest movers" })).toBeVisible();
    // Both the rankings and the projections sections list every position, so this has to say which.
    const ranked = page.getByRole("region", { name: "Top players by position" });
    for (const name of ["Quarterbacks", "Running backs", "Wide receivers", "Tight ends", "Kickers"]) {
      await expect(ranked.getByRole("heading", { level: 3, name })).toBeVisible();
    }
  });

  test("switches the movers between positions", async ({ page }) => {
    await page.goto("/");
    const rb = page.getByRole("tab", { name: "RB" });

    await expect(page.getByRole("tab", { name: "QB" })).toHaveAttribute("aria-selected", "true");
    await rb.click();

    await expect(rb).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("tab", { name: "QB" })).toHaveAttribute("aria-selected", "false");
  });

  test("links into the rankings", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Browse rankings" }).click();

    await expect(page).toHaveURL(/\/rankings\/QB\/$/);
    await expect(page.getByRole("heading", { level: 1, name: "Quarterbacks" })).toBeVisible();
  });
});

test.describe("Rankings", () => {
  test("lists the ranked players in order, best first", async ({ page }) => {
    await page.goto("/rankings/QB/");

    await expect(rows(page).first()).toContainText("Josh Allen");
    await expect(rows(page).first().locator("td").first()).toContainText("1");
    await expect(rows(page)).toHaveCount(12);
  });

  test("has a tab for every position", async ({ page }) => {
    await page.goto("/rankings/QB/");
    const tabs = page.getByRole("navigation", { name: "Positions" });

    for (const position of ["RB", "WR", "TE", "K"]) {
      await tabs.getByRole("link", { name: position }).click();
      await expect(page).toHaveURL(new RegExp(`/rankings/${position}/$`));
      await expect(rows(page).first()).toBeVisible();
    }
  });

  test("switches to the fantasy view and keeps it in the URL", async ({ page }) => {
    await page.goto("/rankings/QB/");
    await page.getByRole("radio", { name: "Fantasy PPR" }).click();

    await expect(page).toHaveURL(/view=fantasy/);
    await expect(page.getByRole("radio", { name: "Fantasy PPR" })).toHaveAttribute("aria-checked", "true");
    await expect(page.getByRole("columnheader", { name: /Per game/ })).toBeVisible();
    await expect(page.getByRole("table").first().locator("caption")).toContainText("PPR fantasy points");
  });

  test("restores the view and week from a shared link", async ({ page }) => {
    await page.goto("/rankings/WR/?view=fantasy&week=1");

    await expect(page.getByRole("radio", { name: "Fantasy PPR" })).toHaveAttribute("aria-checked", "true");
    await expect(page.getByLabel("Week", { exact: true })).toHaveValue("1");
    await expect(page.getByText(/Week 1 ·/)).toBeVisible();
  });

  test("falls back to the latest week for a week that does not exist", async ({ page }) => {
    await page.goto("/rankings/QB/?week=99");

    await expect(page.getByLabel("Week", { exact: true })).toHaveValue("2");
  });

  test("changes the week", async ({ page }) => {
    await page.goto("/rankings/QB/");
    await page.getByLabel("Week", { exact: true }).selectOption("1");

    await expect(page).toHaveURL(/week=1/);
    await expect(page.getByText(/Week 1 ·/)).toBeVisible();
  });

  test("filters by name and by team", async ({ page }) => {
    await page.goto("/rankings/QB/");
    await page.getByLabel("Filter players by name").fill("allen");
    await expect(rows(page)).toHaveCount(1);
    await expect(rows(page).first()).toContainText("Josh Allen");

    await page.getByLabel("Filter players by name").fill("");
    await page.getByLabel("Team", { exact: true }).selectOption("BUF");
    for (const row of await rows(page).all()) {
      await expect(row).toContainText("BUF");
    }
  });

  test("says so when nothing matches", async ({ page }) => {
    await page.goto("/rankings/QB/");
    await page.getByLabel("Filter players by name").fill("zzzzzz");

    await expect(page.getByText("No players match")).toBeVisible();
  });

  test("sorts by a column and flips the order when clicked again", async ({ page }) => {
    await page.goto("/rankings/QB/");
    const names = async () =>
      (await rows(page).locator("td:nth-child(2) a .truncate").allInnerTexts()).map((text) => text.trim());

    await page.getByRole("button", { name: "Sort by Player" }).click();
    const ascending = await names();
    expect(ascending).toEqual([...ascending].sort((a, b) => a.localeCompare(b)));
    await expect(page.getByRole("columnheader", { name: /Player/ })).toHaveAttribute("aria-sort", "ascending");

    await page.getByRole("button", { name: "Sort by Player" }).click();
    expect(await names()).toEqual([...ascending].reverse());
    await expect(page.getByRole("columnheader", { name: /Player/ })).toHaveAttribute("aria-sort", "descending");
  });

  test("lists players without enough volume separately", async ({ page }) => {
    await page.goto("/rankings/QB/");
    const summary = page.getByText("Not ranked yet");

    await expect(summary).toBeVisible();
    await summary.click();

    await expect(page.getByText(/haven.t had enough attempts/)).toBeVisible();
  });

  test("shows an error with a retry when the data cannot be loaded", async ({ page }) => {
    await page.route("**/data/v1/rankings/**", (route) => route.abort());
    await page.goto("/rankings/QB/");

    const alert = page.getByRole("alert").filter({ hasText: "Couldn't load the rankings" });
    await expect(alert).toBeVisible();
    await expect(alert.getByRole("button", { name: "Try again" })).toBeVisible();
  });
});

test.describe("Player page", () => {
  test("opens from the rankings and shows rank history and the breakdown", async ({ page }) => {
    await page.goto("/rankings/QB/");
    await rows(page).first().getByRole("link", { name: "Josh Allen" }).click();

    await expect(page).toHaveURL(/\/player\/\?id=/);
    await expect(page.getByRole("heading", { level: 1, name: "Josh Allen" })).toBeVisible();
    await expect(page.getByRole("img", { name: /rank by week/ })).toBeVisible();
    await expect(page.getByRole("meter").first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Why this rank" })).toBeVisible();
  });

  test("offers the rank history as a table too", async ({ page }) => {
    await page.goto("/rankings/QB/");
    await rows(page).first().getByRole("link", { name: "Josh Allen" }).click();
    await page.getByText("View as a table").click();

    await expect(page.getByRole("table", { name: /weekly ranks/ })).toBeVisible();
  });

  test("explains when a player cannot be found", async ({ page }) => {
    await page.goto("/player/?id=does-not-exist");

    await expect(page.getByRole("alert").filter({ hasText: "couldn't find that player" })).toBeVisible();
  });

  test("asks for a player when none is chosen", async ({ page }) => {
    await page.goto("/player/");

    await expect(page.getByText("No player selected")).toBeVisible();
  });
});

test.describe("Search", () => {
  test("finds a player with the keyboard shortcut and jumps to them", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("heading", { level: 3, name: "Kickers" }).waitFor(); // hydrated and loaded
    await page.keyboard.press("/");

    const dialog = page.getByRole("dialog", { name: "Search players" });
    await expect(dialog).toBeVisible();
    await dialog.getByRole("textbox").fill("allen");
    await dialog.getByRole("link", { name: /Josh Allen/ }).click();

    await expect(page).toHaveURL(/\/player\/\?id=/);
    await expect(page.getByRole("heading", { level: 1, name: "Josh Allen" })).toBeVisible();
  });

  test("closes with Escape and reopens with Ctrl+K", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("heading", { level: 3, name: "Kickers" }).waitFor();
    await page.getByRole("button", { name: "Search players" }).click();
    const dialog = page.getByRole("dialog", { name: "Search players" });
    await expect(dialog).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();

    await page.keyboard.press("Control+k");
    await expect(dialog).toBeVisible();
  });

  test("says when nothing matches", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("heading", { level: 3, name: "Kickers" }).waitFor();
    await page.keyboard.press("/");
    await page.getByRole("dialog").getByRole("textbox").fill("qqqqq");

    await expect(page.getByText(/No players match/)).toBeVisible();
  });

  test("does not open while typing a slash in a text field", async ({ page }) => {
    await page.goto("/rankings/QB/");
    await page.getByLabel("Filter players by name").fill("a/b");

    await expect(page.getByRole("dialog", { name: "Search players" })).toBeHidden();
  });
});

test.describe("Methodology and About", () => {
  test("methodology shows the settings and the backtest", async ({ page }) => {
    await page.goto("/methodology/");

    await expect(
      page.getByRole("heading", { level: 1, name: "How the rankings work" }),
    ).toBeVisible();
    await expect(page.getByRole("heading", { name: "What counts at each position" })).toBeVisible();
    const backtest = page.getByRole("region", { name: "Backtest" });
    await expect(backtest.getByRole("row", { name: /^QB/ })).toBeVisible();
    await expect(backtest).toContainText("fantasy points per game");
  });

  test("about credits nflverse and links its license", async ({ page }) => {
    await page.goto("/about/");

    await expect(page.getByRole("link", { name: "nflverse" }).first()).toHaveAttribute(
      "href",
      "https://github.com/nflverse/nflverse-data",
    );
    await expect(page.getByRole("link", { name: /Creative Commons Attribution/ })).toBeVisible();
    await expect(page.getByText(/not affiliated with or endorsed by the NFL/).first()).toBeVisible();
  });

  test("the header reaches every section", async ({ page }) => {
    await page.goto("/");
    const nav = page.getByRole("navigation", { name: "Primary" });

    await nav.getByRole("link", { name: "Methodology" }).click();
    await expect(page).toHaveURL(/\/methodology\/$/);
    await nav.getByRole("link", { name: "About" }).click();
    await expect(page).toHaveURL(/\/about\/$/);
    await nav.getByRole("link", { name: "Rankings" }).click();
    await expect(page).toHaveURL(/\/rankings\/QB\/$/);
  });

  test("unknown pages get a helpful 404", async ({ page }) => {
    const response = await page.goto("/no-such-page/");

    expect(response?.status()).toBe(404);
    await expect(page.getByText("Page not found")).toBeVisible();
  });
});

test.describe("Author credit", () => {
  for (const path of ["/", "/rankings/QB/", "/about/"]) {
    test(`${path} says who built the site and links to their other projects`, async ({ page }) => {
      await page.goto(path);
      const footer = page.getByRole("contentinfo");

      await expect(footer.getByText("John Wasikye")).toBeVisible();
      const link = footer.getByRole("link", { name: /See my other projects/ });
      await expect(link).toBeVisible();
      await expect(link).toHaveAttribute("href", /.+/);
    });
  }
});

test.describe("Theme", () => {
  test("switches to dark, remembers the choice, and switches back", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Switch to dark theme" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

    await page.getByRole("button", { name: "Switch to light theme" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  });

  test("follows the system setting when there is no saved choice", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/");

    await expect(page.getByRole("button", { name: "Switch to light theme" })).toBeVisible();
  });
});

test.describe("Freshness", () => {
  test("shows no warning when the data is fresh", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText(/2026 season/)).toBeVisible();

    await expect(page.getByText(/were last updated/)).toHaveCount(0);
  });

  test("warns when the data is more than a day and a half old", async ({ page }) => {
    await page.route("**/data/v1/meta.json", async (route) => {
      const response = await route.fetch();
      const meta = await response.json();
      meta.generated_at = new Date(Date.now() - 3 * 24 * 3600 * 1000).toISOString();
      await route.fulfill({ response, json: meta });
    });
    await page.goto("/");

    await expect(page.getByText(/were last updated 3 days ago/)).toBeVisible();
  });
});
