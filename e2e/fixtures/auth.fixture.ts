import { test as base, type Page } from "@playwright/test";

type AuthFixtures = {
  authenticatedPage: Page;
};

export const test = base.extend<AuthFixtures>({
  authenticatedPage: async ({ page }, use) => {
    // Step 1: Navigate to app → onboarding
    await page.goto("/");

    // Step 2: Guest login
    await page.getByRole("button", { name: "כניסה כאורח" }).click();

    // Step 3: Wait for value cards to appear, then skip
    await page.getByText("רשימה שמרעננת את עצמה").waitFor({ timeout: 10_000 });
    await page.getByRole("button", { name: "דלג" }).click();

    // Step 4: Choose "create list" action
    await page.getByText("יצירת רשימה").click();

    // Now authenticated and on /list
    await page.waitForURL("**/list");

    await use(page);
  },
});

export { expect } from "@playwright/test";
