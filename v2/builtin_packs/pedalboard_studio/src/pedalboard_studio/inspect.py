"""Audio waveform visualization and technical stats analysis for ``pedalboard_studio``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, TypedDict

import numpy as np
from PIL import Image, ImageDraw
from plynx_sdk import AudioWav, ImageFile, JsonFile, Op, Range

from pedalboard_studio.effects import _read_audio


class AudioWaveformVisualizer(Op):
    """Render a dual-panel studio stereo waveform and RMS envelope image."""

    TITLE = "Audio Waveform Visualizer"
    CATEGORY = "Audio / Inspect"
    CACHEABLE = True

    class Outputs(TypedDict):
        waveform: ImageFile

    def run(
        self,
        audio: AudioWav,
        width: Annotated[int, Range(400, 1920)] = 1000,
        height: Annotated[int, Range(200, 800)] = 360,
    ) -> Outputs:
        audio_data, sample_rate = _read_audio(audio)
        n_channels, total_samples = audio_data.shape

        img = Image.new("RGB", (width, height), color=(26, 26, 26))
        draw = ImageDraw.Draw(img)

        # Header banner
        draw.rectangle([(0, 0), (width, 28)], fill=(36, 36, 36))
        dur_sec = total_samples / sample_rate
        header_text = f"AUDIO WAVEFORM • {dur_sec:.2f}s • {sample_rate} Hz • {n_channels} CH"
        draw.text((12, 8), header_text, fill=(200, 200, 200))

        # Channel layout
        ch_height = (height - 36) // n_channels
        ch_colors = [(0, 216, 255), (56, 193, 114)]  # Cyan (Left), Green (Right)

        for ch in range(n_channels):
            ch_data = audio_data[ch]
            top_y = 32 + ch * ch_height
            bot_y = top_y + ch_height
            mid_y = (top_y + bot_y) // 2

            # Background grid lines
            draw.line([(0, mid_y), (width, mid_y)], fill=(45, 45, 45), width=1)
            draw.line([(0, top_y), (width, top_y)], fill=(50, 50, 50), width=1)

            ch_name = "LEFT CHANNEL" if ch == 0 else "RIGHT CHANNEL"
            draw.text((12, top_y + 4), ch_name, fill=(130, 130, 130))

            # Downsample to pixel width
            chunk_size = max(1, total_samples // width)
            color = ch_colors[ch % len(ch_colors)]

            for x in range(width):
                s_start = x * chunk_size
                s_end = min(total_samples, (x + 1) * chunk_size)
                if s_start >= total_samples or s_end <= s_start:
                    continue
                chunk = ch_data[s_start:s_end]
                c_min = float(np.min(chunk))
                c_max = float(np.max(chunk))

                half_span = (ch_height // 2) - 10
                y1 = int(mid_y - c_max * half_span)
                y2 = int(mid_y - c_min * half_span)
                draw.line([(x, y1), (x, y2)], fill=color, width=1)

        out_path = Path("waveform.png")
        img.save(str(out_path), format="PNG")
        return {"waveform": out_path}


class AudioStats(Op):
    """Compute technical audio metrics: RMS, peak dBFS, dynamic range, and duration."""

    TITLE = "Audio Technical Stats"
    CATEGORY = "Audio / Inspect"
    CACHEABLE = True

    class Outputs(TypedDict):
        stats: JsonFile

    def run(self, audio: AudioWav) -> Outputs:
        audio_data, sample_rate = _read_audio(audio)
        n_channels, total_samples = audio_data.shape

        duration_sec = total_samples / sample_rate

        # Peak amplitude and dBFS
        peak_amp = float(np.max(np.abs(audio_data)))
        peak_db = 20.0 * np.log10(max(peak_amp, 1e-9))

        # RMS amplitude and dBFS
        rms_amp = float(np.sqrt(np.mean(audio_data**2)))
        rms_db = 20.0 * np.log10(max(rms_amp, 1e-9))

        # Dynamic range (crest factor)
        crest_factor_db = peak_db - rms_db

        stats = {
            "duration_sec": round(duration_sec, 3),
            "sample_rate": sample_rate,
            "channels": n_channels,
            "total_samples": total_samples,
            "peak_amplitude": round(peak_amp, 4),
            "peak_dbfs": round(peak_db, 2),
            "rms_amplitude": round(rms_amp, 4),
            "rms_dbfs": round(rms_db, 2),
            "crest_factor_db": round(crest_factor_db, 2),
            "clipping_detected": bool(peak_amp >= 0.999),
        }

        out_path = Path("audio_stats.json")
        out_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
        return {"stats": out_path}


__all__ = ["AudioStats", "AudioWaveformVisualizer"]
