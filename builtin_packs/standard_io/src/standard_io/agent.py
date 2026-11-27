"""Coding-agent operations in the built-in ``standard_io`` pack."""

from __future__ import annotations

from typing import TypedDict

from plynx_sdk import AgentOp, MarkdownFile, SideEffect, StageValidatorOp


class AgentPrompt(AgentOp):
    """Run a coding agent with a prompt or prompt file and return a Markdown response."""

    TITLE = "Agent Prompt"
    CATEGORY = "Core / Agents"
    CACHEABLE = True
    SIDE_EFFECTS = SideEffect.READ

    class Outputs(TypedDict):
        response: MarkdownFile


class StageSupervisor(StageValidatorOp):
    """Inspect stage outputs, warnings, and logs, and optionally propose a bounded graph patch."""

    TITLE = "Stage Supervisor"
    CATEGORY = "Core / Agents"
    CACHEABLE = True
    SIDE_EFFECTS = SideEffect.READ


__all__ = [
    "AgentPrompt",
    "StageSupervisor",
]
