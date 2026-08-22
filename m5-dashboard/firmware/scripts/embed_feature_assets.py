#!/usr/bin/env python3
"""Prepare and embed the selected AI-alert and Obsidian-dice raster assets."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter


PROJECT = Path(__file__).resolve().parents[3]
ASSET_DIR = PROJECT / "design" / "assets"
OUTPUT = PROJECT / "m5-dashboard" / "firmware" / "M5Dashboard" / "feature_assets.h"
PAPER = (245, 234, 214)
CORAL = (255, 75, 67)


def remove_uniform_background(image: Image.Image, tolerance: int = 46) -> Image.Image:
    rgba = image.convert("RGBA")
    background = Image.new("RGBA", rgba.size, rgba.getpixel((0, 0)))
    difference = ImageChops.difference(rgba, background).convert("L")
    alpha = difference.point(lambda value: 0 if value <= tolerance else 255)
    rgba.putalpha(alpha)
    return rgba


def save_indexed(
    canvas: Image.Image,
    destination: Path,
    exact_corner_color: tuple[int, int, int] | None = None,
) -> None:
    # Reserve palette index 0 for transparent pixels. Pillow's direct RGBA
    # quantizer is free to put an opaque colour at index 0, so merely passing
    # transparency=0 can accidentally turn the asset background black while
    # punching holes into the artwork. Quantize the visible RGB colours to
    # indexes 0...254, then shift those indexes to 1...255 explicitly.
    visible = canvas.convert("RGB").quantize(
        colors=255,
        method=Image.Quantize.FASTOCTREE,
        # The feature art contains flat colour and a deliberately preblended
        # antialiased edge. Error-diffusion turns that edge into visible LCD
        # speckle, so keep the nearest palette colour instead.
        dither=Image.Dither.NONE,
    )
    visible_palette = visible.getpalette()[: 255 * 3]
    if exact_corner_color is not None:
        # FASTOCTREE can shift a flat field by one RGB step. Pin the palette
        # entry used by the square's corner so the opaque asset disappears
        # exactly into the firmware page background.
        corner_index = visible.getpixel((0, 0))
        palette_offset = corner_index * 3
        visible_palette[palette_offset : palette_offset + 3] = exact_corner_color
    palette = [0, 0, 0] + visible_palette
    palette.extend([0] * (768 - len(palette)))
    alpha = canvas.getchannel("A")
    indexed = Image.new("P", canvas.size, 0)
    indexed.putpalette(palette)
    indexed.putdata([
        0 if opacity <= 24 else colour + 1
        for colour, opacity in zip(
            visible.get_flattened_data(), alpha.get_flattened_data()
        )
    ])
    destination.parent.mkdir(parents=True, exist_ok=True)
    indexed.save(destination, format="PNG", optimize=True, transparency=0)


def prepare(source: Path, destination: Path, size: int, crop: bool) -> None:
    with Image.open(source) as opened:
        image = remove_uniform_background(opened)
    if crop:
        bbox = image.getbbox()
        if bbox is None:
            raise RuntimeError(f"{source} contains no visible asset")
        left, top, right, bottom = bbox
        padding = max(12, (right - left) // 24)
        left = max(0, left - padding)
        top = max(0, top - padding)
        right = min(image.width, right + padding)
        bottom = min(image.height, bottom + padding)
        image = image.crop((left, top, right, bottom))
    image.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(image, ((size - image.width) // 2, (size - image.height) // 2))
    save_indexed(canvas, destination)


def upscale_selected(source: Path, destination: Path, size: int) -> None:
    """Preserve the selected silhouette while preparing a native-size device asset."""
    with Image.open(source) as opened:
        source_alpha = opened.convert("RGBA").getchannel("A")
    # Reconstruct coverage at 4x and resolve it once into the exact page paper.
    # Keeping the result opaque lets M5GFX display the antialiased colour ramp
    # instead of reducing the edge to binary palette transparency. The square
    # itself is invisible because it uses the hardware-calibrated paper colour.
    supersample = 4
    alpha = source_alpha.resize(
        (size * supersample, size * supersample), Image.Resampling.LANCZOS
    ).filter(ImageFilter.GaussianBlur(2.6))
    alpha = alpha.resize((size, size), Image.Resampling.LANCZOS)
    coral = Image.new("RGB", (size, size), CORAL)
    paper = Image.new("RGB", (size, size), PAPER)
    image = Image.composite(coral, paper, alpha).convert("RGBA")
    save_indexed(image, destination, exact_corner_color=PAPER)


def png_bytes(path: Path, size: int) -> bytes:
    with Image.open(path) as image:
        if image.size != (size, size):
            raise RuntimeError(f"{path} must be {size} x {size}")
        if image.mode != "P" or "transparency" not in image.info:
            raise RuntimeError(f"{path} must be an indexed PNG with transparency")
    return path.read_bytes()


def array_source(name: str, data: bytes) -> str:
    rows = []
    for offset in range(0, len(data), 12):
        rows.append("  " + ", ".join(f"0x{value:02x}" for value in data[offset : offset + 12]))
    return (
        f"static const uint8_t {name}[] PROGMEM = {{\n"
        + ",\n".join(rows)
        + "\n};\n"
        + f"static const unsigned int {name}_len = {len(data)};\n"
    )


def write_header(burst_source: Path, burst: Path, dice: Path) -> None:
    content = "\n".join(
        (
            "#pragma once",
            "",
            "#include <Arduino.h>",
            "",
            "// Raster assets generated for the selected Signal Burst + Lucky Note direction.",
            array_source(
                "ai_hotspot_burst_source_png", png_bytes(burst_source, 220)
            ).rstrip(),
            "",
            array_source("ai_hotspot_burst_png", png_bytes(burst, 360)).rstrip(),
            "",
            array_source("obsidian_dice_png", png_bytes(dice, 150)).rstrip(),
            "",
        )
    )
    OUTPUT.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--burst-source", type=Path)
    parser.add_argument("--dice-source", type=Path)
    args = parser.parse_args()
    burst_source = ASSET_DIR / "ai-hotspot-burst-220.png"
    burst = ASSET_DIR / "ai-hotspot-burst-360.png"
    dice = ASSET_DIR / "obsidian-dice-150.png"
    if args.burst_source:
        prepare(args.burst_source, burst_source, 220, crop=False)
    upscale_selected(burst_source, burst, 360)
    if args.dice_source:
        prepare(args.dice_source, dice, 150, crop=True)
    if not burst.is_file() or not dice.is_file():
        raise RuntimeError("Pass both selected feature sources once, or keep the prepared assets")
    write_header(burst_source, burst, dice)
    print(f"Prepared feature assets in {ASSET_DIR}")
    print(f"Generated {OUTPUT}")


if __name__ == "__main__":
    main()
