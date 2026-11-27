"""Unit and cross-pack pipeline integration tests for ``podcast_studio`` pack."""

from __future__ import annotations

import platform
import shutil
import wave
from pathlib import Path

import numpy as np
import pytest
from media_studio.inspect import AudioWaveformVisualizer
from pedalboard_studio.effects import AudioMixer
from pedalboard_studio.score import ChordProgressionScore
from pedalboard_studio.synth import PolySynth
from PIL import Image
from plynx.registry.pack_registry import PackRegistry
from plynx.workflow.models import load_workflow
from plynx.workflow.validator import validate_workflow
from podcast_studio.notes import ShowNotesGenerator
from podcast_studio.voice import TextToSpeech


def test_text_to_speech_synthesis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify TextToSpeech generates 44.1kHz 16-bit PCM WAV on macOS and fails cleanly otherwise."""
    monkeypatch.chdir(tmp_path)
    tts_op = TextToSpeech()
    if platform.system() != "Darwin" or shutil.which("say") is None:
        with pytest.raises(RuntimeError, match="macOS"):
            tts_op.run(text="Hello from non-macOS.", voice="Samantha", rate=180)
        return

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


def test_text_to_speech_fails_when_say_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify TextToSpeech raises RuntimeError rather than returning fake fallback audio."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("podcast_studio.voice.shutil.which", lambda _name: None)
    with pytest.raises(RuntimeError, match="say"):
        TextToSpeech().run(text="Should fail cleanly.")


def test_podcast_cross_pack_full_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify cross-pack pipeline: TTS + MIDI Rhodes BGM -> AudioMixer -> Waveform + ShowNotes."""
    if platform.system() != "Darwin" or shutil.which("say") is None:
        pytest.skip("Cross-pack podcast TTS synthesis requires macOS 'say'")
    monkeypatch.chdir(tmp_path)

    # 1. Voiceover (podcast_studio)
    tts_op = TextToSpeech()
    tts_res = tts_op.run(
        text="Episode 1. Today we discuss graph workflows.",
        voice="Samantha",
        rate=180,
    )
    voice_wav = tts_res["voiceover"]

    # 2. MIDI Chord Progression -> PolySynth BGM (pedalboard_studio)
    score_res = ChordProgressionScore().run(
        progression="ii7 - V7 - Imaj7 - vi7",
        key="C",
        bpm=96,
        bars=2,
        voicing_style="arpeggio",
    )
    bgm_res = PolySynth().run(midi=score_res["midi"], waveform="rhodes", cutoff_hz=2400.0)
    bgm_wav = bgm_res["audio"]

    # 3. Mixing & Ducking (pedalboard_studio/effects:AudioMixer)
    mixer_op = AudioMixer()
    mix_res = mixer_op.run(
        track_1=voice_wav,
        track_2=bgm_wav,
        track_1_gain=1.0,
        track_2_gain=0.35,
        ducking_enabled=True,
        ducking_amount_db=12.0,
        lead_in_sec=0.5,
        tail_sec=1.0,
        loop_background=True,
    )
    mixed_wav = mix_res["mixed_audio"]
    assert mixed_wav.is_file()
    assert mix_res["total_duration_sec"] >= 1.5

    # Stereo BGM + Mono Voice -> Stereo output preserved!
    with wave.open(str(mixed_wav), "rb") as wf:
        assert wf.getframerate() == 44100
        assert wf.getnchannels() == 2

    # 4. Waveform Visualization (media_studio)
    vis_op = AudioWaveformVisualizer()
    vis_res = vis_op.run(audio=mixed_wav, width=600, height=200, theme="emerald")
    wave_png = vis_res["waveform"]
    assert wave_png.is_file()
    with Image.open(str(wave_png)) as img:
        assert img.size == (600, 200)
        assert img.format == "PNG"

    # 5. Show Notes Generator (podcast_studio)
    notes_op = ShowNotesGenerator()
    notes_res = notes_op.run(
        title="Episode 1: Graph Workflows",
        podcast_name="Plynx Podcast",
        host="Plynx Host",
        summary="A test of autonomous podcast pipeline generation.",
        chapters="00:00 - Introduction\n00:03 - Graph Scheduling\n00:06 - Outro",
        transcript="Episode 1. Today we discuss graph workflows.",
        production_notes="- Synthesized on macOS.",
    )
    notes_md = notes_res["show_notes"]
    assert notes_md.is_file()
    assert notes_res["chapter_count"] == 3
    content = notes_md.read_text(encoding="utf-8")
    assert "# Plynx Podcast" in content
    assert "Episode 1: Graph Workflows" in content
    assert "macOS" in content


def test_podcast_pack_slim_discovery_and_workflow() -> None:
    """Verify slimmed podcast_studio ops and cross-pack podcast_producer_macos.yaml validation."""
    workspace_root = Path(__file__).resolve().parent.parent
    registry = PackRegistry(workspace_root)

    # Slimmed podcast_studio has only TextToSpeech and ShowNotesGenerator
    assert registry.get("podcast_studio/voice:TextToSpeech") is not None
    assert registry.get("podcast_studio/notes:ShowNotesGenerator") is not None
    assert registry.get("podcast_studio/music:BGMTrackGenerator") is None
    assert registry.get("podcast_studio/mixer:AudioMixer") is None

    # Shared AudioMixer lives in pedalboard_studio
    assert registry.get("pedalboard_studio/effects:AudioMixer") is not None

    workflow_path = workspace_root / "examples" / "workflows" / "podcast_producer_macos.yaml"
    assert workflow_path.is_file()
    doc = load_workflow(workflow_path)
    issues = validate_workflow(doc, registry=registry)
    errors = [issue for issue in issues if issue.severity == "error"]
    assert not errors, f"Workflow validation errors: {errors}"


def test_audio_mixer_stereo_preservation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify AudioMixer preserves stereo when inputs contain stereo audio."""
    monkeypatch.chdir(tmp_path)

    voice_path = tmp_path / "voice.wav"
    with wave.open(str(voice_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes((np.sin(np.linspace(0, 100, 44100)) * 10000).astype(np.int16).tobytes())

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
    res = mixer.run(track_1=voice_path, track_2=bgm_path, ducking_enabled=True)
    mixed_path = res["mixed_audio"]
    with wave.open(str(mixed_path), "rb") as wf:
        assert wf.getnchannels() == 2, f"Expected 2 channels, got {wf.getnchannels()}"
