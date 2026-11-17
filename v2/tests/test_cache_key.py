"""Tests for cache key computation (PROTOCOL.md section 6, PLAN.md task 3.4)."""

from __future__ import annotations

from pathlib import Path

from plynx.cas import (
    canonical_json,
    compute_cache_key,
    compute_cache_key_raw,
    compute_inputs_hash,
    compute_params_hash,
    hash_bytes,
)
from plynx_sdk.protocol import (
    InputDirectoryValue,
    InputFileValue,
    InputsManifest,
    ScalarValue,
)


def test_golden_cache_key() -> None:
    """Accept: golden test with a fixed expected hash."""
    op_entrypoint = "standard_io/demo:Echo"
    file_sha256 = "11" * 32
    uv_lock_sha256 = "22" * 32
    inputs_hash = hash_bytes(canonical_json({"doc": "33" * 32}).encode("utf-8"))
    params_hash = hash_bytes(
        canonical_json({"text": "hello", "__checkpoint_answers__": {"cp_0": "foo"}}).encode("utf-8")
    )

    key = compute_cache_key_raw(
        op_entrypoint=op_entrypoint,
        file_sha256=file_sha256,
        uv_lock_sha256=uv_lock_sha256,
        inputs_hash=inputs_hash,
        params_hash=params_hash,
    )

    # Fixed expected hash calculated from the exact PROTOCOL.md formula
    expected_golden = "66e2c855bc1ae575485f30096ac1f3e23ba8ae2fc17511601900bbb10960652a"
    assert key == expected_golden


def test_each_component_change_alters_the_key() -> None:
    """Accept: each component change alters the key."""
    base_kwargs = {
        "op_entrypoint": "standard_io/demo:Echo",
        "file_sha256": "11" * 32,
        "uv_lock_sha256": "22" * 32,
        "inputs_hash": compute_inputs_hash({"file": "33" * 32}),
        "params_hash": compute_params_hash({"text": "hi"}, checkpoint_answers={"cp_0": "1"}),
    }
    base_key = compute_cache_key_raw(**base_kwargs)

    # 1. Change op_entrypoint
    k1 = compute_cache_key_raw(**{**base_kwargs, "op_entrypoint": "standard_io/demo:Concat"})
    assert k1 != base_key

    # 2. Change file_sha256 (source file of op)
    k2 = compute_cache_key_raw(**{**base_kwargs, "file_sha256": "aa" * 32})
    assert k2 != base_key

    # 3. Change uv_lock_sha256
    k3 = compute_cache_key_raw(**{**base_kwargs, "uv_lock_sha256": "bb" * 32})
    assert k3 != base_key

    # 4. Change inputs_hash
    k4 = compute_cache_key_raw(
        **{**base_kwargs, "inputs_hash": compute_inputs_hash({"file": "44" * 32})}
    )
    assert k4 != base_key

    # 5. Change params_hash via scalar value
    k5 = compute_cache_key_raw(
        **{
            **base_kwargs,
            "params_hash": compute_params_hash(
                {"text": "different"},
                checkpoint_answers={"cp_0": "1"},
            ),
        }
    )
    assert k5 != base_key

    # 6. Change params_hash via checkpoint answer
    k6 = compute_cache_key_raw(
        **{
            **base_kwargs,
            "params_hash": compute_params_hash({"text": "hi"}, checkpoint_answers={"cp_0": "2"}),
        }
    )
    assert k6 != base_key


def test_unrelated_file_change_in_pack_does_not_alter_key(tmp_path: Path) -> None:
    """Accept: a change in an unrelated file of the pack does not alter the key."""
    pack_dir = tmp_path / "my_pack"
    pack_dir.mkdir()
    op_file = pack_dir / "my_op.py"
    op_file.write_text("class MyOp:\n    pass\n", encoding="utf-8")
    uv_lock = pack_dir / "uv.lock"
    uv_lock.write_text("lockfile v1\n", encoding="utf-8")
    unrelated_file = pack_dir / "helper.py"
    unrelated_file.write_text("def helper(): return 42\n", encoding="utf-8")

    inputs = InputsManifest(
        inputs={
            "f": InputFileValue(path="inputs/f/file.txt", sha256="aa" * 32, size_bytes=10),
            "d": InputDirectoryValue(path="inputs/d", tree_sha256="bb" * 32),
            "p": ScalarValue(value="param_val"),
        }
    )

    key_before = compute_cache_key(
        op_entrypoint="my_pack/my_op:MyOp",
        op_source_file=op_file,
        inputs=inputs,
        pack_dir=pack_dir,
    )

    # Modify unrelated file in the pack
    unrelated_file.write_text("def helper(): return 9999\n# added comments\n", encoding="utf-8")
    (pack_dir / "README.md").write_text("# Doc\n", encoding="utf-8")

    key_after = compute_cache_key(
        op_entrypoint="my_pack/my_op:MyOp",
        op_source_file=op_file,
        inputs=inputs,
        pack_dir=pack_dir,
    )

    # Key must be completely identical
    assert key_before == key_after

    # But modifying the op file itself DOES change the key
    op_file.write_text("class MyOp:\n    # changed\n    pass\n", encoding="utf-8")
    key_op_changed = compute_cache_key(
        op_entrypoint="my_pack/my_op:MyOp",
        op_source_file=op_file,
        inputs=inputs,
        pack_dir=pack_dir,
    )
    assert key_op_changed != key_before
