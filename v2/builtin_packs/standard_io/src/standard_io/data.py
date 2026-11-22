"""Data and primitive operations in the built-in ``standard_io`` pack."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Literal, TypedDict

from plynx_sdk import CsvFile, JsonFile, MarkdownFile, Op


class TemplateFormat(Op):
    """Format a template string using scalar parameters and optional dictionary values.

    Args:
        template: Python format string containing replacement fields like '{a}', '{b}'.
        values: Optional dictionary mapping field names to values.
    """

    TITLE = "Template Format"
    CATEGORY = "Core / Text & Data"
    CACHEABLE = True
    ALLOW_EXTRA_INPUTS = True

    class Outputs(TypedDict):
        text: str

    def run(
        self,
        template: str,
        values: dict[str, Any] | None = None,
        **extra_values: Any,
    ) -> Outputs:
        kwargs: dict[str, Any] = {}
        if values is not None:
            kwargs.update(values)
        kwargs.update(extra_values)
        return {"text": template.format(**kwargs)}


class MathOp(Op):
    """Perform basic arithmetic operations on numeric operands.

    Args:
        a: First numeric operand.
        b: Second numeric operand.
        operation: Arithmetic operation: 'add', 'sub', 'mul', 'div', 'pow', or 'mod'.
    """

    TITLE = "Math Operation"
    CATEGORY = "Core / Text & Data"
    CACHEABLE = True

    class Outputs(TypedDict):
        result: float
        is_positive: bool
        rounded: int

    def run(
        self,
        a: float,
        b: float = 0.0,
        operation: Literal["add", "sub", "mul", "div", "pow", "mod"] = "add",
    ) -> Outputs:
        if operation == "add":
            res = a + b
        elif operation == "sub":
            res = a - b
        elif operation == "mul":
            res = a * b
        elif operation == "div":
            if b == 0.0:
                raise ZeroDivisionError("Cannot divide by zero in MathOp")
            res = a / b
        elif operation == "pow":
            res = math.pow(a, b)
        elif operation == "mod":
            if b == 0.0:
                raise ZeroDivisionError("Cannot modulo by zero in MathOp")
            res = a % b
        else:
            raise ValueError(f"Unsupported math operation: {operation!r}")

        return {
            "result": float(res),
            "is_positive": res > 0,
            "rounded": round(res),
        }


class JsonExtract(Op):
    """Extract a value or sub-tree from a JSON object or JSON file.

    Args:
        json_data: In-memory JSON dictionary.
        json_file: Path to a JSON file on disk.
        key: Dot-separated path to the key to extract (e.g. 'user.profile.name').
            Empty string targets root.
        default: Fallback string value if the specified key path is not found.
    """

    TITLE = "JSON Extract"
    CATEGORY = "Core / Text & Data"
    CACHEABLE = True

    class Outputs(TypedDict):
        value_str: str
        value_json: dict[str, Any]
        found: bool

    def run(
        self,
        json_data: dict[str, Any] | None = None,
        json_file: JsonFile | None = None,
        key: str = "",
        default: str = "",
    ) -> Outputs:
        data: Any = None
        if json_file is not None:
            content = Path(json_file).read_text(encoding="utf-8")
            data = json.loads(content)
        elif json_data is not None:
            data = json_data

        if data is None:
            return {"value_str": default, "value_json": {}, "found": False}

        if not key:
            val_str = data if isinstance(data, str) else json.dumps(data)
            val_json = data if isinstance(data, dict) else {"value": data}
            return {"value_str": val_str, "value_json": val_json, "found": True}

        parts = key.split(".")
        current: Any = data
        found = True
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
                current = current[int(part)]
            else:
                found = False
                break

        if not found:
            return {"value_str": default, "value_json": {}, "found": False}

        val_str = current if isinstance(current, str) else json.dumps(current)
        val_json = current if isinstance(current, dict) else {"value": current}
        return {"value_str": val_str, "value_json": val_json, "found": True}


class JsonMerge(Op):
    """Merge two JSON objects and write the combined dictionary to a JSON file.

    Args:
        a: Primary JSON dictionary.
        b: Secondary JSON dictionary whose keys take precedence on conflict.
        output_filename: Relative destination filename for the merged JSON artifact.
    """

    TITLE = "JSON Merge"
    CATEGORY = "Core / Text & Data"
    CACHEABLE = True

    class Outputs(TypedDict):
        merged: dict[str, Any]
        file: JsonFile

    def run(
        self,
        a: dict[str, Any],
        b: dict[str, Any],
        output_filename: str = "merged.json",
    ) -> Outputs:
        out_path = Path(output_filename)
        if out_path.is_absolute() or ".." in out_path.parts or len(out_path.parts) != 1:
            raise ValueError(
                f"output_filename must be a single relative file name, got {output_filename!r}"
            )

        merged = {**a, **b}
        out_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
        return {"merged": merged, "file": out_path}


class CsvSummary(Op):
    """Parse a CSV file and output summary metrics, stats JSON, and summary Markdown.

    Args:
        csv_file: Path to the input CSV file.
        delimiter: Column delimiter character used in the CSV.
    """

    TITLE = "CSV Summary"
    CATEGORY = "Core / Text & Data"
    CACHEABLE = True

    class Outputs(TypedDict):
        row_count: int
        column_count: int
        column_names: list[str]
        stats_json: JsonFile
        summary_md: MarkdownFile

    def run(self, csv_file: CsvFile, delimiter: str = ",") -> Outputs:
        csv_path = Path(csv_file)
        with open(csv_path, encoding="utf-8", newline="") as f:
            reader = csv.reader(f, delimiter=delimiter)
            header = next(reader, None)
            if header is None:
                column_names: list[str] = []
                row_count = 0
            else:
                column_names = [col.strip() for col in header]
                row_count = sum(1 for _ in reader)

        column_count = len(column_names)

        stats_path = Path("stats.json")
        stats_data = {
            "row_count": row_count,
            "column_count": column_count,
            "column_names": column_names,
        }
        stats_path.write_text(json.dumps(stats_data, indent=2), encoding="utf-8")

        cols_list = (
            "\n".join(f"- `{col}`" for col in column_names) if column_names else "- *(none)*"
        )
        summary_content = (
            f"# CSV Summary\n\n"
            f"- **Row count**: {row_count}\n"
            f"- **Column count**: {column_count}\n\n"
            f"### Columns\n\n"
            f"{cols_list}\n"
        )
        summary_path = Path("summary.md")
        summary_path.write_text(summary_content, encoding="utf-8")

        return {
            "row_count": row_count,
            "column_count": column_count,
            "column_names": column_names,
            "stats_json": stats_path,
            "summary_md": summary_path,
        }


__all__ = [
    "CsvSummary",
    "JsonExtract",
    "JsonMerge",
    "MathOp",
    "TemplateFormat",
]
