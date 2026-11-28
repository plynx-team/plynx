"""Pydantic models for statuses, run state, SSE events, and REST API bodies.

Single source of truth for REST/SSE contracts and generated TypeScript types (Task 0.4).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal

from plynx_sdk.protocol import (
    AgentProvider as AgentProvider,
)
from plynx_sdk.protocol import (
    AgentTurnStatus as AgentTurnStatus,
)
from plynx_sdk.protocol import (
    GraphEditPolicy as GraphEditPolicy,
)
from plynx_sdk.protocol import (
    SideEffect as SideEffect,
)
from plynx_sdk.protocol import (
    ValidatorMode as ValidatorMode,
)
from pydantic import BaseModel, ConfigDict, Field

from plynx import __version__
from plynx.workflow.models import Workflow


class NodeStatus(StrEnum):
    """Node execution statuses (ARCHITECTURE.md section 'Statuses')."""

    PENDING = "PENDING"
    BUILDING_ENVIRONMENT = "BUILDING_ENVIRONMENT"
    RUNNING = "RUNNING"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELED = "CANCELED"
    BLOCKED = "BLOCKED"


class RunStatus(StrEnum):
    """Run execution statuses (ARCHITECTURE.md section 'Statuses')."""

    RUNNING = "RUNNING"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class StageGateStatus(StrEnum):
    """Stage gate approval statuses (PROTOCOL.md section 7)."""

    WAITING = "WAITING"
    APPROVED = "APPROVED"


class StageGateKind(StrEnum):
    """Kind of stage gate: pre-stage input collection or post-stage approval."""

    INPUT = "input"
    APPROVAL = "approval"


PortType = Literal["str", "int", "float", "bool", "json", "file", "directory"]
LogStream = Literal["stdout", "stderr"]
EventType = Literal[
    "run_status",
    "node_status",
    "node_checkpoint",
    "checkpoint_resolved",
    "stage_approval",
    "stage_resolved",
    "node_log",
]


# ---------------------------------------------------------------------------
# Run state models (PROTOCOL.md sections 7 & 10)
# ---------------------------------------------------------------------------


class NodeRunState(BaseModel):
    """Per-node execution state within a run."""

    model_config = ConfigDict(extra="forbid")

    node_id: str
    status: NodeStatus
    cache_hit: bool = False
    cache_key: str | None = None
    attempt: int = 0
    exit_code: int | None = None
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)
    started_at: float | None = None
    finished_at: float | None = None


SINGLE_QUESTION_ID = "default"


class CheckpointQuestionState(BaseModel):
    """One question of a checkpoint prompt."""

    model_config = ConfigDict(extra="forbid")

    id: str
    question: str
    header: str = ""
    options: list[str] = Field(default_factory=list)
    multi_select: bool = False
    allow_freeform: bool = True


def is_batch_checkpoint(questions: list[CheckpointQuestionState]) -> bool:
    """Return whether answers are a map of question id to value (not a single string)."""
    if not questions:
        return False
    return not (len(questions) == 1 and questions[0].id == SINGLE_QUESTION_ID)


class GraphPatchModel(BaseModel):
    """Proposed dynamic DAG patch inside an agent turn or confirmation checkpoint."""

    model_config = ConfigDict(extra="forbid")

    reason: str
    add_nodes: dict[str, dict[str, Any]] = Field(default_factory=dict)
    rewire_inputs: dict[str, dict[str, Any]] = Field(default_factory=dict)


class CheckpointState(BaseModel):
    """State of a checkpoint prompt requested by a node.

    ``questions`` is empty for rows created before batch checkpoints; treat it as one
    ``default`` question built from ``question`` / ``options`` / ``allow_freeform``.
    For batch checkpoints ``answer`` holds the JSON-encoded answer map and ``answers`` the
    decoded map.
    """

    model_config = ConfigDict(extra="forbid")

    node_id: str
    checkpoint_id: str
    question: str
    options: list[str] | None = None
    allow_freeform: bool = False
    questions: list[CheckpointQuestionState] = Field(default_factory=list)
    graph_patch: GraphPatchModel | None = None
    answer: str | None = None
    answers: dict[str, str | list[str]] | None = None
    created_at: float
    answered_at: float | None = None


class StageGateState(BaseModel):
    """State of a stage gate (input collection or post-stage approval)."""

    model_config = ConfigDict(extra="forbid")

    stage_id: str
    kind: StageGateKind = StageGateKind.APPROVAL
    status: StageGateStatus
    created_at: float
    decided_at: float | None = None


class RunSummary(BaseModel):
    """Summary row for a run in ``GET /runs``."""

    model_config = ConfigDict(extra="forbid")

    id: str
    workflow_path: str
    workflow_sha256: str
    status: RunStatus
    owner_pid: int | None = None
    cancel_requested: bool = False
    pinned: bool = False
    created_at: float
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None


class NodePosition(BaseModel):
    """2D canvas position for a node in the layout sidecar."""

    model_config = ConfigDict(extra="forbid")

    x: float
    y: float


class Viewport(BaseModel):
    """Canvas viewport coordinates and zoom in the layout sidecar."""

    model_config = ConfigDict(extra="forbid")

    x: float = 0.0
    y: float = 0.0
    zoom: float = 1.0


class WorkflowLayout(BaseModel):
    """Layout sidecar ``.<name>.layout.json`` (PROTOCOL.md section 2)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: Literal[1] = Field(default=1, alias="schema")
    nodes: dict[str, NodePosition] = Field(default_factory=dict)
    viewport: Viewport | None = None


