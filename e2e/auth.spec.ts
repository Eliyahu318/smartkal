import { test, expect } from "@playwright/test";
import { test as authTest, expect as authExpect } from "./fixtures/auth.fixture";

test.describe("Authentication", () => {
  test("shows onboarding with guest login button", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByRole("heading", { name: "סמארט-כל" })).toBeVisible();
    await expect(
      page.getByRole("button", { name: "כניסה כאורח" })
    ).toBeVisible();
  });

  test("guest login shows value cards", async ({ page }) => {
    await page.goto("/");

    await page.getByRole("button", { name: "כניסה כאורח" }).click();

    // Should transition to step 2 — first value card
    await expect(
      page.getByText("רשימה שמרעננת את עצמה")
    ).toBeVisible({ timeout: 10_000 });
  });

  test("can skip value cards", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "כניסה כאורח" }).click();
    await expect(page.getByText("רשימה שמרעננת את עצמה")).toBeVisible({
      timeout: 10_000,
    });

    await page.getByRole("button", { name: "דלג" }).click();

    await expect(
      page.getByRole("heading", { name: "מה תרצה לעשות?" })
    ).toBeVisible();
  });

  test("completing onboarding via list navigates to /list", async ({
    page,
  }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "כניסה כאורח" }).click();
    await expect(page.getByText("רשימה שמרעננת את עצמה")).toBeVisible({
      timeout: 10_000,
    });
    await page.getByRole("button", { name: "דלג" }).click();

    await page.getByText("יצירת רשימה").click();

    await page.waitForURL("**/list");
    await expect(page).toHaveURL(/\/list$/);
  });

  test("completing onboarding via receipts navigates to /receipts", async ({
    page,
  }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "כניסה כאורח" }).click();
    await expect(page.getByText("רשימה שמרעננת את עצמה")).toBeVisible({
      timeout: 10_000,
    });
    await page.getByRole("button", { name: "דלג" }).click();

    await page.getByText("העלאת קבלה").click();

    await page.waitForURL("**/receipts");
    await expect(page).toHaveURL(/\/receipts$/);
  });

  test("value cards carousel navigation works", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "כניסה כאורח" }).click();
    await expect(page.getByText("רשימה שמרעננת את עצמה")).toBeVisible({
      timeout: 10_000,
    });

    // Navigate to second card
    await page.getByRole("button", { name: "הבא" }).click();
    await expect(page.getByText("העלה קבלה — תראה איפה זול")).toBeVisible();

    // Navigate to third (last) card — "המשך" button should appear
    await page.getByRole("button", { name: "הבא" }).click();
    await expect(page.getByText("ככל שתשתמש — ככה חכמה יותר")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "המשך" })
    ).toBeVisible();
  });
});

// Uses authenticatedPage fixture — user already logged in
authTest.describe("Returning user", () => {
  authTest(
    "authenticated user is redirected past onboarding",
    async ({ authenticatedPage }) => {
      // Already on /list from fixture — navigate to root
      await authenticatedPage.goto("/");

      // Should redirect back to /list, not onboarding
      await authenticatedPage.waitForURL("**/list");
      await authExpect(authenticatedPage).toHaveURL(/\/list$/);
    }
  );
});
