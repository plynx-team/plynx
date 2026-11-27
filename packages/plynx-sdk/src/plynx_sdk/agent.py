"""``AgentOp`` and ``StageValidatorOp`` authoring API (ENTRYPOINT.md sections 2.3 & 2.4).

Standard library only. Provides:
- 0-token replay across ``checkpoint_batch()`` restarts via ``nodes/<node_id>/agent_turns.json``
- Auto-generated JSON Schema envelope (``workdir/turn_schema.json``) from ``class Outputs(TypedDict)``
- Universal ``workdir/turn_output.json`` file-out contract with stdout fallback
- Automatic scalar validation and file output materialization (``MarkdownFile`` -> ``.md``, etc.)
"""

from __future__ import annotations

import inspect
import json
import os
import tempfile
import time
import types
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    ClassVar,
    TypedDict,
    Union,
    get_args,
    get_origin,
    get_type_hints,
    is_typeddict,
)

from plynx_sdk.adapters import (
    execute_provider_turn,
    resolve_runtime_model,
    resolve_runtime_provider,
)
from plynx_sdk.op import Op
from plynx_sdk.protocol import (
    AgentProvider,
    AgentProviderLiteral,
    AgentTurnRecord,
    AgentTurnsManifest,
    AgentTurnStatus,
    AnswerValue,
    CheckpointQuestion,
    GraphEditPolicy,
    GraphPatchPayload,
    InputsManifest,
    JsonValue,
    ProtocolError,
)
from plynx_sdk.types import DirectoryMarker, MarkdownFile, Media, Range

AGENT_TURNS_FILENAME = "agent_turns.json"
TURN_SCHEMA_FILENAME = "turn_schema.json"
TURN_OUTPUT_FILENAME = "turn_output.json"
GRAPH_PATCH_FILENAME = "graph_patch.json"
STAGE_CONTEXT_FILENAME = "stage_context.json"

_MEDIA_EXTENSIONS: dict[str, str] = {
    "text/markdown": ".md",
    "application/json": ".json",
    "text/plain": ".txt",
    "text/csv": ".csv",
    "application/pdf": ".pdf",
    "audio/wav": ".wav",
    "audio/midi": ".mid",
    "image/png": ".png",
    "text/html": ".html",
    "application/yaml": ".yaml",
}


@dataclass
class _AgentExecutionState:
    """Per-attempt node directory, workdir, and turn counter bound by the child harness."""

    node_dir: Path
    workdir: Path
    inputs_manifest: InputsManifest | None = None
    turn_counter: int = 0


_CURRENT_AGENT_STATE: ContextVar[_AgentExecutionState | None] = ContextVar(
    "_plynx_agent_execution_state",
    default=None,
)


@dataclass(frozen=True)
class _OutputFieldSpec:
    """Parsed output annotation metadata for schema generation and file materialization."""

    name: str
    kind: str  # "scalar" | "file" | "directory"
    scalar_type: type[Any] | None = None
    literal_options: tuple[Any, ...] | None = None
    media: str | None = None
    range_bounds: Range | None = None
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


@contextmanager
def agent_context(
    *,
    node_dir: Path,
    workdir: Path | None = None,
    inputs_manifest: InputsManifest | None = None,
) -> Iterator[None]:
    """Bind ``node_dir`` and ``workdir`` for an ``AgentOp`` execution attempt."""
    resolved_node = node_dir.resolve()
    resolved_work = (workdir or (resolved_node / "workdir")).resolve()
    resolved_work.mkdir(parents=True, exist_ok=True)
    state = _AgentExecutionState(
        node_dir=resolved_node,
        workdir=resolved_work,
        inputs_manifest=inputs_manifest,
        turn_counter=0,
    )
    token = _CURRENT_AGENT_STATE.set(state)
    try:
        yield
    finally:
        _CURRENT_AGENT_STATE.reset(token)


def _resolve_dirs() -> tuple[Path, Path, _AgentExecutionState | None]:
    state = _CURRENT_AGENT_STATE.get()
    if state is not None:
        return state.node_dir, state.workdir, state
    cwd = Path.cwd().resolve()
    if cwd.name == "workdir":
        return cwd.parent, cwd, None
    workdir = cwd / "workdir"
    workdir.mkdir(parents=True, exist_ok=True)
    return cwd, workdir, None


