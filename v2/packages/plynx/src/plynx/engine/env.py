"""Minimal ``.env`` parser and child environment builder (PROTOCOL.md sections 5 & 12)."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final

from ruamel.yaml import YAML

# System variables required by the OS, Python, and `uv` to spawn processes when
# `env_passthrough` restricts inherited host variables.
_ESSENTIAL_HOST_VARS: Final[frozenset[str]] = frozenset(
    {
        "PATH",
        "HOME",
        "USER",
        "LOGNAME",
        "SHELL",
        "TMPDIR",
        "TEMP",
        "TMP",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "PATHEXT",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "PROGRAMDATA",
        "PROGRAMFILES",
        "COMMONPROGRAMFILES",
        "HOMEDRIVE",
        "HOMEPATH",
        "UV_CACHE_DIR",
        "UV_PYTHON_INSTALL_DIR",
        "UV_TOOL_DIR",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
    }
)


def _unquote_dotenv_value(raw: str) -> str:
    val = raw.strip()
    if len(val) >= 2 and val[0] == "'" and val[-1] == "'":
        return val[1:-1]
    if len(val) >= 2 and val[0] == '"' and val[-1] == '"':
        inner = val[1:-1]
        out: list[str] = []
        idx = 0
        while idx < len(inner):
            ch = inner[idx]
            if ch == "\\" and idx + 1 < len(inner):
                nxt = inner[idx + 1]
                if nxt == "n":
                    out.append("\n")
                elif nxt == "r":
                    out.append("\r")
                elif nxt == "t":
                    out.append("\t")
                elif nxt in ('"', "\\", "$"):
                    out.append(nxt)
                else:
                    out.append(ch)
                    out.append(nxt)
                idx += 2
            else:
                out.append(ch)
                idx += 1
        return "".join(out)

    # Unquoted value: strip inline comment preceded by whitespace
    for idx, ch in enumerate(val):
        if ch == "#" and (idx == 0 or val[idx - 1].isspace()):
            val = val[:idx].rstrip()
            break
    return val


def parse_dotenv(content: str) -> dict[str, str]:
    """Parse ``.env`` file content into a dictionary of key-value pairs."""
    result: dict[str, str] = {}
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export ") and len(line) > 7 and line[6].isspace():
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, _, raw_val = line.partition("=")
        key = key.strip()
        if not key:
            continue
        result[key] = _unquote_dotenv_value(raw_val)
    return result


def load_dotenv_file(dotenv_path: Path) -> dict[str, str]:
    """Read and parse ``dotenv_path`` if it exists; return ``{}`` otherwise."""
    if not dotenv_path.is_file():
        return {}
    return parse_dotenv(dotenv_path.read_text(encoding="utf-8"))


def load_workspace_env_passthrough(workspace_root: Path) -> list[str] | None:
    """Read ``env_passthrough`` from ``<workspace_root>/plynx.yaml`` if present."""
    cfg_path = workspace_root / "plynx.yaml"
    if not cfg_path.is_file():
        return None
    yaml = YAML(typ="safe")
    try:
        parsed = yaml.load(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(parsed, Mapping):
        return None
    raw_passthrough = parsed.get("env_passthrough")
    if not isinstance(raw_passthrough, list):
        return None
    return [str(item) for item in raw_passthrough if isinstance(item, str)]


def build_child_environment(
    workspace_root: Path,
    env_dir: Path,
    *,
    host_env: Mapping[str, str] | None = None,
    env_passthrough: Sequence[str] | None = None,
    extra_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Construct the environment variable dictionary for a node child process."""
    source_host = os.environ if host_env is None else host_env
    effective_passthrough: Sequence[str]
    if env_passthrough is not None:
        effective_passthrough = env_passthrough
    else:
        configured = load_workspace_env_passthrough(workspace_root)
        effective_passthrough = configured if configured is not None else ["*"]

    passthrough_set = set(effective_passthrough)
    inherit_all = "*" in passthrough_set

    env: dict[str, str] = {}
    for key, val in source_host.items():
        if key == "VIRTUAL_ENV":
            continue
        if inherit_all or key in passthrough_set or key in _ESSENTIAL_HOST_VARS:
            env[key] = val

    dotenv_vars = load_dotenv_file(workspace_root / ".env")
    env.update(dotenv_vars)

    if extra_env:
        env.update(extra_env)

    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONUTF8"] = "1"
    env["UV_PROJECT_ENVIRONMENT"] = str(env_dir)
    return env


__all__ = [
    "build_child_environment",
    "load_dotenv_file",
    "load_workspace_env_passthrough",
    "parse_dotenv",
]
