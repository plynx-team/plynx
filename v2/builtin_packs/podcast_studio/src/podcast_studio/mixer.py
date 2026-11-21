"""Audio mixing and automatic voice ducking operation in ``podcast_studio``."""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Annotated, TypedDict

import numpy as np
from plynx_sdk import AudioWav, Op, Range


def _read_wav_to_float(path: Path) -> tuple[int, np.ndarray]:
    """Read a mono or stereo WAV file into normalized float32 mono ndarray."""
    with wave.open(str(path), "rb") as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        sample_rate = wf.getframerate()
        frames = wf.getnframes()
        raw_bytes = wf.readframes(frames)

    if sampwidth == 2:
        shorts = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        if channels == 1:
            samples = shorts
        else:
            samples = shorts.reshape(-1, channels).mean(axis=1)
    elif sampwidth == 4:
        floats = np.frombuffer(raw_bytes, dtype=np.float32)
        if channels == 1:
            samples = floats
        else:
            samples = floats.reshape(-1, channels).mean(axis=1)
    else:
        samples = np.zeros(frames, dtype=np.float32)

    return sample_rate, samples


def _write_pcm16_wav(path: Path, samples: np.ndarray, sample_rate: int = 44100) -> None:
    """Write float ndarray (-1.0 to 1.0) as 16-bit mono PCM WAV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    clamped = np.clip(samples, -1.0, 1.0)
    int_samples = (clamped * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(int_samples.tobytes())


class AudioMixer(Op):
    """Overlay speech over background music with automatic dynamic ducking."""

    TITLE = "Podcast Audio Mixer & Ducker"
    CATEGORY = "Podcast / Mixing"
    CACHEABLE = True

    class Outputs(TypedDict):
        mixed_audio: AudioWav
        speech_duration_sec: float
        total_duration_sec: float

    def run(
        self,
        voiceover: AudioWav,
        bgm: AudioWav,
        speech_volume: Annotated[float, Range(0.0, 2.0)] = 1.0,
        bgm_volume: Annotated[float, Range(0.0, 1.0)] = 0.35,
        ducking_amount_db: Annotated[float, Range(0.0, 30.0)] = 14.0,
        lead_in_sec: Annotated[float, Range(0.0, 10.0)] = 1.0,
        tail_sec: Annotated[float, Range(0.0, 10.0)] = 2.0,
    ) -> Outputs:
        """Mix speech and background music with smooth ducking.

        Args:
            voiceover: Spoken voiceover WAV audio track.
            bgm: Background music WAV audio track.
            speech_volume: Volume multiplier for the voiceover track.
            bgm_volume: Baseline volume multiplier for the BGM track when speech is silent.
            ducking_amount_db: Amount in decibels to attenuate BGM while speech is active.
            lead_in_sec: Seconds of music before speech begins.
            tail_sec: Seconds of music after speech concludes.

        Returns:
            Dictionary containing `mixed_audio`, `speech_duration_sec`, and `total_duration_sec`.
        """
        sr_voice, voice_samples = _read_wav_to_float(Path(voiceover))
        sr_bgm, bgm_samples = _read_wav_to_float(Path(bgm))
        sample_rate = sr_voice

        # Resample BGM length if sample rates differ (simple interpolation if needed)
        if sr_bgm != sr_voice and len(bgm_samples) > 0:
            target_len = int(len(bgm_samples) * (sr_voice / float(sr_bgm)))
            indices = np.linspace(0, len(bgm_samples) - 1, target_len)
            bgm_samples = np.interp(indices, np.arange(len(bgm_samples)), bgm_samples)

        speech_duration = float(len(voice_samples)) / sample_rate
        lead_in_samples = int(lead_in_sec * sample_rate)
        tail_samples = int(tail_sec * sample_rate)
        total_samples = lead_in_samples + len(voice_samples) + tail_samples

        # Prepare BGM layer (loop or tile BGM if it is shorter than total_samples)
        if len(bgm_samples) == 0:
            bgm_track = np.zeros(total_samples, dtype=np.float32)
        else:
            repeats = int(np.ceil(total_samples / float(len(bgm_samples))))
            bgm_track = np.tile(bgm_samples, repeats)[:total_samples]

        # Prepare speech layer positioned after lead_in
        speech_track = np.zeros(total_samples, dtype=np.float32)
        speech_track[lead_in_samples:lead_in_samples + len(voice_samples)] = voice_samples * speech_volume

        # Compute speech activity envelope for ducking
        speech_abs = np.abs(speech_track)
        threshold = 0.015  # Speech presence energy threshold

        duck_gain = 10.0 ** (-ducking_amount_db / 20.0)
        target_gains = np.ones(total_samples, dtype=np.float32)

        speech_active_indices = np.where(speech_abs > threshold)[0]
        if len(speech_active_indices) > 0:
            # Hold speech activity with 150ms pre/post margin
            margin = int(0.15 * sample_rate)
            for idx in speech_active_indices:
                start_idx = max(0, idx - margin)
                end_idx = min(total_samples, idx + margin)
                target_gains[start_idx:end_idx] = duck_gain

        # Smooth gain curve with exponential moving average
        smoothed_gain = np.ones(total_samples, dtype=np.float32)
        current_g = 1.0
        alpha_attack = 0.005   # Fast ducking response (~25ms)
        alpha_release = 0.0005  # Smooth swell-up response (~200ms)

        for i in range(total_samples):
            tg = target_gains[i]
            if tg < current_g:
                current_g += (tg - current_g) * alpha_attack
            else:
                current_g += (tg - current_g) * alpha_release
            smoothed_gain[i] = current_g

        # Apply ducking gain to BGM
        ducked_bgm = bgm_track * (smoothed_gain * bgm_volume)

        # Final mix
        mixed = speech_track + ducked_bgm

        # Outro fade (last 1.5 seconds)
        fade_out_samples = min(total_samples, int(1.5 * sample_rate))
        if fade_out_samples > 0:
            mixed[-fade_out_samples:] *= np.linspace(1.0, 0.0, fade_out_samples)

        # Master brickwall limiter / normalization
        peak = float(np.max(np.abs(mixed)))
        if peak > 0.95:
            mixed = (mixed / peak) * 0.95

        out_path = Path("mixed_audio.wav")
        _write_pcm16_wav(out_path, mixed, sample_rate)

        total_duration = float(total_samples) / sample_rate
        return {
            "mixed_audio": out_path,
            "speech_duration_sec": round(speech_duration, 2),
            "total_duration_sec": round(total_duration, 2),
        }


__all__ = ["AudioMixer"]
