# PLynx v2.1.0 Agent Implementation Entrypoint

Self-contained technical specification, architectural rationale, implementation checklist, and test plan for **PLynx `v2.1.0`** (building on the shipped `v2.0.0` baseline).

---

## 0. Instructions for the Implementing Agent ("Ask, Do Not Guess")

1. **Ask, Do Not Guess**:
   - Every architectural decision in this document was deliberately chosen to preserve PLynx `v2.0.0` invariants while avoiding over-engineering.
   - If you encounter an ambiguity, an unexpected conflict with existing `v2.0.0` code, or an edge case not covered here, **stop and ask the user a short, direct question rather than guessing or inventing unapproved abstractions**.
2. **Preserve All PLynx `v2.0.0` Core Invariants**:
   - **Invariant 1 (`plynx-sdk` is stdlib-only)**: `packages/plynx-sdk` must remain 100% Python standard library (`Python >= 3.11`). Never add third-party dependencies (`pydantic`, `ruamel.yaml`, `click`, LLM SDKs, etc.) to `plynx-sdk`.
   - **Invariant 2 (Logic vs. Layout separation)**: `workflow.yaml` holds pure DAG logic (round-trip read/written via `ruamel.yaml`). Node `(x, y)` coordinates live strictly in `workflows/.<name>.layout.json` and `.plynx/runs/<run_id>/layout.snapshot.json`. The Python backend never computes `(x, y)` coordinates.
   - **Invariant 3 (Strict Subprocess Isolation)**: Every node attempt runs in its own OS process group (`engine/procgroup.py`, `python -m plynx_sdk.harness`). Child processes never access SQLite (`plynx.db`) or the parent `Scheduler` in memory; all IPC occurs strictly via JSON files in `.plynx/runs/<run_id>/nodes/<node_id>/` and process exit codes (`0`, `10`, `1`, `2`).
   - **Invariant 4 (Within-Run Immutability)**: Completed (`SUCCESS`) node outputs within a `run_id` never mutate.
   - **Invariant 5 (Read-Only CAS & Secrets Isolation)**: External user files are copied (never hardlinked) into `.plynx/cache/blobs/`. Secrets come from `.env` / host environment (`env_passthrough`) and are never written to snapshots, manifests, logs, or SQLite.
   - **Invariant 6 (Strict Typed Constants via `enum.StrEnum`)**: Never use raw magic strings for statuses, modes, policies, or providers in Python or TypeScript. Define all protocol states as `enum.StrEnum` in `plynx_sdk/protocol.py` and `plynx/api_models.py`, and regenerate `ui/src/api/types.gen.ts` via `uv run python scripts/gen_ts_types.py`.

---

## 1. Master Implementation Checklist

Track progress against this ordered checklist:

- [x] **Phase 1 — `BUG-UI-1`: Fix `/workflows` & `/runs` List Table Column Rendering**
  - [x] 1.1 Fix CSS grid/flex column alignment on `/workflows` and `/runs` list views so Title, stages/status, and filename render in distinct columns rather than stacking into a single column.
  - [x] 1.2 Add/update frontend vitest test verifying multi-column row structure.
- [ ] **Phase 2 — `FEAT-AGT-1a`: `StrEnum` Protocol Constants, `self.warn()`, & Batch Multi-Question Checkpoints**
  - [ ] 2.1 Add `StrEnum` classes (`AgentTurnStatus`, `GraphEditPolicy`, `ValidatorMode`, `AgentProvider`) to `plynx_sdk/protocol.py`.
  - [ ] 2.2 Add `self.warn(message: str)` to `Op` and a module-level `warn(message: str)` helper (matching `checkpoint()` for `@op` functions) in `plynx-sdk`, recording `warnings: list[str]` in `OutputsManifest` (`outputs.json`) and `ResultManifest` (`result.json`).
  - [ ] 2.3 Upgrade `CheckpointManifest` (`checkpoint.json`) and `self.checkpoint()` to support a batch list of questions (`questions: list[CheckpointQuestion]`, each with `id`, `header`, `question`, `options`, `multi_select`, `allow_freeform`) while keeping single-question `self.checkpoint("...")` 100% backward-compatible.
  - [ ] 2.4 Update SQLite `checkpoints` (with an automatic `PRAGMA user_version` / `ALTER TABLE` migration so existing `v2.0.0` `.plynx/plynx.db` workspaces upgrade cleanly), REST `POST /runs/{id}/checkpoints/{node_id}/{checkpoint_id}/answer`, SSE `node_checkpoint`, CLI `--answer`, and `types.gen.ts` to handle batch answer maps (`dict[str, str | list[str]]`).
  - [ ] 2.5 Update React UI (`Stepper` & `.PropertiesBar`) to render multi-question checkpoint cards (radio buttons for single-select, checkboxes for `multi_select: true`, freeform input when `allow_freeform: true`) with a single **[Submit Answers]** button.
