"""Score generation and acoustic physical-harmonic synthesizer for ``pedalboard_studio``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict

import numpy as np
from plynx_sdk import AudioWav, JsonFile, Op, Range

# J.S. Bach: Prelude I in C Major, BWV 846 (The Well-Tempered Clavier, Book 1)
# Authentic 35-measure harmonic chord structure.
# Each tuple defines the 5 voices from lowest to highest MIDI pitch: (bass, tenor, alto, soprano1, soprano2).
BWV_846_BARS: list[tuple[int, int, int, int, int]] = [
    (48, 52, 55, 60, 64),  # Bar 1:  C major
    (48, 50, 57, 62, 65),  # Bar 2:  Dm7 / C
    (47, 50, 55, 62, 65),  # Bar 3:  G7 / B
    (48, 52, 55, 60, 64),  # Bar 4:  C major
    (48, 52, 57, 64, 69),  # Bar 5:  Am / C
    (48, 50, 54, 57, 62),  # Bar 6:  D7 / C
    (47, 50, 55, 62, 67),  # Bar 7:  G / B
    (47, 48, 52, 55, 60),  # Bar 8:  C / B
    (45, 48, 52, 55, 60),  # Bar 9:  Am7
    (38, 45, 50, 54, 60),  # Bar 10: D7
    (43, 47, 50, 55, 59),  # Bar 11: G major
    (43, 46, 52, 55, 61),  # Bar 12: Edim7 / G
    (41, 45, 50, 57, 62),  # Bar 13: Dm / F
    (41, 44, 50, 53, 59),  # Bar 14: Bdim7 / F
    (40, 43, 48, 55, 60),  # Bar 15: C / E
    (40, 41, 45, 48, 53),  # Bar 16: F / E
    (38, 41, 45, 48, 53),  # Bar 17: Dm7
    (31, 38, 43, 47, 53),  # Bar 18: G7
    (36, 40, 43, 48, 52),  # Bar 19: C major
    (36, 43, 46, 48, 52),  # Bar 20: C7
    (29, 41, 45, 48, 52),  # Bar 21: Fmaj7
    (30, 36, 45, 48, 51),  # Bar 22: F#dim7
    (32, 41, 47, 48, 50),  # Bar 23: Abdim7
    (31, 41, 43, 47, 50),  # Bar 24: G7
    (31, 40, 43, 48, 52),  # Bar 25: C / G
    (31, 38, 43, 48, 53),  # Bar 26: Gsus4
    (31, 38, 43, 47, 53),  # Bar 27: G7
    (31, 39, 45, 48, 54),  # Bar 28: Adim7 / G
    (31, 40, 43, 48, 55),  # Bar 29: C / G
    (31, 38, 43, 48, 53),  # Bar 30: Gsus4
    (31, 38, 43, 47, 53),  # Bar 31: G7
    (24, 36, 43, 46, 52),  # Bar 32: C7 / C
    (24, 41, 45, 48, 53),  # Bar 33: F / C
    (24, 42, 48, 50, 57),  # Bar 34: D7 / C
    (24, 36, 48, 52, 55),  # Bar 35: Final C Major Chord resolution
]


class BachPreludeScore(Op):
    """Generate the musical score for J.S. Bach's Prelude I in C Major (BWV 846)."""

    TITLE = "Bach Prelude Score (BWV 846)"
    CATEGORY = "Audio / Score"
    CACHEABLE = True

    class Outputs(TypedDict):
        score: JsonFile

    def run(
        self,
        tempo_bpm: Annotated[int, Range(40, 160)] = 84,
        bars_count: Annotated[int, Range(1, 35)] = 35,
        dynamics: Literal["expressive", "flat", "crescendo"] = "expressive",
        octave_shift: Annotated[int, Range(-2, 2)] = 0,
    ) -> Outputs:
        sixteenth_sec = (60.0 / tempo_bpm) / 4.0
        selected_bars = BWV_846_BARS[:bars_count]
        notes: list[dict[str, Any]] = []

        # Arpeggiation order per half-measure: (1, 2, 3, 4, 5, 3, 4, 5)
        # Corresponding 0-based voice indices:
        pattern_indices = [0, 1, 2, 3, 4, 2, 3, 4]

        current_time = 0.0
        shift = octave_shift * 12

        for bar_idx, voices in enumerate(selected_bars):
            # Dynamic curve computation
            if dynamics == "expressive":
                # Subtle romantic arch peaking around bars 22-24
                progress = bar_idx / max(1, len(selected_bars) - 1)
                bar_vel = 0.65 + 0.25 * float(np.sin(progress * np.pi))
            elif dynamics == "crescendo":
                bar_vel = 0.5 + 0.4 * (bar_idx / max(1, len(selected_bars) - 1))
            else:
                bar_vel = 0.75

            # Bar 35 is the final held grand cadence
            is_final_bar = bar_idx == len(selected_bars) - 1 and len(selected_bars) == 35

            if is_final_bar:
                # In bar 35, all chord notes strike simultaneously and sustain
                chord_notes = [voices[0], voices[1], voices[2], voices[3], voices[4], 60 + shift, 64 + shift]
                for n in chord_notes:
                    pitch = n + shift
                    freq = 440.0 * (2.0 ** ((pitch - 69) / 12.0))
                    notes.append(
                        {
                            "pitch": pitch,
                            "freq": round(freq, 2),
                            "start_time": round(current_time, 4),
                            "duration": round(sixteenth_sec * 16.0, 4),
                            "velocity": round(bar_vel * 0.9, 2),
                            "voice": "cadence",
                        }
                    )
                current_time += sixteenth_sec * 16.0
                continue

            # Two identical 8-note arpeggio figures per measure
            for half in range(2):
                for step_idx, v_idx in enumerate(pattern_indices):
                    pitch = voices[v_idx] + shift
                    freq = 440.0 * (2.0 ** ((pitch - 69) / 12.0))

                    # Bass notes (voices 0 and 1) hold longer
                    if v_idx in (0, 1) and step_idx in (0, 1):
                        dur = sixteenth_sec * 8.0  # hold through half-bar
                        vel = bar_vel * (1.1 if v_idx == 0 else 0.95)
                    else:
                        dur = sixteenth_sec * 3.5  # sustained ringing pedal
                        # Accent soprano peak notes slightly
                        vel = bar_vel * (1.05 if v_idx == 4 else 0.9)

                    notes.append(
                        {
                            "pitch": pitch,
                            "freq": round(freq, 2),
                            "start_time": round(current_time, 4),
                            "duration": round(dur, 4),
                            "velocity": round(min(1.0, vel), 2),
                            "voice": f"v{v_idx}",
                        }
                    )
                    current_time += sixteenth_sec

        score_data = {
            "title": "Prelude I in C Major, BWV 846",
            "composer": "Johann Sebastian Bach",
            "tempo_bpm": tempo_bpm,
            "bars_count": len(selected_bars),
            "total_duration_sec": round(current_time, 3),
            "notes_count": len(notes),
            "notes": notes,
        }

        out_path = Path("score.json")
        out_path.write_text(json.dumps(score_data, indent=2), encoding="utf-8")
        return {"score": out_path}


