"""Static AST extraction for PLynx operations (PROTOCOL.md section 3).

The registry reads Python source with ``ast``. It never imports pack code.
Anything outside the supported subset yields ``valid: False`` with a reason, never a crash.
"""

from __future__ import annotations

import ast
import inspect
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from plynx_sdk.protocol import AGENT_PROVIDER_VALUES, AgentProvider, GraphEditPolicy
from plynx_sdk.types import SEMANTIC_MEDIA_ALIASES

from plynx.api_models import InputPortSpec, OpEntry, OutputPortSpec, PortType

_SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_AGENT_BASE_CLASSES = ("AgentOp", "StageValidatorOp")
_SUPPORTED_OP_BASES = ("Op", "AgentOp", "StageValidatorOp")


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
    if isinstance(node, ast.Attribute):
        owner = _get_name_or_attr(node.value)
        if owner == "AgentProvider" and node.attr in AgentProvider.__members__:
            return AgentProvider[node.attr].value
        if owner == "GraphEditPolicy" and node.attr in GraphEditPolicy.__members__:
            return GraphEditPolicy[node.attr].value
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


def _extract_literal_str(expr: ast.AST, field_name: str, context: str = "") -> str:
    """Extract a string literal from an AST node, raising ValueError on computed/non-string values."""
    if not isinstance(expr, ast.Constant):
        msg = f"Computed metadata is not supported: {field_name} must be a string literal"
        if context:
            msg = f"Computed metadata is not supported: {field_name} in {context} must be a string literal"
        raise ValueError(msg)
    if not isinstance(expr.value, str):
        tname = type(expr.value).__name__
        msg = f"{field_name} must be a string literal, got {tname}"
        if context:
            msg = f"Op {field_name} must be a string literal, got {tname}"
        raise ValueError(msg)
    return expr.value


