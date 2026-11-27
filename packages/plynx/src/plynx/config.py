"""Workspace configuration loader for ``plynx.yaml`` (PROTOCOL.md section 12)."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from plynx_sdk.protocol import AgentProvider
from ruamel.yaml import YAML

DEFAULT_AGENT_CONCURRENCY = 2
DEFAULT_MAX_INJECTED_NODES = 3

_SIZE_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z]*)\s*$")

_SIZE_UNITS: dict[str, int] = {
    "": 1,
    "b": 1,
    "byte": 1,
    "bytes": 1,
    "k": 1024,
    "kb": 1024,
    "kib": 1024,
    "m": 1024**2,
    "mb": 1024**2,
    "mib": 1024**2,
    "g": 1024**3,
    "gb": 1024**3,
    "gib": 1024**3,
    "t": 1024**4,
    "tb": 1024**4,
    "tib": 1024**4,
}


def parse_size_bytes(val: str | int | float) -> int:
    """Parse a size representation into integer bytes.

    Supports integer bytes or strings with unit suffixes (e.g. '10GB', '500MB', '100KB').
    """
    if isinstance(val, (int, float)):
        if val < 0:
            raise ValueError(f"Size must be non-negative, got {val}")
        return int(val)

    match = _SIZE_RE.match(val)
    if not match:
        raise ValueError(f"Invalid size string: {val!r}")

    number_str, unit_str = match.groups()
    unit = unit_str.lower()
    if unit not in _SIZE_UNITS:
        raise ValueError(f"Unknown size unit {unit_str!r} in {val!r}")

    bytes_per_unit = _SIZE_UNITS[unit]
    number = float(number_str)
    return int(number * bytes_per_unit)


@dataclass(frozen=True)
class WorkspaceConfig:
    """Parsed workspace settings from ``plynx.yaml``."""

    workspace_root: Path
    workflows: list[str] = field(default_factory=lambda: ["workflows"])
    packs: list[Path] = field(default_factory=list)
    db: str = ".plynx/plynx.db"
    concurrency: int | None = None
    env_passthrough: list[str] | None = None
    cache_max_size: int | None = None
    agent_provider: AgentProvider = AgentProvider.DEFAULT
    agent_model: str = ""
    agent_concurrency: int = DEFAULT_AGENT_CONCURRENCY
    max_injected_nodes: int = DEFAULT_MAX_INJECTED_NODES
    agent_models: list[str] = field(default_factory=list)
    agent_custom_command: str = ""


def _parse_positive_int(raw: object) -> int | None:
    if isinstance(raw, int) and not isinstance(raw, bool) and raw > 0:
        return int(raw)
    return None


def _parse_non_negative_int(raw: object) -> int | None:
    if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0:
        return int(raw)
    return None


def load_workspace_config(workspace_root: Path) -> WorkspaceConfig:
    """Load configuration from ``<workspace_root>/plynx.yaml`` if present."""
    root = workspace_root.resolve()
    cfg_path = root / "plynx.yaml"
    if not cfg_path.is_file():
        return WorkspaceConfig(workspace_root=root)

    yaml = YAML(typ="safe")
    try:
        parsed = yaml.load(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return WorkspaceConfig(workspace_root=root)

    if not isinstance(parsed, Mapping):
        return WorkspaceConfig(workspace_root=root)

    # 1. workflows
    workflows: list[str] = ["workflows"]
    raw_workflows = parsed.get("workflows")
    if isinstance(raw_workflows, str):
        workflows = [raw_workflows]
    elif isinstance(raw_workflows, list):
        workflows = [str(x) for x in raw_workflows if isinstance(x, (str, int))]

    # 2. packs
    packs: list[Path] = []
    raw_packs = parsed.get("packs")
    if isinstance(raw_packs, list):
        for item in raw_packs:
            if isinstance(item, str):
                p = Path(item)
                resolved = p.resolve() if p.is_absolute() else (root / p).resolve()
                if resolved not in packs:
                    packs.append(resolved)

    # 3. db
    raw_db = parsed.get("db")
    db_path = str(raw_db) if isinstance(raw_db, str) else ".plynx/plynx.db"

    # 4. concurrency
    concurrency = _parse_positive_int(parsed.get("concurrency"))

    # 5. env_passthrough
    raw_passthrough = parsed.get("env_passthrough")
    env_passthrough: list[str] | None = None
    if isinstance(raw_passthrough, list):
        env_passthrough = [str(item) for item in raw_passthrough if isinstance(item, str)]

    # 6. cache max_size
    cache_max_size: int | None = None
    raw_cache = parsed.get("cache")
    if isinstance(raw_cache, Mapping):
        max_size_val = raw_cache.get("max_size")
        if max_size_val is not None:
            try:
                cache_max_size = parse_size_bytes(max_size_val)
            except ValueError:
                cache_max_size = None
    elif isinstance(raw_cache, (str, int)):
        try:
            cache_max_size = parse_size_bytes(raw_cache)
        except ValueError:
            cache_max_size = None

    # 7. agent settings
    agent_provider = AgentProvider.DEFAULT
    agent_model = ""
    agent_concurrency = (
        _parse_positive_int(parsed.get("agent_concurrency")) or DEFAULT_AGENT_CONCURRENCY
    )
    top_max_injected = _parse_non_negative_int(parsed.get("max_injected_nodes"))
    max_injected_nodes = (
        top_max_injected if top_max_injected is not None else DEFAULT_MAX_INJECTED_NODES
    )
    agent_models: list[str] = []
    agent_custom_command = ""

    raw_agent = parsed.get("agent")
    if isinstance(raw_agent, Mapping):
        raw_prov = raw_agent.get("provider")
        if isinstance(raw_prov, str) and raw_prov.strip():
            try:
                agent_provider = AgentProvider(raw_prov.strip())
            except ValueError:
                agent_provider = AgentProvider.DEFAULT
        raw_model = raw_agent.get("model")
        if isinstance(raw_model, str):
            agent_model = raw_model.strip()
        nested_conc = _parse_positive_int(
            raw_agent.get("agent_concurrency", raw_agent.get("concurrency"))
        )
        if nested_conc is not None:
            agent_concurrency = nested_conc
        nested_max_inj = _parse_non_negative_int(raw_agent.get("max_injected_nodes"))
        if nested_max_inj is not None:
            max_injected_nodes = nested_max_inj
        raw_models = raw_agent.get("models")
        if isinstance(raw_models, list):
            for m_item in raw_models:
                if (
                    isinstance(m_item, str)
                    and m_item.strip()
                    and m_item.strip() not in agent_models
                ):
                    agent_models.append(m_item.strip())
        raw_custom = raw_agent.get("custom_command")
        if isinstance(raw_custom, str):
            agent_custom_command = raw_custom.strip()

    return WorkspaceConfig(
        workspace_root=root,
        workflows=workflows,
        packs=packs,
        db=db_path,
        concurrency=concurrency,
        env_passthrough=env_passthrough,
        cache_max_size=cache_max_size,
        agent_provider=agent_provider,
        agent_model=agent_model,
        agent_concurrency=agent_concurrency,
        max_injected_nodes=max_injected_nodes,
        agent_models=agent_models,
        agent_custom_command=agent_custom_command,
    )


def resolve_effective_agent_config(
    *,
    workspace_config: WorkspaceConfig,
    workflow_provider: str | AgentProvider | None = None,
    workflow_model: str | None = None,
    cli_provider: str | AgentProvider | None = None,
    cli_model: str | None = None,
    node_provider: object = None,
    node_model: object = None,
    set_provider: object = None,
    set_model: object = None,
    env: Mapping[str, str] | None = None,
) -> tuple[str, str]:
    """Resolve effective ``(provider, model)`` across the 4-level hierarchy.

    Precedence (lowest to highest):
    1. ``plynx.yaml`` ``agent.{provider,model}`` (or ``PLYNX_AGENT_PROVIDER`` / ``PLYNX_AGENT_MODEL``).
    2. ``workflow.yaml`` ``agent.{provider,model}``.
    3. CLI ``--agent-provider`` / ``--agent-model``.
    4. Node input port ``provider`` (when non-default) / ``model`` (when non-empty),
       with CLI ``--set <node>.provider`` / ``--set <node>.model`` winning at the port level.
    """
    source_env = os.environ if env is None else env

    # --- Provider ---
    provider = workspace_config.agent_provider.value
    env_prov = source_env.get("PLYNX_AGENT_PROVIDER", "").strip()
    if env_prov and env_prov != AgentProvider.DEFAULT.value:
        provider = env_prov

    if workflow_provider is not None:
        wf_prov = (
            workflow_provider.value
            if isinstance(workflow_provider, AgentProvider)
            else str(workflow_provider).strip()
        )
        if wf_prov and wf_prov != AgentProvider.DEFAULT.value:
            provider = wf_prov

    if cli_provider is not None:
        c_prov = (
            cli_provider.value
            if isinstance(cli_provider, AgentProvider)
            else str(cli_provider).strip()
        )
        if c_prov and c_prov != AgentProvider.DEFAULT.value:
            provider = c_prov

    effective_node_provider = set_provider if set_provider is not None else node_provider
    if isinstance(effective_node_provider, str):
        n_prov = effective_node_provider.strip()
        if n_prov and n_prov != AgentProvider.DEFAULT.value:
            provider = n_prov

    # --- Model ---
    model = workspace_config.agent_model
    env_model = source_env.get("PLYNX_AGENT_MODEL", "").strip()
    if env_model:
        model = env_model

    if workflow_model is not None and workflow_model.strip():
        model = workflow_model.strip()

    if cli_model is not None and cli_model.strip():
        model = cli_model.strip()

    effective_node_model = set_model if set_model is not None else node_model
    if isinstance(effective_node_model, str) and effective_node_model.strip():
        model = effective_node_model.strip()

    return provider, model


def resolve_max_injected_nodes(
    *,
    workspace_config: WorkspaceConfig,
    workflow_max: int | None = None,
    cli_max: int | None = None,
) -> int:
    """Resolve effective ``max_injected_nodes`` budget (CLI > workflow > plynx.yaml > 3)."""
    if cli_max is not None:
        return max(cli_max, 0)
    if workflow_max is not None:
        return max(workflow_max, 0)
    return max(workspace_config.max_injected_nodes, 0)


__all__ = [
    "DEFAULT_AGENT_CONCURRENCY",
    "DEFAULT_MAX_INJECTED_NODES",
    "WorkspaceConfig",
    "load_workspace_config",
    "parse_size_bytes",
    "resolve_effective_agent_config",
    "resolve_max_injected_nodes",
]