class RunState(BaseModel):
    """Full state of a run returned by ``GET /runs/{id}``."""

    model_config = ConfigDict(extra="forbid")

    id: str
    workflow_path: str
    workflow_sha256: str
    status: RunStatus
    run_inputs: dict[str, Any] = Field(default_factory=dict)
    owner_pid: int | None = None
    cancel_requested: bool = False
    pinned: bool = False
    created_at: float
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None
    nodes: dict[str, NodeRunState] = Field(default_factory=dict)
    checkpoints: list[CheckpointState] = Field(default_factory=list)
    stage_gates: dict[str, StageGateState] = Field(default_factory=dict)
    workflow_snapshot: Workflow | None = None
    layout_snapshot: WorkflowLayout | None = None


# ---------------------------------------------------------------------------
# Seven event types as a tagged union (PROTOCOL.md section 9)
# ---------------------------------------------------------------------------


class RunStatusData(BaseModel):
    """Payload for ``run_status`` events."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    status: RunStatus
    error: str | None = None


class NodeStatusData(BaseModel):
    """Payload for ``node_status`` events."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    node_id: str
    status: NodeStatus
    cache_hit: bool = False
    attempt: int = 0
    exit_code: int | None = None
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)


class NodeCheckpointData(BaseModel):
    """Payload for ``node_checkpoint`` events."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    node_id: str
    checkpoint_id: str
    question: str
    options: list[str] | None = None
    allow_freeform: bool = False
    questions: list[CheckpointQuestionState] = Field(default_factory=list)
    graph_patch: GraphPatchModel | None = None


class CheckpointResolvedData(BaseModel):
    """Payload for ``checkpoint_resolved`` events."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    node_id: str
    checkpoint_id: str


class StageApprovalData(BaseModel):
    """Payload for ``stage_approval`` events."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    stage_id: str
    title: str
    kind: StageGateKind = StageGateKind.APPROVAL


class StageResolvedData(BaseModel):
    """Payload for ``stage_resolved`` events."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    stage_id: str
    kind: StageGateKind = StageGateKind.APPROVAL


class NodeLogData(BaseModel):
    """Payload for ``node_log`` SSE events."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    node_id: str
    stream: LogStream
    offset: int = Field(ge=0)
    lines: list[str]


class RunStatusEvent(BaseModel):
    """Event emitted when the overall run status changes."""

    model_config = ConfigDict(extra="forbid")

    seq: int = Field(ge=1)
    ts: float
    type: Literal["run_status"] = "run_status"
    data: RunStatusData


class NodeStatusEvent(BaseModel):
    """Event emitted when a node's status changes."""

    model_config = ConfigDict(extra="forbid")

    seq: int = Field(ge=1)
    ts: float
    type: Literal["node_status"] = "node_status"
    data: NodeStatusData


class NodeCheckpointEvent(BaseModel):
    """Event emitted when a node pauses at a checkpoint."""

    model_config = ConfigDict(extra="forbid")

    seq: int = Field(ge=1)
    ts: float
    type: Literal["node_checkpoint"] = "node_checkpoint"
    data: NodeCheckpointData


class CheckpointResolvedEvent(BaseModel):
    """Event emitted when an open checkpoint receives an answer."""

    model_config = ConfigDict(extra="forbid")

    seq: int = Field(ge=1)
    ts: float
    type: Literal["checkpoint_resolved"] = "checkpoint_resolved"
    data: CheckpointResolvedData


