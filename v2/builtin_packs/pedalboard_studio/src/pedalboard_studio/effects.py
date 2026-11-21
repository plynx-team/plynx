"""DSP audio effects powered by Spotify's Pedalboard library for ``pedalboard_studio``."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, TypedDict

import numpy as np
from pedalboard import Chorus, Delay, HighpassFilter, LowpassFilter, Pedalboard, Reverb  # type: ignore[attr-defined]
from pedalboard.io import AudioFile
from plynx_sdk import AudioWav, Op, Range
from scipy.ndimage import maximum_filter1d  # type: ignore[import-untyped]
from scipy.signal import lfilter  # type: ignore[import-untyped]


def _read_audio(path: Path) -> tuple[np.ndarray, int]:
    """Read a WAV file using Pedalboard into (channels, samples) float32 array and sample rate."""
    with AudioFile(str(path)) as f:
        audio = f.read(f.frames)
        sr = int(f.samplerate)
    if audio.ndim == 1:
        audio = np.stack([audio, audio])
    return audio, sr


def _read_audio_preserve_channels(path: Path) -> tuple[np.ndarray, int]:
    """Read a WAV file preserving its native channel count as ``(channels, samples)`` float32."""
    with AudioFile(str(path)) as f:
        audio = f.read(f.frames)
        sr = int(f.samplerate)
    if audio.ndim == 1:
        audio = audio[np.newaxis, :]
    return audio.astype(np.float32), sr


def _resample_channels(audio: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    """Linearly resample a ``(channels, samples)`` array when sample rates differ."""
    if src_sr == dst_sr or audio.shape[1] == 0:
        return audio
    target_len = max(1, round(audio.shape[1] * (dst_sr / float(src_sr))))
    src_x = np.arange(audio.shape[1], dtype=np.float32)
    dst_x = np.linspace(0.0, float(audio.shape[1] - 1), target_len, dtype=np.float32)
    out = np.zeros((audio.shape[0], target_len), dtype=np.float32)
    for ch in range(audio.shape[0]):
        out[ch] = np.interp(dst_x, src_x, audio[ch])
    return out


def _write_audio(path: Path, audio: np.ndarray, sample_rate: int) -> Path:
    """Write (channels, samples) float32 audio to a 16-bit PCM WAV file."""
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


class AudioMixer(Op):
    """Mix two or more audio tracks with stereo preservation and optional voiceover ducking.

    Supports arbitrary extra audio tracks via dynamic inputs (`+ Add input` in the Inspector),
    preserving 2-channel stereo whenever any input is stereo.

    Enable ``ducking_enabled`` to use ``track_1`` as a sidechain/voiceover signal that
    automatically ducks ``track_2`` and all extra background tracks when speech is active.
    """

    TITLE = "Multi-Track Audio Mixer"
    CATEGORY = "Audio / Effects & Mixing"
    CACHEABLE = True
    ALLOW_EXTRA_INPUTS = True

    class Outputs(TypedDict):
        mixed_audio: AudioWav
        total_duration_sec: float

    def run(
        self,
        track_1: AudioWav,
        track_2: AudioWav | None = None,
        track_1_gain: Annotated[float, Range(0.0, 2.0)] = 1.0,
        track_2_gain: Annotated[float, Range(0.0, 2.0)] = 0.8,
        extra_tracks_gain: Annotated[float, Range(0.0, 2.0)] = 0.8,
        ducking_enabled: bool = False,
        ducking_amount_db: Annotated[float, Range(0.0, 30.0)] = 14.0,
        lead_in_sec: Annotated[float, Range(0.0, 10.0)] = 0.0,
        tail_sec: Annotated[float, Range(0.0, 10.0)] = 0.0,
        loop_background: bool = False,
        **extra_tracks: AudioWav,
    ) -> Outputs:
        """Sum multiple audio tracks with optional sidechain ducking and stereo preservation.

        Args:
            track_1: Primary audio track (sidechain/voiceover trigger when ducking is enabled).
            track_2: Optional second audio track (e.g. background music or drums).
            track_1_gain: Volume multiplier for `track_1`.
            track_2_gain: Volume multiplier for `track_2`.
            extra_tracks_gain: Volume multiplier applied to all dynamically added extra tracks.
            ducking_enabled: Attenuate background tracks automatically while `track_1` is active.
            ducking_amount_db: Attenuation depth in dB during voiceover activity.
            lead_in_sec: Seconds of background audio before `track_1` starts.
            tail_sec: Seconds of background audio after `track_1` finishes.
            loop_background: Loop shorter background tracks to cover the full mix duration.
            **extra_tracks: Arbitrary additional `AudioWav` tracks to mix together.

        Returns:
            Dictionary containing `mixed_audio` and `total_duration_sec`.
        """
        primary_audio, sample_rate = _read_audio_preserve_channels(Path(track_1))

        bg_entries: list[tuple[np.ndarray, float]] = []
        if track_2 is not None:
            t2_audio, t2_sr = _read_audio_preserve_channels(Path(track_2))
            bg_entries.append(
                (_resample_channels(t2_audio, t2_sr, sample_rate), float(track_2_gain))
            )

        for key in sorted(extra_tracks):
            val = extra_tracks[key]
            if val is not None:
                ex_audio, ex_sr = _read_audio_preserve_channels(Path(val))
                bg_entries.append(
                    (_resample_channels(ex_audio, ex_sr, sample_rate), float(extra_tracks_gain))
                )

        # Preserve stereo if any input track has 2+ channels
        out_channels = max([primary_audio.shape[0]] + [arr.shape[0] for arr, _ in bg_entries])
        if primary_audio.shape[0] < out_channels:
            primary_audio = np.repeat(primary_audio, out_channels, axis=0)

        normalized_bg: list[tuple[np.ndarray, float]] = []
        for arr, gain in bg_entries:
            if arr.shape[0] < out_channels:
                arr = np.repeat(arr, out_channels, axis=0)
            normalized_bg.append((arr, gain))

        lead_in_samples = int(lead_in_sec * sample_rate)
        tail_samples = int(tail_sec * sample_rate)
        primary_span = lead_in_samples + primary_audio.shape[1] + tail_samples

        if ducking_enabled or loop_background:
            total_samples = max(1, primary_span)
        else:
            bg_max = max((arr.shape[1] for arr, _ in normalized_bg), default=0)
            total_samples = max(1, primary_span, bg_max)

        primary_layer = np.zeros((out_channels, total_samples), dtype=np.float32)
        p_end = min(total_samples, lead_in_samples + primary_audio.shape[1])
        if p_end > lead_in_samples:
            primary_layer[:, lead_in_samples:p_end] = primary_audio[
                :, : p_end - lead_in_samples
            ] * float(track_1_gain)

        bg_mix = np.zeros((out_channels, total_samples), dtype=np.float32)
        for arr, gain in normalized_bg:
            if arr.shape[1] == 0:
                continue
            if loop_background and arr.shape[1] < total_samples:
                repeats = int(np.ceil(total_samples / float(arr.shape[1])))
                tiled = np.tile(arr, (1, repeats))[:, :total_samples]
                bg_mix += tiled * gain
            else:
                copy_len = min(total_samples, arr.shape[1])
                bg_mix[:, :copy_len] += arr[:, :copy_len] * gain

        if ducking_enabled and normalized_bg:
            # Vectorized voice-activity detection + smooth gain envelope
            speech_abs = np.max(np.abs(primary_layer), axis=0)
            margin_samples = max(1, int(0.15 * sample_rate))
            envelope = maximum_filter1d(speech_abs, size=margin_samples * 2 + 1)
            duck_gain = float(10.0 ** (-ducking_amount_db / 20.0))
            target_gain = np.where(envelope > 0.015, duck_gain, 1.0).astype(np.float32)
            # Smooth transitions (~60ms exponential moving average)
            smooth_alpha = float(1.0 - np.exp(-1.0 / max(1.0, 0.06 * sample_rate)))
            smoothed = np.asarray(
                lfilter([smooth_alpha], [1.0, -(1.0 - smooth_alpha)], target_gain), dtype=np.float32
            )
            bg_mix *= smoothed[np.newaxis, :]

        mixed = primary_layer + bg_mix

        if ducking_enabled and tail_sec > 0.0:
            fade_len = min(total_samples, int(min(1.5, tail_sec) * sample_rate))
            if fade_len > 0:
                fade = np.linspace(1.0, 0.0, fade_len, dtype=np.float32)
                mixed[:, -fade_len:] *= fade

        peak = float(np.max(np.abs(mixed)))
        if peak > 0.95:
            mixed = (mixed / peak) * 0.95

        out_path = Path("mixed_audio.wav")
        _write_audio(out_path, mixed, sample_rate)
        return {
            "mixed_audio": out_path,
            "total_duration_sec": round(total_samples / float(sample_rate), 3),
        }


__all__ = [
    "AudioMixer",
    "PedalboardChorus",
    "PedalboardDelay",
    "PedalboardReverb",
    "PedalboardToneFilter",
]
