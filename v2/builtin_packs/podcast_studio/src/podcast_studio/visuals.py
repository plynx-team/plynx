"""Audio waveform visualization operation in ``podcast_studio``."""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Annotated, Literal, TypedDict

import numpy as np
from PIL import Image, ImageDraw
from plynx_sdk import AudioWav, ImageFile, Op, Range


def _read_wav_floats(path: Path) -> tuple[int, np.ndarray]:
    """Read WAV file into normalized float32 mono ndarray."""
    with wave.open(str(path), "rb") as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        sample_rate = wf.getframerate()
        frames = wf.getnframes()
        raw_bytes = wf.readframes(frames)

    if sampwidth == 2:
        shorts = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        samples = shorts if channels == 1 else shorts.reshape(-1, channels).mean(axis=1)
    else:
        samples = np.zeros(frames, dtype=np.float32)

    return sample_rate, samples


THEMES = {
    "emerald": {
        "primary": (16, 185, 129),
        "secondary": (52, 211, 153),
        "highlight": (167, 243, 208),
        "grid": (39, 39, 42),
    },
    "cyan": {
        "primary": (6, 182, 212),
        "secondary": (56, 189, 248),
        "highlight": (186, 230, 253),
        "grid": (39, 39, 42),
    },
    "violet": {
        "primary": (139, 92, 246),
        "secondary": (167, 139, 250),
        "highlight": (221, 214, 254),
        "grid": (39, 39, 42),
    },
    "amber": {
        "primary": (245, 158, 11),
        "secondary": (251, 191, 36),
        "highlight": (253, 230, 138),
        "grid": (39, 39, 42),
    },
}


class WaveformVisualizer(Op):
    """Render a soundwave amplitude plot image of an audio track."""

    TITLE = "Audio Waveform Visualizer"
    CATEGORY = "Podcast / Visuals"
    CACHEABLE = True

    class Outputs(TypedDict):
        waveform: ImageFile

    def run(
        self,
        audio: AudioWav,
        width: Annotated[int, Range(300, 2400)] = 800,
        height: Annotated[int, Range(100, 800)] = 240,
        theme: Literal["emerald", "cyan", "violet", "amber"] = "emerald",
    ) -> Outputs:
        """Render audio waveform envelope to PNG image.

        Args:
            audio: Input WAV audio artifact.
            width: Image width in pixels.
            height: Image height in pixels.
            theme: Color theme palette (emerald, cyan, violet, amber).

        Returns:
            Dictionary containing the generated `waveform` ImageFile.
        """
        sample_rate, samples = _read_wav_floats(Path(audio))
        colors = THEMES.get(theme, THEMES["emerald"])

        img = Image.new("RGB", (width, height), color=(18, 18, 22))
        draw = ImageDraw.Draw(img)

        cy = height // 2
        half_h = cy - 8

        # Draw grid lines (-6dB, -12dB, center)
        draw.line([(0, cy), (width, cy)], fill=colors["grid"], width=1)
        draw.line([(0, cy - int(half_h * 0.5)), (width, cy - int(half_h * 0.5))], fill=(28, 28, 32), width=1)
        draw.line([(0, cy + int(half_h * 0.5)), (width, cy + int(half_h * 0.5))], fill=(28, 28, 32), width=1)

        total_samples = len(samples)
        if total_samples > 0:
            chunk_size = max(1, total_samples // width)
            for x in range(width):
                start = x * chunk_size
                end = min(total_samples, start + chunk_size)
                if start >= total_samples:
                    break
                chunk = samples[start:end]
                peak = float(np.max(np.abs(chunk))) if len(chunk) > 0 else 0.0
                rms = float(np.sqrt(np.mean(chunk**2))) if len(chunk) > 0 else 0.0

                peak_h = max(1, int(peak * half_h))
                rms_h = max(1, int(rms * half_h))

                # Draw peak bar (secondary color)
                draw.line([(x, cy - peak_h), (x, cy + peak_h)], fill=colors["secondary"], width=1)
                # Draw core RMS energy (primary color)
                draw.line([(x, cy - rms_h), (x, cy + rms_h)], fill=colors["primary"], width=1)

        # Subtle border
        draw.rectangle([(0, 0), (width - 1, height - 1)], outline=(40, 40, 48), width=1)

        out_path = Path("waveform.png")
        img.save(str(out_path), "PNG")
        return {"waveform": out_path}


__all__ = ["WaveformVisualizer"]
