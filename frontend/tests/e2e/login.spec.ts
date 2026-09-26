import { test, expect } from "@playwright/test";
import { E2E_EMAIL, E2E_EMAIL_AVAILABLE, E2E_PASSWORD_AVAILABLE, loginAs } from "./helpers";

test.describe("login", () => {
  test("renders the login form", async ({ page }) => {
    await page.goto("/login", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("textbox", { name: "Email" })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Password" })).toBeVisible();
    await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible();
  });

  test("empty submit does not navigate", async ({ page }) => {
    await page.goto("/login", { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: /sign in/i }).click();
    await page.waitForTimeout(1_000);
    await expect(page).toHaveURL(/\/login/);
  });

  test("invalid credentials show an error", async ({ page }) => {
    test.skip(!E2E_EMAIL_AVAILABLE, "E2E_EMAIL not set");
    test.setTimeout(90_000);
    await page.goto("/login", { waitUntil: "domcontentloaded" });
    await page.getByRole("textbox", { name: "Email" }).fill(E2E_EMAIL);
    await page.getByRole("textbox", { name: "Password" }).fill("definitely-wrong-password");
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page.getByRole("alert")).toBeVisible({ timeout: 30_000 });
    await expect(page).toHaveURL(/\/login/);
  });

  test("valid credentials land on the dashboard", async ({ page }) => {
    test.skip(!E2E_PASSWORD_AVAILABLE || !E2E_EMAIL_AVAILABLE, "E2E_PASSWORD or E2E_EMAIL not set");
    await loginAs(page);
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 30_000 });
  });
});