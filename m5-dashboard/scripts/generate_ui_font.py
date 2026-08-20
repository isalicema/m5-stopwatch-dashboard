#!/usr/bin/env python3
"""Build the embedded Noto Sans SC font used by the round-screen UI.

The M5GFX VLW reader expects a big-endian metrics table followed by one
8-bit alpha bitmap per glyph.  The generated binary stays in mapped flash;
PlatformIO expands it into a generated C++ header immediately before build.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


FONT_NAME = "Noto Sans CJK SC Regular"
FONT_MARKER = "M5DASH_FONT_NOTO_SANS_CJK_SC_16_V1"
DEFAULT_SIZE = 16


def gb2312_characters() -> list[str]:
    characters = {chr(codepoint) for codepoint in range(0x21, 0x7F)}
    for lead in range(0xA1, 0xF8):
        for trail in range(0xA1, 0xFF):
            try:
                decoded = bytes((lead, trail)).decode("gb2312")
            except UnicodeDecodeError:
                continue
            characters.update(decoded)
    # These UI punctuation characters are outside the strict GB2312 mapping.
    characters.update("·—…“”‘’•→←↕⌄")
    return sorted(characters, key=ord)


def render_glyph(font: ImageFont.FreeTypeFont, character: str) -> tuple[bytes, tuple[int, ...]]:
    left, top, right, bottom = font.getbbox(character, anchor="ls")
    width = max(0, right - left)
    height = max(0, bottom - top)
    advance = max(1, round(font.getlength(character)))
    if width == 0 or height == 0:
        bitmap = b""
    else:
        image = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(image)
        draw.text((-left, -top), character, font=font, fill=255, anchor="ls")
        bitmap = image.tobytes()
    metrics = (
        ord(character),
        height,
        width,
        advance,
        -top,
        left & 0xFFFFFFFF,
        0,
    )
    return bitmap, metrics


def build_vlw(
    font_path: Path, size: int, *, require_noto_identity: bool = True
) -> tuple[bytes, dict[str, object]]:
    font = ImageFont.truetype(str(font_path), size=size)
    family, style = font.getname()
    identity_verified = "Noto Sans CJK SC" in family and "Regular" in style
    if require_noto_identity and not identity_verified:
        raise SystemExit(
            f"Font identity mismatch: expected Noto Sans CJK SC Regular, got {family} {style}"
        )
    ascent, descent = font.getmetrics()
    characters = gb2312_characters()
    records: list[bytes] = []
    bitmaps: list[bytes] = []
    for character in characters:
        bitmap, metrics = render_glyph(font, character)
        records.append(struct.pack(">7I", *metrics))
        bitmaps.append(bitmap)

    header = struct.pack(
        ">6I",
        len(characters),
        11,
        ascent + descent,
        0,
        ascent,
        descent,
    )
    data = header + b"".join(records) + b"".join(bitmaps)
    encoded_codepoints = [
        struct.unpack_from(">I", data, 24 + index * 28)[0]
        for index in range(len(characters))
    ]
    if encoded_codepoints != sorted(encoded_codepoints):
        raise SystemExit("VLW glyph records are not sorted by Unicode codepoint")
    required = set("麦克风正在收音对话你任务关闭")
    if not required.issubset(characters):
        raise SystemExit("VLW font is missing required UI probe glyphs")
    manifest: dict[str, object] = {
        "font_name": f"{family} {style}",
        "font_marker": FONT_MARKER if identity_verified else "M5DASH_FONT_DEVELOPMENT_ONLY",
        "identity_verified": identity_verified,
        "pixel_size": size,
        "glyph_count": len(characters),
        "first_codepoint": ord(characters[0]),
        "last_codepoint": ord(characters[-1]),
        "vlw_size": len(data),
        "vlw_sha256": hashlib.sha256(data).hexdigest(),
        "source_file": font_path.name,
        "source_sha256": hashlib.sha256(font_path.read_bytes()).hexdigest(),
        "required_probe_glyphs": "".join(sorted(required, key=ord)),
    }
    return data, manifest


def write_preview(path: Path, font_path: Path) -> None:
    image = Image.new("RGB", (900, 520), (7, 8, 13))
    draw = ImageDraw.Draw(image)
    title = ImageFont.truetype(str(font_path), size=42)
    body = ImageFont.truetype(str(font_path), size=32)
    small = ImageFont.truetype(str(font_path), size=25)
    draw.text((70, 55), "Codex", font=title, fill=(246, 246, 249))
    draw.rounded_rectangle((410, 120, 825, 215), 28, fill=(10, 132, 255))
    draw.text((450, 145), "把界面重新优化一下", font=body, fill=(255, 255, 255))
    draw.rounded_rectangle((70, 240, 690, 365), 28, fill=(38, 38, 42))
    draw.text((105, 265), "已经换成真正的思源黑体，", font=body, fill=(248, 248, 250))
    draw.text((105, 310), "不是旧的内置中文字库。", font=body, fill=(248, 248, 250))
    draw.text((280, 430), "正在收音  ·  再按一次关闭麦克风", font=small, fill=(176, 176, 184))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def main() -> int:
    project = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Generate the embedded Noto Sans SC M5GFX font")
    parser.add_argument("font", type=Path, help="Path to NotoSansCJKsc-Regular.otf")
    parser.add_argument("--size", type=int, default=DEFAULT_SIZE)
    parser.add_argument(
        "--output",
        type=Path,
        default=project / "firmware/M5Dashboard/ui_font_noto_sans_sc_16.vlw",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=project / "firmware/M5Dashboard/ui_font_noto_sans_sc_16.json",
    )
    parser.add_argument(
        "--preview",
        type=Path,
        default=project / "design-preview/font-proof-noto-sans-sc.png",
    )
    args = parser.parse_args()

    font_path = args.font.expanduser().resolve()
    if not font_path.is_file():
        raise SystemExit(f"Font file does not exist: {font_path}")
    if font_path.name != "NotoSansCJKsc-Regular.otf":
        raise SystemExit("Expected the official file named NotoSansCJKsc-Regular.otf")

    vlw, manifest = build_vlw(font_path, args.size)
    manifest["embedded_storage"] = "direct_flash_vlw"
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_bytes(vlw)
    args.manifest.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.manifest.resolve().write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_preview(args.preview.resolve(), font_path)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
