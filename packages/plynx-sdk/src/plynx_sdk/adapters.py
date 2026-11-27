"""Modular multi-provider CLI coding harness adapters (ENTRYPOINT.md section 2.3.E).

Standard library only. Spawns non-interactive CLI coding agents with ``stdin=DEVNULL``,
no forced default timeout, explicit ``--resume <session_id>`` (never ``--continue``),
and no ``--bare`` flag so upward ``.agents/skills/`` discovery works naturally.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from plynx_sdk.protocol import AgentProvider, AgentTurnStatus, AnswerValue, ProtocolError

_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_VALID_TURN_STATUSES: frozenset[str] = frozenset(s.value for s in AgentTurnStatus)

# Keep inline CLI prompt arguments safely below Windows CreateProcess (~32 KB)
# and POSIX ARG_MAX limits; larger prompts are read from workdir/turn_prompt.md.
_MAX_INLINE_PROMPT_BYTES = 24_000


@dataclass(frozen=True)
class AdapterTurnResult:
    """Parsed JSON response envelope and optional session ID from one CLI turn."""

    envelope: dict[str, Any]
    session_id: str | None = None


def _atomic_write_utf8(path: Path, content: str) -> None:
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


def resolve_runtime_provider(provider: str | AgentProvider) -> AgentProvider:
    """Resolve ``provider`` (falling back to ``PLYNX_AGENT_PROVIDER`` when ``default``)."""
    raw = provider.value if isinstance(provider, AgentProvider) else str(provider).strip()
    if not raw or raw == AgentProvider.DEFAULT.value:
        env_val = os.environ.get("PLYNX_AGENT_PROVIDER", "").strip()
        if env_val and env_val != AgentProvider.DEFAULT.value:
            raw = env_val
    try:
        resolved = AgentProvider(raw)
    except ValueError as exc:
        raise ProtocolError(f"Unsupported agent provider: {raw!r}") from exc
    if resolved == AgentProvider.DEFAULT:
        raise RuntimeError(
            "Agent provider resolved to 'default'. Configure 'agent.provider' in plynx.yaml, "
            "workflow.yaml, '--agent-provider', PLYNX_AGENT_PROVIDER, or the node 'provider' port."
        )
    return resolved


def resolve_runtime_model(model: str) -> str:
    """Resolve ``model`` (falling back to ``PLYNX_AGENT_MODEL`` when empty)."""
    cleaned = model.strip()
    if cleaned:
        return cleaned
    return os.environ.get("PLYNX_AGENT_MODEL", "").strip()


def _sanitize_schema_for_claude(node: Any) -> Any:
    """Strip numeric ``minimum``/``maximum`` rejected by Anthropic's raw JSON schema decoder."""
    if isinstance(node, list):
        return [_sanitize_schema_for_claude(item) for item in node]
    if not isinstance(node, Mapping):
        return node

    out: dict[str, Any] = {}
    min_val = node.get("minimum")
    max_val = node.get("maximum")
    for k, v in node.items():
        if k in ("$schema", "minimum", "maximum"):
            continue
        out[k] = _sanitize_schema_for_claude(v)

    if min_val is not None or max_val is not None:
        bounds_note = f"Range: [{min_val}, {max_val}]."
        existing_desc = str(out.get("description", "")).strip()
        out["description"] = f"{existing_desc} {bounds_note}".strip()
    return out


def _schema_has_open_object(node: Any) -> bool:
    """Return True if ``node`` contains an unconstrained ``{"type": "object"}`` map.

    OpenAI's ``strict: true`` grammar compiler (used by ``codex exec --output-schema``)
    rejects object schemas without fixed ``properties`` (such as dynamic ``graph_patch``
    maps or ``dict`` output ports).
    """
    if isinstance(node, list):
        return any(_schema_has_open_object(item) for item in node)
    if not isinstance(node, Mapping):
        return False
    if node.get("type") == "object" and not isinstance(node.get("properties"), Mapping):
        return True
    return any(_schema_has_open_object(v) for v in node.values())