class StageApprovalEvent(BaseModel):
    """Event emitted when a stage with ``require_approval: true`` awaits approval."""

    model_config = ConfigDict(extra="forbid")

    seq: int = Field(ge=1)
    ts: float
    type: Literal["stage_approval"] = "stage_approval"
    data: StageApprovalData


class StageResolvedEvent(BaseModel):
    """Event emitted when a stage approval gate is approved."""

    model_config = ConfigDict(extra="forbid")

    seq: int = Field(ge=1)
    ts: float
    type: Literal["stage_resolved"] = "stage_resolved"
    data: StageResolvedData


class NodeLogEvent(BaseModel):
    """SSE-only log batch event (not stored in ``events.jsonl``; ``seq`` is omitted)."""

    model_config = ConfigDict(extra="forbid")

    seq: int | None = None
    ts: float
    type: Literal["node_log"] = "node_log"
    data: NodeLogData


RunEvent = Annotated[
    RunStatusEvent
    | NodeStatusEvent
    | NodeCheckpointEvent
    | CheckpointResolvedEvent
    | StageApprovalEvent
    | StageResolvedEvent
    | NodeLogEvent,
    Field(discriminator="type"),
]


# ---------------------------------------------------------------------------
# Registry and REST API request/response models (PROTOCOL.md sections 2, 3, 10)

# ---------------------------------------------------------------------------


class InputPortSpec(BaseModel):
    """Input port schema in a registry entry."""

    model_config = ConfigDict(extra="forbid")

    name: str
    type: PortType
    media: str | None = None
    options: list[str | int] | None = None
    suggestions: list[str] | None = None
    min: int | float | None = None
    max: int | float | None = None
    step: int | float | None = None
    required: bool = True
    default: Any = None
    description: str | None = None


class OutputPortSpec(BaseModel):
    """Output port schema in a registry entry."""

    model_config = ConfigDict(extra="forbid")

    name: str
    type: PortType
    media: str | None = None
    description: str | None = None


class OpEntry(BaseModel):
    """Operation registry entry returned by ``GET /ops``."""

    model_config = ConfigDict(extra="forbid")

    id: str
    pack: str
    module: str
    name: str
    kind: Literal["class", "function"]
    agent_role: Literal["agent", "validator"] | None = None
    allow_graph_edits: GraphEditPolicy | None = None
    title: str
    category: str = "Uncategorized"
    cacheable: bool = True
    side_effects: SideEffect = SideEffect.NONE
    description: str = ""
    inputs: list[InputPortSpec] = Field(default_factory=list)
    outputs: list[OutputPortSpec] = Field(default_factory=list)
    allow_extra_inputs: bool = False
    extra_inputs_type: InputPortSpec | None = None
    source: str
    valid: bool = True
    error: str | None = None


