import { expect, type Page } from "@playwright/test";

/**
 * Open the search dialog with the "/" shortcut.
 *
 * A heading that came from the pre-rendered HTML can be on screen before the page's key listener
 * is attached, and a key pressed in that gap is lost. Pressing again until the dialog is up avoids
 * that without a fixed wait. The key is not pressed again once the dialog is open, so it never
 * types a "/" into the search box.
 */
export async function openSearchWithSlash(page: Page) {
  const dialog = page.getByRole("dialog", { name: "Search players" });
  await expect(async () => {
    await page.keyboard.press("/");
    await expect(dialog).toBeVisible({ timeout: 1500 });
  }).toPass({ timeout: 15_000 });
  return dialog;
}
