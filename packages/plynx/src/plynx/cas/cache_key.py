"""Cache key computation per PROTOCOL.md section 6."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from plynx_sdk.protocol import (
    CheckpointAnswer,
    InputDirectoryValue,
    InputFileValue,
    InputsManifest,
    ScalarValue,
)

from plynx.cas.blob_store import hash_bytes, hash_file


def canonical_json(data: Any) -> str:
    """Serialize data to canonical JSON: sorted keys, separators (',', ':'), UTF-8 characters."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_inputs_hash(file_and_dir_hashes: Mapping[str, str]) -> str:
    """Compute inputs_hash = sha256 of canonical JSON of {port: sha256 | tree_sha256}."""
    text = canonical_json(dict(file_and_dir_hashes))
    return hash_bytes(text.encode("utf-8"))


def compute_params_hash(
    params: Mapping[str, Any],
    *,
    checkpoint_answers: Mapping[str, CheckpointAnswer] | None = None,
) -> str:
    """Compute params_hash = sha256 of canonical JSON of {port: value}.

    Includes __checkpoint_answers__ when answers exist.
    """
    data = dict(params)
    if checkpoint_answers:
        data["__checkpoint_answers__"] = dict(checkpoint_answers)
    text = canonical_json(data)
    return hash_bytes(text.encode("utf-8"))


def compute_cache_key_raw(
    *,
    op_entrypoint: str,
    file_sha256: str,
    uv_lock_sha256: str = "",
    inputs_hash: str,
    params_hash: str,
) -> str:
    """Compute cache_key per PROTOCOL.md section 6.

    cache_key = sha256("\\n".join([
      "plynx-cache-1",
      op_entrypoint,
      file_sha256,
      uv_lock_sha256,
      inputs_hash,
      params_hash,
    ]))
    """
    lines = [
        "plynx-cache-1",
        op_entrypoint,
        file_sha256,
        uv_lock_sha256,
        inputs_hash,
        params_hash,
    ]
    return hash_bytes("\n".join(lines).encode("utf-8"))


def compute_cache_key(
    *,
    op_entrypoint: str,
    op_source_file: Path,
    inputs: InputsManifest,
    pack_dir: Path | None = None,
    uv_lock_path: Path | None = None,
) -> str:
    """Compute the cache key for a node attempt given its source file, inputs, and pack uv.lock."""
    file_sha256, _ = hash_file(op_source_file)

    uv_lock_sha256 = ""
    lock_file = uv_lock_path
    if lock_file is None and pack_dir is not None:
        direct = pack_dir / "uv.lock"
        if direct.is_file():
            lock_file = direct
    if lock_file is not None and lock_file.is_file():
        uv_lock_sha256, _ = hash_file(lock_file)

    file_and_dir_hashes: dict[str, str] = {}
    scalar_params: dict[str, Any] = {}
    for port_name, inp_val in inputs.inputs.items():
        if isinstance(inp_val, InputFileValue):
            file_and_dir_hashes[port_name] = inp_val.sha256
        elif isinstance(inp_val, InputDirectoryValue):
            file_and_dir_hashes[port_name] = inp_val.tree_sha256
        elif isinstance(inp_val, ScalarValue):
            scalar_params[port_name] = inp_val.value

    inputs_hash = compute_inputs_hash(file_and_dir_hashes)
    params_hash = compute_params_hash(scalar_params, checkpoint_answers=inputs.checkpoint_answers)

    return compute_cache_key_raw(
        op_entrypoint=op_entrypoint,
        file_sha256=file_sha256,
        uv_lock_sha256=uv_lock_sha256,
        inputs_hash=inputs_hash,
        params_hash=params_hash,
    )
