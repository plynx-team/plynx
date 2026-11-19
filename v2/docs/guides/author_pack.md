# Guide: Author a Node Pack

A **Node Pack** is an isolated Python package containing one or more operation definitions (`Op`). Packs execute inside isolated virtual environments managed by `uv`.

---

## 1. Directory Structure

Custom packs live under `custom_packs/<pack_name>` (or in custom directories declared in `plynx.yaml`):

```text
my_workspace/
├── custom_packs/
│   └── my_pack/
│       ├── pyproject.toml
│       ├── uv.lock
│       └── src/
│           └── my_pack/
│               ├── __init__.py
│               └── text_ops.py
```

---

## 2. Pack Configuration (`pyproject.toml`)

The pack must depend on `plynx-sdk` and declare its own third-party dependencies:

```toml
[project]
name = "my-pack"
version = "0.1.0"
description = "Custom operations for my team"
requires-python = ">=3.11"
dependencies = [
    "plynx-sdk",
    "polars>=1.0.0",
]

[build-system]
requires = ["uv_build>=0.9.0,<0.10"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "my_pack"
```

> [!IMPORTANT]
> Always generate and commit `uv.lock` inside your pack directory so runs are fully reproducible:
> ```bash
> cd custom_packs/my_pack && uv lock
> ```

---

## 3. Defining Operations

You can author ops using either functional `@op` or class-based `Op`.

### Approach A: Functional `@op` (Recommended for lightweight ops)

```python
"""Module containing text operations."""

from typing import TypedDict
from plynx_sdk import op


class ConcatOutputs(TypedDict):
    result: str


@op(title="Concat Strings", category="Text", cacheable=True)
def concat(prefix: str, suffix: str = "!") -> ConcatOutputs:
    """Concatenate two strings together."""
    return {"result": f"{prefix}{suffix}"}
```

### Approach B: Class-based `Op` (Recommended for files, complex state, or checkpoints)

```python
"""Module containing file processing operations."""

from pathlib import Path
from typing import TypedDict
from plynx_sdk import Op, checkpoint


class FileCountOutputs(TypedDict):
    count: int
    summary_file: Path


class CountLines(Op):
    """Count lines in an input file and optionally ask the user to proceed."""

    TITLE = "Count Lines"
    CATEGORY = "File Processing"
    CACHEABLE = True

    input_file: Path
    prefix: str = "Total lines: "

    def run(self) -> FileCountOutputs:
        # 1. Read read-only input file
        lines = self.input_file.read_text(encoding="utf-8").splitlines()
        count = len(lines)

        # 2. Checkpoint: human-in-the-loop confirmation
        if count > 1000:
            proceed = checkpoint(
                f"File contains {count} lines. Proceed?",
                options=["yes", "no"],
            )
            if proceed == "no":
                raise ValueError("Operation stopped by user choice.")

        # 3. Write outputs only inside workdir (current working directory)
        out_path = Path("summary.txt")
        out_path.write_text(f"{self.prefix}{count}\n", encoding="utf-8")

        # 4. Return relative paths for file outputs
        return {
            "count": count,
            "summary_file": out_path,
        }
```

---

## 4. Port Types and Media Types

| Type | Python Annotation | Description |
| :--- | :--- | :--- |
| **Scalar** | `str`, `int`, `float`, `bool` | Inlined in inputs manifest; editable via UI widgets. |
| **File** | `Path` | Backed by CAS blob store; previewed via UI previewers. |
| **Directory** | `Path` (annotated as directory) | Directory artifact tree. |
| **Collection** | `dict[str, Any]`, `list[Any]` | JSON-serializable structured payloads (< 1 MiB). |

---

## 5. Discovering and Verifying Ops

From your workspace root, verify that PLynx discovers your pack:

```bash
plynx ops
```

You should see your ops listed as `<pack_name>/<module>:<OpName>`.
Validate your workflow with:

```bash
plynx validate workflows/my_workflow.yaml
```
