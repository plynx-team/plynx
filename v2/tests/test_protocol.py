"""Tests for ``plynx_sdk.protocol`` wire manifest dataclasses and validation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Protocol

import pytest
from plynx_sdk.protocol import (
    MAX_SCALAR_BYTES,
    CheckpointManifest,
    DirectoryEntry,
    InputDirectoryValue,
    InputFileValue,
    InputsManifest,
    OutputDirectoryValue,
    OutputFileValue,
    OutputsManifest,
    ProtocolError,
    ResultDirectoryValue,
    ResultFileValue,
    ResultManifest,
    ScalarValue,
)

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
PROTOCOL_DOC = ROOT / "docs" / "PROTOCOL.md"


class _ManifestType(Protocol):
    @classmethod
    def from_json(cls, raw: str | bytes) -> _ManifestInstance: ...


class _ManifestInstance(Protocol):
    def to_json(self) -> str: ...


MANIFEST_FIXTURES: list[tuple[str, type[_ManifestType]]] = [
    ("inputs.json", InputsManifest),
    ("outputs.json", OutputsManifest),
    ("result.json", ResultManifest),
    ("checkpoint.json", CheckpointManifest),
]


@pytest.mark.parametrize(("filename", "manifest_cls"), MANIFEST_FIXTURES)
def test_section5_fixtures_round_trip_unchanged(
    filename: str,
    manifest_cls: type[_ManifestType],
) -> None:
    """Every JSON example from PROTOCOL.md section 5 round-trips unchanged."""
    raw = (FIXTURES / filename).read_text(encoding="utf-8")
    parsed = manifest_cls.from_json(raw)
    serialized = parsed.to_json()
    assert serialized == raw
    assert json.loads(serialized) == json.loads(raw)
    assert manifest_cls.from_json(serialized.encode("utf-8")) == parsed


def test_fixtures_match_protocol_md_section5() -> None:
    """Fixtures in tests/fixtures/ match the JSON examples in PROTOCOL.md section 5."""
    doc = PROTOCOL_DOC.read_text(encoding="utf-8")
    sec5_start = doc.index("## 5. IPC between engine and child")
    sec6_start = doc.index("## 6. Cache key")
    sec5 = doc[sec5_start:sec6_start]
    blocks = re.findall(r"```json\n(.*?)\n```", sec5, flags=re.DOTALL)
    assert len(blocks) == len(MANIFEST_FIXTURES)
    for block, (filename, manifest_cls) in zip(blocks, MANIFEST_FIXTURES, strict=True):
        fixture_raw = (FIXTURES / filename).read_text(encoding="utf-8")
        assert json.loads(block) == json.loads(fixture_raw)
        round_tripped = manifest_cls.from_json(block).to_json()
        assert round_tripped == fixture_raw


def test_invalid_fixture_missing_schema_rejected() -> None:
    """Manifests missing the schema field are rejected."""
    raw = (FIXTURES / "invalid_missing_schema.json").read_text(encoding="utf-8")
    with pytest.raises(ProtocolError, match="schema"):
        InputsManifest.from_json(raw)


@pytest.mark.parametrize("bad_schema", [0, 2, True, "1", None])
def test_invalid_schema_values_rejected(bad_schema: object) -> None:
    """Only integer schema == 1 is accepted."""
    payload = json.dumps({"schema": bad_schema, "inputs": {}})
    with pytest.raises(ProtocolError, match="schema"):
        InputsManifest.from_json(payload)


def test_invalid_fixture_path_dotdot_rejected() -> None:
    """Paths containing '..' are rejected."""
    raw = (FIXTURES / "invalid_path_dotdot.json").read_text(encoding="utf-8")
    with pytest.raises(ProtocolError, match="path"):
        InputsManifest.from_json(raw)


@pytest.mark.parametrize(
    "bad_path",
    [
        "",
        "..",
        "../secret.txt",
        "inputs/../../secret.txt",
        "inputs/doc/..",
        "/abs/path.txt",
        "inputs\\doc\\file.txt",
        "C:/Users/doc.txt",
        "C:\\Users\\doc.txt",
        "./inputs/doc.txt",
        "inputs//doc.txt",
        "inputs/",
    ],
)
def test_invalid_relative_paths_rejected(bad_path: str) -> None:
    """All manifest file and directory paths reject traversal, backslashes, drives, and roots."""
    with pytest.raises(ProtocolError, match="path"):
        InputFileValue(path=bad_path, sha256="abc", size_bytes=1)
    with pytest.raises(ProtocolError, match="path"):
        InputDirectoryValue(path=bad_path, tree_sha256="abc")
    with pytest.raises(ProtocolError, match="path"):
        OutputFileValue(path=bad_path)
    with pytest.raises(ProtocolError, match="path"):
        OutputDirectoryValue(path=bad_path)
    with pytest.raises(ProtocolError, match="path"):
        DirectoryEntry(path=bad_path, sha256="abc", size_bytes=1)


def test_scalar_over_1_mib_rejected() -> None:
    """A scalar whose UTF-8 JSON exceeds 1 MiB is rejected on init and from_json."""
    # Quotes add 2 bytes to the JSON string representation.
    exact_limit_str = "a" * (MAX_SCALAR_BYTES - 2)
    over_limit_str = "a" * (MAX_SCALAR_BYTES - 1)

    ok_val = ScalarValue(value=exact_limit_str)
    assert len(json.dumps(ok_val.value).encode("utf-8")) == MAX_SCALAR_BYTES

    with pytest.raises(ProtocolError, match="exceeds"):
        ScalarValue(value=over_limit_str)

    over_limit_fixture = json.dumps(
        {
            "schema": 1,
            "inputs": {"big": {"kind": "scalar", "value": over_limit_str}},
            "checkpoint_answers": {},
        }
    )
    with pytest.raises(ProtocolError, match="exceeds"):
        InputsManifest.from_json(over_limit_fixture)


def test_to_json_validates_mutated_instances() -> None:
    """Calling to_json() re-validates in case a dataclass field was mutated after construction."""
    manifest = InputsManifest(inputs={"a": ScalarValue(value="ok")})
    manifest.inputs["a"] = ScalarValue.from_dict({"kind": "scalar", "value": "ok"})
    manifest.schema = 99
    with pytest.raises(ProtocolError, match="schema"):
        manifest.to_json()


def test_unknown_fields_and_invalid_values_rejected() -> None:
    """Unknown keys, negative sizes, bad timestamps, and bad filenames are rejected."""
    with pytest.raises(ProtocolError, match="unknown"):
        CheckpointManifest.from_json(
            json.dumps(
                {
                    "schema": 1,
                    "checkpoint_id": "cp_0",
                    "question": "q?",
                    "options": ["a"],
                    "allow_freeform": False,
                    "extra": 1,
                }
            )
        )

    with pytest.raises(ProtocolError, match="size_bytes"):
        InputFileValue(path="inputs/a/b.txt", sha256="abc", size_bytes=-1)

    with pytest.raises(ProtocolError, match="finished_at"):
        OutputsManifest(started_at=10.0, finished_at=5.0, outputs={})

    with pytest.raises(ProtocolError, match="filename"):
        ResultFileValue(sha256="abc", size_bytes=1, media=None, filename="sub/file.txt")

    with pytest.raises(ProtocolError, match="checkpoint_id"):
        CheckpointManifest(checkpoint_id="bad_id", question="q?", options=["a"])


def test_result_directory_round_trip() -> None:
    """ResultDirectoryValue and ResultManifest round-trip through JSON."""
    result = ResultManifest(
        status="SUCCESS",
        cache_key="deadbeef",
        cache_hit=True,
        started_at=1.0,
        finished_at=2.0,
        outputs={
            "dir": ResultDirectoryValue(
                tree_sha256="cafebabe",
                entries=[DirectoryEntry(path="sub/a.txt", sha256="111", size_bytes=4)],
            )
        },
    )
    assert ResultManifest.from_json(result.to_json()) == result
