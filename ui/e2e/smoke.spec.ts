import { spawn, type ChildProcess } from "node:child_process";
import * as fs from "node:fs";
import * as path from "node:path";
import { test, expect } from "@playwright/test";

async function waitForHealth(baseUrl: string, timeoutMs = 15000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`${baseUrl}/health`);
      if (res.ok) return;
    } catch {
      // Server not ready yet
    }
    await new Promise((r) => setTimeout(r, 150));
  }
  throw new Error(`Timed out waiting for ${baseUrl}/health`);
}

function startPlynxServer(workspaceRoot: string, port: number): ChildProcess {
  const binPath =
    process.platform === "win32"
      ? path.join(workspaceRoot, ".venv", "Scripts", "plynx.exe")
      : path.join(workspaceRoot, ".venv", "bin", "plynx");
  return spawn(binPath, ["ui", "--no-browser", "--port", String(port)], {
    cwd: workspaceRoot,
    stdio: "ignore",
  });
}

async function stopProcess(proc: ChildProcess | null, signal: NodeJS.Signals = "SIGTERM"): Promise<void> {
  if (!proc || proc.exitCode !== null) return;
  await new Promise<void>((resolve) => {
    proc.once("exit", () => resolve());
    proc.kill(signal);
    setTimeout(resolve, 3000);
  });
}

