"""Child process entrypoint: ``python -m plynx_sdk.harness`` (PROTOCOL.md section 5).

Standard library only. Reads ``inputs.json``, invokes the target op inside ``workdir/``,
validates declared outputs, and writes ``outputs.json`` (exit 0) or ``checkpoint.json`` (exit 10).
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import os
import sys
import tempfile
import time
import traceback
import types
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import (
    Annotated,
    Any,
    Literal,
    Union,
    get_args,
    get_origin,
    get_type_hints,
    is_typeddict,
)

from plynx_sdk.checkpoint import CheckpointInterrupt, checkpoint_context
from plynx_sdk.op import Op
from plynx_sdk.protocol import (
    InputDirectoryValue,
    InputFileValue,
    InputsManifest,
    OutputDirectoryValue,
    OutputFileValue,
    OutputsManifest,
    OutputValue,
    ProtocolError,
    ScalarValue,
)
from plynx_sdk.types import DirectoryMarker, Media, Range

EXIT_SUCCESS = 0
EXIT_OP_ERROR = 1
EXIT_PROTOCOL_ERROR = 2
EXIT_CHECKPOINT = 10


class HarnessProtocolError(Exception):
    """Raised when inputs, op resolution, or outputs violate the protocol."""


@dataclass(frozen=True)
class _PortTypeInfo:
    """Resolved runtime type expectations for an input or output port."""

    kind: Literal["scalar", "file", "directory"]
    scalar_type: type[Any] | None = None
    literal_options: tuple[Any, ...] | None = None
    media: str | None = None
    optional: bool = False


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


def _parse_type_annotation(annotation: Any) -> _PortTypeInfo:
    optional = False
    origin = get_origin(annotation)
    if origin is Union or isinstance(annotation, types.UnionType):
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(args) != len(get_args(annotation)):
            optional = True
        if len(args) == 1:
            annotation = args[0]
            origin = get_origin(annotation)
        else:
            raise HarnessProtocolError(f"Unsupported union annotation: {annotation!r}")

    metadata: tuple[Any, ...] = ()
    if origin is Annotated:
        ann_args = get_args(annotation)
        annotation = ann_args[0]
        metadata = ann_args[1:]
        origin = get_origin(annotation)

    for meta in metadata:
        if isinstance(meta, DirectoryMarker):
            if annotation is not Path:
                raise HarnessProtocolError("DirectoryMarker is only valid on pathlib.Path")
            return _PortTypeInfo(kind="directory", optional=optional)

    media: str | None = None
    for meta in metadata:
        if isinstance(meta, Media):
            media = meta.mime
        elif isinstance(meta, Range) and annotation not in (int, float):
            raise HarnessProtocolError("Range is only valid on int or float")

    if annotation is Path:
        return _PortTypeInfo(kind="file", media=media, optional=optional)

    if origin is Literal:
        lit_args = get_args(annotation)
        if not lit_args:
            raise HarnessProtocolError("Empty Literal annotation")
        return _PortTypeInfo(
            kind="scalar",
            literal_options=tuple(lit_args),
            optional=optional,
        )

    if origin in (dict, list):
        annotation = origin

    if annotation in (str, int, float, bool, dict, list):
        return _PortTypeInfo(kind="scalar", scalar_type=annotation, optional=optional)

    raise HarnessProtocolError(f"Unsupported port type annotation: {annotation!r}")


def _resolve_op_target(
    op_spec: str,
) -> tuple[Callable[..., Any], dict[str, _PortTypeInfo], bool]:
    """Import ``op_spec`` and return ``(callable, output_ports, is_single_return)``."""
    if ":" not in op_spec:
        raise HarnessProtocolError(
            f"Invalid --op spec {op_spec!r}: expected '<module>:<Name>' or '<pack>/<module>:<Name>'"
        )
    raw_module, _, op_name = op_spec.partition(":")
    module_name = raw_module.strip().replace("/", ".")
    op_name = op_name.strip()
    if not module_name or not op_name:
        raise HarnessProtocolError(f"Invalid --op spec {op_spec!r}")

    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        raise HarnessProtocolError(f"Could not import module {module_name!r}: {exc}") from exc

    if not hasattr(module, op_name):
        raise HarnessProtocolError(f"Module {module_name!r} has no attribute {op_name!r}")

    target = getattr(module, op_name)
    globalns = vars(module)

    if isinstance(target, type) and issubclass(target, Op) and target is not Op:
        try:
            instance = target()
        except Exception as exc:
            raise HarnessProtocolError(f"Failed to instantiate Op {op_name!r}: {exc}") from exc
        run_fn = instance.run
        outputs_cls = getattr(target, "Outputs", None)
        if outputs_cls is not None and is_typeddict(outputs_cls):
            hints = get_type_hints(
                outputs_cls, globalns=globalns, localns=vars(target), include_extras=True
            )
            out_ports = {name: _parse_type_annotation(ann) for name, ann in hints.items()}
            return run_fn, out_ports, False

        run_hints = get_type_hints(
            run_fn, globalns=globalns, localns=vars(target), include_extras=True
        )
        if "return" not in run_hints:
            raise HarnessProtocolError(
                f"Op {op_name!r} has no Outputs TypedDict or return annotation"
            )
        ret_ann = run_hints["return"]
        if is_typeddict(ret_ann):
            td_hints = get_type_hints(
                ret_ann, globalns=globalns, localns=vars(target), include_extras=True
            )
            out_ports = {name: _parse_type_annotation(ann) for name, ann in td_hints.items()}
            return run_fn, out_ports, False
        return run_fn, {"result": _parse_type_annotation(ret_ann)}, True

    if callable(target) and not isinstance(target, type):
        fn_hints = get_type_hints(target, globalns=globalns, include_extras=True)
        if "return" not in fn_hints:
            raise HarnessProtocolError(f"Op function {op_name!r} is missing a return annotation")
        ret_ann = fn_hints["return"]
        if is_typeddict(ret_ann):
            td_hints = get_type_hints(ret_ann, globalns=globalns, include_extras=True)
            out_ports = {name: _parse_type_annotation(ann) for name, ann in td_hints.items()}
            return target, out_ports, False
        return target, {"result": _parse_type_annotation(ret_ann)}, True

    raise HarnessProtocolError(
        f"Target {op_spec!r} is neither an Op subclass nor a callable function"
    )


def _prepare_call_kwargs(
    callable_fn: Callable[..., Any],
    inputs_manifest: InputsManifest,
    node_dir: Path,
) -> dict[str, Any]:
    sig = inspect.signature(callable_fn)
    module = inspect.getmodule(callable_fn)
    globalns = vars(module) if module is not None else {}
    try:
        param_hints = get_type_hints(callable_fn, globalns=globalns, include_extras=True)
    except Exception:
        param_hints = {}

    kwargs: dict[str, Any] = {}
    resolved_node_dir = node_dir.resolve()

    for port_name, input_val in inputs_manifest.inputs.items():
        if isinstance(input_val, (InputFileValue, InputDirectoryValue)):
            kwargs[port_name] = resolved_node_dir / input_val.path
        elif isinstance(input_val, ScalarValue):
            ann = param_hints.get(port_name)
            if ann is None:
                for param in sig.parameters.values():
                    if param.kind == inspect.Parameter.VAR_KEYWORD:
                        ann = param_hints.get(param.name)
                        break
            if ann is not None and input_val.value is not None:
                try:
                    info = _parse_type_annotation(ann)
                except HarnessProtocolError:
                    info = None
                if info is not None and info.kind in ("file", "directory"):
                    if not isinstance(input_val.value, str):
                        val_type = type(input_val.value).__name__
                        raise HarnessProtocolError(
                            f"Input port {port_name!r} expects a path string, got {val_type}"
                        )
                    kwargs[port_name] = Path(input_val.value)
                    continue
            kwargs[port_name] = input_val.value
        else:
            raise HarnessProtocolError(f"Unsupported input value for {port_name!r}")

    try:
        sig.bind(**kwargs)
    except TypeError as exc:
        raise HarnessProtocolError(f"Input arguments do not match op signature: {exc}") from exc

    return kwargs


def _validate_and_resolve_workdir_path(
    raw_value: Any,
    *,
    port_name: str,
    node_dir: Path,
    workdir: Path,
    expect_dir: bool,
) -> str:
    if isinstance(raw_value, Path):
        raw_str = raw_value.as_posix()
    elif isinstance(raw_value, str):
        if "\\" in raw_value:
            raise HarnessProtocolError(
                f"Output {port_name!r}: path must not contain backslashes: {raw_value!r}"
            )
        raw_str = raw_value
    else:
        raise HarnessProtocolError(
            f"Output {port_name!r}: expected Path or str, got {type(raw_value).__name__}"
        )

    if not raw_str:
        raise HarnessProtocolError(f"Output {port_name!r}: path must be non-empty")

    if (
        raw_str.startswith("/")
        or PurePosixPath(raw_str).is_absolute()
        or PureWindowsPath(raw_str).drive
    ):
        raise HarnessProtocolError(f"Output {port_name!r}: path must be relative, got {raw_str!r}")

    parts = raw_str.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise HarnessProtocolError(
            f"Output {port_name!r}: path contains invalid segment: {raw_str!r}"
        )

    resolved_workdir = workdir.resolve()
    candidate_in_workdir = (resolved_workdir / raw_str).resolve()
    if candidate_in_workdir.exists() and candidate_in_workdir.is_relative_to(resolved_workdir):
        target_path = candidate_in_workdir
    elif parts[0] == "workdir" and len(parts) > 1:
        candidate_from_node = (node_dir.resolve() / raw_str).resolve()
        if candidate_from_node.exists() and candidate_from_node.is_relative_to(resolved_workdir):
            target_path = candidate_from_node
        else:
            raise HarnessProtocolError(
                f"Output {port_name!r}: path {raw_str!r} does not exist inside workdir/"
            )
    else:
        raise HarnessProtocolError(
            f"Output {port_name!r}: path {raw_str!r} does not exist inside workdir/"
        )

    if expect_dir:
        if not target_path.is_dir():
            raise HarnessProtocolError(f"Output {port_name!r}: expected a directory at {raw_str!r}")
    else:
        if not target_path.is_file():
            raise HarnessProtocolError(f"Output {port_name!r}: expected a file at {raw_str!r}")

    rel_to_workdir = target_path.relative_to(resolved_workdir).as_posix()
    return f"workdir/{rel_to_workdir}"


def _validate_scalar_output(raw_value: Any, info: _PortTypeInfo, *, port_name: str) -> ScalarValue:
    if raw_value is None:
        if info.optional:
            return ScalarValue(value=None)
        raise HarnessProtocolError(
            f"Output {port_name!r}: None is not allowed for non-optional port"
        )

    if info.literal_options is not None:
        matched = any(
            raw_value == opt and type(raw_value) is type(opt) for opt in info.literal_options
        )
        if not matched:
            opts = list(info.literal_options)
            raise HarnessProtocolError(
                f"Output {port_name!r}: value {raw_value!r} not in Literal{opts}"
            )
    elif info.scalar_type is not None:
        expected = info.scalar_type
        if expected is int:
            if isinstance(raw_value, bool) or not isinstance(raw_value, int):
                raise HarnessProtocolError(
                    f"Output {port_name!r}: expected int, got {type(raw_value).__name__}"
                )
        elif expected is float:
            if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
                raise HarnessProtocolError(
                    f"Output {port_name!r}: expected float, got {type(raw_value).__name__}"
                )
        elif expected is bool:
            if not isinstance(raw_value, bool):
                raise HarnessProtocolError(
                    f"Output {port_name!r}: expected bool, got {type(raw_value).__name__}"
                )
        elif not isinstance(raw_value, expected):
            val_type = type(raw_value).__name__
            raise HarnessProtocolError(
                f"Output {port_name!r}: expected {expected.__name__}, got {val_type}"
            )

    try:
        return ScalarValue(value=raw_value)
    except ProtocolError as exc:
        raise HarnessProtocolError(f"Output {port_name!r}: {exc}") from exc


def _build_outputs_map(
    raw_result: Any,
    output_specs: Mapping[str, _PortTypeInfo],
    *,
    is_single_return: bool,
    node_dir: Path,
    workdir: Path,
) -> dict[str, OutputValue]:
    if is_single_return:
        spec = output_specs["result"]
        if (
            isinstance(raw_result, Mapping)
            and spec.scalar_type is not dict
            and set(raw_result.keys()) == {"result"}
        ):
            raw_map: Mapping[str, Any] = raw_result
        else:
            raw_map = {"result": raw_result}
    else:
        if not isinstance(raw_result, Mapping):
            raise HarnessProtocolError(
                f"Op must return a dict matching Outputs, got {type(raw_result).__name__}"
            )
        raw_map = raw_result

    expected_keys = set(output_specs.keys())
    actual_keys = set(raw_map.keys())
    if actual_keys != expected_keys:
        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)
        details: list[str] = []
        if missing:
            details.append(f"missing={missing}")
        if extra:
            details.append(f"unexpected={extra}")
        raise HarnessProtocolError(f"Output keys mismatch ({', '.join(details)})")

    outputs: dict[str, OutputValue] = {}
    for port_name, info in output_specs.items():
        val = raw_map[port_name]
        if info.kind == "file":
            rel_path = _validate_and_resolve_workdir_path(
                val,
                port_name=port_name,
                node_dir=node_dir,
                workdir=workdir,
                expect_dir=False,
            )
            outputs[port_name] = OutputFileValue(path=rel_path, media=info.media)
        elif info.kind == "directory":
            rel_path = _validate_and_resolve_workdir_path(
                val,
                port_name=port_name,
                node_dir=node_dir,
                workdir=workdir,
                expect_dir=True,
            )
            outputs[port_name] = OutputDirectoryValue(path=rel_path)
        else:
            outputs[port_name] = _validate_scalar_output(val, info, port_name=port_name)

    return outputs


def run_harness(op_spec: str, node_dir: Path) -> int:
    """Execute one node attempt inside ``node_dir`` and return the protocol exit code."""
    resolved_node_dir = node_dir.resolve()
    inputs_path = resolved_node_dir / "inputs.json"
    if not inputs_path.is_file():
        print(f"Harness protocol error: missing {inputs_path}", file=sys.stderr)
        return EXIT_PROTOCOL_ERROR

    try:
        inputs_manifest = InputsManifest.from_json(inputs_path.read_bytes())
        callable_fn, output_specs, is_single_return = _resolve_op_target(op_spec)
        call_kwargs = _prepare_call_kwargs(callable_fn, inputs_manifest, resolved_node_dir)
    except (ProtocolError, HarnessProtocolError, OSError) as exc:
        print(f"Harness protocol error: {exc}", file=sys.stderr)
        return EXIT_PROTOCOL_ERROR

    workdir = resolved_node_dir / "workdir"
    workdir.mkdir(parents=True, exist_ok=True)

    prev_cwd = Path.cwd()
    started_at = time.time()
    try:
        os.chdir(workdir)
        with checkpoint_context(
            answers=inputs_manifest.checkpoint_answers,
            node_dir=resolved_node_dir,
        ):
            raw_result = callable_fn(**call_kwargs)
    except CheckpointInterrupt as cp_exc:
        cp_path = resolved_node_dir / "checkpoint.json"
        if not cp_path.is_file():
            _atomic_write_text(cp_path, cp_exc.manifest.to_json())
        return EXIT_CHECKPOINT
    except BaseException:
        traceback.print_exc(file=sys.stderr)
        return EXIT_OP_ERROR
    finally:
        os.chdir(prev_cwd)

    finished_at = time.time()
    if finished_at < started_at:
        finished_at = started_at

    try:
        outputs_map = _build_outputs_map(
            raw_result,
            output_specs,
            is_single_return=is_single_return,
            node_dir=resolved_node_dir,
            workdir=workdir,
        )
        outputs_manifest = OutputsManifest(
            started_at=started_at,
            finished_at=finished_at,
            outputs=outputs_map,
        )
        _atomic_write_text(resolved_node_dir / "outputs.json", outputs_manifest.to_json())
    except (ProtocolError, HarnessProtocolError, OSError) as exc:
        print(f"Harness protocol error: {exc}", file=sys.stderr)
        return EXIT_PROTOCOL_ERROR

    return EXIT_SUCCESS


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for ``python -m plynx_sdk.harness``."""
    parser = argparse.ArgumentParser(prog="python -m plynx_sdk.harness")
    parser.add_argument("--op", required=True, help="Target op '<pack>.<module>:<Name>'")
    parser.add_argument("--dir", required=True, type=Path, help="Node attempt directory")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else EXIT_PROTOCOL_ERROR
        return EXIT_PROTOCOL_ERROR if code != 0 else 0

    return run_harness(args.op, args.dir)


if __name__ == "__main__":
    sys.exit(main())
