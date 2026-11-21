"""Unit and integration tests for ``pedalboard_studio`` pack and Bach Prelude workflow."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from media_studio.inspect import AudioWaveformVisualizer
from pedalboard.io import AudioFile
from pedalboard_studio.effects import (
    PedalboardChorus,
    PedalboardDelay,
    PedalboardReverb,
    PedalboardToneFilter,
)
from pedalboard_studio.inspect import AudioStats
from pedalboard_studio.mastering import PedalboardMastering
from pedalboard_studio.synth import AcousticPianoSynth, BachPreludeScore
from PIL import Image
from plynx.registry.pack_registry import PackRegistry
from plynx.workflow.models import load_workflow
from plynx.workflow.validator import validate_workflow


def test_bach_prelude_score_generation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify BachPreludeScore generates authentic 35-bar BWV 846 note events."""
    monkeypatch.chdir(tmp_path)
    score_op = BachPreludeScore()

    # Test short 2-bar preview
    res_short = score_op.run(tempo_bpm=120, bars_count=2, dynamics="flat")
    score_path = res_short["score"]
    assert score_path.is_file()
    data = json.loads(score_path.read_text(encoding="utf-8"))
    assert data["bars_count"] == 2
    assert data["notes_count"] == 32  # 16 notes per bar * 2 = 32
    assert data["notes"][0]["pitch"] == 48  # C3
    assert data["notes"][1]["pitch"] == 52  # E3
    assert data["notes"][2]["pitch"] == 55  # G3

    # Test full 35-bar score
    res_full = score_op.run(tempo_bpm=84, bars_count=35, dynamics="expressive")
    full_data = json.loads(res_full["score"].read_text(encoding="utf-8"))
    assert full_data["bars_count"] == 35
    assert full_data["total_duration_sec"] > 50.0


def test_pedalboard_studio_full_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the entire synthesis -> DSP effects -> mastering -> visualization pipeline."""
    monkeypatch.chdir(tmp_path)

    # 1. Score: 2 bars for fast test execution
    score_op = BachPreludeScore()
    score_res = score_op.run(tempo_bpm=120, bars_count=2)
    score_file = score_res["score"]

    # 2. Synthesis: Acoustic piano
    synth_op = AcousticPianoSynth()
    synth_res = synth_op.run(score=score_file, sample_rate=44100, brightness=1.1)
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
        assert float(np.max(audio_data)) <= 1.0  # Limiter works!

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