def _extract_literal_bool(expr: ast.AST, field_name: str, context: str = "") -> bool:
    """Extract a bool literal from an AST node, raising ValueError on computed/non-bool values."""
    if not isinstance(expr, ast.Constant):
        msg = f"Computed metadata is not supported: {field_name} must be a boolean literal"
        if context:
            msg = f"Computed metadata is not supported: {field_name} in {context} must be a boolean literal"
        raise ValueError(msg)
    if not isinstance(expr.value, bool):
        tname = type(expr.value).__name__
        msg = f"{field_name} must be a boolean literal, got {tname}"
        if context:
            msg = f"Op {field_name} must be a boolean literal, got {tname}"
        raise ValueError(msg)
    return expr.value


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

        if unwrapped.id in ("AgentProvider", "AgentProviderLiteral"):
            return _ParsedAnnotation(
                port_type="str",
                options=list(AGENT_PROVIDER_VALUES),
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
        if unwrapped.attr in ("AgentProvider", "AgentProviderLiteral"):
            return _ParsedAnnotation(
                port_type="str",
                options=list(AGENT_PROVIDER_VALUES),
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
    if any(_get_name_or_attr(base) == "TypedDict" for base in node.bases):
        return False
    if any(_get_name_or_attr(base) in _SUPPORTED_OP_BASES for base in node.bases):
        return True

    has_run = any(isinstance(item, ast.FunctionDef) and item.name == "run" for item in node.body)
    has_title = False
    for item in node.body:
        if isinstance(item, ast.Assign):
            for t in item.targets:
                if isinstance(t, ast.Name) and t.id == "TITLE":
                    has_title = True
                    break
        elif (
            isinstance(item, ast.AnnAssign)
            and isinstance(item.target, ast.Name)
            and item.target.id == "TITLE"
        ):
            has_title = True
            break

    has_op_base = any(_get_name_or_attr(base).endswith("Op") for base in node.bases)
    return bool(has_run and (has_title or has_op_base))


def _get_op_decorator(node: ast.FunctionDef) -> ast.Call | ast.AST | None:
    """Return the ``@op(...)`` decorator node if present on ``node``, else ``None``."""
    for dec in node.decorator_list:
        if isinstance(dec, ast.Call) and _get_name_or_attr(dec.func) == "op":
            return dec
        if isinstance(dec, (ast.Name, ast.Attribute)) and _get_name_or_attr(dec) == "op":
            return dec
    return None


def _format_op_id(pack: str, module: str, name: str) -> str:
    """Format an op ID as <pack>/<module>:<name>, <pack>:<name>, <module>:<name>, or <name>."""
    if pack and module:
        return f"{pack}/{module}:{name}"
    if pack:
        return f"{pack}:{name}"
    if module:
        return f"{module}:{name}"
    return name


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
    module = file_path.stem if file_path.stem != "__init__" else ""

    for i, part in enumerate(parts):
        if part in ("builtin_packs", "custom_packs") and i + 1 < len(parts):
            pack = parts[i + 1]
            break

    if not pack and "packages" in parts:
        idx = parts.index("packages")
        if idx + 1 < len(parts):
            pack = parts[idx + 1]

    if file_path.stem == "__init__" and pack:
        try:
            if pack in parts:
                pack_idx = parts.index(pack)
                subparts = list(parts[pack_idx + 1 : -1])
                if subparts and subparts[0] == "src":
                    subparts.pop(0)
                if subparts and subparts[0] == pack:
                    subparts.pop(0)
                module = ".".join(subparts)
        except Exception:
            module = ""

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
    allow_extra_inputs: bool = False,
) -> tuple[list[InputPortSpec], InputPortSpec | None]:
    """Extract input port specifications from function or method arguments."""
    if args.vararg is not None:
        if args.kwarg is not None:
            raise ValueError("*args and **kwargs are not supported in Op signatures")
        raise ValueError("*args is not supported in Op signatures")
    if args.kwarg is not None and not allow_extra_inputs:
        raise ValueError(
            f"**{args.kwarg.arg} is not supported in Op signatures unless "
            "allow_extra_inputs=True (or ALLOW_EXTRA_INPUTS = True on class)"
        )
    if allow_extra_inputs and args.kwarg is None:
        raise ValueError(
            f"Op '{owner_name}' declared allow_extra_inputs=True but signature is missing **kwargs"
        )

    extra_inputs_type: InputPortSpec | None = None
    if args.kwarg is not None:
        kwarg_name = args.kwarg.arg
        if not _SNAKE_CASE_RE.match(kwarg_name):
            raise ValueError(f"Var-keyword name '{kwarg_name}' in {owner_name} must be snake_case")
        if args.kwarg.annotation is not None:
            if _get_name_or_attr(args.kwarg.annotation) == "Any":
                extra_inputs_type = None
            else:
                parsed = _parse_annotation(args.kwarg.annotation, module_aliases)
                desc = param_descriptions.get(kwarg_name, None) if param_descriptions else None
                extra_inputs_type = InputPortSpec(
                    name=kwarg_name,
                    type=parsed.port_type,
                    media=parsed.media,
                    options=parsed.options,
                    min=parsed.min,
                    max=parsed.max,
                    step=parsed.step,
                    required=False,
                    default=None,
                    description=desc,
                )

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

    return inputs, extra_inputs_type


def _extract_outputs(
    returns: ast.AST | None,
    typed_dicts: dict[str, ast.ClassDef],
    module_aliases: dict[str, ast.AST],
    *,
    allow_default_outputs_typed_dict: bool = False,
) -> list[OutputPortSpec]:
    """Extract output port specifications from return annotations or a TypedDict."""
    outputs: list[OutputPortSpec] = []
    output_typed_dict: ast.ClassDef | None = None

    if returns is not None:
        ret_name = _get_name_or_attr(returns)
        if ret_name in typed_dicts:
            output_typed_dict = typed_dicts[ret_name]

    if output_typed_dict is None and allow_default_outputs_typed_dict and "Outputs" in typed_dicts:
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


def _default_agent_input_ports(
    param_descriptions: Mapping[str, str] | None = None,
) -> list[InputPortSpec]:
    """Return the inherited Choice A input ports for ``AgentOp`` / ``StageValidatorOp``."""
    descs = param_descriptions or {}
    return [
        InputPortSpec(
            name="prompt_file",
            type="file",
            media="text/markdown",
            required=False,
            default=None,
            description=descs.get(
                "prompt_file",
                "Optional Markdown file with domain instructions.",
            ),
        ),
        InputPortSpec(
            name="prompt",
            type="str",
            required=False,
            default="",
            description=descs.get("prompt", "Inline domain instructions."),
        ),
        InputPortSpec(
            name="provider",
            type="str",
            options=list(AGENT_PROVIDER_VALUES),
            required=False,
            default=AgentProvider.DEFAULT.value,
            description=descs.get("provider", "Coding agent CLI provider."),
        ),
        InputPortSpec(
            name="model",
            type="str",
            required=False,
            default="",
            description=descs.get("model", "Optional model identifier override."),
        ),
    ]


def _extract_class_op(
    class_node: ast.ClassDef,
    *,
    pack: str,
    module: str,
    source_path: str,
    module_aliases: dict[str, ast.AST],
    module_typed_dicts: dict[str, ast.ClassDef],
) -> OpEntry:
    """Extract an ``OpEntry`` from an ``Op``, ``AgentOp``, or ``StageValidatorOp`` AST node."""
    title: str | None = None
    category = "Uncategorized"
    cacheable = True
    allow_extra_inputs = False
    agent_role: Literal["agent", "validator"] | None = None
    allow_graph_edits: GraphEditPolicy | None = None
    inner_typed_dicts: dict[str, ast.ClassDef] = {}
    run_func: ast.FunctionDef | None = None
    op_id = _format_op_id(pack, module, class_node.name)

    try:
        # Check base inheritance
        if (
            not class_node.bases
            or len(class_node.bases) != 1
            or _get_name_or_attr(class_node.bases[0]) not in _SUPPORTED_OP_BASES
        ):
            raise ValueError(
                "Inheritance from a custom base class is not supported in v2.0.0 "
                "(must inherit directly from Op, AgentOp, or StageValidatorOp)"
            )

        base_name = _get_name_or_attr(class_node.bases[0])
        is_agent_base = base_name in _AGENT_BASE_CLASSES
        is_validator_base = base_name == "StageValidatorOp"
        if is_validator_base:
            agent_role = "validator"
            category = "Agents / Validators"
            allow_extra_inputs = True
            allow_graph_edits = GraphEditPolicy.CONFIRM
        elif is_agent_base:
            agent_role = "agent"
            allow_extra_inputs = True
            allow_graph_edits = GraphEditPolicy.FORBIDDEN

        for item in class_node.body:
            if isinstance(item, ast.ClassDef):
                if any(_get_name_or_attr(base) == "TypedDict" for base in item.bases):
                    inner_typed_dicts[item.name] = item
            elif isinstance(item, (ast.Assign, ast.AnnAssign)):
                pairs: list[tuple[str, ast.AST]] = []
                if isinstance(item, ast.Assign):
                    for t in item.targets:
                        if isinstance(t, ast.Name):
                            pairs.append((t.id, item.value))
                elif isinstance(item.target, ast.Name) and item.value is not None:
                    pairs.append((item.target.id, item.value))

                for target_id, val_expr in pairs:
                    if target_id == "TITLE":
                        title = _extract_literal_str(val_expr, "TITLE")
                    elif target_id == "CATEGORY":
                        category = _extract_literal_str(val_expr, "CATEGORY")
                    elif target_id == "CACHEABLE":
                        cacheable = _extract_literal_bool(val_expr, "CACHEABLE")
                    elif target_id == "ALLOW_EXTRA_INPUTS":
                        allow_extra_inputs = _extract_literal_bool(val_expr, "ALLOW_EXTRA_INPUTS")
                    elif target_id == "ALLOW_GRAPH_EDITS":
                        raw_pol = _extract_literal(val_expr)
                        if not isinstance(raw_pol, str):
                            raise ValueError(
                                "ALLOW_GRAPH_EDITS must be a GraphEditPolicy or string literal"
                            )
                        try:
                            allow_graph_edits = GraphEditPolicy(raw_pol)
                        except ValueError as exc:
                            raise ValueError(
                                f"Invalid ALLOW_GRAPH_EDITS value {raw_pol!r}"
                            ) from exc
            elif isinstance(item, ast.FunctionDef) and item.name == "run":
                run_func = item

        if title is None:
            raise ValueError(f"Op class '{class_node.name}' is missing required TITLE attribute")

        if run_func is None and not is_agent_base:
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

        has_inner_outputs = "Outputs" in inner_typed_dicts
        if run_func is None:
            inputs = _default_agent_input_ports(param_descriptions)
            extra_inputs_type = None
            if has_inner_outputs:
                outputs = _extract_outputs(
                    None,
                    all_typed_dicts,
                    module_aliases,
                    allow_default_outputs_typed_dict=True,
                )
            elif is_validator_base:
                outputs = [OutputPortSpec(name="summary", type="str")]
            else:
                raise ValueError(
                    f"Op class '{class_node.name}' has no Outputs TypedDict or return annotation"
                )
        else:
            if not has_inner_outputs and run_func.returns is None and not is_validator_base:
                raise ValueError(
                    f"Op class '{class_node.name}' has no Outputs TypedDict or return annotation"
                )
            if not has_inner_outputs and run_func.returns is None and is_validator_base:
                outputs = [OutputPortSpec(name="summary", type="str")]
            else:
                outputs = _extract_outputs(
                    run_func.returns,
                    all_typed_dicts,
                    module_aliases,
                    allow_default_outputs_typed_dict=has_inner_outputs,
                )
            inputs, extra_inputs_type = _extract_inputs(
                run_func.args,
                is_method=True,
                owner_name=f"{class_node.name}.run",
                module_aliases=module_aliases,
                param_descriptions=param_descriptions,
                allow_extra_inputs=allow_extra_inputs,
            )

        return OpEntry(
            id=op_id,
            pack=pack,
            module=module,
            name=class_node.name,
            kind="class",
            agent_role=agent_role,
            allow_graph_edits=allow_graph_edits,
            title=title,
            category=category,
            cacheable=cacheable,
            description=description,
            inputs=inputs,
            outputs=outputs,
            allow_extra_inputs=allow_extra_inputs,
            extra_inputs_type=extra_inputs_type,
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
            agent_role=agent_role,
            title=title or class_node.name,
            category=category,
            cacheable=cacheable,
            description="",
            inputs=[],
            outputs=[],
            allow_extra_inputs=allow_extra_inputs,
            extra_inputs_type=None,
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
    allow_extra_inputs = False
    op_id = _format_op_id(pack, module, func_node.name)

    try:
        dec = _get_op_decorator(func_node)
        if not isinstance(dec, ast.Call):
            raise ValueError(
                f"Op decorator on '{func_node.name}' must be called with arguments "
                "(e.g. @op(title=...))"
            )

        raw_kwargs: dict[str, ast.expr] = {}
        for name, expr in zip(["title", "category", "cacheable"], dec.args, strict=False):
            raw_kwargs[name] = expr
        for kw in dec.keywords:
            if kw.arg is not None:
                raw_kwargs[kw.arg] = kw.value

        for name, expr in raw_kwargs.items():
            if name == "title":
                title = _extract_literal_str(expr, "title", context="@op")
            elif name == "category":
                category = _extract_literal_str(expr, "category", context="@op")
            elif name == "cacheable":
                cacheable = _extract_literal_bool(expr, "cacheable", context="@op")
            elif name == "allow_extra_inputs":
                allow_extra_inputs = _extract_literal_bool(
                    expr, "allow_extra_inputs", context="@op"
                )

        if title is None:
            raise ValueError(
                f"Op function '{func_node.name}' is missing required 'title' in @op decorator"
            )

        doc = ast.get_docstring(func_node) or ""
        description = inspect.cleandoc(doc) if doc else ""
        param_descriptions = _parse_docstring_args(doc)

        if func_node.returns is None:
            raise ValueError(f"Op function '{func_node.name}' is missing a return annotation")

        outputs = _extract_outputs(
            func_node.returns,
            module_typed_dicts,
            module_aliases,
            allow_default_outputs_typed_dict=False,
        )
        inputs, extra_inputs_type = _extract_inputs(
            func_node.args,
            is_method=False,
            owner_name=func_node.name,
            module_aliases=module_aliases,
            param_descriptions=param_descriptions,
            allow_extra_inputs=allow_extra_inputs,
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
            allow_extra_inputs=allow_extra_inputs,
            extra_inputs_type=extra_inputs_type,
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
            allow_extra_inputs=allow_extra_inputs,
            extra_inputs_type=None,
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
        op_id = _format_op_id(pack, module, "<syntax_error>")
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
