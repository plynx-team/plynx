"""macOS Native Speech Synthesis operation in ``podcast_studio``."""

from __future__ import annotations

import logging
import math
import platform
import shutil
import struct
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Annotated, Literal, TypedDict

from plynx_sdk import AudioWav, Op, Range, TextFile

logger = logging.getLogger(__name__)

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


def _write_pcm16_wav(path: Path, samples: list[float], sample_rate: int = 44100) -> None:
    """Write normalized float samples (-1.0 to 1.0) as 16-bit mono PCM WAV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        raw_bytes = bytearray()
        for s in samples:
            clamped = max(-1.0, min(1.0, s))
            int_val = int(clamped * 32767.0)
            raw_bytes.extend(struct.pack("<h", int_val))
        wf.writeframes(bytes(raw_bytes))


class TextToSpeech(Op):
    """Convert input script text to voiceover audio using native macOS speech synthesis.

    Note:
        This operation is macOS only. It uses the operating system's built-in `say` command
        to produce studio-quality offline speech synthesis with zero API keys.
    """

    TITLE = "Text to Speech (macOS only)"
    CATEGORY = "Audio / Synth & Voice"
    CACHEABLE = True

    class Outputs(TypedDict):
        voiceover: AudioWav
        character_count: int

    def _generate_synthetic_fallback(
        self,
        out_path: Path,
        text: str,
        rate: int,
        sample_rate: int = 44100,
    ) -> None:
        """Synthesize a fallback vocal acoustic track when 'say' is unavailable."""
        words = text.split()
        num_words = max(1, len(words))
        # Estimate duration from words per minute
        duration_sec = max(1.5, (num_words / float(rate)) * 60.0)
        total_samples = int(duration_sec * sample_rate)
        samples = [0.0] * total_samples

        word_len = total_samples // num_words
        for w_idx in range(num_words):
            start = w_idx * word_len
            end = min(total_samples, start + int(word_len * 0.8))
            f0 = 180.0 + (w_idx % 4) * 15.0
            for i in range(start, end):
                t = (i - start) / float(sample_rate)
                # Formant-like harmonic blend
                harm1 = math.sin(2.0 * math.pi * f0 * t)
                harm2 = 0.5 * math.sin(2.0 * math.pi * f0 * 2.0 * t)
                harm3 = 0.25 * math.sin(2.0 * math.pi * f0 * 3.0 * t)
                val = harm1 + harm2 + harm3
                env = math.sin(math.pi * (i - start) / (end - start))
                samples[i] = val * env * 0.4

        _write_pcm16_wav(out_path, samples, sample_rate)

    def run(
        self,
        text: str = (
            "Welcome to Plynx Studio! In today's episode, we explore reproducible graph automation, "
            "macOS native voice synthesis, and dynamic audio ducking with zero cloud API keys."
        ),
        script: TextFile | None = None,
        voice: MACOS_VOICES = "Samantha",
        rate: Annotated[int, Range(100, 300)] = 175,
    ) -> Outputs:
        """Run macOS speech synthesis.

        Args:
            text: Inline speech text to read if `script` file is not supplied.
            script: Optional text file containing the episode transcript or script.
            voice: Name of the macOS native system voice.
            rate: Speech rate in words per minute (typical conversational speech is 160-190 wpm).

        Returns:
            Dictionary containing the generated `voiceover` AudioWav and `character_count`.
        """
        content = text
        if script is not None:
            script_path = Path(script)
            if script_path.is_file():
                content = script_path.read_text(encoding="utf-8").strip()

        if not content:
            content = "This is a placeholder voiceover."

        out_path = Path("voiceover.wav")

        is_macos = platform.system() == "Darwin"
        say_bin = shutil.which("say")

        if is_macos and say_bin:
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
                    logger.warning(
                        "say command failed (code %d): %s. Falling back to synthetic tone.",
                        proc.returncode,
                        proc.stderr,
                    )
                    self._generate_synthetic_fallback(out_path, content, rate)
            finally:
                temp_text_path.unlink(missing_ok=True)
        else:
            logger.info("Non-macOS platform or 'say' command not available. Using synthetic audio fallback.")
            self._generate_synthetic_fallback(out_path, content, rate)

        return {
            "voiceover": out_path,
            "character_count": len(content),
        }


__all__ = ["MACOS_VOICES", "TextToSpeech"]