- [ ] **Phase 3 — `FEAT-AGT-1b`: `AgentOp`, `agent_turns.json`, & Multi-Provider Coding Harness Adapters**
  - [ ] 3.1 Implement `AgentTurnsManifest` (`nodes/<node_id>/agent_turns.json`, non-hidden) in `plynx-sdk` for 0-token replay across `checkpoint()` restarts.
  - [ ] 3.2 Implement `AgentOp` base class (and `self.agent_turn()` helper) in `plynx-sdk`, supporting both Choice A (inherited `run()` with default `prompt_file`, `prompt`, `provider`, `model`, `**extra`) and Choice B (explicit `def run()` with mandatory typed inputs + `**extra`).
  - [ ] 3.3 Update static AST extractor (`registry/extractor.py`) to recognize `AgentOp` and `StageValidatorOp` subclasses in `<1ms` (defaulting `ALLOW_EXTRA_INPUTS = True` and injecting default ports when `def run()` is omitted).
  - [ ] 3.4 Implement auto-generated JSON Schema envelope from `class Outputs(TypedDict)` (`status`, `outputs`, `questions`, `graph_patch`), automatic file output materialization (`MarkdownFile`, `JsonFile`, `TextFile`, `CsvFile`, `Path` written to `workdir/<port>.<ext>`), and the universal file-out fallback (`workdir/turn_output.json` validated against `workdir/turn_schema.json`).
  - [ ] 3.5 Implement modular CLI coding harness adapters (`claude`, `cursor-agent`, `codex`, `gemini`, `opencode`, `goose`, `aider`, `custom`, plus deterministic `mock` for offline `pytest`) with forced non-interactive flags (`stdin=DEVNULL`), no forced default timeout, upward `.agents/skills/` discovery, prompt-enforced `workdir/` write scoping, explicit `--resume <session_id>`, and `agent_concurrency` semaphore in `plynx.yaml`.
  - [ ] 3.6 Implement 4-level `provider` (`Literal` dropdown) and `model` (`str` with optional `<datalist>` suggestions from `plynx.yaml`) resolution (`plynx.yaml` -> `workflow.yaml` -> CLI `--agent-provider`/`--agent-model`/`--set` -> node input port).
  - [ ] 3.7 Add **"Agent Turns"** tab to the Web UI node log/inspector drawer displaying `agent_turns.json`.
- [ ] **Phase 4 — `FEAT-AGT-3`: Bounded Mini-Harness, Stage Validator / Supervisor, & Dynamic DAG Reload**
  - [ ] 4.1 Extend `workflow.yaml` schema (`stages.<stage_id>.validator:`) and `StageValidatorOp` in `plynx-sdk`.
  - [ ] 4.2 Schedule and store each stage validator as a reserved stage-end node in SQLite `node_runs` (`node_id = "__stage_validator__<stage_id>"`, depending on all nodes in `stage_id`).
  - [ ] 4.3 Implement Stage Validator trigger rules: skip on 100% CAS cache hit; in `ValidatorMode.ON_ANOMALY`, trigger only when a stage node emits `self.warn(...)` or exits `1` (`FAILED`, intercepting failure before aborting the run); pass automatic stage context bundle (`outputs.json`, `warnings`, `stdout`/`stderr` tails, `workflow.snapshot.yaml`, `plynx ops` schemas).
  - [ ] 4.4 Implement **"Quiesce -> Apply to `workflow.snapshot.yaml` -> Validate -> Reload DAG"** loop in `engine/scheduler.py` and `validate_snapshot_mutation(old_snapshot, new_snapshot)` enforcing: (1) `plynx validate`, (2) `PENDING`-only targets, (3) **Lineage Preservation (`U -> [New Subgraph] -> V`)** across 1-to-1 adapters, N-to-1 input aggregators, and `ALLOW_EXTRA_INPUTS`, and (4) `max_injected_nodes` budget.
  - [ ] 4.5 Support outer coding agent snapshot edits (`FEAT-AGT-3`): when a paused run's `.plynx/runs/<run_id>/workflow.snapshot.yaml` is edited and `plynx resume <run_id>` is called, run `validate_snapshot_mutation(...)` and reload the DAG.
  - [ ] 4.6 Add Stage Validator UI across Graph (`StageGroupNode` validator pill), Stepper (`StageCard` validator row + `[Approve Patch / Reject]` diff card), `.PropertiesBar` (validator editor), and `RunInspector` (`"Added by Agent"` badge + client-side layout toggle: *"Original Layout (+ Auto-place Added Nodes)"* vs. *"Re-Layout Full Run DAG"*).
  - [ ] 4.7 Add Baseline Drift Detection & execution stats (`plynx runs --stats` / UI drift banner when the same `(injected_op, upstream_op, downstream_op)` splice recurs in $K$ of the last $N$ runs).
- [ ] **Phase 5 — `FEAT-AGT-4` & Built-in Showcase: `standard_io/agent`, Thin-Shim Skills, `AGENT_GUIDE.md` Heuristics, & Example Workflow**
  - [ ] 5.1 Add `standard_io/agent:AgentPrompt` and `standard_io/agent:StageSupervisor` to `builtin_packs/standard_io/`.
  - [ ] 5.2 Update `AGENT_GUIDE.md` (`plynx agent-guide`) with the **Workflow Design & Granularity Heuristics** and new `v2.1.0` capabilities.
  - [ ] 5.3 Bundle `plynx-create-workflow/SKILL.md` in `packages/plynx/src/plynx/skills/` and materialize thin-shim `.agents/skills/plynx-create-workflow/SKILL.md` during `plynx init`.
  - [ ] 5.4 Add an end-to-end showcase workflow in `examples/workflows/` demonstrating `self.warn()`, `StageSupervisor` graph repair, and batch multi-question `checkpoint()`.

