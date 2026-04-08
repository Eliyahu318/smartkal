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

  test("duplicates page shows empty state when there are no duplicates", async ({
    authenticatedPage: page,
  }) => {
    // Navigate directly to /duplicates — should show empty state for a fresh user
    await page.goto("/duplicates");
    await expect(
      page.getByRole("heading", { name: "איחוד פריטים כפולים" })
    ).toBeVisible();
    await expect(page.getByText("אין כפילויות ברשימה שלך")).toBeVisible({
      timeout: 10_000,
    });
  });

  test("manually-added near-duplicate items can be merged via /duplicates page", async ({
    authenticatedPage: page,
  }) => {
    // Add three near-duplicate items
    await page.getByRole("button", { name: "הוסף מוצר" }).click();
    await page.getByTestId("add-item-input").fill("עגבניות שרי");
    await page.getByTestId("add-item-input").press("Enter");
    await expect(page.getByTestId("add-item-input")).toHaveValue("", {
      timeout: 10_000,
    });

    await page.getByTestId("add-item-input").fill("עגבניות שרי פרימיום");
    await page.getByTestId("add-item-input").press("Enter");
    await expect(page.getByTestId("add-item-input")).toHaveValue("", {
      timeout: 10_000,
    });

    await page.getByTestId("add-item-input").fill("עגבניות שרי עגול");
    await page.getByTestId("add-item-input").press("Enter");
    await expect(page.getByTestId("add-item-input")).toHaveValue("", {
      timeout: 10_000,
    });

    // Reload the list once so the lazy backfill runs and writes canonical_key
    await page.reload();
    await page.waitForURL("**/list");

    // Wait for the duplicates badge to appear in the header
    await expect(
      page.getByText(/נמצאו .* קבוצות כפילויות/)
    ).toBeVisible({ timeout: 10_000 });

    // Click the badge → navigates to /duplicates
    await page.getByText(/נמצאו .* קבוצות כפילויות/).click();
    await page.waitForURL("**/duplicates");

    // Confirm merge by clicking the primary CTA in the first group card
    await page.getByRole("button", { name: "אחד פריטים אלה" }).first().click();

    // Wait for the empty state to appear after the merge succeeds
    await expect(page.getByText("אין כפילויות ברשימה שלך")).toBeVisible({
      timeout: 10_000,
    });

    // Navigate back to /list and verify only one of the three items remains
    await page.goto("/list");
    const cherryTomatoItems = page.locator('[class*="leading-tight"]', {
      hasText: "עגבניות שרי",
    });
    await expect(cherryTomatoItems).toHaveCount(1, { timeout: 10_000 });
  });
});
