"""DSP audio effects powered by Spotify's Pedalboard library for ``pedalboard_studio``."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, TypedDict

import numpy as np
from pedalboard import Chorus, Delay, HighpassFilter, LowpassFilter, Pedalboard, Reverb  # type: ignore[attr-defined]
from pedalboard.io import AudioFile
from plynx_sdk import AudioWav, Op, Range


def _read_audio(path: Path) -> tuple[np.ndarray, int]:
    """Read a WAV file using Pedalboard into (channels, samples) float32 array and sample rate."""
    with AudioFile(str(path)) as f:
        audio = f.read(f.frames)
        sr = int(f.samplerate)
    if audio.ndim == 1:
        audio = np.stack([audio, audio])
    return audio, sr


def _write_audio(path: Path, audio: np.ndarray, sample_rate: int) -> Path:
    """Write (channels, samples) float32 audio to a WAV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with AudioFile(str(path), "w", samplerate=sample_rate, num_channels=audio.shape[0]) as f:
        f.write(audio)
    return path


class PedalboardToneFilter(Op):
    """Shape audio frequency response with studio high-pass and low-pass filters."""

    TITLE = "Pedalboard Tone Filter"
    CATEGORY = "Audio / Effects & Mixing"
    CACHEABLE = True

    class Outputs(TypedDict):
        filtered_audio: AudioWav

    def run(
        self,
        audio: AudioWav,
        highpass_cutoff_hz: Annotated[float, Range(20.0, 500.0)] = 55.0,
        lowpass_cutoff_hz: Annotated[float, Range(2000.0, 22000.0)] = 14000.0,
    ) -> Outputs:
        audio_data, sample_rate = _read_audio(audio)

        board = Pedalboard(
            [
                HighpassFilter(cutoff_frequency_hz=float(highpass_cutoff_hz)),
                LowpassFilter(cutoff_frequency_hz=float(lowpass_cutoff_hz)),
            ]
        )
        effected = board(audio_data, sample_rate)

        out_path = Path("filtered_tone.wav")
        _write_audio(out_path, effected, sample_rate)
        return {"filtered_audio": out_path}


class PedalboardChorus(Op):
    """Add warm multi-voice stereo chorus modulation and width."""

    TITLE = "Pedalboard Chorus"
    CATEGORY = "Audio / Effects & Mixing"
    CACHEABLE = True

    class Outputs(TypedDict):
        chorus_audio: AudioWav

    def run(
        self,
        audio: AudioWav,
        rate_hz: Annotated[float, Range(0.1, 5.0)] = 0.75,
        depth: Annotated[float, Range(0.0, 1.0)] = 0.25,
        centre_delay_ms: Annotated[float, Range(1.0, 30.0)] = 8.0,
        feedback: Annotated[float, Range(0.0, 0.8)] = 0.15,
        mix: Annotated[float, Range(0.0, 1.0)] = 0.35,
    ) -> Outputs:
        audio_data, sample_rate = _read_audio(audio)

        board = Pedalboard(
            [
                Chorus(
                    rate_hz=float(rate_hz),
                    depth=float(depth),
                    centre_delay_ms=float(centre_delay_ms),
                    feedback=float(feedback),
                    mix=float(mix),
                )
            ]
        )
        effected = board(audio_data, sample_rate)

        out_path = Path("chorus.wav")
        _write_audio(out_path, effected, sample_rate)
        return {"chorus_audio": out_path}


class PedalboardDelay(Op):
    """Apply spatial delay and rhythmic echoes to the audio signal."""

    TITLE = "Pedalboard Delay"
    CATEGORY = "Audio / Effects & Mixing"
    CACHEABLE = True

    class Outputs(TypedDict):
        delayed_audio: AudioWav

    def run(
        self,
        audio: AudioWav,
        delay_seconds: Annotated[float, Range(0.05, 1.5)] = 0.32,
        feedback: Annotated[float, Range(0.0, 0.9)] = 0.22,
        mix: Annotated[float, Range(0.0, 1.0)] = 0.20,
    ) -> Outputs:
        audio_data, sample_rate = _read_audio(audio)

        board = Pedalboard(
            [
                Delay(
                    delay_seconds=float(delay_seconds),
                    feedback=float(feedback),
                    mix=float(mix),
                )
            ]
        )
        effected = board(audio_data, sample_rate)

        out_path = Path("delay.wav")
        _write_audio(out_path, effected, sample_rate)
        return {"delayed_audio": out_path}


class PedalboardReverb(Op):
    """Simulate lush acoustic concert hall and cathedral reverberation."""

    TITLE = "Pedalboard Reverb"
    CATEGORY = "Audio / Effects & Mixing"
    CACHEABLE = True

    class Outputs(TypedDict):
        reverb_audio: AudioWav

    def run(
        self,
        audio: AudioWav,
        room_size: Annotated[float, Range(0.0, 1.0)] = 0.72,
        damping: Annotated[float, Range(0.0, 1.0)] = 0.35,
        wet_level: Annotated[float, Range(0.0, 1.0)] = 0.38,
        dry_level: Annotated[float, Range(0.0, 1.0)] = 0.82,
        width: Annotated[float, Range(0.0, 1.0)] = 1.0,
    ) -> Outputs:
        audio_data, sample_rate = _read_audio(audio)

        board = Pedalboard(
            [
                Reverb(
                    room_size=float(room_size),
                    damping=float(damping),
                    wet_level=float(wet_level),
                    dry_level=float(dry_level),
                    width=float(width),
                )
            ]
        )
        effected = board(audio_data, sample_rate)

        out_path = Path("reverb.wav")
        _write_audio(out_path, effected, sample_rate)
        return {"reverb_audio": out_path}


__all__ = [
    "PedalboardChorus",
    "PedalboardDelay",
    "PedalboardReverb",
    "PedalboardToneFilter",
]