---

## 2. Detailed Technical Specifications & Rationale

### 2.1 `BUG-UI-1`: `/workflows` & `/runs` List Table Column Rendering

- **Problem**: On `/workflows` and `/runs` list views in `ui/src/`, row items collapse Title, stages count/status, and filename into a single vertical or cramped column due to CSS specificity conflicts between legacy `.node-list-item` styles in `ui/src/index.css` and Tailwind flex/grid classes.
- **Requirement**:
  - Ensure list rows use an explicit, responsive CSS Grid or Flexbox table layout with distinct, aligned columns (`Title`, `Path / Filename`, `Stages / Nodes` or `Status / Created At`, `Actions`).
- **Verification**:
  - Component unit tests in `ui/src/` and visual check on `plynx ui`.

---

### 2.2 `StrEnum` Constants, `self.warn()`, & Batch Multi-Question Checkpoints (`FEAT-AGT-1a`)

#### A. Required `enum.StrEnum` Definitions (`plynx_sdk/protocol.py`)
```python
from enum import StrEnum


class AgentTurnStatus(StrEnum):
    COMPLETED = "completed"
    NEEDS_INPUT = "needs_input"
    PROPOSE_PATCH = "propose_patch"


class GraphEditPolicy(StrEnum):
    FORBIDDEN = "forbidden"
    CONFIRM = "confirm"
    AUTO = "auto"


class ValidatorMode(StrEnum):
    ON_ANOMALY = "on_anomaly"
    ON_FAILURE = "on_failure"
    ALWAYS = "always"


class AgentProvider(StrEnum):
    DEFAULT = "default"
    CLAUDE = "claude"
    CURSOR = "cursor"
    CODEX = "codex"
    GEMINI = "gemini"
    OPENCODE = "opencode"
    GOOSE = "goose"
    AIDER = "aider"
    CUSTOM = "custom"
    MOCK = "mock"
```

#### B. Per-Node Anomaly Warnings (`self.warn(message: str)`)
- **Why**: Deterministic operations (`ParsePDF`, `CsvSummary`) should never invoke LLMs or propose graph patches themselves. Instead, when they detect a non-fatal data anomaly (e.g., `"Detected French language (lang=fr)"` or `"Table header missing, used fallback"`), they call `self.warn("...")` and exit `0`.
- **How**:
  - `Op.warn(self, message: str) -> None` (and module-level `warn(message: str)` in `plynx_sdk` for `@op` functions) appends `message` to the current attempt's warning list.
  - `plynx_sdk.harness` writes `warnings: list[str]` into `outputs.json` (`OutputsManifest`), and the engine copies `warnings` into `.plynx/runs/<run_id>/nodes/<node_id>/result.json` (`ResultManifest`).
  - In the UI (`Stepper` and `Graph`), a node that succeeded with non-empty `warnings` displays a warning indicator and lists the warnings in `.PropertiesBar`.

#### C. Batch Multi-Question Checkpoints (Single Pause, Single Resume)
- **Why**: When an `AgentOp` identifies 3 missing pieces of information (`Q1`, `Q2`, `Q3`) in Turn 0, asking them one by one (`cp_0` -> resume -> LLM Turn 1 -> `cp_1` -> resume -> LLM Turn 2 -> `cp_2`) costs **3 pauses and 4 LLM calls**. Packing a list of questions into a single checkpoint (`cp_0`), waiting for the user to answer all of them in one UI card, and resuming once takes **1 pause and 2 LLM calls total**.
- **Schema (`plynx_sdk/protocol.py`)**:
  ```python
  @dataclass
  class CheckpointQuestion:
      id: str
      question: str
      header: str = ""
      options: list[str] = field(default_factory=list)
      multi_select: bool = False
      allow_freeform: bool = True


  @dataclass
  class CheckpointManifest:
      checkpoint_id: str
      question: str = ""
      options: list[str] = field(default_factory=list)
      allow_freeform: bool = True
      questions: list[CheckpointQuestion] = field(default_factory=list)
  ```
- **Backward Compatibility**:
  - `self.checkpoint(question="Pick one", options=["A", "B"], allow_freeform=False) -> str` continues to work unchanged (populates a 1-item `questions` list with `id="default"` and returns a `str`).
  - `self.checkpoint_batch(questions: list[CheckpointQuestion | dict]) -> dict[str, str | list[str]]` pauses once (`exit 10`) and on replay returns the dictionary mapping each `question.id` to the user's answer (`str` when `multi_select=False`, `list[str]` when `multi_select=True`).
- **Frontend UI (`Stepper` & `.PropertiesBar`)**:
  - Render all items in `checkpoint.questions` inside a single form card:
    - `multi_select == false` with `options`: radio group (+ optional "Other" freeform text input if `allow_freeform == true`).
    - `multi_select == true` with `options`: checkbox group (+ optional freeform input if `allow_freeform == true`).
    - Empty `options`: text input / textarea.
  - A single **[Submit Answers]** button posts `{"answers": {"q1": "...", "q2": ["..."]}}` to `POST /runs/{run_id}/checkpoints/{node_id}/{checkpoint_id}/answer`.

