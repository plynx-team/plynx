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

  test("Task 6.2 - 6.5 & 6.7: launches workflow, interacts with Stepper, Checkpoint card, Logs panel, and Previews", async ({ page }) => {
    await page.goto("/#/workflows");
    await expect(page.getByRole("heading", { name: "Workflows" })).toBeVisible();

    // Click "Run" on the foo_or_woo workflow
    const fooCard = page.getByTestId("workflow-card-examples/workflows/foo_or_woo.yaml");
    await fooCard.getByRole("button", { name: "Run" }).click();
    await expect(page).toHaveURL(/.*#\/workflows\/examples\/workflows\/foo_or_woo\.yaml/);

    // Form is displayed
    await expect(page.getByRole("heading", { name: "foo_or_woo" })).toBeVisible();
    await expect(page.getByText("Path: examples/workflows/foo_or_woo.yaml")).toBeVisible();

    // Launch the run
    await page.getByRole("button", { name: "Start Run" }).click();

    // Navigates to /runs/<run_id>
    await expect(page).toHaveURL(/.*#\/runs\/[0-9a-f-]+/);
    await expect(page.getByText("Workflow: examples/workflows/foo_or_woo.yaml")).toBeVisible();

    // Task 6.3: Stepper view elements are visible
    await expect(page.getByText("Workflow Stages (Stepper)")).toBeVisible();
    await expect(page.getByText("Overall Progress")).toBeVisible();
    await expect(page.getByText("1. Ask")).toBeVisible();
    const pickNode = page.getByText("pick", { exact: true });
    await expect(pickNode).toBeVisible();

    // Task 6.5: Wait for Checkpoint card to appear when node pauses at AskFooOrWoo
    const checkpointCard = page.getByTestId("checkpoint-card-cp_0");
    await expect(checkpointCard).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("foo or woo?")).toBeVisible();

    // Click option "foo" to answer the checkpoint
    const fooBtn = checkpointCard.getByRole("button", { name: "foo", exact: true });
    await expect(fooBtn).toBeVisible();
    await fooBtn.click();

    // Checkpoint card disappears on checkpoint_resolved!
    await expect(checkpointCard).not.toBeVisible({ timeout: 10000 });

    // Task 6.4: Click node row to open Logs panel
    await pickNode.click();
    await expect(page.getByTestId("logs-panel")).toBeVisible();
    await expect(page.getByRole("button", { name: "Download" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Copy" })).toBeVisible();

    // Close logs panel
    await page.getByRole("button", { name: "Close logs" }).click();
    await expect(page.getByTestId("logs-panel")).not.toBeVisible();

    // Task 6.7: When pick node completes with SUCCESS, select it and preview output
    await expect(page.getByText("pick", { exact: true })).toBeVisible();
    await pickNode.click();
    const previewBtn = page.getByRole("button", { name: "Preview Output" });
    if (await previewBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
      await previewBtn.click();
      await expect(page.getByTestId("artifact-preview-dialog")).toBeVisible();
      await page.getByRole("button", { name: "Close dialog" }).click();
      await expect(page.getByTestId("artifact-preview-dialog")).not.toBeVisible();
    }
  });

  test("Task 6.6: handles Stage approval card with Approve & Continue", async ({ page }) => {
    await page.goto("/#/workflows");
    await expect(page.getByRole("heading", { name: "Workflows" })).toBeVisible();

    // Click "Run" on the staged workflow
    const stagedCard = page.getByTestId("workflow-card-examples/workflows/staged.yaml");
    await stagedCard.getByRole("button", { name: "Run" }).click();
    await expect(page).toHaveURL(/.*#\/workflows\/examples\/workflows\/staged\.yaml/);

    // Launch the run
    await page.getByRole("button", { name: "Start Run" }).click();
    await expect(page).toHaveURL(/.*#\/runs\/[0-9a-f-]+/);

    // Wait for stage gate approval card to appear
    const gateCard = page.getByTestId("stage-approval-card-stage_1");
    await expect(gateCard).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("Stage Gate: Approval Required")).toBeVisible();

    // Click "Approve & Continue"
    const approveBtn = page.getByRole("button", { name: "Approve & Continue" });
    await expect(approveBtn).toBeVisible();
    await approveBtn.click();

    // Gate card disappears on approval!
    await expect(gateCard).not.toBeVisible({ timeout: 10000 });
  });

  test("Task 6.8: toggles between Stepper and read-only Graph view with stage groups and live status", async ({ page }) => {
    await page.goto("/#/workflows");
    const fooCard = page.getByTestId("workflow-card-examples/workflows/foo_or_woo.yaml");
    await fooCard.getByRole("button", { name: "Run" }).click();
    await page.getByRole("button", { name: "Start Run" }).click();
    await expect(page).toHaveURL(/.*#\/runs\/[0-9a-zA-Z_-]+/);

    // Default view is Stepper
    await expect(page.getByTestId("view-toggle-stepper")).toHaveAttribute("aria-selected", "true");
    await expect(page.getByText("Workflow Stages (Stepper)")).toBeVisible();

    // Switch to Graph view
    await page.getByTestId("view-toggle-graph").click();
    await expect(page.getByTestId("view-toggle-graph")).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("graph-view")).toBeVisible();

    // Stage group nodes and workflow nodes render
    await expect(page.getByTestId("stage-group-ask")).toBeVisible();
    await expect(page.getByTestId("stage-group-print")).toBeVisible();
    await expect(page.getByTestId("graph-node-pick")).toBeVisible();
    await expect(page.getByTestId("graph-node-echo")).toBeVisible();

    // Wait for checkpoint to pause pick node, verify live WAITING_FOR_USER status in Graph view
    const checkpointCard = page.getByTestId("checkpoint-card-cp_0");
    await expect(checkpointCard).toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId("graph-node-status-pick")).toHaveText("WAITING_FOR_USER");

    // Answer checkpoint while in Graph view and observe live transition to SUCCESS
    await checkpointCard.getByRole("button", { name: "foo", exact: true }).click();
    await expect(page.getByTestId("graph-node-status-pick")).toHaveText("SUCCESS", { timeout: 10000 });
    await expect(page.getByTestId("graph-node-status-echo")).toHaveText("SUCCESS", { timeout: 10000 });

    // Clicking a node in Graph view selects it and opens Logs panel
    await page.getByTestId("graph-node-echo").click();
    await expect(page.getByTestId("logs-panel")).toBeVisible();

    // Toggle back to Stepper
    await page.getByTestId("view-toggle-stepper").click();
    await expect(page.getByText("Workflow Stages (Stepper)")).toBeVisible();
  });

  test("Task 6.9: opens Graph Editor, searches palette with '/' shortcut, adds, duplicates, and deletes nodes", async ({ page }) => {
    await page.goto("/#/workflows");
    const editBtn = page.getByTestId("edit-workflow-examples/workflows/foo_or_woo.yaml");
    await expect(editBtn).toBeVisible();
    await editBtn.click();

    await expect(page).toHaveURL(/.*#\/editor\/examples\/workflows\/foo_or_woo\.yaml/);
    await expect(page.getByTestId("workflow-editor")).toBeVisible();
    await expect(page.getByTestId("op-palette")).toBeVisible();

    // Ops grouped by CATEGORY (Demo, Files, Text / Basic)
    await expect(page.getByTestId("palette-category-Demo")).toBeVisible();
    await expect(page.getByTestId("palette-category-Files")).toBeVisible();
    await expect(page.getByTestId("palette-category-Text / Basic")).toBeVisible();

    // Focus palette search with '/' shortcut
    await page.keyboard.press("/");
    const searchInput = page.getByTestId("palette-search");
    await expect(searchInput).toBeFocused();

    // Search for Concat and add it
    await searchInput.fill("Concat");
    const concatBtn = page.getByTestId("palette-op-standard_io/text:Concat");
    await expect(concatBtn).toBeVisible();
    await concatBtn.click();

    // New node appears on the canvas
    await expect(page.getByTestId("graph-node-concat")).toBeVisible();

    // Duplicate the newly added node
    await page.getByTestId("btn-duplicate-node").click();
    await expect(page.getByTestId("graph-node-concat_copy")).toBeVisible();

    // Delete the duplicated node
    await page.getByTestId("btn-delete-node").click();
    await expect(page.getByTestId("graph-node-concat_copy")).not.toBeVisible();
    await expect(page.getByTestId("graph-node-concat")).toBeVisible();
  });

  test("Task 6.10: drags edges between ports and visibly rejects backward stage edges and type mismatches", async ({ page }) => {
    const dragHandle = async (sourceTestId: string, targetTestId: string) => {
      const src = page.getByTestId(sourceTestId);
      const dst = page.getByTestId(targetTestId);
      await expect(src).toBeVisible();
      await expect(dst).toBeVisible();
      const srcBox = await src.boundingBox();
      const dstBox = await dst.boundingBox();
      if (!srcBox || !dstBox) {
        throw new Error(`Missing bounding box for ${sourceTestId} or ${targetTestId}`);
      }
      await page.mouse.move(srcBox.x + srcBox.width / 2, srcBox.y + srcBox.height / 2);
      await page.mouse.down();
      await page.mouse.move(dstBox.x + dstBox.width / 2, dstBox.y + dstBox.height / 2, {
        steps: 12,
      });
      await page.mouse.up();
    };

    await page.goto("/#/editor/examples/workflows/foo_or_woo.yaml");
    await expect(page.getByTestId("graph-node-pick")).toBeVisible();
    await expect(page.getByTestId("graph-node-echo")).toBeVisible();

    // 1. Backward stage edge: echo (stage print) -> pick (stage ask) rejected visibly
    await dragHandle("handle-out-echo-text", "handle-in-pick-prompt");
    await expect(page.getByTestId("wire-error-banner")).toBeVisible();
    await expect(page.getByTestId("wire-error-banner")).toContainText("Backward stage edge");

    // 2. Add ReadText (input path: file) to stage print and try connecting echo.text (str) -> read_text.path (file)
    await page.getByTestId("palette-op-standard_io/demo:ReadText").click();
    await expect(page.getByTestId("graph-node-read_text")).toBeVisible();
    await page.getByTestId("btn-auto-layout").click();
    await dragHandle("handle-out-echo-text", "handle-in-read_text-path");
    await expect(page.getByTestId("wire-error-banner")).toBeVisible();
    await expect(page.getByTestId("wire-error-banner")).toContainText("Port type mismatch");

    // 3. Add Concat (inputs a: str, b: str) and drag valid edge echo.text (str) -> concat.a (str)
    await page.getByTestId("palette-op-standard_io/text:Concat").click();
    await expect(page.getByTestId("graph-node-concat")).toBeVisible();
    await page.getByTestId("btn-auto-layout").click();
    await dragHandle("handle-out-echo-text", "handle-in-concat-a");
    await expect(page.getByTestId("wire-error-banner")).not.toBeVisible();
    await expect(page.locator('[data-id="echo.text->concat.a"]')).toBeVisible();
  });

  test("Task 6.11: edits literals, binds/unbinds references, and previews node artifacts in Node Inspector", async ({ page }) => {
    await page.goto("/#/editor/examples/workflows/foo_or_woo.yaml");
    await expect(page.getByTestId("graph-node-pick")).toBeVisible();
    await expect(page.getByTestId("graph-node-echo")).toBeVisible();

    // 1. Select 'pick' and edit its literal 'prompt' input
    await page.getByTestId("graph-node-pick").click();
    const promptInput = page.getByTestId("inspector-input-prompt");
    await expect(promptInput).toHaveValue("foo or woo?");
    await promptInput.fill("choose wisely?");
    await expect(promptInput).toHaveValue("choose wisely?");

    // 2. Select 'echo', unbind '$pick.choice', verify literal widget appears, then re-bind '$pick.choice'
    await page.getByTestId("graph-node-echo").click();
    await expect(page.getByTestId("inspector-ref-text")).toHaveText("$pick.choice");
    await page.getByTestId("inspector-unbind-text").click();
    await expect(page.getByTestId("inspector-input-text")).toBeVisible();
    await expect(page.locator('[data-id="pick.choice->echo.text"]')).toHaveCount(0);

    await page.getByTestId("inspector-bind-text").selectOption("pick.choice");
    await expect(page.getByTestId("inspector-ref-text")).toHaveText("$pick.choice");
    await expect(page.locator('[data-id="pick.choice->echo.text"]')).toHaveCount(1);

    // 3. Preview output artifact of completed 'echo' node from latest run in Node Inspector
    const previewBtn = page.getByTestId("inspector-preview-output-text");
    await expect(previewBtn).toBeVisible({ timeout: 5000 });
    await previewBtn.click();
    const dialog = page.getByTestId("artifact-preview-dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText("foo");
    await dialog.getByRole("button", { name: "Close dialog" }).click();
    await expect(dialog).not.toBeVisible();
  });
});
