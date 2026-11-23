"""Unit tests for the media_studio pack operations."""

import wave
from pathlib import Path

import pytest
from media_studio.audio import AudioEchoFilter, ChordProgression, ToneSynth
from media_studio.image import CardOrPoster, GeometricPattern, ImageFilterOp, MandelbrotFractal
from media_studio.inspect import AudioWaveformVisualizer, MediaMetadataInspector
from PIL import Image


def test_tone_synth_and_echo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    synth = ToneSynth()
    res = synth.run(waveform="sine", frequency=440, duration_sec=0.5, volume=0.5)
    audio_path = Path(res["audio"])
    assert audio_path.is_file()

    with wave.open(str(audio_path), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getframerate() == 44100
        assert wf.getnframes() > 0

    echo = AudioEchoFilter()
    echo_res = echo.run(audio=audio_path, delay_ms=100, decay=0.3, repeats=2)
    echo_path = Path(echo_res["filtered_audio"])
    assert echo_path.is_file()

    with wave.open(str(echo_path), "rb") as wf:
        assert wf.getnframes() > 0


def test_chord_progression(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    chord = ChordProgression()
    res = chord.run(progression="pop_chords", tempo_bpm=120, duration_sec=1.0)
    audio_path = Path(res["audio"])
    assert audio_path.is_file()


def test_mandelbrot_and_filter_and_poster(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    fractal = MandelbrotFractal()
    f_res = fractal.run(palette="neon_glow", width=200, height=200, max_iter=30, zoom=1.0)
    img_path = Path(f_res["image"])
    assert img_path.is_file()

    with Image.open(img_path) as im:
        assert im.size == (200, 200)

    f_op = ImageFilterOp()
    filtered_res = f_op.run(image=img_path, filter_type="sepia")
    filtered_path = Path(filtered_res["filtered_image"])
    assert filtered_path.is_file()

    poster_op = CardOrPoster()
    poster_res = poster_op.run(
        image=filtered_path, title="Test Art", subtitle="Sample Card", badge="VIP"
    )
    poster_path = Path(poster_res["card"])
    assert poster_path.is_file()

    with Image.open(poster_path) as im:
        assert im.size[0] > 200
        assert im.size[1] > 200


def test_geometric_pattern(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    pattern = GeometricPattern()
    res = pattern.run(pattern="gradient_wave", width=200, height=200)
    pattern_path = Path(res["image"])
    assert pattern_path.is_file()


def test_media_inspector(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    # Create dummy audio and image
    synth = ToneSynth()
    aud = synth.run(frequency=220, duration_sec=0.2)["audio"]

    pattern = GeometricPattern()
    img = pattern.run(width=100, height=100)["image"]

    inspector = MediaMetadataInspector()
    report = inspector.run(image=img, audio=aud)

    summary_file = Path(report["summary"])
    metadata_file = Path(report["metadata"])

    assert summary_file.is_file()
    assert metadata_file.is_file()

    summary_text = summary_file.read_text(encoding="utf-8")
    assert "# Media Studio Inspection Report" in summary_text
    assert "Image Dimensions" in summary_text
    assert "Audio Duration" in summary_text


def test_audio_waveform_visualizer_mono_and_stereo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    # 1. Mono WAV
    synth = ToneSynth()
    mono_wav = synth.run(frequency=440, duration_sec=0.5)["audio"]
    vis = AudioWaveformVisualizer()
    res_mono = vis.run(audio=mono_wav, width=400, height=150, theme="cyan")
    assert Path(res_mono["waveform"]).is_file()

    # 2. Stereo WAV (2-channel)
    stereo_path = tmp_path / "stereo_test.wav"
    with wave.open(str(stereo_path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        # 1000 frames of stereo
        payload = bytearray()
        for _ in range(1000):
            payload.extend(b"\x00\x10\x00\x20")
        wf.writeframes(bytes(payload))

    res_stereo = vis.run(audio=stereo_path, width=400, height=200, theme="violet")
    assert Path(res_stereo["waveform"]).is_file()
    with Image.open(res_stereo["waveform"]) as im:
        assert im.size == (400, 200)