def _parse_output_field(name: str, annotation: Any) -> _OutputFieldSpec:
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
            raise ProtocolError(f"Unsupported union annotation on output {name!r}: {annotation!r}")

    metadata: tuple[Any, ...] = ()
    if origin is Annotated:
        ann_args = get_args(annotation)
        annotation = ann_args[0]
        metadata = ann_args[1:]
        origin = get_origin(annotation)

    for meta in metadata:
        if isinstance(meta, DirectoryMarker):
            return _OutputFieldSpec(name=name, kind="directory", optional=optional)

    media: str | None = None
    range_bounds: Range | None = None
    for meta in metadata:
        if isinstance(meta, Media):
            media = meta.mime
        elif isinstance(meta, Range):
            range_bounds = meta

    if annotation is Path:
        return _OutputFieldSpec(name=name, kind="file", media=media, optional=optional)

    from typing import Literal as TypingLiteral

    if origin is TypingLiteral:
        return _OutputFieldSpec(
            name=name,
            kind="scalar",
            literal_options=tuple(get_args(annotation)),
            optional=optional,
        )

    if origin in (dict, list):
        annotation = origin

    if annotation in (str, int, float, bool, dict, list):
        return _OutputFieldSpec(
            name=name,
            kind="scalar",
            scalar_type=annotation,
            range_bounds=range_bounds,
            optional=optional,
        )

    raise ProtocolError(f"Unsupported output port annotation on {name!r}: {annotation!r}")


def _extract_output_specs_for_op(op_cls: type[Op]) -> dict[str, _OutputFieldSpec]:
    module = inspect.getmodule(op_cls)
    globalns = vars(module) if module is not None else {}
    outputs_cls = getattr(op_cls, "Outputs", None)
    if outputs_cls is not None and is_typeddict(outputs_cls):
        hints = get_type_hints(
            outputs_cls,
            globalns=globalns,
            localns=vars(op_cls),
            include_extras=True,
        )
        return {port: _parse_output_field(port, ann) for port, ann in hints.items()}

    run_fn = getattr(op_cls, "run", None)
    if run_fn is not None:
        try:
            run_hints = get_type_hints(
                run_fn,
                globalns=globalns,
                localns=vars(op_cls),
                include_extras=True,
            )
        except Exception:
            run_hints = {}
        ret_ann = run_hints.get("return")
        if ret_ann is not None and ret_ann is not Any:
            if is_typeddict(ret_ann):
                td_hints = get_type_hints(
                    ret_ann,
                    globalns=globalns,
                    localns=vars(op_cls),
                    include_extras=True,
                )
                return {port: _parse_output_field(port, ann) for port, ann in td_hints.items()}
            return {"result": _parse_output_field("result", ret_ann)}

    raise ProtocolError(
        f"AgentOp subclass {op_cls.__name__!r} must declare class Outputs(TypedDict)"
    )


def _field_to_json_schema(spec: _OutputFieldSpec) -> dict[str, Any]:
    schema: dict[str, Any]
    if spec.kind == "file":
        ext = _MEDIA_EXTENSIONS.get(spec.media or "", ".txt")
        if spec.media == "application/json":
            schema = {
                "anyOf": [
                    {"type": "string"},
                    {"type": "object"},
                    {"type": "array"},
                ],
                "description": (
                    f"Relative path to a JSON file in workdir/ (e.g. '{spec.name}{ext}') "
                    "or inline JSON content."
                ),
            }
        else:
            schema = {
                "type": "string",
                "description": (
                    f"Relative file path written inside workdir/ (e.g. '{spec.name}{ext}') "
                    f"or inline {spec.media or 'text'} content."
                ),
            }
    elif spec.kind == "directory":
        schema = {
            "type": "string",
            "description": f"Relative directory path created inside workdir/ (e.g. '{spec.name}').",
        }
    elif spec.literal_options is not None:
        opts = list(spec.literal_options)
        base_type = (
            "integer"
            if all(isinstance(o, int) and not isinstance(o, bool) for o in opts)
            else "string"
        )
        schema = {"type": base_type, "enum": opts}
    elif spec.scalar_type is str:
        schema = {"type": "string"}
    elif spec.scalar_type is int:
        schema = {"type": "integer"}
    elif spec.scalar_type is float:
        schema = {"type": "number"}
    elif spec.scalar_type is bool:
        schema = {"type": "boolean"}
    elif spec.scalar_type is dict:
        schema = {"type": "object"}
    elif spec.scalar_type is list:
        schema = {"type": "array"}
    else:
        schema = {}

    if spec.range_bounds is not None and spec.scalar_type in (int, float):
        schema["minimum"] = spec.range_bounds.min
        schema["maximum"] = spec.range_bounds.max

    if spec.optional:
        return {"anyOf": [schema, {"type": "null"}]}
    return schema


