"""Generative image processing and card composition in ``media_studio``."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Annotated, Literal, TypedDict

from PIL import Image, ImageDraw, ImageFilter, ImageOps
from plynx_sdk import ImageFile, Op, Range


def _parse_hex_color(hex_str: str, default: tuple[int, int, int] = (38, 128, 235)) -> tuple[int, int, int]:
    """Parse hex color like '#2680eb' or '2680eb' into RGB tuple."""
    clean = hex_str.strip().lstrip("#")
    if len(clean) == 6:
        try:
            return int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16)
        except ValueError:
            pass
    return default


def _get_palette_color(t: float, palette: str) -> tuple[int, int, int]:
    """Return RGB color for normalized scalar t in [0.0, 1.0]."""
    if palette == "fire":
        r = int(min(255, t * 2.0 * 255))
        g = int(min(255, max(0, (t - 0.3) * 1.8 * 255)))
        b = int(min(255, max(0, (t - 0.7) * 3.3 * 255)))
        return (r, g, b)
    elif palette == "ocean":
        r = int(min(255, max(0, (t - 0.6) * 2.5 * 255)))
        g = int(min(255, (0.3 + 0.7 * t) * 255))
        b = int(min(255, (0.5 + 0.5 * t) * 255))
        return (r, g, b)
    elif palette == "psychedelic":
        r = int((0.5 + 0.5 * math.sin(6.28 * t)) * 255)
        g = int((0.5 + 0.5 * math.sin(6.28 * t + 2.09)) * 255)
        b = int((0.5 + 0.5 * math.sin(6.28 * t + 4.18)) * 255)
        return (r, g, b)
    elif palette == "grayscale":
        val = int(t * 255)
        return (val, val, val)
    else:  # neon_glow
        r = int((0.5 + 0.5 * math.cos(6.28 * t + 0.5)) * 255)
        g = int((0.5 + 0.5 * math.sin(6.28 * t + 1.2)) * 255)
        b = int(min(255, max(40, int(t * 255 * 1.2))))
        return (r, g, b)


class MandelbrotFractal(Op):
    """Generate a high-resolution Mandelbrot fractal art image."""

    TITLE = "Mandelbrot Fractal Art"
    CATEGORY = "Image"
    CACHEABLE = True

    class Outputs(TypedDict):
        image: ImageFile

    def run(
        self,
        palette: Literal["neon_glow", "fire", "ocean", "psychedelic", "grayscale"] = "neon_glow",
        width: Annotated[int, Range(200, 1000)] = 400,
        height: Annotated[int, Range(200, 1000)] = 400,
        max_iter: Annotated[int, Range(20, 300)] = 80,
        zoom: Annotated[float, Range(0.5, 5.0)] = 1.0,
    ) -> Outputs:
        img = Image.new("RGB", (width, height), (15, 15, 15))
        pixels = img.load()
        assert pixels is not None

        # Complex bounds centered on Seahorse Valley / interesting region
        cx, cy = -0.743643887037158704752191506114774, 0.131825904205311970493132056385139
        scale = 2.5 / (zoom * min(width, height))

        for py in range(height):
            y0 = cy + (py - height / 2.0) * scale
            for px in range(width):
                x0 = cx + (px - width / 2.0) * scale
                x, y = 0.0, 0.0
                iteration = 0
                while x * x + y * y <= 4.0 and iteration < max_iter:
                    xtemp = x * x - y * y + x0
                    y = 2.0 * x * y + y0
                    x = xtemp
                    iteration += 1

                if iteration == max_iter:
                    pixels[px, py] = (10, 10, 12)
                else:
                    # Smooth fractional coloring
                    smooth_i = iteration + 1 - math.log(max(1.0, math.log(x * x + y * y) / 2.0)) / math.log(2.0)
                    t = (smooth_i / max_iter) % 1.0
                    pixels[px, py] = _get_palette_color(t, palette)

        out_path = Path("mandelbrot.png")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, format="PNG")
        return {"image": out_path}


class GeometricPattern(Op):
    """Generate procedural geometric art with configurable palette."""

    TITLE = "Geometric Pattern"
    CATEGORY = "Image"
    CACHEABLE = True

    class Outputs(TypedDict):
        image: ImageFile

    def run(
        self,
        pattern: Literal["gradient_wave", "geometric_grid", "radial_rings", "checkerboard"] = "gradient_wave",
        width: Annotated[int, Range(200, 800)] = 400,
        height: Annotated[int, Range(200, 800)] = 400,
        primary_color: str = "#2680eb",
        secondary_color: str = "#00d8ff",
    ) -> Outputs:
        c1 = _parse_hex_color(primary_color, (38, 128, 235))
        c2 = _parse_hex_color(secondary_color, (0, 216, 255))

        img = Image.new("RGB", (width, height), (20, 20, 24))
        draw = ImageDraw.Draw(img)

        if pattern == "gradient_wave":
            for y in range(height):
                for x in range(0, width, 2):
                    t = (math.sin(x * 0.03) + math.cos(y * 0.03) + 2.0) / 4.0
                    r = int(c1[0] * (1 - t) + c2[0] * t)
                    g = int(c1[1] * (1 - t) + c2[1] * t)
                    b = int(c1[2] * (1 - t) + c2[2] * t)
                    draw.point((x, y), fill=(r, g, b))
                    draw.point((x + 1, y), fill=(r, g, b))

        elif pattern == "geometric_grid":
            step = 32
            for x in range(0, width, step):
                for y in range(0, height, step):
                    idx = (x // step + y // step) % 2
                    col = c1 if idx == 0 else c2
                    draw.rectangle([x + 2, y + 2, x + step - 2, y + step - 2], outline=col, width=2)
                    draw.line([x + 2, y + 2, x + step - 2, y + step - 2], fill=col, width=1)

        elif pattern == "radial_rings":
            center_x, center_y = width / 2.0, height / 2.0
            max_r = int(math.hypot(center_x, center_y))
            for r in range(10, max_r, 16):
                t = (r / max_r) % 1.0
                col = (
                    int(c1[0] * (1 - t) + c2[0] * t),
                    int(c1[1] * (1 - t) + c2[1] * t),
                    int(c1[2] * (1 - t) + c2[2] * t),
                )
                draw.ellipse(
                    [center_x - r, center_y - r, center_x + r, center_y + r],
                    outline=col,
                    width=3,
                )

        else:  # checkerboard
            tile = 40
            for x in range(0, width, tile):
                for y in range(0, height, tile):
                    if ((x // tile) + (y // tile)) % 2 == 0:
                        draw.rectangle([x, y, x + tile, y + tile], fill=c1)
                    else:
                        draw.rectangle([x, y, x + tile, y + tile], fill=c2)

        out_path = Path("pattern.png")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, format="PNG")
        return {"image": out_path}


class ImageFilterOp(Op):
    """Apply styling, convolution, or color filters to an image."""

    TITLE = "Image Filters & Effects"
    CATEGORY = "Image"
    CACHEABLE = True

    class Outputs(TypedDict):
        filtered_image: ImageFile

    def run(
        self,
        image: ImageFile,
        filter_type: Literal["grayscale", "sepia", "invert", "blur", "contour", "edge_enhance"] = "sepia",
    ) -> Outputs:
        src = Image.open(image).convert("RGB")

        if filter_type == "grayscale":
            out = ImageOps.grayscale(src).convert("RGB")
        elif filter_type == "sepia":
            gray = ImageOps.grayscale(src)
            out = ImageOps.colorize(gray, "#241808", "#f0d49e")
        elif filter_type == "invert":
            out = ImageOps.invert(src)
        elif filter_type == "blur":
            out = src.filter(ImageFilter.GaussianBlur(radius=4))
        elif filter_type == "contour":
            out = src.filter(ImageFilter.CONTOUR)
        elif filter_type == "edge_enhance":
            out = src.filter(ImageFilter.EDGE_ENHANCE_MORE)
        else:
            out = src

        out_path = Path("filtered.png")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out.save(out_path, format="PNG")
        return {"filtered_image": out_path}


class CardOrPoster(Op):
    """Compose an image into a framed studio card with badge, title, and subtitle."""

    TITLE = "Card & Poster Studio"
    CATEGORY = "Image"
    CACHEABLE = True

    class Outputs(TypedDict):
        card: ImageFile

    def run(
        self,
        image: ImageFile,
        title: str = "Plynx Studio",
        subtitle: str = "Generative Audio & Visuals",
        badge: str = "PROD",
        border_color: str = "#2680eb",
    ) -> Outputs:
        src = Image.open(image).convert("RGBA")
        base_w, base_h = src.size

        # Card framing dimensions
        pad = 24
        header_h = 44
        footer_h = 56
        card_w = base_w + pad * 2
        card_h = base_h + header_h + footer_h + pad * 2

        card = Image.new("RGBA", (card_w, card_h), (26, 26, 28, 255))
        draw = ImageDraw.Draw(card)
        accent = _parse_hex_color(border_color, (38, 128, 235))

        # Outer card frame border
        draw.rounded_rectangle([2, 2, card_w - 3, card_h - 3], radius=12, outline=accent, width=2)

        # Header tag / badge
        badge_w = max(40, len(badge) * 8 + 16)
        draw.rounded_rectangle([pad, pad, pad + badge_w, pad + 24], radius=4, fill=accent)
        draw.text((pad + 8, pad + 5), badge.upper(), fill=(255, 255, 255))

        # Paste core artwork
        art_y = pad + header_h
        card.paste(src, (pad, art_y), mask=src if src.mode == "RGBA" else None)
        draw.rectangle([pad - 1, art_y - 1, pad + base_w, art_y + base_h], outline=(60, 60, 60), width=1)

        # Footer Title & Subtitle
        foot_y = art_y + base_h + 12
        draw.text((pad, foot_y), title, fill=(240, 240, 240))
        draw.text((pad, foot_y + 20), subtitle, fill=(160, 160, 160))

        out_path = Path("card.png")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        card.save(out_path, format="PNG")
        return {"card": out_path}


__all__ = ["CardOrPoster", "GeometricPattern", "ImageFilterOp", "MandelbrotFractal"]
