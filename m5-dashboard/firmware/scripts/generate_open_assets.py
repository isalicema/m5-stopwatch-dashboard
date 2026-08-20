#!/usr/bin/env python3
"""Generate original, trademark-free dashboard icons as indexed PNG headers."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "M5Dashboard"
SIZE = 96

# Tableau categorical colors plus neutral UI colors. Palette index 0 is the
# only transparent entry so every embedded image remains PNG8 with tRNS.
COLORS = [
    (0, 0, 0),
    (78, 121, 167),   # Tableau blue
    (45, 74, 104),
    (247, 247, 242),
    (18, 24, 31),
    (89, 161, 79),    # Tableau green
    (237, 201, 72),   # Tableau yellow
    (225, 87, 89),    # Tableau red
    (242, 142, 43),   # Tableau orange
    (186, 176, 172),
    (118, 183, 178),  # Tableau cyan
]

GLYPHS = {
    "2": ("11110", "00001", "00001", "11110", "10000", "10000", "11111"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
}


def new_image() -> Image.Image:
    image = Image.new("P", (SIZE, SIZE), 0)
    palette = [channel for color in COLORS for channel in color]
    image.putpalette(palette + [0] * (768 - len(palette)))
    image.info["transparency"] = 0
    return image


def draw_label(draw: ImageDraw.ImageDraw, text: str, center_y: int, scale: int) -> None:
    gap = scale
    width = len(text) * 5 * scale + (len(text) - 1) * gap
    left = (SIZE - width) // 2
    top = center_y - (7 * scale) // 2
    for char in text:
        glyph = GLYPHS[char]
        for row, pattern in enumerate(glyph):
            for column, pixel in enumerate(pattern):
                if pixel == "1":
                    x = left + column * scale
                    y = top + row * scale
                    draw.rectangle((x, y, x + scale - 1, y + scale - 1), fill=3)
        left += 5 * scale + gap


def tile(color: int) -> Image.Image:
    image = new_image()
    ImageDraw.Draw(image).rounded_rectangle((5, 5, 90, 90), radius=20, fill=color)
    return image


def label_tile(text: str, color: int, scale: int) -> Image.Image:
    image = tile(color)
    draw_label(ImageDraw.Draw(image), text, 48, scale)
    return image


def claude_mark() -> Image.Image:
    image = new_image()
    draw_label(ImageDraw.Draw(image), "CL", 48, 6)
    return image


def robot_frame(mode: str, index: int) -> Image.Image:
    image = tile(1)
    draw = ImageDraw.Draw(image)
    offset = (-2, 1, -1, 2, 0, -2, 2, 0)[index] if mode == "failed" else 0

    # An original geometric robot face, deliberately unrelated to any vendor mascot.
    draw.line((48 + offset, 13, 48 + offset, 20), fill=3, width=3)
    draw.ellipse((44 + offset, 9, 52 + offset, 17), fill=6 if mode == "waiting" else 10)
    draw.rounded_rectangle((20 + offset, 21, 76 + offset, 63), radius=11, fill=2)
    draw.ellipse((31 + offset, 34, 39 + offset, 42), fill=3)
    draw.ellipse((57 + offset, 34, 65 + offset, 42), fill=3)
    draw.line((35 + offset, 52, 61 + offset, 52), fill=10, width=3)

    if mode == "work":
        scan_y = 27 + (index % 6) * 5
        draw.line((25, scan_y, 71, scan_y), fill=6, width=2)
        draw.ellipse((10 + index * 3, 68, 15 + index * 3, 73), fill=10)
    elif mode == "waiting":
        pulse = (index % 3) + 2
        for x in (34, 48, 62):
            draw.ellipse((x - pulse, 69 - pulse, x + pulse, 69 + pulse), fill=6)
    elif mode == "done":
        draw.ellipse((66, 62, 89, 85), fill=5)
        reach = min(10, 4 + index)
        draw.line((72, 74, 77, 79), fill=3, width=3)
        draw.line((77, 79, 77 + reach, 68), fill=3, width=3)
    elif mode == "failed":
        draw.ellipse((68, 62, 88, 82), fill=7)
        draw.line((78, 67, 78, 75), fill=3, width=3)
        draw.ellipse((76, 78, 80, 82), fill=3)
    else:
        draw_label(draw, "CX", 75, 3)
    return image


def png_bytes(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True, transparency=0)
    return output.getvalue()


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


def write_header(path: Path, comment: str, assets: Iterable[tuple[str, Image.Image]], tail: str = "") -> None:
    body = ["#pragma once", "", "#include <Arduino.h>", "", comment, ""]
    for name, image in assets:
        body.append(array_source(name, png_bytes(image)))
    if tail:
        body.append(tail.rstrip())
    path.write_text("\n".join(body).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    idle = robot_frame("idle", 0)
    write_header(
        OUTPUT / "icons.h",
        "// Original generic P2S and CX symbols generated by generate_open_assets.py.",
        (("bambu_logo_png", label_tile("P2S", 5, 4)), ("codex_icon_png", idle)),
    )
    write_header(
        OUTPUT / "claude_icon.h",
        "// Original generic CL symbol generated by generate_open_assets.py.",
        (("claude_icon_png", label_tile("CL", 8, 6)),),
    )

    frames: list[tuple[str, Image.Image]] = [("claude_mark_png", claude_mark())]
    frames.append(("codex_pet_idle_0_png", idle))
    for mode, count in (("work", 6), ("waiting", 6), ("done", 6), ("failed", 8)):
        frames.extend((f"codex_pet_{mode}_{index}_png", robot_frame(mode, index)) for index in range(count))

    tail = """
