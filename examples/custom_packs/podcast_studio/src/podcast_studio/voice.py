"""macOS Native Speech Synthesis operation in ``podcast_studio``."""

from __future__ import annotations

import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Annotated, Literal, TypedDict

from plynx_sdk import AudioWav, Op, Range, SideEffect, TextFile

MACOS_VOICES = Literal[
    "Samantha",
    "Daniel",
    "Fred",
    "Karen",
    "Moira",
    "Alex",
    "Albert",
    "Ralph",
]


class TextToSpeech(Op):
    """Convert input script text to 44.1 kHz 16-bit mono WAV using macOS ``say`` (macOS only).

    Requires macOS with the native ``say`` command on ``PATH``; raises ``RuntimeError``
    on unsupported platforms or synthesis errors so downstream nodes stop cleanly (and
    optional stage validators can inspect ``stderr.log`` to propose an alternative).
    """

    TITLE = "Text to Speech (macOS only)"
    CATEGORY = "Audio / Synth & Voice"
    CACHEABLE = True
    SIDE_EFFECTS = SideEffect.NONE

    class Outputs(TypedDict):
        voiceover: AudioWav
        character_count: int

    def run(
        self,
        text: str = "",
        script: TextFile | None = None,
        voice: MACOS_VOICES = "Samantha",
        rate: Annotated[int, Range(100, 300)] = 175,
    ) -> Outputs:
        """Run macOS speech synthesis via ``say``.

        Args:
            text: Inline speech text to synthesize if `script` file is not supplied.
            script: Optional text file containing the transcript or script.
            voice: Name of the macOS native system voice.
            rate: Speech rate in words per minute (typical conversational speech is 160-190 wpm).

        Returns:
            Dictionary containing the generated `voiceover` AudioWav and `character_count`.
        """
        if platform.system() != "Darwin":
            raise RuntimeError(f"TextToSpeech requires macOS (Darwin), got {platform.system()!r}.")
        say_bin = shutil.which("say")
        if say_bin is None:
            raise RuntimeError("TextToSpeech requires the macOS 'say' command on PATH.")

        content = text.strip()
        if script is not None:
            script_path = Path(script)
            if not script_path.is_file():
                raise FileNotFoundError(f"Script file not found: {script_path}")
            content = script_path.read_text(encoding="utf-8").strip()

        if not content:
            raise ValueError("Provide non-empty 'text' or a 'script' file for speech synthesis.")

        out_path = Path("voiceover.wav")
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as tf:
            tf.write(content)
            temp_text_path = Path(tf.name)

        try:
            cmd = [
                say_bin,
                "-v",
                voice,
                "-r",
                str(rate),
                "--file-format=WAVE",
                "--data-format=LEI16@44100",
                "-f",
                str(temp_text_path),
                "-o",
                str(out_path),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if proc.returncode != 0 or not out_path.is_file() or out_path.stat().st_size == 0:
                raise RuntimeError(
                    f"macOS 'say' command failed (exit {proc.returncode}): {proc.stderr.strip()}"
                )
        finally:
            temp_text_path.unlink(missing_ok=True)

        return {
            "voiceover": out_path,
            "character_count": len(content),
        }


__all__ = ["MACOS_VOICES", "TextToSpeech"]
