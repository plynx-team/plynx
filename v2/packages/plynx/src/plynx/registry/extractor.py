"""Static AST extraction for PLynx operations (PROTOCOL.md section 3).

The registry reads Python source with ``ast``. It never imports pack code.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from plynx_sdk.types import SEMANTIC_MEDIA_ALIASES

from plynx.api_models import InputPortSpec, OpEntry, OutputPortSpec, PortType


@dataclass(frozen=True)
class _ParsedAnnotation:
    """Parsed metadata from a port type annotation."""

    port_type: PortType
    media: str | None = None
    options: list[str | int] | None = None
    min: int | float | None = None
    max: int | float | None = None
    step: int | float | None = None


def _get_name_or_attr(node: ast.AST) -> str:
    """Return the identifier name of an ``ast.Name`` or ``ast.Attribute`` node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _extract_literal(node: ast.AST) -> Any:
    """Evaluate an AST expression node into a literal Python value."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        operand = _extract_literal(node.operand)
        if isinstance(operand, (int, float)):
            return -operand if isinstance(node.op, ast.USub) else operand
    if isinstance(node, ast.List):
        return [_extract_literal(elt) for elt in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_extract_literal(elt) for elt in node.elts)
    if isinstance(node, ast.Dict):
        res: dict[Any, Any] = {}
        for k, v in zip(node.keys, node.values, strict=True):
            if k is None:
                raise ValueError("Dict unpacking is not supported in literals")
            res[_extract_literal(k)] = _extract_literal(v)
        return res
    raise ValueError(f"Expression is not a supported literal: {ast.dump(node)}")


def _unwrap_optional(node: ast.AST) -> tuple[ast.AST, bool]:
    """Unwrap ``Optional[X]`` or ``X | None`` / ``None | X`` returning the inner node."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        if (isinstance(node.left, ast.Constant) and node.left.value is None) or (
            isinstance(node.left, ast.Name) and node.left.id == "None"
        ):
            inner, _ = _unwrap_optional(node.right)
            return inner, True
        if (isinstance(node.right, ast.Constant) and node.right.value is None) or (
            isinstance(node.right, ast.Name) and node.right.id == "None"
        ):
            inner, _ = _unwrap_optional(node.left)
            return inner, True
    if isinstance(node, ast.Subscript):
        name = _get_name_or_attr(node.value)
        if name in ("Optional", "Union"):
            if isinstance(node.slice, ast.Tuple):
                non_none = [
                    elt
                    for elt in node.slice.elts
                    if not (
                        (isinstance(elt, ast.Constant) and elt.value is None)
                        or (isinstance(elt, ast.Name) and elt.id == "None")
                    )
                ]
                if len(non_none) == 1:
                    inner, _ = _unwrap_optional(non_none[0])
                    return inner, True
            else:
                inner, _ = _unwrap_optional(node.slice)
                return inner, True
    return node, False


