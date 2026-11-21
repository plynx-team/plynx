"""Static AST extraction for PLynx operations (PROTOCOL.md section 3).

The registry reads Python source with ``ast``. It never imports pack code.
Anything outside the supported subset yields ``valid: False`` with a reason, never a crash.
"""

from __future__ import annotations

import ast
import inspect
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from plynx_sdk.types import SEMANTIC_MEDIA_ALIASES

from plynx.api_models import InputPortSpec, OpEntry, OutputPortSpec, PortType

_SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


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


def _parse_annotation(
    node: ast.AST,
    module_aliases: dict[str, ast.AST],
    visited_aliases: set[str] | None = None,
) -> _ParsedAnnotation:
    """Parse a type annotation AST node into a ``_ParsedAnnotation``."""
    unwrapped, _ = _unwrap_optional(node)
    visited = set() if visited_aliases is None else set(visited_aliases)

    if isinstance(unwrapped, ast.Name):
        if unwrapped.id in visited:
            raise ValueError(f"Circular type alias detected: {unwrapped.id}")
        alias_target = module_aliases.get(unwrapped.id)
        if alias_target is not None:
            visited.add(unwrapped.id)
            return _parse_annotation(alias_target, module_aliases, visited)

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

        raise ValueError(f"Unknown or unsupported port annotation: '{unwrapped.id}'")

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

        raise ValueError(f"Unknown or unsupported port annotation: '{unwrapped.attr}'")

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
            base = _parse_annotation(elts[0], module_aliases, visited)
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
                    else:
                        raise ValueError(
                            f"Unknown or unsupported annotation marker in Annotated: '{func_name}'"
                        )
                else:
                    marker_name = _get_name_or_attr(meta)
                    raise ValueError(
                        f"Unknown or unsupported annotation marker in Annotated: '{marker_name}'"
                    )

            return _ParsedAnnotation(
                port_type=port_type,
                media=media,
                options=base_options,
                min=min_val,
                max=max_val,
                step=step_val,
            )

        raise ValueError(f"Unknown or unsupported port annotation: '{name}'")

    raise ValueError(f"Unknown or unsupported port annotation: {ast.dump(unwrapped)}")


def _is_op_candidate_class(node: ast.ClassDef) -> bool:
    """Return whether ``node`` is an attempted PLynx Op class."""
    if any(_get_name_or_attr(base) == "Op" for base in node.bases):
        return True
    if any(_get_name_or_attr(base).endswith("Op") for base in node.bases):
        return True
    for item in node.body:
        if isinstance(item, ast.Assign):
            for t in item.targets:
                if isinstance(t, ast.Name) and t.id == "TITLE":
                    return True
        elif (
            isinstance(item, ast.AnnAssign)
            and isinstance(item.target, ast.Name)
            and item.target.id == "TITLE"
        ):
            return True
    return False


def _get_op_decorator(node: ast.FunctionDef) -> ast.Call | ast.AST | None:
    """Return the ``@op(...)`` decorator node if present on ``node``, else ``None``."""
    for dec in node.decorator_list:
        if isinstance(dec, ast.Call) and _get_name_or_attr(dec.func) == "op":
            return dec
        if isinstance(dec, (ast.Name, ast.Attribute)) and _get_name_or_attr(dec) == "op":
            return dec
    return None


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


def _parse_docstring_args(doc: str) -> dict[str, str]:
    """Parse parameter descriptions from Google-style 'Args:' section in docstring."""
    if not doc:
        return {}
    cleaned = inspect.cleandoc(doc)
    lines = cleaned.splitlines()
    in_args = False
    result: dict[str, str] = {}
    current_param: str | None = None
    current_desc: list[str] = []

    def commit() -> None:
        nonlocal current_param, current_desc
        if current_param:
            result[current_param] = " ".join(current_desc).strip()
            current_param = None
            current_desc = []

    for line in lines:
        stripped = line.strip()
        if not in_args:
            if re.match(r"^(?:Args|Arguments|Parameters):\s*$", stripped, re.IGNORECASE):
                in_args = True
            continue

        # If another Google-style section starts, end the Args section
        if re.match(
            r"^(?:Returns|Yields|Raises|Note|Notes|Examples|Example|Attributes):\s*$",
            stripped,
            re.IGNORECASE,
        ):
            commit()
            break

        # Check for new parameter: "name [(type)]: description"
        param_match = re.match(
            r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)(?:\s*\([^)]*\))?\s*:\s*(.*)$",
            line,
        )
        if param_match:
            commit()
            current_param = param_match.group(1)
            desc_part = param_match.group(2).strip()
            if desc_part:
                current_desc.append(desc_part)
        elif current_param is not None and stripped:
            current_desc.append(stripped)

    commit()
    return result


