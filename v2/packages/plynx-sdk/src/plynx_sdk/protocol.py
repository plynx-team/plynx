"""IPC manifest dataclasses and validation for communication between engine and child.

Standard library only. All wire manifests carry ``"schema": 1`` and validate on construction,
``from_dict`` / ``from_json``, and ``to_dict`` / ``to_json``.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Final, Literal, TypeVar

_T = TypeVar("_T")

SCHEMA_VERSION: Final[int] = 1
MAX_SCALAR_BYTES: Final[int] = 1024 * 1024

ValueKind = Literal["scalar", "file", "directory"]
ScalarPrimitive = str | int | float | bool | None
JsonValue = ScalarPrimitive | list["JsonValue"] | dict[str, "JsonValue"]
ScalarData = str | int | float | bool | list[JsonValue] | dict[str, JsonValue] | None

_PORT_NAME_RE: Final[re.Pattern[str]] = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_CHECKPOINT_ID_RE: Final[re.Pattern[str]] = re.compile(r"^cp_[0-9]+$")


class ProtocolError(ValueError):
    """Raised when an IPC manifest or value fails validation."""


def _check_keys(
    data: Mapping[str, Any],
    *,
    required: set[str],
    optional: set[str] | None = None,
    context: str,
) -> None:
    allowed = required | (optional or set())
    missing = required - data.keys()
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ProtocolError(f"{context}: missing required field(s): {missing_list}")
    unknown = data.keys() - allowed
    if unknown:
        unknown_list = ", ".join(sorted(unknown))
        raise ProtocolError(f"{context}: unknown field(s): {unknown_list}")


def _validate_schema(schema: object, *, context: str) -> None:
    if isinstance(schema, bool) or not isinstance(schema, int):
        raise ProtocolError(f"{context}: 'schema' must be an int, got {type(schema).__name__}")
    if schema != SCHEMA_VERSION:
        raise ProtocolError(
            f"{context}: unsupported schema version {schema!r} (expected {SCHEMA_VERSION})"
        )


def _validate_non_empty_str(value: object, *, field_name: str, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProtocolError(f"{context}: '{field_name}' must be a non-empty str")
    return value


def _validate_non_negative_int(value: object, *, field_name: str, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ProtocolError(f"{context}: '{field_name}' must be a non-negative int")
    return value


def _validate_timestamp(value: object, *, field_name: str, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProtocolError(f"{context}: '{field_name}' must be a number")
    float_val = float(value)
    if not math.isfinite(float_val):
        raise ProtocolError(f"{context}: '{field_name}' must be finite")
    return float_val


def validate_relative_path(path: object, *, field_name: str = "path", context: str = "path") -> str:
    """Validate that ``path`` is a node-relative '/' path without ``..`` or drive letters."""
    if not isinstance(path, str) or not path:
        raise ProtocolError(f"{context}: '{field_name}' must be a non-empty str")
    if "\\" in path:
        raise ProtocolError(f"{context}: '{field_name}' must use '/' separators: {path!r}")
    if path.startswith("/"):
        raise ProtocolError(f"{context}: '{field_name}' must be relative, not absolute: {path!r}")
    if PureWindowsPath(path).drive or PurePosixPath(path).is_absolute():
        raise ProtocolError(f"{context}: '{field_name}' must not contain a drive or root: {path!r}")
    parts = path.split("/")
    for part in parts:
        if part in ("", ".", ".."):
            raise ProtocolError(
                f"{context}: '{field_name}' contains invalid segment {part!r}: {path!r}"
            )
    return path


def _validate_filename(filename: object, *, context: str) -> str:
    if not isinstance(filename, str) or not filename:
        raise ProtocolError(f"{context}: 'filename' must be a non-empty str")
    if "/" in filename or "\\" in filename or filename in (".", ".."):
        raise ProtocolError(f"{context}: 'filename' must be a single file name: {filename!r}")
    if PureWindowsPath(filename).drive:
        raise ProtocolError(f"{context}: 'filename' must not contain a drive letter: {filename!r}")
    return filename


def _validate_json_value(value: object, *, context: str) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ProtocolError(f"{context}: float scalar must be finite")
        return
    if isinstance(value, list):
        for item in value:
            _validate_json_value(item, context=context)
        return
    if isinstance(value, dict):
        for k, v in value.items():
            if not isinstance(k, str):
                raise ProtocolError(f"{context}: dict scalar keys must be str")
            _validate_json_value(v, context=context)
        return
    raise ProtocolError(f"{context}: unsupported scalar value type {type(value).__name__}")


def _validate_scalar_value(value: object, *, context: str) -> None:
    _validate_json_value(value, context=context)
    try:
        serialized = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProtocolError(f"{context}: scalar value is not JSON-serializable: {exc}") from exc
    if len(serialized) > MAX_SCALAR_BYTES:
        raise ProtocolError(
            f"{context}: scalar exceeds {MAX_SCALAR_BYTES} bytes ({len(serialized)} bytes)"
        )


def _loads_json_object(raw: str | bytes, *, context: str) -> dict[str, Any]:
    if isinstance(raw, bytes):
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProtocolError(f"{context}: invalid UTF-8: {exc}") from exc
    elif isinstance(raw, str):
        text = raw
    else:
        raise ProtocolError(f"{context}: expected str or bytes, got {type(raw).__name__}")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"{context}: invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ProtocolError(f"{context}: top-level JSON value must be an object")
    return parsed


def _dumps_json(data: Mapping[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


@dataclass
class ScalarValue:
    """A JSON-serializable scalar port value (at most 1 MiB serialized)."""

    value: ScalarData
    kind: Literal["scalar"] = "scalar"

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate this scalar value."""
        if self.kind != "scalar":
            raise ProtocolError(f"ScalarValue: 'kind' must be 'scalar', got {self.kind!r}")
        _validate_scalar_value(self.value, context="ScalarValue")

    def to_dict(self) -> dict[str, Any]:
        """Convert to a validated JSON-ready dictionary."""
        self.validate()
        return {"kind": self.kind, "value": self.value}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ScalarValue:
        """Validate and construct from a dictionary."""
        _check_keys(data, required={"kind", "value"}, context="ScalarValue")
        if data["kind"] != "scalar":
            raise ProtocolError(f"ScalarValue: expected kind 'scalar', got {data['kind']!r}")
        return cls(value=data["value"])

    def to_json(self) -> str:
        """Serialize to a validated JSON string."""
        return _dumps_json(self.to_dict())

    @classmethod
    def from_json(cls, raw: str | bytes) -> ScalarValue:
        """Deserialize and validate from a JSON string or UTF-8 bytes."""
        return cls.from_dict(_loads_json_object(raw, context="ScalarValue"))


