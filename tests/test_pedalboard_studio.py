"""Unit and integration tests for ``pedalboard_studio`` MIDI ecosystem and audio ops."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from media_studio.inspect import AudioWaveformVisualizer
from pedalboard.io import AudioFile
from pedalboard_studio.effects import (
    AudioMixer,
    PedalboardChorus,
    PedalboardDelay,
    PedalboardReverb,
    PedalboardToneFilter,
)
from pedalboard_studio.inspect import AudioStats, MidiPianoRoll
from pedalboard_studio.mastering import PedalboardMastering
from pedalboard_studio.midi_io import DRUM_CHANNEL, MidiNote, MidiScore, read_midi, write_midi
from pedalboard_studio.score import ChordProgressionScore, MidiMerge, MidiTransform, StepSequencer
from pedalboard_studio.synth import (
    AcousticPianoSynth,
    DrumSynth,
    PolySynth,
)
from PIL import Image
from plynx.registry.pack_registry import PackRegistry
from plynx.workflow.models import Workflow, load_workflow
from plynx.workflow.validator import validate_workflow


def test_midi_io_round_trip(tmp_path: Path) -> None:
    """Verify pure-Python SMF writer and reader preserve multi-channel notes and tempo."""
    original = MidiScore(
        notes=[
            MidiNote(pitch=60, start_sec=0.0, duration_sec=0.5, velocity=100, channel=0),
            MidiNote(pitch=64, start_sec=0.25, duration_sec=0.5, velocity=85, channel=1),
            MidiNote(
                pitch=36, start_sec=0.0, duration_sec=0.25, velocity=120, channel=DRUM_CHANNEL
            ),
        ],
        tempo_bpm=120.0,
        title="Round Trip Test",
    )
    mid_path = write_midi(tmp_path / "test.mid", original)
    raw = mid_path.read_bytes()
    assert raw[:4] == b"MThd"
    assert b"MTrk" in raw

    parsed = read_midi(mid_path)
    assert parsed.tempo_bpm == pytest.approx(120.0, abs=0.5)
    assert parsed.title == "Round Trip Test"
    assert len(parsed.notes) == 3

    by_pitch = {n.pitch: n for n in parsed.notes}
    assert by_pitch[60].channel == 0
    assert by_pitch[60].duration_sec == pytest.approx(0.5, abs=0.02)
    assert by_pitch[64].channel == 1
    assert by_pitch[36].channel == DRUM_CHANNEL
    assert by_pitch[36].velocity == 120


def test_midi_transform_and_bwv_846_sample(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify MidiTransform adjusts tempo, transposition, dynamics, and bar count on bwv_846 sample."""
    sample_mid = (
        Path(__file__).resolve().parent.parent
        / "examples"
        / "samples"
        / "bwv_846_prelude_c_major.mid"
    )
    assert sample_mid.is_file()

    monkeypatch.chdir(tmp_path)
    transform_op = MidiTransform()

    # Short 2-bar preview at 120 BPM transposed up 2 semitones
    res_short = transform_op.run(
        midi=sample_mid,
        tempo_bpm=120,
        transpose_semitones=2,
        dynamics="flat",
        max_bars=2,
    )
    midi_path = res_short["midi"]
    assert midi_path.is_file()
    parsed = read_midi(midi_path)
    assert len(parsed.notes) == 32  # 16 notes per bar * 2 = 32
    assert parsed.notes[0].pitch == 50  # C3 (48) + 2 semitones = D3 (50)
    assert parsed.notes[1].pitch == 54  # E3 (52) + 2 = F#3 (54)

    meta = json.loads(res_short["metadata"].read_text(encoding="utf-8"))
    assert meta["notes_count"] == 32
    assert meta["tempo_bpm"] == 120

    # Full 35-bar score at 84 BPM
    res_full = transform_op.run(
        midi=sample_mid,
        tempo_bpm=84,
        dynamics="expressive",
        max_bars=35,
    )
    full_meta = json.loads(res_full["metadata"].read_text(encoding="utf-8"))
    assert full_meta["total_duration_sec"] > 50.0


@pytest.mark.parametrize("voicing_style", ["block", "arpeggio", "waltz", "strumming"])
def test_chord_progression_score_voicings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, voicing_style: str
) -> None:
    """Verify ChordProgressionScore parses Roman numerals and renders all voicing styles."""
    monkeypatch.chdir(tmp_path)
    res = ChordProgressionScore().run(
        progression="vi - IV - I - V",
        key="Am",
        bpm=110,
        bars=4,
        voicing_style=voicing_style,  # type: ignore[arg-type]
    )
    assert res["midi"].is_file()
    assert res["note_count"] > 0
    parsed = read_midi(res["midi"])
    assert len(parsed.notes) == res["note_count"]
    assert parsed.tempo_bpm == pytest.approx(110.0, abs=0.5)