def generate_turn_schema(
    op_cls: type[Op],
    *,
    allow_graph_edits: GraphEditPolicy = GraphEditPolicy.FORBIDDEN,
) -> dict[str, Any]:
    """Generate the ``turn_schema.json`` envelope schema from ``op_cls.Outputs``."""
    output_specs = _extract_output_specs_for_op(op_cls)
    allowed_statuses = [
        AgentTurnStatus.COMPLETED.value,
        AgentTurnStatus.NEEDS_INPUT.value,
    ]
    if allow_graph_edits != GraphEditPolicy.FORBIDDEN:
        allowed_statuses.append(AgentTurnStatus.PROPOSE_PATCH.value)

    outputs_properties = {name: _field_to_json_schema(spec) for name, spec in output_specs.items()}
    outputs_required = [name for name, spec in output_specs.items() if not spec.optional]

    envelope_props: dict[str, Any] = {
        "status": {
            "type": "string",
            "enum": allowed_statuses,
            "description": "Turn outcome status.",
        },
        "outputs": {
            "type": "object",
            "properties": outputs_properties,
            "required": outputs_required,
            "additionalProperties": False,
        },
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "header": {"type": "string"},
                    "question": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}},
                    "multi_select": {"type": "boolean"},
                    "allow_freeform": {"type": "boolean"},
                },
                "required": ["id", "question"],
                "additionalProperties": False,
            },
        },
    }

    if allow_graph_edits != GraphEditPolicy.FORBIDDEN:
        envelope_props["graph_patch"] = {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Concise human-readable reason for the proposed DAG patch.",
                },
                "add_nodes": {
                    "type": "object",
                    "description": (
                        'Mapping of new_node_id -> {"op": "<pack>/<mod>:<Op>", '
                        '"stage": "<stage_id>", "title": "...", "inputs": {"<port>": "$<up>.<out>"}}.'
                    ),
                },
                "rewire_inputs": {
                    "type": "object",
                    "description": (
                        'Nested mapping of target_node_id -> {"<port>": "$<new_node_id>.<out>"}.'
                    ),
                },
            },
            "required": ["reason"],
            "additionalProperties": False,
        }

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": envelope_props,
        "required": ["status"],
        "additionalProperties": False,
    }


def _looks_like_existing_workdir_file(
    raw_str: str,
    *,
    node_dir: Path,
    workdir: Path,
) -> Path | None:
    """If ``raw_str`` names an existing file inside ``workdir/``, return its workdir-relative Path."""
    if (
        not raw_str
        or len(raw_str) > 512
        or "\n" in raw_str
        or "\r" in raw_str
        or "\x00" in raw_str
        or "\\" in raw_str
    ):
        return None
    if (
        raw_str.startswith("/")
        or PurePosixPath(raw_str).is_absolute()
        or PureWindowsPath(raw_str).drive
    ):
        return None
    parts = raw_str.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return None

    resolved_work = workdir.resolve()
    direct = (resolved_work / raw_str).resolve()
    if (
        direct.is_file()
        and direct.is_relative_to(resolved_work)
        and direct.name not in (TURN_OUTPUT_FILENAME, TURN_SCHEMA_FILENAME)
    ):
        return direct.relative_to(resolved_work)

    if parts[0] == "workdir" and len(parts) > 1:
        from_node = (node_dir.resolve() / raw_str).resolve()
        if (
            from_node.is_file()
            and from_node.is_relative_to(resolved_work)
            and from_node.name not in (TURN_OUTPUT_FILENAME, TURN_SCHEMA_FILENAME)
        ):
            return from_node.relative_to(resolved_work)

    return None