def _extract_inputs(
    args: ast.arguments,
    *,
    is_method: bool,
    owner_name: str,
    module_aliases: dict[str, ast.AST],
    param_descriptions: dict[str, str] | None = None,
) -> list[InputPortSpec]:
    """Extract input port specifications from function or method arguments."""
    if args.vararg is not None or args.kwarg is not None:
        raise ValueError("*args and **kwargs are not supported in Op signatures")

    inputs: list[InputPortSpec] = []
    pos_args = args.args
    if is_method and pos_args and pos_args[0].arg == "self":
        pos_args = pos_args[1:]

    num_pos = len(pos_args)
    num_defaults = len(args.defaults)
    offset = num_pos - num_defaults

    for i, arg in enumerate(pos_args):
        port_name = arg.arg
        if not _SNAKE_CASE_RE.match(port_name):
            raise ValueError(f"Port name '{port_name}' in {owner_name} must be snake_case")
        if arg.annotation is None:
            raise ValueError(
                f"Input port '{port_name}' in {owner_name} is missing a type annotation"
            )
        parsed = _parse_annotation(arg.annotation, module_aliases)
        if i >= offset:
            default_node = args.defaults[i - offset]
            default_val = _extract_literal(default_node)
            required = False
        else:
            default_val = None
            required = True
        desc = param_descriptions.get(port_name, None) if param_descriptions else None
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
                description=desc,
            )
        )

    for kwarg, kw_default_node in zip(
        args.kwonlyargs,
        args.kw_defaults,
        strict=True,
    ):
        port_name = kwarg.arg
        if not _SNAKE_CASE_RE.match(port_name):
            raise ValueError(f"Port name '{port_name}' in {owner_name} must be snake_case")
        if kwarg.annotation is None:
            raise ValueError(
                f"Input port '{port_name}' in {owner_name} is missing a type annotation"
            )
        parsed = _parse_annotation(kwarg.annotation, module_aliases)
        if kw_default_node is not None:
            default_val = _extract_literal(kw_default_node)
            required = False
        else:
            default_val = None
            required = True
        desc = param_descriptions.get(port_name, None) if param_descriptions else None
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
                description=desc,
            )
        )

    return inputs


