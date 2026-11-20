"""Generate ``ui/src/api/types.gen.ts`` from the Pydantic JSON Schema in ``plynx``.

Usage:
    python scripts/gen_ts_types.py           # write ui/src/api/types.gen.ts
    python scripts/gen_ts_types.py --check   # exit 1 if ui/src/api/types.gen.ts is stale
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, TypeAdapter
from pydantic.json_schema import models_json_schema

from plynx.api_models import (AnswerCheckpointRequest, ApiErrorDetail, ApiErrorResponse, CheckpointResolvedData, CheckpointResolvedEvent, CheckpointState,
                              CleanRequest, CleanResponse, CreateRunRequest, CreateRunResponse, EventType, HealthResponse, InputPortSpec, LogStream,
                              NodeCheckpointData, NodeCheckpointEvent, NodeLogData, NodeLogEvent, NodePosition, NodeRunState, NodeStatus, NodeStatusData,
                              NodeStatusEvent, OpEntry, OutputPortSpec, PortType, RunEvent, RunListResponse, RunState, RunStatus, RunStatusData, RunStatusEvent,
                              RunSummary, StageApprovalData, StageApprovalEvent, StageApproveRequest, StageGateState, StageGateStatus, StageInputsRequest,
                              StageResolvedData, StageResolvedEvent, UploadResponse, ValidateWorkflowRequest, ValidateWorkflowResponse, ValidationIssue,
                              Viewport, WorkflowDocument, WorkflowInputSpec, WorkflowLayout, WorkflowListItem)
from plynx.workflow.models import NodeRef, NodeSpec, Stage, Workflow

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TARGET_PATH = PROJECT_ROOT / "ui" / "src" / "api" / "types.gen.ts"

SCHEMA_MODELS: tuple[type[BaseModel], ...] = (
    NodeRef,
    Stage,
    NodeSpec,
    Workflow,
    NodeRunState,
    CheckpointState,
    StageGateState,
    RunSummary,
    RunState,
    RunStatusData,
    NodeStatusData,
    NodeCheckpointData,
    CheckpointResolvedData,
    StageApprovalData,
    StageResolvedData,
    NodeLogData,
    RunStatusEvent,
    NodeStatusEvent,
    NodeCheckpointEvent,
    CheckpointResolvedEvent,
    StageApprovalEvent,
    StageResolvedEvent,
    NodeLogEvent,
    InputPortSpec,
    OutputPortSpec,
    OpEntry,
    NodePosition,
    Viewport,
    WorkflowLayout,
    HealthResponse,
    WorkflowListItem,
    WorkflowDocument,
    ValidationIssue,
    ValidateWorkflowRequest,
    ValidateWorkflowResponse,
    WorkflowInputSpec,
    UploadResponse,
    CreateRunRequest,
    CreateRunResponse,
    RunListResponse,
    AnswerCheckpointRequest,
    CleanRequest,
    CleanResponse,
    StageApproveRequest,
    StageInputsRequest,
    ApiErrorDetail,
    ApiErrorResponse,
)

ENUM_TYPES: tuple[tuple[str, type[Any]], ...] = (
    ("NodeStatus", NodeStatus),
    ("RunStatus", RunStatus),
    ("StageGateStatus", StageGateStatus),
)

TYPE_ALIASES: tuple[tuple[str, Any], ...] = (
    ("PortType", PortType),
    ("LogStream", LogStream),
    ("EventType", EventType),
    ("RunEvent", RunEvent),
)


def _ts_literal(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    raise ValueError(f"Unsupported literal in JSON Schema: {value!r}")


def _schema_to_ts(schema: Mapping[str, Any]) -> str:
    if "$ref" in schema:
        ref = str(schema["$ref"])
        return ref.rsplit("/", 1)[-1]
    if "const" in schema:
        return _ts_literal(schema["const"])
    if "enum" in schema:
        members = [_ts_literal(item) for item in schema["enum"]]
        return " | ".join(members) if members else "never"
    for combiner in ("anyOf", "oneOf"):
        if combiner in schema:
            parts: list[str] = []
            for sub in schema[combiner]:
                rendered = _schema_to_ts(sub)
                if rendered not in parts:
                    parts.append(rendered)
            return " | ".join(parts) if parts else "unknown"

    schema_type = schema.get("type")
    if schema_type == "string":
        return "string"
    if schema_type in ("integer", "number"):
        return "number"
    if schema_type == "boolean":
        return "boolean"
    if schema_type == "null":
        return "null"
    if schema_type == "array":
        items = schema.get("items")
        if isinstance(items, Mapping):
            item_ts = _schema_to_ts(items)
            return f"Array<{item_ts}>"
        return "Array<unknown>"
    if schema_type == "object":
        additional = schema.get("additionalProperties")
        if isinstance(additional, Mapping):
            val_ts = _schema_to_ts(additional)
            return f"Record<string, {val_ts}>"
        return "Record<string, unknown>"
    return "unknown"


def _is_nullable(prop_schema: Mapping[str, Any]) -> bool:
    if prop_schema.get("type") == "null":
        return True
    for combiner in ("anyOf", "oneOf"):
        if combiner in prop_schema:
            return any(
                isinstance(sub, Mapping) and sub.get("type") == "null"
                for sub in prop_schema[combiner]
            )
    return False


def _render_interface(name: str, def_schema: Mapping[str, Any]) -> str:
    properties: Mapping[str, Any] = def_schema.get("properties", {})
    required_set = set(def_schema.get("required", []))
    is_request_or_spec = name.endswith("Request") or name in ("Workflow", "NodeSpec", "Stage")

    lines: list[str] = []
    description = def_schema.get("description")
    if isinstance(description, str) and description:
        first_line = description.strip().splitlines()[0]
        lines.append(f"/** {first_line} */")
    lines.append(f"export interface {name} {{")
    for prop_name, prop_schema in properties.items():
        if not isinstance(prop_schema, Mapping):
            continue
        ts_type = _schema_to_ts(prop_schema)
        nullable = _is_nullable(prop_schema)
        is_optional = prop_name not in required_set and (nullable or is_request_or_spec)
        opt_mark = "?" if is_optional else ""
        lines.append(f"  {prop_name}{opt_mark}: {ts_type};")
    lines.append("}")
    return "\n".join(lines)


def render_ts_types() -> str:
    """Render the complete TypeScript definitions string from Pydantic JSON Schemas."""
    _, top_schema = models_json_schema(
        [(model, "serialization") for model in SCHEMA_MODELS],
        by_alias=True,
    )
    defs: Mapping[str, Any] = top_schema.get("$defs", {})

    sections: list[str] = [
        "// AUTO-GENERATED by scripts/gen_ts_types.py — DO NOT EDIT.\n"
        "// Source of truth: packages/plynx/src/plynx/api_models.py and workflow/models.py",
    ]

    for enum_name, enum_cls in ENUM_TYPES:
        enum_schema = defs.get(enum_name) or TypeAdapter(enum_cls).json_schema(mode="serialization")
        ts_union = _schema_to_ts(enum_schema)
        sections.append(f"export type {enum_name} = {ts_union};")

    for alias_name, alias_tp in TYPE_ALIASES:
        adapter_schema = TypeAdapter(alias_tp).json_schema(by_alias=True, mode="serialization")
        ts_union = _schema_to_ts(adapter_schema)
        sections.append(f"export type {alias_name} = {ts_union};")

    emitted_names = {name for name, _ in ENUM_TYPES} | {name for name, _ in TYPE_ALIASES}
    ordered_model_names: list[str] = [m.__name__ for m in SCHEMA_MODELS]
    for extra_name in sorted(defs.keys()):
        if extra_name not in ordered_model_names and extra_name not in emitted_names:
            ordered_model_names.append(extra_name)

    for model_name in ordered_model_names:
        if model_name in emitted_names or model_name not in defs:
            continue
        def_schema = defs[model_name]
        if "enum" in def_schema:
            sections.append(f"export type {model_name} = {_schema_to_ts(def_schema)};")
        else:
            sections.append(_render_interface(model_name, def_schema))
        emitted_names.add(model_name)

    return "\n\n".join(sections) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for generating or checking ``ui/src/api/types.gen.ts``."""
    parser = argparse.ArgumentParser(description="Generate TypeScript types from Pydantic models.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify that ui/src/api/types.gen.ts is up to date without writing.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=TARGET_PATH,
        help="Output path (default: ui/src/api/types.gen.ts).",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    rendered = render_ts_types()
    output_path: Path = args.output
    if args.check:
        if not output_path.is_file():
            print(f"{output_path} does not exist. Run scripts/gen_ts_types.py.", file=sys.stderr)
            return 1
        current = output_path.read_text(encoding="utf-8")
        if current != rendered:
            print(
                f"{output_path} is out of date. Re-run scripts/gen_ts_types.py.",
                file=sys.stderr,
            )
            return 1
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
