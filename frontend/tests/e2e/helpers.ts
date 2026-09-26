import { type Page, expect } from "@playwright/test";

export const E2E_PASSWORD = process.env.E2E_PASSWORD ?? "";
export const E2E_PASSWORD_AVAILABLE = E2E_PASSWORD.length > 0;

export const E2E_EMAIL = process.env.E2E_EMAIL ?? "";
export const E2E_EMAIL_AVAILABLE = E2E_EMAIL.length > 0;

export async function loginAs(page: Page, password = E2E_PASSWORD, email = E2E_EMAIL): Promise<void> {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.getByRole("textbox", { name: "Email" }).fill(email);
  await page.getByRole("textbox", { name: "Password" }).fill(password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 30_000 });
}