"""Show notes and markdown compilation operation in ``podcast_studio``."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from plynx_sdk import MarkdownFile, Op, TextFile


class ShowNotesGenerator(Op):
    """Compile episode metadata, chapter markers, and transcript into Markdown show notes."""

    TITLE = "Podcast Show Notes Generator"
    CATEGORY = "Inspect & Visualize"
    CACHEABLE = True

    class Outputs(TypedDict):
        show_notes: MarkdownFile
        chapter_count: int

    def run(
        self,
        title: str = "Episode 1",
        podcast_name: str = "Podcast",
        host: str = "Host",
        summary: str = "",
        chapters: str = "",
        transcript: str = "",
        script: TextFile | None = None,
        production_notes: str = "",
    ) -> Outputs:
        """Generate podcast episode show notes.

        Args:
            title: Title of the podcast episode.
            podcast_name: Name of the podcast show or channel.
            host: Name or handle of the episode host.
            summary: Brief description of the episode.
            chapters: Newline-separated list of chapter markers (e.g. '00:00 - Intro').
            transcript: Full spoken text or dialogue of the episode.
            script: Optional TextFile containing the original script (overrides `transcript`).
            production_notes: Optional Markdown notes appended under a Production Notes heading.

        Returns:
            Dictionary containing `show_notes` MarkdownFile and parsed `chapter_count`.
        """
        full_transcript = transcript
        if script is not None:
            script_path = Path(script)
            if script_path.is_file():
                full_transcript = script_path.read_text(encoding="utf-8").strip()

        chapter_rows: list[str] = []
        parsed_count = 0
        for raw_line in chapters.strip().splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split("-", 1)]
            if len(parts) == 2:
                timestamp, topic = parts
                chapter_rows.append(f"| `{timestamp}` | **{topic}** |")
            else:
                chapter_rows.append(f"| `•` | {line} |")
            parsed_count += 1

        md_content: list[str] = [
            f"# {podcast_name}",
            "",
            f"## {title}",
            "",
            f"> **Host:** {host}",
            "",
        ]
        if summary.strip():
            md_content.extend(
                [
                    "### Episode Summary",
                    "",
                    summary.strip(),
                    "",
                ]
            )
        if chapter_rows:
            md_content.extend(
                [
                    "### Chapter Markers",
                    "",
                    "| Time | Segment |",
                    "| :--- | :--- |",
                    *chapter_rows,
                    "",
                ]
            )

        md_content.extend(
            [
                "### Transcript",
                "",
                f'"{full_transcript}"' if full_transcript.strip() else "*[No transcript provided]*",
                "",
            ]
        )

        if production_notes.strip():
            md_content.extend(
                [
                    "### Production Notes",
                    "",
                    production_notes.strip(),
                    "",
                ]
            )

        out_path = Path("show_notes.md")
        out_path.write_text("\n".join(md_content), encoding="utf-8")

        return {
            "show_notes": out_path,
            "chapter_count": parsed_count,
        }


__all__ = ["ShowNotesGenerator"]