def _make_nullable(subschema: dict[str, Any]) -> dict[str, Any]:
    if "anyOf" in subschema and isinstance(subschema["anyOf"], list):
        if any(
            isinstance(opt, Mapping) and opt.get("type") == "null" for opt in subschema["anyOf"]
        ):
            return subschema
        return {"anyOf": [*subschema["anyOf"], {"type": "null"}]}
    return {"anyOf": [subschema, {"type": "null"}]}


def _to_openai_strict_schema(node: Any) -> Any:
    """Normalize a closed JSON Schema into OpenAI's ``strict: true`` subset for Codex."""
    if isinstance(node, list):
        return [_to_openai_strict_schema(item) for item in node]
    if not isinstance(node, Mapping):
        return node

    out: dict[str, Any] = {
        k: _to_openai_strict_schema(v) for k, v in node.items() if k != "$schema"
    }
    if out.get("type") == "object" and isinstance(out.get("properties"), dict):
        props: dict[str, Any] = out["properties"]
        orig_req = set(out.get("required") or [])
        strict_props: dict[str, Any] = {}
        for prop_name, prop_schema in props.items():
            if prop_name in orig_req or not isinstance(prop_schema, dict):
                strict_props[prop_name] = prop_schema
            else:
                strict_props[prop_name] = _make_nullable(prop_schema)
        out["properties"] = strict_props
        out["required"] = list(strict_props.keys())
        out["additionalProperties"] = False
    return out


def _append_positional_prompt(cmd: list[str], prompt: str) -> None:
    """Append positional ``prompt``, inserting ``--`` if ``prompt`` starts with ``-``."""
    if prompt.startswith("-"):
        cmd.append("--")
    cmd.append(prompt)


