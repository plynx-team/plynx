"""Pure-Python Standard MIDI File (SMF Type 0 / Type 1) reader and writer.

Zero external dependencies — uses Python standard library only so any pack or tool
can read and write canonical ``MidiFile`` (``audio/midi``) artifacts.
"""

from __future__ import annotations

import re
import struct
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_PPQN = 480
DEFAULT_TEMPO_BPM = 120.0
DRUM_CHANNEL = 9  # 0-indexed channel 9 = GM 1-indexed channel 10

_NOTE_OFFSETS: dict[str, int] = {
    "C": 0,
    "D": 2,
    "E": 4,
    "F": 5,
    "G": 7,
    "A": 9,
    "B": 11,
}
_NOTE_RE = re.compile(r"^([A-Ga-g])([#b]?)(-?\d)$")


@dataclass(frozen=True)
class MidiNote:
    """A single MIDI note event in absolute seconds."""

    pitch: int
    start_sec: float
    duration_sec: float
    velocity: int = 100
    channel: int = 0


@dataclass
class MidiScore:
    """In-memory representation of a multi-channel MIDI score."""

    notes: list[MidiNote] = field(default_factory=list)
    tempo_bpm: float = DEFAULT_TEMPO_BPM
    ppqn: int = DEFAULT_PPQN
    title: str = ""

    @property
    def duration_sec(self) -> float:
        """Return the end time in seconds of the latest note (0.0 if empty)."""
        if not self.notes:
            return 0.0
        return max(n.start_sec + n.duration_sec for n in self.notes)


def midi_pitch_to_freq(pitch: int) -> float:
    """Convert a MIDI note number (0-127) to frequency in Hz (A4 = 69 = 440 Hz)."""
    return float(440.0 * (2.0 ** ((pitch - 69) / 12.0)))


def note_name_to_midi(name: str) -> int:
    """Parse a pitch name like ``C4``, ``F#3``, or ``Bb2`` into a MIDI pitch (0-127).

    Raises:
        ValueError: If ``name`` is not a valid note name or falls outside 0-127.
    """
    match = _NOTE_RE.match(name.strip())
    if not match:
        raise ValueError(f"Invalid MIDI note name: {name!r}")
    letter, accidental, octave_str = match.groups()
    semitone = _NOTE_OFFSETS[letter.upper()]
    if accidental == "#":
        semitone += 1
    elif accidental == "b":
        semitone -= 1
    midi = (int(octave_str) + 1) * 12 + semitone
    if not 0 <= midi <= 127:
        raise ValueError(f"MIDI note {name!r} resolves to out-of-range pitch {midi}")
    return midi


def _encode_vlq(value: int) -> bytes:
    """Encode a non-negative integer as a MIDI Variable-Length Quantity."""
    if value < 0:
        value = 0
    chunks = [value & 0x7F]
    value >>= 7
    while value > 0:
        chunks.append((value & 0x7F) | 0x80)
        value >>= 7
    chunks.reverse()
    return bytes(chunks)


def _decode_vlq(data: bytes, offset: int) -> tuple[int, int]:
    """Decode a MIDI Variable-Length Quantity starting at ``offset``.

    Returns:
        Tuple of ``(value, new_offset)``.
    """
    value = 0
    length = len(data)
    while offset < length:
        byte = data[offset]
        offset += 1
        value = (value << 7) | (byte & 0x7F)
        if not (byte & 0x80):
            break
    return value, offset


def _build_track_chunk(events: list[tuple[int, int, bytes]]) -> bytes:
    """Build an ``MTrk`` chunk from ``(abs_tick, sort_priority, raw_event_bytes)`` tuples."""
    sorted_events = sorted(events, key=lambda item: (item[0], item[1]))
    body = bytearray()
    prev_tick = 0
    for tick, _priority, payload in sorted_events:
        delta = max(0, tick - prev_tick)
        body.extend(_encode_vlq(delta))
        body.extend(payload)
        prev_tick = tick
    # End of Track meta event
    body.extend(b"\x00\xff\x2f\x00")
    return b"MTrk" + struct.pack(">I", len(body)) + bytes(body)