@dataclass
class InputFileValue:
    """A materialized file input inside ``inputs.json``."""

    path: str
    sha256: str
    size_bytes: int
    kind: Literal["file"] = "file"

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate this input file value."""
        if self.kind != "file":
            raise ProtocolError(f"InputFileValue: 'kind' must be 'file', got {self.kind!r}")
        validate_relative_path(self.path, field_name="path", context="InputFileValue")
        _validate_non_empty_str(self.sha256, field_name="sha256", context="InputFileValue")
        _validate_non_negative_int(
            self.size_bytes, field_name="size_bytes", context="InputFileValue"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to a validated JSON-ready dictionary."""
        self.validate()
        return {
            "kind": self.kind,
            "path": self.path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> InputFileValue:
        """Validate and construct from a dictionary."""
        _check_keys(
            data,
            required={"kind", "path", "sha256", "size_bytes"},
            context="InputFileValue",
        )
        if data["kind"] != "file":
            raise ProtocolError(f"InputFileValue: expected kind 'file', got {data['kind']!r}")
        return cls(
            path=data["path"],
            sha256=data["sha256"],
            size_bytes=data["size_bytes"],
        )

    def to_json(self) -> str:
        """Serialize to a validated JSON string."""
        return _dumps_json(self.to_dict())

    @classmethod
    def from_json(cls, raw: str | bytes) -> InputFileValue:
        """Deserialize and validate from a JSON string or UTF-8 bytes."""
        return cls.from_dict(_loads_json_object(raw, context="InputFileValue"))


@dataclass
class InputDirectoryValue:
    """A materialized directory input inside ``inputs.json``."""

    path: str
    tree_sha256: str
    kind: Literal["directory"] = "directory"
    entries: list[DirectoryEntry] | None = None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate this input directory value."""
        if self.kind != "directory":
            raise ProtocolError(
                f"InputDirectoryValue: 'kind' must be 'directory', got {self.kind!r}"
            )
        validate_relative_path(self.path, field_name="path", context="InputDirectoryValue")
        _validate_non_empty_str(
            self.tree_sha256, field_name="tree_sha256", context="InputDirectoryValue"
        )
        if self.entries is not None:
            if not isinstance(self.entries, list):
                raise ProtocolError("InputDirectoryValue: 'entries' must be a list or None")
            for entry in self.entries:
                if not isinstance(entry, DirectoryEntry):
                    raise ProtocolError("InputDirectoryValue: every entry must be a DirectoryEntry")
                entry.validate()

    def to_dict(self) -> dict[str, Any]:
        """Convert to a validated JSON-ready dictionary."""
        self.validate()
        out: dict[str, Any] = {
            "kind": self.kind,
            "path": self.path,
            "tree_sha256": self.tree_sha256,
        }
        if self.entries is not None:
            out["entries"] = [e.to_dict() for e in self.entries]
        return out

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> InputDirectoryValue:
        """Validate and construct from a dictionary."""
        _check_keys(
            data,
            required={"kind", "path", "tree_sha256"},
            optional={"entries"},
            context="InputDirectoryValue",
        )
        if data["kind"] != "directory":
            raise ProtocolError(
                f"InputDirectoryValue: expected kind 'directory', got {data['kind']!r}"
            )
        raw_entries = data.get("entries")
        entries: list[DirectoryEntry] | None = None
        if raw_entries is not None:
            if not isinstance(raw_entries, list):
                raise ProtocolError("InputDirectoryValue: 'entries' must be a list")
            entries = [DirectoryEntry.from_dict(item) for item in raw_entries]
        return cls(path=data["path"], tree_sha256=data["tree_sha256"], entries=entries)

    def to_json(self) -> str:
        """Serialize to a validated JSON string."""
        return _dumps_json(self.to_dict())

    @classmethod
    def from_json(cls, raw: str | bytes) -> InputDirectoryValue:
        """Deserialize and validate from a JSON string or UTF-8 bytes."""
        return cls.from_dict(_loads_json_object(raw, context="InputDirectoryValue"))


@dataclass
class OutputFileValue:
    """A file output reported by the harness in ``outputs.json``."""

    path: str
    media: str | None = None
    kind: Literal["file"] = "file"

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate this output file value."""
        if self.kind != "file":
            raise ProtocolError(f"OutputFileValue: 'kind' must be 'file', got {self.kind!r}")
        validate_relative_path(self.path, field_name="path", context="OutputFileValue")
        if self.media is not None:
            _validate_non_empty_str(self.media, field_name="media", context="OutputFileValue")

    def to_dict(self) -> dict[str, Any]:
        """Convert to a validated JSON-ready dictionary."""
        self.validate()
        return {
            "kind": self.kind,
            "path": self.path,
            "media": self.media,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> OutputFileValue:
        """Validate and construct from a dictionary."""
        _check_keys(
            data,
            required={"kind", "path"},
            optional={"media"},
            context="OutputFileValue",
        )
        if data["kind"] != "file":
            raise ProtocolError(f"OutputFileValue: expected kind 'file', got {data['kind']!r}")
        return cls(path=data["path"], media=data.get("media"))

    def to_json(self) -> str:
        """Serialize to a validated JSON string."""
        return _dumps_json(self.to_dict())

    @classmethod
    def from_json(cls, raw: str | bytes) -> OutputFileValue:
        """Deserialize and validate from a JSON string or UTF-8 bytes."""
        return cls.from_dict(_loads_json_object(raw, context="OutputFileValue"))


@dataclass
class OutputDirectoryValue:
    """A directory output reported by the harness in ``outputs.json``."""

    path: str
    kind: Literal["directory"] = "directory"

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate this output directory value."""
        if self.kind != "directory":
            raise ProtocolError(
                f"OutputDirectoryValue: 'kind' must be 'directory', got {self.kind!r}"
            )
        validate_relative_path(self.path, field_name="path", context="OutputDirectoryValue")

    def to_dict(self) -> dict[str, Any]:
        """Convert to a validated JSON-ready dictionary."""
        self.validate()
        return {
            "kind": self.kind,
            "path": self.path,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> OutputDirectoryValue:
        """Validate and construct from a dictionary."""
        _check_keys(data, required={"kind", "path"}, context="OutputDirectoryValue")
        if data["kind"] != "directory":
            raise ProtocolError(
                f"OutputDirectoryValue: expected kind 'directory', got {data['kind']!r}"
            )
        return cls(path=data["path"])

    def to_json(self) -> str:
        """Serialize to a validated JSON string."""
        return _dumps_json(self.to_dict())

    @classmethod
    def from_json(cls, raw: str | bytes) -> OutputDirectoryValue:
        """Deserialize and validate from a JSON string or UTF-8 bytes."""
        return cls.from_dict(_loads_json_object(raw, context="OutputDirectoryValue"))


@dataclass
class DirectoryEntry:
    """A single file entry inside a ``ResultDirectoryValue``."""

    path: str
    sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate this directory entry."""
        validate_relative_path(self.path, field_name="path", context="DirectoryEntry")
        _validate_non_empty_str(self.sha256, field_name="sha256", context="DirectoryEntry")
        _validate_non_negative_int(
            self.size_bytes, field_name="size_bytes", context="DirectoryEntry"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to a validated JSON-ready dictionary."""
        self.validate()
        return {
            "path": self.path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DirectoryEntry:
        """Validate and construct from a dictionary."""
        if not isinstance(data, Mapping):
            raise ProtocolError("DirectoryEntry: expected mapping")
        _check_keys(data, required={"path", "sha256", "size_bytes"}, context="DirectoryEntry")
        return cls(
            path=data["path"],
            sha256=data["sha256"],
            size_bytes=data["size_bytes"],
        )

    def to_json(self) -> str:
        """Serialize to a validated JSON string."""
        return _dumps_json(self.to_dict())

    @classmethod
    def from_json(cls, raw: str | bytes) -> DirectoryEntry:
        """Deserialize and validate from a JSON string or UTF-8 bytes."""
        return cls.from_dict(_loads_json_object(raw, context="DirectoryEntry"))


@dataclass
class ResultFileValue:
    """An ingested file output recorded in ``result.json``."""

    sha256: str
    size_bytes: int
    media: str | None
    filename: str
    kind: Literal["file"] = "file"

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate this result file value."""
        if self.kind != "file":
            raise ProtocolError(f"ResultFileValue: 'kind' must be 'file', got {self.kind!r}")
        _validate_non_empty_str(self.sha256, field_name="sha256", context="ResultFileValue")
        _validate_non_negative_int(
            self.size_bytes, field_name="size_bytes", context="ResultFileValue"
        )
        if self.media is not None:
            _validate_non_empty_str(self.media, field_name="media", context="ResultFileValue")
        _validate_filename(self.filename, context="ResultFileValue")

    def to_dict(self) -> dict[str, Any]:
        """Convert to a validated JSON-ready dictionary."""
        self.validate()
        return {
            "kind": self.kind,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "media": self.media,
            "filename": self.filename,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ResultFileValue:
        """Validate and construct from a dictionary."""
        _check_keys(
            data,
            required={"kind", "sha256", "size_bytes", "filename"},
            optional={"media"},
            context="ResultFileValue",
        )
        if data["kind"] != "file":
            raise ProtocolError(f"ResultFileValue: expected kind 'file', got {data['kind']!r}")
        return cls(
            sha256=data["sha256"],
            size_bytes=data["size_bytes"],
            media=data.get("media"),
            filename=data["filename"],
        )

    def to_json(self) -> str:
        """Serialize to a validated JSON string."""
        return _dumps_json(self.to_dict())

    @classmethod
    def from_json(cls, raw: str | bytes) -> ResultFileValue:
        """Deserialize and validate from a JSON string or UTF-8 bytes."""
        return cls.from_dict(_loads_json_object(raw, context="ResultFileValue"))


@dataclass
class ResultDirectoryValue:
    """An ingested directory output recorded in ``result.json``."""

    tree_sha256: str
    entries: list[DirectoryEntry] = field(default_factory=list)
    kind: Literal["directory"] = "directory"

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate this result directory value."""
        if self.kind != "directory":
            raise ProtocolError(
                f"ResultDirectoryValue: 'kind' must be 'directory', got {self.kind!r}"
            )
        _validate_non_empty_str(
            self.tree_sha256, field_name="tree_sha256", context="ResultDirectoryValue"
        )
        if not isinstance(self.entries, list):
            raise ProtocolError("ResultDirectoryValue: 'entries' must be a list")
        for entry in self.entries:
            if not isinstance(entry, DirectoryEntry):
                raise ProtocolError(
                    "ResultDirectoryValue: each entry must be a DirectoryEntry instance"
                )
            entry.validate()

    def to_dict(self) -> dict[str, Any]:
        """Convert to a validated JSON-ready dictionary."""
        self.validate()
        return {
            "kind": self.kind,
            "tree_sha256": self.tree_sha256,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ResultDirectoryValue:
        """Validate and construct from a dictionary."""
        _check_keys(
            data,
            required={"kind", "tree_sha256", "entries"},
            context="ResultDirectoryValue",
        )
        if data["kind"] != "directory":
            raise ProtocolError(
                f"ResultDirectoryValue: expected kind 'directory', got {data['kind']!r}"
            )
        raw_entries = data["entries"]
        if not isinstance(raw_entries, list):
            raise ProtocolError("ResultDirectoryValue: 'entries' must be a list")
        entries = [DirectoryEntry.from_dict(item) for item in raw_entries]
        return cls(tree_sha256=data["tree_sha256"], entries=entries)

    def to_json(self) -> str:
        """Serialize to a validated JSON string."""
        return _dumps_json(self.to_dict())

    @classmethod
    def from_json(cls, raw: str | bytes) -> ResultDirectoryValue:
        """Deserialize and validate from a JSON string or UTF-8 bytes."""
        return cls.from_dict(_loads_json_object(raw, context="ResultDirectoryValue"))


InputValue = ScalarValue | InputFileValue | InputDirectoryValue
OutputValue = ScalarValue | OutputFileValue | OutputDirectoryValue
ResultValue = ScalarValue | ResultFileValue | ResultDirectoryValue


def _parse_kind_value(
    data: object,
    parsers: Mapping[str, type[_T]],
    *,
    context: str,
) -> _T:
    if not isinstance(data, Mapping):
        raise ProtocolError(f"{context}: expected an object")
    kind = data.get("kind")
    parser = parsers.get(kind) if isinstance(kind, str) else None
    if parser is not None:
        return parser.from_dict(data)  # type: ignore[attr-defined,no-any-return]
    raise ProtocolError(f"{context}: unknown kind {kind!r}")


def _parse_input_value(data: object, *, port: str) -> InputValue:
    parsers: dict[str, type[InputValue]] = {
        "scalar": ScalarValue,
        "file": InputFileValue,
        "directory": InputDirectoryValue,
    }
    return _parse_kind_value(data, parsers, context=f"InputsManifest.inputs[{port!r}]")


def _parse_output_value(data: object, *, port: str) -> OutputValue:
    parsers: dict[str, type[OutputValue]] = {
        "scalar": ScalarValue,
        "file": OutputFileValue,
        "directory": OutputDirectoryValue,
    }
    return _parse_kind_value(data, parsers, context=f"OutputsManifest.outputs[{port!r}]")


def _parse_result_value(data: object, *, port: str) -> ResultValue:
    parsers: dict[str, type[ResultValue]] = {
        "scalar": ScalarValue,
        "file": ResultFileValue,
        "directory": ResultDirectoryValue,
    }
    return _parse_kind_value(data, parsers, context=f"ResultManifest.outputs[{port!r}]")


def _validate_port_name(name: object, *, context: str) -> None:
    if not isinstance(name, str) or not _PORT_NAME_RE.match(name):
        raise ProtocolError(f"{context}: invalid port name {name!r}")


def _validate_checkpoint_id(checkpoint_id: object, *, context: str) -> None:
    if not isinstance(checkpoint_id, str) or not _CHECKPOINT_ID_RE.match(checkpoint_id):
        raise ProtocolError(
            f"{context}: invalid checkpoint_id {checkpoint_id!r} (expected 'cp_<n>')"
        )


@dataclass
class InputsManifest:
    """``inputs.json`` written by the engine before launching a child process."""

    inputs: dict[str, InputValue] = field(default_factory=dict)
    checkpoint_answers: dict[str, str] = field(default_factory=dict)
    schema: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate this ``InputsManifest``."""
        _validate_schema(self.schema, context="InputsManifest")
        if not isinstance(self.inputs, dict):
            raise ProtocolError("InputsManifest: 'inputs' must be a dict")
        for port, val in self.inputs.items():
            _validate_port_name(port, context="InputsManifest")
            if not isinstance(val, (ScalarValue, InputFileValue, InputDirectoryValue)):
                raise ProtocolError(
                    f"InputsManifest.inputs[{port!r}]: invalid value type {type(val).__name__}"
                )
        if not isinstance(self.checkpoint_answers, dict):
            raise ProtocolError("InputsManifest: 'checkpoint_answers' must be a dict")
        for cp_id, answer in self.checkpoint_answers.items():
            _validate_checkpoint_id(cp_id, context="InputsManifest.checkpoint_answers")
            if not isinstance(answer, str):
                raise ProtocolError(
                    f"InputsManifest.checkpoint_answers[{cp_id!r}]: answer must be a str"
                )

    def to_dict(self) -> dict[str, Any]:
        """Convert to a validated JSON-ready dictionary."""
        self.validate()
        return {
            "schema": self.schema,
            "inputs": {port: val.to_dict() for port, val in self.inputs.items()},
            "checkpoint_answers": dict(self.checkpoint_answers),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> InputsManifest:
        """Validate and construct from a dictionary."""
        _check_keys(
            data,
            required={"schema", "inputs"},
            optional={"checkpoint_answers"},
            context="InputsManifest",
        )
        _validate_schema(data["schema"], context="InputsManifest")
        raw_inputs = data["inputs"]
        if not isinstance(raw_inputs, Mapping):
            raise ProtocolError("InputsManifest: 'inputs' must be an object")
        inputs: dict[str, InputValue] = {}
        for port, raw_val in raw_inputs.items():
            _validate_port_name(port, context="InputsManifest")
            inputs[port] = _parse_input_value(raw_val, port=port)
        raw_answers = data.get("checkpoint_answers", {})
        if not isinstance(raw_answers, Mapping):
            raise ProtocolError("InputsManifest: 'checkpoint_answers' must be an object")
        answers: dict[str, str] = {}
        for cp_id, ans in raw_answers.items():
            _validate_checkpoint_id(cp_id, context="InputsManifest.checkpoint_answers")
            if not isinstance(ans, str):
                raise ProtocolError(
                    f"InputsManifest.checkpoint_answers[{cp_id!r}]: answer must be a str"
                )
            answers[cp_id] = ans
        return cls(inputs=inputs, checkpoint_answers=answers, schema=data["schema"])

    def to_json(self) -> str:
        """Serialize to a validated JSON string."""
        return _dumps_json(self.to_dict())

    @classmethod
    def from_json(cls, raw: str | bytes) -> InputsManifest:
        """Deserialize and validate from a JSON string or UTF-8 bytes."""
        return cls.from_dict(_loads_json_object(raw, context="InputsManifest"))


@dataclass
class OutputsManifest:
    """``outputs.json`` written by the child harness when an op succeeds."""

    started_at: float
    finished_at: float
    outputs: dict[str, OutputValue] = field(default_factory=dict)
    schema: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        self.started_at = _validate_timestamp(
            self.started_at, field_name="started_at", context="OutputsManifest"
        )
        self.finished_at = _validate_timestamp(
            self.finished_at, field_name="finished_at", context="OutputsManifest"
        )
        self.validate()

    def validate(self) -> None:
        """Validate this ``OutputsManifest``."""
        _validate_schema(self.schema, context="OutputsManifest")
        start = _validate_timestamp(
            self.started_at, field_name="started_at", context="OutputsManifest"
        )
        end = _validate_timestamp(
            self.finished_at, field_name="finished_at", context="OutputsManifest"
        )
        if end < start:
            raise ProtocolError(
                "OutputsManifest: 'finished_at' cannot be earlier than 'started_at'"
            )
        if not isinstance(self.outputs, dict):
            raise ProtocolError("OutputsManifest: 'outputs' must be a dict")
        for port, val in self.outputs.items():
            _validate_port_name(port, context="OutputsManifest")
            if not isinstance(val, (ScalarValue, OutputFileValue, OutputDirectoryValue)):
                raise ProtocolError(
                    f"OutputsManifest.outputs[{port!r}]: invalid value type {type(val).__name__}"
                )

    def to_dict(self) -> dict[str, Any]:
        """Convert to a validated JSON-ready dictionary."""
        self.validate()
        return {
            "schema": self.schema,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "outputs": {port: val.to_dict() for port, val in self.outputs.items()},
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> OutputsManifest:
        """Validate and construct from a dictionary."""
        _check_keys(
            data,
            required={"schema", "started_at", "finished_at", "outputs"},
            context="OutputsManifest",
        )
        _validate_schema(data["schema"], context="OutputsManifest")
        raw_outputs = data["outputs"]
        if not isinstance(raw_outputs, Mapping):
            raise ProtocolError("OutputsManifest: 'outputs' must be an object")
        outputs: dict[str, OutputValue] = {}
        for port, raw_val in raw_outputs.items():
            _validate_port_name(port, context="OutputsManifest")
            outputs[port] = _parse_output_value(raw_val, port=port)
        return cls(
            started_at=data["started_at"],
            finished_at=data["finished_at"],
            outputs=outputs,
            schema=data["schema"],
        )

    def to_json(self) -> str:
        """Serialize to a validated JSON string."""
        return _dumps_json(self.to_dict())

    @classmethod
    def from_json(cls, raw: str | bytes) -> OutputsManifest:
        """Deserialize and validate from a JSON string or UTF-8 bytes."""
        return cls.from_dict(_loads_json_object(raw, context="OutputsManifest"))


@dataclass
class ResultManifest:
    """``result.json`` written by the engine after ingesting outputs into the blob store."""

    status: str
    cache_key: str
    cache_hit: bool
    started_at: float
    finished_at: float
    outputs: dict[str, ResultValue] = field(default_factory=dict)
    schema: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        self.started_at = _validate_timestamp(
            self.started_at, field_name="started_at", context="ResultManifest"
        )
        self.finished_at = _validate_timestamp(
            self.finished_at, field_name="finished_at", context="ResultManifest"
        )
        self.validate()

    def validate(self) -> None:
        """Validate this ``ResultManifest``."""
        _validate_schema(self.schema, context="ResultManifest")
        _validate_non_empty_str(self.status, field_name="status", context="ResultManifest")
        _validate_non_empty_str(self.cache_key, field_name="cache_key", context="ResultManifest")
        if not isinstance(self.cache_hit, bool):
            raise ProtocolError("ResultManifest: 'cache_hit' must be a bool")
        start = _validate_timestamp(
            self.started_at, field_name="started_at", context="ResultManifest"
        )
        end = _validate_timestamp(
            self.finished_at, field_name="finished_at", context="ResultManifest"
        )
        if end < start:
            raise ProtocolError("ResultManifest: 'finished_at' cannot be earlier than 'started_at'")
        if not isinstance(self.outputs, dict):
            raise ProtocolError("ResultManifest: 'outputs' must be a dict")
        for port, val in self.outputs.items():
            _validate_port_name(port, context="ResultManifest")
            if not isinstance(val, (ScalarValue, ResultFileValue, ResultDirectoryValue)):
                raise ProtocolError(
                    f"ResultManifest.outputs[{port!r}]: invalid value type {type(val).__name__}"
                )

    def to_dict(self) -> dict[str, Any]:
        """Convert to a validated JSON-ready dictionary."""
        self.validate()
        return {
            "schema": self.schema,
            "status": self.status,
            "cache_key": self.cache_key,
            "cache_hit": self.cache_hit,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "outputs": {port: val.to_dict() for port, val in self.outputs.items()},
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ResultManifest:
        """Validate and construct from a dictionary."""
        _check_keys(
            data,
            required={
                "schema",
                "status",
                "cache_key",
                "cache_hit",
                "started_at",
                "finished_at",
                "outputs",
            },
            context="ResultManifest",
        )
        _validate_schema(data["schema"], context="ResultManifest")
        raw_outputs = data["outputs"]
        if not isinstance(raw_outputs, Mapping):
            raise ProtocolError("ResultManifest: 'outputs' must be an object")
        outputs: dict[str, ResultValue] = {}
        for port, raw_val in raw_outputs.items():
            _validate_port_name(port, context="ResultManifest")
            outputs[port] = _parse_result_value(raw_val, port=port)
        return cls(
            status=data["status"],
            cache_key=data["cache_key"],
            cache_hit=data["cache_hit"],
            started_at=data["started_at"],
            finished_at=data["finished_at"],
            outputs=outputs,
            schema=data["schema"],
        )

    def to_json(self) -> str:
        """Serialize to a validated JSON string."""
        return _dumps_json(self.to_dict())

    @classmethod
    def from_json(cls, raw: str | bytes) -> ResultManifest:
        """Deserialize and validate from a JSON string or UTF-8 bytes."""
        return cls.from_dict(_loads_json_object(raw, context="ResultManifest"))


@dataclass
class CheckpointManifest:
    """``checkpoint.json`` written by the child harness when an op requests user input."""

    checkpoint_id: str
    question: str
    options: list[str] | None = None
    allow_freeform: bool = False
    schema: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate this ``CheckpointManifest``."""
        _validate_schema(self.schema, context="CheckpointManifest")
        _validate_checkpoint_id(self.checkpoint_id, context="CheckpointManifest")
        _validate_non_empty_str(self.question, field_name="question", context="CheckpointManifest")
        if self.options is not None:
            if not isinstance(self.options, list) or not self.options:
                raise ProtocolError(
                    "CheckpointManifest: 'options' must be a non-empty list or null"
                )
            for item in self.options:
                if not isinstance(item, str):
                    raise ProtocolError("CheckpointManifest: all items in 'options' must be str")
        if not isinstance(self.allow_freeform, bool):
            raise ProtocolError("CheckpointManifest: 'allow_freeform' must be a bool")

    def to_dict(self) -> dict[str, Any]:
        """Convert to a validated JSON-ready dictionary."""
        self.validate()
        return {
            "schema": self.schema,
            "checkpoint_id": self.checkpoint_id,
            "question": self.question,
            "options": list(self.options) if self.options is not None else None,
            "allow_freeform": self.allow_freeform,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CheckpointManifest:
        """Validate and construct from a dictionary."""
        _check_keys(
            data,
            required={"schema", "checkpoint_id", "question", "options", "allow_freeform"},
            context="CheckpointManifest",
        )
        _validate_schema(data["schema"], context="CheckpointManifest")
        return cls(
            checkpoint_id=data["checkpoint_id"],
            question=data["question"],
            options=data["options"],
            allow_freeform=data["allow_freeform"],
            schema=data["schema"],
        )

    def to_json(self) -> str:
        """Serialize to a validated JSON string."""
        return _dumps_json(self.to_dict())

    @classmethod
    def from_json(cls, raw: str | bytes) -> CheckpointManifest:
        """Deserialize and validate from a JSON string or UTF-8 bytes."""
        return cls.from_dict(_loads_json_object(raw, context="CheckpointManifest"))


__all__ = [
    "MAX_SCALAR_BYTES",
    "SCHEMA_VERSION",
    "CheckpointManifest",
    "DirectoryEntry",
    "InputDirectoryValue",
    "InputFileValue",
    "InputValue",
    "InputsManifest",
    "JsonValue",
    "OutputDirectoryValue",
    "OutputFileValue",
    "OutputValue",
    "OutputsManifest",
    "ProtocolError",
    "ResultDirectoryValue",
    "ResultFileValue",
    "ResultManifest",
    "ResultValue",
    "ScalarData",
    "ScalarPrimitive",
    "ScalarValue",
    "ValueKind",
    "validate_relative_path",
]
