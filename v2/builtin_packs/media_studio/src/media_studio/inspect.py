"""Media metadata extraction and report generation in ``media_studio``."""

from __future__ import annotations

import json
import math
import struct
import wave
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict

from PIL import Image, ImageDraw
from plynx_sdk import AudioWav, ImageFile, JsonFile, MarkdownFile, Op, Range

THEMES = {
    "emerald": {
        "primary": (16, 185, 129),
        "secondary": (52, 211, 153),
        "highlight": (167, 243, 208),
        "grid": (39, 39, 42),
    },
    "cyan": {
        "primary": (6, 182, 212),
        "secondary": (56, 189, 248),
        "highlight": (186, 230, 253),
        "grid": (39, 39, 42),
    },
    "violet": {
        "primary": (139, 92, 246),
        "secondary": (167, 139, 250),
        "highlight": (221, 214, 254),
        "grid": (39, 39, 42),
    },
    "amber": {
        "primary": (245, 158, 11),
        "secondary": (251, 191, 36),
        "highlight": (253, 230, 138),
        "grid": (39, 39, 42),
    },
}


def _read_wav_channels(path: Path) -> tuple[int, list[list[float]]]:
    """Read a WAV file into per-channel normalized float samples (-1.0 to 1.0).

    Supports 16-bit, 24-bit, and 32-bit PCM/float WAV files.
    """
    with wave.open(str(path), "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        sample_rate = wf.getframerate()
        n_frames = wf.getnframes()
        raw_data = wf.readframes(n_frames)

    channels: list[list[float]] = [[] for _ in range(n_channels)]

    if sampwidth == 2:
        count = len(raw_data) // 2
        shorts = struct.unpack(f"<{count}h", raw_data)
        for i, val in enumerate(shorts):
            channels[i % n_channels].append(val / 32768.0)
    elif sampwidth == 3:
        # 24-bit PCM
        for i in range(0, len(raw_data) - 2, 3):
            val = int.from_bytes(raw_data[i:i + 3], byteorder="little", signed=True)
            ch_idx = (i // 3) % n_channels
            channels[ch_idx].append(val / 8388608.0)
    elif sampwidth == 4:
        # Check if 32-bit float or 32-bit int
        # Usually standard WAV format 3 is IEEE float, format 1 is PCM int.
        # Try unpacking float first, check range:
        try:
            count = len(raw_data) // 4
            floats = struct.unpack(f"<{count}f", raw_data)
            max_val = max(abs(f) for f in floats[:1000]) if floats else 0.0
            if max_val <= 1.5:
                for i, val in enumerate(floats):
                    channels[i % n_channels].append(float(val))
            else:
                ints = struct.unpack(f"<{count}i", raw_data)
                for i, val in enumerate(ints):
                    channels[i % n_channels].append(val / 2147483648.0)
        except Exception:
            count = len(raw_data) // 4
            ints = struct.unpack(f"<{count}i", raw_data)
            for i, val in enumerate(ints):
                channels[i % n_channels].append(val / 2147483648.0)
    else:
        # Fallback
        for ch in range(n_channels):
            channels[ch] = [0.0] * n_frames

    return sample_rate, channels


class AudioWaveformVisualizer(Op):
    """Render a soundwave amplitude plot image of a mono or stereo audio track."""

    TITLE = "Audio Waveform Visualizer"
    CATEGORY = "Inspect & Visualize"
    CACHEABLE = True

    class Outputs(TypedDict):
        waveform: ImageFile

    def run(
        self,
        audio: AudioWav,
        width: Annotated[int, Range(300, 2400)] = 800,
        height: Annotated[int, Range(100, 800)] = 240,
        theme: Literal["emerald", "cyan", "violet", "amber"] = "emerald",
    ) -> Outputs:
        _sample_rate, ch_samples = _read_wav_channels(Path(audio))
        n_channels = len(ch_samples)
        colors = THEMES.get(theme, THEMES["emerald"])

        img = Image.new("RGB", (width, height), color=(18, 18, 22))
        draw = ImageDraw.Draw(img)

        # Draw border
        draw.rectangle([(0, 0), (width - 1, height - 1)], outline=(40, 40, 48), width=1)

        total_samples = len(ch_samples[0]) if n_channels > 0 and len(ch_samples[0]) > 0 else 0
        if total_samples == 0:
            out_path = Path("waveform.png")
            img.save(str(out_path), "PNG")
            return {"waveform": out_path}

        panel_height = height // n_channels
        chunk_size = max(1, total_samples // width)

        for ch in range(n_channels):
            samples = ch_samples[ch]
            top_y = ch * panel_height
            bot_y = top_y + panel_height
            cy = (top_y + bot_y) // 2
            half_h = max(2, (panel_height // 2) - 6)

            # Grid lines
            upper_grid_y = cy - int(half_h * 0.5)
            lower_grid_y = cy + int(half_h * 0.5)
            draw.line([(0, cy), (width, cy)], fill=colors["grid"], width=1)
            draw.line([(0, upper_grid_y), (width, upper_grid_y)], fill=(28, 28, 32), width=1)
            draw.line([(0, lower_grid_y), (width, lower_grid_y)], fill=(28, 28, 32), width=1)

            if n_channels > 1:
                ch_label = "L" if ch == 0 else "R"
                draw.text((6, top_y + 4), ch_label, fill=(100, 100, 110))

            for x in range(width):
                start = x * chunk_size
                end = min(total_samples, start + chunk_size)
                if start >= total_samples or start >= end:
                    continue
                chunk = samples[start:end]
                peak = max(abs(s) for s in chunk)
                sq_sum = sum(s * s for s in chunk)
                rms = math.sqrt(sq_sum / len(chunk))

                peak_h = max(1, int(peak * half_h))
                rms_h = max(1, int(rms * half_h))

                # Draw peak bar
                draw.line([(x, cy - peak_h), (x, cy + peak_h)], fill=colors["secondary"], width=1)
                # Draw RMS energy
                draw.line([(x, cy - rms_h), (x, cy + rms_h)], fill=colors["primary"], width=1)

        out_path = Path("waveform.png")
        img.save(str(out_path), "PNG")
        return {"waveform": out_path}


class MediaMetadataInspector(Op):
    """Inspect image and audio artifacts, extracting dimensions, duration, and metadata."""

    TITLE = "Media Metadata Inspector"
    CATEGORY = "Inspect & Visualize"
    CACHEABLE = True

    class Outputs(TypedDict):
        summary: MarkdownFile
        metadata: JsonFile

    def run(
        self,
        image: ImageFile | None = None,
        audio: AudioWav | None = None,
    ) -> Outputs:
        data: dict[str, Any] = {
            "has_image": image is not None,
            "has_audio": audio is not None,
            "image": None,
            "audio": None,
        }

        md_lines = [
            "# Media Studio Inspection Report",
            "",
            "Artifact properties generated by **Plynx Media Studio**.",
            "",
            "## Summary Table",
            "",
            "| Property | Value |",
            "| :--- | :--- |",
        ]

        if image is not None and Path(image).is_file():
            img_path = Path(image)
            with Image.open(img_path) as im:
                w, h = im.size
                fmt = im.format or "PNG"
                mode = im.mode
            file_kb = round(img_path.stat().st_size / 1024.0, 2)
            data["image"] = {
                "filename": img_path.name,
                "width": w,
                "height": h,
                "format": fmt,
                "mode": mode,
                "file_size_kb": file_kb,
            }
            md_lines.extend(
                [
                    f"| **Image File** | `{img_path.name}` |",
                    f"| **Image Dimensions** | {w} x {h} px |",
                    f"| **Color Mode** | `{mode}` ({fmt}) |",
                    f"| **Image File Size** | {file_kb} KB |",
                ]
            )

        if audio is not None and Path(audio).is_file():
            aud_path = Path(audio)
            with wave.open(str(aud_path), "rb") as wf:
                ch = wf.getnchannels()
                rate = wf.getframerate()
                frames = wf.getnframes()
                dur = round(frames / float(rate), 2)
                width_bytes = wf.getsampwidth()
            file_kb = round(aud_path.stat().st_size / 1024.0, 2)
            data["audio"] = {
                "filename": aud_path.name,
                "channels": ch,
                "sample_rate_hz": rate,
                "bit_depth": width_bytes * 8,
                "duration_sec": dur,
                "file_size_kb": file_kb,
            }
            md_lines.extend(
                [
                    f"| **Audio File** | `{aud_path.name}` |",
                    f"| **Audio Duration** | {dur} seconds |",
                    f"| **Audio Sample Rate** | {rate} Hz ({ch} channel) |",
                    f"| **Audio Bit Depth** | {width_bytes * 8}-bit PCM |",
                    f"| **Audio File Size** | {file_kb} KB |",
                ]
            )

        md_lines.extend(
            [
                "",
                "---",
                "*Inspected with Plynx v2 Node Pack.*",
            ]
        )

        out_summary = Path("summary.md")
        out_summary.write_text("\n".join(md_lines), encoding="utf-8")

        out_meta = Path("metadata.json")
        out_meta.write_text(json.dumps(data, indent=2), encoding="utf-8")

        return {
            "summary": out_summary,
            "metadata": out_meta,
        }


__all__ = ["AudioWaveformVisualizer", "MediaMetadataInspector"]
