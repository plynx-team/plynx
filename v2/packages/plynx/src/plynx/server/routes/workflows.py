"""Workflow discovery, reading, validation, and saving routes."""

from __future__ import annotations

import asyncio
import json
from collections.abc import MutableMapping
from io import StringIO
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from ruamel.yaml import YAML

from plynx.api_models import (
    ValidateWorkflowRequest,
    ValidateWorkflowResponse,
    WorkflowDocument,
    WorkflowInputSpec,
    WorkflowLayout,
    WorkflowListItem,
)
from plynx.config import load_workspace_config
from plynx.server.state import ServerStateDep, error_response
from plynx.store import atomic_write_text
from plynx.workflow.models import NodeRef, Workflow, load_workflow
from plynx.workflow.validator import get_unbound_run_inputs, validate_workflow

router = APIRouter()


def discover_workflows(workspace_root: Path) -> list[WorkflowListItem]:
    """Discover YAML workflow files configured in ``workspace_root``."""
    config = load_workspace_config(workspace_root)
    wf_dir_names: list[str] = config.workflows

    items: list[WorkflowListItem] = []
    seen_paths: set[str] = set()

    for dir_name in wf_dir_names:
        wf_dir = (workspace_root / dir_name).resolve()
        if not wf_dir.is_dir():
            continue
        for ext in ("*.yaml", "*.yml"):
            for candidate in sorted(wf_dir.rglob(ext)):
                if candidate.name.startswith((".", "#")):
                    continue
                try:
                    rel_path = candidate.resolve().relative_to(workspace_root.resolve()).as_posix()
                except ValueError:
                    rel_path = candidate.as_posix()
                if rel_path in seen_paths:
                    continue
                try:
                    wf = load_workflow(candidate)
                    name = wf.name or candidate.stem
                    stage_count = len(wf.stages)
                    items.append(
                        WorkflowListItem(
                            path=rel_path,
                            name=name,
                            stage_count=stage_count,
                        )
                    )
                    seen_paths.add(rel_path)
                except Exception:
                    continue

    items.sort(key=lambda it: it.path)
    return items


def workflow_to_dict(wf: Workflow) -> dict[str, Any]:
    """Convert a ``Workflow`` model into a canonical YAML-serializable dictionary."""
    out: dict[str, Any] = {"version": wf.version}
    if wf.name:
        out["name"] = wf.name
    if wf.description:
        out["description"] = wf.description
    if wf.concurrency is not None:
        out["concurrency"] = wf.concurrency

    custom_stages: dict[str, Any] = {}
    for sid, stage in wf.stages.items():
        if sid == "main" and not stage.require_approval and (stage.title in (None, "Workflow")):
            continue
        s_data: dict[str, Any] = {}
        if stage.title and stage.title != sid:
            s_data["title"] = stage.title
        if stage.require_approval:
            s_data["require_approval"] = True
        custom_stages[sid] = s_data
    if custom_stages:
        out["stages"] = custom_stages

    nodes_out: dict[str, Any] = {}
    for nid, node in wf.nodes.items():
        n_data: dict[str, Any] = {"op": node.op}
        if node.title:
            n_data["title"] = node.title
        if node.stage and node.stage != "main":
            n_data["stage"] = node.stage
        inputs_out: dict[str, Any] = {}
        for port, val in node.inputs.items():
            if isinstance(val, NodeRef):
                inputs_out[port] = f"${val.from_node}.{val.output}"
            elif isinstance(val, str) and val.startswith("$"):
                inputs_out[port] = f"${val}"
            else:
                inputs_out[port] = val
        if inputs_out:
            n_data["inputs"] = inputs_out
        nodes_out[nid] = n_data
    out["nodes"] = nodes_out
    return out


def dump_workflow_yaml(wf: Workflow) -> bytes:
    """Serialize a ``Workflow`` model to UTF-8 YAML bytes."""
    yaml = YAML()
    yaml.preserve_quotes = True
    buf = StringIO()
    yaml.dump(workflow_to_dict(wf), buf)
    return buf.getvalue().encode("utf-8")


def _render_workflow_yaml(wf_candidate: Path, workflow: Workflow) -> str:
    """Render ``workflow`` as YAML, preserving comments and formatting when editing existing files."""
    yaml = YAML()
    yaml.preserve_quotes = True
    if wf_candidate.is_file():
        try:
            existing_wf = load_workflow(wf_candidate)
            if existing_wf == workflow:
                data = yaml.load(wf_candidate.read_text(encoding="utf-8"))
                buf = StringIO()
                yaml.dump(data, buf)
                return buf.getvalue()
        except Exception:
            pass

        try:
            data = yaml.load(wf_candidate.read_text(encoding="utf-8"))
            new_dict = workflow_to_dict(workflow)
            if isinstance(data, MutableMapping):
                for k, v in new_dict.items():
                    data[k] = v
                for k in list(data.keys()):
                    if k not in new_dict:
                        del data[k]
            else:
                data = new_dict
            buf = StringIO()
            yaml.dump(data, buf)
            return buf.getvalue()
        except Exception:
            pass

    new_dict = workflow_to_dict(workflow)
    buf = StringIO()
    yaml.dump(new_dict, buf)
    return buf.getvalue()