def build_provider_command(
    provider: AgentProvider,
    *,
    prompt: str,
    schema_path: Path,
    schema_dict: Mapping[str, Any],
    output_path: Path,
    prompt_file_path: Path,
    workdir: Path,
    model: str = "",
    resume_session_id: str | None = None,
    custom_command: str | None = None,
) -> list[str]:
    """Construct the non-interactive subprocess command list for ``provider``.

    Never uses ``--continue`` or ``--bare``. Omits model flags when ``model == ""``.
    """
    model_clean = model.strip()
    sid = resume_session_id.strip() if resume_session_id else ""

    if provider == AgentProvider.CLAUDE:
        claude_schema = _sanitize_schema_for_claude(schema_dict)
        compact_schema = json.dumps(claude_schema, separators=(",", ":"), ensure_ascii=False)
        cmd = [
            "claude",
            "-p",
            "--output-format",
            "json",
            "--json-schema",
            compact_schema,
            "--add-dir",
            str(workdir.parent),
        ]
        if model_clean:
            cmd.extend(["--model", model_clean])
        if sid:
            cmd.extend(["--resume", sid])
        cmd.append("--dangerously-skip-permissions")
        _append_positional_prompt(cmd, prompt)
        return cmd

    if provider == AgentProvider.CURSOR:
        cmd = [
            "cursor-agent",
            "-p",
            "--output-format",
            "json",
        ]
        if model_clean:
            cmd.extend(["--model", model_clean])
        if sid:
            cmd.extend(["--resume", sid])
        cmd.append("--force")
        _append_positional_prompt(cmd, prompt)
        return cmd

    if provider == AgentProvider.CODEX:
        if sid:
            cmd = ["codex", "exec", "resume", "--full-auto"]
            if model_clean:
                cmd.extend(["-m", model_clean])
            cmd.append(sid)
            _append_positional_prompt(cmd, prompt)
            return cmd

        cmd = ["codex", "exec", "--full-auto"]
        if not _schema_has_open_object(schema_dict):
            codex_schema_path = schema_path
            if schema_path.parent.is_dir():
                codex_schema_path = schema_path.with_name("turn_schema.codex.json")
                strict_schema = _to_openai_strict_schema(schema_dict)
                _atomic_write_utf8(
                    codex_schema_path,
                    json.dumps(strict_schema, indent=2, ensure_ascii=False) + "\n",
                )
            cmd.extend(["--output-schema", str(codex_schema_path)])
        if model_clean:
            cmd.extend(["-m", model_clean])
        _append_positional_prompt(cmd, prompt)
        return cmd

    if provider == AgentProvider.GEMINI:
        binary = "gemini"
        if shutil.which("gemini") is None and shutil.which("agy") is not None:
            binary = "agy"
        if binary == "agy":
            cmd = [
                binary,
                "--output-format",
                "json",
                "--json-schema",
                str(schema_path),
                "--add-dir",
                str(workdir.parent),
                "--dangerously-skip-permissions",
            ]
            if model_clean:
                cmd.extend(["--model", model_clean])
            if sid:
                cmd.extend(["--conversation", sid])
            if prompt.startswith("-"):
                cmd.append(f"--print={prompt}")
            else:
                cmd.extend(["-p", prompt])
            return cmd

        cmd = [binary, "--output-format", "json", "--yolo"]
        if model_clean:
            cmd.extend(["-m", model_clean])
        if sid:
            cmd.extend(["--resume", sid])
        if prompt.startswith("-"):
            cmd.append(f"--prompt={prompt}")
        else:
            cmd.extend(["-p", prompt])
        return cmd

    if provider == AgentProvider.OPENCODE:
        cmd = ["opencode", "run", "--format", "json"]
        if model_clean:
            cmd.extend(["-m", model_clean])
        if sid:
            cmd.extend(["-s", sid])
        _append_positional_prompt(cmd, prompt)
        return cmd

    if provider == AgentProvider.GOOSE:
        cmd = ["goose", "run"]
        if model_clean:
            cmd.extend(["--model", model_clean])
        if sid:
            cmd.extend(["--resume", "--name", sid])
        if prompt.startswith("-"):
            cmd.append(f"--text={prompt}")
        else:
            cmd.extend(["--text", prompt])
        return cmd

    if provider == AgentProvider.AIDER:
        cmd = [
            "aider",
            "--yes-always",
            "--no-input",
            "--no-auto-commits",
            "--no-gitignore",
        ]
        if model_clean:
            cmd.extend(["--model", model_clean])
        if prompt.startswith("-"):
            cmd.append(f"--message={prompt}")
        else:
            cmd.extend(["--message", prompt])
        return cmd

    if provider == AgentProvider.CUSTOM:
        template = (
            custom_command
            if custom_command is not None and custom_command.strip()
            else os.environ.get("PLYNX_AGENT_CUSTOM_COMMAND", "").strip()
        )
        if not template:
            raise RuntimeError(
                "AgentProvider.CUSTOM requires 'agent.custom_command' in plynx.yaml "
                "or PLYNX_AGENT_CUSTOM_COMMAND in the environment"
            )
        raw_tokens = shlex.split(template, posix=(os.name != "nt"))
        if not raw_tokens:
            raise RuntimeError("AgentProvider.CUSTOM command template is empty")
        substitutions = {
            "prompt": prompt,
            "prompt_file": str(prompt_file_path),
            "schema_path": str(schema_path),
            "output_path": str(output_path),
            "model": model_clean,
            "session_id": sid,
            "workdir": str(workdir),
        }
        has_prompt_placeholder = any(
            "{prompt}" in tok or "{prompt_file}" in tok for tok in raw_tokens
        )
        rendered: list[str] = []
        for tok in raw_tokens:
            formatted = tok.format(**substitutions)
            if formatted or tok == "{prompt}":
                rendered.append(formatted)
        if not has_prompt_placeholder:
            _append_positional_prompt(rendered, prompt)
        return rendered

    raise ProtocolError(f"Cannot build subprocess command for provider {provider.value!r}")


def _extract_session_id(obj: Mapping[str, Any]) -> str | None:
    for key in ("session_id", "sessionID", "chat_id", "thread_id", "conversation_id"):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    part = obj.get("part")
    if isinstance(part, Mapping):
        val = part.get("sessionID") or part.get("session_id")
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _is_turn_envelope(obj: Any) -> bool:
    """Return True iff ``obj`` is a PLynx turn envelope (never an outer CLI wrapper)."""
    if not isinstance(obj, Mapping):
        return False
    status = obj.get("status")
    return isinstance(status, str) and status in _VALID_TURN_STATUSES