def materialize_turn_outputs(
    raw_outputs: Mapping[str, Any],
    op_cls: type[Op],
    *,
    node_dir: Path,
    workdir: Path,
) -> dict[str, Any]:
    """Validate ``raw_outputs`` against ``op_cls.Outputs`` and materialize inline file contents."""
    specs = _extract_output_specs_for_op(op_cls)
    result: dict[str, Any] = {}

    missing = [name for name, s in specs.items() if not s.optional and name not in raw_outputs]
    if missing:
        raise ProtocolError(f"Agent turn outputs missing required port(s): {', '.join(missing)}")
    unknown = [str(k) for k in raw_outputs if k not in specs]
    if unknown:
        raise ProtocolError(f"Agent turn outputs contain unknown port(s): {', '.join(unknown)}")

    resolved_work = workdir.resolve()

    for port_name, spec in specs.items():
        val = raw_outputs.get(port_name)
        if val is None:
            if spec.optional:
                result[port_name] = None
                continue
            raise ProtocolError(f"Agent output {port_name!r} cannot be null")

        if spec.kind == "file":
            ext = _MEDIA_EXTENSIONS.get(spec.media or "", ".txt")
            default_rel = Path(f"{port_name}{ext}")

            if isinstance(val, Path):
                existing = _looks_like_existing_workdir_file(
                    val.as_posix(), node_dir=node_dir, workdir=resolved_work
                )
                if existing is None:
                    raise ProtocolError(
                        f"Agent file output {port_name!r} path {val.as_posix()!r} not found in workdir/"
                    )
                result[port_name] = existing
                continue

            if isinstance(val, str):
                existing = _looks_like_existing_workdir_file(
                    val, node_dir=node_dir, workdir=resolved_work
                )
                if existing is not None:
                    result[port_name] = existing
                    continue
                if spec.media == "application/json":
                    try:
                        parsed_json = json.loads(val)
                        formatted = json.dumps(parsed_json, indent=2, ensure_ascii=False) + "\n"
                    except json.JSONDecodeError as exc:
                        raise ProtocolError(
                            f"Agent JsonFile output {port_name!r} is neither an existing file "
                            f"in workdir/ nor valid JSON: {exc}"
                        ) from exc
                    _atomic_write_text(resolved_work / default_rel, formatted)
                else:
                    _atomic_write_text(resolved_work / default_rel, val)
                result[port_name] = default_rel
                continue

            if isinstance(val, (dict, list)) and spec.media == "application/json":
                formatted = json.dumps(val, indent=2, ensure_ascii=False) + "\n"
                _atomic_write_text(resolved_work / default_rel, formatted)
                result[port_name] = default_rel
                continue

            raise ProtocolError(
                f"Agent file output {port_name!r} expected str or JSON content, "
                f"got {type(val).__name__}"
            )

        if spec.kind == "directory":
            raw_dir = val.as_posix() if isinstance(val, Path) else str(val)
            if not raw_dir or ".." in raw_dir.split("/"):
                raise ProtocolError(f"Agent directory output {port_name!r} invalid: {raw_dir!r}")
            cand_dir = (resolved_work / raw_dir).resolve()
            if not (cand_dir.is_dir() and cand_dir.is_relative_to(resolved_work)):
                raise ProtocolError(
                    f"Agent directory output {port_name!r} not found inside workdir/: {raw_dir!r}"
                )
            result[port_name] = cand_dir.relative_to(resolved_work)
            continue

        # Scalar validation
        if spec.literal_options is not None:
            if not any(val == opt and type(val) is type(opt) for opt in spec.literal_options):
                raise ProtocolError(
                    f"Agent output {port_name!r}: {val!r} not in {list(spec.literal_options)}"
                )
        elif spec.scalar_type is int:
            if isinstance(val, bool) or not isinstance(val, int):
                raise ProtocolError(
                    f"Agent output {port_name!r}: expected int, got {type(val).__name__}"
                )
        elif spec.scalar_type is float:
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                raise ProtocolError(
                    f"Agent output {port_name!r}: expected float, got {type(val).__name__}"
                )
        elif spec.scalar_type is bool:
            if not isinstance(val, bool):
                raise ProtocolError(
                    f"Agent output {port_name!r}: expected bool, got {type(val).__name__}"
                )
        elif spec.scalar_type is not None and not isinstance(val, spec.scalar_type):
            raise ProtocolError(
                f"Agent output {port_name!r}: expected {spec.scalar_type.__name__}, "
                f"got {type(val).__name__}"
            )

        if (
            spec.range_bounds is not None
            and isinstance(val, (int, float))
            and not isinstance(val, bool)
            and (val < spec.range_bounds.min or val > spec.range_bounds.max)
        ):
            raise ProtocolError(
                f"Agent output {port_name!r}: value {val} outside Range"
                f"({spec.range_bounds.min}, {spec.range_bounds.max})"
            )

        result[port_name] = val

    return result