test.describe("PLynx UI Smoke Test", () => {
  test("Task 6.1: renders navbar and navigates between Workflows and Runs", async ({ page }) => {
    // 1. Visit root (defaults to Workflows)
    await page.goto("/");

    // 2. Navbar is rendered
    await expect(page.locator("header")).toBeVisible();
    await expect(page.getByRole("link", { name: "PLynx" })).toBeVisible();

    // 3. Default view is Workflows
    await expect(
      page.getByPlaceholder("Search workflows by name or file path..."),
    ).toBeVisible();
    await expect(page.getByText("examples/workflows/foo_or_woo.yaml")).toBeVisible();

    // 4. Click Runs nav link
    await page.getByRole("link", { name: "Runs", exact: true }).click();
    await expect(page).toHaveURL(/.*#\/runs/);
    await expect(page.getByPlaceholder("Filter by run ID or workflow...")).toBeVisible();

    // 5. Click Workflows nav link to return
    await page.getByRole("link", { name: "Workflows", exact: true }).click();
    await expect(page).toHaveURL(/.*#\/workflows/);
    await expect(
      page.getByTestId("workflow-card-examples/workflows/foo_or_woo.yaml"),
    ).toBeVisible();
  });

  test("Task 6.2 - 6.5 & 6.7: launches workflow, interacts with Stepper, Checkpoint card, Logs panel, and Previews", async ({ page }) => {
    await page.goto("/#/workflows");
    await expect(page.getByText("examples/workflows/foo_or_woo.yaml")).toBeVisible();

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
    await expect(page).toHaveURL(/.*#\/runs\/[0-9a-zA-Z_-]+/);

    // Task 6.3: Stepper view elements are visible
    await expect(page.getByText("Overall Progress")).toBeVisible();
    await expect(page.getByRole("heading", { name: "1. Ask" })).toBeVisible();
    const pickNode = page.getByText("pick", { exact: true });
    await expect(pickNode).toBeVisible();

    // Task 6.5: Wait for Checkpoint card to appear when node pauses at AskFooOrWoo
    const checkpointCard = page.getByTestId("checkpoint-card-cp_0");
    await expect(checkpointCard).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("foo or woo?")).toBeVisible();

    // Select option "foo" and submit to answer the checkpoint
    const fooRadio = checkpointCard.getByRole("radio", { name: "foo", exact: true });
    await expect(fooRadio).toBeVisible();
    await fooRadio.check();
    await checkpointCard.getByRole("button", { name: "Submit Answers" }).click();

    // Checkpoint card disappears on checkpoint_resolved!
    await expect(checkpointCard).not.toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId("run-status-badge")).toHaveText("SUCCESS", { timeout: 10000 });

    // Task 6.4: Click node row to open Logs panel
    await pickNode.click();
    await expect(page.getByTestId("logs-panel")).toBeVisible();
    await expect(page.getByRole("button", { name: "Download" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Copy" })).toBeVisible();

    // Close logs panel
    await page.getByRole("button", { name: "Close logs" }).click();
    await expect(page.getByTestId("logs-panel")).not.toBeVisible();

    // Task 6.7: Preview output via NodeInspector
    await pickNode.click();
    const previewBtn = page.getByTestId("inspector-preview-output-choice");
    await expect(previewBtn).toBeVisible({ timeout: 5000 });
    await previewBtn.click();
    await expect(page.getByTestId("artifact-preview-dialog")).toBeVisible();
    await page.getByRole("button", { name: "Close dialog" }).click();
    await expect(page.getByTestId("artifact-preview-dialog")).not.toBeVisible();
  });

  test("Task 6.6: handles Stage approval card with Approve & Continue", async ({ page }) => {
    await page.goto("/#/workflows");
    await expect(page.getByText("examples/workflows/staged.yaml")).toBeVisible();

    // Click "Run" on the staged workflow
    const stagedCard = page.getByTestId("workflow-card-examples/workflows/staged.yaml");
    await stagedCard.getByRole("button", { name: "Run" }).click();
    await expect(page).toHaveURL(/.*#\/workflows\/examples\/workflows\/staged\.yaml/);

    // Launch the run
    await page.getByRole("button", { name: "Start Run" }).click();
    await expect(page).toHaveURL(/.*#\/runs\/[0-9a-zA-Z_-]+/);

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
    await checkpointCard.getByRole("radio", { name: "foo", exact: true }).check();
    await checkpointCard.getByRole("button", { name: "Submit Answers" }).click();
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

    // Ops grouped by CATEGORY (Core / Files, Core / Interactive, Core / Text & Data)
    await expect(page.getByTestId("palette-category-Core / Files")).toBeVisible();
    await expect(page.getByTestId("palette-category-Core / Interactive")).toBeVisible();
    await expect(page.getByTestId("palette-category-Core / Text & Data")).toBeVisible();

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
    await dragHandle("handle-out-echo-text", "handle-in-pick-question");
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

    // 1. Select 'pick' and edit its literal 'question' input
    await page.getByTestId("graph-node-pick").click();
    const questionInput = page.getByTestId("inspector-input-question");
    await expect(questionInput).toHaveValue("foo or woo?");
    await questionInput.fill("choose wisely?");
    await expect(questionInput).toHaveValue("choose wisely?");

    // 2. Select 'echo', unbind '$pick.choice', verify literal widget appears, then re-bind '$pick.choice'
    await page.getByTestId("graph-node-echo").click();
    await expect(page.getByTestId("inspector-ref-text")).toHaveText("$pick.choice");
    await page.getByTestId("inspector-unbind-text").click();
    await expect(page.getByTestId("inspector-input-text")).toBeVisible();
    await expect(page.locator('[data-id="pick.choice->echo.text"]')).toHaveCount(0);

    await page.getByTestId("inspector-bind-text").selectOption("pick.choice");
    await expect(page.getByTestId("inspector-ref-text")).toHaveText("$pick.choice");
    await expect(page.locator('[data-id="pick.choice->echo.text"]')).toHaveCount(1);
  });

  test("Task 6.12: saves a temporary workflow via PUT /workflows with layout sidecar and dirty indicator, surviving reload without mutating examples", async ({ page }) => {
    const workspaceRoot = path.dirname(process.cwd());
    const tmpName = `__e2e_save_test_${Date.now()}`;
    const relPath = `examples/workflows/${tmpName}.yaml`;
    const wfFile = path.join(workspaceRoot, "examples", "workflows", `${tmpName}.yaml`);
    const sidecarFile = path.join(workspaceRoot, "examples", "workflows", `.${tmpName}.layout.json`);

    const initialYaml = `version: 1
name: ${tmpName}
stages:
  ask:
    title: "1. Ask"
    require_approval: false
  print:
    title: "2. Print"
    require_approval: false
nodes:
  pick:
    op: standard_io/interactive:AskChoice
    stage: ask
    inputs:
      question: "foo or woo?"
      options_csv: "foo, woo"
  echo:
    op: standard_io/demo:Echo
    stage: print
    inputs:
      text: "$pick.choice"
`;
    fs.writeFileSync(wfFile, initialYaml, "utf-8");

    try {
      await page.goto(`/#/editor/${relPath}`);
      await expect(page.getByTestId("graph-node-pick")).toBeVisible();

      // Initially clean (not dirty)
      await expect(page.getByTestId("dirty-indicator")).not.toBeVisible();

      // Edit a literal -> dirty indicator appears
      await page.getByTestId("graph-node-pick").click();
      const questionInput = page.getByTestId("inspector-input-question");
      await questionInput.fill("foo or woo saved?");
      await expect(page.getByTestId("dirty-indicator")).toBeVisible();
      await expect(page.getByTestId("dirty-indicator")).toContainText("Unsaved changes");

      // Drag echo node slightly so coordinates are saved to sidecar
      const echoNode = page.getByTestId("graph-node-echo");
      const echoBox = await echoNode.boundingBox();
      if (!echoBox) throw new Error("Missing echo bounding box");
      await page.mouse.move(echoBox.x + echoBox.width / 2, echoBox.y + 16);
      await page.mouse.down();
      await page.mouse.move(echoBox.x + echoBox.width / 2 + 40, echoBox.y + 56, { steps: 6 });
      await page.mouse.up();

      // Save through PUT /workflows
      await page.getByTestId("btn-save-workflow").click();
      await expect(page.getByTestId("dirty-indicator")).not.toBeVisible({ timeout: 5000 });
      await expect(page.getByTestId("save-status")).toHaveText("Saved");

      // Layout sidecar exists on disk with schema: 1, node coordinates, and NO viewport
      expect(fs.existsSync(sidecarFile)).toBe(true);
      const parsedSidecar = JSON.parse(fs.readFileSync(sidecarFile, "utf-8")) as {
        schema: number;
        nodes: Record<string, { x: number; y: number }>;
        viewport?: unknown;
      };
      expect(parsedSidecar.schema).toBe(1);
      expect(parsedSidecar.nodes.pick).toBeDefined();
      expect(parsedSidecar.nodes.echo).toBeDefined();
      expect(parsedSidecar.viewport).toBeUndefined();

      // Reload page -> edited question and clean state survive from YAML + sidecar
      await page.reload();
      await expect(page.getByTestId("graph-node-pick")).toBeVisible();
      await expect(page.getByTestId("dirty-indicator")).not.toBeVisible();
      await page.getByTestId("graph-node-pick").click();
      await expect(page.getByTestId("inspector-input-question")).toHaveValue("foo or woo saved?");
    } finally {
      if (fs.existsSync(wfFile)) {
        fs.unlinkSync(wfFile);
      }
      if (fs.existsSync(sidecarFile)) {
        fs.unlinkSync(sidecarFile);
      }
    }
  });

  test("Task 6.13: refresh during a run, during a checkpoint, and after a real server restart restores view from SQLite", async ({ page }) => {
    // Part A: Refresh during an active run & checkpoint (also verifying Graph view persists)
    await page.goto("/#/workflows");
    const fooCard = page.getByTestId("workflow-card-examples/workflows/foo_or_woo.yaml");
    await fooCard.getByRole("button", { name: "Run" }).click();
    await page.getByRole("button", { name: "Start Run" }).click();
    await expect(page).toHaveURL(/.*#\/runs\/[0-9a-zA-Z_-]+/);

    // Switch to Graph view and wait for checkpoint pause
    await page.getByTestId("view-toggle-graph").click();
    const checkpointCard = page.getByTestId("checkpoint-card-cp_0");
    await expect(checkpointCard).toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId("run-status-badge")).toHaveText("WAITING_FOR_USER");

    // Browser refresh during open checkpoint restores Graph view, WAITING_FOR_USER, and checkpoint card from SQLite
    await page.reload();
    await expect(page.getByTestId("graph-view")).toBeVisible();
    await expect(page.getByTestId("run-status-badge")).toHaveText("WAITING_FOR_USER");
    await expect(page.getByTestId("checkpoint-card-cp_0")).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("foo or woo?")).toBeVisible();

    // Answer after reload -> run completes to SUCCESS, and reloading again restores SUCCESS from SQLite
    const reloadedCard = page.getByTestId("checkpoint-card-cp_0");
    await reloadedCard.getByRole("radio", { name: "foo", exact: true }).check();
    await reloadedCard.getByRole("button", { name: "Submit Answers" }).click();
    await expect(page.getByTestId("run-status-badge")).toHaveText("SUCCESS", { timeout: 10000 });
    await page.reload();
    await expect(page.getByTestId("run-status-badge")).toHaveText("SUCCESS");
    await expect(page.getByTestId("graph-node-status-echo")).toHaveText("SUCCESS");

    // Part B: Refresh after a real server crash & restart restores FAILED (engine_died) from SQLite and allows Resume
    const workspaceRoot = path.dirname(process.cwd());
    const restartPort = 8089;
    const restartBase = `http://127.0.0.1:${restartPort}`;
    let server1: ChildProcess | null = null;
    let server2: ChildProcess | null = null;

    try {
      server1 = startPlynxServer(workspaceRoot, restartPort);
      await waitForHealth(restartBase);

      await page.goto(`${restartBase}/#/workflows`);
      await page.getByTestId("workflow-card-examples/workflows/foo_or_woo.yaml").getByRole("button", { name: "Run" }).click();
      await page.getByRole("button", { name: "Start Run" }).click();
      await expect(page).toHaveURL(/.*#\/runs\/[0-9a-zA-Z_-]+/);
      await expect(page.getByTestId("checkpoint-card-cp_0")).toBeVisible({ timeout: 10000 });

      // Kill server 1 abruptly while run is paused at checkpoint, then start server 2
      await stopProcess(server1, "SIGKILL");
      server1 = null;

      server2 = startPlynxServer(workspaceRoot, restartPort);
      await waitForHealth(restartBase);

      // Reload browser -> server 2 reconciled dead owner in SQLite -> UI shows FAILED (engine_died) + Resume Run
      await page.reload();
      await expect(page.getByTestId("run-status-badge")).toHaveText("FAILED", { timeout: 10000 });
      await expect(page.getByTestId("run-error-banner")).toContainText("engine_died");
      await expect(page.getByTestId("checkpoint-card-cp_0")).not.toBeVisible();

      // Resume Run on server 2 -> checkpoint re-opens -> answer -> SUCCESS
      await page.getByRole("button", { name: "Resume Run" }).click();
      const resumedCp = page.getByTestId("checkpoint-card-cp_0");
      await expect(resumedCp).toBeVisible({ timeout: 10000 });
      await resumedCp.getByRole("radio", { name: "woo", exact: true }).check();
      await resumedCp.getByRole("button", { name: "Submit Answers" }).click();
      await expect(page.getByTestId("run-status-badge")).toHaveText("SUCCESS", { timeout: 10000 });
    } finally {
      await stopProcess(server1, "SIGKILL");
      await stopProcess(server2, "SIGTERM");
    }
  });
});
