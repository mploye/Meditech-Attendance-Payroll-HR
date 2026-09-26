import { test, expect, type Page } from "@playwright/test";
import { E2E_PASSWORD_AVAILABLE, loginAs } from "./helpers";

async function expectNoHorizontalOverflow(page: Page) {
  await page.waitForLoadState("domcontentloaded");
  const overflow = await page.evaluate(() => {
    const doc = document.documentElement;
    return doc.scrollWidth - doc.clientWidth > 1;
  });
  expect(overflow).toBe(false);
}

test.describe("responsive", () => {
  for (const path of ["/login", "/dashboard"]) {
    test(`no horizontal overflow on ${path}`, async ({ page }) => {
      const response = await page.goto(path);
      expect(response?.ok()).toBe(true);
      await expectNoHorizontalOverflow(page);
    });
  }
});

test.describe("responsive authenticated", () => {
  test.skip(!E2E_PASSWORD_AVAILABLE, "E2E_PASSWORD not set");

  test("no horizontal overflow on dashboard after login", async ({ page }) => {
    await loginAs(page);
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 30_000 });
    await expectNoHorizontalOverflow(page);
  });
});