def _extract_outputs(
    returns: ast.AST | None,
    typed_dicts: dict[str, ast.ClassDef],
    module_aliases: dict[str, ast.AST],
) -> list[OutputPortSpec]:
    """Extract output port specifications from return annotations or a TypedDict."""
    outputs: list[OutputPortSpec] = []
    output_typed_dict: ast.ClassDef | None = None

    if returns is not None:
        ret_name = _get_name_or_attr(returns)
        if ret_name in typed_dicts:
            output_typed_dict = typed_dicts[ret_name]

    if output_typed_dict is None and "Outputs" in typed_dicts:
        output_typed_dict = typed_dicts["Outputs"]

    if output_typed_dict is not None:
        for out_item in output_typed_dict.body:
            if isinstance(out_item, ast.AnnAssign) and isinstance(out_item.target, ast.Name):
                port_name = out_item.target.id
                if not _SNAKE_CASE_RE.match(port_name):
                    raise ValueError(f"Output port name '{port_name}' must be snake_case")
                out_parsed = _parse_annotation(out_item.annotation, module_aliases)
                outputs.append(
                    OutputPortSpec(
                        name=port_name,
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

    return outputs


def _extract_class_op(
    class_node: ast.ClassDef,
    *,
    pack: str,
    module: str,
    source_path: str,
    module_aliases: dict[str, ast.AST],
    module_typed_dicts: dict[str, ast.ClassDef],
) -> OpEntry:
    """Extract an ``OpEntry`` from an ``Op`` subclass AST node."""
    title: str | None = None
    category = "Uncategorized"
    cacheable = True
    inner_typed_dicts: dict[str, ast.ClassDef] = {}
    run_func: ast.FunctionDef | None = None
    op_id = f"{pack}/{module}:{class_node.name}" if pack else f"{module}:{class_node.name}"

    try:
        # Check base inheritance
        if (
            not class_node.bases
            or len(class_node.bases) != 1
            or _get_name_or_attr(class_node.bases[0]) != "Op"
        ):
            raise ValueError(
                "Inheritance from a custom base class is not supported in v2.0.0 "
                "(must inherit directly from Op)"
            )

        for item in class_node.body:
            if isinstance(item, ast.ClassDef):
                if any(_get_name_or_attr(base) == "TypedDict" for base in item.bases):
                    inner_typed_dicts[item.name] = item
            elif isinstance(item, ast.Assign):
                for t in item.targets:
                    if isinstance(t, ast.Name):
                        if t.id == "TITLE":
                            if not isinstance(item.value, ast.Constant):
                                raise ValueError(
                                    "Computed metadata is not supported: "
                                    "TITLE must be a string literal"
                                )
                            val = item.value.value
                            if not isinstance(val, str):
                                tname = type(val).__name__
                                raise ValueError(f"TITLE must be a string literal, got {tname}")
                            title = val
                        elif t.id == "CATEGORY":
                            if not isinstance(item.value, ast.Constant):
                                raise ValueError(
                                    "Computed metadata is not supported: "
                                    "CATEGORY must be a string literal"
                                )
                            val = item.value.value
                            if not isinstance(val, str):
                                tname = type(val).__name__
                                raise ValueError(f"CATEGORY must be a string literal, got {tname}")
                            category = val
                        elif t.id == "CACHEABLE":
                            if not isinstance(item.value, ast.Constant):
                                raise ValueError(
                                    "Computed metadata is not supported: "
                                    "CACHEABLE must be a boolean literal"
                                )
                            val = item.value.value
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
                    if not isinstance(item.value, ast.Constant):
                        raise ValueError(
                            "Computed metadata is not supported: TITLE must be a string literal"
                        )
                    val = item.value.value
                    if not isinstance(val, str):
                        tname = type(val).__name__
                        raise ValueError(f"TITLE must be a string literal, got {tname}")
                    title = val
                elif item.target.id == "CATEGORY":
                    if not isinstance(item.value, ast.Constant):
                        raise ValueError(
                            "Computed metadata is not supported: CATEGORY must be a string literal"
                        )
                    val = item.value.value
                    if not isinstance(val, str):
                        tname = type(val).__name__
                        raise ValueError(f"CATEGORY must be a string literal, got {tname}")
                    category = val
                elif item.target.id == "CACHEABLE":
                    if not isinstance(item.value, ast.Constant):
                        raise ValueError(
                            "Computed metadata is not supported: "
                            "CACHEABLE must be a boolean literal"
                        )
                    val = item.value.value
                    if not isinstance(val, bool):
                        tname = type(val).__name__
                        raise ValueError(f"CACHEABLE must be a boolean literal, got {tname}")
                    cacheable = val
            elif isinstance(item, ast.FunctionDef) and item.name == "run":
                run_func = item

        if title is None:
            raise ValueError(f"Op class '{class_node.name}' is missing required TITLE attribute")

        if run_func is None:
            raise ValueError(f"Op class '{class_node.name}' must define a 'run' method")

        class_doc = ast.get_docstring(class_node)
        run_doc = ast.get_docstring(run_func) if run_func else None

        # Build parameter descriptions from run() docstring first, supplemented by class docstring
        param_descriptions: dict[str, str] = {}
        if run_doc:
            param_descriptions.update(_parse_docstring_args(run_doc))
        if class_doc:
            for k, v in _parse_docstring_args(class_doc).items():
                if k not in param_descriptions:
                    param_descriptions[k] = v

        # Preserve full markdown docstring (prefer class docstring, fallback to run docstring)
        raw_doc = class_doc or run_doc or ""
        description = inspect.cleandoc(raw_doc) if raw_doc else ""

        all_typed_dicts = dict(module_typed_dicts)
        all_typed_dicts.update(inner_typed_dicts)

        outputs = _extract_outputs(run_func.returns, all_typed_dicts, module_aliases)
        inputs = _extract_inputs(
            run_func.args,
            is_method=True,
            owner_name=f"{class_node.name}.run",
            module_aliases=module_aliases,
            param_descriptions=param_descriptions,
        )

        return OpEntry(
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
    except Exception as exc:
        return OpEntry(
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


def _extract_function_op(
    func_node: ast.FunctionDef,
    *,
    pack: str,
    module: str,
    source_path: str,
    module_aliases: dict[str, ast.AST],
    module_typed_dicts: dict[str, ast.ClassDef],
) -> OpEntry:
    """Extract an ``OpEntry`` from an ``@op(...)`` decorated function AST node."""
    title: str | None = None
    category = "Uncategorized"
    cacheable = True
    op_id = f"{pack}/{module}:{func_node.name}" if pack else f"{module}:{func_node.name}"

    try:
        dec = _get_op_decorator(func_node)
        if not isinstance(dec, ast.Call):
            raise ValueError(
                f"Op decorator on '{func_node.name}' must be called with arguments "
                "(e.g. @op(title=...))"
            )

        # Positional arguments to @op(...)
        if len(dec.args) >= 1:
            arg0 = dec.args[0]
            if not isinstance(arg0, ast.Constant):
                raise ValueError(
                    "Computed metadata is not supported: title in @op must be a string literal"
                )
            if not isinstance(arg0.value, str):
                tname = type(arg0.value).__name__
                raise ValueError(f"Op title must be a string literal, got {tname}")
            title = arg0.value
        if len(dec.args) >= 2:
            arg1 = dec.args[1]
            if not isinstance(arg1, ast.Constant):
                raise ValueError(
                    "Computed metadata is not supported: category in @op must be a string literal"
                )
            if not isinstance(arg1.value, str):
                tname = type(arg1.value).__name__
                raise ValueError(f"Op category must be a string literal, got {tname}")
            category = arg1.value
        if len(dec.args) >= 3:
            arg2 = dec.args[2]
            if not isinstance(arg2, ast.Constant):
                raise ValueError(
                    "Computed metadata is not supported: cacheable in @op must be a boolean literal"
                )
            if not isinstance(arg2.value, bool):
                tname = type(arg2.value).__name__
                raise ValueError(f"Op cacheable must be a boolean literal, got {tname}")
            cacheable = arg2.value

        # Keyword arguments to @op(...)
        for kw in dec.keywords:
            if kw.arg == "title":
                if not isinstance(kw.value, ast.Constant):
                    raise ValueError(
                        "Computed metadata is not supported: title in @op must be a string literal"
                    )
                if not isinstance(kw.value.value, str):
                    tname = type(kw.value.value).__name__
                    raise ValueError(f"Op title must be a string literal, got {tname}")
                title = kw.value.value
            elif kw.arg == "category":
                if not isinstance(kw.value, ast.Constant):
                    raise ValueError(
                        "Computed metadata is not supported: "
                        "category in @op must be a string literal"
                    )
                if not isinstance(kw.value.value, str):
                    tname = type(kw.value.value).__name__
                    raise ValueError(f"Op category must be a string literal, got {tname}")
                category = kw.value.value
            elif kw.arg == "cacheable":
                if not isinstance(kw.value, ast.Constant):
                    raise ValueError(
                        "Computed metadata is not supported: "
                        "cacheable in @op must be a boolean literal"
                    )
                if not isinstance(kw.value.value, bool):
                    tname = type(kw.value.value).__name__
                    raise ValueError(f"Op cacheable must be a boolean literal, got {tname}")
                cacheable = kw.value.value

        if title is None:
            raise ValueError(
                f"Op function '{func_node.name}' is missing required 'title' in @op decorator"
            )

        doc = ast.get_docstring(func_node) or ""
        description = inspect.cleandoc(doc) if doc else ""
        param_descriptions = _parse_docstring_args(doc)

        outputs = _extract_outputs(func_node.returns, module_typed_dicts, module_aliases)
        inputs = _extract_inputs(
            func_node.args,
            is_method=False,
            owner_name=func_node.name,
            module_aliases=module_aliases,
            param_descriptions=param_descriptions,
        )

        return OpEntry(
            id=op_id,
            pack=pack,
            module=module,
            name=func_node.name,
            kind="function",
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
    except Exception as exc:
        return OpEntry(
            id=op_id,
            pack=pack,
            module=module,
            name=func_node.name,
            kind="function",
            title=title or func_node.name,
            category=category,
            cacheable=cacheable,
            description="",
            inputs=[],
            outputs=[],
            source=source_path,
            valid=False,
            error=str(exc),
        )


def extract_ops_from_source(
    source: str,
    *,
    pack: str = "",
    module: str = "",
    source_path: str = "",
) -> list[OpEntry]:
    """Extract PLynx ``Op`` definitions from a Python source string via AST without importing."""
    try:
        tree = ast.parse(source, filename=source_path or "<string>")
    except SyntaxError as exc:
        op_id = f"{pack}/{module}:<syntax_error>" if pack else f"{module}:<syntax_error>"
        return [
            OpEntry(
                id=op_id,
                pack=pack,
                module=module,
                name="<syntax_error>",
                kind="class",
                title="Syntax Error",
                category="Error",
                cacheable=False,
                description="",
                inputs=[],
                outputs=[],
                source=source_path,
                valid=False,
                error=f"Python syntax error: {exc.msg} (line {exc.lineno})",
            )
        ]

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
        if isinstance(stmt, ast.ClassDef) and _is_op_candidate_class(stmt):
            entries.append(
                _extract_class_op(
                    stmt,
                    pack=pack,
                    module=module,
                    source_path=source_path,
                    module_aliases=module_aliases,
                    module_typed_dicts=module_typed_dicts,
                )
            )
        elif isinstance(stmt, ast.FunctionDef) and _get_op_decorator(stmt) is not None:
            entries.append(
                _extract_function_op(
                    stmt,
                    pack=pack,
                    module=module,
                    source_path=source_path,
                    module_aliases=module_aliases,
                    module_typed_dicts=module_typed_dicts,
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
