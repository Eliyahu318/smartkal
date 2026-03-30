import path from "path";
import { test, expect } from "./fixtures/auth.fixture";
import receiptFixture from "./fixtures/receipt-upload-response.json";

const TEST_PDF_PATH = path.resolve(__dirname, "fixtures/test-receipt.pdf");

/** Mock the upload endpoint to avoid calling Claude AI. */
async function mockUploadEndpoint(page: import("@playwright/test").Page) {
  await page.route("**/api/v1/receipts/upload", async (route) => {
    // Simulate a short processing delay
    await new Promise((r) => setTimeout(r, 300));
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify(receiptFixture),
    });
  });
}

/** Navigate to receipts page via bottom nav. */
async function goToReceipts(page: import("@playwright/test").Page) {
  await page.getByTestId("nav-receipts").click();
  await page.waitForURL("**/receipts");
}

/** Upload a test PDF file via the hidden file input. */
async function uploadTestPdf(page: import("@playwright/test").Page) {
  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles(TEST_PDF_PATH);
}

test.describe.configure({ mode: "serial" });

test.describe("Receipts", () => {
  test("shows upload zone", async ({ authenticatedPage: page }) => {
    await goToReceipts(page);

    await expect(
      page.getByText("גרור קובץ PDF לכאן או לחץ לבחירה")
    ).toBeVisible();
    await expect(page.getByTestId("receipt-dropzone")).toBeVisible();
  });

  test("shows empty history for new user", async ({
    authenticatedPage: page,
  }) => {
    await goToReceipts(page);

    await expect(
      page.getByText("עדיין אין קבלות — העלו את הקבלה הראשונה!")
    ).toBeVisible({ timeout: 10_000 });
  });

  test("uploading a receipt shows loading then results", async ({
    authenticatedPage: page,
  }) => {
    await mockUploadEndpoint(page);
    await goToReceipts(page);

    await uploadTestPdf(page);

    // Loading state should appear
    await expect(page.getByText("מנתח את הקבלה...")).toBeVisible();

    // After mock resolves — results should show store name
    await expect(page.getByText("רמי לוי")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("receipt-save")).toBeVisible();
  });

  test("receipt results show match summary", async ({
    authenticatedPage: page,
  }) => {
    await mockUploadEndpoint(page);
    await goToReceipts(page);
    await uploadTestPdf(page);

    // Wait for results
    await expect(page.getByText("רמי לוי")).toBeVisible({ timeout: 10_000 });

    // Match summary card
    await expect(page.getByText("פריטים הושלמו ברשימה")).toBeVisible();

    // Unmatched items warning
    await expect(page.getByText("מוצרים לא זוהו")).toBeVisible();
  });

  test("can delete a purchase from results", async ({
    authenticatedPage: page,
  }) => {
    await mockUploadEndpoint(page);
    await goToReceipts(page);
    await uploadTestPdf(page);

    await expect(page.getByText("רמי לוי")).toBeVisible({ timeout: 10_000 });

    // Should have 2 items initially (from fixture)
    await expect(page.getByText("פריטים (2)")).toBeVisible();

    // Delete one item
    await page
      .getByRole("button", { name: "מחק פריט" })
      .first()
      .click();

    // Should now show 1 item
    await expect(page.getByText("פריטים (1)")).toBeVisible();
  });

  test("save navigates to list", async ({ authenticatedPage: page }) => {
    await mockUploadEndpoint(page);
    await goToReceipts(page);
    await uploadTestPdf(page);

    await expect(page.getByText("רמי לוי")).toBeVisible({ timeout: 10_000 });

    // Mock the history fetch that happens during save
    await page.route("**/api/v1/receipts?*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ receipts: [], total: 0, page: 1, page_size: 50 }),
      });
    });

    await page.getByTestId("receipt-save").click();

    await page.waitForURL("**/list", { timeout: 10_000 });
    await expect(page).toHaveURL(/\/list$/);
  });

  test("new upload resets to upload view", async ({
    authenticatedPage: page,
  }) => {
    await mockUploadEndpoint(page);
    await goToReceipts(page);
    await uploadTestPdf(page);

    await expect(page.getByText("רמי לוי")).toBeVisible({ timeout: 10_000 });

    // Click "new upload" link
    await page.getByText("העלאה חדשה").click();

    // Should show upload zone again
    await expect(page.getByTestId("receipt-dropzone")).toBeVisible();
    await expect(
      page.getByText("גרור קובץ PDF לכאן או לחץ לבחירה")
    ).toBeVisible();
  });
});
