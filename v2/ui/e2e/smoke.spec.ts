import { test, expect } from "@playwright/test";

test.describe("PLynx UI Smoke Test", () => {
  test("Task 6.1: renders navbar and navigates between Runs and Workflows", async ({ page }) => {
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

  test("Task 6.2 & 6.3: opens Run inputs form, launches workflow, displays Stepper view", async ({ page }) => {
    await page.goto("/#/workflows");
    await expect(page.getByRole("heading", { name: "Workflows" })).toBeVisible();

    // Click "Run" on the foo_or_woo workflow
    await page.getByRole("button", { name: "Run", exact: true }).click();
    await expect(page).toHaveURL(/.*#\/workflows\/examples\/workflows\/foo_or_woo\.yaml/);

    // Form is displayed
    await expect(page.getByRole("heading", { name: "foo_or_woo" })).toBeVisible();
    await expect(page.getByText("Path: examples/workflows/foo_or_woo.yaml")).toBeVisible();
    await expect(page.getByText("Force re-run (disable cache lookup:")).toBeVisible();

    // Launch the run
    await page.getByRole("button", { name: "Start Run" }).click();

    // Navigates to /runs/<run_id>
    await expect(page).toHaveURL(/.*#\/runs\/[0-9a-f-]+/);
    await expect(page.getByText("Workflow: examples/workflows/foo_or_woo.yaml")).toBeVisible();

    // Task 6.3: Stepper view elements are visible
    await expect(page.getByText("Workflow Stages (Stepper)")).toBeVisible();
    await expect(page.getByText("Overall Progress")).toBeVisible();
    await expect(page.getByText("1. Ask")).toBeVisible();
    await expect(page.getByText("pick", { exact: true })).toBeVisible();
  });
});
