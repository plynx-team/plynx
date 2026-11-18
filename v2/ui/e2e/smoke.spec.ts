import { test, expect } from "@playwright/test";

test.describe("PLynx UI App Shell (Task 6.1)", () => {
  test("renders navbar and navigates between Runs and Workflows", async ({ page }) => {
    // 1. Visit root
    await page.goto("/");

    // 2. Navbar is rendered
    await expect(page.locator("header")).toBeVisible();
    await expect(page.getByRole("link", { name: "PLynx v2.0" })).toBeVisible();

    // 3. Default view is Runs
    await expect(page.getByRole("heading", { name: "Runs" })).toBeVisible();
    await expect(page.getByPlaceholder("Filter by run ID or workflow...")).toBeVisible();

    // 4. Click Workflows nav link
    await page.getByRole("link", { name: "Workflows" }).click();
    await expect(page).toHaveURL(/.*#\/workflows/);
    await expect(page.getByRole("heading", { name: "Workflows" })).toBeVisible();

    // 5. Check that workflows discovered in workspace are displayed
    await expect(page.getByText("examples/workflows/foo_or_woo.yaml")).toBeVisible();

    // 6. Click "Runs" nav link to return
    await page.getByRole("link", { name: "Runs" }).click();
    await expect(page).toHaveURL(/.*#\/runs/);
    await expect(page.getByRole("heading", { name: "Runs" })).toBeVisible();
  });
});
