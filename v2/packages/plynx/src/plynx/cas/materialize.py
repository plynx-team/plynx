"""Materialize inputs for node execution (PROTOCOL.md section 5, PLAN.md task 3.3)."""

from __future__ import annotations

import contextlib
import os
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from plynx_sdk.protocol import (
    InputDirectoryValue,
    InputFileValue,
    InputsManifest,
    InputValue,
    OutputDirectoryValue,
    OutputFileValue,
    OutputValue,
    ResultDirectoryValue,
    ResultFileValue,
    ResultValue,
    ScalarValue,
)

from plynx.api_models import CheckpointState
from plynx.cas.blob_store import BlobStore, make_writable
from plynx.cas.ingest import ingest_directory, materialize_directory
from plynx.registry import OpRegistry
from plynx.workflow.models import NodeRef, NodeSpec


def safe_rmtree(path: Path) -> None:
    """Recursively remove a directory, clearing read-only attributes so deletion succeeds."""
    if not path.exists():
        return
    for root, _, files in os.walk(path):
        for f in files:
            p = Path(root) / f
            with contextlib.suppress(OSError):
                make_writable(p)
    shutil.rmtree(path)


def materialize_input_file(
    *,
    dst_node_dir: Path,
    port_name: str,
    sha256: str,
    size_bytes: int,
    filename: str,
    blob_store: BlobStore,
) -> InputFileValue:
    """Materialize a single file input from CAS at ``inputs/<port>/<filename>`` as read-only."""
    target = dst_node_dir / "inputs" / port_name / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        try:
            make_writable(target)
            target.unlink()
        except OSError:
            pass

    blob_store.materialize(sha256, target)
    return InputFileValue(
        path=f"inputs/{port_name}/{filename}",
        sha256=sha256,
        size_bytes=size_bytes,
    )


def materialize_input_directory(
    *,
    dst_node_dir: Path,
    port_name: str,
    result_dir: ResultDirectoryValue,
    blob_store: BlobStore,
) -> InputDirectoryValue:
    """Materialize a directory input from CAS at ``inputs/<port>`` as read-only."""
    target_dir = dst_node_dir / "inputs" / port_name
    if target_dir.exists():
        safe_rmtree(target_dir)

    materialize_directory(result_dir, target_dir, blob_store)
    return InputDirectoryValue(
        path=f"inputs/{port_name}",
        tree_sha256=result_dir.tree_sha256,
        entries=list(result_dir.entries),
    )


def _resolve_expected_port_type(
    port_name: str,
    port_types: Mapping[str, str],
    op_entry: Any,
) -> str | None:
    expected_type = port_types.get(port_name)
    if (
        expected_type is None
        and op_entry is not None
        and op_entry.allow_extra_inputs
        and op_entry.extra_inputs_type is not None
    ):
        return str(op_entry.extra_inputs_type.type)
    return expected_type


def _materialize_node_ref(
    *,
    port_name: str,
    binding: NodeRef,
    dst_node_dir: Path,
    completed_outputs: Mapping[str, Mapping[str, ResultValue | OutputValue]],
    blob_store: BlobStore,
    workspace_root: Path,
) -> InputValue | None:
    src_outs = completed_outputs.get(binding.from_node, {})
    out_val = src_outs.get(binding.output)
    if out_val is None:
        return None

    if isinstance(out_val, ResultFileValue):
        return materialize_input_file(
            dst_node_dir=dst_node_dir,
            port_name=port_name,
            sha256=out_val.sha256,
            size_bytes=out_val.size_bytes,
            filename=out_val.filename,
            blob_store=blob_store,
        )
    if isinstance(out_val, OutputFileValue):
        src_file = (
            workspace_root
            / ".plynx"
            / "runs"
            / dst_node_dir.parent.parent.name
            / "nodes"
            / binding.from_node
            / out_val.path
        )
        sha, size = blob_store.put_file(src_file)
        return materialize_input_file(
            dst_node_dir=dst_node_dir,
            port_name=port_name,
            sha256=sha,
            size_bytes=size,
            filename=src_file.name,
            blob_store=blob_store,
        )
    if isinstance(out_val, ResultDirectoryValue):
        return materialize_input_directory(
            dst_node_dir=dst_node_dir,
            port_name=port_name,
            result_dir=out_val,
            blob_store=blob_store,
        )
    if isinstance(out_val, OutputDirectoryValue):
        src_dir = (
            workspace_root
            / ".plynx"
            / "runs"
            / dst_node_dir.parent.parent.name
            / "nodes"
            / binding.from_node
            / out_val.path
        )
        res_dir = ingest_directory(src_dir, blob_store)
        return materialize_input_directory(
            dst_node_dir=dst_node_dir,
            port_name=port_name,
            result_dir=res_dir,
            blob_store=blob_store,
        )
    if isinstance(out_val, ScalarValue):
        return ScalarValue(value=out_val.value)
    return None