def _summarize_prompt(domain_text: str, max_len: int = 160) -> str:
    collapsed = " ".join(domain_text.split())
    if len(collapsed) <= max_len:
        return collapsed
    return collapsed[: max_len - 3] + "..."


def _build_full_turn_prompt(
    *,
    node_dir: Path,
    workdir: Path,
    schema_path: Path,
    output_path: Path,
    domain_prompt: str,
    task_inputs: Mapping[str, Any],
    allow_graph_edits: GraphEditPolicy,
    turn_index: int,
    user_answers: Mapping[str, AnswerValue] | None,
) -> str:
    inputs_dir = node_dir / "inputs"
    sections: list[str] = [
        "## PLynx Execution Envelope",
        (
            f"Your working directory is `{workdir}`. Read your task inputs strictly from "
            f"`{inputs_dir}/` and write all generated artifacts and `{TURN_OUTPUT_FILENAME}` "
            f"inside `{workdir}`. You may use workspace `.agents/skills/` and `AGENTS.md` "
            f"guidelines, but do not modify tracked workspace files outside `{workdir}`."
        ),
        (
            f"Write your final response as a JSON object conforming to `{schema_path}` "
            f"into `{output_path}` (do not search PLynx engine source code; write `{TURN_OUTPUT_FILENAME}` and finish as soon as your task is resolved):\n"
            '- Set `"status": "completed"` and populate `"outputs"` when the task is complete.\n'
            '- Set `"status": "needs_input"` and populate `"questions"` (batch all needed '
            "human clarifications into one list) only when human user input is required."
            + (
                '\n- Set `"status": "propose_patch"` and populate `"graph_patch"` '
                '(`{"reason": "...", "add_nodes": {"<new_id>": {"op": "<pack>/<mod>:<Op>", "stage": "<stage_id>", "inputs": {"<port>": "$<up>.<out>"}}}, '
                '"rewire_inputs": {"<downstream_id>": {"<port>": "$<new_id>.<out>"}}}`) '
                "if the workflow graph needs bounded repair (omit `outputs` when proposing a patch)."
                if allow_graph_edits != GraphEditPolicy.FORBIDDEN
                else ""
            )
        ),
    ]

    if domain_prompt.strip():
        sections.append("## Task Instructions\n" + domain_prompt.strip())

    if task_inputs:
        input_lines: list[str] = []
        for k, v in task_inputs.items():
            if isinstance(v, Path):
                input_lines.append(f"- `{k}` (path): `{v}`")
            else:
                serialized = json.dumps(v, ensure_ascii=False)
                input_lines.append(f"- `{k}`: {serialized}")
        sections.append("## Task Inputs\n" + "\n".join(input_lines))

    stage_ctx_path = node_dir / STAGE_CONTEXT_FILENAME
    if stage_ctx_path.is_file():
        ctx_lines = [
            f"Inspect `{stage_ctx_path}` for full stage outputs, warnings, log tails, "
            "`workflow.snapshot.yaml`, and registered `plynx ops` schemas."
        ]
        try:
            ctx_data = json.loads(stage_ctx_path.read_text(encoding="utf-8"))
            if isinstance(ctx_data, Mapping):
                if isinstance(ctx_data.get("nodes"), Mapping):
                    for s_nid, s_info in ctx_data["nodes"].items():
                        if not isinstance(s_info, Mapping):
                            continue
                        s_status = s_info.get("status", "UNKNOWN")
                        s_warns = s_info.get("warnings") or []
                        s_err = s_info.get("error")
                        if s_status == "FAILED" or s_warns or s_err:
                            detail = f"status={s_status}"
                            if s_err:
                                detail += f", error={s_err!r}"
                            if s_warns:
                                detail += f", warnings={list(s_warns)!r}"
                            ctx_lines.append(f"- Node `{s_nid}`: {detail}")
                wf_yaml = ctx_data.get("workflow_snapshot_yaml")
                if isinstance(wf_yaml, str) and 0 < len(wf_yaml) <= 8000:
                    ctx_lines.append(
                        f"\nCurrent `workflow.snapshot.yaml`:\n```yaml\n{wf_yaml.strip()}\n```"
                    )
        except Exception:
            pass
        sections.append("## Stage Context\n" + "\n".join(ctx_lines))

    if turn_index > 0 and user_answers is not None:
        answers_json = json.dumps(dict(user_answers), indent=2, ensure_ascii=False)
        sections.append(
            f"## User Answers to Turn {turn_index - 1} Questions\n```json\n{answers_json}\n```"
        )

    return "\n\n".join(sections) + "\n"