def _parse_annotation(node: ast.AST, module_aliases: dict[str, ast.AST]) -> _ParsedAnnotation:
    """Parse a type annotation AST node into a ``_ParsedAnnotation``."""
    unwrapped, _ = _unwrap_optional(node)

    if isinstance(unwrapped, ast.Name):
        alias_target = module_aliases.get(unwrapped.id)
        if alias_target is not None:
            return _parse_annotation(alias_target, module_aliases)

        if unwrapped.id in SEMANTIC_MEDIA_ALIASES:
            return _ParsedAnnotation(
                port_type="file",
                media=SEMANTIC_MEDIA_ALIASES[unwrapped.id],
            )

        primitive_map: dict[str, PortType] = {
            "str": "str",
            "int": "int",
            "float": "float",
            "bool": "bool",
            "dict": "json",
            "list": "json",
            "Path": "file",
            "Directory": "directory",
        }
        if unwrapped.id in primitive_map:
            return _ParsedAnnotation(port_type=primitive_map[unwrapped.id])

    if isinstance(unwrapped, ast.Attribute):
        if unwrapped.attr in SEMANTIC_MEDIA_ALIASES:
            return _ParsedAnnotation(
                port_type="file",
                media=SEMANTIC_MEDIA_ALIASES[unwrapped.attr],
            )
        if unwrapped.attr == "Path":
            return _ParsedAnnotation(port_type="file")
        if unwrapped.attr == "Directory":
            return _ParsedAnnotation(port_type="directory")

    if isinstance(unwrapped, ast.Subscript):
        name = _get_name_or_attr(unwrapped.value)

        if name in ("dict", "list", "Dict", "List"):
            return _ParsedAnnotation(port_type="json")

        if name == "Literal":
            elts = (
                unwrapped.slice.elts
                if isinstance(unwrapped.slice, ast.Tuple)
                else [unwrapped.slice]
            )
            options = [_extract_literal(elt) for elt in elts]
            if all(isinstance(opt, str) for opt in options):
                return _ParsedAnnotation(port_type="str", options=options)
            if all(isinstance(opt, int) and not isinstance(opt, bool) for opt in options):
                return _ParsedAnnotation(port_type="int", options=options)
            raise ValueError(
                f"Literal options must be all strings or all integers, got: {options!r}"
            )

        if name == "Annotated":
            elts = (
                unwrapped.slice.elts
                if isinstance(unwrapped.slice, ast.Tuple)
                else [unwrapped.slice]
            )
            if not elts:
                raise ValueError("Annotated requires a target type argument")
            base = _parse_annotation(elts[0], module_aliases)
            media = base.media
            min_val = base.min
            max_val = base.max
            step_val = base.step
            base_options = base.options
            port_type = base.port_type

            for meta in elts[1:]:
                if isinstance(meta, ast.Call):
                    func_name = _get_name_or_attr(meta.func)
                    if func_name == "Media":
                        if meta.args:
                            media = str(_extract_literal(meta.args[0]))
                        for kw in meta.keywords:
                            if kw.arg == "mime":
                                media = str(_extract_literal(kw.value))
                    elif func_name == "Range":
                        if len(meta.args) >= 2:
                            min_val = _extract_literal(meta.args[0])
                            max_val = _extract_literal(meta.args[1])
                            if len(meta.args) >= 3:
                                step_val = _extract_literal(meta.args[2])
                        for kw in meta.keywords:
                            if kw.arg == "min":
                                min_val = _extract_literal(kw.value)
                            elif kw.arg == "max":
                                max_val = _extract_literal(kw.value)
                            elif kw.arg == "step":
                                step_val = _extract_literal(kw.value)

            return _ParsedAnnotation(
                port_type=port_type,
                media=media,
                options=base_options,
                min=min_val,
                max=max_val,
                step=step_val,
            )

    raise ValueError(f"Unsupported port annotation: {ast.dump(unwrapped)}")


def _is_op_class(node: ast.ClassDef) -> bool:
    """Return whether ``node`` subclasses ``Op``."""
    return any(_get_name_or_attr(base) == "Op" for base in node.bases)


def _deduce_pack_and_module(
    file_path: Path,
    workspace_root: Path | None = None,
) -> tuple[str, str, str]:
    """Return ``(pack, module, relative_source_path)`` deduced from ``file_path``."""
    resolved = file_path.resolve()
    ws = (workspace_root or Path.cwd()).resolve()
    try:
        rel = resolved.relative_to(ws)
        source_path = str(rel).replace("\\", "/")
    except ValueError:
        source_path = str(file_path).replace("\\", "/")

    parts = Path(source_path).parts
    pack = ""
    module = file_path.stem

    for i, part in enumerate(parts):
        if part in ("builtin_packs", "custom_packs") and i + 1 < len(parts):
            pack = parts[i + 1]
            break

    if not pack and "packages" in parts:
        idx = parts.index("packages")
        if idx + 1 < len(parts):
            pack = parts[idx + 1]

    return pack, module, source_path


