# Guide: Authoring a Node Pack

A **Node Pack** is a Python package defining one or more PLynx operations (`Op` subclasses or `@op` functions). Custom packs run in isolated `uv` virtual environments so heavy or conflicting dependencies stay out of the core engine.

## 1. Directory Layout & Discovery

Place custom packs under `custom_packs/<pack_name>/` in your workspace (or configure additional pack directories in `plynx.yaml`):

```text
my_workspace/
├── plynx.yaml
├── custom_packs/
│   └── my_pack/
│       ├── pyproject.toml
│       ├── uv.lock
│       └── src/
│           └── my_pack/
│               ├── __init__.py
│               └── text_ops.py
```

Optional `plynx.yaml` configuration:

```yaml
workflows: workflows
packs:
  - custom_packs
  - external_packs
env_passthrough:
  - OPENAI_API_KEY
```

### `pyproject.toml`

A pack depends on `plynx-sdk` and its own libraries. Never depend on `plynx`.

```toml
[project]
name = "my-pack"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "plynx-sdk>=2.0.0,<3.0.0",
    "polars>=1.0.0",
]

[build-system]
requires = ["hatchling>=1.25"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/my_pack"]
```

Generate and commit `uv.lock` inside each custom pack for reproducible environments and cache keys:

```bash
cd custom_packs/my_pack && uv lock
```

## 2. Defining Operations

PLynx discovers operations via static AST parsing (pack code is never imported at discovery time). Metadata (`TITLE`, `CATEGORY`, `CACHEABLE`, `ALLOW_EXTRA_INPUTS`, and `@op(...)` arguments) and port defaults must be plain literals.

### Function Form (`@op`)

Use `@op` for concise, stateless operations. Declare multiple outputs with a module-level `TypedDict`, or return a single typed value (which becomes output `result`):

```python
"""Text helper operations."""

from typing import TypedDict

from plynx_sdk import op


class ConcatOutputs(TypedDict):
    result: str


@op(title="Concat Strings", category="Text", cacheable=True)
def concat(prefix: str, suffix: str = "!") -> ConcatOutputs:
    """Concatenate two strings."""
    return {"result": f"{prefix}{suffix}"}
```

### Class Form (`Op`)

Use `Op` when grouping outputs as a nested `Outputs(TypedDict)` or calling `self.checkpoint(...)`. Input ports are parameters of `run(self, ...)`, **not** class attributes:

```python
"""File processing operations."""

from pathlib import Path
from typing import TypedDict

from plynx_sdk import Op, TextFile


class CountLines(Op):
    """Count lines in a text file and write a summary."""

    TITLE = "Count Lines"
    CATEGORY = "Files"
    CACHEABLE = True

    class Outputs(TypedDict):
        count: int
        summary_file: TextFile

    def run(self, input_file: Path, prefix: str = "Total lines: ") -> Outputs:
        """Count lines and optionally confirm before writing summary.

        Args:
            input_file: Source text file to inspect.
            prefix: Prefix text written before the line count.
        """
        lines = input_file.read_text(encoding="utf-8").splitlines()
        count = len(lines)

        if count > 1000:
            proceed = self.checkpoint(
                f"File contains {count} lines. Proceed?",
                options=["yes", "no"],
            )
            if proceed == "no":
                raise ValueError("Operation stopped by user choice.")

        out_path = Path("summary.txt")
        out_path.write_text(f"{prefix}{count}\n", encoding="utf-8")
        return {"count": count, "summary_file": out_path}
```

## 3. Port Types & Annotations

| Port Type | Python Annotation | Notes |
| :--- | :--- | :--- |
| Scalars | `str`, `int`, `float`, `bool` | Inlined in `inputs.json`; editable in UI. |
| Choices | `Literal["fast", "accurate"]` | String or int literals; renders as a dropdown (`options`). |
| Bounded numbers | `Annotated[int, Range(0, 100, step=5)]` | `Range(min, max, step=...)` from `plynx_sdk` for `int` or `float`. |
| JSON collections | `dict`, `list` | Serialized as JSON (< 1 MiB). Use a file for larger payloads. |
| Generic file | `Path` | Stored in CAS; materialized read-only under `inputs/<port>/`. |
| Typed media file | `Annotated[Path, Media("image/png")]` | Enforces MIME compatibility and selects UI previewer. |
| Built-in media aliases | `PdfFile`, `AudioWav`, `MidiFile`, `MarkdownFile`, `JsonFile`, `ImageFile`, `CsvFile`, `TextFile` | Imported from `plynx_sdk` (or `plynx_sdk.types`). |
| Directory tree | `Directory` | Imported from `plynx_sdk`. Materialized read-only; hashed via `tree_sha256`. |
| Optional | `X \| None` or `Optional[X]` | Marks the port optional. |

