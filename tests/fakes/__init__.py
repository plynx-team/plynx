"""Test fakes for executor and registry."""

from tests.fakes.fake_executor import (
    FakeExecutionRecord,
    FakeExecutor,
    FakeNodeScript,
    scalar_outputs,
)
from tests.fakes.fake_registry import (
    FakeRegistry,
    default_fake_ops,
)

__all__ = [
    "FakeExecutionRecord",
    "FakeExecutor",
    "FakeNodeScript",
    "FakeRegistry",
    "default_fake_ops",
    "scalar_outputs",
]
