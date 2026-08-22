#!/usr/bin/env python3
"""Prepare provider-page brand icons and the large percent mark."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PROJECT = Path(__file__).resolve().parents[3]
ASSET_DIR = PROJECT / "design" / "assets"
OUTPUT = PROJECT / "m5-dashboard" / "firmware" / "M5Dashboard" / "provider_brand_icons.h"
FONT = PROJECT / "m5-dashboard" / "NotoSansCJKsc-Bold.otf"
SIZE = 96
PERCENT_SIZE = 96
PERCENT_ASSET = ASSET_DIR / "provider-percent-96.png"


def prepare_icon(source: Path, destination: Path) -> None:
    with Image.open(source) as opened:
        image = opened.convert("RGBA").resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    indexed = image.quantize(
        colors=255,
        method=Image.Quantize.FASTOCTREE,
        dither=Image.Dither.FLOYDSTEINBERG,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    indexed.save(destination, format="PNG", optimize=True)


def validate_png(path: Path) -> None:
    with Image.open(path) as image:
        if image.size != (SIZE, SIZE):
            raise RuntimeError(f"{path} must be {SIZE} x {SIZE}")
        if image.mode != "P" or "transparency" not in image.info:
            raise RuntimeError(f"{path} must be an indexed PNG with transparency")


def rgb565_pixels(path: Path, background: tuple[int, int, int]) -> list[int]:
    validate_png(path)
    with Image.open(path) as opened:
        foreground = opened.convert("RGBA")
    base = Image.new("RGBA", (SIZE, SIZE), (*background, 255))
    flattened = Image.alpha_composite(base, foreground).convert("RGB")
    return [
        ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)
        for red, green, blue in flattened.get_flattened_data()
    ]


def array_source(name: str, data: list[int]) -> str:
    rows = []
    for offset in range(0, len(data), 10):
        rows.append("  " + ", ".join(f"0x{value:04x}" for value in data[offset : offset + 10]))
    return (
        f"static const uint16_t {name}[] PROGMEM = {{\n"
        + ",\n".join(rows)
        + "\n};\n"
        + f"static const unsigned int {name}_pixels = {len(data)};\n"
    )


def byte_array_source(name: str, data: bytes) -> str:
    rows = []
    for offset in range(0, len(data), 12):
        rows.append(
            "  " + ", ".join(f"0x{value:02x}" for value in data[offset : offset + 12])
        )
    return (
        f"static const uint8_t {name}[] PROGMEM = {{\n"
        + ",\n".join(rows)
        + "\n};\n"
        + f"static const unsigned int {name}_len = {len(data)};\n"
    )


def prepare_percent(destination: Path) -> tuple[int, int]:
    """Render a tight RGBA glyph so M5GFX can blend its antialiased edge."""
    font = ImageFont.truetype(str(FONT), size=PERCENT_SIZE)
    left, top, right, bottom = font.getbbox("%", anchor="ls")
    width = right - left
    height = bottom - top
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.text((-left, -top), "%", font=font, fill=(5, 5, 5, 255), anchor="ls")
    visible_bounds = image.getbbox()
    if visible_bounds is None:
        raise RuntimeError("Rendered percent glyph is empty")
    image = image.crop(visible_bounds)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="PNG", optimize=True)
    return image.size


def write_header(codex: Path, claude: Path, percent: Path, percent_size: tuple[int, int]) -> None:
    percent_width, percent_height = percent_size
    content = "\n".join(
        (
            "#pragma once",
            "",
            "#include <Arduino.h>",
            "",
            "// Provider brand icons prepared from the installed Codex and Claude desktop apps.",
            "// They are flattened onto their fixed page accents at build time so the device",
            "// can copy RGB565 pixels without running a PNG decoder during page transitions.",
            "",
            array_source(
                "codex_brand_icon_rgb565",
                rgb565_pixels(codex, (95, 103, 255)),
            ).rstrip(),
            "",
            array_source(
                "claude_brand_icon_rgb565",
                rgb565_pixels(claude, (226, 122, 86)),
            ).rstrip(),
            "",
            "// The 96 px percent mark is a tight RGBA PNG. Its per-pixel alpha keeps",
            "// the edge smooth across both the paper background and provider accent.",
            byte_array_source("provider_percent_96_png", percent.read_bytes()).rstrip(),
            f"static const unsigned int provider_percent_96_png_width = {percent_width};",
            f"static const unsigned int provider_percent_96_png_height = {percent_height};",
            "",
        )
    )
    OUTPUT.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--codex-source", type=Path)
    parser.add_argument("--claude-source", type=Path)
    args = parser.parse_args()

    codex = ASSET_DIR / "codex-brand-icon-96.png"
    claude = ASSET_DIR / "claude-brand-icon-96.png"
    if args.codex_source:
        prepare_icon(args.codex_source, codex)
    if args.claude_source:
        prepare_icon(args.claude_source, claude)
    if not codex.is_file() or not claude.is_file():
        raise RuntimeError("Pass both provider sources once, or keep the prepared design assets")
    percent_size = prepare_percent(PERCENT_ASSET)
    write_header(codex, claude, PERCENT_ASSET, percent_size)
    print(f"Prepared provider icons in {ASSET_DIR}")
    print(f"Generated {OUTPUT}")


if __name__ == "__main__":
    main()
