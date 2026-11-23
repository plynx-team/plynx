"""Pydantic models and YAML loader for ``workflow.yaml`` (PROTOCOL.md section 2)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from io import StringIO
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

NODE_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]*$")
PORT_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
REF_STRING_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^\$([a-z][a-z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)$"
)

DEFAULT_STAGE_ID: Final[str] = "main"
DEFAULT_STAGE_TITLE: Final[str] = "Workflow"


class NodeRef(BaseModel):
    """A wire reference to an upstream node's output port."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    from_node: str
    output: str

    @field_validator("from_node")
    @classmethod
    def _validate_from_node(cls, value: str) -> str:
        if not NODE_ID_PATTERN.match(value):
            raise ValueError(
                f"Invalid node ID {value!r} in reference: must match ^[a-z][a-z0-9_]*$"
            )
        return value

    @field_validator("output")
    @classmethod
    def _validate_output(cls, value: str) -> str:
        if not PORT_NAME_PATTERN.match(value):
            raise ValueError(f"Invalid output port name {value!r} in reference")
        return value


def parse_input_value(value: Any, *, port: str = "") -> Any:
    """Parse a raw node input value according to the ``$`` reference and ``$$`` escape rules."""
    if isinstance(value, NodeRef):
        return value
    if isinstance(value, str):
        if value.startswith("$$"):
            return value[1:]
        if value.startswith("$"):
            match = REF_STRING_PATTERN.match(value)
            if not match:
                target = f" for input {port!r}" if port else ""
                raise ValueError(
                    f"Invalid '$' reference {value!r}{target}: expected '$<node_id>.<output>' "
                    "(where node_id matches ^[a-z][a-z0-9_]*$) or escape a literal '$' as '$$'"
                )
            return NodeRef(from_node=match.group(1), output=match.group(2))
        return value
    if isinstance(value, Mapping):
        if (
            set(value.keys()) == {"from_node", "output"}
            and isinstance(value.get("from_node"), str)
            and isinstance(value.get("output"), str)
        ):
            return NodeRef.model_validate(dict(value))
        return dict(value)
    if isinstance(value, list):
        return list(value)
    return value


class Stage(BaseModel):
    """A workflow execution stage."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    require_approval: bool = False


class NodeSpec(BaseModel):
    """A single node declaration inside ``workflow.yaml``."""

    model_config = ConfigDict(extra="forbid")

    op: str
    title: str | None = None
    stage: str = DEFAULT_STAGE_ID
    inputs: dict[str, Any] = Field(default_factory=dict)

    @field_validator("op")
    @classmethod
    def _validate_op(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Node 'op' must be a non-empty string")
        return value

    @field_validator("stage")
    @classmethod
    def _validate_stage(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Node 'stage' must be a non-empty string")
        return value

    @field_validator("inputs", mode="before")
    @classmethod
    def _validate_inputs(cls, raw_inputs: Any) -> dict[str, Any]:
        if raw_inputs is None:
            return {}
        if not isinstance(raw_inputs, Mapping):
            raise ValueError("Node 'inputs' must be a mapping")
        parsed: dict[str, Any] = {}
        for port, raw_val in raw_inputs.items():
            if not isinstance(port, str) or not PORT_NAME_PATTERN.match(port):
                raise ValueError(f"Invalid input port name {port!r}")
            parsed[port] = parse_input_value(raw_val, port=port)
        return parsed

    @field_serializer("inputs")
    def _serialize_inputs(self, inputs: dict[str, Any]) -> dict[str, Any]:
        serialized: dict[str, Any] = {}
        for port, val in inputs.items():
            if isinstance(val, NodeRef):
                serialized[port] = val.model_dump()
            elif isinstance(val, str) and val.startswith("$"):
                serialized[port] = f"${val}"
            else:
                serialized[port] = val
        return serialized


class Workflow(BaseModel):
    """Top-level ``workflow.yaml`` model."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    name: str = ""
    description: str = ""
    concurrency: int | None = None
    stages: dict[str, Stage] = Field(default_factory=dict)
    nodes: dict[str, NodeSpec] = Field(default_factory=dict)

    @field_validator("concurrency")
    @classmethod
    def _validate_concurrency(cls, value: int | None) -> int | None:
        if value is not None and (isinstance(value, bool) or value < 1):
            raise ValueError("Workflow 'concurrency' must be an integer >= 1")
        return value

    @field_validator("stages", mode="before")
    @classmethod
    def _normalize_stages(cls, raw_stages: Any) -> dict[str, Any]:
        if raw_stages is None:
            return {}
        if not isinstance(raw_stages, Mapping):
            raise ValueError("Workflow 'stages' must be a mapping")
        return {k: ({} if v is None else v) for k, v in raw_stages.items()}

    @model_validator(mode="after")
    def _validate_ids_and_order_stages(self) -> Workflow:
        for node_id in self.nodes:
            if not NODE_ID_PATTERN.match(node_id):
                raise ValueError(f"Invalid node ID {node_id!r}: must match ^[a-z][a-z0-9_]*$")
        ordered_stages: dict[str, Stage] = {}
        for stage_id, stage in self.stages.items():
            if not stage_id or not stage_id.strip():
                raise ValueError("Stage ID must be a non-empty string")
            default_title = DEFAULT_STAGE_TITLE if stage_id == DEFAULT_STAGE_ID else stage_id
            ordered_stages[stage_id] = Stage(
                title=stage.title if stage.title is not None else default_title,
                require_approval=stage.require_approval,
            )
        for node in self.nodes.values():
            if node.stage not in ordered_stages:
                default_title = (
                    DEFAULT_STAGE_TITLE if node.stage == DEFAULT_STAGE_ID else node.stage
                )
                ordered_stages[node.stage] = Stage(
                    title=default_title,
                    require_approval=False,
                )
        self.stages = ordered_stages
        return self


def parse_workflow_yaml(
    raw: str | bytes,
    *,
    default_name: str | None = None,
) -> Workflow:
    """Parse and validate a ``workflow.yaml`` string or UTF-8 bytes."""
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    yaml = YAML(typ="safe")
    try:
        data = yaml.load(StringIO(text))
    except YAMLError as exc:
        raise ValueError(f"Invalid workflow YAML: {exc}") from exc
    if not isinstance(data, Mapping):
        raise ValueError("Workflow YAML top-level value must be a mapping")
    payload = dict(data)
    if default_name and not payload.get("name"):
        payload["name"] = default_name
    return Workflow.model_validate(payload)


def load_workflow(path: Path) -> Workflow:
    """Load and validate a ``workflow.yaml`` file from disk."""
    raw = path.read_text(encoding="utf-8")
    return parse_workflow_yaml(raw, default_name=path.stem)
