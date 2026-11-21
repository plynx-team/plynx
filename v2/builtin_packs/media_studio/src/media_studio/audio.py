"""Generative audio operations in ``media_studio``."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path
from typing import Annotated, Literal, TypedDict

from plynx_sdk import AudioWav, Op, Range


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
            int_sample = int(clamped * 32767.0)
            raw_bytes.extend(struct.pack("<h", int_sample))
        wf.writeframes(bytes(raw_bytes))


def _read_pcm16_wav(path: Path) -> tuple[int, list[float]]:
    """Read a 16-bit mono or stereo WAV file into normalized float samples."""
    with wave.open(str(path), "rb") as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        rate = wf.getframerate()
        frames_count = wf.getnframes()
        raw_data = wf.readframes(frames_count)

    samples: list[float] = []
    if sampwidth == 2:
        count = len(raw_data) // 2
        shorts = struct.unpack(f"<{count}h", raw_data)
        if channels == 1:
            samples = [s / 32767.0 for s in shorts]
        else:
            # Average stereo channels to mono
            samples = [(shorts[i] + shorts[i + 1]) / (2.0 * 32767.0) for i in range(0, len(shorts) - 1, channels)]
    else:
        # Fallback for 8-bit or unhandled: zero pad
        samples = [0.0] * frames_count
    return rate, samples


class ToneSynth(Op):
    """Synthesize a musical tone with selectable waveform and frequency."""

    TITLE = "Synthesize Tone"
    CATEGORY = "Audio / Synth"
    CACHEABLE = True

    class Outputs(TypedDict):
        audio: AudioWav

    def run(
        self,
        waveform: Literal["sine", "sawtooth", "square", "triangle"] = "sine",
        frequency: Annotated[int, Range(40, 2000)] = 440,
        duration_sec: Annotated[float, Range(0.5, 30.0)] = 3.0,
        volume: Annotated[float, Range(0.0, 1.0)] = 0.5,
    ) -> Outputs:
        sample_rate = 44100
        total_samples = int(sample_rate * duration_sec)
        samples: list[float] = []
        fade_len = int(sample_rate * 0.02)  # 20ms anti-click fade

        for i in range(total_samples):
            t = i / sample_rate
            phase = (frequency * t) % 1.0

            if waveform == "sine":
                val = math.sin(2.0 * math.pi * frequency * t)
            elif waveform == "sawtooth":
                val = 2.0 * phase - 1.0
            elif waveform == "square":
                val = 1.0 if phase < 0.5 else -1.0
            elif waveform == "triangle":
                val = 4.0 * abs(phase - 0.5) - 1.0
            else:
                val = math.sin(2.0 * math.pi * frequency * t)

            # Apply volume and fade envelope
            env = 1.0
            if i < fade_len:
                env = i / fade_len
            elif i > total_samples - fade_len:
                env = (total_samples - i) / fade_len

            samples.append(val * volume * env)

        out_path = Path("tone.wav")
        _write_pcm16_wav(out_path, samples, sample_rate)
        return {"audio": out_path}


class ChordProgression(Op):
    """Synthesize a musical chord progression or ambient harmonic drone."""

    TITLE = "Chords & Melodies"
    CATEGORY = "Audio / Synth"
    CACHEABLE = True

    class Outputs(TypedDict):
        audio: AudioWav

    def run(
        self,
        progression: Literal["pop_chords", "ambient_drone", "arpeggio", "bassline"] = "pop_chords",
        tempo_bpm: Annotated[int, Range(60, 240)] = 120,
        duration_sec: Annotated[float, Range(1.0, 30.0)] = 6.0,
        volume: Annotated[float, Range(0.0, 1.0)] = 0.5,
    ) -> Outputs:
        sample_rate = 44100
        total_samples = int(sample_rate * duration_sec)
        samples = [0.0] * total_samples

        if progression == "pop_chords":
            # I - V - vi - IV progression (C, G, Am, F)
            chords = [
                [261.63, 329.63, 392.00],  # C major
                [196.00, 246.94, 293.66],  # G major
                [220.00, 261.63, 329.63],  # A minor
                [174.61, 220.00, 261.63],  # F major
            ]
            beat_sec = 60.0 / tempo_bpm
            chord_dur = beat_sec * 2.0
            for ci, chord in enumerate(chords):
                start_s = int(ci * chord_dur * sample_rate)
                end_s = min(total_samples, int((ci + 1) * chord_dur * sample_rate))
                for i in range(start_s, end_s):
                    t = (i - start_s) / sample_rate
                    val = 0.0
                    for freq in chord:
                        val += math.sin(2.0 * math.pi * freq * t)
                    val /= len(chord)
                    # Envelope
                    env = math.exp(-1.5 * t)
                    samples[i] += val * env * volume

        elif progression == "ambient_drone":
            # Rich ethereal harmonic pad: 110Hz root, 165Hz fifth, 220Hz octave, 277.18Hz major third
            freqs = [110.0, 164.81, 220.0, 277.18]
            for i in range(total_samples):
                t = i / sample_rate
                val = 0.0
                for idx, f in enumerate(freqs):
                    # Slight chorusing / lfo detune
                    detune = math.sin(t * (0.2 + idx * 0.1)) * 0.7
                    val += math.sin(2.0 * math.pi * (f + detune) * t)
                val /= len(freqs)
                fade = min(1.0, i / (sample_rate * 0.5)) * min(1.0, (total_samples - i) / (sample_rate * 0.5))
                samples[i] = val * volume * fade

        elif progression == "arpeggio":
            notes = [261.63, 329.63, 392.00, 523.25, 392.00, 329.63]
            note_dur = 60.0 / (tempo_bpm * 2.0)
            note_len = int(note_dur * sample_rate)
            for i in range(total_samples):
                note_idx = int(i / note_len) % len(notes)
                freq = notes[note_idx]
                t_note = (i % note_len) / sample_rate
                val = math.sin(2.0 * math.pi * freq * t_note)
                env = math.exp(-4.0 * t_note)
                samples[i] = val * env * volume

        else:  # bassline
            bass_notes = [55.0, 55.0, 65.41, 73.42]
            note_dur = 60.0 / tempo_bpm
            note_len = int(note_dur * sample_rate)
            for i in range(total_samples):
                note_idx = int(i / note_len) % len(bass_notes)
                freq = bass_notes[note_idx]
                t_note = (i % note_len) / sample_rate
                # Warm sawtooth-like square
                phase = (freq * t_note) % 1.0
                val = (1.0 if phase < 0.5 else -1.0) * 0.7 + math.sin(2.0 * math.pi * freq * t_note) * 0.3
                env = math.exp(-2.5 * t_note)
                samples[i] = val * env * volume

        out_path = Path("progression.wav")
        _write_pcm16_wav(out_path, samples, sample_rate)
        return {"audio": out_path}


class AudioEchoFilter(Op):
    """Apply delay, echo, and decay reverberation to an input audio track."""

    TITLE = "Audio Echo & Reverb"
    CATEGORY = "Audio / Effects"
    CACHEABLE = True

    class Outputs(TypedDict):
        filtered_audio: AudioWav

    def run(
        self,
        audio: AudioWav,
        delay_ms: Annotated[int, Range(50, 800)] = 200,
        decay: Annotated[float, Range(0.1, 0.9)] = 0.4,
        repeats: Annotated[int, Range(1, 6)] = 3,
    ) -> Outputs:
        sample_rate, samples = _read_pcm16_wav(audio)
        delay_samples = int(sample_rate * (delay_ms / 1000.0))
        extra_len = delay_samples * repeats
        out_samples = list(samples) + [0.0] * extra_len

        for r in range(1, repeats + 1):
            offset = delay_samples * r
            gain = decay**r
            for i in range(len(samples)):
                out_samples[i + offset] += samples[i] * gain

        # Normalize to prevent clipping
        peak = max(abs(s) for s in out_samples) if out_samples else 1.0
        if peak > 1.0:
            out_samples = [s / peak for s in out_samples]

        out_path = Path("echo.wav")
        _write_pcm16_wav(out_path, out_samples, sample_rate)
        return {"filtered_audio": out_path}


__all__ = ["AudioEchoFilter", "ChordProgression", "ToneSynth"]
