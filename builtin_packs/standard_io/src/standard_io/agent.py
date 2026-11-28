"""Coding-agent operations in the built-in ``standard_io`` pack."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict

from plynx_sdk import (
    AgentOp,
    AgentProviderLiteral,
    JsonFile,
    MarkdownFile,
    SideEffect,
    StageValidatorOp,
)


class _AgentJsonTurnOutputs(TypedDict):
    """Internal LLM turn schema for ``AgentJson`` (materializes ``file`` deterministically)."""

    data: dict[str, Any]


class AgentPrompt(AgentOp):
    """Run a coding agent with a prompt or prompt file and return a Markdown response."""

    TITLE = "Agent Prompt"
    CATEGORY = "Core / Agents"
    CACHEABLE = True
    SIDE_EFFECTS = SideEffect.READ

    class Outputs(TypedDict):
        response: MarkdownFile


class AgentText(AgentOp):
    """Run a coding agent with a prompt or prompt file and return a plain string output."""

    TITLE = "Agent Text"
    CATEGORY = "Core / Agents"
    CACHEABLE = True
    SIDE_EFFECTS = SideEffect.READ

    class Outputs(TypedDict):
        text: str


class AgentJson(AgentOp):
    """Run a coding agent and return a structured JSON object plus a saved JSON file."""

    TITLE = "Agent JSON"
    CATEGORY = "Core / Agents"
    CACHEABLE = True
    SIDE_EFFECTS = SideEffect.READ

    class Outputs(TypedDict):
        data: dict[str, Any]
        file: JsonFile

    def run(
        self,
        prompt_file: MarkdownFile | None = None,
        prompt: str = "",
        provider: AgentProviderLiteral = "default",
        model: str = "",
        **extra: Any,
    ) -> Outputs:
        turn_out = self.run_agent(
            prompt_file=prompt_file,
            prompt=prompt,
            provider=provider,
            model=model,
            output_schema=_AgentJsonTurnOutputs,
            **extra,
        )
        data = turn_out["data"]
        out_path = Path("data.json")
        out_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return {"data": data, "file": out_path}


class AgentBool(AgentOp):
    """Run a coding agent to make a boolean decision with an accompanying explanation."""

    TITLE = "Agent Bool"
    CATEGORY = "Core / Agents"
    CACHEABLE = True
    SIDE_EFFECTS = SideEffect.READ

    class Outputs(TypedDict):
        value: bool
        reason: str


class StageSupervisor(StageValidatorOp):
    """Inspect stage outputs, warnings, and logs, and optionally propose a bounded graph patch."""

    TITLE = "Stage Supervisor"
    CATEGORY = "Core / Agents"
    CACHEABLE = True
    SIDE_EFFECTS = SideEffect.READ


__all__ = [
    "AgentBool",
    "AgentJson",
    "AgentPrompt",
    "AgentText",
    "StageSupervisor",
]
