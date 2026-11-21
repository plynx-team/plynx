import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent, cleanup } from "@testing-library/react";
import { RunInputsForm } from "./RunInputsForm";
import { RouterProvider } from "../router/Router";
import * as client from "../api/client";
import type { WorkflowDocument, WorkflowInputSpec } from "../api/types.gen";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const mockDoc: WorkflowDocument = {
  workflow: {
    version: 1,
    name: "File Processing Workflow",
    description: "Processes input files with scalar options",
    stages: {
      s1: { title: "Stage One" },
    },
    nodes: {
      reader: {
        op: "standard_io/demo:ReadText",
        stage: "s1",
      },
      processor: {
        op: "standard_io/text:Concat",
        stage: "s1",
      },
    },
  },
};

const mockInputs: Array<WorkflowInputSpec> = [
  {
    node_id: "reader",
    name: "path",
    type: "file",
    required: true,
    default: "data/input.txt",
    stage_id: "s1",
  },
  {
    node_id: "processor",
    name: "suffix",
    type: "str",
    required: false,
    default: "_processed",
    stage_id: "s1",
  },
  {
    node_id: "processor",
    name: "count",
    type: "int",
    required: true,
    default: 1,
    stage_id: "s1",
  },
];

describe("RunInputsForm component", () => {
  beforeEach(() => {
    vi.spyOn(client, "fetchWorkflow").mockResolvedValue(mockDoc);
    vi.spyOn(client, "fetchWorkflowInputs").mockResolvedValue(mockInputs);
    vi.spyOn(client, "createRun").mockResolvedValue({ run_id: "new-run-888" });
  });

  it("renders workflow header and unbound inputs with defaults", async () => {
    render(
      <RouterProvider>
        <RunInputsForm workflowPath="workflows/process.yaml" />
      </RouterProvider>,
    );

    expect(screen.getByText("Loading workflow inputs...")).toBeDefined();

    await waitFor(() => {
      expect(screen.getByText("File Processing Workflow")).toBeDefined();
      expect(screen.getByText("Stage One")).toBeDefined();
    });

    // Check fields rendered
    expect(screen.getByText("Drop file here, or click to browse")).toBeDefined();
    expect(screen.getByPlaceholderText("Default: _processed")).toBeDefined();
    expect(screen.getByPlaceholderText("Default: 1")).toBeDefined();
  });

  it("submits the form with filled inputs and triggers createRun", async () => {
    render(
      <RouterProvider>
        <RunInputsForm workflowPath="workflows/process.yaml" />
      </RouterProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("File Processing Workflow")).toBeDefined();
    });

    const submitBtn = screen.getByRole("button", { name: "Start Run" });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(client.createRun).toHaveBeenCalledWith({
        workflow_path: "workflows/process.yaml",
        inputs: {
          "reader.path": "data/input.txt",
          "processor.suffix": "_processed",
          "processor.count": 1,
        },
        no_cache: false,
      });
      expect(window.location.hash).toBe("#/runs/new-run-888");
    });
  });

  it("handles empty inputs workflow", async () => {
    vi.spyOn(client, "fetchWorkflowInputs").mockResolvedValue([]);
    render(
      <RouterProvider>
        <RunInputsForm workflowPath="workflows/empty.yaml" />
      </RouterProvider>,
    );

    await waitFor(() => {
      expect(
        screen.getByText("No unbound input parameters required"),
      ).toBeDefined();
    });

    const submitBtn = screen.getByRole("button", { name: "Start Run" });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(client.createRun).toHaveBeenCalledWith({
        workflow_path: "workflows/empty.yaml",
        inputs: {},
        no_cache: false,
      });
    });
  });

  it("allows starting run when stage 2 required input is left empty (deferred to stage 2 execution)", async () => {
    const multiStageDoc: WorkflowDocument = {
      workflow: {
        version: 1,
        name: "Multi-Stage Pipeline",
        stages: {
          stage1: { title: "Stage 1" },
          stage2: { title: "Stage 2" },
        },
        nodes: {
          step1: { op: "standard_io/demo:Echo", stage: "stage1" },
          step2: { op: "standard_io/demo:Echo", stage: "stage2" },
        },
      },
    };

    const multiStageInputs: Array<WorkflowInputSpec> = [
      {
        node_id: "step1",
        name: "text1",
        type: "str",
        required: true,
        default: "ready",
        stage_id: "stage1",
      },
      {
        node_id: "step2",
        name: "text2",
        type: "str",
        required: true,
        default: null,
        stage_id: "stage2",
      },
    ];

    vi.spyOn(client, "fetchWorkflow").mockResolvedValue(multiStageDoc);
    vi.spyOn(client, "fetchWorkflowInputs").mockResolvedValue(multiStageInputs);

    render(
      <RouterProvider>
        <RunInputsForm workflowPath="workflows/multi.yaml" />
      </RouterProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("Multi-Stage Pipeline")).toBeDefined();
      expect(screen.getByText("Deferred to Stage Execution")).toBeDefined();
    });

    // text2 is empty, but since it belongs to Stage 2, starting the run should not be blocked!
    const submitBtn = screen.getByRole("button", { name: "Start Run" });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(client.createRun).toHaveBeenCalledWith({
        workflow_path: "workflows/multi.yaml",
        inputs: {
          "step1.text1": "ready",
        },
        no_cache: false,
      });
    });
  });

  it("uses inMemoryWorkflow when running an unsaved draft", async () => {
    vi.spyOn(client, "createRun").mockResolvedValue({ run_id: "unsaved-run-999" });
    const inMemoryWf = {
      version: 1 as const,
      name: "Draft Workflow",
      stages: { main: { title: "Main" } },
      nodes: {
        step1: {
          op: "standard_io/demo:Echo",
          inputs: { text: "draft text" },
        },
      },
    };

    render(
      <RouterProvider>
        <RunInputsForm
          workflowPath="workflows/test.yaml"
          inMemoryWorkflow={inMemoryWf}
        />
      </RouterProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("Draft Workflow")).toBeDefined();
      expect(screen.getByTestId("badge-unsaved-draft")).toBeDefined();
    });

    const submitBtn = screen.getByRole("button", { name: "Start Run" });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(client.createRun).toHaveBeenCalledWith({
        workflow_path: "workflows/test.yaml",
        inputs: {},
        no_cache: false,
        workflow: inMemoryWf,
        layout: undefined,
      });
    });
  });
});