### Variadic Inputs (`ALLOW_EXTRA_INPUTS`)

To accept arbitrary named inputs of a uniform type (for example, mixing an arbitrary number of audio tracks), enable `ALLOW_EXTRA_INPUTS = True` (or `@op(..., allow_extra_inputs=True)`) and declare a typed `**kwargs` parameter:

```python
"""Variadic directory bundling example."""

from pathlib import Path
from typing import Annotated, Literal, TypedDict

from plynx_sdk import Directory, Media, Op, Range

CustomText = Annotated[Path, Media("text/plain")]


class JoinFiles(Op):
    """Join an arbitrary number of named text files."""

    TITLE = "Join Files"
    CATEGORY = "Files"
    CACHEABLE = True
    ALLOW_EXTRA_INPUTS = True

    class Outputs(TypedDict):
        out_dir: Directory
        combined: CustomText

    def run(
        self,
        mode: Literal["concat", "numbered"] = "concat",
        max_lines: Annotated[int, Range(1, 10000, step=1)] = 1000,
        **files: CustomText,
    ) -> Outputs:
        """Merge all extra file inputs into one output file and directory."""
        out_dir = Path("bundle")
        out_dir.mkdir(parents=True, exist_ok=True)
        parts: list[str] = []
        for name, file_path in sorted(files.items()):
            lines = file_path.read_text(encoding="utf-8").splitlines()[:max_lines]
            if mode == "numbered":
                lines = [f"{i + 1}: {line}" for i, line in enumerate(lines)]
            chunk = "\n".join(lines)
            (out_dir / f"{name}.txt").write_text(chunk, encoding="utf-8")
            parts.append(chunk)
        combined = Path("combined.txt")
        combined.write_text("\n".join(parts), encoding="utf-8")
        return {"out_dir": out_dir, "combined": combined}
```

## 4. Authoring Rules & Invariants

The engine cannot enforce every rule below; breaking them can produce stale cache hits or broken runs.

1. **Never modify input files or directories.** Inputs are read-only CAS links. Copy into `workdir/` before editing.
2. **Write outputs only inside `workdir/` (the current working directory).** Return relative `Path` objects; never return absolute paths or `..`.
3. **Keep scalar/JSON outputs under 1 MiB.** Write larger data to a file.
4. **Stay cross-platform.** Use `pathlib.Path` instead of OS-specific shell commands (`rm`, `cp`, `grep`).
5. **Make `checkpoint()` calls replay-safe.** After a user answers a checkpoint, the engine replays the node from the start of `run()`. Keep work before `checkpoint()` cheap and side-effect-free, call checkpoints in a deterministic order, and never catch `BaseException` or use bare `except:` around `checkpoint()`.
6. **Know the cache key scope.** Cache keys hash: op entrypoint, op source **file bytes**, pack `uv.lock`, input file/directory hashes, scalar parameters, and checkpoint answers. They do **not** hash shared helper modules, environment variables, system time, or network state:
   - After editing a shared helper module, run once with `plynx run --no-cache`.
   - Set `CACHEABLE = False` (or `cacheable=False`) for non-deterministic ops.
7. **Handle secrets via environment variables.** Read secrets from `.env` or host env (configured with `env_passthrough` in `plynx.yaml`). Never write secrets to outputs, files, or logs.
8. **Let exceptions propagate.** Log to stdout/stderr with `print` or `logging`. Do not call `sys.exit(2)` or `sys.exit(10)` manually.
9. **Build context-free ops with 100% accurate descriptions.** Design every op to be reusable across future workflows: expose workflow-specific prompts, thresholds, or choices as input ports rather than hardcoding them in Python (outside `tests/`). Ensure `TITLE` and docstrings state concisely and accurately what the op actually does on arbitrary inputs.

## 5. Verifying Discovery

From your workspace root, inspect discovered ops and their exact schemas:

```bash
plynx ops
plynx ops --json
```

Ops appear as `<pack>/<module>:<Name>`. Any op that violates the static AST subset is reported with `"valid": false` and an `"error"` explanation. Validate workflows referencing your ops with:

```bash
plynx validate workflows/my_workflow.yaml
```
