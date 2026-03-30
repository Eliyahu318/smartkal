import { test, expect } from "./fixtures/auth.fixture";

test.describe.configure({ mode: "serial" });

test.describe("Shopping List", () => {
  test("shows empty list for new user", async ({ authenticatedPage: page }) => {
    await expect(page.getByTestId("list-empty-state")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "הוסף מוצר" })
    ).toBeVisible();
  });

  test("can add an item to the list", async ({ authenticatedPage: page }) => {
    // Open add input
    await page.getByRole("button", { name: "הוסף מוצר" }).click();
    await expect(page.getByTestId("add-item-input")).toBeVisible();

    // Type item name and submit
    await page.getByTestId("add-item-input").fill("חלב");
    await page.getByTestId("add-item-input").press("Enter");

    // Wait for input to clear (POST succeeded) then verify item in list
    await expect(page.getByTestId("add-item-input")).toHaveValue("", {
      timeout: 10_000,
    });
    await expect(
      page.locator('[class*="leading-tight"]', { hasText: "חלב" })
    ).toBeVisible({ timeout: 10_000 });
  });

  test("can add multiple items", async ({ authenticatedPage: page }) => {
    // Open add input
    await page.getByRole("button", { name: "הוסף מוצר" }).click();

    // Add first item
    await page.getByTestId("add-item-input").fill("חלב");
    await page.getByTestId("add-item-input").press("Enter");
    await expect(page.getByTestId("add-item-input")).toHaveValue("", {
      timeout: 10_000,
    });

    // Input should still be open — add second item
    await page.getByTestId("add-item-input").fill("לחם");
    await page.getByTestId("add-item-input").press("Enter");
    await expect(page.getByTestId("add-item-input")).toHaveValue("", {
      timeout: 10_000,
    });

    // Both items visible in list
    const listItems = page.locator('[class*="leading-tight"]');
    await expect(listItems.filter({ hasText: "חלב" })).toBeVisible();
    await expect(listItems.filter({ hasText: "לחם" })).toBeVisible();
  });

  test("can mark item as completed", async ({ authenticatedPage: page }) => {
    // Add an item
    await page.getByRole("button", { name: "הוסף מוצר" }).click();
    await page.getByTestId("add-item-input").fill("חלב");
    await page.getByTestId("add-item-input").press("Enter");
    await expect(page.getByTestId("add-item-input")).toHaveValue("", {
      timeout: 10_000,
    });

    // Close input to avoid interference
    await page.getByRole("button", { name: "סגור" }).click();

    // Wait for the toggle button to be present (item rendered in list)
    const toggleBtn = page.getByRole("button", { name: "סמן כהושלם" });
    await toggleBtn.waitFor({ state: "visible", timeout: 10_000 });

    // Toggle item to completed
    await toggleBtn.click();

    // Completed section should appear (wait for list refresh after animation)
    await expect(page.getByTestId("completed-toggle")).toBeVisible({
      timeout: 15_000,
    });
  });

  test("can reactivate completed item", async ({
    authenticatedPage: page,
  }) => {
    // Add and complete an item
    await page.getByRole("button", { name: "הוסף מוצר" }).click();
    await page.getByTestId("add-item-input").fill("חלב");
    await page.getByTestId("add-item-input").press("Enter");
    await expect(page.getByTestId("add-item-input")).toHaveValue("", {
      timeout: 10_000,
    });
    await page.getByRole("button", { name: "סגור" }).click();

    await page
      .getByRole("button", { name: "סמן כהושלם" })
      .click({ timeout: 10_000 });
    await expect(page.getByTestId("completed-toggle")).toBeVisible({
      timeout: 10_000,
    });

    // Expand completed section
    await page.getByTestId("completed-toggle").click();

    // Reactivate the item
    await page
      .getByRole("button", { name: "הפעל מחדש" })
      .click({ timeout: 10_000 });

    // Item should return to active list
    await expect(
      page.locator('[class*="leading-tight"]', { hasText: "חלב" })
    ).toBeVisible({ timeout: 10_000 });
  });

  test("can close add-item input", async ({ authenticatedPage: page }) => {
    // Open FAB
    await page.getByRole("button", { name: "הוסף מוצר" }).click();
    await expect(page.getByTestId("add-item-input")).toBeVisible();

    // Close it
    await page.getByRole("button", { name: "סגור" }).click();

    // FAB should reappear
    await expect(
      page.getByRole("button", { name: "הוסף מוצר" })
    ).toBeVisible();
  });

  test("can navigate to receipts via bottom nav", async ({
    authenticatedPage: page,
  }) => {
    await page.getByTestId("nav-receipts").click();

    await page.waitForURL("**/receipts");
    await expect(
      page.getByRole("heading", { name: "קבלות", exact: true })
    ).toBeVisible();
  });
});