@router.get("/workflows", response_model=list[WorkflowListItem])
async def list_workflows_endpoint(
    state: ServerStateDep,
) -> list[WorkflowListItem]:
    """Return list of discovered workflow files in the workspace."""
    return await asyncio.to_thread(discover_workflows, state.workspace_root)


@router.get("/workflows/{path:path}/inputs", response_model=list[WorkflowInputSpec])
async def get_workflow_inputs(
    path: str,
    state: ServerStateDep,
) -> Any:
    """Return run inputs still unbound for the given workflow path."""
    wf_candidate = (state.workspace_root / path).resolve()
    try:
        wf_candidate.relative_to(state.workspace_root)
    except ValueError:
        return error_response(
            400,
            "invalid_workflow_path",
            "workflow path must stay inside the workspace root",
        )
    if not wf_candidate.is_file():
        return error_response(404, "workflow_not_found", f"Workflow file not found: {path}")
    try:
        wf_model = await asyncio.to_thread(load_workflow, wf_candidate)
    except Exception as exc:
        return error_response(400, "invalid_workflow", str(exc))
    return get_unbound_run_inputs(wf_model, state.registry)


@router.get("/workflows/{path:path}", response_model=WorkflowDocument)
async def get_workflow_endpoint(
    path: str,
    state: ServerStateDep,
) -> Any:
    """Return the workflow document and optional layout sidecar."""
    wf_candidate = (state.workspace_root / path).resolve()
    try:
        wf_candidate.relative_to(state.workspace_root)
    except ValueError:
        return error_response(
            400,
            "invalid_workflow_path",
            "workflow path must stay inside the workspace root",
        )
    if not wf_candidate.is_file():
        return error_response(404, "workflow_not_found", f"Workflow file not found: {path}")
    try:
        wf_model = await asyncio.to_thread(load_workflow, wf_candidate)
    except Exception as exc:
        return error_response(400, "invalid_workflow", str(exc))

    sidecar = wf_candidate.with_name(f".{wf_candidate.stem}.layout.json")
    layout: WorkflowLayout | None = None
    if sidecar.is_file():
        try:
            sidecar_text = await asyncio.to_thread(sidecar.read_text, encoding="utf-8")
            layout = WorkflowLayout.model_validate_json(sidecar_text)
        except Exception:
            layout = None

    return WorkflowDocument(workflow=wf_model, layout=layout)


@router.post("/workflows/validate", response_model=ValidateWorkflowResponse)
async def validate_workflow_endpoint(
    body: ValidateWorkflowRequest,
    state: ServerStateDep,
) -> ValidateWorkflowResponse:
    """Statically validate a workflow against the registered ops."""
    issues = await asyncio.to_thread(validate_workflow, body.workflow, state.registry)
    return ValidateWorkflowResponse(issues=issues)


@router.put("/workflows/{path:path}", response_model=WorkflowDocument)
async def save_workflow_endpoint(
    path: str,
    body: WorkflowDocument,
    state: ServerStateDep,
) -> Any:
    """Validate and save a workflow document and optional layout sidecar."""
    wf_candidate = (state.workspace_root / path).resolve()
    try:
        wf_candidate.relative_to(state.workspace_root)
    except ValueError:
        return error_response(
            400,
            "invalid_workflow_path",
            "workflow path must stay inside the workspace root",
        )

    if not path.endswith((".yaml", ".yml")):
        return error_response(
            400,
            "invalid_workflow_path",
            "Workflow path must end with .yaml or .yml",
        )

    issues = validate_workflow(body.workflow, state.registry)
    errors = [i for i in issues if i.severity == "error"]
    if errors:
        msg = "; ".join(i.message for i in errors)
        return error_response(422, "validation_failed", msg)

    yaml_text = await asyncio.to_thread(_render_workflow_yaml, wf_candidate, body.workflow)
    await asyncio.to_thread(atomic_write_text, wf_candidate, yaml_text)

    sidecar = wf_candidate.with_name(f".{wf_candidate.stem}.layout.json")
    if body.layout is not None:
        sidecar_json = (
            json.dumps(
                body.layout.model_dump(mode="json", by_alias=True),
                indent=2,
            )
            + "\n"
        )
        await asyncio.to_thread(atomic_write_text, sidecar, sidecar_json)

    return WorkflowDocument(workflow=body.workflow, layout=body.layout)