def write_midi(path: Path, score: MidiScore) -> Path:
    """Write a ``MidiScore`` to a Standard MIDI File (SMF Type 1).

    Args:
        path: Output ``.mid`` file path.
        score: ``MidiScore`` containing notes, tempo, and PPQN.

    Returns:
        The written ``Path``.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    ppqn = max(24, int(score.ppqn))
    tempo_bpm = max(10.0, float(score.tempo_bpm))
    us_per_beat = max(1, round(60_000_000.0 / tempo_bpm))
    ticks_per_sec = (tempo_bpm / 60.0) * ppqn

    # Track 0: tempo & title meta track
    meta_events: list[tuple[int, int, bytes]] = []
    if score.title:
        title_bytes = score.title.encode("utf-8", errors="replace")[:127]
        meta_events.append((0, 0, b"\xff\x03" + _encode_vlq(len(title_bytes)) + title_bytes))
    tempo_bytes = us_per_beat.to_bytes(3, byteorder="big")
    meta_events.append((0, 1, b"\xff\x51\x03" + tempo_bytes))

    tracks: list[bytes] = [_build_track_chunk(meta_events)]

    # Group notes by MIDI channel (one track per active channel)
    by_channel: dict[int, list[MidiNote]] = defaultdict(list)
    for note in score.notes:
        ch = max(0, min(15, int(note.channel)))
        by_channel[ch].append(note)

    for ch in sorted(by_channel):
        track_events: list[tuple[int, int, bytes]] = []
        for note in by_channel[ch]:
            pitch = max(0, min(127, int(note.pitch)))
            vel = max(1, min(127, int(note.velocity)))
            start_tick = max(0, round(note.start_sec * ticks_per_sec))
            dur_ticks = max(1, round(note.duration_sec * ticks_per_sec))
            end_tick = start_tick + dur_ticks
            # Priority: 0 for Note Off, 1 for Note On (prevents stuck notes on re-trigger)
            track_events.append((start_tick, 1, bytes([0x90 | ch, pitch, vel])))
            track_events.append((end_tick, 0, bytes([0x80 | ch, pitch, 0])))
        tracks.append(_build_track_chunk(track_events))

    header = b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), ppqn)
    payload = header + b"".join(tracks)
    path.write_bytes(payload)
    return path


def _ticks_to_seconds(tick: int, tempo_map: list[tuple[int, int]], ppqn: int) -> float:
    """Convert an absolute MIDI tick to seconds using a sorted ``(tick, us_per_beat)`` tempo map."""
    elapsed_sec = 0.0
    prev_tick = 0
    current_us_per_beat = 500_000  # 120 BPM default

    for change_tick, us_per_beat in tempo_map:
        if change_tick >= tick:
            break
        if change_tick > prev_tick:
            elapsed_sec += ((change_tick - prev_tick) / ppqn) * (current_us_per_beat / 1_000_000.0)
            prev_tick = change_tick
        current_us_per_beat = us_per_beat

    if tick > prev_tick:
        elapsed_sec += ((tick - prev_tick) / ppqn) * (current_us_per_beat / 1_000_000.0)
    return elapsed_sec


def read_midi(path: Path) -> MidiScore:
    """Parse a Standard MIDI File (SMF Type 0 or Type 1) into a ``MidiScore``.

    Args:
        path: Path to an existing ``.mid`` file.

    Returns:
        Parsed ``MidiScore`` with absolute note timings in seconds.

    Raises:
        ValueError: If the file does not have a valid SMF header.
    """
    data = Path(path).read_bytes()
    if len(data) < 14 or data[:4] != b"MThd":
        raise ValueError(f"Invalid MIDI file (missing MThd header): {path}")

    header_len, _fmt, _num_tracks, division = struct.unpack(">IHHH", data[4:14])
    # SMPTE timecode division fallback when bit 15 is set
    ppqn = DEFAULT_PPQN if (division & 0x8000) else max(1, division)

    offset = 8 + header_len
    tempo_changes: list[tuple[int, int]] = []
    raw_note_events: list[tuple[int, int, int, int, bool]] = []  # (tick, ch, pitch, vel, is_on)
    title = ""

    while offset + 8 <= len(data):
        chunk_id = data[offset : offset + 4]
        chunk_len = struct.unpack(">I", data[offset + 4 : offset + 8])[0]
        chunk_start = offset + 8
        chunk_end = min(len(data), chunk_start + chunk_len)
        offset = chunk_end

        if chunk_id != b"MTrk":
            continue

        pos = chunk_start
        abs_tick = 0
        running_status = 0

        while pos < chunk_end:
            delta, pos = _decode_vlq(data, pos)
            abs_tick += delta
            if pos >= chunk_end:
                break

            status = data[pos]
            if status & 0x80:
                pos += 1
                if status < 0xF0:
                    running_status = status
            else:
                status = running_status

            if status == 0xFF:
                if pos >= chunk_end:
                    break
                meta_type = data[pos]
                pos += 1
                meta_len, pos = _decode_vlq(data, pos)
                meta_data = data[pos : pos + meta_len]
                pos += meta_len
                if meta_type == 0x51 and len(meta_data) == 3:
                    us_per_beat = int.from_bytes(meta_data, byteorder="big")
                    if us_per_beat > 0:
                        tempo_changes.append((abs_tick, us_per_beat))
                elif meta_type == 0x03 and not title:
                    title = meta_data.decode("utf-8", errors="replace").strip()
                elif meta_type == 0x2F:
                    break
            elif status in (0xF0, 0xF7):
                sysex_len, pos = _decode_vlq(data, pos)
                pos += sysex_len
            else:
                msg_type = status & 0xF0
                ch = status & 0x0F
                if msg_type in (0xC0, 0xD0):
                    # 1-data-byte channel messages (Program Change, Channel Pressure)
                    pos += 1
                elif msg_type in (0x80, 0x90, 0xA0, 0xB0, 0xE0):
                    if pos + 1 >= chunk_end:
                        break
                    d1 = data[pos]
                    d2 = data[pos + 1]
                    pos += 2
                    if msg_type == 0x90 and d2 > 0:
                        raw_note_events.append((abs_tick, ch, d1, d2, True))
                    elif msg_type == 0x80 or (msg_type == 0x90 and d2 == 0):
                        raw_note_events.append((abs_tick, ch, d1, 0, False))

    tempo_changes.sort(key=lambda item: item[0])
    initial_bpm = (60_000_000.0 / tempo_changes[0][1]) if tempo_changes else DEFAULT_TEMPO_BPM

    # Pair note-on and note-off events in chronological order
    # Sort note-offs before note-ons at the exact same tick
    raw_note_events.sort(key=lambda item: (item[0], 1 if item[4] else 0))
    active: dict[tuple[int, int], deque[tuple[int, int]]] = defaultdict(deque)
    notes: list[MidiNote] = []

    for tick, ch, pitch, vel, is_on in raw_note_events:
        key = (ch, pitch)
        if is_on:
            active[key].append((tick, vel))
        elif active[key]:
            start_tick, start_vel = active[key].popleft()
            start_sec = _ticks_to_seconds(start_tick, tempo_changes, ppqn)
            end_sec = _ticks_to_seconds(tick, tempo_changes, ppqn)
            dur_sec = max(0.01, end_sec - start_sec)
            notes.append(
                MidiNote(
                    pitch=pitch,
                    start_sec=start_sec,
                    duration_sec=dur_sec,
                    velocity=start_vel,
                    channel=ch,
                )
            )

    notes.sort(key=lambda n: (n.start_sec, n.channel, n.pitch))
    return MidiScore(notes=notes, tempo_bpm=round(initial_bpm, 2), ppqn=ppqn, title=title)


__all__ = [
    "DEFAULT_PPQN",
    "DEFAULT_TEMPO_BPM",
    "DRUM_CHANNEL",
    "MidiNote",
    "MidiScore",
    "midi_pitch_to_freq",
    "note_name_to_midi",
    "read_midi",
    "write_midi",
]
