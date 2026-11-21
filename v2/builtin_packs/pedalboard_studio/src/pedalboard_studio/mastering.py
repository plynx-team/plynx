"""Studio mastering compressor, limiter, and dynamics chain for ``pedalboard_studio``."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, TypedDict

from pedalboard import Compressor, Gain, Limiter, PeakFilter, Pedalboard  # type: ignore[attr-defined]
from plynx_sdk import AudioWav, Op, Range

from pedalboard_studio.effects import _read_audio, _write_audio


class PedalboardMastering(Op):
    """Apply studio dynamic compression, EQ sweetening, and brickwall limiting."""

    TITLE = "Pedalboard Studio Mastering"
    CATEGORY = "Audio / Mastering"
    CACHEABLE = True

    class Outputs(TypedDict):
        mastered_audio: AudioWav

    def run(
        self,
        audio: AudioWav,
        compressor_threshold_db: Annotated[float, Range(-40.0, 0.0)] = -16.0,
        compressor_ratio: Annotated[float, Range(1.0, 10.0)] = 2.5,
        presence_boost_db: Annotated[float, Range(-6.0, 6.0)] = 1.5,
        presence_freq_hz: Annotated[float, Range(2000.0, 8000.0)] = 3500.0,
        gain_db: Annotated[float, Range(-12.0, 12.0)] = 1.5,
        limiter_threshold_db: Annotated[float, Range(-6.0, 0.0)] = -0.5,
    ) -> Outputs:
        audio_data, sample_rate = _read_audio(audio)

        board = Pedalboard(
            [
                PeakFilter(
                    cutoff_frequency_hz=float(presence_freq_hz),
                    gain_db=float(presence_boost_db),
                    q=0.7,
                ),
                Compressor(
                    threshold_db=float(compressor_threshold_db),
                    ratio=float(compressor_ratio),
                    attack_ms=15.0,
                    release_ms=120.0,
                ),
                Gain(gain_db=float(gain_db)),
                Limiter(threshold_db=float(limiter_threshold_db)),
            ]
        )
        effected = board(audio_data, sample_rate)

        out_path = Path("mastered_track.wav")
        _write_audio(out_path, effected, sample_rate)
        return {"mastered_audio": out_path}


__all__ = ["PedalboardMastering"]