class HealthResponse(BaseModel):
    """Response body for ``GET /health``."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
    version: str = __version__


class WorkflowListItem(BaseModel):
    """Item in the response of ``GET /workflows``."""

    model_config = ConfigDict(extra="forbid")

    path: str
    name: str
    stage_count: int


class WorkflowDocument(BaseModel):
    """Request and response body for ``GET /workflows/{path}`` and ``PUT /workflows/{path}``."""

    model_config = ConfigDict(extra="forbid")

    workflow: Workflow
    layout: WorkflowLayout | None = None


class ValidationIssue(BaseModel):
    """Single validation error or warning returned by ``POST /workflows/validate``."""

    model_config = ConfigDict(extra="forbid")

    severity: Literal["error", "warning"]
    node_id: str | None = None
    message: str


class ValidateWorkflowRequest(BaseModel):
    """Request body for ``POST /workflows/validate``."""

    model_config = ConfigDict(extra="forbid")

    workflow: Workflow


class ValidateWorkflowResponse(BaseModel):
    """Response body for ``POST /workflows/validate``."""

    model_config = ConfigDict(extra="forbid")

    issues: list[ValidationIssue] = Field(default_factory=list)


class WorkflowInputSpec(BaseModel):
    """Unbound run input returned by ``GET /workflows/{path}/inputs``."""

    model_config = ConfigDict(extra="forbid")

    node_id: str
    name: str
    type: PortType
    media: str | None = None
    options: list[str | int] | None = None
    suggestions: list[str] | None = None
    min: int | float | None = None
    max: int | float | None = None
    step: int | float | None = None
    required: bool
    default: Any = None
    description: str | None = None
    stage_id: str


class UploadResponse(BaseModel):
    """Response body for ``POST /uploads``."""

    model_config = ConfigDict(extra="forbid")

    path: str


class CreateRunRequest(BaseModel):
    """Request body for ``POST /runs``."""

    model_config = ConfigDict(extra="forbid")

    workflow_path: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    no_cache: bool = False
    agent_provider: AgentProvider | None = None
    agent_model: str | None = None
    max_injected_nodes: int | None = Field(default=None, ge=0)
    workflow: Workflow | None = None
    layout: WorkflowLayout | None = None


class CreateRunResponse(BaseModel):
    """Response body for ``POST /runs``."""

    model_config = ConfigDict(extra="forbid")

    run_id: str


class BaselineDriftAlert(BaseModel):
    """Recurring dynamic splice detected across recent runs of a workflow."""

    model_config = ConfigDict(extra="forbid")

    workflow_path: str
    injected_op: str
    upstream_op: str | None = None
    downstream_op: str | None = None
    occurrences: int
    window_runs: int
    message: str


class NodeExecutionStat(BaseModel):
    """Aggregated execution telemetry for a node across historical runs."""

    model_config = ConfigDict(extra="forbid")

    workflow_path: str
    node_id: str
    op: str = ""
    executions: int = 0
    cache_hits: int = 0
    cache_hit_rate: float = 0.0
    avg_duration_seconds: float | None = None
    failures: int = 0
    dynamic_injections: int = 0


class RunStatsResponse(BaseModel):
    """Response body for ``GET /runs/stats``."""

    model_config = ConfigDict(extra="forbid")

    total_runs: int = 0
    nodes: list[NodeExecutionStat] = Field(default_factory=list)
    drift_alerts: list[BaselineDriftAlert] = Field(default_factory=list)


class RunListResponse(BaseModel):
    """Response body for ``GET /runs``."""

    model_config = ConfigDict(extra="forbid")

    runs: list[RunSummary] = Field(default_factory=list)
    next_cursor: str | None = None
    drift_alerts: list[BaselineDriftAlert] | None = None


class AnswerCheckpointRequest(BaseModel):
    """Request body for ``POST /runs/{id}/checkpoints/{node_id}/{checkpoint_id}/answer``."""

    model_config = ConfigDict(extra="forbid")

    answer: str | None = None
    answers: dict[str, str | list[str]] | None = None


class StageApproveRequest(BaseModel):
    """Request body for ``POST /runs/{id}/stages/{stage_id}/approve``."""

    model_config = ConfigDict(extra="forbid")

    inputs: dict[str, Any] = Field(default_factory=dict)


class StageInputsRequest(BaseModel):
    """Request body for ``POST /runs/{id}/stages/{stage_id}/inputs``."""

    model_config = ConfigDict(extra="forbid")

    inputs: dict[str, Any] = Field(default_factory=dict)


class CleanRequest(BaseModel):
    """Request body for ``POST /clean``."""

    model_config = ConfigDict(extra="forbid")

    days: int = Field(default=14, ge=0)
    dry_run: bool = False


class CleanResponse(BaseModel):
    """Response body for ``POST /clean``."""

    model_config = ConfigDict(extra="forbid")

    deleted_runs: int = 0
    deleted_blobs: int = 0
    reclaimed_bytes: int = 0


class AgentTurnModel(BaseModel):
    """Single recorded coding-agent turn from ``agent_turns.json``."""

    model_config = ConfigDict(extra="forbid")

    turn_index: int
    provider: AgentProvider
    model: str = ""
    session_id: str | None = None
    status: AgentTurnStatus
    prompt_summary: str = ""
    outputs: dict[str, Any] | None = None
    questions: list[CheckpointQuestionState] = Field(default_factory=list)
    user_answers: dict[str, str | list[str]] | None = None
    graph_patch: GraphPatchModel | None = None
    started_at: float
    finished_at: float


class AgentTurnsResponse(BaseModel):
    """Response body for ``GET /runs/{id}/nodes/{node_id}/agent-turns``."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: Literal[1] = Field(default=1, alias="schema")
    turns: list[AgentTurnModel] = Field(default_factory=list)


class ApiErrorDetail(BaseModel):
    """Error payload inside ``ApiErrorResponse``."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class ApiErrorResponse(BaseModel):
    """Standard REST error response body."""

    model_config = ConfigDict(extra="forbid")

    error: ApiErrorDetail
