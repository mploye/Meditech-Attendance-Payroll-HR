import { test, expect } from "@playwright/test";
import { E2E_PASSWORD_AVAILABLE, loginAs } from "./helpers";

const ROUTES = [
  ["/dashboard", "/Dashboard/"],
  ["/employees", "/Employees/"],
  ["/departments", "/Departments/"],
  ["/designations", "/Designations/"],
  ["/users", "/Users/"],
  ["/attendance", "/Attendance/"],
  ["/shifts", "/Shifts/"],
  ["/devices", "/Devices/"],
  ["/holidays", "/Holidays/"],
  ["/leaves", "/Leave Requests/"],
  ["/overtime", "/Overtime/"],
  ["/loans", "/Loans/"],
  ["/payroll", "/Payroll Periods/"],
  ["/payslips", "/Payslips/"],
  ["/reports", "/Reports/"],
  ["/settings", "/Company & eSSL/"],
  ["/audit", "/Audit Logs/"],
] as const;

test.describe("navigation direct", () => {
  for (const [route] of ROUTES) {
    test(`route ${route} responds and renders`, async ({ page }) => {
      const response = await page.goto(route);
      expect(response?.ok()).toBe(true);
      const body = page.locator("body");
      await expect(body).toBeVisible();
    });
  }
});

test.describe("navigation click-through", () => {
  test.skip(!E2E_PASSWORD_AVAILABLE, "E2E_PASSWORD not set");
  test.skip(({ isMobile }) => isMobile, "desktop only");

  test("shell nav links navigate to each route", async ({ page }) => {
    await loginAs(page);
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 30_000 });

    const nav = page.locator("nav");
    await expect(nav).toBeVisible();

    for (const [route, label] of ROUTES) {
      const link = nav.getByRole("link", { name: new RegExp(label) }).first();
      await link.click();
      await expect(page).toHaveURL(new RegExp(`${route}$`), { timeout: 30_000 });
      const body = page.locator("body");
      await expect(body).toBeVisible();
    }
  });
});