"""Unit and pipeline integration tests for ``podcast_studio`` pack."""

from __future__ import annotations

import wave
from pathlib import Path

import pytest
from media_studio.inspect import AudioWaveformVisualizer
from PIL import Image
from plynx.registry.pack_registry import PackRegistry
from plynx.workflow.models import load_workflow
from plynx.workflow.validator import validate_workflow
from podcast_studio.mixer import AudioMixer
from podcast_studio.music import BGMTrackGenerator
from podcast_studio.notes import ShowNotesGenerator
from podcast_studio.voice import TextToSpeech


def test_text_to_speech_synthesis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify TextToSpeech generates a valid 44.1kHz 16-bit PCM voiceover WAV."""
    monkeypatch.chdir(tmp_path)
    tts_op = TextToSpeech()
    res = tts_op.run(
        text="Hello and welcome to the Plynx podcast. This is a local synthesis test.",
        voice="Samantha",
        rate=180,
    )
    wav_path = res["voiceover"]
    assert wav_path.is_file()
    assert res["character_count"] > 0

    with wave.open(str(wav_path), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 44100
        assert wf.getnframes() > 0


def test_bgm_track_generator(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify BGMTrackGenerator synthesizes lo-fi background loop."""
    monkeypatch.chdir(tmp_path)
    bgm_op = BGMTrackGenerator()
    res = bgm_op.run(mood="lofi_chill", duration_sec=4.0, tempo_bpm=90, volume=0.3)
    bgm_path = res["bgm"]
    assert bgm_path.is_file()

    with wave.open(str(bgm_path), "rb") as wf:
        assert wf.getframerate() == 44100
        frames = wf.getnframes()
        dur = frames / 44100.0
        assert 3.8 <= dur <= 4.2


def test_podcast_full_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify end-to-end podcast production chain: Speech -> BGM -> Mix -> Waveform -> ShowNotes."""
    monkeypatch.chdir(tmp_path)

    # 1. Voiceover
    tts_op = TextToSpeech()
    tts_res = tts_op.run(
        text="Episode 1. Today we discuss graph workflows.",
        voice="Samantha",
        rate=180,
    )
    voice_wav = tts_res["voiceover"]

    # 2. BGM
    bgm_op = BGMTrackGenerator()
    bgm_res = bgm_op.run(mood="lofi_chill", duration_sec=8.0, volume=0.3)
    bgm_wav = bgm_res["bgm"]

    # 3. Mixing & Ducking
    mixer_op = AudioMixer()
    mix_res = mixer_op.run(
        voiceover=voice_wav,
        bgm=bgm_wav,
        speech_volume=1.0,
        bgm_volume=0.3,
        ducking_amount_db=12.0,
        lead_in_sec=0.5,
        tail_sec=1.0,
    )
    mixed_wav = mix_res["mixed_audio"]
    assert mixed_wav.is_file()
    assert mix_res["speech_duration_sec"] > 0
    assert mix_res["total_duration_sec"] >= mix_res["speech_duration_sec"]

    with wave.open(str(mixed_wav), "rb") as wf:
        assert wf.getframerate() == 44100
        assert wf.getnchannels() == 1

    # 4. Waveform Visualization
    vis_op = AudioWaveformVisualizer()
    vis_res = vis_op.run(audio=mixed_wav, width=600, height=200, theme="emerald")
    wave_png = vis_res["waveform"]
    assert wave_png.is_file()
    with Image.open(str(wave_png)) as img:
        assert img.size == (600, 200)
        assert img.format == "PNG"

    # 5. Show Notes Generator
    notes_op = ShowNotesGenerator()
    notes_res = notes_op.run(
        title="Episode 1: Graph Workflows",
        podcast_name="Plynx Podcast",
        host="Plynx Host",
        summary="A test of autonomous podcast pipeline generation.",
        chapters="00:00 - Introduction\n00:03 - Graph Scheduling\n00:06 - Outro",
        transcript="Episode 1. Today we discuss graph workflows.",
    )
    notes_md = notes_res["show_notes"]
    assert notes_md.is_file()
    assert notes_res["chapter_count"] == 3
    content = notes_md.read_text(encoding="utf-8")
    assert "# Plynx Podcast" in content
    assert "Episode 1: Graph Workflows" in content
    assert "macOS" in content


def test_podcast_pack_discovery_and_workflow() -> None:
    """Verify registry discovers podcast_studio ops and validates workflow."""
    workspace_root = Path(__file__).resolve().parent.parent
    registry = PackRegistry(workspace_root)

    expected_ops = [
        "podcast_studio/voice:TextToSpeech",
        "podcast_studio/music:BGMTrackGenerator",
        "podcast_studio/mixer:AudioMixer",
                "podcast_studio/notes:ShowNotesGenerator",
    ]
    for op_id in expected_ops:
        entry = registry.get(op_id)
        assert entry is not None, f"Expected {op_id} to be discovered in registry"

    workflow_path = workspace_root / "examples" / "workflows" / "podcast_producer_macos.yaml"
    assert workflow_path.is_file()
    doc = load_workflow(workflow_path)
    issues = validate_workflow(doc, registry=registry)
    errors = [issue for issue in issues if issue.severity == "error"]
    assert not errors, f"Workflow validation errors: {errors}"


def test_audio_mixer_stereo_preservation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify AudioMixer preserves stereo when inputs contain stereo audio."""
    monkeypatch.chdir(tmp_path)
    import numpy as np

    # Create mono voice
    voice_path = tmp_path / "voice.wav"
    with wave.open(str(voice_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes((np.sin(np.linspace(0, 100, 44100)) * 10000).astype(np.int16).tobytes())

    # Create stereo bgm
    bgm_path = tmp_path / "bgm_stereo.wav"
    with wave.open(str(bgm_path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        stereo_data = np.zeros((44100, 2), dtype=np.int16)
        stereo_data[:, 0] = (np.sin(np.linspace(0, 50, 44100)) * 8000).astype(np.int16)
        stereo_data[:, 1] = (np.cos(np.linspace(0, 50, 44100)) * 8000).astype(np.int16)
        wf.writeframes(stereo_data.tobytes())

    mixer = AudioMixer()
    res = mixer.run(voiceover=voice_path, bgm=bgm_path)
    mixed_path = res["mixed_audio"]
    with wave.open(str(mixed_path), "rb") as wf:
        assert wf.getnchannels() == 2, f"Expected 2 channels, got {wf.getnchannels()}"
