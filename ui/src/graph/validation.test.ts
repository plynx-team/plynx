import { describe, expect, it } from "vitest";
import type { OpEntry, Workflow } from "../api/types.gen";
import { inputHandleId, outputHandleId } from "./types";
import {
  getCompatibleUpstreamOutputs,
  portsCompatible,
  validateConnection,
} from "./validation";

const OPS_MAP: Record<string, OpEntry> = {
  "pack/mod:StrOut": {
    id: "pack/mod:StrOut",
    pack: "pack",
    module: "mod",
    name: "StrOut",
    kind: "class",
    title: "String Output",
    category: "Test",
    cacheable: true,
    side_effects: "none",
    description: "",
    inputs: [
      {
        name: "prompt",
        type: "str",
        media: null,
        options: null,
        min: null,
        max: null,
        step: null,
        required: false,
        default: "hi",
      },
    ],
    outputs: [
      { name: "text", type: "str", media: null },
      { name: "count", type: "int", media: null },
      { name: "pdf", type: "file", media: "application/pdf" },
      { name: "raw_file", type: "file", media: null },
    ],
    allow_extra_inputs: false,
    source: "mod.py",
    valid: true,
    error: null,
  },
  "pack/mod:Consumer": {
    id: "pack/mod:Consumer",
    pack: "pack",
    module: "mod",
    name: "Consumer",
    kind: "class",
    title: "Consumer",
    category: "Test",
    cacheable: true,
    side_effects: "none",
    description: "",
    inputs: [
      {
        name: "text",
        type: "str",
        media: null,
        options: null,
        min: null,
        max: null,
        step: null,
        required: true,
        default: null,
      },
      {
        name: "ratio",
        type: "float",
        media: null,
        options: null,
        min: null,
        max: null,
        step: null,
        required: false,
        default: 1.0,
      },
      {
        name: "csv",
        type: "file",
        media: "text/csv",
        options: null,
        min: null,
        max: null,
        step: null,
        required: false,
        default: null,
      },
      {
        name: "pdf_in",
        type: "file",
        media: "application/pdf",
        options: null,
        min: null,
        max: null,
        step: null,
        required: false,
        default: null,
      },
    ],
    outputs: [{ name: "out", type: "str", media: null }],
    allow_extra_inputs: false,
    source: "mod.py",
    valid: true,
    error: null,
  },
};

const WORKFLOW: Workflow = {
  version: 1,
  name: "wiring_test",
  stages: {
    s1: { title: "Stage 1", require_approval: false },
    s2: { title: "Stage 2", require_approval: false },
  },
  nodes: {
    a: { op: "pack/mod:StrOut", stage: "s1", inputs: {} },
    b: { op: "pack/mod:Consumer", stage: "s2", inputs: {} },
    c: {
      op: "pack/mod:Consumer",
      stage: "s2",
      inputs: { text: { from_node: "b", output: "out" } },
    },
  },
};

describe("graph wiring validation (Task 6.10)", () => {
  it("accepts matching types, int-to-float promotion, and generic file to typed media", () => {
    expect(
      portsCompatible(
        { name: "text", type: "str", media: null },
        {
          name: "text",
          type: "str",
          media: null,
          options: null,
          min: null,
          max: null,
          step: null,
          required: true,
          default: null,
        },
      ),
    ).toEqual({ valid: true });

    // int -> float accepted
    expect(
      validateConnection(
        {
          source: "a",
          sourceHandle: outputHandleId("count"),
          target: "b",
          targetHandle: inputHandleId("ratio"),
        },
        WORKFLOW,
        OPS_MAP,
      ),
    ).toMatchObject({ valid: true, sourceNodeId: "a", targetNodeId: "b" });

    // Path (media: null) -> PdfFile (media: application/pdf) accepted
    expect(
      validateConnection(
        {
          source: "a",
          sourceHandle: outputHandleId("raw_file"),
          target: "b",
          targetHandle: inputHandleId("pdf_in"),
        },
        WORKFLOW,
        OPS_MAP,
      ),
    ).toMatchObject({ valid: true });
  });

  it("rejects port type mismatches with a visible reason", () => {
    const res = validateConnection(
      {
        source: "a",
        sourceHandle: outputHandleId("text"),
        target: "b",
        targetHandle: inputHandleId("csv"),
      },
      WORKFLOW,
      OPS_MAP,
    );
    expect(res.valid).toBe(false);
    if (!res.valid) {
      expect(res.reason).toContain("Port type mismatch");
      expect(res.reason).toContain("str");
      expect(res.reason).toContain("file");
    }
  });

  it("rejects media mismatches with a visible reason", () => {
    const res = validateConnection(
      {
        source: "a",
        sourceHandle: outputHandleId("pdf"),
        target: "b",
        targetHandle: inputHandleId("csv"),
      },
      WORKFLOW,
      OPS_MAP,
    );
    expect(res.valid).toBe(false);
    if (!res.valid) {
      expect(res.reason).toContain("Media mismatch");
      expect(res.reason).toContain("application/pdf");
      expect(res.reason).toContain("text/csv");
    }
  });

  it("rejects backward stage edges with a visible reason", () => {
    const res = validateConnection(
      {
        source: "b",
        sourceHandle: outputHandleId("out"),
        target: "a",
        targetHandle: inputHandleId("prompt"),
      },
      WORKFLOW,
      OPS_MAP,
    );
    expect(res.valid).toBe(false);
    if (!res.valid) {
      expect(res.reason).toContain("Backward stage edge");
      expect(res.reason).toContain("s2");
      expect(res.reason).toContain("s1");
    }
  });

  it("rejects cycles and self-loops with a visible reason", () => {
    const cycleRes = validateConnection(
      {
        source: "c",
        sourceHandle: outputHandleId("out"),
        target: "b",
        targetHandle: inputHandleId("text"),
      },
      WORKFLOW,
      OPS_MAP,
    );
    expect(cycleRes.valid).toBe(false);
    if (!cycleRes.valid) {
      expect(cycleRes.reason).toContain("Cycle detected");
    }

    const selfRes = validateConnection(
      {
        source: "b",
        sourceHandle: outputHandleId("out"),
        target: "b",
        targetHandle: inputHandleId("text"),
      },
      WORKFLOW,
      OPS_MAP,
    );
    expect(selfRes.valid).toBe(false);
    if (!selfRes.valid) {
      expect(selfRes.reason).toContain("itself");
    }
  });

  it("lists compatible upstream outputs excluding backward stages and cycles", () => {
    const strPort = OPS_MAP["pack/mod:Consumer"].inputs[0];
    const candidatesForB = getCompatibleUpstreamOutputs(
      WORKFLOW,
      "b",
      strPort,
      OPS_MAP,
    );
    expect(candidatesForB.map((c) => `${c.nodeId}.${c.output.name}`)).toEqual([
      "a.text",
    ]);
  });
});