def _normalize_envelope(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Strip nullable OpenAI strict-mode ``None`` placeholders on optional envelope fields."""
    cleaned: dict[str, Any] = {}
    for k, v in raw.items():
        if k in ("outputs", "questions", "graph_patch") and v is None:
            continue
        cleaned[k] = v
    raw_qs = cleaned.get("questions")
    if isinstance(raw_qs, list):
        norm_qs: list[Any] = []
        for q in raw_qs:
            if isinstance(q, Mapping):
                norm_qs.append({qk: qv for qk, qv in q.items() if qv is not None})
            else:
                norm_qs.append(q)
        cleaned["questions"] = norm_qs
    return cleaned


def _parse_envelope_from_text(text: str) -> tuple[dict[str, Any] | None, str | None]:
    """Extract ``(envelope, session_id)`` from CLI stdout JSON, wrapper, JSONL, or fenced block."""
    stripped = text.strip()
    if not stripped:
        return None, None

    discovered_sid: str | None = None

    def _inspect_parsed(parsed: Any) -> dict[str, Any] | None:
        nonlocal discovered_sid
        if not isinstance(parsed, Mapping):
            return None
        sid = _extract_session_id(parsed)
        if sid is not None:
            discovered_sid = sid
        # Check schema-constrained structured_output first (claude / agy --json-schema),
        # before top-level or text fields, since outer CLI wrappers carry their own "status"
        # (e.g. agy's {"status": "SUCCESS", "structured_output": {...}}).
        structured = parsed.get("structured_output")
        if _is_turn_envelope(structured):
            assert isinstance(structured, Mapping)
            return _normalize_envelope(structured)
        if _is_turn_envelope(parsed):
            return _normalize_envelope(parsed)
        for nested_key in ("output", "response", "data", "result", "message", "content"):
            nested = parsed.get(nested_key)
            if _is_turn_envelope(nested):
                assert isinstance(nested, Mapping)
                return _normalize_envelope(nested)
        for text_key in ("result", "response", "message", "content"):
            text_field = parsed.get(text_key)
            if isinstance(text_field, str) and text_field.strip():
                inner_env, inner_sid = _parse_envelope_from_text(text_field)
                if inner_sid and not discovered_sid:
                    discovered_sid = inner_sid
                if inner_env is not None:
                    return inner_env
        return None

    try:
        whole = json.loads(stripped)
        env = _inspect_parsed(whole)
        if env is not None:
            return env, discovered_sid
    except json.JSONDecodeError:
        pass

    # Try JSONL lines (e.g., codex / opencode event streams), scanning all lines for
    # session_id and reassembling streamed opencode ``part.text`` chunks if needed.
    lines = [ln.strip() for ln in stripped.splitlines() if ln.strip()]
    if len(lines) > 1:
        last_env: dict[str, Any] | None = None
        streamed_text_parts: list[str] = []
        for line in lines:
            if not (line.startswith("{") and line.endswith("}")):
                continue
            try:
                line_obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            cand = _inspect_parsed(line_obj)
            if cand is not None:
                last_env = cand
            if isinstance(line_obj, Mapping) and line_obj.get("type") == "text":
                part = line_obj.get("part")
                if isinstance(part, Mapping) and isinstance(part.get("text"), str):
                    streamed_text_parts.append(part["text"])
        if last_env is not None:
            return last_env, discovered_sid
        if streamed_text_parts:
            joined_stream = "".join(streamed_text_parts)
            stream_env, stream_sid = _parse_envelope_from_text(joined_stream)
            if stream_sid and not discovered_sid:
                discovered_sid = stream_sid
            if stream_env is not None:
                return stream_env, discovered_sid

    # Try fenced ```json ... ``` blocks
    matches = list(_FENCED_JSON_RE.finditer(stripped))
    for match in reversed(matches):
        try:
            block_obj = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        cand = _inspect_parsed(block_obj)
        if cand is not None:
            return cand, discovered_sid

    return None, discovered_sid


def _load_mock_turn(
    *,
    turn_index: int,
    node_id: str,
    prompt: str,
    workdir: Path,
    output_path: Path,
    resume_session_id: str | None,
    user_answers: Mapping[str, AnswerValue] | None,
    mock_responses: Any = None,
) -> AdapterTurnResult:
    source = mock_responses
    if source is None:
        raw_env = os.environ.get("PLYNX_MOCK_AGENT_RESPONSES", "").strip()
        if not raw_env:
            raise RuntimeError(
                "AgentProvider.MOCK requires 'mock_responses' or PLYNX_MOCK_AGENT_RESPONSES "
                "(inline JSON or path to a JSON file)"
            )
        if raw_env.startswith(("{", "[")):
            try:
                source = json.loads(raw_env)
            except json.JSONDecodeError as exc:
                raise ProtocolError(f"Invalid JSON in PLYNX_MOCK_AGENT_RESPONSES: {exc}") from exc
        else:
            candidate_path = Path(raw_env)
            if not candidate_path.is_file():
                raise FileNotFoundError(
                    f"PLYNX_MOCK_AGENT_RESPONSES file not found: {candidate_path}"
                )
            source = json.loads(candidate_path.read_text(encoding="utf-8"))

    if callable(source):
        selected = source(
            turn_index=turn_index,
            node_id=node_id,
            prompt=prompt,
            workdir=workdir,
            resume_session_id=resume_session_id,
            user_answers=user_answers,
        )
    elif isinstance(source, str):
        selected = json.loads(source)
    else:
        selected = source

    # Unwrap node-scoped mapping if keyed by node_id (and not already a turn envelope)
    if (
        isinstance(selected, Mapping)
        and not _is_turn_envelope(selected)
        and "turns" not in selected
        and node_id in selected
    ):
        selected = selected[node_id]
    elif (
        isinstance(selected, Mapping)
        and not _is_turn_envelope(selected)
        and "turns" not in selected
        and "*" in selected
    ):
        selected = selected["*"]

    if isinstance(selected, Mapping) and "turns" in selected and not _is_turn_envelope(selected):
        selected = selected["turns"]

    if isinstance(selected, list):
        if turn_index >= len(selected):
            raise RuntimeError(
                f"AgentProvider.MOCK has {len(selected)} scripted turn(s), "
                f"but turn_index {turn_index} was requested"
            )
        turn_payload = selected[turn_index]
    elif isinstance(selected, Mapping) and str(turn_index) in selected:
        turn_payload = selected[str(turn_index)]
    elif isinstance(selected, Mapping):
        turn_payload = selected
    else:
        raise ProtocolError(
            f"Unsupported mock agent response payload of type {type(selected).__name__}"
        )

    if not isinstance(turn_payload, Mapping):
        raise ProtocolError("Mock agent turn payload must be a JSON object")

    payload_copy = dict(turn_payload)
    stdout_only = bool(payload_copy.pop("_stdout_only", False))
    explicit_sid = _extract_session_id(payload_copy)
    session_id = explicit_sid or resume_session_id or f"mock_session_{node_id or '0'}"
    payload_copy.pop("session_id", None)

    # Allow mock scripts to write files inside workdir via optional "_files" helper
    mock_files = payload_copy.pop("_files", None)
    if isinstance(mock_files, Mapping):
        for rel_file, content in mock_files.items():
            target = (workdir / str(rel_file)).resolve()
            if not target.is_relative_to(workdir.resolve()):
                raise ProtocolError(f"Mock _files path escapes workdir: {rel_file!r}")
            _atomic_write_utf8(target, str(content))

    serialized = json.dumps(payload_copy, indent=2, ensure_ascii=False) + "\n"
    if stdout_only:
        wrapper = json.dumps({"session_id": session_id, "result": serialized})
        parsed_env, parsed_sid = _parse_envelope_from_text(wrapper)
        if parsed_env is None:
            raise ProtocolError("Mock stdout fallback failed to parse turn envelope")
        return AdapterTurnResult(envelope=parsed_env, session_id=parsed_sid or session_id)

    _atomic_write_utf8(output_path, serialized)
    disk_env = json.loads(output_path.read_text(encoding="utf-8"))
    return AdapterTurnResult(envelope=_normalize_envelope(disk_env), session_id=session_id)


def execute_provider_turn(
    provider: AgentProvider,
    *,
    turn_index: int,
    node_id: str,
    prompt: str,
    schema_path: Path,
    schema_dict: Mapping[str, Any],
    output_path: Path,
    workdir: Path,
    model: str = "",
    resume_session_id: str | None = None,
    user_answers: Mapping[str, AnswerValue] | None = None,
    timeout_seconds: int | float | None = None,
    custom_command: str | None = None,
    mock_responses: Any = None,
) -> AdapterTurnResult:
    """Execute one non-interactive coding-agent turn and return ``AdapterTurnResult``."""
    prompt_file_path = workdir / "turn_prompt.md"
    _atomic_write_utf8(prompt_file_path, prompt)

    if output_path.is_file():
        output_path.unlink()

    if provider == AgentProvider.MOCK:
        return _load_mock_turn(
            turn_index=turn_index,
            node_id=node_id,
            prompt=prompt,
            workdir=workdir,
            output_path=output_path,
            resume_session_id=resume_session_id,
            user_answers=user_answers,
            mock_responses=mock_responses,
        )

    cli_prompt = prompt
    if len(prompt.encode("utf-8")) > _MAX_INLINE_PROMPT_BYTES:
        cli_prompt = (
            f"Read your full task instructions from `{prompt_file_path}` and write your "
            f"final JSON response conforming to `{schema_path}` into `{output_path}`."
        )

    effective_sid = resume_session_id
    goose_generated_sid: str | None = None
    if provider == AgentProvider.GOOSE and not effective_sid:
        safe_nid = re.sub(r"[^a-zA-Z0-9_-]", "_", node_id or "node")
        goose_generated_sid = f"plynx_{safe_nid}_{os.getpid()}"

    cmd = build_provider_command(
        provider,
        prompt=cli_prompt,
        schema_path=schema_path,
        schema_dict=schema_dict,
        output_path=output_path,
        prompt_file_path=prompt_file_path,
        workdir=workdir,
        model=model,
        resume_session_id=effective_sid,
        custom_command=custom_command,
    )
    if goose_generated_sid is not None and provider == AgentProvider.GOOSE:
        # Name Turn 0 session explicitly so Turn 1 `--resume --name <sid>` can locate it.
        cmd = [*cmd[:2], "--name", goose_generated_sid, *cmd[2:]]

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(workdir),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Agent CLI binary {cmd[0]!r} for provider {provider.value!r} was not found on PATH"
        ) from exc

    if proc.stderr:
        sys.stderr.write(proc.stderr)
        if not proc.stderr.endswith("\n"):
            sys.stderr.write("\n")
        sys.stderr.flush()

    stdout_env, stdout_sid = _parse_envelope_from_text(proc.stdout or "")
    fallback_sid = stdout_sid or resume_session_id or goose_generated_sid

    if output_path.is_file():
        try:
            raw_disk = json.loads(output_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ProtocolError(
                f"turn_output.json written by {provider.value!r} is not valid JSON: {exc}"
            ) from exc
        if not isinstance(raw_disk, Mapping):
            raise ProtocolError("turn_output.json must contain a top-level JSON object")
        disk_dict = _normalize_envelope(raw_disk)
        disk_sid = _extract_session_id(disk_dict) or fallback_sid
        disk_dict.pop("session_id", None)
        return AdapterTurnResult(envelope=disk_dict, session_id=disk_sid)

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        snippet = f": {detail[:400]}" if detail else ""
        raise RuntimeError(
            f"Agent CLI {provider.value!r} exited with code {proc.returncode}{snippet}"
        )

    if stdout_env is not None:
        clean_env = dict(stdout_env)
        env_sid = _extract_session_id(clean_env) or fallback_sid
        clean_env.pop("session_id", None)
        return AdapterTurnResult(envelope=clean_env, session_id=env_sid)

    raise ProtocolError(
        f"Agent CLI {provider.value!r} did not write {output_path.name} "
        "and did not return a valid JSON envelope on stdout"
    )


__all__ = [
    "AdapterTurnResult",
    "build_provider_command",
    "execute_provider_turn",
    "resolve_runtime_model",
    "resolve_runtime_provider",
]