struct DashboardPngFrame {
  const uint8_t *data;
  uint32_t length;
};

static constexpr DashboardPngFrame codex_pet_idle_frames[] = {
  {codex_pet_idle_0_png, codex_pet_idle_0_png_len},
};

static constexpr DashboardPngFrame codex_pet_work_frames[] = {
  {codex_pet_work_0_png, codex_pet_work_0_png_len},
  {codex_pet_work_1_png, codex_pet_work_1_png_len},
  {codex_pet_work_2_png, codex_pet_work_2_png_len},
  {codex_pet_work_3_png, codex_pet_work_3_png_len},
  {codex_pet_work_4_png, codex_pet_work_4_png_len},
  {codex_pet_work_5_png, codex_pet_work_5_png_len},
};

static constexpr DashboardPngFrame codex_pet_waiting_frames[] = {
  {codex_pet_waiting_0_png, codex_pet_waiting_0_png_len},
  {codex_pet_waiting_1_png, codex_pet_waiting_1_png_len},
  {codex_pet_waiting_2_png, codex_pet_waiting_2_png_len},
  {codex_pet_waiting_3_png, codex_pet_waiting_3_png_len},
  {codex_pet_waiting_4_png, codex_pet_waiting_4_png_len},
  {codex_pet_waiting_5_png, codex_pet_waiting_5_png_len},
};

static constexpr DashboardPngFrame codex_pet_done_frames[] = {
  {codex_pet_done_0_png, codex_pet_done_0_png_len},
  {codex_pet_done_1_png, codex_pet_done_1_png_len},
  {codex_pet_done_2_png, codex_pet_done_2_png_len},
  {codex_pet_done_3_png, codex_pet_done_3_png_len},
  {codex_pet_done_4_png, codex_pet_done_4_png_len},
  {codex_pet_done_5_png, codex_pet_done_5_png_len},
};

static constexpr DashboardPngFrame codex_pet_failed_frames[] = {
  {codex_pet_failed_0_png, codex_pet_failed_0_png_len},
  {codex_pet_failed_1_png, codex_pet_failed_1_png_len},
  {codex_pet_failed_2_png, codex_pet_failed_2_png_len},
  {codex_pet_failed_3_png, codex_pet_failed_3_png_len},
  {codex_pet_failed_4_png, codex_pet_failed_4_png_len},
  {codex_pet_failed_5_png, codex_pet_failed_5_png_len},
  {codex_pet_failed_6_png, codex_pet_failed_6_png_len},
  {codex_pet_failed_7_png, codex_pet_failed_7_png_len},
};
"""
    write_header(
        OUTPUT / "codex_pet_frames.h",
        "// Original generic CX/CL assets generated by generate_open_assets.py.",
        frames,
        tail,
    )


if __name__ == "__main__":
    main()
