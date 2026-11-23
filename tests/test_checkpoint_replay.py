"""Tests for Task 1.3: ``checkpoint()`` interrupt, ``checkpoint.json``, exit 10, and replay."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from plynx_sdk.protocol import (
    CheckpointManifest,
    InputsManifest,
    OutputsManifest,
    ScalarValue,
)

SDK_SRC = Path(__file__).resolve().parent.parent / "packages" / "plynx-sdk" / "src"

CHECKPOINT_FIXTURE_CODE = '''"""Fixture ops for checkpoint interrupt and replay tests."""

from __future__ import annotations

from typing import TypedDict

from plynx_sdk import Op, checkpoint, op


class AskFooOrWoo(Op):
    """Ask the user foo or woo, inside a try/except Exception block."""

    TITLE = "Ask foo or woo"
    CATEGORY = "Demo"
    CACHEABLE = False

    class Outputs(TypedDict):
        choice: str

    def run(self, prompt: str = "foo or woo?") -> Outputs:
        try:
            answer = self.checkpoint(
                prompt,
                options=["foo", "woo"],
                allow_freeform=False,
            )
        except Exception:
            # Must NEVER swallow CheckpointInterrupt (which is a BaseException).
            return {"choice": "swallowed_by_except_exception"}
        return {"choice": answer}


class TwoStepOut(TypedDict):
    """Outputs for two-checkpoint function op."""

    combined: str


@op(title="Two step ask", cacheable=False)
def two_step_ask() -> TwoStepOut:
    """Ask two questions in sequence to verify call-index IDs (cp_0, cp_1)."""
    first = checkpoint("First choice?", options=["a", "b"])
    second = checkpoint("Second freeform?", allow_freeform=True)
    return {"combined": f"{first}:{second}"}
'''


def _setup_checkpoint_pack(base_dir: Path) -> Path:
    pack_src = base_dir / "cp_pack_src"
    pkg_dir = pack_src / "cp_pack"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (pkg_dir / "ops.py").write_text(CHECKPOINT_FIXTURE_CODE, encoding="utf-8")
    return pack_src


def _invoke_harness(
    pack_src: Path,
    op_spec: str,
    node_dir: Path,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    parts = [str(SDK_SRC), str(pack_src)]
    if env.get("PYTHONPATH"):
        parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(parts)

    return subprocess.run(
        [
            sys.executable,
            "-m",
            "plynx_sdk.harness",
            "--op",
            op_spec,
            "--dir",
            str(node_dir),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_ask_foo_or_woo_exits_10_then_replays_answer(tmp_path: Path) -> None:
    """Fixture op asking 'foo or woo?' exits 10 first and returns answer on second run;
    except Exception in the op does not swallow the interrupt.
    """
    pack_src = _setup_checkpoint_pack(tmp_path)
    node_dir = tmp_path / "node_pick"
    node_dir.mkdir()

    # Attempt 1: no answers -> exits 10 and writes checkpoint.json
    inputs_1 = InputsManifest(inputs={"prompt": ScalarValue(value="foo or woo?")})
    (node_dir / "inputs.json").write_text(inputs_1.to_json(), encoding="utf-8")

    proc_1 = _invoke_harness(pack_src, "cp_pack.ops:AskFooOrWoo", node_dir)
    assert proc_1.returncode == 10, f"stderr={proc_1.stderr}"
    assert not (node_dir / "outputs.json").exists()
    cp_path = node_dir / "checkpoint.json"
    assert cp_path.is_file()
    cp_manifest = CheckpointManifest.from_json(cp_path.read_text(encoding="utf-8"))
    assert cp_manifest.checkpoint_id == "cp_0"
    assert cp_manifest.question == "foo or woo?"
    assert cp_manifest.options == ["foo", "woo"]
    assert cp_manifest.allow_freeform is False

    # Attempt 2: replay with cp_0="foo" -> exits 0 and writes outputs.json
    inputs_2 = InputsManifest(
        inputs={"prompt": ScalarValue(value="foo or woo?")},
        checkpoint_answers={"cp_0": "foo"},
    )
    (node_dir / "inputs.json").write_text(inputs_2.to_json(), encoding="utf-8")

    proc_2 = _invoke_harness(pack_src, "cp_pack.ops:AskFooOrWoo", node_dir)
    assert proc_2.returncode == 0, f"stderr={proc_2.stderr}"
    outputs = OutputsManifest.from_json((node_dir / "outputs.json").read_text(encoding="utf-8"))
    assert outputs.outputs == {"choice": ScalarValue(value="foo")}


def test_multiple_checkpoints_by_call_index(tmp_path: Path) -> None:
    """Multiple checkpoint() calls receive sequential IDs cp_0, cp_1 and replay in order."""
    pack_src = _setup_checkpoint_pack(tmp_path)
    node_dir = tmp_path / "node_two_step"
    node_dir.mkdir()

    # Attempt 1: stops at cp_0
    (node_dir / "inputs.json").write_text(InputsManifest().to_json(), encoding="utf-8")
    p1 = _invoke_harness(pack_src, "cp_pack.ops:two_step_ask", node_dir)
    assert p1.returncode == 10
    cp0 = CheckpointManifest.from_json((node_dir / "checkpoint.json").read_text(encoding="utf-8"))
    assert cp0.checkpoint_id == "cp_0"
    assert cp0.question == "First choice?"

    # Attempt 2: cp_0 answered, stops at cp_1
    (node_dir / "inputs.json").write_text(
        InputsManifest(checkpoint_answers={"cp_0": "b"}).to_json(),
        encoding="utf-8",
    )
    p2 = _invoke_harness(pack_src, "cp_pack.ops:two_step_ask", node_dir)
    assert p2.returncode == 10
    cp1 = CheckpointManifest.from_json((node_dir / "checkpoint.json").read_text(encoding="utf-8"))
    assert cp1.checkpoint_id == "cp_1"
    assert cp1.question == "Second freeform?"
    assert cp1.allow_freeform is True

    # Attempt 3: both cp_0 and cp_1 answered, finishes with exit 0
    (node_dir / "inputs.json").write_text(
        InputsManifest(checkpoint_answers={"cp_0": "b", "cp_1": "custom"}).to_json(),
        encoding="utf-8",
    )
    p3 = _invoke_harness(pack_src, "cp_pack.ops:two_step_ask", node_dir)
    assert p3.returncode == 0, f"stderr={p3.stderr}"
    outputs = OutputsManifest.from_json((node_dir / "outputs.json").read_text(encoding="utf-8"))
    assert outputs.outputs == {"combined": ScalarValue(value="b:custom")}
