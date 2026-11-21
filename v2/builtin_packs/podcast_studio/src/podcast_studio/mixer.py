"""Audio mixing and automatic voice ducking operation in ``podcast_studio``."""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Annotated, TypedDict

import numpy as np
from plynx_sdk import AudioWav, Op, Range


def _read_wav_to_float(path: Path) -> tuple[int, np.ndarray]:
    """Read a mono or stereo WAV file into normalized float32 ndarray of shape (channels, samples).

    Supports 16-bit, 24-bit, and 32-bit PCM/float WAV files.
    """
    with wave.open(str(path), "rb") as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        sample_rate = wf.getframerate()
        frames = wf.getnframes()
        raw_bytes = wf.readframes(frames)

    if sampwidth == 2:
        shorts = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        samples = shorts.reshape(-1, channels).T
    elif sampwidth == 3:
        # 24-bit PCM
        total_samples = len(raw_bytes) // 3
        # Fast decode 24-bit
        int_array = np.zeros(total_samples, dtype=np.int32)
        raw_np = np.frombuffer(raw_bytes, dtype=np.uint8)
        int_array = (
            raw_np[0::3].astype(np.int32)
            | (raw_np[1::3].astype(np.int32) << 8)
            | (raw_np[2::3].astype(np.int32) << 16)
        )
        # Sign extend 24-bit to 32-bit
        int_array[int_array >= 0x800000] -= 0x1000000
        samples = (int_array.astype(np.float32) / 8388608.0).reshape(-1, channels).T
    elif sampwidth == 4:
        # Try float32 first
        floats = np.frombuffer(raw_bytes, dtype=np.float32)
        if len(floats) > 0 and np.max(np.abs(floats[:1000])) <= 1.5:
            samples = floats.reshape(-1, channels).T
        else:
            ints = np.frombuffer(raw_bytes, dtype=np.int32).astype(np.float32) / 2147483648.0
            samples = ints.reshape(-1, channels).T
    else:
        samples = np.zeros((channels, frames), dtype=np.float32)

    return sample_rate, samples


def _write_pcm16_wav(path: Path, samples: np.ndarray, sample_rate: int = 44100) -> None:
    """Write float ndarray of shape (samples,) or (channels, samples) as 16-bit PCM WAV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if samples.ndim == 1:
        channels = 1
        clamped = np.clip(samples, -1.0, 1.0)
        int_samples = (clamped * 32767.0).astype(np.int16)
        payload = int_samples.tobytes()
    else:
        channels = samples.shape[0]
        clamped = np.clip(samples, -1.0, 1.0)
        int_samples = (clamped * 32767.0).astype(np.int16)
        # Interleave channels: shape (samples, channels)
        payload = int_samples.T.tobytes()

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(payload)


class AudioMixer(Op):
    """Overlay speech over background music with automatic dynamic ducking."""

    TITLE = "Podcast Audio Mixer & Ducker"
    CATEGORY = "Audio / Effects & Mixing"
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

        # Check stereo status: if either input is 2-channel stereo, produce 2-channel stereo
        out_channels = max(voice_samples.shape[0], bgm_samples.shape[0])
        if voice_samples.shape[0] < out_channels:
            voice_samples = np.repeat(voice_samples, out_channels, axis=0)
        if bgm_samples.shape[0] < out_channels:
            bgm_samples = np.repeat(bgm_samples, out_channels, axis=0)

        # Resample BGM length if sample rates differ (simple interpolation if needed)
        if sr_bgm != sr_voice and bgm_samples.shape[1] > 0:
            target_len = int(bgm_samples.shape[1] * (sr_voice / float(sr_bgm)))
            indices = np.linspace(0, bgm_samples.shape[1] - 1, target_len)
            resampled_bgm = np.zeros((out_channels, target_len), dtype=np.float32)
            for ch in range(out_channels):
                resampled_bgm[ch] = np.interp(indices, np.arange(bgm_samples.shape[1]), bgm_samples[ch])
            bgm_samples = resampled_bgm

        n_voice_frames = voice_samples.shape[1]
        speech_duration = float(n_voice_frames) / sample_rate
        lead_in_samples = int(lead_in_sec * sample_rate)
        tail_samples = int(tail_sec * sample_rate)
        total_samples = lead_in_samples + n_voice_frames + tail_samples

        # Prepare BGM layer (loop or tile BGM if it is shorter than total_samples)
        if bgm_samples.shape[1] == 0:
            bgm_track = np.zeros((out_channels, total_samples), dtype=np.float32)
        else:
            repeats = int(np.ceil(total_samples / float(bgm_samples.shape[1])))
            bgm_track = np.tile(bgm_samples, (1, repeats))[:, :total_samples]

        # Prepare speech layer positioned after lead_in
        speech_track = np.zeros((out_channels, total_samples), dtype=np.float32)
        speech_track[:, lead_in_samples:lead_in_samples + n_voice_frames] = voice_samples * speech_volume

        # Compute speech activity envelope across channels for ducking
        speech_abs = np.max(np.abs(speech_track), axis=0)
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
            fade_curve = np.linspace(1.0, 0.0, fade_out_samples, dtype=np.float32)
            mixed[:, -fade_out_samples:] *= fade_curve

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
