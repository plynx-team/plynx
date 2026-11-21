"""Score generation and MIDI-driven synthesizers for ``pedalboard_studio``.

All synthesizers consume a canonical ``MidiFile`` (``audio/midi``) and output stereo
16-bit PCM ``AudioWav`` (``audio/wav``), enabling seamless composition across all
score generators, effects, and mixers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict

import numpy as np
from pedalboard.io import AudioFile
from plynx_sdk import AudioWav, JsonFile, MidiFile, Op, Range
from scipy.signal import lfilter  # type: ignore[import-untyped]

from pedalboard_studio.midi_io import (
    DRUM_CHANNEL,
    MidiNote,
    MidiScore,
    midi_pitch_to_freq,
    read_midi,
    write_midi,
)

# J.S. Bach: Prelude I in C Major, BWV 846 (The Well-Tempered Clavier, Book 1)
# Authentic 35-measure harmonic chord structure.
# Each tuple defines 5 voices from lowest to highest MIDI pitch: (bass, tenor, alto, s1, s2).
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


def _write_stereo_wav(path: Path, left: np.ndarray, right: np.ndarray, sample_rate: int) -> Path:
    """Normalize stereo channels safely and write 16-bit PCM WAV via Pedalboard."""
    peak = max(float(np.max(np.abs(left))), float(np.max(np.abs(right))), 1e-6)
    if peak > 0.95:
        norm = 0.95 / peak
        left = left * norm
        right = right * norm
    audio_data = np.stack([left.astype(np.float32), right.astype(np.float32)])
    path.parent.mkdir(parents=True, exist_ok=True)
    with AudioFile(str(path), "w", samplerate=sample_rate, num_channels=2) as f:
        f.write(audio_data)
    return path


class BachPreludeScore(Op):
    """Generate the Standard MIDI score for J.S. Bach's Prelude I in C Major (BWV 846).

    Produces an authentic 35-measure arpeggiated MIDI score with expressive dynamics,
    alongside a JSON metadata summary. Wire ``midi`` into ``AcousticPianoSynth``,
    ``PolySynth``, or ``MidiPianoRoll``.
    """

    TITLE = "Bach Prelude Score (BWV 846)"
    CATEGORY = "Audio / Score"
    CACHEABLE = True

    class Outputs(TypedDict):
        midi: MidiFile
        metadata: JsonFile

    def run(
        self,
        tempo_bpm: Annotated[int, Range(40, 160)] = 84,
        bars_count: Annotated[int, Range(1, 35)] = 35,
        dynamics: Literal["expressive", "flat", "crescendo"] = "expressive",
        octave_shift: Annotated[int, Range(-2, 2)] = 0,
    ) -> Outputs:
        """Generate Bach's BWV 846 Prelude I as a Standard MIDI File.

        Args:
            tempo_bpm: Playback tempo in beats per minute.
            bars_count: Number of measures to generate (1 to 35).
            dynamics: Velocity phrasing curve ('expressive', 'flat', or 'crescendo').
            octave_shift: Transpose the score up or down by whole octaves.

        Returns:
            Dictionary containing `midi` (MidiFile) and `metadata` (JsonFile).
        """
        sixteenth_sec = (60.0 / tempo_bpm) / 4.0
        selected_bars = BWV_846_BARS[:bars_count]
        midi_notes: list[MidiNote] = []

        # Arpeggiation order per half-measure: (1, 2, 3, 4, 5, 3, 4, 5)
        pattern_indices = [0, 1, 2, 3, 4, 2, 3, 4]

        current_time = 0.0
        shift = octave_shift * 12

        for bar_idx, voices in enumerate(selected_bars):
            if dynamics == "expressive":
                progress = bar_idx / max(1, len(selected_bars) - 1)
                bar_vel = 0.65 + 0.25 * float(np.sin(progress * np.pi))
            elif dynamics == "crescendo":
                bar_vel = 0.5 + 0.4 * (bar_idx / max(1, len(selected_bars) - 1))
            else:
                bar_vel = 0.75

            is_final_bar = bar_idx == len(selected_bars) - 1 and len(selected_bars) == 35

            if is_final_bar:
                chord_notes = [voices[0], voices[1], voices[2], voices[3], voices[4], 60, 64]
                for base_pitch in chord_notes:
                    pitch = max(0, min(127, base_pitch + shift))
                    vel_int = max(1, min(127, round(bar_vel * 0.9 * 127)))
                    midi_notes.append(
                        MidiNote(
                            pitch=pitch,
                            start_sec=current_time,
                            duration_sec=sixteenth_sec * 16.0,
                            velocity=vel_int,
                            channel=0,
                        )
                    )
                current_time += sixteenth_sec * 16.0
                continue

            for _half in range(2):
                for step_idx, v_idx in enumerate(pattern_indices):
                    pitch = max(0, min(127, voices[v_idx] + shift))
                    if v_idx in (0, 1) and step_idx in (0, 1):
                        dur = sixteenth_sec * 8.0
                        vel = bar_vel * (1.1 if v_idx == 0 else 0.95)
                    else:
                        dur = sixteenth_sec * 3.5
                        vel = bar_vel * (1.05 if v_idx == 4 else 0.9)

                    vel_int = max(1, min(127, round(min(1.0, vel) * 127)))
                    midi_notes.append(
                        MidiNote(
                            pitch=pitch,
                            start_sec=current_time,
                            duration_sec=dur,
                            velocity=vel_int,
                            channel=0,
                        )
                    )
                    current_time += sixteenth_sec

        midi_score = MidiScore(
            notes=midi_notes,
            tempo_bpm=float(tempo_bpm),
            title="Prelude I in C Major, BWV 846",
        )
        midi_path = Path("bach_bwv_846.mid")
        write_midi(midi_path, midi_score)

        metadata: dict[str, Any] = {
            "title": "Prelude I in C Major, BWV 846",
            "composer": "Johann Sebastian Bach",
            "tempo_bpm": tempo_bpm,
            "bars_count": len(selected_bars),
            "total_duration_sec": round(current_time, 3),
            "notes_count": len(midi_notes),
        }
        meta_path = Path("score_metadata.json")
        meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return {"midi": midi_path, "metadata": meta_path}


class AcousticPianoSynth(Op):
    """Synthesize a MIDI score into an expressive stereo acoustic grand piano track.

    Uses multi-harmonic additive string modeling with subtle inharmonicity, felt hammer
    strike transients, and realistic keyboard stereo panning. Automatically ignores
    Channel 9 (percussion) so multi-channel MIDI scores render cleanly.
    """

    TITLE = "Acoustic Piano Synthesizer"
    CATEGORY = "Audio / Synth & Voice"
    CACHEABLE = True

    class Outputs(TypedDict):
        audio: AudioWav

    def run(
        self,
        midi: MidiFile,
        sample_rate: Annotated[int, Range(22050, 48000)] = 44100,
        brightness: Annotated[float, Range(0.2, 2.0)] = 1.0,
        sustain_resonance: Annotated[float, Range(0.1, 1.0)] = 0.7,
        stereo_width: Annotated[float, Range(0.0, 1.0)] = 0.6,
    ) -> Outputs:
        """Render melodic MIDI notes as a stereo concert grand piano WAV.

        Args:
            midi: Input Standard MIDI File.
            sample_rate: Output audio sample rate in Hz.
            brightness: Upper harmonic emphasis (higher = brighter concert grand).
            sustain_resonance: String sustain length factor.
            stereo_width: Stereo spread from bass (left) to treble (right).

        Returns:
            Dictionary containing stereo 16-bit PCM `audio`.
        """
        score = read_midi(Path(midi))
        melodic_notes = [n for n in score.notes if n.channel != DRUM_CHANNEL]
        total_dur = max(1.0, score.duration_sec) + 2.5

        total_samples = int(total_dur * sample_rate)
        left = np.zeros(total_samples, dtype=np.float32)
        right = np.zeros(total_samples, dtype=np.float32)

        harmonics = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
        base_weights = [
            1.0,
            0.65 * brightness,
            0.40 * brightness,
            0.25 * (brightness**1.2),
            0.15,
            0.08,
            0.04,
        ]

        for note in melodic_notes:
            start_s = int(note.start_sec * sample_rate)
            dur_s = int((note.duration_sec + 0.6) * sample_rate)
            end_s = min(total_samples, start_s + dur_s)
            if start_s >= total_samples or end_s <= start_s:
                continue

            n_samples = end_s - start_s
            t = np.arange(n_samples, dtype=np.float32) / sample_rate
            f0 = midi_pitch_to_freq(note.pitch)
            vel = note.velocity / 127.0

            pan_norm = float(np.clip((note.pitch - 36) / 48.0, 0.0, 1.0))
            pan_l = 0.5 - 0.5 * stereo_width * (pan_norm * 2.0 - 1.0)
            pan_r = 1.0 - pan_l

            decay_rate = 1.8 * (f0 / 261.63) ** 0.35 / max(0.2, sustain_resonance)

            attack_len = int(sample_rate * 0.005)
            env = np.exp(-t * decay_rate)
            if attack_len > 0 and n_samples > attack_len:
                env[:attack_len] *= np.linspace(0.0, 1.0, attack_len, dtype=np.float32)

            note_wave = np.zeros(n_samples, dtype=np.float32)
            inharmonicity = 0.0001
            for h_idx, (h_num, weight) in enumerate(zip(harmonics, base_weights, strict=True)):
                h_freq = f0 * h_num * float(np.sqrt(1.0 + inharmonicity * (h_num**2)))
                h_decay = np.exp(-t * (decay_rate * (1.0 + 0.3 * h_idx)))
                note_wave += float(weight) * np.sin(2.0 * np.pi * h_freq * t) * h_decay

            click_len = min(n_samples, int(sample_rate * 0.008))
            if click_len > 0:
                click_t = t[:click_len]
                click = np.sin(2.0 * np.pi * 1800.0 * click_t) * np.exp(-click_t * 600.0) * 0.15
                note_wave[:click_len] += click

            gain = vel * 0.18
            note_wave *= env * gain

            left[start_s:end_s] += note_wave * pan_l
            right[start_s:end_s] += note_wave * pan_r

        out_path = _write_stereo_wav(Path("piano_track.wav"), left, right, sample_rate)
        return {"audio": out_path}


def _one_pole_lowpass(signal: np.ndarray, cutoff_hz: float, sample_rate: int) -> np.ndarray:
    """Apply a fast vectorized single-pole low-pass filter using scipy.signal.lfilter."""
    rc = 1.0 / (2.0 * np.pi * max(40.0, min(cutoff_hz, sample_rate * 0.45)))
    dt = 1.0 / float(sample_rate)
    alpha = float(dt / (rc + dt))
    filtered = lfilter([alpha], [1.0, -(1.0 - alpha)], signal)
    return np.asarray(filtered, dtype=np.float32)


class PolySynth(Op):
    """Polyphonic analog-inspired synthesizer converting any MIDI score into stereo audio.

    Supports lush detuned pads, bright analog saws, plucks, warm Rhodes electric piano,
    and retro square leads with ADSR amplitude shaping and low-pass filtering.
    Automatically skips Channel 9 (percussion) so multi-channel MIDI scores compose cleanly.
    """

    TITLE = "Polyphonic Synthesizer"
    CATEGORY = "Audio / Synth & Voice"
    CACHEABLE = True

    class Outputs(TypedDict):
        audio: AudioWav

    def run(
        self,
        midi: MidiFile,
        waveform: Literal["pad", "saw", "pluck", "rhodes", "square"] = "pad",
        sample_rate: Annotated[int, Range(22050, 48000)] = 44100,
        attack_ms: Annotated[float, Range(2.0, 500.0)] = 35.0,
        release_ms: Annotated[float, Range(20.0, 2000.0)] = 350.0,
        cutoff_hz: Annotated[float, Range(200.0, 16000.0)] = 2800.0,
        stereo_width: Annotated[float, Range(0.0, 1.0)] = 0.65,
    ) -> Outputs:
        """Synthesize melodic MIDI notes with an analog polyphonic voice engine.

        Args:
            midi: Input Standard MIDI File.
            waveform: Oscillator voice style ('pad', 'saw', 'pluck', 'rhodes', 'square').
            sample_rate: Output sample rate in Hz.
            attack_ms: Envelope attack time in milliseconds.
            release_ms: Envelope release tail in milliseconds.
            cutoff_hz: Low-pass filter cutoff frequency in Hz.
            stereo_width: Stereo detune and panning width (0.0 mono to 1.0 wide).

        Returns:
            Dictionary containing stereo 16-bit PCM `audio`.
        """
        score = read_midi(Path(midi))
        melodic_notes = [n for n in score.notes if n.channel != DRUM_CHANNEL]
        release_sec = release_ms / 1000.0
        total_dur = max(1.0, score.duration_sec) + release_sec + 0.5
        total_samples = int(total_dur * sample_rate)

        left = np.zeros(total_samples, dtype=np.float32)
        right = np.zeros(total_samples, dtype=np.float32)

        for note in melodic_notes:
            start_s = int(note.start_sec * sample_rate)
            note_samples = max(1, int(note.duration_sec * sample_rate))
            rel_samples = max(1, int(release_sec * sample_rate))
            total_note_s = note_samples + rel_samples
            end_s = min(total_samples, start_s + total_note_s)
            if start_s >= total_samples or end_s <= start_s:
                continue

            n_len = end_s - start_s
            t = np.arange(n_len, dtype=np.float32) / sample_rate
            f0 = midi_pitch_to_freq(note.pitch)
            vel = note.velocity / 127.0

            # Generate waveform
            if waveform == "saw":
                phase_a = (f0 * t) % 1.0
                phase_b = (f0 * 1.004 * t) % 1.0
                wave_l = (2.0 * phase_a - 1.0).astype(np.float32)
                wave_r = (2.0 * phase_b - 1.0).astype(np.float32)
            elif waveform == "pad":
                # Warm 3-voice detuned chorus saw/sine blend
                p1 = (f0 * 0.996 * t) % 1.0
                p2 = (f0 * 1.004 * t) % 1.0
                sub = np.sin(2.0 * np.pi * f0 * t)
                wave_l = (0.5 * (2.0 * p1 - 1.0) + 0.5 * sub).astype(np.float32)
                wave_r = (0.5 * (2.0 * p2 - 1.0) + 0.5 * sub).astype(np.float32)
            elif waveform == "pluck":
                phase = (f0 * t) % 1.0
                raw = (2.0 * phase - 1.0) * np.exp(-t * 5.5)
                wave_l = raw.astype(np.float32)
                wave_r = raw.astype(np.float32)
            elif waveform == "rhodes":
                # Warm bell-like electric piano (fundamental + harmonics + subtle tremolo)
                trem = 1.0 + 0.08 * np.sin(2.0 * np.pi * 4.2 * t)
                body = (
                    np.sin(2.0 * np.pi * f0 * t) * np.exp(-t * 1.4)
                    + 0.35 * np.sin(2.0 * np.pi * f0 * 2.0 * t) * np.exp(-t * 2.8)
                    + 0.18 * np.sin(2.0 * np.pi * f0 * 3.0 * t) * np.exp(-t * 6.5)
                ) * trem
                wave_l = body.astype(np.float32)
                wave_r = body.astype(np.float32)
            else:
                # square
                wave_l = np.sign(np.sin(2.0 * np.pi * f0 * t)).astype(np.float32)
                wave_r = np.sign(np.sin(2.0 * np.pi * f0 * 1.003 * t)).astype(np.float32)

            # ADSR envelope
            env = np.ones(n_len, dtype=np.float32)
            atk_s = min(n_len, max(1, int((attack_ms / 1000.0) * sample_rate)))
            env[:atk_s] = np.linspace(0.0, 1.0, atk_s, dtype=np.float32)
            if note_samples < n_len:
                rel_len = n_len - note_samples
                env[note_samples:] = np.linspace(1.0, 0.0, rel_len, dtype=np.float32)

            # Stereo panning based on pitch
            pan_norm = float(np.clip((note.pitch - 36) / 48.0, 0.0, 1.0))
            pan_l = 0.5 - 0.5 * stereo_width * (pan_norm * 2.0 - 1.0)
            pan_r = 1.0 - pan_l

            gain = vel * 0.22
            left[start_s:end_s] += wave_l * env * gain * pan_l
            right[start_s:end_s] += wave_r * env * gain * pan_r

        # Apply master low-pass filter
        left = _one_pole_lowpass(left, cutoff_hz, sample_rate)
        right = _one_pole_lowpass(right, cutoff_hz, sample_rate)

        out_path = _write_stereo_wav(Path(f"polysynth_{waveform}.wav"), left, right, sample_rate)
        return {"audio": out_path}


class DrumSynth(Op):
    """Synthesize General MIDI Channel 9 percussion notes into a stereo drum track.

    Synthesizes kick (35/36), rim (37), snare (38/40), hand clap (39), closed/open
    hi-hats (42/44/46), toms (41-50), and cymbals (49/51) directly from a ``MidiFile``.
    Wire ``StepSequencer`` or ``MidiMerge`` directly into this op.
    """

    TITLE = "Drum Machine Synthesizer"
    CATEGORY = "Audio / Synth & Voice"
    CACHEABLE = True

    class Outputs(TypedDict):
        audio: AudioWav

    def run(
        self,
        midi: MidiFile,
        kit: Literal["electronic_808", "acoustic", "lofi"] = "electronic_808",
        sample_rate: Annotated[int, Range(22050, 48000)] = 44100,
        punch: Annotated[float, Range(0.2, 2.0)] = 1.0,
        stereo_width: Annotated[float, Range(0.0, 1.0)] = 0.5,
    ) -> Outputs:
        """Synthesize Channel 9 MIDI percussion notes into a stereo WAV drum track.

        Args:
            midi: Input Standard MIDI File (reads Channel 9 percussion notes).
            kit: Drum timbre kit ('electronic_808', 'acoustic', or 'lofi').
            sample_rate: Output audio sample rate in Hz.
            punch: Transient and drive multiplier.
            stereo_width: Stereo panning spread for hats, claps, and toms.

        Returns:
            Dictionary containing stereo 16-bit PCM `audio`.
        """
        score = read_midi(Path(midi))
        drum_notes = [n for n in score.notes if n.channel == DRUM_CHANNEL]
        total_dur = max(1.0, score.duration_sec) + 1.0
        total_samples = int(total_dur * sample_rate)

        left = np.zeros(total_samples, dtype=np.float32)
        right = np.zeros(total_samples, dtype=np.float32)
        rng = np.random.default_rng(seed=42)

        for note in drum_notes:
            start_s = int(note.start_sec * sample_rate)
            if start_s >= total_samples:
                continue
            vel = (note.velocity / 127.0) * punch
            pitch = note.pitch

            pan = 0.5  # center default
            hit: np.ndarray
            if pitch in (35, 36):
                # Kick drum: pitch-swept sine + sub body + click
                dur = 0.45 if kit == "electronic_808" else 0.28
                n_s = min(total_samples - start_s, int(dur * sample_rate))
                t = np.arange(n_s, dtype=np.float32) / sample_rate
                f_start = 155.0 if kit == "electronic_808" else 130.0
                f_end = 44.0 if kit == "electronic_808" else 52.0
                freq_env = f_end + (f_start - f_end) * np.exp(-t * 32.0)
                phase = 2.0 * np.pi * np.cumsum(freq_env) / sample_rate
                decay = 5.5 if kit == "electronic_808" else 11.0
                sig = np.sin(phase) * np.exp(-t * decay)
                click = np.sin(2.0 * np.pi * 1200.0 * t) * np.exp(-t * 220.0) * 0.25
                hit = (sig + click) * vel * 0.85

            elif pitch in (38, 40):
                # Snare drum: tonal body + crisp filtered noise
                dur = 0.24
                n_s = min(total_samples - start_s, int(dur * sample_rate))
                t = np.arange(n_s, dtype=np.float32) / sample_rate
                body = np.sin(2.0 * np.pi * 185.0 * t) * np.exp(-t * 24.0) * 0.55
                noise = rng.standard_normal(n_s).astype(np.float32)
                if kit == "lofi":
                    noise = _one_pole_lowpass(noise, 3200.0, sample_rate)
                snare_noise = noise * np.exp(-t * 16.0) * 0.65
                hit = (body + snare_noise) * vel * 0.65
                pan = 0.48

            elif pitch == 39:
                # Hand clap: multi-burst filtered noise
                dur = 0.26
                n_s = min(total_samples - start_s, int(dur * sample_rate))
                t = np.arange(n_s, dtype=np.float32) / sample_rate
                noise = rng.standard_normal(n_s).astype(np.float32)
                noise = _one_pole_lowpass(noise, 4500.0, sample_rate)
                env = np.exp(-t * 15.0)
                for offset_ms in (0.010, 0.020, 0.032):
                    idx = int(offset_ms * sample_rate)
                    if idx < n_s:
                        env[idx : min(n_s, idx + 80)] *= 1.6
                hit = noise * env * vel * 0.55
                pan = 0.56

            elif pitch in (42, 44):
                # Closed hi-hat: short high-passed metallic noise
                dur = 0.075
                n_s = min(total_samples - start_s, int(dur * sample_rate))
                t = np.arange(n_s, dtype=np.float32) / sample_rate
                noise = rng.standard_normal(n_s).astype(np.float32)
                hp = noise - _one_pole_lowpass(noise, 5500.0, sample_rate)
                hit = hp * np.exp(-t * 58.0) * vel * 0.35
                pan = 0.64

            elif pitch in (46, 49, 51):
                # Open hi-hat / crash / ride
                dur = 0.42 if pitch == 46 else 0.75
                n_s = min(total_samples - start_s, int(dur * sample_rate))
                t = np.arange(n_s, dtype=np.float32) / sample_rate
                noise = rng.standard_normal(n_s).astype(np.float32)
                hp = noise - _one_pole_lowpass(noise, 4200.0, sample_rate)
                decay = 8.5 if pitch == 46 else 4.5
                hit = hp * np.exp(-t * decay) * vel * 0.32
                pan = 0.35 if pitch == 49 else 0.66

            else:
                # Toms / rim / generic percussion
                dur = 0.25
                n_s = min(total_samples - start_s, int(dur * sample_rate))
                t = np.arange(n_s, dtype=np.float32) / sample_rate
                base_f = 90.0 + max(0, pitch - 41) * 14.0
                freq_env = base_f + 45.0 * np.exp(-t * 22.0)
                phase = 2.0 * np.pi * np.cumsum(freq_env) / sample_rate
                hit = np.sin(phase) * np.exp(-t * 14.0) * vel * 0.6
                pan = 0.38 if pitch < 47 else 0.62

            pan_l = 0.5 - 0.5 * stereo_width * (pan * 2.0 - 1.0)
            pan_r = 1.0 - pan_l
            end_s = start_s + len(hit)
            left[start_s:end_s] += hit.astype(np.float32) * pan_l
            right[start_s:end_s] += hit.astype(np.float32) * pan_r

        if kit == "lofi":
            left = _one_pole_lowpass(left, 6500.0, sample_rate)
            right = _one_pole_lowpass(right, 6500.0, sample_rate)

        out_path = _write_stereo_wav(Path(f"drums_{kit}.wav"), left, right, sample_rate)
        return {"audio": out_path}


__all__ = [
    "AcousticPianoSynth",
    "BachPreludeScore",
    "DrumSynth",
    "PolySynth",
]
