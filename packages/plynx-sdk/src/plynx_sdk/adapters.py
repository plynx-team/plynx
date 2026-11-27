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

from plynx_sdk.protocol import AgentProvider, AnswerValue, ProtocolError

_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


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
    compact_schema = json.dumps(schema_dict, separators=(",", ":"), ensure_ascii=False)

    if provider == AgentProvider.CLAUDE:
        cmd = [
            "claude",
            "-p",
            "--output-format",
            "json",
            "--json-schema",
            compact_schema,
        ]
        if model_clean:
            cmd.extend(["--model", model_clean])
        if sid:
            cmd.extend(["--resume", sid])
        cmd.extend(["--dangerously-skip-permissions", prompt])
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
        cmd.extend(["--force", prompt])
        return cmd

    if provider == AgentProvider.CODEX:
        if sid:
            cmd = ["codex", "exec", "resume", "--full-auto"]
            if model_clean:
                cmd.extend(["-m", model_clean])
            cmd.extend([sid, prompt])
            return cmd
        cmd = [
            "codex",
            "exec",
            "--full-auto",
            "--output-schema",
            str(schema_path),
        ]
        if model_clean:
            cmd.extend(["-m", model_clean])
        cmd.append(prompt)
        return cmd

    if provider == AgentProvider.GEMINI:
        binary = "gemini"
        if shutil.which("gemini") is None and shutil.which("agy") is not None:
            binary = "agy"
        if binary == "agy":
            cmd = [
                binary,
                "-p",
                "--output-format",
                "json",
                "--json-schema",
                str(schema_path),
                "--dangerously-skip-permissions",
            ]
            if model_clean:
                cmd.extend(["--model", model_clean])
            if sid:
                cmd.extend(["--conversation", sid])
            cmd.append(prompt)
            return cmd
        cmd = [binary, "-p", prompt, "--output-format", "json", "--yolo"]
        if model_clean:
            cmd.extend(["-m", model_clean])
        if sid:
            cmd.extend(["--resume", sid])
        return cmd

    if provider == AgentProvider.OPENCODE:
        cmd = ["opencode", "run", "--format", "json"]
        if model_clean:
            cmd.extend(["-m", model_clean])
        if sid:
            cmd.extend(["-s", sid])
        cmd.append(prompt)
        return cmd

    if provider == AgentProvider.GOOSE:
        cmd = ["goose", "run"]
        if model_clean:
            cmd.extend(["--model", model_clean])
        if sid:
            cmd.extend(["--resume", "--name", sid])
        cmd.extend(["--text", prompt])
        return cmd

    if provider == AgentProvider.AIDER:
        cmd = ["aider", "--message", prompt, "--yes-always", "--no-input"]
        if model_clean:
            cmd.extend(["--model", model_clean])
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
            rendered.append(prompt)
        return rendered

    raise ProtocolError(f"Cannot build subprocess command for provider {provider.value!r}")


def _extract_session_id(obj: Mapping[str, Any]) -> str | None:
    for key in ("session_id", "sessionID", "chat_id", "thread_id", "conversation_id"):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _is_turn_envelope(obj: Any) -> bool:
    return isinstance(obj, Mapping) and isinstance(obj.get("status"), str)


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
        if _is_turn_envelope(parsed):
            return dict(parsed)
        for nested_key in ("structured_output", "output", "response", "data"):
            nested = parsed.get(nested_key)
            if _is_turn_envelope(nested):
                assert isinstance(nested, Mapping)
                return dict(nested)
        result_field = parsed.get("result") or parsed.get("message") or parsed.get("content")
        if _is_turn_envelope(result_field):
            assert isinstance(result_field, Mapping)
            return dict(result_field)
        if isinstance(result_field, str) and result_field.strip():
            inner_env, inner_sid = _parse_envelope_from_text(result_field)
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

    # Try JSONL lines (e.g., codex / opencode event streams) from last to first for envelope,
    # while scanning all lines for session_id.
    lines = [ln.strip() for ln in stripped.splitlines() if ln.strip()]
    if len(lines) > 1:
        last_env: dict[str, Any] | None = None
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
        if last_env is not None:
            return last_env, discovered_sid

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
    return AdapterTurnResult(envelope=disk_env, session_id=session_id)


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

    cmd = build_provider_command(
        provider,
        prompt=prompt,
        schema_path=schema_path,
        schema_dict=schema_dict,
        output_path=output_path,
        prompt_file_path=prompt_file_path,
        workdir=workdir,
        model=model,
        resume_session_id=resume_session_id,
        custom_command=custom_command,
    )

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

    if output_path.is_file():
        try:
            raw_disk = json.loads(output_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ProtocolError(
                f"turn_output.json written by {provider.value!r} is not valid JSON: {exc}"
            ) from exc
        if not isinstance(raw_disk, Mapping):
            raise ProtocolError("turn_output.json must contain a top-level JSON object")
        disk_dict = dict(raw_disk)
        disk_sid = _extract_session_id(disk_dict) or stdout_sid or resume_session_id
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
        env_sid = _extract_session_id(clean_env) or stdout_sid or resume_session_id
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
