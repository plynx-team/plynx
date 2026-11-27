"""Universal MIDI score generators and combinators for ``pedalboard_studio``.

Every op in this module outputs a canonical ``MidiFile`` (``audio/midi``) that wires
directly into any synthesizer (``AcousticPianoSynth``, ``PolySynth``, ``DrumSynth``)
or visualizer (``MidiPianoRoll``).
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict

from plynx_sdk import JsonFile, MidiFile, Op, Range

from pedalboard_studio.midi_io import (
    DRUM_CHANNEL,
    MidiNote,
    MidiScore,
    note_name_to_midi,
    read_midi,
    write_midi,
)

# ---------------------------------------------------------------------------
# Music theory tables for Roman numeral & chord-symbol parsing
# ---------------------------------------------------------------------------

_KEY_ROOT_SEMITONES: dict[str, int] = {
    "C": 0,
    "C#": 1,
    "Db": 1,
    "D": 2,
    "D#": 3,
    "Eb": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "Gb": 6,
    "G": 7,
    "G#": 8,
    "Ab": 8,
    "A": 9,
    "A#": 10,
    "Bb": 10,
    "B": 11,
}

_MAJOR_SCALE_INTERVALS = [0, 2, 4, 5, 7, 9, 11]
_MINOR_SCALE_INTERVALS = [0, 2, 3, 5, 7, 8, 10]

_ROMAN_TO_DEGREE: dict[str, int] = {
    "I": 0,
    "II": 1,
    "III": 2,
    "IV": 3,
    "V": 4,
    "VI": 5,
    "VII": 6,
}

# Match Roman numerals: optional accidental, numeral (I-VII/i-vii), optional quality
_ROMAN_RE = re.compile(
    r"^([#b]?)(III|VII|II|IV|VI|I|V|iii|vii|ii|iv|vi|i|v)"
    r"(maj7|maj9|m7b5|dim7|dim|aug|sus2|sus4|add9|m7|m6|m9|7|9|6|o|°)?$"
)

# Match explicit chord symbols like Cmaj7, Dm7, F#m, Bb7, Asus4
_CHORD_NAME_RE = re.compile(
    r"^([A-G])([#b]?)(maj7|maj9|m7b5|dim7|dim|aug|sus2|sus4|add9|m7|m6|m9|min|m|7|9|6|o|°)?$"
)

_QUALITY_INTERVALS: dict[str, tuple[int, ...]] = {
    "maj": (0, 4, 7),
    "min": (0, 3, 7),
    "m": (0, 3, 7),
    "dim": (0, 3, 6),
    "o": (0, 3, 6),
    "°": (0, 3, 6),
    "aug": (0, 4, 8),
    "sus2": (0, 2, 7),
    "sus4": (0, 5, 7),
    "6": (0, 4, 7, 9),
    "m6": (0, 3, 7, 9),
    "7": (0, 4, 7, 10),
    "maj7": (0, 4, 7, 11),
    "m7": (0, 3, 7, 10),
    "dim7": (0, 3, 6, 9),
    "m7b5": (0, 3, 6, 10),
    "add9": (0, 4, 7, 14),
    "9": (0, 4, 7, 10, 14),
    "maj9": (0, 4, 7, 11, 14),
    "m9": (0, 3, 7, 10, 14),
}

KEY_CHOICES = Literal[
    "C",
    "Cm",
    "Db",
    "D",
    "Dm",
    "Eb",
    "E",
    "Em",
    "F",
    "Fm",
    "F#",
    "G",
    "Gm",
    "Ab",
    "A",
    "Am",
    "Bb",
    "B",
    "Bm",
]

# General MIDI Percussion Map (Channel 9)
_DRUM_MAP: dict[str, int] = {
    "kick": 36,
    "bd": 36,
    "rim": 37,
    "snare": 38,
    "sd": 38,
    "clap": 39,
    "cp": 39,
    "hat": 42,
    "hihat": 42,
    "ch": 42,
    "lt": 45,
    "tom": 45,
    "ohat": 46,
    "oh": 46,
    "mt": 47,
    "crash": 49,
    "ht": 50,
    "ride": 51,
}

_STEP_NOTE_TOKEN_RE = re.compile(r"([A-Ga-g][#b]?-?\d|\.|~|-)")


def _parse_key(key: str) -> tuple[int, bool]:
    """Return ``(root_semitone, is_minor)`` for a key string like ``'C'`` or ``'Dm'``."""
    cleaned = key.strip()
    is_minor = cleaned.endswith("m") and len(cleaned) >= 2
    root_name = cleaned[:-1] if is_minor else cleaned
    root_semitone = _KEY_ROOT_SEMITONES.get(root_name, 0)
    return root_semitone, is_minor


def _parse_chord_token(
    token: str, key_root: int, is_minor_key: bool, base_octave: int
) -> list[int]:
    """Resolve a Roman numeral (``vi``, ``ii7``) or chord name (``Dm7``) to MIDI pitches."""
    raw = token.strip()
    if "/" in raw:
        raw = raw.split("/", 1)[0].strip()

    base_midi = (base_octave + 1) * 12

    roman_match = _ROMAN_RE.match(raw)
    if roman_match:
        accidental, numeral, quality = roman_match.groups()
        degree = _ROMAN_TO_DEGREE[numeral.upper()]
        scale = _MINOR_SCALE_INTERVALS if is_minor_key else _MAJOR_SCALE_INTERVALS
        semitone = key_root + scale[degree]
        if accidental == "#":
            semitone += 1
        elif accidental == "b":
            semitone -= 1
        is_lower = numeral.islower()
        if not quality:
            quality_key = "min" if is_lower else "maj"
        elif quality == "7" and is_lower:
            quality_key = "m7"
        else:
            quality_key = quality
        intervals = _QUALITY_INTERVALS.get(quality_key, (0, 4, 7))
        root_midi = base_midi + (semitone % 12)
        return [max(24, min(108, root_midi + iv)) for iv in intervals]

    chord_match = _CHORD_NAME_RE.match(raw)
    if chord_match:
        letter, accidental, quality = chord_match.groups()
        root_name = f"{letter}{accidental}"
        semitone = _KEY_ROOT_SEMITONES.get(root_name, 0)
        quality_key = quality or "maj"
        intervals = _QUALITY_INTERVALS.get(quality_key, (0, 4, 7))
        root_midi = base_midi + semitone
        return [max(24, min(108, root_midi + iv)) for iv in intervals]

    raise ValueError(f"Unrecognized chord or Roman numeral token: {token!r}")


def _parse_progression_tokens(progression: str) -> list[str]:
    """Split a chord progression string like ``'vi - IV - I - V'`` into tokens."""
    tokens = [tok for tok in re.split(r"[\s,|/\-]+", progression.strip()) if tok]
    if not tokens:
        raise ValueError("Chord progression cannot be empty.")
    return tokens


class ChordProgressionScore(Op):
    """Generate a Standard MIDI File from a Roman numeral or chord-symbol progression.

    Supports both Roman numeral notation (relative to ``key``) and explicit chord symbols,
    rendering smooth bass + voicing patterns ready for ``AcousticPianoSynth`` or ``PolySynth``.

    ### Progression Syntax
    Separate chords with `-`, spaces, `|`, or commas:
    - **Pop Classic:** `I - V - vi - IV`
    - **Emotional / Cinematic:** `vi - IV - I - V`
    - **Jazz ii-V-I:** `ii7 - V7 - Imaj7 - VI7`
    - **Lo-Fi Chill:** `ii9 - V7 - Imaj7 - vi7`
    - **Explicit Chords:** `Am7 - Fmaj7 - Cmaj7 - G7`

    ### Supported Qualities
    Uppercase numerals (`I`, `IV`, `V`) are major; lowercase (`ii`, `iii`, `vi`) are minor.
    Qualities: `maj7`, `m7`, `7`, `dim`, `dim7`, `m7b5`, `aug`, `sus2`, `sus4`,
    `6`, `m6`, `add9`, `9`, `maj9`, `m9`.
    """

    TITLE = "Chord Progression Score"
    CATEGORY = "Audio / Score"
    CACHEABLE = True

    class Outputs(TypedDict):
        midi: MidiFile
        note_count: int
        duration_sec: float

    def run(
        self,
        progression: str = "vi - IV - I - V",
        key: KEY_CHOICES = "C",
        bpm: Annotated[int, Range(40, 220)] = 92,
        bars: Annotated[int, Range(1, 32)] = 8,
        voicing_style: Literal["block", "arpeggio", "waltz", "strumming"] = "arpeggio",
        octave: Annotated[int, Range(2, 6)] = 4,
    ) -> Outputs:
        """Render a chord progression into a Standard MIDI File.

        Args:
            progression: Roman numeral or chord symbol progression (e.g. 'vi - IV - I - V').
            key: Musical key signature (major or minor, e.g. 'C', 'Am', 'F#', 'Bb').
            bpm: Tempo in beats per minute.
            bars: Total number of bars to generate (loops through the progression).
            voicing_style: How each chord is played ('block', 'arpeggio', 'waltz', 'strumming').
            octave: Base octave for chord voicings (bass plays one octave below).

        Returns:
            Dictionary containing `midi`, `note_count`, and `duration_sec`.
        """
        tokens = _parse_progression_tokens(progression)
        key_root, is_minor_key = _parse_key(key)
        chords = [_parse_chord_token(tok, key_root, is_minor_key, octave) for tok in tokens]

        beat_sec = 60.0 / float(bpm)
        beats_per_bar = 3 if voicing_style == "waltz" else 4
        bar_sec = beat_sec * beats_per_bar
        notes: list[MidiNote] = []

        for bar_idx in range(bars):
            chord = chords[bar_idx % len(chords)]
            bar_start = bar_idx * bar_sec
            bass_pitch = max(24, chord[0] - 12)

            if voicing_style == "block":
                # Sustained bass + full chord pad across the bar
                notes.append(
                    MidiNote(
                        pitch=bass_pitch,
                        start_sec=bar_start,
                        duration_sec=bar_sec * 0.95,
                        velocity=92,
                        channel=0,
                    )
                )
                for idx, pitch in enumerate(chord):
                    vel = 84 if idx == 0 else 76
                    notes.append(
                        MidiNote(
                            pitch=pitch,
                            start_sec=bar_start,
                            duration_sec=bar_sec * 0.92,
                            velocity=vel,
                            channel=0,
                        )
                    )

            elif voicing_style == "arpeggio":
                # Held bass + eighth-note rolling arpeggio up and down
                notes.append(
                    MidiNote(
                        pitch=bass_pitch,
                        start_sec=bar_start,
                        duration_sec=bar_sec * 0.92,
                        velocity=90,
                        channel=0,
                    )
                )
                arp_pool = list(chord) + ([chord[0] + 12] if chord[0] + 12 <= 108 else [])
                eighth = beat_sec / 2.0
                for step in range(8):
                    idx = step % len(arp_pool)
                    pitch = arp_pool[idx]
                    vel = 88 if step % 4 == 0 else 72
                    notes.append(
                        MidiNote(
                            pitch=pitch,
                            start_sec=bar_start + step * eighth,
                            duration_sec=eighth * 1.6,
                            velocity=vel,
                            channel=0,
                        )
                    )

            elif voicing_style == "waltz":
                # 3/4 time: bass on beat 1, chord hits on beats 2 and 3
                notes.append(
                    MidiNote(
                        pitch=bass_pitch,
                        start_sec=bar_start,
                        duration_sec=beat_sec * 1.5,
                        velocity=96,
                        channel=0,
                    )
                )
                for beat in (1, 2):
                    for pitch in chord:
                        notes.append(
                            MidiNote(
                                pitch=pitch,
                                start_sec=bar_start + beat * beat_sec,
                                duration_sec=beat_sec * 0.75,
                                velocity=74 if beat == 1 else 68,
                                channel=0,
                            )
                        )

            else:
                # strumming: acoustic rhythm pattern with slight roll across strings
                strum_beats = [0.0, 1.5, 2.0, 3.0, 3.5]
                notes.append(
                    MidiNote(
                        pitch=bass_pitch,
                        start_sec=bar_start,
                        duration_sec=beat_sec * 2.0,
                        velocity=92,
                        channel=0,
                    )
                )
                notes.append(
                    MidiNote(
                        pitch=bass_pitch,
                        start_sec=bar_start + 2.0 * beat_sec,
                        duration_sec=beat_sec * 1.8,
                        velocity=86,
                        channel=0,
                    )
                )
                for s_idx, b_offset in enumerate(strum_beats):
                    base_t = bar_start + b_offset * beat_sec
                    dur = beat_sec * (1.2 if s_idx in (0, 2) else 0.55)
                    for n_idx, pitch in enumerate(chord):
                        roll = n_idx * 0.014
                        vel = 86 if s_idx in (0, 2) else 70
                        notes.append(
                            MidiNote(
                                pitch=pitch,
                                start_sec=base_t + roll,
                                duration_sec=dur,
                                velocity=vel,
                                channel=0,
                            )
                        )

        score = MidiScore(
            notes=notes,
            tempo_bpm=float(bpm),
            title=f"Chord Progression ({key}): {progression}",
        )
        out_path = Path("chord_progression.mid")
        write_midi(out_path, score)
        return {
            "midi": out_path,
            "note_count": len(notes),
            "duration_sec": round(bar_sec * bars, 3),
        }


class StepSequencer(Op):
    """Parse a multi-track 16-step ASCII pattern grid into a synced Standard MIDI File.

    Drum tracks are automatically routed to **MIDI Channel 9** (General MIDI Percussion)
    for ``DrumSynth``, while melodic tracks (`bass`, `lead`, `arp`, `synth`) are routed
    to melodic channels (`0`, `1`, ...) for ``PolySynth`` or ``AcousticPianoSynth``.

    ### Pattern Syntax
    One track per line in `name: pattern` format:
    ```text
    kick:  x...x...x...x...
    snare: ....x.......x...
    hat:   x.x.x.x.x.x.x.x.
    clap:  ....x.......x..o
    bass:  C2..C2..G1..A1..
    ```
    - **Drum velocity symbols:** `X` = accent (120), `x` = hit (96), `o` = ghost (56),
      `.` or `-` = rest.
    - **Supported drum names:** `kick` (`bd`), `snare` (`sd`), `clap` (`cp`), `hat` (`ch`),
      `ohat` (`oh`), `tom` (`lt`/`mt`/`ht`), `rim`, `crash`, `ride`.
    - **Melodic symbols:** Note names (`C2`, `F#3`, `Bb2`), `.` = rest,
      `-` or `~` = sustain previous note.
    """

    TITLE = "Step Sequencer"
    CATEGORY = "Audio / Score"
    CACHEABLE = True

    class Outputs(TypedDict):
        midi: MidiFile
        note_count: int
        duration_sec: float

    def run(
        self,
        pattern: str = (
            "kick:  x...x...x...x...\n"
            "snare: ....x.......x...\n"
            "hat:   x.o.x.o.x.o.x.o.\n"
            "clap:  ....X.......X...\n"
            "bass:  C2..C2..G1..A1.."
        ),
        bpm: Annotated[int, Range(50, 220)] = 110,
        bars: Annotated[int, Range(1, 16)] = 4,
        swing: Annotated[float, Range(0.0, 0.5)] = 0.0,
    ) -> Outputs:
        """Compile an ASCII step-sequencer grid into a multi-channel MIDI file.

        Args:
            pattern: Multi-line `track: steps` grid for drums and melodic lines.
            bpm: Tempo in beats per minute.
            bars: Number of times to repeat the pattern cycle.
            swing: Off-beat 16th-note swing delay fraction (0.0 = straight, 0.3 = groove).

        Returns:
            Dictionary containing `midi`, `note_count`, and `duration_sec`.
        """
        step_sec = (60.0 / float(bpm)) / 4.0  # 16th note duration
        notes: list[MidiNote] = []
        max_steps_per_bar = 16
        next_melodic_channel = 0

        parsed_tracks: list[tuple[str, str]] = []
        for raw_line in pattern.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            track_name, grid = line.split(":", 1)
            name_clean = track_name.strip().lower()
            grid_clean = grid.strip()
            if name_clean and grid_clean:
                parsed_tracks.append((name_clean, grid_clean))

        if not parsed_tracks:
            raise ValueError("StepSequencer pattern must contain at least one 'track: steps' line.")

        for track_name, grid in parsed_tracks:
            if track_name in _DRUM_MAP:
                drum_pitch = _DRUM_MAP[track_name]
                cells = [ch for ch in grid if not ch.isspace()]
                if not cells:
                    continue
                max_steps_per_bar = max(max_steps_per_bar, len(cells))
                for bar_idx in range(bars):
                    for step_idx, symbol in enumerate(cells):
                        if symbol == "X":
                            vel = 120
                        elif symbol == "x":
                            vel = 96
                        elif symbol == "o":
                            vel = 56
                        else:
                            continue
                        abs_step = bar_idx * len(cells) + step_idx
                        swing_offset = (step_sec * swing) if (step_idx % 2 == 1) else 0.0
                        notes.append(
                            MidiNote(
                                pitch=drum_pitch,
                                start_sec=abs_step * step_sec + swing_offset,
                                duration_sec=step_sec * 0.85,
                                velocity=vel,
                                channel=DRUM_CHANNEL,
                            )
                        )
            else:
                # Melodic track: assign next non-drum channel (skip channel 9)
                if next_melodic_channel == DRUM_CHANNEL:
                    next_melodic_channel += 1
                ch = next_melodic_channel % 16
                next_melodic_channel += 1

                tokens = _STEP_NOTE_TOKEN_RE.findall(grid)
                if not tokens:
                    continue
                max_steps_per_bar = max(max_steps_per_bar, len(tokens))

                for bar_idx in range(bars):
                    step_idx = 0
                    while step_idx < len(tokens):
                        tok = tokens[step_idx]
                        if tok in (".", "-", "~"):
                            step_idx += 1
                            continue
                        pitch = note_name_to_midi(tok)
                        # Count following sustain markers ('-' or '~')
                        sustain_steps = 1
                        while step_idx + sustain_steps < len(tokens) and tokens[
                            step_idx + sustain_steps
                        ] in ("-", "~"):
                            sustain_steps += 1
                        abs_step = bar_idx * len(tokens) + step_idx
                        swing_offset = (step_sec * swing) if (step_idx % 2 == 1) else 0.0
                        notes.append(
                            MidiNote(
                                pitch=pitch,
                                start_sec=abs_step * step_sec + swing_offset,
                                duration_sec=step_sec * sustain_steps * 0.92,
                                velocity=92,
                                channel=ch,
                            )
                        )
                        step_idx += sustain_steps

        total_duration = round(bars * max_steps_per_bar * step_sec, 3)
        score = MidiScore(notes=notes, tempo_bpm=float(bpm), title="Step Sequencer Pattern")
        out_path = Path("sequencer_pattern.mid")
        write_midi(out_path, score)
        return {
            "midi": out_path,
            "note_count": len(notes),
            "duration_sec": total_duration,
        }


class MidiMerge(Op):
    """Merge two or more MIDI files into a single multi-channel Standard MIDI File.

    Preserves **Channel 9** (General MIDI drums/percussion) across all inputs and assigns
    melodic tracks to separate non-colliding MIDI channels so downstream synthesizers and
    ``MidiPianoRoll`` keep voices cleanly separated.

    Supports dynamic extra inputs (`+ Add input` in the Inspector) to merge 3, 4, or more tracks.
    """

    TITLE = "MIDI Track Merger"
    CATEGORY = "Audio / Score"
    CACHEABLE = True
    ALLOW_EXTRA_INPUTS = True

    class Outputs(TypedDict):
        midi: MidiFile
        track_count: int
        note_count: int

    def run(
        self,
        track_a: MidiFile,
        track_b: MidiFile | None = None,
        **extra_tracks: MidiFile,
    ) -> Outputs:
        """Merge multiple MIDI files onto distinct channels.

        Args:
            track_a: Primary MIDI file (determines master tempo).
            track_b: Optional second MIDI file to layer onto the score.
            **extra_tracks: Arbitrary additional MIDI tracks to merge.

        Returns:
            Dictionary containing merged `midi`, `track_count`, and `note_count`.
        """
        input_paths: list[Path] = [Path(track_a)]
        if track_b is not None:
            input_paths.append(Path(track_b))
        for key in sorted(extra_tracks):
            val = extra_tracks[key]
            if val is not None:
                input_paths.append(Path(val))

        scores = [read_midi(p) for p in input_paths]
        master_bpm = scores[0].tempo_bpm if scores else 120.0

        used_melodic_channels: set[int] = set()
        merged_notes: list[MidiNote] = []

        for score in scores:
            channel_remap: dict[int, int] = {}
            for note in score.notes:
                if note.channel == DRUM_CHANNEL:
                    target_ch = DRUM_CHANNEL
                else:
                    if note.channel not in channel_remap:
                        candidate = note.channel
                        if candidate in used_melodic_channels or candidate == DRUM_CHANNEL:
                            # Find first unused melodic channel
                            candidate = next(
                                (
                                    c
                                    for c in range(16)
                                    if c != DRUM_CHANNEL and c not in used_melodic_channels
                                ),
                                note.channel,
                            )
                        channel_remap[note.channel] = candidate
                        used_melodic_channels.add(candidate)
                    target_ch = channel_remap[note.channel]

                merged_notes.append(
                    MidiNote(
                        pitch=note.pitch,
                        start_sec=note.start_sec,
                        duration_sec=note.duration_sec,
                        velocity=note.velocity,
                        channel=target_ch,
                    )
                )

        merged_notes.sort(key=lambda n: (n.start_sec, n.channel, n.pitch))
        merged = MidiScore(
            notes=merged_notes,
            tempo_bpm=master_bpm,
            title=f"Merged MIDI ({len(scores)} tracks)",
        )
        out_path = Path("merged.mid")
        write_midi(out_path, merged)
        return {
            "midi": out_path,
            "track_count": len(scores),
            "note_count": len(merged_notes),
        }


class MidiTransform(Op):
    """Adjust tempo, pitch transposition, velocity dynamics, or bar length of any MIDI file.

    Accepts any Standard MIDI File (``.mid``) and outputs a transformed ``MidiFile`` plus a
    JSON summary of note count, tempo, and duration. Melodic channels are transposed cleanly
    while General MIDI percussion (Channel 9) pitches remain untouched.
    """

    TITLE = "MIDI Transform & Trim"
    CATEGORY = "Audio / Score"
    CACHEABLE = True

    class Outputs(TypedDict):
        midi: MidiFile
        metadata: JsonFile
        note_count: int
        duration_sec: float

    def run(
        self,
        midi: MidiFile,
        tempo_bpm: Annotated[int, Range(0, 240)] = 0,
        transpose_semitones: Annotated[int, Range(-24, 24)] = 0,
        dynamics: Literal["original", "expressive", "flat", "crescendo"] = "original",
        max_bars: Annotated[int, Range(0, 128)] = 0,
    ) -> Outputs:
        """Transform tempo, transposition, dynamics, or bar length of an input MIDI file.

        Args:
            midi: Input Standard MIDI File to transform.
            tempo_bpm: Target tempo in BPM (0 keeps the input MIDI file's original tempo).
            transpose_semitones: Semitone shift applied to non-percussion channels (-24 to +24).
            dynamics: Velocity phrasing curve ('original', 'expressive', 'flat', or 'crescendo').
            max_bars: Trim output to the first N 4/4 bars (0 keeps the entire score).

        Returns:
            Dictionary containing `midi`, `metadata`, `note_count`, and `duration_sec`.
        """
        src_score = read_midi(Path(midi))
        orig_bpm = max(20.0, float(src_score.tempo_bpm))
        target_bpm = float(tempo_bpm) if tempo_bpm > 0 else orig_bpm
        time_scale = orig_bpm / target_bpm

        bar_duration_sec = (60.0 / target_bpm) * 4.0
        cutoff_sec = (max_bars * bar_duration_sec) if max_bars > 0 else None

        scaled_notes: list[MidiNote] = []
        for note in src_score.notes:
            new_start = note.start_sec * time_scale
            if cutoff_sec is not None and new_start >= cutoff_sec - 1e-6:
                continue
            new_dur = note.duration_sec * time_scale
            if cutoff_sec is not None and new_start + new_dur > cutoff_sec:
                new_dur = max(0.02, cutoff_sec - new_start)

            new_pitch = (
                note.pitch
                if note.channel == DRUM_CHANNEL
                else max(0, min(127, note.pitch + transpose_semitones))
            )
            scaled_notes.append(
                MidiNote(
                    pitch=new_pitch,
                    start_sec=new_start,
                    duration_sec=new_dur,
                    velocity=note.velocity,
                    channel=note.channel,
                )
            )

        total_span = max(
            (n.start_sec + n.duration_sec for n in scaled_notes),
            default=0.0,
        )
        if dynamics != "original" and scaled_notes:
            shaped_notes: list[MidiNote] = []
            denom = max(total_span, 1e-6)
            for n in scaled_notes:
                progress = min(1.0, max(0.0, n.start_sec / denom))
                if dynamics == "expressive":
                    curve = 0.72 + 0.28 * math.sin(progress * math.pi)
                    vel = round(min(127.0, max(1.0, n.velocity * curve / 0.85)))
                elif dynamics == "crescendo":
                    vel = round(56.0 + 64.0 * progress)
                else:  # flat
                    vel = 96
                shaped_notes.append(
                    MidiNote(
                        pitch=n.pitch,
                        start_sec=n.start_sec,
                        duration_sec=n.duration_sec,
                        velocity=max(1, min(127, int(vel))),
                        channel=n.channel,
                    )
                )
            scaled_notes = shaped_notes

        out_score = MidiScore(
            notes=scaled_notes,
            tempo_bpm=target_bpm,
            title=src_score.title or Path(midi).stem,
        )
        out_midi = Path("transformed.mid")
        write_midi(out_midi, out_score)

        bars_estimated = round(total_span / bar_duration_sec, 2) if bar_duration_sec > 0 else 0.0
        meta: dict[str, Any] = {
            "title": out_score.title,
            "source_tempo_bpm": round(orig_bpm, 2),
            "tempo_bpm": round(target_bpm, 2),
            "transpose_semitones": transpose_semitones,
            "dynamics": dynamics,
            "bars_estimated": bars_estimated,
            "total_duration_sec": round(total_span, 3),
            "notes_count": len(scaled_notes),
        }
        meta_path = Path("score_metadata.json")
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        return {
            "midi": out_midi,
            "metadata": meta_path,
            "note_count": len(scaled_notes),
            "duration_sec": round(total_span, 3),
        }


__all__ = [
    "KEY_CHOICES",
    "ChordProgressionScore",
    "MidiMerge",
    "MidiTransform",
    "StepSequencer",
]
