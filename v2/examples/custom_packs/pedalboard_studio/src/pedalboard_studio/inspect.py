"""Audio technical stats analysis and MIDI piano-roll visualization for ``pedalboard_studio``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, TypedDict

import numpy as np
from PIL import Image, ImageDraw
from plynx_sdk import AudioWav, ImageFile, JsonFile, MidiFile, Op, Range

from pedalboard_studio.effects import _read_audio
from pedalboard_studio.midi_io import DRUM_CHANNEL, read_midi

# Dark studio MIDI channel color palette (RGB)
_CHANNEL_COLORS: dict[int, tuple[int, int, int]] = {
    0: (56, 189, 248),  # Sky blue
    1: (52, 211, 153),  # Emerald
    2: (167, 139, 250),  # Violet
    3: (244, 114, 182),  # Pink
    4: (251, 191, 36),  # Amber
    5: (45, 212, 191),  # Teal
    6: (129, 140, 248),  # Indigo
    7: (163, 230, 53),  # Lime
    8: (251, 146, 60),  # Orange
    DRUM_CHANNEL: (248, 113, 113),  # Coral red for GM drums
}
_BLACK_KEY_SEMITONES = {1, 3, 6, 8, 10}


class AudioStats(Op):
    """Compute technical audio metrics: RMS, peak dBFS, dynamic range, and duration."""

    TITLE = "Audio Technical Stats"
    CATEGORY = "Inspect & Visualize"
    CACHEABLE = True

    class Outputs(TypedDict):
        stats: JsonFile

    def run(self, audio: AudioWav) -> Outputs:
        audio_data, sample_rate = _read_audio(audio)
        n_channels, total_samples = audio_data.shape

        duration_sec = total_samples / sample_rate

        # Peak amplitude and dBFS
        peak_amp = float(np.max(np.abs(audio_data)))
        peak_db = 20.0 * np.log10(max(peak_amp, 1e-9))

        # RMS amplitude and dBFS
        rms_amp = float(np.sqrt(np.mean(audio_data**2)))
        rms_db = 20.0 * np.log10(max(rms_amp, 1e-9))

        # Dynamic range (crest factor)
        crest_factor_db = peak_db - rms_db

        stats = {
            "duration_sec": round(duration_sec, 3),
            "sample_rate": sample_rate,
            "channels": n_channels,
            "total_samples": total_samples,
            "peak_amplitude": round(peak_amp, 4),
            "peak_dbfs": round(peak_db, 2),
            "rms_amplitude": round(rms_amp, 4),
            "rms_dbfs": round(rms_db, 2),
            "crest_factor_db": round(crest_factor_db, 2),
            "clipping_detected": bool(peak_amp >= 0.999),
        }

        out_path = Path("audio_stats.json")
        out_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
        return {"stats": out_path}


class MidiPianoRoll(Op):
    """Render a dark studio piano-roll visualization (pitch vs. time) of a MIDI file.

    Colors note rectangles by MIDI channel (with GM Channel 9 percussion highlighted in
    coral) and scales brightness by velocity so you can visually inspect chord voicings,
    arpeggios, and drum patterns directly in the Plynx UI.
    """

    TITLE = "MIDI Piano Roll Visualizer"
    CATEGORY = "Inspect & Visualize"
    CACHEABLE = True

    class Outputs(TypedDict):
        piano_roll: ImageFile
        note_count: int
        duration_sec: float

    def run(
        self,
        midi: MidiFile,
        width: Annotated[int, Range(400, 2400)] = 1000,
        height: Annotated[int, Range(200, 1200)] = 420,
        show_keyboard: bool = True,
    ) -> Outputs:
        """Render a Standard MIDI File as a piano-roll PNG image.

        Args:
            midi: Input Standard MIDI File to visualize.
            width: Output image width in pixels.
            height: Output image height in pixels.
            show_keyboard: Draw a piano keyboard gutter with C-octave labels on the left.

        Returns:
            Dictionary containing `piano_roll` (ImageFile), `note_count`, and `duration_sec`.
        """
        score = read_midi(Path(midi))
        img = Image.new("RGB", (width, height), color=(15, 16, 22))
        draw = ImageDraw.Draw(img)

        gutter_w = 54 if show_keyboard else 8
        header_h = 26
        roll_x0 = gutter_w
        roll_y0 = header_h
        roll_w = max(1, width - roll_x0 - 8)
        roll_h = max(1, height - roll_y0 - 8)

        # Header bar
        draw.rectangle([(0, 0), (width - 1, header_h - 1)], fill=(22, 24, 32))
        header_label = (
            f"{score.title or 'MIDI Score'}  |  {score.tempo_bpm:.0f} BPM  |  "
            f"{len(score.notes)} notes  |  {score.duration_sec:.1f}s"
        )
        draw.text((10, 7), header_label, fill=(210, 216, 230))

        if not score.notes:
            draw.text(
                (roll_x0 + 16, roll_y0 + 16), "Empty MIDI score (0 notes)", fill=(130, 136, 150)
            )
            out_path = Path("piano_roll.png")
            img.save(str(out_path), "PNG")
            return {"piano_roll": out_path, "note_count": 0, "duration_sec": 0.0}

        min_pitch = max(0, min(n.pitch for n in score.notes) - 2)
        max_pitch = min(127, max(n.pitch for n in score.notes) + 2)
        pitch_span = max(12, max_pitch - min_pitch + 1)
        row_h = roll_h / float(pitch_span)

        total_dur = max(0.25, score.duration_sec)
        beat_sec = 60.0 / max(20.0, score.tempo_bpm)

        # Draw horizontal pitch rows & optional keyboard gutter
        for offset in range(pitch_span):
            pitch = max_pitch - offset
            y_top = roll_y0 + offset * row_h
            y_bot = roll_y0 + (offset + 1) * row_h
            semitone = pitch % 12
            is_black = semitone in _BLACK_KEY_SEMITONES

            row_bg = (18, 20, 27) if is_black else (24, 26, 35)
            draw.rectangle([(roll_x0, y_top), (roll_x0 + roll_w, y_bot)], fill=row_bg)

            if semitone == 0:
                draw.line([(roll_x0, y_bot), (roll_x0 + roll_w, y_bot)], fill=(45, 50, 65), width=1)

            if show_keyboard:
                key_color = (34, 36, 46) if is_black else (215, 220, 232)
                draw.rectangle([(2, y_top), (gutter_w - 3, max(y_top, y_bot - 1))], fill=key_color)
                if semitone == 0 and row_h >= 7:
                    octave_num = (pitch // 12) - 1
                    draw.text((6, int(y_top)), f"C{octave_num}", fill=(30, 34, 44))

        # Draw vertical beat and bar grid lines
        num_beats = int(total_dur / beat_sec) + 1
        for beat_idx in range(num_beats + 1):
            t_sec = beat_idx * beat_sec
            if t_sec > total_dur:
                break
            x = roll_x0 + int((t_sec / total_dur) * roll_w)
            is_bar = beat_idx % 4 == 0
            line_color = (56, 62, 80) if is_bar else (32, 35, 46)
            draw.line([(x, roll_y0), (x, roll_y0 + roll_h)], fill=line_color, width=1)

        # Draw note rectangles
        for note in score.notes:
            x0 = roll_x0 + int((note.start_sec / total_dur) * roll_w)
            x1 = roll_x0 + int(((note.start_sec + note.duration_sec) / total_dur) * roll_w)
            if x1 <= x0 + 2:
                x1 = x0 + 2

            row_idx = max_pitch - note.pitch
            y0 = roll_y0 + row_idx * row_h + 1
            y1 = roll_y0 + (row_idx + 1) * row_h - 1
            if y1 <= y0:
                y1 = y0 + 1

            base_rgb = _CHANNEL_COLORS.get(note.channel, _CHANNEL_COLORS[note.channel % 9])
            vel_scale = 0.55 + 0.45 * (note.velocity / 127.0)
            fill_rgb = (
                min(255, int(base_rgb[0] * vel_scale)),
                min(255, int(base_rgb[1] * vel_scale)),
                min(255, int(base_rgb[2] * vel_scale)),
            )
            outline_rgb = (
                min(255, fill_rgb[0] + 35),
                min(255, fill_rgb[1] + 35),
                min(255, fill_rgb[2] + 35),
            )
            draw.rectangle(
                [(x0, y0), (min(roll_x0 + roll_w, x1), y1)], fill=fill_rgb, outline=outline_rgb
            )

        # Outer border
        draw.rectangle([(0, 0), (width - 1, height - 1)], outline=(44, 48, 62), width=1)

        out_path = Path("piano_roll.png")
        img.save(str(out_path), "PNG")
        return {
            "piano_roll": out_path,
            "note_count": len(score.notes),
            "duration_sec": round(score.duration_sec, 3),
        }


__all__ = ["AudioStats", "MidiPianoRoll"]
