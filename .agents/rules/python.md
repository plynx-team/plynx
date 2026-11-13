---
trigger: always_on
description: Python coding style, architecture patterns, and required checks for Plynx.
---

# Python Rules

## Style & Idioms

- **Pythonic Code (Python 3.10+)**: Write clean, idiomatic Python. Prefer dataclasses, comprehensions, context managers, and explicit type hints. Avoid bare `except` blocks.
- **Line Length**: Max **160** characters (`setup.cfg`, `.isort.cfg`, `pylintrc`).
- **Quotes & Strings**: Use double quotes (`"`) and f-strings (`f"..."`), including in `logging` calls.
- **Naming (`pylintrc`)**:
  - `snake_case`: functions, methods, variables, modules.
  - `PascalCase`: classes.
  - `UPPER_CASE`: constants.
  - Forbidden names: `foo`, `bar`, `baz`, `toto`, `tutu`, `tata`.
- **Docstrings**: Required for all modules, classes, and public functions/methods (anything not starting with `_`). Preserve existing relevant comments.
- **Imports**: Sort with `isort` (`src_paths=plynx`, `line_length=160`). Never use wildcard imports.

## Architecture Patterns

- **Database Models**: Inherit from [`DBObject`](plynx/db/db_object.py) and decorate with `@dataclass_json` and `@dataclass`. Use `to_dict()` and `from_dict()` for serialization.
- **Plugins**: Inherit from [`BaseExecutor`](plynx/base/executor.py), [`BaseResource`](plynx/base/resource.py), or [`BaseHub`](plynx/base/hub.py) and register in [`template_config.yaml`](template_config.yaml).
- **Constants**: Place shared enums and string constants in [`plynx/constants/`](plynx/constants/), not inline magic strings.
- **Storage**: Use [`plynx.utils.file_handler`](plynx/utils/file_handler.py) instead of raw `open()` when reading/writing stored resources so local, S3, and GCS backends work transparently.
- **Dependencies**: Runtime dependencies live in [`requirements.txt`](requirements.txt) and [`setup.py`](setup.py); dev tools live in [`requirements-dev.txt`](requirements-dev.txt).

## Required Checks

All changes must pass these checks (Pylint requires a 10.0 score):

```bash
uv run flake8 plynx tests
uv run isort plynx tests
uv run mypy plynx --ignore-missing-imports
uv run pylint --disable=F0401 plynx
make pytest
```
