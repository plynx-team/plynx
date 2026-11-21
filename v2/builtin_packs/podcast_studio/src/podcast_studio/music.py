"""Procedural music and ambient background track synthesis in ``podcast_studio``."""

from __future__ import annotations

import math
import wave
from pathlib import Path
from typing import Annotated, Literal, TypedDict

import numpy as np
from plynx_sdk import AudioWav, Op, Range


def _write_pcm16_wav(path: Path, samples: np.ndarray, sample_rate: int = 44100) -> None:
    """Write normalized float ndarray (-1.0 to 1.0) as 16-bit mono PCM WAV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    clamped = np.clip(samples, -1.0, 1.0)
    int_samples = (clamped * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(int_samples.tobytes())


class BGMTrackGenerator(Op):
    """Synthesize a musical background track or ambient loop for podcasts."""

    TITLE = "BGM Track Generator"
    CATEGORY = "Audio / Synth & Voice"
    CACHEABLE = True

    class Outputs(TypedDict):
        bgm: AudioWav

    def run(
        self,
        mood: Literal["lofi_chill", "ambient_pad", "acoustic_piano", "cyber_pulse"] = "lofi_chill",
        duration_sec: Annotated[float, Range(3.0, 180.0)] = 20.0,
        tempo_bpm: Annotated[int, Range(50, 160)] = 85,
        volume: Annotated[float, Range(0.0, 1.0)] = 0.35,
    ) -> Outputs:
        """Synthesize BGM audio loop.

        Args:
            mood: Style of background music (lo-fi chill, ambient pad, piano, or cyber pulse).
            duration_sec: Total duration of the synthesized BGM track in seconds.
            tempo_bpm: Music tempo in beats per minute.
            volume: Master volume scaling factor (0.0 to 1.0).

        Returns:
            Dictionary containing the generated `bgm` AudioWav artifact.
        """
        sample_rate = 44100
        total_samples = int(sample_rate * duration_sec)
        t_arr = np.linspace(0.0, duration_sec, total_samples, endpoint=False)
        audio = np.zeros(total_samples, dtype=np.float32)

        beat_sec = 60.0 / float(tempo_bpm)

        if mood == "lofi_chill":
            # Dm9 -> G13 -> Cmaj9 -> A7alt progression
            chords = [
                [146.83, 174.61, 220.00, 261.63, 329.63],  # Dm9
                [98.00, 174.61, 246.94, 329.63, 392.00],   # G13
                [130.81, 164.81, 196.00, 246.94, 293.66],  # Cmaj9
                [110.00, 196.00, 277.18, 349.23, 440.00],  # A7alt
            ]
            chord_dur = beat_sec * 4.0  # 1 measure per chord
            for i, chord in enumerate(chords):
                chord_start = i * chord_dur
                while chord_start < duration_sec:
                    c_start_sample = int(chord_start * sample_rate)
                    c_end_sample = min(total_samples, int((chord_start + chord_dur) * sample_rate))
                    dur_samples = c_end_sample - c_start_sample
                    if dur_samples <= 0:
                        break
                    t_chord = np.linspace(0.0, dur_samples / sample_rate, dur_samples, endpoint=False)
                    chord_wave = np.zeros(dur_samples, dtype=np.float32)

                    # Electric Rhodes harmonics: fundamental + bell chime + warm octave
                    for freq in chord:
                        fund = np.sin(2.0 * np.pi * freq * t_chord)
                        bell = 0.25 * np.sin(2.0 * np.pi * (freq * 3.0) * t_chord) * np.exp(-6.0 * t_chord)
                        octave = 0.3 * np.sin(2.0 * np.pi * (freq * 0.5) * t_chord)
                        chord_wave += (fund + bell + octave) / len(chord)

                    # Smooth acoustic envelope with decay
                    env = np.exp(-1.4 * t_chord)
                    # Warm saturation
                    saturated = np.tanh(chord_wave * env * 1.5)
                    audio[c_start_sample:c_end_sample] += saturated
                    chord_start += len(chords) * chord_dur

            # Vinyl crackle texture layer
            crackle = (np.random.rand(total_samples) - 0.5) * 0.015
            audio += crackle

        elif mood == "ambient_pad":
            # Ethereal evolving fifths
            frequencies = [110.0, 164.81, 220.0, 277.18, 329.63]
            for idx, freq in enumerate(frequencies):
                lfo = 0.5 * np.sin(2.0 * np.pi * (0.15 + idx * 0.05) * t_arr)
                layer = np.sin(2.0 * np.pi * (freq + lfo) * t_arr)
                audio += layer / len(frequencies)

        elif mood == "acoustic_piano":
            notes = [130.81, 196.00, 261.63, 329.63, 392.00, 523.25]
            note_dur = beat_sec * 0.5
            note_samples = int(note_dur * sample_rate)
            for i in range(total_samples):
                note_idx = int(i / note_samples) % len(notes)
                freq = notes[note_idx]
                t_n = (i % note_samples) / float(sample_rate)
                val = math.sin(2.0 * math.pi * freq * t_n) + 0.3 * math.sin(4.0 * math.pi * freq * t_n)
                note_env = math.exp(-4.5 * t_n)
                audio[i] += val * note_env

        else:  # cyber_pulse
            bass_seq = [55.0, 55.0, 65.41, 73.42]
            step_dur = beat_sec * 0.5
            step_samples = int(step_dur * sample_rate)
            for i in range(total_samples):
                step_idx = int(i / step_samples) % len(bass_seq)
                freq = bass_seq[step_idx]
                t_n = (i % step_samples) / float(sample_rate)
                phase = (freq * t_n) % 1.0
                square = 0.8 if phase < 0.5 else -0.8
                pulse_env = math.exp(-3.0 * t_n)
                audio[i] += square * pulse_env

        # Master intro/outro fade (0.5s in, 1.5s out)
        fade_in_samples = min(total_samples // 2, int(0.5 * sample_rate))
        fade_out_samples = min(total_samples // 2, int(1.5 * sample_rate))
        if fade_in_samples > 0:
            audio[:fade_in_samples] *= np.linspace(0.0, 1.0, fade_in_samples)
        if fade_out_samples > 0:
            audio[-fade_out_samples:] *= np.linspace(1.0, 0.0, fade_out_samples)

        # Normalize and scale by volume
        peak = float(np.max(np.abs(audio)))
        if peak > 0.001:
            audio = (audio / peak) * volume

        out_path = Path("bgm.wav")
        _write_pcm16_wav(out_path, audio, sample_rate)
        return {"bgm": out_path}


__all__ = ["BGMTrackGenerator"]