def _materialize_literal_binding(
    *,
    node_id: str,
    port_name: str,
    binding: Any,
    expected_type: str | None,
    dst_node_dir: Path,
    blob_store: BlobStore,
    workspace_root: Path,
) -> InputValue:
    if expected_type == "file" and isinstance(binding, (str, Path)):
        if not str(binding).strip():
            raise FileNotFoundError(f"Input '{node_id}.{port_name}': empty file path")
        raw_path = Path(binding)
        file_path = raw_path if raw_path.is_absolute() else (workspace_root / raw_path).resolve()
        if not file_path.is_file():
            raise FileNotFoundError(f"Input '{node_id}.{port_name}': file not found: {binding}")
        sha, size = blob_store.put_file(file_path, allow_hardlink=False)
        return materialize_input_file(
            dst_node_dir=dst_node_dir,
            port_name=port_name,
            sha256=sha,
            size_bytes=size,
            filename=file_path.name,
            blob_store=blob_store,
        )
    if expected_type == "directory" and isinstance(binding, (str, Path)):
        if not str(binding).strip():
            raise FileNotFoundError(f"Input '{node_id}.{port_name}': empty directory path")
        raw_path = Path(binding)
        dir_path = raw_path if raw_path.is_absolute() else (workspace_root / raw_path).resolve()
        if not dir_path.is_dir():
            raise FileNotFoundError(
                f"Input '{node_id}.{port_name}': directory not found: {binding}"
            )
        res_dir = ingest_directory(dir_path, blob_store, allow_hardlink=False)
        return materialize_input_directory(
            dst_node_dir=dst_node_dir,
            port_name=port_name,
            result_dir=res_dir,
            blob_store=blob_store,
        )
    return ScalarValue(value=binding)


def materialize_inputs(
    *,
    node_id: str,
    spec: NodeSpec,
    dst_node_dir: Path,
    completed_outputs: Mapping[str, Mapping[str, ResultValue | OutputValue]],
    blob_store: BlobStore,
    workspace_root: Path,
    registry: OpRegistry | None = None,
    run_inputs: Mapping[str, Any] | None = None,
    answers: Mapping[str, str] | None = None,
    db_checkpoints: Sequence[CheckpointState] | None = None,
) -> InputsManifest:
    """Resolve and materialize all inputs for a node into its ``inputs/`` directory.

    Preserves original file extensions and filenames, makes inputs read-only,
    and returns a validated ``InputsManifest``.
    """
    op_entry = registry.get(spec.op) if registry is not None else None
    port_types: dict[str, str] = {}
    resolved_inputs: dict[str, InputValue] = {}
    if op_entry is not None:
        for port in op_entry.inputs:
            port_types[port.name] = port.type
            if not port.required and port.default is not None:
                resolved_inputs[port.name] = ScalarValue(value=port.default)

    # 1. Resolve bindings from workflow node spec
    for port_name, binding in spec.inputs.items():
        if isinstance(binding, NodeRef):
            ref_val = _materialize_node_ref(
                port_name=port_name,
                binding=binding,
                dst_node_dir=dst_node_dir,
                completed_outputs=completed_outputs,
                blob_store=blob_store,
                workspace_root=workspace_root,
            )
            if ref_val is not None:
                resolved_inputs[port_name] = ref_val
        else:
            expected_type = _resolve_expected_port_type(port_name, port_types, op_entry)
            resolved_inputs[port_name] = _materialize_literal_binding(
                node_id=node_id,
                port_name=port_name,
                binding=binding,
                expected_type=expected_type,
                dst_node_dir=dst_node_dir,
                blob_store=blob_store,
                workspace_root=workspace_root,
            )

    # 2. Overrides from run_inputs (CLI --set, --input)
    if run_inputs:
        prefix = f"{node_id}."
        for key, raw_val in run_inputs.items():
            if key.startswith(prefix):
                port_name = key[len(prefix) :]
                expected_type = _resolve_expected_port_type(port_name, port_types, op_entry)
                resolved_inputs[port_name] = _materialize_literal_binding(
                    node_id=node_id,
                    port_name=port_name,
                    binding=raw_val,
                    expected_type=expected_type,
                    dst_node_dir=dst_node_dir,
                    blob_store=blob_store,
                    workspace_root=workspace_root,
                )

    # 3. Checkpoint answers
    cp_answers: dict[str, str] = {}
    if answers:
        prefix = f"{node_id}."
        for key, ans in answers.items():
            if key.startswith(prefix):
                cp_answers[key[len(prefix) :]] = ans

    if db_checkpoints:
        for cp in db_checkpoints:
            if cp.node_id == node_id and cp.answer is not None:
                cp_answers[cp.checkpoint_id] = cp.answer

    return InputsManifest(inputs=resolved_inputs, checkpoint_answers=cp_answers)
