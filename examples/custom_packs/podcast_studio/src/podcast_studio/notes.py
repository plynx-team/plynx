"""Show notes and markdown compilation operation in ``podcast_studio``."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from plynx_sdk import MarkdownFile, Op, TextFile


class ShowNotesGenerator(Op):
    """Compile episode metadata, chapter markers, and transcript into formatted show notes."""

    TITLE = "Podcast Show Notes Generator"
    CATEGORY = "Inspect & Visualize"
    CACHEABLE = True

    class Outputs(TypedDict):
        show_notes: MarkdownFile
        chapter_count: int

    def run(
        self,
        title: str = "Episode 42: The Power of Local DAGs",
        podcast_name: str = "Plynx Audio Labs",
        host: str = "Plynx Studio",
        summary: str = (
            "Explore how macOS native speech synthesis (`say`) pairs with procedural lo-fi "
            "music loops, dynamic audio ducking, and atomic workflow execution in Plynx v2."
        ),
        chapters: str = (
            "00:00 - Introduction & Welcome\n"
            "00:03 - macOS Speech & Zero Cloud Keys\n"
            "00:08 - Real-Time Audio Ducking & Mixing\n"
            "00:14 - Atomic Reproducibility & Outro"
        ),
        transcript: str = "",
        script: TextFile | None = None,
    ) -> Outputs:
        """Generate podcast episode show notes.

        Args:
            title: Title of the podcast episode.
            podcast_name: Name of the podcast show or channel.
            host: Name or handle of the episode host.
            summary: Brief description or pitch of the episode.
            chapters: Newline-separated list of chapter markers (e.g. '00:00 - Intro').
            transcript: Full spoken text or dialogue of the episode.
            script: Optional TextFile containing the original script.

        Returns:
            Dictionary containing `show_notes` MarkdownFile and parsed `chapter_count`.
        """
        full_transcript = transcript
        if script is not None:
            script_path = Path(script)
            if script_path.is_file():
                full_transcript = script_path.read_text(encoding="utf-8").strip()

        # Parse chapters into table rows
        chapter_rows: list[str] = []
        parsed_count = 0
        for line in chapters.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split("-", 1)]
            if len(parts) == 2:
                timestamp, topic = parts
                chapter_rows.append(f"| `{timestamp}` | **{topic}** |")
                parsed_count += 1
            else:
                chapter_rows.append(f"| `•` | {line} |")
                parsed_count += 1

        md_content = [
            f"# {podcast_name}",
            "",
            f"## {title}",
            "",
            f"> **Host:** {host}  ",
            "> **Produced with:** [Plynx v2](https://github.com/plynx-team/plynx) (macOS Native Audio Pipeline)  ",
            "> **Audio Engine:** macOS Native Speech (`say`) + Dynamic Ducking Mixer  ",
            "",
            "---",
            "",
            "### 📖 Episode Summary",
            "",
            summary,
            "",
            "### ⏱️ Chapter Markers",
            "",
            "| Time | Segment |",
            "| :--- | :--- |",
        ]
        md_content.extend(chapter_rows)
        md_content.extend(
            [
                "",
                "---",
                "",
                "### 🎙️ Spoken Transcript",
                "",
                f'"{full_transcript}"' if full_transcript else "*[No transcript provided]*",
                "",
                "---",
                "",
                "### 🛠️ Production Notes",
                "",
                "- **Speech Engine:** macOS Native TTS (`say` with PCM 16-bit 44.1 kHz LEI16).",
                "- **BGM:** Procedural lo-fi chord synthesis with Rhodes electric piano harmonics.",
                "- **Mixing:** Automatic RMS ducking (-14 dB attenuation during voice).",
                "- **Visuals:** High-resolution stereo soundwave envelope.",
                "",
                "*Generated automatically by Plynx v2 `podcast_studio` pack.*",
            ]
        )

        out_path = Path("show_notes.md")
        out_path.write_text("\n".join(md_content), encoding="utf-8")

        return {
            "show_notes": out_path,
            "chapter_count": parsed_count,
        }


__all__ = ["ShowNotesGenerator"]
