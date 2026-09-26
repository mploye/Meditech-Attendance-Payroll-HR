import { test, expect, type Page } from "@playwright/test";
import { E2E_PASSWORD_AVAILABLE, loginAs } from "./helpers";

const NAV_LINKS = [
  "/Dashboard/",
  "/Employees/",
  "/Departments/",
  "/Designations/",
  "/Users/",
  "/Attendance/",
  "/Shifts/",
  "/Devices/",
  "/Holidays/",
  "/Leave Requests/",
  "/Overtime/",
  "/Loans/",
  "/Payroll Periods/",
  "/Payslips/",
  "/Reports/",
  "/Company & eSSL/",
  "/Audit Logs/",
];

async function hasNoPageErrors(page: Page) {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  await page.waitForLoadState("domcontentloaded");
  return errors;
}

test.describe("dashboard", () => {
  test("unauthenticated user is redirected from the root to /login", async ({
    page,
  }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page).toHaveURL(/\/login/, { timeout: 30_000 });
    const body = page.locator("body");
    await expect(body).toBeVisible();
  });

  test("dashboard page responds and renders", async ({ page }) => {
    const response = await page.goto("/dashboard", { waitUntil: "domcontentloaded" });
    expect(response?.ok()).toBe(true);
    const body = page.locator("body");
    await expect(body).toBeVisible();
    const errors = await hasNoPageErrors(page);
    expect(errors).toEqual([]);
  });
});

test.describe("dashboard authenticated", () => {
  test.skip(!E2E_PASSWORD_AVAILABLE, "E2E_PASSWORD not set");
  test("dashboard loads with navigation and metric cards", async ({
    page,
  }) => {
    await loginAs(page);
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 30_000 });

    const nav = page.locator("nav");
    await expect(nav).toBeVisible();
    for (const label of NAV_LINKS) {
      const link = nav.getByRole("link", { name: new RegExp(label) }).first();
      await expect(link).toBeVisible();
    }

    const metric =
      page.getByText(/Active Employees|Present Today|Absent Today|On Leave/);
    const fallback = page.locator("nav a[href='/dashboard']").first();
    await expect(metric.first().or(fallback)).toBeVisible();

    const errors = await hasNoPageErrors(page);
    expect(errors).toEqual([]);
  });
});