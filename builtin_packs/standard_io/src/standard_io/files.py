"""File and directory operations in the built-in ``standard_io`` pack."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, TypedDict

from plynx_sdk import Directory, JsonFile, MarkdownFile, Op


class ListDirectory(Op):
    """List the contents of an input directory and produce file statistics and a manifest.

    Args:
        directory: Directory path to inspect and list.
        recursive: Whether to traverse subdirectories recursively.
        pattern: Glob pattern to filter matching file paths.
    """

    TITLE = "List Directory"
    CATEGORY = "Core / Files"
    CACHEABLE = True

    class Outputs(TypedDict):
        file_count: int
        filenames: list[str]
        manifest: JsonFile

    def run(
        self,
        directory: Directory,
        recursive: bool = True,
        pattern: str = "*",
    ) -> Outputs:
        dir_path = Path(directory)
        if not dir_path.is_dir():
            raise ValueError(f"Input path {directory} is not a valid directory")

        if recursive:
            file_paths = sorted([p for p in dir_path.rglob(pattern) if p.is_file()])
        else:
            file_paths = sorted([p for p in dir_path.glob(pattern) if p.is_file()])

        rel_filenames = [p.relative_to(dir_path).as_posix() for p in file_paths]
        manifest_path = Path("manifest.json")
        manifest_data = {
            "directory": dir_path.name,
            "file_count": len(rel_filenames),
            "filenames": rel_filenames,
        }
        manifest_path.write_text(
            json.dumps(manifest_data, indent=2), encoding="utf-8", newline="\n"
        )

        return {
            "file_count": len(rel_filenames),
            "filenames": rel_filenames,
            "manifest": manifest_path,
        }


class BundleDirectory(Op):
    """Bundle arbitrary files or sub-directories into a single structured output directory.

    Args:
        bundle_name: Name of the output destination folder in the working directory.
    """

    TITLE = "Bundle Directory"
    CATEGORY = "Core / Files"
    CACHEABLE = True
    ALLOW_EXTRA_INPUTS = True

    class Outputs(TypedDict):
        bundle: Directory
        file_count: int

    def run(
        self,
        bundle_name: str = "bundle",
        **files: Path,
    ) -> Outputs:
        bundle_path = Path(bundle_name)
        if bundle_path.is_absolute() or ".." in bundle_path.parts or len(bundle_path.parts) != 1:
            raise ValueError(
                f"bundle_name must be a single relative folder name, got {bundle_name!r}"
            )

        bundle_path.mkdir(parents=True, exist_ok=True)

        for candidate in files.values():
            if candidate is not None:
                src = Path(candidate)
                if not src.exists():
                    raise FileNotFoundError(f"Input file or directory to bundle not found: {src}")
                target = bundle_path / src.name
                if target.exists():
                    counter = 1
                    while target.exists():
                        target = bundle_path / f"{src.stem}_{counter}{src.suffix}"
                        counter += 1
                if src.is_dir():
                    shutil.copytree(src, target, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, target)

        total_files = sum(1 for p in bundle_path.rglob("*") if p.is_file())
        return {
            "bundle": bundle_path,
            "file_count": total_files,
        }


class MarkdownReport(Op):
    """Generate a clean Markdown document report from a title, body, and metrics.

    Args:
        title: Title displayed as the primary H1 header.
        body: Descriptive Markdown body content for the report.
        metrics: Optional key-value metrics dictionary to render as a list.
        filename: Output filename for the generated Markdown report.
    """

    TITLE = "Markdown Report"
    CATEGORY = "Core / Files"
    CACHEABLE = True

    class Outputs(TypedDict):
        report: MarkdownFile

    def run(
        self,
        title: str = "Execution Report",
        body: str = "",
        metrics: dict[str, Any] | None = None,
        filename: str = "report.md",
    ) -> Outputs:
        out_path = Path(filename)
        if out_path.is_absolute() or ".." in out_path.parts or len(out_path.parts) != 1:
            raise ValueError(f"filename must be a single relative file name, got {filename!r}")

        lines = [f"# {title}", ""]
        if body.strip():
            lines.extend([body.strip(), ""])
        if metrics:
            lines.extend(["## Metrics", ""])
            for key, value in metrics.items():
                lines.append(f"- **{key}**: {value}")
            lines.append("")

        out_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
        return {"report": out_path}


__all__ = [
    "BundleDirectory",
    "ListDirectory",
    "MarkdownReport",
]
