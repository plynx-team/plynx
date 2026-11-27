"""Validate YAML and Python code blocks across README, AGENT_GUIDE, and user guides."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest
from click.testing import CliRunner
from plynx.cli import main as cli_main
from plynx.registry import PackRegistry
from plynx.registry.extractor import extract_ops_from_source
from plynx.workflow.models import Workflow
from plynx.workflow.validator import validate_workflow
from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parent.parent

DOC_FILES: list[Path] = [
    ROOT / "README.md",
    ROOT / "docs" / "AGENT_GUIDE.md",
    ROOT / "docs" / "guides" / "create_workflow.md",
    ROOT / "docs" / "guides" / "author_pack.md",
    ROOT / "docs" / "guides" / "agentic_workflows.md",
    ROOT / "docs" / "guides" / "debug_failed_node.md",
]

VALID_PLYNX_YAML_KEYS = frozenset(
    {
        "workflows",
        "packs",
        "db",
        "concurrency",
        "env_passthrough",
        "cache",
        "agent",
        "max_injected_nodes",
    }
)

_FENCE_RE = re.compile(r"^```([a-zA-Z0-9_-]*)\n(.*?)^```", re.MULTILINE | re.DOTALL)


def _extract_code_blocks(path: Path) -> list[tuple[str, str]]:
    """Return ``(lang, content)`` pairs for all fenced code blocks in ``path``."""
    text = path.read_text(encoding="utf-8")
    return [(m.group(1).strip().lower(), m.group(2)) for m in _FENCE_RE.finditer(text)]


@pytest.mark.parametrize("doc_path", DOC_FILES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_doc_yaml_and_python_snippets_are_valid(doc_path: Path) -> None:
    """Every YAML workflow, plynx.yaml, and Python op block in docs parses and validates cleanly."""
    assert doc_path.is_file(), f"Expected doc file missing: {doc_path}"
    registry = PackRegistry(ROOT)
    yaml_loader = YAML(typ="safe")

    blocks = _extract_code_blocks(doc_path)
    yaml_blocks = [code for lang, code in blocks if lang in ("yaml", "yml")]
    py_blocks = [code for lang, code in blocks if lang in ("python", "py")]

    for idx, code in enumerate(yaml_blocks):
        parsed = yaml_loader.load(code)
        assert isinstance(parsed, dict), (
            f"{doc_path.name} yaml block #{idx} did not parse to a dict"
        )
        if "version" in parsed and "nodes" in parsed:
            wf = Workflow.model_validate(parsed)
            issues = validate_workflow(wf, registry=registry)
            errors = [issue for issue in issues if issue.severity == "error"]
            assert not errors, (
                f"{doc_path.name} workflow snippet #{idx} failed validation: "
                + "; ".join(e.message for e in errors)
            )
        else:
            unknown = set(parsed.keys()) - VALID_PLYNX_YAML_KEYS
            assert not unknown, f"{doc_path.name} config snippet #{idx} has unknown keys: {unknown}"

    for idx, code in enumerate(py_blocks):
        ast.parse(code, filename=f"{doc_path.name}#py-{idx}")
        ops = extract_ops_from_source(
            code,
            pack="doc_pack",
            module=f"snippet_{idx}",
            source_path=f"{doc_path.name}#py-{idx}",
        )
        assert ops, f"{doc_path.name} python snippet #{idx} yielded no PLynx ops"
        for entry in ops:
            assert entry.valid, (
                f"{doc_path.name} python snippet #{idx} op {entry.id!r} invalid: {entry.error}"
            )
            assert entry.error is None


def test_agent_guide_cli_and_blank_repo_workflow_loop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In a blank directory, an agent can init, read agent-guide, inspect ops, validate, and run."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    # 1. Print agent guide from CLI
    guide_res = runner.invoke(cli_main, ["agent-guide"])
    assert guide_res.exit_code == 0, guide_res.output
    expected_guide = (ROOT / "docs" / "AGENT_GUIDE.md").read_text(encoding="utf-8")
    assert guide_res.output == expected_guide
    assert "Workflow Design & Granularity Heuristics" in guide_res.output
    assert "Reuse Before Authoring" in guide_res.output
    assert "Goldilocks Granularity" in guide_res.output
    assert "Cache-Boundary Splitting" in guide_res.output

    # 2. Initialize blank workspace
    init_res = runner.invoke(cli_main, ["init"])
    assert init_res.exit_code == 0, init_res.output
    assert (tmp_path / ".plynx").is_dir()
    assert (tmp_path / "workflows").is_dir()
    assert (tmp_path / "custom_packs").is_dir()
    assert (tmp_path / "plynx.yaml").is_file()
    skill_path = tmp_path / ".agents" / "skills" / "plynx-create-workflow" / "SKILL.md"
    assert skill_path.is_file()
    skill_text = skill_path.read_text(encoding="utf-8")
    assert "name: plynx-create-workflow" in skill_text
    assert "plynx agent-guide" in skill_text
    assert "plynx ops --json" in skill_text

    # 3. Inspect ops --json
    ops_res = runner.invoke(cli_main, ["ops", "--json"])
    assert ops_res.exit_code == 0, ops_res.output
    ops_list = json.loads(ops_res.output)
    op_ids = {op["id"] for op in ops_list}
    assert "standard_io/interactive:AskChoice" in op_ids
    assert "standard_io/demo:Echo" in op_ids
    assert "standard_io/agent:AgentPrompt" in op_ids
    assert "standard_io/agent:StageSupervisor" in op_ids

    # 4. Extract starter workflow from README.md, write to workflows/hello.yaml, validate & run
    readme_yaml_blocks = [
        code for lang, code in _extract_code_blocks(ROOT / "README.md") if lang in ("yaml", "yml")
    ]
    assert readme_yaml_blocks, "README.md must contain a starter workflow YAML block"
    wf_file = tmp_path / "workflows" / "hello.yaml"
    wf_file.write_text(readme_yaml_blocks[0], encoding="utf-8")

    val_res = runner.invoke(cli_main, ["validate", str(wf_file)])
    assert val_res.exit_code == 0, val_res.output

    run_res = runner.invoke(
        cli_main,
        ["run", "--non-interactive", "--answer", "pick.cp_0=Hello", str(wf_file)],
    )
    assert run_res.exit_code == 0, run_res.output

    runs_res = runner.invoke(cli_main, ["runs"])
    assert runs_res.exit_code == 0, runs_res.output
    assert "SUCCESS" in runs_res.output