def load_agent_turns(node_dir: Path) -> AgentTurnsManifest:
    """Load ``nodes/<node_id>/agent_turns.json`` if present, else return an empty manifest."""
    turns_path = node_dir / AGENT_TURNS_FILENAME
    if not turns_path.is_file():
        return AgentTurnsManifest()
    return AgentTurnsManifest.from_json(turns_path.read_bytes())


def save_agent_turns(node_dir: Path, manifest: AgentTurnsManifest) -> None:
    """Atomically write ``nodes/<node_id>/agent_turns.json``."""
    _atomic_write_text(node_dir / AGENT_TURNS_FILENAME, manifest.to_json())


class AgentOp(Op):
    """Base class for coding-agent-backed operations (Choice A inherited ``run()`` or Choice B)."""

    CATEGORY: ClassVar[str] = "Uncategorized"
    CACHEABLE: ClassVar[bool] = True
    ALLOW_EXTRA_INPUTS: ClassVar[bool] = True
    ALLOW_GRAPH_EDITS: ClassVar[GraphEditPolicy] = GraphEditPolicy.FORBIDDEN
    TIMEOUT_SECONDS: ClassVar[int | None] = None

    def _resolve_graph_edit_policy(
        self,
        explicit: GraphEditPolicy | str | None,
        *,
        state: _AgentExecutionState | None,
        node_dir: Path,
    ) -> GraphEditPolicy:
        if explicit is not None:
            return explicit if isinstance(explicit, GraphEditPolicy) else GraphEditPolicy(explicit)
        if (
            state is not None
            and state.inputs_manifest is not None
            and state.inputs_manifest.allow_graph_edits is not None
        ):
            return state.inputs_manifest.allow_graph_edits
        stage_ctx_path = node_dir / STAGE_CONTEXT_FILENAME
        if stage_ctx_path.is_file():
            try:
                ctx_data = json.loads(stage_ctx_path.read_text(encoding="utf-8"))
                raw_pol = (
                    ctx_data.get("allow_graph_edits") if isinstance(ctx_data, Mapping) else None
                )
                if isinstance(raw_pol, str) and raw_pol:
                    return GraphEditPolicy(raw_pol)
            except Exception:
                pass
        return self.ALLOW_GRAPH_EDITS

    def agent_turn(
        self,
        *,
        prompt: str = "",
        prompt_file: Path | str | None = None,
        provider: str | AgentProvider = AgentProvider.DEFAULT,
        model: str = "",
        turn_index: int | None = None,
        resume_session_id: str | None = None,
        user_answers: Mapping[str, AnswerValue] | None = None,
        allow_graph_edits: GraphEditPolicy | None = None,
        timeout_seconds: int | float | None = None,
        custom_command: str | None = None,
        mock_responses: Any = None,
        **task_inputs: Any,
    ) -> AgentTurnRecord:
        """Execute one agent turn or replay it in 0 tokens from ``agent_turns.json``."""
        node_dir, workdir, state = _resolve_dirs()
        if turn_index is None:
            if state is not None:
                idx = state.turn_counter
                state.turn_counter += 1
            else:
                idx = getattr(self, "_local_turn_counter", 0)
                self._local_turn_counter = idx + 1
        else:
            idx = turn_index
            if state is not None and state.turn_counter <= idx:
                state.turn_counter = idx + 1

        manifest = load_agent_turns(node_dir)
        if idx < len(manifest.turns):
            return manifest.turns[idx]
        if idx > len(manifest.turns):
            raise ProtocolError(
                f"Cannot execute agent turn {idx} when only {len(manifest.turns)} prior turn(s) exist"
            )

        effective_policy = self._resolve_graph_edit_policy(
            allow_graph_edits, state=state, node_dir=node_dir
        )
        effective_timeout = timeout_seconds if timeout_seconds is not None else self.TIMEOUT_SECONDS

        domain_parts: list[str] = []
        if prompt_file is not None:
            pf_path = Path(prompt_file) if not isinstance(prompt_file, Path) else prompt_file
            if pf_path.as_posix().strip():
                if not pf_path.is_file():
                    raise FileNotFoundError(f"prompt_file not found: {pf_path}")
                domain_parts.append(pf_path.read_text(encoding="utf-8").strip())
        if prompt and prompt.strip():
            domain_parts.append(prompt.strip())
        if not domain_parts and self.__doc__:
            domain_parts.append(inspect.cleandoc(self.__doc__))
        domain_text = "\n\n".join(part for part in domain_parts if part)

        resolved_provider = resolve_runtime_provider(provider)
        resolved_model = resolve_runtime_model(model)

        schema_dict = generate_turn_schema(type(self), allow_graph_edits=effective_policy)
        schema_path = workdir / TURN_SCHEMA_FILENAME
        output_path = workdir / TURN_OUTPUT_FILENAME
        _atomic_write_text(
            schema_path,
            json.dumps(schema_dict, indent=2, ensure_ascii=False) + "\n",
        )

        full_prompt = _build_full_turn_prompt(
            node_dir=node_dir,
            workdir=workdir,
            schema_path=schema_path,
            output_path=output_path,
            domain_prompt=domain_text,
            task_inputs=task_inputs,
            allow_graph_edits=effective_policy,
            turn_index=idx,
            user_answers=user_answers,
        )

        started_at = time.time()
        adapter_res = execute_provider_turn(
            resolved_provider,
            turn_index=idx,
            node_id=node_dir.name,
            prompt=full_prompt,
            schema_path=schema_path,
            schema_dict=schema_dict,
            output_path=output_path,
            workdir=workdir,
            model=resolved_model,
            resume_session_id=resume_session_id,
            user_answers=user_answers,
            timeout_seconds=effective_timeout,
            custom_command=custom_command,
            mock_responses=mock_responses,
        )
        finished_at = max(time.time(), started_at)

        envelope = adapter_res.envelope
        raw_status = envelope.get("status")
        try:
            status = AgentTurnStatus(str(raw_status))
        except ValueError as exc:
            raise ProtocolError(f"Agent turn returned invalid status {raw_status!r}") from exc

        if (
            status == AgentTurnStatus.PROPOSE_PATCH
            and effective_policy == GraphEditPolicy.FORBIDDEN
        ):
            raise ProtocolError(
                "Agent proposed a graph_patch while allow_graph_edits is 'forbidden'"
            )

        questions: list[CheckpointQuestion] = []
        if status == AgentTurnStatus.NEEDS_INPUT:
            raw_qs = envelope.get("questions")
            if not isinstance(raw_qs, list) or not raw_qs:
                raise ProtocolError(
                    "Agent turn with status 'needs_input' must provide a non-empty 'questions' list"
                )
            questions = [
                q if isinstance(q, CheckpointQuestion) else CheckpointQuestion.from_dict(q)
                for q in raw_qs
            ]

        graph_patch: GraphPatchPayload | None = None
        if status == AgentTurnStatus.PROPOSE_PATCH:
            raw_patch = envelope.get("graph_patch")
            if not isinstance(raw_patch, Mapping):
                raise ProtocolError(
                    "Agent turn with status 'propose_patch' must provide a 'graph_patch' object"
                )
            graph_patch = GraphPatchPayload.from_dict(raw_patch)

        outputs_payload: dict[str, JsonValue] | None = None
        if status == AgentTurnStatus.COMPLETED:
            raw_outs = envelope.get("outputs")
            if not isinstance(raw_outs, Mapping):
                raise ProtocolError(
                    "Agent turn with status 'completed' must provide an 'outputs' object"
                )
            outputs_payload = dict(raw_outs)
        elif isinstance(envelope.get("outputs"), Mapping):
            outputs_payload = dict(envelope["outputs"])

        record = AgentTurnRecord(
            turn_index=idx,
            provider=resolved_provider,
            model=resolved_model,
            session_id=adapter_res.session_id,
            status=status,
            prompt_summary=_summarize_prompt(
                domain_text or type(self).TITLE or type(self).__name__
            ),
            outputs=outputs_payload,
            questions=questions,
            user_answers=None,
            graph_patch=graph_patch,
            started_at=started_at,
            finished_at=finished_at,
        )
        manifest.turns.append(record)
        save_agent_turns(node_dir, manifest)
        return record

    def run_agent(
        self,
        *,
        prompt_file: MarkdownFile | None = None,
        prompt: str = "",
        provider: str | AgentProvider = AgentProvider.DEFAULT,
        model: str = "",
        allow_graph_edits: GraphEditPolicy | None = None,
        timeout_seconds: int | float | None = None,
        custom_command: str | None = None,
        mock_responses: Any = None,
        **extra: Any,
    ) -> dict[str, Any]:
        """Run the multi-turn agent loop with 0-token checkpoint replay and output materialization."""
        node_dir, workdir, _ = _resolve_dirs()
        turn_idx = 0
        prev_session_id: str | None = None
        latest_answers: dict[str, AnswerValue] | None = None

        while True:
            turn = self.agent_turn(
                prompt=prompt,
                prompt_file=prompt_file,
                provider=provider,
                model=model,
                turn_index=turn_idx,
                resume_session_id=prev_session_id,
                user_answers=latest_answers,
                allow_graph_edits=allow_graph_edits,
                timeout_seconds=timeout_seconds,
                custom_command=custom_command,
                mock_responses=mock_responses,
                **extra,
            )

            if turn.status == AgentTurnStatus.NEEDS_INPUT:
                answers = self.checkpoint_batch(turn.questions)
                if turn.user_answers != answers:
                    manifest = load_agent_turns(node_dir)
                    if turn_idx < len(manifest.turns):
                        manifest.turns[turn_idx].user_answers = dict(answers)
                        save_agent_turns(node_dir, manifest)
                prev_session_id = turn.session_id
                latest_answers = answers
                turn_idx += 1
                continue

            if turn.status == AgentTurnStatus.PROPOSE_PATCH:
                assert turn.graph_patch is not None
                _atomic_write_text(node_dir / GRAPH_PATCH_FILENAME, turn.graph_patch.to_json())
                raw_patch_outs: Mapping[str, Any] = turn.outputs or {}
                specs = _extract_output_specs_for_op(type(self))
                if not raw_patch_outs and set(specs.keys()) == {"summary"}:
                    raw_patch_outs = {"summary": f"Proposed graph patch: {turn.graph_patch.reason}"}
                return materialize_turn_outputs(
                    raw_patch_outs,
                    type(self),
                    node_dir=node_dir,
                    workdir=workdir,
                )

            assert turn.status == AgentTurnStatus.COMPLETED
            return materialize_turn_outputs(
                turn.outputs or {},
                type(self),
                node_dir=node_dir,
                workdir=workdir,
            )

    if TYPE_CHECKING:

        def run(self, *args: Any, **kwargs: Any) -> Any: ...

    else:

        def run(
            self,
            prompt_file: MarkdownFile | None = None,
            prompt: str = "",
            provider: AgentProviderLiteral = "default",
            model: str = "",
            **extra: Any,
        ) -> Any:
            """Default Choice A entrypoint delegating to ``self.run_agent(...)``."""
            return self.run_agent(
                prompt_file=prompt_file,
                prompt=prompt,
                provider=provider,
                model=model,
                **extra,
            )


class StageValidatorOutputs(TypedDict):
    """Default output schema for ``StageValidatorOp`` subclasses."""

    summary: str


class StageValidatorOp(AgentOp):
    """Base class for bounded stage-end validators / supervisors (``FEAT-AGT-3``)."""

    CATEGORY: ClassVar[str] = "Agents / Validators"
    ALLOW_EXTRA_INPUTS: ClassVar[bool] = True
    ALLOW_GRAPH_EDITS: ClassVar[GraphEditPolicy] = GraphEditPolicy.CONFIRM

    Outputs = StageValidatorOutputs


__all__ = [
    "AGENT_TURNS_FILENAME",
    "GRAPH_PATCH_FILENAME",
    "STAGE_CONTEXT_FILENAME",
    "TURN_OUTPUT_FILENAME",
    "TURN_SCHEMA_FILENAME",
    "AgentOp",
    "StageValidatorOp",
    "StageValidatorOutputs",
    "agent_context",
    "generate_turn_schema",
    "load_agent_turns",
    "materialize_turn_outputs",
    "save_agent_turns",
]