def test_chord_progression_jazz_and_explicit_chords(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify jazz 7th Roman numerals and explicit chord names parse cleanly."""
    monkeypatch.chdir(tmp_path)
    res_jazz = ChordProgressionScore().run(progression="ii7 - V7 - Imaj7 - VI7", key="F#", bars=4)
    assert read_midi(res_jazz["midi"]).notes

    res_explicit = ChordProgressionScore().run(
        progression="Am7 - Fmaj7 - Cmaj7 - G7", key="C", bars=4
    )
    assert read_midi(res_explicit["midi"]).notes


def test_step_sequencer_and_midi_merge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify StepSequencer outputs Ch 9 drums + melodic bass, and MidiMerge combines N tracks."""
    monkeypatch.chdir(tmp_path)

    seq_res = StepSequencer().run(
        pattern=(
            "kick:  X...x...X...x...\n"
            "snare: ....x.......x...\n"
            "hat:   x.o.x.o.x.o.x.o.\n"
            "bass:  C2-.C2..G1-.A1.."
        ),
        bpm=120,
        bars=2,
        swing=0.15,
    )
    seq_midi = read_midi(seq_res["midi"])
    drum_notes = [n for n in seq_midi.notes if n.channel == DRUM_CHANNEL]
    bass_notes = [n for n in seq_midi.notes if n.channel != DRUM_CHANNEL]
    assert len(drum_notes) > 0
    assert len(bass_notes) > 0

    chords_res = ChordProgressionScore().run(
        progression="I - V - vi - IV", key="C", bpm=120, bars=2
    )
    extra_res = ChordProgressionScore().run(
        progression="I - IV", key="C", bpm=120, bars=1, octave=5
    )

    # Merge 3 tracks using dynamic extra input
    merge_res = MidiMerge().run(
        track_a=seq_res["midi"],
        track_b=chords_res["midi"],
        lead=extra_res["midi"],
    )
    assert merge_res["track_count"] == 3
    merged = read_midi(merge_res["midi"])
    assert len(merged.notes) == merge_res["note_count"]
    channels = {n.channel for n in merged.notes}
    assert DRUM_CHANNEL in channels
    melodic_channels = channels - {DRUM_CHANNEL}
    assert len(melodic_channels) >= 3  # bass, chords, lead on separate channels


def test_polysynth_drumsynth_multitrack_mixer_and_piano_roll(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify universal MIDI -> PolySynth + DrumSynth -> AudioMixer (3 tracks) -> PianoRoll."""
    monkeypatch.chdir(tmp_path)

    seq_res = StepSequencer().run(bpm=120, bars=1)
    chords_res = ChordProgressionScore().run(
        progression="vi - IV - I - V", key="C", bpm=120, bars=1
    )
    merged_res = MidiMerge().run(track_a=seq_res["midi"], track_b=chords_res["midi"])

    # Visual inspection: MidiPianoRoll
    roll_res = MidiPianoRoll().run(midi=merged_res["midi"], width=800, height=320)
    assert roll_res["piano_roll"].is_file()
    assert roll_res["note_count"] == merged_res["note_count"]
    with Image.open(str(roll_res["piano_roll"])) as img:
        assert img.size == (800, 320)
        assert img.format == "PNG"

    # Parallel synthesis from the SAME merged MIDI score!
    pad_wav = PolySynth().run(midi=merged_res["midi"], waveform="pad")["audio"]
    pluck_wav = PolySynth().run(midi=merged_res["midi"], waveform="pluck")["audio"]
    drum_wav = DrumSynth().run(midi=merged_res["midi"], kit="electronic_808")["audio"]

    # Mix 3 stereo tracks via dynamic extra input
    mix_res = AudioMixer().run(
        track_1=pad_wav,
        track_2=drum_wav,
        pluck=pluck_wav,
    )
    mixed_wav = mix_res["mixed_audio"]
    assert mixed_wav.is_file()
    with AudioFile(str(mixed_wav)) as f:
        assert f.num_channels == 2
        assert f.samplerate == 44100
        assert f.frames > 0


def test_midi_port_type_validation() -> None:
    """Verify validator accepts MidiFile -> MidiFile and rejects AudioWav -> MidiFile."""
    workspace_root = Path(__file__).resolve().parent.parent
    reg = PackRegistry(workspace_root)

    # Valid: ChordProgressionScore (MidiFile) -> PolySynth (MidiFile)
    valid_doc = Workflow.model_validate(
        {
            "version": 1,
            "name": "valid_midi",
            "nodes": {
                "score": {"op": "pedalboard_studio/score:ChordProgressionScore", "inputs": {}},
                "synth": {
                    "op": "pedalboard_studio/synth:PolySynth",
                    "inputs": {"midi": "$score.midi"},
                },
            },
        }
    )
    valid_errors = [i for i in validate_workflow(valid_doc, reg) if i.severity == "error"]
    assert not valid_errors

    # Invalid: PolySynth (AudioWav) -> AcousticPianoSynth (MidiFile)
    invalid_doc = Workflow.model_validate(
        {
            "version": 1,
            "name": "invalid_wav_to_midi",
            "nodes": {
                "score": {"op": "pedalboard_studio/score:ChordProgressionScore", "inputs": {}},
                "synth": {
                    "op": "pedalboard_studio/synth:PolySynth",
                    "inputs": {"midi": "$score.midi"},
                },
                "bad_piano": {
                    "op": "pedalboard_studio/synth:AcousticPianoSynth",
                    "inputs": {"midi": "$synth.audio"},
                },
            },
        }
    )
    invalid_errors = [i for i in validate_workflow(invalid_doc, reg) if i.severity == "error"]
    assert any("audio/wav" in err.message and "audio/midi" in err.message for err in invalid_errors)


def test_pedalboard_studio_full_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the entire MIDI score -> synthesis -> DSP effects -> mastering -> visuals pipeline."""
    monkeypatch.chdir(tmp_path)

    # 1. Score: 2 bars from canonical BWV 846 MIDI sample for fast test execution
    sample_mid = (
        Path(__file__).resolve().parent.parent
        / "examples"
        / "samples"
        / "bwv_846_prelude_c_major.mid"
    )
    score_res = MidiTransform().run(midi=sample_mid, tempo_bpm=120, max_bars=2)
    midi_file = score_res["midi"]

    # 2. Synthesis: Acoustic piano
    synth_op = AcousticPianoSynth()
    synth_res = synth_op.run(midi=midi_file, sample_rate=44100, brightness=1.1)
    dry_wav = synth_res["audio"]
    assert dry_wav.is_file()
    with AudioFile(str(dry_wav)) as f:
        assert f.samplerate == 44100
        assert f.num_channels == 2
        assert f.frames > 0

    # 3. Tone Filter
    filter_op = PedalboardToneFilter()
    filter_res = filter_op.run(audio=dry_wav, highpass_cutoff_hz=60.0, lowpass_cutoff_hz=12000.0)
    filtered_wav = filter_res["filtered_audio"]
    assert filtered_wav.is_file()

    # 4. Chorus
    chorus_op = PedalboardChorus()
    chorus_res = chorus_op.run(audio=filtered_wav, rate_hz=0.8, depth=0.3, mix=0.25)
    chorus_wav = chorus_res["chorus_audio"]
    assert chorus_wav.is_file()

    # 5. Delay
    delay_op = PedalboardDelay()
    delay_res = delay_op.run(audio=chorus_wav, delay_seconds=0.2, feedback=0.15, mix=0.2)
    delayed_wav = delay_res["delayed_audio"]
    assert delayed_wav.is_file()

    # 6. Reverb
    reverb_op = PedalboardReverb()
    reverb_res = reverb_op.run(audio=delayed_wav, room_size=0.6, damping=0.4, wet_level=0.3)
    reverb_wav = reverb_res["reverb_audio"]
    assert reverb_wav.is_file()

    # 7. Mastering
    master_op = PedalboardMastering()
    master_res = master_op.run(
        audio=reverb_wav,
        compressor_threshold_db=-18.0,
        gain_db=1.5,
        limiter_threshold_db=-0.5,
    )
    master_wav = master_res["mastered_audio"]
    assert master_wav.is_file()
    with AudioFile(str(master_wav)) as f:
        assert f.samplerate == 44100
        assert f.num_channels == 2
        audio_data = f.read(f.frames)
        assert float(np.max(audio_data)) <= 1.0

    # 8. Waveform Visualization
    vis_op = AudioWaveformVisualizer()
    vis_res = vis_op.run(audio=master_wav, width=600, height=240)
    wave_png = vis_res["waveform"]
    assert wave_png.is_file()
    with Image.open(str(wave_png)) as img:
        assert img.size == (600, 240)
        assert img.format == "PNG"

    # 9. Technical Audio Stats
    stats_op = AudioStats()
    stats_res = stats_op.run(audio=master_wav)
    stats_json = stats_res["stats"]
    assert stats_json.is_file()
    stats_data = json.loads(stats_json.read_text(encoding="utf-8"))
    assert stats_data["channels"] == 2
    assert stats_data["sample_rate"] == 44100
    assert "rms_dbfs" in stats_data
    assert "peak_dbfs" in stats_data


def test_bach_prelude_workflow_validation() -> None:
    """Verify that bach_prelude_c_major.yaml validates cleanly against the pack registry."""
    workspace_root = Path(__file__).resolve().parent.parent
    reg = PackRegistry(workspace_root)
    wf_path = workspace_root / "examples" / "workflows" / "bach_prelude_c_major.yaml"
    assert wf_path.is_file()

    wf = load_workflow(wf_path)
    issues = validate_workflow(wf, reg)
    error_issues = [issue for issue in issues if issue.severity == "error"]
    assert not error_issues, f"Validation errors found: {error_issues}"
