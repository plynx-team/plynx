"""Operation registry protocol and in-memory ``FakeRegistry``."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Protocol, runtime_checkable

from plynx.api_models import InputPortSpec, OpEntry, OutputPortSpec
from plynx.registry.extractor import extract_ops_from_file, extract_ops_from_source
from plynx.registry.pack_registry import (
    PackRegistry,
    Registry,
    discover_packs,
    find_workspace_root,
)


@runtime_checkable
class OpRegistry(Protocol):
    """Protocol for looking up operation definitions."""

    def get(self, op_id: str) -> OpEntry | None:
        """Return the ``OpEntry`` for ``op_id`` (``<pack>/<module>:<Name>``), or ``None``."""
        ...

    def list_ops(self) -> list[OpEntry]:
        """Return all registered ``OpEntry`` items in deterministic order."""
        ...


def default_fake_ops() -> list[OpEntry]:
    """Return the built-in ``standard_io`` fake op entries used in Phase 0."""
    return [
        OpEntry(
            id="standard_io/demo:AskFooOrWoo",
            pack="standard_io",
            module="demo",
            name="AskFooOrWoo",
            kind="class",
            title="Ask foo or woo",
            category="Core / Interactive",
            cacheable=False,
            description="Ask the user to pick foo or woo.",
            inputs=[
                InputPortSpec(
                    name="prompt",
                    type="str",
                    required=False,
                    default="foo or woo?",
                ),
            ],
            outputs=[
                OutputPortSpec(name="choice", type="str"),
            ],
            source="builtin_packs/standard_io/src/standard_io/demo.py",
        ),
        OpEntry(
            id="standard_io/demo:SecretCodeChallenge",
            pack="standard_io",
            module="demo",
            name="SecretCodeChallenge",
            kind="class",
            title="Secret Code Challenge",
            category="Core / Interactive",
            cacheable=False,
            description="Challenge the user to enter the secret clearance code with interactive checkpoints.",
            inputs=[
                InputPortSpec(
                    name="prompt",
                    type="str",
                    required=False,
                    default="Select the secret clearance code to proceed:",
                ),
            ],
            outputs=[
                OutputPortSpec(name="code", type="str"),
                OutputPortSpec(name="message", type="str"),
            ],
            source="builtin_packs/standard_io/src/standard_io/demo.py",
        ),
        OpEntry(
            id="standard_io/demo:Echo",
            pack="standard_io",
            module="demo",
            name="Echo",
            kind="class",
            title="Echo text",
            category="Core / Text & Data",
            cacheable=True,
            description="Echo an input string to its output.",
            inputs=[
                InputPortSpec(name="text", type="str", required=True),
            ],
            outputs=[
                OutputPortSpec(name="text", type="str"),
            ],
            source="builtin_packs/standard_io/src/standard_io/demo.py",
        ),
        OpEntry(
            id="standard_io/text:Concat",
            pack="standard_io",
            module="text",
            name="Concat",
            kind="class",
            title="Concat text",
            category="Core / Text & Data",
            cacheable=True,
            description="Join two strings.",
            inputs=[
                InputPortSpec(name="a", type="str", required=True),
                InputPortSpec(name="b", type="str", required=False, default=" "),
            ],
            outputs=[
                OutputPortSpec(name="text", type="str"),
            ],
            source="builtin_packs/standard_io/src/standard_io/text.py",
        ),
        OpEntry(
            id="standard_io/demo:ReadText",
            pack="standard_io",
            module="demo",
            name="ReadText",
            kind="class",
            title="Read text file",
            category="Core / Files",
            cacheable=True,
            description="Read UTF-8 text from a file.",
            inputs=[
                InputPortSpec(name="path", type="file", required=True),
            ],
            outputs=[
                OutputPortSpec(name="text", type="str"),
            ],
            source="builtin_packs/standard_io/src/standard_io/demo.py",
        ),
        OpEntry(
            id="standard_io/demo:WriteText",
            pack="standard_io",
            module="demo",
            name="WriteText",
            kind="class",
            title="Write text file",
            category="Core / Files",
            cacheable=True,
            description="Write UTF-8 text to a file.",
            inputs=[
                InputPortSpec(name="text", type="str", required=True),
                InputPortSpec(
                    name="filename",
                    type="str",
                    required=False,
                    default="out.txt",
                ),
            ],
            outputs=[
                OutputPortSpec(name="file", type="file", media="text/plain"),
            ],
            source="builtin_packs/standard_io/src/standard_io/demo.py",
        ),
    ]


class FakeRegistry:
    """In-memory ``OpRegistry`` implementation used in Phase 0 and unit tests."""

    def __init__(
        self,
        ops: Iterable[OpEntry] | None = None,
        *,
        discovered_packs: dict[str, Path] | None = None,
    ) -> None:
        initial = default_fake_ops() if ops is None else list(ops)
        self._ops: dict[str, OpEntry] = {entry.id: entry for entry in initial}
        self.discovered_packs: dict[str, Path] = dict(discovered_packs or {})

    def register(self, entry: OpEntry) -> None:
        """Add or replace an ``OpEntry`` in this registry."""
        self._ops[entry.id] = entry

    def get(self, op_id: str) -> OpEntry | None:
        """Return the ``OpEntry`` for ``op_id``, or ``None`` if not registered."""
        return self._ops.get(op_id)

    def list_ops(self) -> list[OpEntry]:
        """Return all registered ``OpEntry`` items sorted by ``id``."""
        return [self._ops[key] for key in sorted(self._ops.keys())]


__all__ = [
    "FakeRegistry",
    "OpRegistry",
    "PackRegistry",
    "Registry",
    "default_fake_ops",
    "discover_packs",
    "extract_ops_from_file",
    "extract_ops_from_source",
    "find_workspace_root",
]
