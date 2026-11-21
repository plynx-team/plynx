"""Audio technical stats analysis for ``pedalboard_studio``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

import numpy as np
from plynx_sdk import AudioWav, JsonFile, Op

from pedalboard_studio.effects import _read_audio


class AudioStats(Op):
    """Compute technical audio metrics: RMS, peak dBFS, dynamic range, and duration."""

    TITLE = "Audio Technical Stats"
    CATEGORY = "Inspect & Visualize"
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


__all__ = ["AudioStats"]