class AcousticPianoSynth(Op):
    """Synthesize note events into an expressive stereo acoustic piano audio track."""

    TITLE = "Acoustic Piano Synthesizer"
    CATEGORY = "Audio / Synth"
    CACHEABLE = True

    class Outputs(TypedDict):
        audio: AudioWav

    def run(
        self,
        score: JsonFile,
        sample_rate: Annotated[int, Range(22050, 48000)] = 44100,
        brightness: Annotated[float, Range(0.2, 2.0)] = 1.0,
        sustain_resonance: Annotated[float, Range(0.1, 1.0)] = 0.7,
        stereo_width: Annotated[float, Range(0.0, 1.0)] = 0.6,
    ) -> Outputs:
        score_data = json.loads(score.read_text(encoding="utf-8"))
        notes: list[dict[str, Any]] = score_data.get("notes", [])
        total_dur = float(score_data.get("total_duration_sec", 10.0)) + 3.0  # +3s reverb/ring tail

        total_samples = int(total_dur * sample_rate)
        left = np.zeros(total_samples, dtype=np.float32)
        right = np.zeros(total_samples, dtype=np.float32)

        # Pre-compute harmonic weights and decay factors for realistic acoustic piano timbre
        harmonics = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
        base_weights = [1.0, 0.65 * brightness, 0.40 * brightness, 0.25 * (brightness**1.2), 0.15, 0.08, 0.04]

        for note in notes:
            start_s = int(note["start_time"] * sample_rate)
            dur_s = int(note["duration"] * sample_rate)
            end_s = min(total_samples, start_s + dur_s)
            if start_s >= total_samples or end_s <= start_s:
                continue

            n_samples = end_s - start_s
            t = np.arange(n_samples, dtype=np.float32) / sample_rate
            f0 = float(note["freq"])
            vel = float(note["velocity"])
            pitch = int(note["pitch"])

            # Keyboard panning: Bass on left (pan = 0.2), Treble on right (pan = 0.8)
            pan_norm = np.clip((pitch - 36) / 48.0, 0.0, 1.0)
            pan_l = 0.5 - 0.5 * stereo_width * (pan_norm * 2.0 - 1.0)
            pan_r = 1.0 - pan_l

            # Realistic acoustic piano string decay (lower notes ring longer)
            decay_rate = 1.8 * (f0 / 261.63) ** 0.35 / max(0.2, sustain_resonance)

            # Attack envelope (5ms felt hammer strike transient)
            attack_len = int(sample_rate * 0.005)
            env = np.exp(-t * decay_rate)
            if attack_len > 0 and n_samples > attack_len:
                env[:attack_len] *= np.linspace(0.0, 1.0, attack_len, dtype=np.float32)

            # Multi-harmonic string synthesis with subtle inharmonicity
            note_wave = np.zeros(n_samples, dtype=np.float32)
            inharmonicity = 0.0001
            for h_idx, (h_num, weight) in enumerate(zip(harmonics, base_weights)):
                h_freq = f0 * h_num * np.sqrt(1.0 + inharmonicity * (h_num**2))
                h_decay = np.exp(-t * (decay_rate * (1.0 + 0.3 * h_idx)))
                note_wave += float(weight) * np.sin(2.0 * np.pi * h_freq * t) * h_decay

            # Strike transient click
            click_len = min(n_samples, int(sample_rate * 0.008))
            if click_len > 0:
                click_t = t[:click_len]
                click = np.sin(2.0 * np.pi * 1800.0 * click_t) * np.exp(-click_t * 600.0) * 0.15
                note_wave[:click_len] += click

            gain = vel * 0.18
            note_wave *= env * gain

            left[start_s:end_s] += note_wave * pan_l
            right[start_s:end_s] += note_wave * pan_r

        # Soft peak limiter / normalization
        peak = max(float(np.max(np.abs(left))), float(np.max(np.abs(right))), 1e-6)
        if peak > 0.95:
            norm = 0.95 / peak
            left *= norm
            right *= norm

        audio_data = np.stack([left, right])
        out_path = Path("piano_track.wav")

        from pedalboard.io import AudioFile

        with AudioFile(str(out_path), "w", samplerate=sample_rate, num_channels=2) as f:
            f.write(audio_data)

        return {"audio": out_path}


__all__ = ["AcousticPianoSynth", "BachPreludeScore"]