---

### 2.3 `AgentOp`, `agent_turns.json`, & Multi-Provider Coding Harnesses (`FEAT-AGT-1b`)

#### A. Solving the Checkpoint Token Re-Burn Bug (`nodes/<node_id>/agent_turns.json`)
- **The Problem**: In PLynx `v2.0.0`, answering a `checkpoint()` (`exit 10`) replays `def run(self, ...)` in a new subprocess from line 1. If an `AgentOp` calls an LLM before `self.checkpoint_batch(...)`, a naive replay would re-execute Turn 0's 30,000-token LLM query from scratch on Attempt 2 just to reach `cp_0`.
- **The Solution**:
  - Standardize a **non-hidden** manifest `.plynx/runs/<run_id>/nodes/<node_id>/agent_turns.json` (alongside `inputs.json`, `outputs.json`, `checkpoint.json`, `result.json`).
  - Before executing Turn $k$, `AgentOp` checks `agent_turns.json`. If Turn $k$ is already recorded, `AgentOp` returns the recorded turn response in **0ms and 0 tokens**, reaches `self.checkpoint_batch(...)` (which returns the user's stored answers from `inputs.json["__checkpoint_answers__"]`), and proceeds directly to Turn $k+1$ using `--resume <session_id>`.
- **`agent_turns.json` Structure**:
  ```json
  {
    "turns": [
      {
        "turn_index": 0,
        "provider": "cursor",
        "model": "auto",
        "session_id": "chat_abc123",
        "status": "needs_input",
        "prompt_summary": "Compare CV against job description...",
        "questions": [{"id": "role", "question": "Target track?", "options": ["ML", "Backend"]}],
        "user_answers": {"role": "ML"},
        "started_at": "2026-11-26T18:00:00Z",
        "finished_at": "2026-11-26T18:00:08Z"
      }
    ]
  }
  ```
- **Web UI Visibility**:
  - Expose `GET /runs/{run_id}/nodes/{node_id}/agent-turns` (or include in node detail payload) and add an **"Agent Turns"** tab in the UI log/inspector drawer next to `stdout` and `stderr`.

#### B. Strict Separation: Internal Agent Loops vs. Human Checkpoints
- **Rule**: Never use PLynx `checkpoint()` (`exit 10`, `WAITING_FOR_USER`) for an agent to talk to itself (`c0 -> c1 -> c2`).
- Internal multi-step tool/reasoning loops happen 100% inside the CLI coding harness execution. PLynx `checkpoint()` is strictly for **human user feedback** (or human confirmation of a proposed graph patch).

#### C. `<1ms` Static AST Discovery (`registry/extractor.py`) — Choice A vs. Choice B
1. **Base Class Whitelist**: Update `registry/extractor.py` to recognize `AgentOp` and `StageValidatorOp` in addition to `Op`. Default `ALLOW_EXTRA_INPUTS = True` on `AgentOp`.
2. **Choice A (Prompt-Driven Subclass — No `def run()` Overridden)**:
   - The subclass omits `def run()` and only declares `TITLE`, `CATEGORY`, and `class Outputs(TypedDict):`.
   - `extractor.py` automatically registers the standard inherited `AgentOp` input ports:
     - `prompt_file: MarkdownFile | None = None`
     - `prompt: str = ""`
     - `provider: Literal["default", "claude", "cursor", "codex", "gemini", "opencode", "goose", "aider", "custom", "mock"] = "default"`
     - `model: str = ""`
     - plus variadic `**extra` (`ALLOW_EXTRA_INPUTS = True`).
3. **Choice B (Explicit `def run()` Subclass — Mandatory Typed Inputs + `**extra`)**:
   - The subclass overrides `def run(self, cv: MarkdownFile, job_desc: TextFile, prompt_file: MarkdownFile | None = None, prompt: str = "", provider: ... = "default", model: str = "", **extra: Any) -> Outputs: return self.run_agent(...)`.
   - `extractor.py` extracts the explicit mandatory ports (`cv`, `job_desc`) plus the standard ports and `**extra`.
4. **Automatic File vs. Scalar Output Materialization**:
   - `class Outputs(TypedDict)` can mix scalars (`match_score: int`) and file types (`summary: MarkdownFile`, `data: JsonFile`, `report: TextFile`).
   - When `status == AgentTurnStatus.COMPLETED`, `AgentOp` inspects the declared `Outputs` annotations: if a port is a `Path` / `Media` alias and the agent returned inline string/JSON content in `outputs[port]` (rather than a relative path to an existing file in `workdir/`), `AgentOp` writes the content to `workdir/<port>.<ext>` and replaces `outputs[port]` with `Path("<port>.<ext>")` so `plynx_sdk.harness` ingests it into CAS as a real file artifact.

#### D. Auto-Generated JSON Schema Envelope & Universal File-Output Contract (`workdir/turn_output.json`)
- **User Prompt Stays 100% Domain-Only**: Users never write PLynx API or JSON formatting instructions in `prompt` or `prompt_file`.
- **Standard Envelope (`workdir/turn_schema.json`)**:
  - Generated automatically by `AgentOp` from `class Outputs(TypedDict)`:
    - `status`: `AgentTurnStatus` (`"completed" | "needs_input" | "propose_patch"` — omit `"propose_patch"` when `allow_graph_edits == GraphEditPolicy.FORBIDDEN`).
    - `outputs`: object matching `class Outputs(TypedDict)` (required when `status == "completed"`).
    - `questions`: array of `CheckpointQuestion` (required when `status == "needs_input"`).
    - `graph_patch`: `GraphPatchPayload` (`add_nodes`, `rewire_inputs`, `reason` — required when `status == "propose_patch"`).
- **Universal File-Out Mechanism**:
  - `AgentOp` writes `workdir/turn_schema.json` before invoking the CLI adapter.
  - Where a CLI supports native schema flags (`claude -p --output-format json --json-schema ...`, `codex exec --output-schema ...`), pass the flag; across **all** providers (including `cursor-agent`, `codex exec resume`, `gemini`, `opencode`, `goose`, `aider`, `custom`, `mock`), the system prompt envelope also instructs the coding agent to write its final JSON response to `workdir/turn_output.json`.
  - `AgentOp` reads `workdir/turn_output.json` (falling back to parsed `stdout` JSON envelope) and validates it against `Outputs(TypedDict)`.

#### E. Modular Multi-Provider Coding Harness Adapters & Concurrency Guards
- **Supported Providers (`AgentProvider(StrEnum)`)**:
  - `CLAUDE`: `claude -p --output-format json --json-schema <schema> [--model <m>] [--resume <sid>] --dangerously-skip-permissions`
  - `CURSOR`: `cursor-agent -p --output-format json [--model <m>] [--resume <sid>] --force`
  - `CODEX`: `codex exec --output-schema <schema_path> [-m <m>]` (or `codex exec resume <sid>`)
  - `GEMINI`: `gemini -p` / `agy` headless invocation
  - `OPENCODE`: `opencode run [-m <m>]` (supports 80+ BYO API keys & local Ollama models)
  - `GOOSE`: `goose run` (supports BYO API keys & local models)
  - `AIDER`: `aider --message <prompt> --no-input [--model <m>]` (supports BYO API keys & local Ollama models)
  - `CUSTOM`: user-configured command template in `plynx.yaml` (`agent.custom_command`)
  - `MOCK`: deterministic offline provider for `pytest` (reads scripted responses from an env var, parameter, or fixture file without spawning external network CLIs)
- **3 Mandatory Execution & Concurrency Guards**:
  1. **Non-Interactive & No Forced Default Timeout**: Always run with `stdin=subprocess.DEVNULL` and non-interactive permission flags so child CLIs never hang on terminal `y/N` prompts. Keep `timeout_seconds: int | None = None` (no forced timeout by default).
  2. **Upward `.agents/skills/` Discovery + Prompt-Enforced `workdir/` Write Scoping**:
     - Do **not** pass `--bare`. Because `.plynx/runs/<run_id>/nodes/<node_id>/workdir/` sits inside `<workspace_root>`, the CLI agent walks upward to `<workspace_root>` and loads `AGENTS.md`, `.agents/skills/`, and MCP tools.
     - The auto-generated PLynx System Prompt Envelope must explicitly state:
       > *"Your working directory is `<node_workdir>`. Read your task inputs strictly from `<node_dir>/inputs/` and write all generated artifacts and `turn_output.json` inside `<node_workdir>`. You may use workspace `.agents/skills/` and `AGENTS.md` guidelines, but do not modify tracked workspace files outside `<node_workdir>`."*
  3. **Parallel Session Safety & `agent_concurrency`**:
     - Never pass global `--continue` (which hijacks concurrent sessions); always pass explicit `--resume <session_id>` from that node's `agent_turns.json`.
     - Enforce an optional `agent_concurrency: int` semaphore in `plynx.yaml` (default e.g. `2`, separate from CPU `concurrency`) across active `AgentOp` / `StageValidatorOp` executions.
- **4-Level Provider & Model Resolution**:
  1. Global workspace `plynx.yaml`: `agent: { provider: "cursor", model: "", agent_concurrency: 2, models: [...] }` (or `PLYNX_AGENT_PROVIDER` / `PLYNX_AGENT_MODEL` env vars).
  2. Workflow-level default in `workflow.yaml`: `agent: { provider: "...", model: "..." }`.
  3. Per-run CLI override: `plynx run --agent-provider cursor --agent-model gpt-5` (or `--set node.model="gpt-5"`).
  4. Per-node / per-stage-validator input ports: `provider` (`Literal` dropdown in `.PropertiesBar`) and `model` (`str` input with optional HTML `<datalist>` populated from `plynx.yaml` `agent.models`—no background timers or database caching of vendor model lists; when `model == ""`, omit `--model` so the CLI tool uses its own configured default).
  - **Cache Key Consistency**: Write the effective resolved `provider` and `model` values into `inputs.json` before `plynx-cache-1` cache-key computation so changing provider/model via `plynx.yaml`, `workflow.yaml`, or CLI flags reliably invalidates cached `AgentOp` / `StageValidatorOp` results.

---

### 2.4 Bounded Mini-Harness, Stage Validator / Supervisor, & Dynamic DAG Reload (`FEAT-AGT-3`)

#### A. Stage Validator Declaration (`workflow.yaml`) & SQLite Identity
```yaml
stages:
  ingest:
    title: "1. Ingest Documents"
    require_approval: false
    validator:
      op: standard_io/agent:StageSupervisor
      mode: on_anomaly          # on_anomaly | on_failure | always (ValidatorMode)
      allow_graph_edits: confirm # forbidden | confirm | auto (GraphEditPolicy)
      inputs:
        prompt_file: prompts/validators/ingest_check.md
        prompt: "If extracted text is non-English, splice a translation op before Stage 2."
        provider: default
        model: ""
```
- **Cross-DAG Prompt Reuse**: By binding `prompt_file` to a workspace-relative `MarkdownFile` (`prompts/validators/ingest_check.md`), PLynx keeps 100% standard YAML (no custom `!include` tags that break JSON REST round-tripping), hashes the file's `sha256` into `plynx-cache-1` automatically, and previews the Markdown file inline in `.PropertiesBar`.
- **SQLite & Execution Identity**:
  - In `engine/scheduler.py` and SQLite `node_runs`, materialize each stage's `validator` as a reserved stage-end node with `node_id = "__stage_validator__<stage_id>"` that depends on every node in `<stage_id>`, and upon which all nodes in subsequent stages depend.
  - This reuses 100% of `node_runs`, `logs/<node_id>.stdout.log`, SSE `node_status`/`node_log`, `checkpoints`, and `agent_turns.json` with zero new SQLite tables.
  - Ensure `NODE_ID_PATTERN` (enforced by `/logs`, `/outputs`, `/checkpoints`, and `/agent-turns`) explicitly permits reserved `__stage_validator__<stage_id>` IDs while continuing to reject path traversal.
- **Two-Tier Trigger Logic (Zero LLM Tax on Happy Path)**:
  1. If all nodes in `<stage_id>` were `cache_hit: true` and succeeded with no warnings, skip `__stage_validator__<stage_id>` (`SUCCESS`, `cache_hit: true`).
  2. In `ValidatorMode.ON_ANOMALY`: run the validator **only** if at least one node in `<stage_id>` recorded non-empty `warnings` via `self.warn(...)` **or** exited with code `1` (`FAILED`). If all nodes in `<stage_id>` exited `0` with `warnings == []`, mark `__stage_validator__<stage_id>` `SUCCESS` immediately in 0ms without invoking the CLI agent.
  3. In `ValidatorMode.ON_FAILURE`: run the validator only if a node in `<stage_id>` exited `1` (`FAILED`).
  4. In `ValidatorMode.ALWAYS`: always run the validator when the stage finishes.
  5. **Failure Interception**: When a stage has a `validator` covering failures (`ON_ANOMALY` or `ON_FAILURE`) and a node in that stage fails (`exit 1`), do not immediately fail the entire run—run `__stage_validator__<stage_id>` first so it can inspect `stderr.log` and propose a graph repair patch.
- **Automatic Stage Context Bundle**:
  - The engine writes `stage_context.json` into `nodes/__stage_validator__<stage_id>/` containing:
    - Stage node statuses, `warnings`, and output previews/paths (`outputs.json`).
    - Tails (e.g. last 100 lines) of `stdout.log` and `stderr.log` for each node in `<stage_id>`.
    - Current `workflow.snapshot.yaml` and registered `plynx ops` schemas.

#### B. "Quiesce -> Apply to `workflow.snapshot.yaml` -> Validate -> Reload DAG" & Guardrails
When a Stage Validator (or an `AgentOp` with `allow_graph_edits != FORBIDDEN`) exits with `status == AgentTurnStatus.PROPOSE_PATCH` (`graph_patch.json`), **or** when an outer coding agent edits `.plynx/runs/<run_id>/workflow.snapshot.yaml` while paused and runs `plynx resume <run_id>`:

1. **Quiesce Active Workers**: Never mutate `graphlib.TopologicalSorter` while child subprocesses are running. Wait until all currently `RUNNING` node subprocesses finish.
2. **Validate the Proposed Snapshot Mutation (`validate_snapshot_mutation(old_snapshot, new_snapshot)`)**:
   - **Check 1 (Standard Static Validation)**: The mutated snapshot must pass `plynx validate` (all `op` references exist in registry, port types match, no cycles, edges only go within the same stage or forward to a later stage).
   - **Check 2 (`PENDING`-Only Target Rule)**: Existing nodes whose status in `node_runs` is `SUCCESS` or `RUNNING` cannot be deleted or have their `op` or `inputs` modified. Only `PENDING` (or failed/repaired) nodes may have their `inputs` rewired.
   - **Check 3 (Lineage Preservation — `U -> [New Subgraph] -> V`)**:
     - If an existing input wiring `V.inputs[port] = "$U.out"` on a `PENDING` node `V` is changed to `"$N.out"`, node `U` must remain an upstream ancestor of `N` (`U -> ... -> N -> V`) unless the user explicitly approves dropping `U`.
     - This single graph rule allows all 3 valid splice patterns while preventing orphaned upstream work:
       1. *1-to-1 Inline Adapter / Transformer*: `U.out -> TranslateToEnglish -> V.in`.
       2. *N-to-1 Fan-In Input Aggregator*: `(U.out + ExtraFetch.out) -> Concat / JsonMerge / BundleDirectory / TemplateFormat -> V.in`.
       3. *Variadic Extra Port (`ALLOW_EXTRA_INPUTS`)*: `ExtraFetch.out -> V.extra_port` (leaving `U.out -> V.main_port` untouched).
   - **Check 4 (`max_injected_nodes` Budget)**: Total agent-injected nodes in the run must not exceed `max_injected_nodes` (default `3` in `plynx.yaml`, overridable per workflow in `workflow.yaml` or via CLI `plynx run --max-injected-nodes N`).
3. **Human Confirmation Gate (`GraphEditPolicy.CONFIRM` vs. `AUTO`)**:
   - If `allow_graph_edits == GraphEditPolicy.CONFIRM`, pause at `WAITING_FOR_USER` (`checkpoint.json`) displaying the human-readable `reason`, added nodes, and rewired inputs (`[Approve Patch / Reject]`).
   - Once approved (or immediately if `GraphEditPolicy.AUTO`), update `.plynx/runs/<run_id>/workflow.snapshot.yaml` via `ruamel.yaml` (marking added nodes with `meta: { injected_by: "<validator_id>", reason: "..." }`), while leaving the Git-tracked `workflows/<name>.yaml` untouched.
4. **Reload DAG**: Re-initialize `TopologicalSorter` from the updated `workflow.snapshot.yaml` using the `plynx resume` lifecycle (preserving all `SUCCESS` node outputs in `node_runs` and scheduling only the new and remaining `PENDING` nodes).

#### C. Web UI Stage Validator & `RunInspector` Layout Toggle
- **Graph View (`StageGroupNode`)**: Render a clickable **Stage Validator Pill / Footer Bar** inside the stage frame showing validator title, `mode`, and status (`PENDING`, `RUNNING`, `PASSED`, `PATCH_PROPOSED`).
- **Linear Stepper View (`StageCard`)**: Render the Stage Validator row at the bottom of the stage card with logs and interactive `[Approve Patch / Reject]` diff preview.
- **Right Dock (`.PropertiesBar`)**: Selecting a stage or its validator allows attaching/removing a validator op and editing `mode`, `allow_graph_edits`, `prompt_file`, `prompt`, `provider`, and `model` via `PortInput`.
- **`RunInspector` Diff Badges & Client-Side Layout Toggle**:
  - Nodes with `meta.injected_by` (or present in `workflow.snapshot.yaml` but absent from baseline `workflows/<name>.yaml`) display an **`ADDED BY AGENT`** badge alongside `runDiff.ts` diffs.
  - Add a client-side layout toggle in `RunInspector`:
    1. **"Original Layout (+ Auto-place Added Nodes)"** *(Default)*: Locks baseline nodes to their `(x, y)` coordinates from `layout.snapshot.json` and positions injected nodes between their upstream `U` and downstream `V` coordinates.
    2. **"Re-Layout Full Run DAG"**: Runs client-side Dagre auto-layout across the entire `workflow.snapshot.yaml`.

#### D. Baseline Drift Detection & Execution Telemetry (`plynx runs --stats`)
- When comparing `workflow.snapshot.yaml` against `workflows/<name>.yaml`, compute structural splice tuples `(injected_op, upstream_op, downstream_op)`.
- If the same splice tuple appears in $K$ of the last $N$ runs of a workflow (default: `3` of the last `5` runs), display a **Baseline Drift Detected** notice in `plynx runs` and the Web UI suggesting promotion/refactoring into the canonical workflow.
- Add `plynx runs --stats [--workflow <path>]` reporting per-node execution count, CAS cache-hit rate, average duration, failure count, and dynamic injection frequency from SQLite `node_runs`.

---

### 2.5 `FEAT-AGT-4` & Built-in Showcase: `standard_io/agent`, Thin-Shim Skills, `AGENT_GUIDE.md` Heuristics, & Example Workflow

1. **Built-in `standard_io/agent` Operations (`builtin_packs/standard_io/`)**:
   - `standard_io/agent:AgentPrompt`: Ready-to-use Choice A `AgentOp` (`prompt_file`, `prompt`, `provider`, `model`, `**extra` -> `response: MarkdownFile`).
   - `standard_io/agent:StageSupervisor`: Ready-to-use `StageValidatorOp` (`prompt_file`, `prompt`, `provider`, `model`).
2. **Expand `AGENT_GUIDE.md` (`plynx agent-guide`) with Workflow Design & Granularity Heuristics**:
   - Add a dedicated section teaching coding agents:
     - **1. Reuse Before Authoring (`plynx ops --json` first)**: Always inspect `standard_io` and existing `custom_packs/` ops before writing new Python ops.
     - **2. Goldilocks Granularity (Typically 3–8 Nodes Across 2–4 Stages)**: Never write a 1-node monolith script (which defeats Stepper visibility and intermediate CAS caching), and never create 25 tiny 2-line micro-nodes (which causes UI noise and subprocess startup overhead). Each node must be one coherent, human-understandable step.
     - **3. Cache-Boundary Splitting**: Separate expensive/slow steps (LLM `AgentOp`, PDF parsing, network I/O) from fast deterministic formatting so downstream tweaks hit `plynx-cache-1` in 0ms.
     - **4. Regression Testing Refactored Ops with `plynx run-node`**: When consolidating or refactoring Python ops in `custom_packs/`, replay historical `.plynx/runs/<run_id>/nodes/<node_id>` directories via `plynx run-node` to verify corner cases before updating `workflows/<name>.yaml`.
3. **Wheel-Bundled Skill & `plynx init` Thin-Shim Materialization**:
   - Store core skill template at `packages/plynx/src/plynx/skills/plynx-create-workflow/SKILL.md`.
   - Update `plynx init` to materialize `.agents/skills/plynx-create-workflow/SKILL.md` as a concise (~25-line) thin shim (standard YAML frontmatter `name` + `description` + 5-step procedure) whose Step 1 runs `plynx agent-guide` and `plynx ops --json` so upgrading `plynx` via `pip`/`uv` never leaves stale schema documentation in the user's repo.
4. **End-to-End Showcase Workflow (`examples/workflows/`)**:
   - Create a showcase workflow (e.g., `examples/workflows/adaptive_doc_review.yaml`) demonstrating:
     - Stage 1 deterministic ingestion node emitting `self.warn("Detected non-English document (lang=fr)")`.
     - Stage 1 `validator` (`standard_io/agent:StageSupervisor`) proposing a `graph_patch` to splice a translator/adapter node before Stage 2.
     - Stage 2 node using batch multi-question `checkpoint_batch()` (`[Q1, Q2]`) and producing a final Markdown report.

---

## 3. Verification & Test Suite Requirements

Every phase must include automated tests and pass the full verification suite before completion:

1. **`plynx-sdk` Unit Tests (`tests/test_sdk_*.py`)**:
   - Verify `StrEnum` serialization, `self.warn()` emission in `outputs.json`/`result.json`, backward-compatible single `self.checkpoint()` vs. `self.checkpoint_batch()`, `agent_turns.json` 0-token replay across simulated exit-10 restarts, automatic file output materialization (`MarkdownFile` string -> `workdir/<port>.md`), and `AgentProvider.MOCK` + CLI command builders (`claude`, `cursor-agent`, `codex`, `gemini`, `opencode`, `goose`, `aider`).
2. **Static AST Extractor Tests (`tests/test_extractor.py`)**:
   - Verify `<1ms` AST discovery of `AgentOp` (both Choice A inherited `run()` and Choice B explicit `run()`) and `StageValidatorOp`, including `provider` (`Literal` options), `model` (`str`), `prompt_file` (`MarkdownFile`), and `ALLOW_EXTRA_INPUTS = True`.
3. **Engine, Stage Validator & Dynamic DAG Reload Tests (`tests/test_engine_*.py`)**:
   - Using `AgentProvider.MOCK`:
     - Test happy-path stage where no node emits `self.warn()` -> verify `ValidatorMode.ON_ANOMALY` skips LLM invocation in 0ms.
     - Test anomaly stage where a node emits `self.warn("lang=fr")` (or exits `1`) -> verify `__stage_validator__<stage_id>` runs, receives `stage_context.json` (`warnings` + logs + outputs), emits `graph_patch.json`, pauses for confirmation when `GraphEditPolicy.CONFIRM`, applies the patch to `workflow.snapshot.yaml` after active workers quiesce, validates **Lineage Preservation**, reloads the DAG, and executes the newly spliced node(s) while reusing Stage 1 `SUCCESS` outputs.
     - Test rejection of invalid graph patches: (a) rewiring a `SUCCESS` node, (b) orphaning an upstream dependency (violating Lineage Preservation), and (c) exceeding `max_injected_nodes`.
     - Test outer-agent workflow (`FEAT-AGT-3`): pause run -> edit `workflow.snapshot.yaml` -> `plynx resume <run_id>` -> verify `validate_snapshot_mutation` and execution of added nodes.
4. **CLI, Packaging, & Drift Telemetry Tests (`tests/test_cli_*.py`, `tests/test_wheel.py`)**:
   - Verify `plynx init` creates `.agents/skills/plynx-create-workflow/SKILL.md`, `plynx agent-guide` includes the Workflow Design & Granularity Heuristics, `plynx runs --stats` flags recurring splice signatures, and `tests/test_wheel.py` asserts `plynx/skills/plynx-create-workflow/SKILL.md` is bundled in the built wheel.
5. **Docs & Full-Stack Build Checks**:
   - Keep `docs/PROTOCOL.md` and `docs/ARCHITECTURE.md` synced with all new endpoints, schema fields, `StrEnum` values, and CLI flags per `AGENTS.md`.
   ```bash
   uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest
   uv run python scripts/gen_ts_types.py --check
   cd ui && npm run lint && npm run typecheck && npm test && npm run build && cd ..
   uv run python scripts/build.py && uv run pytest tests/test_wheel.py
   ```
