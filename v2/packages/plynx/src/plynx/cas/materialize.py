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
    )


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
    port_defaults: dict[str, Any] = {}
    if op_entry is not None:
        for port in op_entry.inputs:
            port_types[port.name] = port.type
            if not port.required and port.default is not None:
                port_defaults[port.name] = port.default

    resolved_inputs: dict[str, InputValue] = {}
    for port_name, default_val in port_defaults.items():
        resolved_inputs[port_name] = ScalarValue(value=default_val)

    # 1. Resolve bindings from workflow node spec
    for port_name, binding in spec.inputs.items():
        expected_type = port_types.get(port_name)

        if isinstance(binding, NodeRef):
            src_outs = completed_outputs.get(binding.from_node, {})
            out_val = src_outs.get(binding.output)
            if out_val is None:
                continue

            if isinstance(out_val, ResultFileValue):
                resolved_inputs[port_name] = materialize_input_file(
                    dst_node_dir=dst_node_dir,
                    port_name=port_name,
                    sha256=out_val.sha256,
                    size_bytes=out_val.size_bytes,
                    filename=out_val.filename,
                    blob_store=blob_store,
                )
            elif isinstance(out_val, OutputFileValue):
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
                fname = src_file.name
                resolved_inputs[port_name] = materialize_input_file(
                    dst_node_dir=dst_node_dir,
                    port_name=port_name,
                    sha256=sha,
                    size_bytes=size,
                    filename=fname,
                    blob_store=blob_store,
                )
            elif isinstance(out_val, ResultDirectoryValue):
                resolved_inputs[port_name] = materialize_input_directory(
                    dst_node_dir=dst_node_dir,
                    port_name=port_name,
                    result_dir=out_val,
                    blob_store=blob_store,
                )
            elif isinstance(out_val, OutputDirectoryValue):
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
                resolved_inputs[port_name] = materialize_input_directory(
                    dst_node_dir=dst_node_dir,
                    port_name=port_name,
                    result_dir=res_dir,
                    blob_store=blob_store,
                )
            elif isinstance(out_val, ScalarValue):
                resolved_inputs[port_name] = ScalarValue(value=out_val.value)
        else:
            # Literal binding
            if expected_type == "file" and isinstance(binding, (str, Path)):
                file_path = (workspace_root / binding).resolve()
                if file_path.is_file():
                    sha, size = blob_store.put_file(file_path)
                    resolved_inputs[port_name] = materialize_input_file(
                        dst_node_dir=dst_node_dir,
                        port_name=port_name,
                        sha256=sha,
                        size_bytes=size,
                        filename=file_path.name,
                        blob_store=blob_store,
                    )
                else:
                    resolved_inputs[port_name] = ScalarValue(value=str(binding))
            elif expected_type == "directory" and isinstance(binding, (str, Path)):
                dir_path = (workspace_root / binding).resolve()
                if dir_path.is_dir():
                    res_dir = ingest_directory(dir_path, blob_store)
                    resolved_inputs[port_name] = materialize_input_directory(
                        dst_node_dir=dst_node_dir,
                        port_name=port_name,
                        result_dir=res_dir,
                        blob_store=blob_store,
                    )
                else:
                    resolved_inputs[port_name] = ScalarValue(value=str(binding))
            else:
                resolved_inputs[port_name] = ScalarValue(value=binding)

    # 2. Overrides from run_inputs (CLI --set, --input)
    if run_inputs:
        prefix = f"{node_id}."
        for key, raw_val in run_inputs.items():
            if key.startswith(prefix):
                port_name = key[len(prefix) :]
                expected_type = port_types.get(port_name)
                if expected_type == "file" and isinstance(raw_val, (str, Path)):
                    file_path = (
                        Path(raw_val)
                        if Path(raw_val).is_absolute()
                        else (workspace_root / raw_val).resolve()
                    )
                    if file_path.is_file():
                        sha, size = blob_store.put_file(file_path)
                        resolved_inputs[port_name] = materialize_input_file(
                            dst_node_dir=dst_node_dir,
                            port_name=port_name,
                            sha256=sha,
                            size_bytes=size,
                            filename=file_path.name,
                            blob_store=blob_store,
                        )
                        continue
                elif expected_type == "directory" and isinstance(raw_val, (str, Path)):
                    dir_path = (
                        Path(raw_val)
                        if Path(raw_val).is_absolute()
                        else (workspace_root / raw_val).resolve()
                    )
                    if dir_path.is_dir():
                        res_dir = ingest_directory(dir_path, blob_store)
                        resolved_inputs[port_name] = materialize_input_directory(
                            dst_node_dir=dst_node_dir,
                            port_name=port_name,
                            result_dir=res_dir,
                            blob_store=blob_store,
                        )
                        continue

                resolved_inputs[port_name] = ScalarValue(value=raw_val)

    # 3. Checkpoint answers
    cp_answers: dict[str, str] = {}
    if answers:
        prefix = f"{node_id}."
        for key, ans in answers.items():
            if key.startswith(prefix):
                cp_id = key[len(prefix) :]
                cp_answers[cp_id] = ans

    if db_checkpoints:
        for cp in db_checkpoints:
            if cp.node_id == node_id and cp.answer is not None:
                cp_answers[cp.checkpoint_id] = cp.answer

    return InputsManifest(inputs=resolved_inputs, checkpoint_answers=cp_answers)