def extract_ops_from_source(
    source: str,
    *,
    pack: str = "",
    module: str = "",
    source_path: str = "",
) -> list[OpEntry]:
    """Extract PLynx ``Op`` definitions from a Python source string via AST without importing."""
    tree = ast.parse(source, filename=source_path or "<string>")
    module_aliases: dict[str, ast.AST] = {}
    module_typed_dicts: dict[str, ast.ClassDef] = {}

    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                if isinstance(t, ast.Name):
                    module_aliases[t.id] = stmt.value
        elif (
            isinstance(stmt, ast.AnnAssign)
            and isinstance(stmt.target, ast.Name)
            and stmt.value is not None
        ):
            module_aliases[stmt.target.id] = stmt.value
        elif isinstance(stmt, ast.ClassDef) and any(
            _get_name_or_attr(base) == "TypedDict" for base in stmt.bases
        ):
            module_typed_dicts[stmt.name] = stmt

    entries: list[OpEntry] = []

    for stmt in tree.body:
        if not (isinstance(stmt, ast.ClassDef) and _is_op_class(stmt)):
            continue

        class_node = stmt
        title: str | None = None
        category = "Uncategorized"
        cacheable = True
        inner_typed_dicts: dict[str, ast.ClassDef] = {}
        run_func: ast.FunctionDef | None = None

        try:
            for item in class_node.body:
                if isinstance(item, ast.ClassDef):
                    if any(_get_name_or_attr(base) == "TypedDict" for base in item.bases):
                        inner_typed_dicts[item.name] = item
                elif isinstance(item, ast.Assign):
                    for t in item.targets:
                        if isinstance(t, ast.Name):
                            if t.id == "TITLE":
                                val = _extract_literal(item.value)
                                if not isinstance(val, str):
                                    tname = type(val).__name__
                                    raise ValueError(f"TITLE must be a string literal, got {tname}")
                                title = val
                            elif t.id == "CATEGORY":
                                val = _extract_literal(item.value)
                                if not isinstance(val, str):
                                    tname = type(val).__name__
                                    raise ValueError(
                                        f"CATEGORY must be a string literal, got {tname}"
                                    )
                                category = val
                            elif t.id == "CACHEABLE":
                                val = _extract_literal(item.value)
                                if not isinstance(val, bool):
                                    tname = type(val).__name__
                                    raise ValueError(
                                        f"CACHEABLE must be a boolean literal, got {tname}"
                                    )
                                cacheable = val
                elif (
                    isinstance(item, ast.AnnAssign)
                    and isinstance(item.target, ast.Name)
                    and item.value is not None
                ):
                    if item.target.id == "TITLE":
                        val = _extract_literal(item.value)
                        if not isinstance(val, str):
                            tname = type(val).__name__
                            raise ValueError(f"TITLE must be a string literal, got {tname}")
                        title = val
                    elif item.target.id == "CATEGORY":
                        val = _extract_literal(item.value)
                        if not isinstance(val, str):
                            tname = type(val).__name__
                            raise ValueError(f"CATEGORY must be a string literal, got {tname}")
                        category = val
                    elif item.target.id == "CACHEABLE":
                        val = _extract_literal(item.value)
                        if not isinstance(val, bool):
                            tname = type(val).__name__
                            raise ValueError(f"CACHEABLE must be a boolean literal, got {tname}")
                        cacheable = val
                elif isinstance(item, ast.FunctionDef) and item.name == "run":
                    run_func = item

            if title is None:
                raise ValueError(
                    f"Op class '{class_node.name}' is missing required TITLE attribute"
                )

            if run_func is None:
                raise ValueError(f"Op class '{class_node.name}' must define a 'run' method")

            doc = ast.get_docstring(class_node) or ""
            doc_lines = [line.strip() for line in doc.splitlines() if line.strip()]
            description = doc_lines[0] if doc_lines else ""

            # Outputs
            outputs: list[OutputPortSpec] = []
            returns = run_func.returns
            output_typed_dict: ast.ClassDef | None = None

            if returns is not None:
                ret_name = _get_name_or_attr(returns)
                if ret_name in inner_typed_dicts:
                    output_typed_dict = inner_typed_dicts[ret_name]
                elif ret_name in module_typed_dicts:
                    output_typed_dict = module_typed_dicts[ret_name]

            if output_typed_dict is None and "Outputs" in inner_typed_dicts:
                output_typed_dict = inner_typed_dicts["Outputs"]

            if output_typed_dict is not None:
                for out_item in output_typed_dict.body:
                    if isinstance(out_item, ast.AnnAssign) and isinstance(
                        out_item.target, ast.Name
                    ):
                        out_parsed = _parse_annotation(out_item.annotation, module_aliases)
                        outputs.append(
                            OutputPortSpec(
                                name=out_item.target.id,
                                type=out_parsed.port_type,
                                media=out_parsed.media,
                            )
                        )
            elif returns is not None:
                out_parsed = _parse_annotation(returns, module_aliases)
                outputs.append(
                    OutputPortSpec(
                        name="result",
                        type=out_parsed.port_type,
                        media=out_parsed.media,
                    )
                )

            # Inputs
            inputs: list[InputPortSpec] = []
            pos_args = run_func.args.args
            if pos_args and pos_args[0].arg == "self":
                pos_args = pos_args[1:]

            num_pos = len(pos_args)
            num_defaults = len(run_func.args.defaults)
            offset = num_pos - num_defaults

            for i, arg in enumerate(pos_args):
                port_name = arg.arg
                if arg.annotation is None:
                    raise ValueError(
                        f"Input port '{port_name}' in {class_node.name}.run "
                        "is missing a type annotation"
                    )
                parsed = _parse_annotation(arg.annotation, module_aliases)
                if i >= offset:
                    default_node = run_func.args.defaults[i - offset]
                    default_val = _extract_literal(default_node)
                    required = False
                else:
                    default_val = None
                    required = True
                inputs.append(
                    InputPortSpec(
                        name=port_name,
                        type=parsed.port_type,
                        media=parsed.media,
                        options=parsed.options,
                        min=parsed.min,
                        max=parsed.max,
                        step=parsed.step,
                        required=required,
                        default=default_val,
                    )
                )

            for kwarg, kw_default_node in zip(
                run_func.args.kwonlyargs,
                run_func.args.kw_defaults,
                strict=True,
            ):
                port_name = kwarg.arg
                if kwarg.annotation is None:
                    raise ValueError(
                        f"Input port '{port_name}' in {class_node.name}.run "
                        "is missing a type annotation"
                    )
                parsed = _parse_annotation(kwarg.annotation, module_aliases)
                if kw_default_node is not None:
                    default_val = _extract_literal(kw_default_node)
                    required = False
                else:
                    default_val = None
                    required = True
                inputs.append(
                    InputPortSpec(
                        name=port_name,
                        type=parsed.port_type,
                        media=parsed.media,
                        options=parsed.options,
                        min=parsed.min,
                        max=parsed.max,
                        step=parsed.step,
                        required=required,
                        default=default_val,
                    )
                )

            op_id = f"{pack}/{module}:{class_node.name}" if pack else f"{module}:{class_node.name}"
            entries.append(
                OpEntry(
                    id=op_id,
                    pack=pack,
                    module=module,
                    name=class_node.name,
                    kind="class",
                    title=title,
                    category=category,
                    cacheable=cacheable,
                    description=description,
                    inputs=inputs,
                    outputs=outputs,
                    source=source_path,
                    valid=True,
                    error=None,
                )
            )
        except Exception as exc:
            op_id = f"{pack}/{module}:{class_node.name}" if pack else f"{module}:{class_node.name}"
            entries.append(
                OpEntry(
                    id=op_id,
                    pack=pack,
                    module=module,
                    name=class_node.name,
                    kind="class",
                    title=title or class_node.name,
                    category=category,
                    cacheable=cacheable,
                    description="",
                    inputs=[],
                    outputs=[],
                    source=source_path,
                    valid=False,
                    error=str(exc),
                )
            )

    return entries


def extract_ops_from_file(
    path: Path | str,
    *,
    pack: str | None = None,
    module: str | None = None,
    source_path: str | None = None,
    workspace_root: Path | None = None,
) -> list[OpEntry]:
    """Read a Python source file and extract all Op definitions statically via AST."""
    file_path = Path(path)
    source = file_path.read_text(encoding="utf-8")
    deduced_pack, deduced_module, deduced_source = _deduce_pack_and_module(
        file_path,
        workspace_root=workspace_root,
    )
    final_pack = pack if pack is not None else deduced_pack
    final_module = module if module is not None else deduced_module
    final_source = source_path if source_path is not None else deduced_source
    return extract_ops_from_source(
        source,
        pack=final_pack,
        module=final_module,
        source_path=final_source,
    )


__all__ = [
    "extract_ops_from_file",
    "extract_ops_from_source",
]
